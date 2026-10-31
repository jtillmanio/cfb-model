"""Raw lake -> staged tables, in DuckDB, with no API calls (D-027, D-116).

Raw bytes come through the `Lake` protocol into pyarrow and are registered in an in-memory DuckDB
connection, so R2 works without DuckDB's `httpfs` (D-112). Each table builder returns one SELECT;
`engine.transform.rebuild` creates the tables in registry order, so a builder may read the tables
before it.

The latest version of an entity is its record from the newest `fetched_at` across every raw file
of its endpoint, week and season files alike; ties break on the raw key, then `row`. A raw file
whose `params` disagree with its key is skipped by every table and listed in `skipped_raw`.
"""

from __future__ import annotations

import io
import json
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from engine.ingest.endpoints import SETTLE, query
from engine.ingest.lake import Lake, fetched_at_of

if TYPE_CHECKING:
    import duckdb
    import pyarrow as pa

_KEY = re.compile(
    r"raw/cfbd/(?P<endpoint>[^/]+)/season=(?P<season>\d+)"
    r"(?:/season_type=(?P<season_type>[^/]+))?(?:/week=(?P<week>\d+))?"
    r"/fetched_at=[^/]+\.parquet"
)


def connect() -> duckdb.DuckDBPyConnection:
    """An in-memory connection that never downloads an extension: `json` and `icu` ship in the
    wheel, and a missing one fails here instead of reaching the network."""
    import duckdb

    con = duckdb.connect(":memory:", config={"autoinstall_known_extensions": False})
    con.execute("SET TimeZone = 'UTC'")
    return con


def _params_mismatch(
    endpoint: str, season: int, week: int | None, season_type: str, sent: dict[str, Any]
) -> str | None:
    """Why a file's params don't match the query its key stands for, or None if they do."""
    try:
        expected = query(endpoint, season, week, season_type)
        extra = {k: str(v) for k, v in sent.items() if k not in expected}
        expected = query(endpoint, season, week, season_type, extra)
    except (KeyError, ValueError) as e:
        return f"params {json.dumps(sent, sort_keys=True)} don't fit the key: {e}"
    if {k: str(v) for k, v in sent.items()} != {k: str(v) for k, v in expected.items()}:
        return (
            f"params {json.dumps(sent, sort_keys=True)} don't match the key's query "
            f"{json.dumps(expected, sort_keys=True)}"
        )
    return None


def _file_schema() -> pa.Schema:
    import pyarrow as pa

    return pa.schema(
        [
            ("key", pa.string()),
            ("season", pa.int32()),
            ("week", pa.int32()),
            ("season_type", pa.string()),
            ("fetched_at", pa.timestamp("us", "UTC")),
            ("params", pa.string()),
            ("records", pa.int32()),
        ]
    )


@dataclass
class RawEndpoint:
    """Every usable raw file of one endpoint: `records` has a row per record, `files` a row per
    file (an empty response included, with its record count), and `skipped` the files left out,
    with the reason. An empty file has no `params` to check, so it's never skipped (and its
    `params` is NULL)."""

    records: pa.Table
    files: pa.Table
    skipped: list[tuple[str, str]] = field(default_factory=list)


def raw_prefix(endpoint: str, season: int | None = None) -> str:
    prefix = f"raw/cfbd/{endpoint}"
    return prefix if season is None else f"{prefix}/season={season}"


def load_raw(lake: Lake, endpoint: str, season: int | None = None) -> RawEndpoint:
    """The endpoint's raw files, or only one season's."""
    import pyarrow as pa
    import pyarrow.parquet as pq

    files: list[dict[str, Any]] = []
    parts: list[pa.Table] = []
    skipped: list[tuple[str, str]] = []
    for key in lake.walk(raw_prefix(endpoint, season)):
        if not key.endswith(".parquet") or "fetched_at=" not in key:
            continue  # D-098's JSON files stay unread (D-112)
        match = _KEY.fullmatch(key)
        if match is None or match["endpoint"] != endpoint:
            skipped.append((key, "the key doesn't follow the raw layout"))
            continue
        file_season = int(match["season"])
        week = None if match["week"] is None else int(match["week"])
        season_type = match["season_type"] or "regular"
        table = pq.read_table(io.BytesIO(lake.read(key)), columns=["row", "record", "params"])
        params = table.column("params")[0].as_py() if table.num_rows else None
        if params is not None:
            reason = _params_mismatch(
                endpoint, file_season, week, season_type, json.loads(params)
            )
            if reason:
                skipped.append((key, reason))
                continue
        info = {
            "key": key,
            "season": file_season,
            "week": week,
            "season_type": season_type,
            "fetched_at": fetched_at_of(key),
            "params": params,
            "records": table.num_rows,
        }
        files.append(info)
        schema = _file_schema()
        columns = {
            name: pa.array([value] * table.num_rows, schema.field(name).type)
            for name, value in info.items()
            if name != "records"
        }
        parts.append(
            pa.table({**columns, "row": table.column("row"), "record": table.column("record")})
        )

    file_schema = _file_schema()
    record_schema = (
        file_schema.remove(file_schema.get_field_index("records"))
        .append(pa.field("row", pa.int32()))
        .append(pa.field("record", pa.string()))
    )
    records = (
        pa.concat_tables([p.cast(record_schema) for p in parts])
        if parts
        else record_schema.empty_table()
    )
    return RawEndpoint(records, pa.Table.from_pylist(files, _file_schema()), skipped)


