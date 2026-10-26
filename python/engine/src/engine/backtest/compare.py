"""`engine backtest --compare baselines` (TASK-033; docs/04-model.md § 9.5-9.6, D-091, D-133):
the model and every Rung 0 baseline scored on the same games, each against the model.

Each baseline runs with the settings the model's own run chose for each season (`run(...,
choices=)`), so `last_season` and `home_field` carry the model as it was actually scored, and no
baseline re-tunes a grid it ignores. A baseline's rows pass through `baselines.comparable()`
first: a hindsight benchmark or a game with an unrated team never counts as a baseline beaten,
and the comparison says how many it left out, and how many `unseen team` rows it kept.

The model beats a baseline when the week-level paired bootstrap's 95% interval of its absolute
error minus the baseline's lies entirely below zero (`bootstrap.compare`). The bars of 04 § 9.6
for Rung 1 are home field only and last season carried over; the closing line and SP+/FPI are
reported alongside.
"""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from engine.backtest import bootstrap, harness
from engine.backtest.baselines import HINDSIGHT, UNRATED, UNSEEN, comparable
from engine.backtest.harness import BacktestRun, Choices, History, Row
from engine.core.spec import ModelSpec

BASELINES = ("home_field", "last_season", "closing_line", "sp", "fpi")
BARS = frozenset({"home_field", "last_season"})  # what Rung 1 must beat (04 § 9.6, Phase 2)


@dataclass(frozen=True, slots=True)
class Versus:
    """The model against one baseline, on the games both may be compared on."""

    name: str
    games: int  # 0 when every row was left out (e.g. only season-final benchmarks are staged)
    mae: float | None  # the baseline's
    model_mae: float | None  # the model's, on the same games
    difference: bootstrap.Interval | None  # the model's absolute error minus the baseline's
    dropped: Mapping[str, int]  # note -> rows left out (hindsight benchmark, unrated team)
    unseen: int  # `unseen team` rows kept
    bar: bool  # one of 04 § 9.6's bars to beat

    @property
    def beats(self) -> bool:
        return self.difference is not None and self.difference.beats


def run_baselines(
    spec: ModelSpec,
    history: History,
    seasons: Sequence[int],
    tune_from: int,
    choices: Mapping[int, Choices],
) -> dict[str, BacktestRun]:
    """Each baseline's run, with the model's chosen settings for each season."""
    from engine.backtest import MODELS

    return {
        name: harness.run(spec, MODELS[name], history, seasons, tune_from, choices=choices)
        for name in BASELINES
    }


def _mae(rows: Sequence[Mapping[str, Any]]) -> float:
    return math.fsum(abs(r["pred_margin"] - r["margin"]) for r in rows) / len(rows)


def _notes(row: Mapping[str, Any]) -> set[str]:
    note: str = row.get("note") or ""
    return {n for n in note.split("; ") if n}


def versus(name: str, model: Sequence[Row], baseline: Sequence[Row]) -> Versus:
    games = {r["game_source_id"] for r in model}
    if games != {r["game_source_id"] for r in baseline} or len(baseline) != len(model):
        raise ValueError(f"{name} wasn't scored on the model's games")
    kept = comparable(baseline)
    ids = {r["game_source_id"] for r in kept}
    left_out = [r for r in baseline if r["game_source_id"] not in ids]
    dropped = Counter(n for r in left_out for n in _notes(r) & {HINDSIGHT, UNRATED})
    mine = [r for r in model if r["game_source_id"] in ids]
    return Versus(
        name=name,
        games=len(mine),
        mae=_mae(kept) if kept else None,
        model_mae=_mae(mine) if mine else None,
        difference=bootstrap.compare(mine, kept) if kept else None,
        dropped=dict(sorted(dropped.items())),
        unseen=sum(UNSEEN in _notes(r) for r in kept),
        bar=name in BARS,
    )


def compare(model: Sequence[Row], runs: Mapping[str, BacktestRun]) -> list[Versus]:
    return [versus(name, model, run.rows) for name, run in runs.items()]
