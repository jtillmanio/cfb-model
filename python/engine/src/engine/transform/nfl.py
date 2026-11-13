"""nflverse raw files -> staged NFL games, lines and venues, with no network (TASK-069, D-039).

Every file under `raw/nflverse/games/` is read; a game is its record from the newest pull (ties
on the raw key, then `row`). A file whose `params` season isn't its key's is skipped and listed in
`skipped_raw`. nflverse gives every value as text, empty when unknown, so each is read through
NULLIF.

- `nfl_games`: `REG` is `regular`, `WC`, `DIV`, `CON` and `SB` are `postseason`, any other type
  is dropped; `kickoff_at` is `gameday` + `gametime` in Eastern time, NULL when the time is blank;
  `final` when both scores are set, else `scheduled`; `neutral_site` is location `Neutral`.
- `nfl_lines`: one row per game and pull that quotes a price. nflverse's `spread_line` is positive
  when the home team is favored, the opposite of `spread_home` (CLAUDE.md), so `spread_home` is
  its negative. nflverse quotes no open, so `spread_home_open` and `total_open` are NULL; the
  publish picks snapshot and closing rows by pull time as for CFBD (D-120).
- `nfl_venues`: each stadium's name, roof and surface from its latest game that gives them.
"""

from __future__ import annotations

import io
import json
import re
from typing import TYPE_CHECKING, Any

from engine.ingest.lake import Lake, fetched_at_of
from engine.ingest.nflverse import RAW
from engine.sports.nfl import SEASON_TYPES, SOURCE
from engine.transform.staging import Staging

if TYPE_CHECKING:
    import pyarrow as pa

_KEY = re.compile(r"raw/nflverse/games/season=(?P<season>\d+)/fetched_at=[^/]+\.parquet")
NAME = "raw_nflverse_games"
BOOK = SOURCE  # the one sportsbook nflverse's lines are filed under (owner's choice, TASK-069)


def load_raw(lake: Lake) -> tuple[pa.Table, list[tuple[str, str]]]:
    """Every nflverse games record, with its file's key, season and fetch time, and the files
    skipped with the reason."""
    import pyarrow as pa
    import pyarrow.parquet as pq

    schema = pa.schema(
        [
            ("key", pa.string()),
            ("season", pa.int32()),
            ("fetched_at", pa.timestamp("us", "UTC")),
            ("row", pa.int32()),
            ("record", pa.string()),
        ]
    )
    parts: list[pa.Table] = []
    skipped: list[tuple[str, str]] = []
    for key in lake.walk(f"{RAW}/games"):
        if not key.endswith(".parquet") or "fetched_at=" not in key:
            continue
        match = _KEY.fullmatch(key)
        if match is None:
            skipped.append((key, "the key doesn't follow the raw layout"))
            continue
        season = int(match["season"])
        table = pq.read_table(io.BytesIO(lake.read(key)), columns=["row", "record", "params"])
        if table.num_rows:
            sent: dict[str, Any] = json.loads(table.column("params")[0].as_py())
            if sent != {"season": season}:
                skipped.append(
                    (key, f"params {json.dumps(sent, sort_keys=True)} don't fit the key")
                )
                continue
        n = table.num_rows
        parts.append(
            pa.table(
                {
                    "key": pa.array([key] * n, pa.string()),
                    "season": pa.array([season] * n, pa.int32()),
                    "fetched_at": pa.array([fetched_at_of(key)] * n, pa.timestamp("us", "UTC")),
                    "row": table.column("row").cast(pa.int32()),
                    "record": table.column("record"),
                }
            )
        )
    records = pa.concat_tables(parts) if parts else schema.empty_table()
    return records, skipped


def _raw(s: Staging) -> str:
    if NAME not in s._loaded:
        records, skipped = load_raw(s.lake)
        s.con.register(NAME, records)
        s.skipped += skipped
        s._loaded.add(NAME)
    return NAME


def _v(field: str, cast: str | None = None) -> str:
    """A record's field, NULL when empty, optionally cast."""
    text = f"NULLIF(json_extract_string(record, '$.{field}'), '')"
    return f"CAST({text} AS {cast})" if cast else text