def _j(path: str, cast: str | None = None, source: str = "record") -> str:
    """A JSON field of a raw record, as text or cast; a JSON null comes back NULL."""
    text = f"json_extract_string({source}, '$.{path}')"
    return f"CAST({text} AS {cast})" if cast else text


class Staging:
    """One rebuild: the DuckDB connection, the raw endpoints loaded so far, and what was left
    out (raw files skipped, line and advanced-stats rows dropped)."""

    def __init__(self, lake: Lake) -> None:
        self.lake = lake
        self.con = connect()
        self.skipped: list[tuple[str, str]] = []
        self.dropped_lines = 0
        self.dropped_advanced = 0
        self._loaded: set[str] = set()

    def raw(self, endpoint: str, season: int | None = None) -> str:
        """Register `raw_<endpoint>` (records) and `raw_<endpoint>_files`, or with a season
        `raw_<endpoint>_<season>` and its files; returns the first."""
        name = f"raw_{endpoint}" if season is None else f"raw_{endpoint}_{season}"
        if name not in self._loaded:
            raw = load_raw(self.lake, endpoint, season)
            self.con.register(name, raw.records)
            self.con.register(f"{name}_files", raw.files)
            self.skipped += raw.skipped
            self._loaded.add(name)
        return name

    def release(self, endpoint: str, season: int) -> None:
        """Unregister one season's raw records once its tables are written (plays are large)."""
        name = f"raw_{endpoint}_{season}"
        if name in self._loaded:
            self.con.unregister(name)
            self.con.unregister(f"{name}_files")
            self._loaded.remove(name)

    def latest(self, endpoint: str, *id_paths: str) -> str:
        """Register `latest_<endpoint>`: each entity's record from the newest pull."""
        name = f"latest_{endpoint}"
        ids = ", ".join(_j(p) for p in id_paths)
        self.con.execute(
            f"""CREATE OR REPLACE TEMP VIEW {name} AS
            SELECT * FROM {self.raw(endpoint)}
            QUALIFY row_number() OVER (
                PARTITION BY {ids} ORDER BY fetched_at DESC, key DESC, row DESC) = 1"""
        )
        return name


def _start(source: str = "record") -> str:
    return f"CAST({_j('startDate', source=source)} AS TIMESTAMPTZ)"


def _sides(s: Staging) -> str:
    """One row per team per newest game record: the team as /games names it."""
    games = s.latest("games", "id")
    return " UNION ALL ".join(
        f"""SELECT {_j(f"{side}Id")} AS source_id, {_j(f"{side}Team")} AS school,
            {_j("season", "INTEGER")} AS season, {_j(f"{side}Conference")} AS conference,
            {_j(f"{side}Classification")} AS classification, fetched_at, key, row
        FROM {games}"""
        for side in ("home", "away")
    )


