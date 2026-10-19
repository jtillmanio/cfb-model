"""`engine transform --rebuild`: every staged table rebuilt from the raw lake alone, with zero API
calls (D-027, D-116). Staging is derived, so it's overwritten; raw is never touched.

`TABLES` is the registry, built in order (a builder may read the tables before it). TASK-018 and
TASK-019 append to it.
"""

from __future__ import annotations

import io
from collections.abc import Callable

from db.config import refuse_if_live
from engine.ingest.lake import Lake
from engine.transform import staging
from engine.transform.staging import Staging

TABLES: dict[str, Callable[[Staging], str]] = {
    "games": staging.games,
    "teams": staging.teams,
    "team_seasons": staging.team_seasons,
    "venues": staging.venues,
    "calendar": staging.calendar,
    "lines": staging.lines,
    "skipped_raw": staging.skipped_raw,  # last: it lists what the builders above skipped
}


def staging_key(name: str) -> str:
    return f"staging/{name}.parquet"


def rebuild(lake: Lake) -> dict[str, int]:
    """Build every table in memory, then replace the staged files; returns the row counts.
    Refuses under LIVE=true before reading anything."""
    refuse_if_live("rebuild staging")
    import pyarrow.parquet as pq

    s = Staging(lake)
    built = {}
    for name, select in TABLES.items():
        s.con.execute(f"CREATE TABLE {name} AS {select(s)}")
        built[name] = s.con.table(name).to_arrow_table()

    for name, table in built.items():
        buffer = io.BytesIO()
        pq.write_table(table, buffer)
        lake.replace(staging_key(name), buffer.getvalue())

    counts = {name: table.num_rows for name, table in built.items()}
    print("Staged " + ", ".join(f"{n} {name}" for name, n in counts.items()) + ".")
    if s.dropped_lines:
        print(f"Dropped {s.dropped_lines} line rows for games not in staged games (no FBS team).")
    return counts
