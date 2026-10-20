"""The lake fixture of recorded CFBD responses, and helpers to write to it and run the CLI.

`fixtures/lake.json` maps raw keys to `{params, records}`, trimmed from real 2025 pulls: five
week-1 games, their lines (plus Colgate-Monmouth, a game with no FBS team), /teams without Idaho
State and /venues without UNLV's stadium (both filled in from /games), and four calendar weeks
(TASK-017). TASK-018 adds the five games' box scores and advanced stats, the plays and drives of
two of them (Kansas-Fresno State and UNLV-Idaho State), and the 2025 talent, returning
production, recruiting and SP+/FPI/Elo rows of the fixture teams, plus FIU's talent (not a
fixture team, so its `team_source_id` stays NULL) and SP+'s `nationalAverages` row.
"""

from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from engine import cli
from engine.ingest.lake import LocalLake, encode_raw, fetched_at_of

FIXTURE: dict[str, Any] = json.loads(
    (Path(__file__).parent / "fixtures" / "lake.json").read_text("utf-8")
)


def write(lake: LocalLake, key: str, records: list[Any], params: dict[str, Any]) -> None:
    lake.write_new(key, encode_raw(records, params, fetched_at_of(key)))


def write_fixture(lake: LocalLake, fixture: dict[str, Any] = FIXTURE) -> None:
    for key, raw in fixture.items():
        write(lake, key, raw["records"], raw["params"])


def fixture_key(endpoint: str) -> str:
    """The fixture's one raw key for `endpoint`."""
    (key,) = [k for k in FIXTURE if k.startswith(f"raw/cfbd/{endpoint}/")]
    return key


def staged(lake: LocalLake, name: str) -> pa.Table:
    return pq.read_table(io.BytesIO(lake.read(f"staging/{name}.parquet")))


def by_id(table: pa.Table, column: str = "source_id") -> dict[str, dict[str, Any]]:
    return {row[column]: row for row in table.to_pylist()}


def engine(*argv: str) -> int:
    try:
        cli.main(list(argv))
    except SystemExit as e:
        return int(e.code or 0)
    return 0
