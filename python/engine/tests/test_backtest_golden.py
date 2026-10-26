"""Backtest determinism (TASK-030, docs/02-architecture.md › Testing strategy › Model /
backtest): the same spec on the same lake gives byte-identical results, equal to the committed
golden file. The golden file changes only in a commit whose message says why. To regenerate it,
run this test with `UPDATE_GOLDEN=1` and say in the commit why the numbers moved.
"""

from __future__ import annotations

import io
import json
import os
from pathlib import Path

import pyarrow.parquet as pq
import pytest
from lake_fixture import engine, write_backtest_seasons

from engine.ingest.lake import LocalLake
from engine.transform import rebuild

GOLDEN = Path(__file__).parent / "fixtures" / "backtest_golden.csv"
SPEC = {
    "base": "power",
    "hyperparameters": {"margin_cap": {"tune": [14, 28]}, "recency_half_life_weeks": 6},
    "picks": {"min_edge_pts": 3.0, "min_prob": 0.55, "tiers": {"A": 5.0, "B": 3.5, "C": 2.5}},
}


def _text(value: object) -> str:
    if value is None:
        return ""
    # 10 significant digits: the libm behind `**` and `erf` can differ in the last bits
    # between Windows and Linux (CI), and no model number means anything that fine.
    return f"{value:.10g}" if isinstance(value, float) else str(value)


def render(data: bytes) -> str:
    """The results as CSV text: one line per row."""
    table = pq.read_table(io.BytesIO(data))
    lines = [",".join(table.column_names)]
    for row in table.to_pylist():
        lines.append(",".join(_text(v) for v in row.values()))
    return "\n".join(lines) + "\n"


@pytest.fixture
def backtest_lake(empty_lake: LocalLake) -> LocalLake:
    write_backtest_seasons(empty_lake)
    rebuild(empty_lake)
    return empty_lake


def test_the_same_spec_twice_gives_identical_results_equal_to_the_golden_file(
    backtest_lake: LocalLake, tmp_path: Path
) -> None:
    spec = tmp_path / "spec.json"
    spec.write_text(json.dumps(SPEC), "utf-8")
    argv = ["backtest", "--spec", str(spec), "--seasons", "2023", "--tune-from", "2022"]

    assert engine(*argv, "--model", "stub") == 0
    assert engine(*argv, "--model", "stub") == 0

    keys = [k for k in backtest_lake.walk("backtests") if k.endswith("/predictions.parquet")]
    assert len(keys) == 2
    first, second = (backtest_lake.read(k) for k in keys)
    assert first == second

    text = render(first)
    if os.environ.get("UPDATE_GOLDEN") == "1":
        GOLDEN.write_text(text, "utf-8", newline="\n")
    assert text == GOLDEN.read_text("utf-8")
