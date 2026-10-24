"""`engine transform --rebuild`: every staged table rebuilt from the raw lake alone, with zero API
calls (D-027, D-116). Staging is derived, so it's overwritten; raw is never touched.

`TABLES` is the registry, built in order (a builder may read the tables before it). `SEASON_TABLES`
(plays, drives) are too big to hold every season at once, so each is built and written one season
at a time, to `staging/<name>/season=YYYY/data.parquet`, before `skipped_raw` (D-119).
`FEATURE_TABLES` are built from the staged tables, checked against the point-in-time rule, and
written to `features/<name>.parquet` with them (TASK-019).
"""

from __future__ import annotations

import io
import re
from collections.abc import Callable
from typing import TYPE_CHECKING

from db.config import refuse_if_live
from engine.ingest.lake import Lake
from engine.transform import features, staging, stats
from engine.transform.staging import Staging, raw_prefix

if TYPE_CHECKING:
    import pyarrow as pa

TABLES: dict[str, Callable[[Staging], str]] = {
    "games": staging.games,
    "teams": staging.teams,
    "team_seasons": staging.team_seasons,
    "venues": staging.venues,
    "calendar": staging.calendar,
    "lines": staging.lines,
    "team_games": stats.team_games,
    "team_game_advanced": stats.team_game_advanced,
    "talent": stats.talent,
    "returning_production": stats.returning_production,
    "recruiting": stats.recruiting,
    "benchmark_ratings": stats.benchmark_ratings,
    "skipped_raw": staging.skipped_raw,  # last: it lists what every builder skipped
}

# name -> builder for one season; each reads the raw endpoint of the same name.
SEASON_TABLES: dict[str, Callable[[Staging, int], str]] = {
    "plays": stats.plays,
    "drives": stats.drives,
}

# Built in order after `TABLES`, from the staged tables in the connection.
FEATURE_TABLES: dict[str, Callable[[], str]] = {
    "team_week_features": features.team_week_features,
    "game_features": features.game_features,
}

_SEASON = re.compile(r"raw/cfbd/[^/]+/season=(\d+)/")


def staging_key(name: str) -> str:
    return f"staging/{name}.parquet"


def feature_key(name: str) -> str:
    return f"features/{name}.parquet"


def season_key(name: str, season: int) -> str:
    return f"staging/{name}/season={season}/data.parquet"


def _write(lake: Lake, key: str, table: pa.Table) -> None:
    import pyarrow.parquet as pq

    buffer = io.BytesIO()
    pq.write_table(table, buffer)
    lake.replace(key, buffer.getvalue())


def _seasons(lake: Lake, endpoint: str) -> list[int]:
    found = {int(m[1]) for key in lake.walk(raw_prefix(endpoint)) if (m := _SEASON.match(key))}
    return sorted(found)


def _rebuild_seasons(s: Staging) -> tuple[dict[str, int], list[str]]:
    """Build and write each season table one season at a time; returns the total rows and the
    offense and defense names that didn't resolve to an id."""
    counts = dict.fromkeys(SEASON_TABLES, 0)
    unmatched: list[str] = []
    for name, select in SEASON_TABLES.items():
        for season in _seasons(s.lake, name):
            table = s.con.sql(select(s, season)).to_arrow_table()
            s.con.register("season_rows", table)
            unmatched += stats.unmatched_sides(s.con, "season_rows", f"{name} {season}")
            s.con.unregister("season_rows")
            _write(s.lake, season_key(name, season), table)
            counts[name] += table.num_rows
            s.release(name, season)
    return counts, unmatched


def rebuild(lake: Lake) -> dict[str, int]:
    """Build every `TABLES` and `FEATURE_TABLES` table in memory, check the features against
    the point-in-time rule, then replace the staged and feature files; returns the row counts.
    The season tables are written while `skipped_raw` waits for them to finish loading. A
    `features.PointInTimeError` replaces no other staged file and no feature file (the season
    files are already written, as with any failure part-way, D-119). Under LIVE=true it refuses
    before reading anything, unless `staging/` and `features/` are empty: then nothing is
    overwritten (the jobs' scratch lake, TASK-022)."""
    if lake.walk("staging") or lake.walk("features"):
        refuse_if_live("rebuild staging")

    s = Staging(lake)
    built = {}
    season_counts: dict[str, int] = {}
    unmatched: list[str] = []
    for name, select in TABLES.items():
        if name == "skipped_raw":
            season_counts, unmatched = _rebuild_seasons(s)
        s.con.execute(f"CREATE TABLE {name} AS {select(s)}")
        built[name] = s.con.table(name).to_arrow_table()

    for name, select in FEATURE_TABLES.items():
        s.con.execute(f"CREATE TABLE {name} AS {select()}")
    features.check_point_in_time(s.con)
    featured = {name: s.con.table(name).to_arrow_table() for name in FEATURE_TABLES}

    for name, table in built.items():
        _write(lake, staging_key(name), table)
    for name, table in featured.items():
        _write(lake, feature_key(name), table)

    counts = {name: table.num_rows for name, table in (built | featured).items()} | season_counts
    print("Staged " + ", ".join(f"{n} {name}" for name, n in counts.items()) + ".")
    if s.dropped_lines:
        print(f"Dropped {s.dropped_lines} line rows for games not in staged games (no FBS team).")
    if s.dropped_advanced:
        print(
            f"Dropped {s.dropped_advanced} advanced-stats rows for games not in staged games "
            "(no FBS team)."
        )
    unmatched = stats.unmatched_teams(s.con) + unmatched
    if unmatched:
        print(f"{len(unmatched)} team names matched no staged team (team_source_id left NULL):")
        print("\n".join(f"  {item}" for item in unmatched))
    return counts
