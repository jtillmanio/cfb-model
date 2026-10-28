"""The backtest leakage tests (TASK-030, docs/02-architecture.md › Testing strategy › Model /
backtest): changing a game after week N can't change a prediction for week N or earlier. A week-5
game finishes after week 5's `as_of`, so it may move week 6's predictions and no earlier ones.
"""

from __future__ import annotations

import io
import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq
import pytest
from lake_fixture import backtest_game_id, engine, write_backtest_seasons, write_preseason

from engine.ingest.lake import LocalLake
from engine.sports.cfb import preseason
from engine.transform import rebuild

KANSAS_GAME = "401756847"  # Kansas-Fresno State
PREDICTED = ("pred_margin", "margin_sd", "home_win_prob")
SPEC = {
    "base": "power",
    "hyperparameters": {"margin_cap": {"tune": [14, 28]}, "recency_half_life_weeks": 6},
    "picks": {"min_edge_pts": 3.0, "min_prob": 0.55, "tiers": {"A": 5.0, "B": 3.5, "C": 2.5}},
}


def backtest(
    root: Path, spec: str, monkeypatch: pytest.MonkeyPatch, rescore: Any = None
) -> dict[str, dict[str, Any]]:
    """Run the 2023 backtest, tuned on 2022, on a fresh fixture lake; its rows by game."""
    lake = LocalLake(root)
    write_backtest_seasons(lake, rescore=rescore)
    rebuild(lake)
    monkeypatch.setenv("LAKE_URI", str(root))
    argv = ["backtest", "--spec", spec, "--seasons", "2023", "--tune-from", "2022"]
    assert engine(*argv, "--model", "stub") == 0
    (key,) = [k for k in lake.walk("backtests") if k.endswith("/predictions.parquet")]
    rows = pq.read_table(io.BytesIO(lake.read(key))).to_pylist()
    return {r["game_source_id"]: r for r in rows}


def test_changing_a_week5_game_leaves_predictions_through_week5_unchanged(
    empty_lake: LocalLake, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec = tmp_path / "spec.json"
    spec.write_text(json.dumps(SPEC), "utf-8")
    before = backtest(tmp_path / "before", str(spec), monkeypatch)
    # Kansas-Fresno State, week 5 of 2023: 3-45 and a poor offense instead.
    after = backtest(
        tmp_path / "after", str(spec), monkeypatch, rescore=(2023, "regular", 5, KANSAS_GAME)
    )

    assert after.keys() == before.keys()
    changed = backtest_game_id(2023, "regular", 5, KANSAS_GAME)
    assert after[changed]["margin"] == 3 - 45 != before[changed]["margin"]
    later = []
    for game, row in before.items():
        predicted = {c: row[c] for c in PREDICTED}
        moved = {c: after[game][c] for c in PREDICTED}
        if row["season_type"] == "regular" and row["week"] <= 5:
            assert moved == predicted, game
        elif moved != predicted:
            later.append(game)
    assert backtest_game_id(2023, "regular", 6, KANSAS_GAME) in later


# TASK-037 AC-2: every preseason value a prior reads is checked against its source's assumed
# publication time (engine.sports.cfb.preseason) before the season's first as_of.

PRIOR_SPEC = {
    "base": "efficiency",
    "inputs": [{"stat": "epa_per_play"}, {"stat": "success_rate"}],
    "hyperparameters": {"ridge_alpha": 2},
    "shrink_toward": "tier",
    "prior": {
        "components": ["last_season", "returning_production", "talent", "recruiting"],
        "regression": 0.2,
        "decay": {"type": "fitted"},
    },
    "picks": SPEC["picks"],
}


def prior_backtest(root: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> int:
    lake = LocalLake(root)
    write_backtest_seasons(lake, seasons=(2021, 2022, 2023))
    write_preseason(lake, tuple(range(2017, 2025)))
    rebuild(lake)
    monkeypatch.setenv("LAKE_URI", str(root))
    spec = tmp_path / "prior.json"
    spec.write_text(json.dumps(PRIOR_SPEC), "utf-8")
    return engine("backtest", "--spec", str(spec), "--seasons", "2023", "--tune-from", "2022")


def test_a_backtest_with_preseason_priors_runs(
    empty_lake: LocalLake, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert prior_backtest(tmp_path / "lake", tmp_path, monkeypatch) == 0


@pytest.mark.parametrize("source", sorted(preseason.SOURCES))
def test_a_preseason_value_published_after_the_season_starts_stops_the_run(
    source: str,
    empty_lake: LocalLake,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Loosen the rule: each season's prior also reads this source's next season, which is
    # assumed published after the season starts.
    loose = preseason.SOURCES[source]
    later = replace(loose, seasons=lambda y: (*loose.seasons(y), max(loose.seasons(y)) + 1))
    monkeypatch.setitem(preseason.SOURCES, source, later)

    assert prior_backtest(tmp_path / "lake", tmp_path, monkeypatch) == 1

    err = capsys.readouterr()
    assert f"{source} of season" in err.out + err.err
    assert not list(LocalLake(tmp_path / "lake").walk("backtests"))
