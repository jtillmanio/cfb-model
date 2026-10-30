"""`engine backtest … --report DIR` (TASK-031, docs/04-model.md § 9.4): a markdown and an HTML
report of every § 9.4 row, each gate marked, and golden metrics on the TASK-030 fixture run.

The golden file changes only in a commit whose message says why. To regenerate it, run this test
with `UPDATE_GOLDEN=1` and say in the commit why the numbers moved.
"""

from __future__ import annotations

import dataclasses
import io
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

import pytest
from lake_fixture import engine, write_backtest_seasons
from test_backtest_golden import SPEC

from engine.backtest import metrics as m
from engine.backtest import report
from engine.core.spec import ModelSpec
from engine.ingest.lake import LocalLake
from engine.transform import rebuild

GOLDEN = Path(__file__).parent / "fixtures" / "backtest_report_golden.json"

# One label per § 9.4 row the fixture run supports (the holdout row only shows when opened).
ROWS = (
    "Margin accuracy vs the closing line",
    "MAE gap (model − closing)",
    "Model RMSE",
    "ATS vs the closing line",
    "Win %, 95% interval",
    "Edge trend",
    "Consistency",
    "Calibration",
    "Opening line and CLV",
    "Average CLV (pts)",
    "ROI",
    "Win % by pick bucket",
    "Contest top 4",
    "Win probability",
    "Brier score, model",
    "Breakdowns",
    "Week of season",
    "Spread size (closing, either side)",
    "Favorite or underdog (the side the model likes)",
    "Postseason on its own",
)
GATES = ("Margin MAE vs the closing line", "ATS win % vs closing", "Edge trend", "Consistency",
         "Calibration")


@pytest.fixture
def backtest_lake(empty_lake: LocalLake) -> LocalLake:
    write_backtest_seasons(empty_lake)
    rebuild(empty_lake)
    return empty_lake