def games(s: Staging) -> str:
    """Games as `GameRow` maps them, plus each side's classification, the pull they came from,
    and `closing_line_missing`: false when a non-empty /lines pull fetched after kickoff quotes
    a spread, true when such a pull covers the game's week but quotes none, NULL when none
    covers it. An empty pull isn't coverage: CFBD can answer empty just after the games (D-114).
    A TBA kickoff counts as the end of its Eastern `game_date`.

    `status` is `final` when CFBD marks the game completed, `canceled` when its newest record is
    uncompleted and unscored and was pulled `SETTLE` (7 days) or more after its `startDate`
    (D-121: CFBD lists a canceled game as uncompleted forever, with no other signal), else
    `scheduled`. CFBD can't tell a postponed game from a canceled one, and a rescheduled game
    keeps its id under a new date, so the next pull stages it `scheduled` again (TASK-044)."""
    latest = s.latest("games", "id")
    lines = s.raw("lines")
    return f"""
    WITH g AS (
        SELECT
            {_j("id")} AS source_id,
            {_j("season", "INTEGER")} AS season,
            {_j("week", "INTEGER")} AS week,
            {_j("seasonType")} AS season_type,
            CAST({_start()} AT TIME ZONE 'America/New_York' AS DATE) AS game_date,
            CASE WHEN coalesce({_j("startTimeTBD", "BOOLEAN")}, false) THEN NULL
                 ELSE {_start()} END AS kickoff_at,
            coalesce({_j("neutralSite", "BOOLEAN")}, false) AS neutral_site,
            coalesce({_j("conferenceGame", "BOOLEAN")}, false) AS conference_game,
            {_j("venueId")} AS venue_source_id,
            {_j("homeId")} AS home_source_id,
            {_j("awayId")} AS away_source_id,
            {_j("homePoints", "INTEGER")} AS home_points,
            {_j("awayPoints", "INTEGER")} AS away_points,
            CASE WHEN coalesce({_j("completed", "BOOLEAN")}, false) THEN 'final'
                 WHEN {_j("homePoints")} IS NULL AND {_j("awayPoints")} IS NULL
                  AND fetched_at >= {_start()} + INTERVAL {SETTLE.days} DAY THEN 'canceled'
                 ELSE 'scheduled' END AS status,
            {_j("homeClassification")} AS home_classification,
            {_j("awayClassification")} AS away_classification,
            fetched_at,
            CASE WHEN coalesce({_j("startTimeTBD", "BOOLEAN")}, false)
                THEN timezone('America/New_York', CAST(
                    CAST({_start()} AT TIME ZONE 'America/New_York' AS DATE) + 1 AS TIMESTAMP))
                ELSE {_start()} END AS line_cutoff
        FROM {latest}
    ),
    covering AS (  -- non-empty /lines pulls after kickoff whose season and week hold the game
        SELECT g.source_id, f.key
        FROM g JOIN {lines}_files f
          ON f.season = g.season AND f.season_type = g.season_type
         AND (f.week IS NULL OR f.week = g.week) AND f.fetched_at > g.line_cutoff
         AND f.records > 0
    ),
    quoted AS (
        SELECT DISTINCT r.key, {_j("id", source="r.record")} AS game_source_id
        FROM {lines} r, unnest(CAST(json_extract(r.record, '$.lines') AS JSON[])) AS l(line)
        WHERE json_extract_string(l.line, '$.spread') IS NOT NULL
    ),
    mark AS (
        SELECT c.source_id, bool_or(q.key IS NOT NULL) AS has_spread
        FROM covering c
        LEFT JOIN quoted q ON q.key = c.key AND q.game_source_id = c.source_id
        GROUP BY c.source_id
    )
    SELECT g.* EXCLUDE (line_cutoff), NOT m.has_spread AS closing_line_missing
    FROM g LEFT JOIN mark m USING (source_id)
    ORDER BY season, season_type, week, source_id
    """


def teams(s: Staging) -> str:
    """The newest /teams record per team, filled in from /games for teams it doesn't have."""
    latest = s.latest("teams", "id")
    return f"""
    WITH t AS (
        SELECT {_j("id")} AS source_id, {_j("school")} AS school, {_j("mascot")} AS mascot,
            {_j("abbreviation")} AS abbreviation, {_j("color")} AS color,
            {_j("alternateColor")} AS alt_color, {_j("logos[0]")} AS logo_url, fetched_at
        FROM {latest}
    ),
    g AS (
        SELECT source_id, school, fetched_at FROM ({_sides(s)})
        QUALIFY row_number() OVER (
            PARTITION BY source_id ORDER BY fetched_at DESC, key DESC, row DESC) = 1
    )
    SELECT * FROM t
    UNION ALL
    SELECT source_id, school, NULL, NULL, NULL, NULL, NULL, fetched_at
    FROM g WHERE source_id NOT IN (SELECT source_id FROM t)
    ORDER BY source_id
    """


def team_seasons(s: Staging) -> str:
    """Conference, classification (fbs/fcs: Postgres `team_seasons.division`) and CFBD's own
    division (e.g. East/West) per team and season: /teams for that season, else the team's
    newest game record that season."""
    teams_raw = s.raw("teams")
    return f"""
    WITH t AS (
        SELECT {_j("id")} AS team_source_id, season, {_j("conference")} AS conference,
            {_j("classification")} AS classification, {_j("division")} AS cfbd_division,
            fetched_at
        FROM {teams_raw}
        QUALIFY row_number() OVER (
            PARTITION BY {_j("id")}, season ORDER BY fetched_at DESC, key DESC, row DESC) = 1
    ),
    g AS (
        SELECT source_id AS team_source_id, season, conference, classification, fetched_at
        FROM ({_sides(s)})
        QUALIFY row_number() OVER (
            PARTITION BY source_id, season ORDER BY fetched_at DESC, key DESC, row DESC) = 1
    )
    SELECT * FROM t
    UNION ALL
    SELECT team_source_id, season, conference, classification, NULL, fetched_at FROM g
    WHERE (team_source_id, season) NOT IN (SELECT (team_source_id, season) FROM t)
    ORDER BY season, team_source_id
    """