def _season_type() -> str:
    cases = " ".join(f"WHEN '{k}' THEN '{v}'" for k, v in SEASON_TYPES.items())
    return f"CASE {_v('game_type')} {cases} END"


def _latest(s: Staging) -> str:
    """Each game's record from the newest pull, of the game types kept."""
    return f"""
        SELECT * FROM {_raw(s)}
        WHERE {_season_type()} IS NOT NULL
        QUALIFY row_number() OVER (
            PARTITION BY {_v("game_id")} ORDER BY fetched_at DESC, key DESC, row DESC) = 1"""


def nfl_games(s: Staging) -> str:
    return f"""
    SELECT
        {_v("game_id")} AS source_id,
        {_v("season", "INTEGER")} AS season,
        {_v("week", "INTEGER")} AS week,
        {_season_type()} AS season_type,
        {_v("gameday", "DATE")} AS game_date,
        CASE WHEN {_v("gametime")} IS NULL THEN NULL
             ELSE timezone('America/New_York',
                CAST({_v("gameday")} || ' ' || {_v("gametime")} AS TIMESTAMP)) END AS kickoff_at,
        coalesce({_v("location")} = 'Neutral', false) AS neutral_site,
        false AS conference_game,
        {_v("stadium_id")} AS venue_source_id,
        {_v("home_team")} AS home_source_id,
        {_v("away_team")} AS away_source_id,
        {_v("home_score", "INTEGER")} AS home_points,
        {_v("away_score", "INTEGER")} AS away_points,
        CASE WHEN {_v("home_score")} IS NOT NULL AND {_v("away_score")} IS NOT NULL
             THEN 'final' ELSE 'scheduled' END AS status,
        fetched_at
    FROM ({_latest(s)})
    ORDER BY season, season_type, week, source_id
    """


def nfl_lines(s: Staging) -> str:
    return f"""
    SELECT
        {_v("game_id")} AS game_source_id,
        '{BOOK}' AS provider,
        fetched_at,
        -{_v("spread_line", "DOUBLE")} AS spread_home,
        CAST(NULL AS DOUBLE) AS spread_home_open,
        {_v("total_line", "DOUBLE")} AS total,
        CAST(NULL AS DOUBLE) AS total_open,
        CAST({_v("home_moneyline", "DOUBLE")} AS INTEGER) AS ml_home,
        CAST({_v("away_moneyline", "DOUBLE")} AS INTEGER) AS ml_away
    FROM {_raw(s)}
    WHERE {_v("game_id")} IN (SELECT source_id FROM nfl_games)
        AND coalesce({_v("spread_line")}, {_v("total_line")}, {_v("home_moneyline")},
                      {_v("away_moneyline")}) IS NOT NULL
    QUALIFY row_number() OVER (
        PARTITION BY {_v("game_id")}, fetched_at ORDER BY key DESC, row DESC) = 1
    ORDER BY game_source_id, fetched_at
    """


def stage(lake: Lake) -> dict[str, list[dict[str, Any]]]:
    """The NFL tables alone, built in memory from `lake`'s nflverse files (for `engine ingest
    nflverse`, which publishes without rebuilding the CFB tables)."""
    s = Staging(lake)
    rows: dict[str, list[dict[str, Any]]] = {}
    builders = (("nfl_games", nfl_games), ("nfl_lines", nfl_lines), ("nfl_venues", nfl_venues))
    for name, build in builders:
        s.con.execute(f"CREATE TABLE {name} AS {build(s)}")
        rows[name] = s.con.table(name).to_arrow_table().to_pylist()
    for key, reason in s.skipped:
        print(f"Skipped {key}: {reason}")
    return rows


def nfl_venues(s: Staging) -> str:
    return f"""
    SELECT
        {_v("stadium_id")} AS source_id,
        arg_max({_v("stadium")}, {_v("gameday")}) AS name,
        arg_max({_v("roof")}, {_v("gameday")}) FILTER (WHERE {_v("roof")} IS NOT NULL) AS roof,
        arg_max({_v("surface")}, {_v("gameday")})
            FILTER (WHERE {_v("surface")} IS NOT NULL) AS surface,
        max(fetched_at) AS fetched_at
    FROM ({_latest(s)})
    WHERE {_v("stadium_id")} IS NOT NULL
    GROUP BY ALL
    ORDER BY source_id
    """
