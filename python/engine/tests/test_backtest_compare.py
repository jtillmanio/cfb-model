"""`engine backtest --compare baselines` (TASK-033 AC-4; docs/04-model.md § 9.5-9.6, D-133):
Rung 1 and every Rung 0 baseline on the same games, each baseline run with Rung 1's settings, in
one report with the paired bootstrap against the two bars.
"""

from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq
import pytest
from lake_fixture import engine, write_backtest_seasons, write_benchmarks

from engine.backtest import bootstrap, holdout
from engine.backtest.baselines import HINDSIGHT, UNRATED, UNSEEN
from engine.backtest.compare import BASELINES, versus
from engine.ingest.lake import LocalLake
from engine.transform import rebuild

PICKS = {"min_edge_pts": 3.0, "min_prob": 0.55, "tiers": {"A": 5.0, "B": 3.5, "C": 2.5}}
SPEC = {
    "base": "power",
    "hyperparameters": {"margin_cap": {"tune": [14, 28]}, "recency_half_life_weeks": 4},
    "prior": {
        "components": ["last_season"],
        "regression": {"tune": [0.2, 0.5]},
        "decay": {"type": "linear", "zero_at_week": 4},
    },
    "picks": PICKS,
}
LABELS = {
    "home_field": "Home field only",
    "last_season": "Last season carried over",
    "closing_line": "Closing line",
    "sp": "SP+",
    "fpi": "FPI",
}


@pytest.fixture
def backtest_lake(empty_lake: LocalLake) -> LocalLake:
    write_backtest_seasons(empty_lake)
    write_benchmarks(empty_lake)
    rebuild(empty_lake)
    return empty_lake


def spec_file(tmp_path: Path) -> str:
    path = tmp_path / "spec.json"
    path.write_text(json.dumps(SPEC), "utf-8")
    return str(path)


def runs(lake: LocalLake) -> dict[str, tuple[dict[str, Any], list[dict[str, Any]]]]:
    """Each written run's `run.json` and rows, by model."""
    out = {}
    for key in lake.walk("backtests"):
        if key.endswith("/run.json"):
            meta = json.loads(lake.read(key))
            data = lake.read(key.replace("run.json", "predictions.parquet"))
            out[meta["model"]] = (meta, pq.read_table(io.BytesIO(data)).to_pylist())
    return out


def table_row(text: str, label: str) -> list[str]:
    (line,) = [ln for ln in text.splitlines() if ln.startswith(f"| {label} |")]
    return [cell.strip() for cell in line.strip("|").split("|")]


def test_compare_baselines_writes_one_report(backtest_lake: LocalLake, tmp_path: Path) -> None:
    report = tmp_path / "report"
    argv = ["backtest", "--spec", spec_file(tmp_path), "--seasons", "2023", "--tune-from", "2022"]
    assert engine(*argv, "--compare", "baselines", "--report", str(report)) == 0

    written = runs(backtest_lake)
    assert written.keys() == {"power", *BASELINES}
    power_meta, power_rows = written["power"]
    games = [r["game_source_id"] for r in power_rows]
    for name in BASELINES:
        meta, rows = written[name]
        # Same games, and Rung 1's settings, not a grid of the baseline's own.
        assert [r["game_source_id"] for r in rows] == games, name
        assert meta["choices"] == power_meta["choices"], name

    text = (report / "report.md").read_text("utf-8")
    assert (report / "report.html").exists()
    assert "## Comparison with the baselines" in text
    for name, label in LABELS.items():
        row = table_row(text, label)
        rows = written[name][1]
        kept = [r for r in rows if not {HINDSIGHT, UNRATED} & set((r["note"] or "").split("; "))]
        ids = {r["game_source_id"] for r in kept}
        mine = [r for r in power_rows if r["game_source_id"] in ids]
        interval = bootstrap.compare(mine, kept)
        assert row[1] == str(len(kept)), name
        assert row[4] == f"{interval.estimate:+.2f} ({interval.low:+.2f} to {interval.high:+.2f})"
        if name in ("home_field", "last_season"):
            assert row[5] == ("beats it" if interval.beats else "doesn't beat it"), name
        else:
            assert row[5] == "reported only", name
        hindsight = sum(HINDSIGHT in (r["note"] or "") for r in rows)
        assert (f"hindsight benchmark dropped: {hindsight}" in row[6]) == (hindsight > 0), name
    # The fixture's benchmarks include a season-final pull, so SP+ and FPI lose rows to it.
    assert "hindsight benchmark dropped" in table_row(text, "FPI")[6]