def venues(s: Staging) -> str:
    """The newest /venues record per venue, filled in from /games for venues it doesn't have."""
    latest = s.latest("venues", "id")
    games_latest = s.latest("games", "id")
    return f"""
    WITH v AS (
        SELECT {_j("id")} AS source_id, {_j("name")} AS name, {_j("city")} AS city,
            {_j("state")} AS state, {_j("latitude", "DOUBLE")} AS lat,
            {_j("longitude", "DOUBLE")} AS lon, {_j("elevation", "DOUBLE")} AS elevation,
            {_j("dome", "BOOLEAN")} AS dome, {_j("grass", "BOOLEAN")} AS grass,
            {_j("timezone")} AS timezone, {_j("capacity", "INTEGER")} AS capacity, fetched_at
        FROM {latest}
    ),
    g AS (
        SELECT {_j("venueId")} AS source_id, {_j("venue")} AS name, fetched_at
        FROM {games_latest} WHERE {_j("venueId")} IS NOT NULL
        QUALIFY row_number() OVER (
            PARTITION BY {_j("venueId")} ORDER BY fetched_at DESC, key DESC, row DESC) = 1
    )
    SELECT * FROM v
    UNION ALL
    SELECT source_id, name, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, fetched_at
    FROM g WHERE source_id NOT IN (SELECT source_id FROM v)
    ORDER BY source_id
    """


def calendar(s: Staging) -> str:
    """CFBD /calendar weeks, the newest pull per season, season type and week (UTC times)."""
    latest = s.latest("calendar", "season", "seasonType", "week")
    return f"""
    SELECT {_j("season", "INTEGER")} AS season, {_j("seasonType")} AS season_type,
        {_j("week", "INTEGER")} AS week,
        {_j("startDate", "TIMESTAMPTZ")} AS start_at, {_j("endDate", "TIMESTAMPTZ")} AS end_at,
        {_j("firstGameStart", "TIMESTAMPTZ")} AS first_game_start,
        {_j("lastGameStart", "TIMESTAMPTZ")} AS last_game_start, fetched_at
    FROM {latest}
    ORDER BY season, season_type, week
    """


def lines(s: Staging) -> str:
    """Every pull's line per game and provider (each pull is a snapshot; TASK-020 picks the
    opening, closing and snapshot rows, D-115). Games not in staged games (no FBS team: CFBD's
    /lines takes no classification) are dropped and counted."""
    raw = s.raw("lines")
    s.con.execute(
        f"""CREATE OR REPLACE TEMP VIEW lines_exploded AS
        SELECT key, row, fetched_at, game_source_id, unnest(lines) AS line,
            unnest(range(len(lines))) AS idx
        FROM (
            SELECT key, row, fetched_at, {_j("id")} AS game_source_id,
                CAST(json_extract(record, '$.lines') AS JSON[]) AS lines
            FROM {raw}
        )"""
    )
    row = s.con.execute(
        "SELECT count(*) FROM lines_exploded WHERE game_source_id NOT IN "
        "(SELECT source_id FROM games)"
    ).fetchone()
    s.dropped_lines = row[0] if row else 0
    return f"""
    SELECT game_source_id, {_j("provider", source="line")} AS provider, fetched_at,
        {_j("spread", "DOUBLE", "line")} AS spread_home,
        {_j("spreadOpen", "DOUBLE", "line")} AS spread_home_open,
        {_j("overUnder", "DOUBLE", "line")} AS total,
        {_j("overUnderOpen", "DOUBLE", "line")} AS total_open,
        CAST({_j("homeMoneyline", "DOUBLE", "line")} AS INTEGER) AS ml_home,
        CAST({_j("awayMoneyline", "DOUBLE", "line")} AS INTEGER) AS ml_away
    FROM lines_exploded
    WHERE game_source_id IN (SELECT source_id FROM games)
    QUALIFY row_number() OVER (
        PARTITION BY game_source_id, provider, fetched_at
        ORDER BY key DESC, row DESC, idx DESC) = 1
    ORDER BY game_source_id, provider, fetched_at
    """


def skipped_raw(s: Staging) -> str:
    """The raw files the tables above left out, with the reason (D-116)."""
    import pyarrow as pa

    table = pa.table(
        {
            "key": pa.array([k for k, _ in s.skipped], pa.string()),
            "reason": pa.array([r for _, r in s.skipped], pa.string()),
        }
    )
    s.con.register("skipped_list", table)
    return "SELECT DISTINCT key, reason FROM skipped_list ORDER BY key"