def _rounded(value: Any) -> Any:
    """10 significant digits, as the harness golden: libm differs in the last bits by platform."""
    if isinstance(value, float):
        return float(f"{value:.10g}")
    if isinstance(value, dict):
        return {k: _rounded(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_rounded(v) for v in value]
    return value


def golden_text(metrics: m.Metrics) -> str:
    data = {
        "gates": {name: [g.status, g.detail] for name, g in metrics.gates},
        "metrics": dataclasses.asdict(metrics),
    }
    return json.dumps(_rounded(data), indent=2, ensure_ascii=False) + "\n"


def test_the_report_has_every_row_and_marks_every_gate(
    backtest_lake: LocalLake, tmp_path: Path
) -> None:
    spec = tmp_path / "spec.json"
    spec.write_text(json.dumps(SPEC), "utf-8")
    out = tmp_path / "report"
    argv = ["backtest", "--spec", str(spec), "--seasons", "2023", "--tune-from", "2022"]

    assert engine(*argv, "--model", "stub", "--report", str(out)) == 0

    md = (out / "report.md").read_text("utf-8")
    page = (out / "report.html").read_text("utf-8")
    for label in ROWS:
        assert label in md, label
        assert f">{label}<" in page.replace("&#x27;", "'"), label
    for gate in GATES:
        (line,) = [row for row in md.splitlines() if row.startswith(f"| {gate} |")]
        assert re.match(rf"\| {re.escape(gate)} \| (PASS|FAIL|n/a) \| ", line), line
    assert "| Holdout |" not in md  # a gate only when the run opened the holdout
    assert "Pick rules by season" not in md  # only when the spec tunes its pick rules
    assert page.startswith("<!doctype html>")


def test_the_report_lists_each_season_s_tuned_pick_rules(
    empty_lake: LocalLake, tmp_path: Path
) -> None:
    """AC-6 (TASK-039): each scored season's chosen pick rules and its tuning-season picks."""
    write_backtest_seasons(empty_lake, (2021, 2022, 2023))
    rebuild(empty_lake)
    picks = {
        **SPEC["picks"],
        "market_shrinkage_k": {"tune": [0.5, 1.0]},
        "min_edge_pts": {"tune": [1.0, 3.0]},
    }
    spec = tmp_path / "spec.json"
    spec.write_text(json.dumps({**SPEC, "picks": picks}), "utf-8")
    out = tmp_path / "report"
    argv = ["backtest", "--spec", str(spec), "--seasons", "2022-2023", "--tune-from", "2021"]

    assert engine(*argv, "--model", "stub", "--report", str(out)) == 0

    md = (out / "report.md").read_text("utf-8")
    (folder,) = {k.rpartition("/")[0] for k in empty_lake.walk("backtests")}
    run = json.loads(empty_lake.read(f"{folder}/run.json"))
    assert "## Pick rules by season" in md
    for season, tuned_on in (("2022", "2021–2021"), ("2023", "2021–2022")):
        choices, tuning = run["choices"][season], run["pick_tuning"][season]
        k, edge = choices["picks.market_shrinkage_k"], choices["picks.min_edge_pts"]
        floor = "yes" if tuning["floor_met"] else "no"
        line = f"| {season} | {tuned_on} | {k:g} | {edge:g} | 55.0% | 5 / 3.5 / 2.5 | "
        assert f"{line}{tuning['picks']} | {floor} |" in md


def test_the_report_summary_prints_on_a_windows_console(
    backtest_lake: LocalLake, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A cp1252 console has no − or ≤: the gate summary the command prints must still encode."""
    spec = tmp_path / "spec.json"
    spec.write_text(json.dumps(SPEC), "utf-8")
    console = io.TextIOWrapper(io.BytesIO(), encoding="cp1252")
    monkeypatch.setattr(sys, "stdout", console)
    argv = ["backtest", "--spec", str(spec), "--seasons", "2023", "--tune-from", "2022"]

    assert engine(*argv, "--model", "stub", "--report", str(tmp_path / "report")) == 0

    console.seek(0)
    printed = console.read()
    for gate in GATES:
        assert re.search(rf"(PASS|FAIL|N/A) +{re.escape(gate)}", printed), gate


def test_the_fixture_run_matches_the_golden_metrics(
    backtest_lake: LocalLake, tmp_path: Path
) -> None:
    import pyarrow.parquet as pq

    spec_file = tmp_path / "spec.json"
    spec_file.write_text(json.dumps(SPEC), "utf-8")
    argv = ["backtest", "--spec", str(spec_file), "--seasons", "2023", "--tune-from", "2022"]
    assert engine(*argv, "--model", "stub") == 0
    (folder,) = {k.rpartition("/")[0] for k in backtest_lake.walk("backtests")}
    rows = pq.read_table(io.BytesIO(backtest_lake.read(f"{folder}/predictions.parquet")))
    run = json.loads(backtest_lake.read(f"{folder}/run.json"))
    choices = {int(s): c for s, c in run["choices"].items()}

    metrics = m.compute(rows.to_pylist(), ModelSpec.model_validate(run["spec"]), choices)

    assert metrics.games == 33
    text = golden_text(metrics)
    if os.environ.get("UPDATE_GOLDEN") == "1":
        GOLDEN.write_text(text, "utf-8", newline="\n")
    assert text == GOLDEN.read_text("utf-8")


def row(
    margin: int, open_line: float | None = -3.0, open_close: float | None = -3.0
) -> dict[str, Any]:
    """A 2020 week-1 game the model likes home by 7 against a −3 close."""
    return {
        "season": 2020,
        "season_type": "regular",
        "week": 1,
        "game_source_id": f"g{margin}",
        "pred_margin": 10.0,
        "margin_sd": 14.0,
        "home_win_prob": 0.76,
        "spread_home": -3.0,
        "spread_home_open": open_line,
        "spread_home_open_close": open_close,
        "margin": margin,
    }


SPEC_EVERY_EDGE = ModelSpec.model_validate(
    {
        "base": "power",
        "picks": {"min_edge_pts": 0.0, "min_prob": 0.5, "tiers": {"A": 5.0, "B": 3.5, "C": 2.5}},
    }
)


def test_the_report_shows_records_without_pushes_in_win_pct() -> None:
    """AC-1 as the report shows it: 3-1-1, 75.0%, +1.9u, ROI 1.9 / 4.4."""
    rows = [row(10), row(7), row(4), row(0), row(3)]  # W W W L P against −3

    metrics = m.compute(rows, SPEC_EVERY_EDGE, {})
    md = report.markdown(report.build(metrics, {"model": "fixture"}))

    assert str(metrics.picks) == "3-1-1"
    assert "| Record (W-L-P) | 3-1-1 |" in md
    assert "| Win % (pushes excluded) | 75.0% |" in md
    assert "| Units at −110 | +1.9u |" in md
    assert f"| ROI | {1.9 / 4.4 * 100:+.1f}% |" in md


def test_clv_measures_the_opener_against_the_same_books_close() -> None:
    """A home pick at −1 whose books closed −4 beat their close by 3 points, though the main
    (consensus) close is −3: CLV never mixes sources (D-132). A game with no opener is out."""
    metrics = m.compute([row(10, -1.0, -4.0), row(7, None, None)], SPEC_EVERY_EDGE, {})

    assert metrics.opening.games == 1
    assert metrics.opening.clv == pytest.approx(3.0)
    assert str(metrics.opening.picks) == "1-0-0"
    assert not metrics.opening.warning


def test_clv_needs_the_same_books_close() -> None:
    """With no close from the opener's books there's no CLV: the main close never stands in."""
    metrics = m.compute([row(10, -1.0, None)], SPEC_EVERY_EDGE, {})

    assert metrics.opening.games == 1
    assert str(metrics.opening.picks) == "1-0-0"  # graded at the opener, which needs no close
    assert metrics.opening.clv is None


def test_a_run_with_no_opener_says_so() -> None:
    """CFBD's books quote no openers before 2021, so a 2016-2020 run has no CLV to measure.
    (A regression guard: the message arrived with the report itself.)"""
    metrics = m.compute([row(10, None, None), row(7, None, None)], SPEC_EVERY_EDGE, {})
    md = report.markdown(report.build(metrics, {}))

    assert metrics.opening.games == 0
    assert metrics.opening.clv is None
    assert "| Games with an opening line | 0 of 2 |" in md
    assert "No game in this run has an opening line, so there's no CLV to measure." in md