def test_versus_counts_what_it_drops_and_keeps() -> None:
    def row(game: str, week: int, pred: float, margin: int, note: str | None = None) -> Any:
        return {
            "season": 2023,
            "season_type": "regular",
            "week": week,
            "game_source_id": game,
            "pred_margin": pred,
            "margin": margin,
            "note": note,
        }

    model = [row("a", 1, 3, 7), row("b", 1, -2, -10), row("c", 2, 0, 4), row("d", 2, 1, 1)]
    baseline = [
        row("a", 1, 0, 7),
        row("b", 1, 0, -10, HINDSIGHT),
        row("c", 2, 0, 4, f"{HINDSIGHT}; {UNRATED}"),
        row("d", 2, 0, 1, UNSEEN),
    ]
    v = versus("sp", model, baseline)
    assert v.games == 2
    assert v.dropped == {HINDSIGHT: 2, UNRATED: 1}
    assert v.unseen == 1
    assert v.mae == pytest.approx((7 + 1) / 2)
    assert v.model_mae == pytest.approx((4 + 0) / 2)  # games a and d only
    assert not v.bar

    with pytest.raises(ValueError, match="model's games"):
        versus("sp", model, baseline[:3])

    # Only season-final benchmarks staged: nothing to compare, and the row says why.
    hindsight = [{**r, "note": HINDSIGHT} for r in baseline]
    none = versus("fpi", model, hindsight)
    assert (none.games, none.mae, none.difference, none.beats) == (0, None, None, False)
    assert none.dropped == {HINDSIGHT: 4}


@pytest.mark.parametrize("flags", [["--model", "stub"], ["--holdout", "--reason", "a look"]])
def test_compare_runs_the_specs_own_model_on_validation_seasons_only(
    flags: list[str], empty_lake: LocalLake, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write_backtest_seasons(empty_lake, (2023, 2024))
    rebuild(empty_lake)
    seasons = "2024" if "--holdout" in flags else "2023"
    argv = ["backtest", "--spec", spec_file(tmp_path), "--seasons", seasons, "--tune-from", "2023"]
    assert engine(*argv, "--compare", "baselines", *flags) == 2
    assert "--compare" in capsys.readouterr().err
    assert empty_lake.walk("backtests") == []
    assert holdout.count(empty_lake) == 0


# `engine compare` (TASK-036): two stored runs on the same games.


def test_engine_compare_pairs_two_stored_runs_by_game(
    backtest_lake: LocalLake, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from engine.backtest.compare import runs as compare_runs

    argv = ["--seasons", "2023", "--tune-from", "2022"]
    assert engine("backtest", "--spec", spec_file(tmp_path), *argv) == 0
    other = tmp_path / "home.json"
    other.write_text(json.dumps({**SPEC, "home_field": 10.0}), "utf-8")
    assert engine("backtest", "--spec", str(other), *argv) == 0
    folders = sorted({k.rpartition("/")[0] for k in backtest_lake.walk("backtests")})
    first, second = (
        pq.read_table(io.BytesIO(backtest_lake.read(f"{f}/predictions.parquet"))).to_pylist()
        for f in folders
    )
    capsys.readouterr()

    assert engine("compare", *folders) == 0

    out = capsys.readouterr().out
    expected = bootstrap.compare(first, second)
    v = compare_runs(first, second)
    assert v.games == len(first) == len(second)
    assert v.difference == expected
    assert f"A - B: {expected.estimate:+.3f} [{expected.low:+.3f}, {expected.high:+.3f}]" in out
    assert f"{len(first)} shared games (0 only in A, 0 only in B left out)" in out
    assert v.verdict in out

    # A game only one run scored is left out and counted.
    trimmed = compare_runs(first, second[1:])
    assert (trimmed.games, trimmed.only_a, trimmed.only_b) == (len(first) - 1, 1, 0)


def test_engine_compare_refuses_a_missing_run(backtest_lake: LocalLake) -> None:
    assert engine("compare", "backtests/nope", "backtests/nor-this") == 2
