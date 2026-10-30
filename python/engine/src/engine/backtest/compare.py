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

`runs` pairs any two stored runs the same way (`engine compare`), e.g. Rung 2 against Rung 1 or
`shrink_toward: tier` against `zero` (TASK-036), and scores each one's cover probabilities on
the shared games, graded as its own spec says: the Brier score and the calibration bins, so
`distribution: empirical` can be judged against `normal` on the same games (TASK-038).
"""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from engine.backtest import bootstrap, harness
from engine.backtest import metrics as m
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


@dataclass(frozen=True, slots=True)
class RunVersus:
    """`engine compare A B` (TASK-036): two stored runs on the games both scored."""

    games: int
    only_a: int  # games A scored and B didn't, left out
    only_b: int
    mae_a: float
    mae_b: float
    difference: bootstrap.Interval  # A's absolute error minus B's: below zero favors A

    @property
    def verdict(self) -> str:
        if self.difference.beats:
            return "A beats B"
        if self.difference.low > 0:
            return "B beats A"
        return "no clear difference (the interval includes zero)"


def runs(a: Sequence[Mapping[str, Any]], b: Sequence[Mapping[str, Any]]) -> RunVersus:
    """Pair two runs by game, e.g. Rung 2 against Rung 1, or one spec against a variant of it
    (04 § 9.5)."""
    in_b = {r["game_source_id"] for r in b}
    in_a = {r["game_source_id"] for r in a}
    shared = in_a & in_b
    if not shared:
        raise ValueError("the runs share no game")
    mine = [r for r in a if r["game_source_id"] in shared]
    theirs = [r for r in b if r["game_source_id"] in shared]
    return RunVersus(
        games=len(shared),
        only_a=len(in_a - in_b),
        only_b=len(in_b - in_a),
        mae_a=_mae(mine),
        mae_b=_mae(theirs),
        difference=bootstrap.compare(mine, theirs),
    )


@dataclass(frozen=True, slots=True)
class CoverScores:
    """One run's cover probabilities, graded with its own spec, pushes left out."""

    distribution: str
    brier: float | None
    calibration: m.Calibration
    picks: m.Record  # qualifying picks against the close, under each season's pick rules


def cover_scores(
    rows: Sequence[Mapping[str, Any]], spec: ModelSpec, choices: Mapping[int, Choices]
) -> CoverScores:
    games = m.grade_rows(rows, spec, choices)
    calibration = m.calibration((g.prob, g.result) for g in games)
    picks = m.Record.of(g.result for g in games if g.pick is not None)
    return CoverScores(spec.distribution, m.cover_brier(games), calibration, picks)


def bin_label(b: m.CalibrationBin) -> str:
    """ASCII, for a cp1252 console: `50-52.5%`, `65%+`."""
    low = f"{b.low * 100:g}"
    return f"{low}%+" if b.high is None else f"{low}-{b.high * 100:g}%"
