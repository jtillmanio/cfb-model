"""Staged box scores, advanced stats, preseason inputs, benchmark ratings, plays and drives
(TASK-018, D-119): the inputs the feature tables, preseason priors and baselines read.

Every builder returns one SELECT, as in `staging`; it may read the tables built before it.
CFBD names teams rather than giving ids in most of these, so ids are resolved by name:
advanced stats, plays and drives by the game's home and away names in its newest /games record,
the season endpoints by staged `teams.school` (a school two teams share matches neither). A name
that doesn't match stays NULL, and `unmatched_teams` and `unmatched_sides` list it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from engine.transform.staging import Staging, _j

if TYPE_CHECKING:
    import duckdb

# team_game_advanced columns: suffix -> (path under `offense`/`defense`, type). Columns are
# `off_<suffix>` for the team's offense and `def_<suffix>` for its defense.
ADVANCED: dict[str, tuple[str, str]] = {
    "plays": ("plays", "INTEGER"),
    "ppa": ("ppa", "DOUBLE"),
    "success_rate": ("successRate", "DOUBLE"),
    "explosiveness": ("explosiveness", "DOUBLE"),
    "power_success": ("powerSuccess", "DOUBLE"),
    "stuff_rate": ("stuffRate", "DOUBLE"),
    "line_yards": ("lineYards", "DOUBLE"),
    "rush_ppa": ("rushingPlays.ppa", "DOUBLE"),
    "rush_success_rate": ("rushingPlays.successRate", "DOUBLE"),
    "rush_explosiveness": ("rushingPlays.explosiveness", "DOUBLE"),
    "pass_ppa": ("passingPlays.ppa", "DOUBLE"),
    "pass_success_rate": ("passingPlays.successRate", "DOUBLE"),
    "pass_explosiveness": ("passingPlays.explosiveness", "DOUBLE"),
}

# Benchmark systems: endpoint and the field holding the overall rating.
BENCHMARKS: dict[str, tuple[str, str]] = {
    "sp": ("ratings_sp", "rating"),
    "fpi": ("ratings_fpi", "fpi"),
    "elo": ("ratings_elo", "elo"),
}

# Tables whose `team_source_id` is resolved from a name.
NAME_KEYED = (
    "team_game_advanced",
    "talent",
    "returning_production",
    "recruiting",
    "benchmark_ratings",
)


def _game_names(s: Staging) -> str:
    """Each game's home and away names and ids, from its newest /games record."""
    games = s.latest("games", "id")
    return f"""SELECT {_j("id")} AS game_source_id, {_j("homeTeam")} AS home,
        {_j("homeId")} AS home_id, {_j("awayTeam")} AS away, {_j("awayId")} AS away_id
        FROM {games}"""


def _side_id(name: str) -> str:
    return f"CASE {name} WHEN g.home THEN g.home_id WHEN g.away THEN g.away_id END"


_SCHOOL_IDS = """(SELECT school, min(source_id) AS source_id FROM teams
    GROUP BY school HAVING count(*) = 1)"""


def _newest_per_team(raw: str) -> str:
    """One season endpoint's newest record per season and team name."""
    return f"""SELECT * FROM {raw}
        QUALIFY row_number() OVER (
            PARTITION BY season, {_j("team")} ORDER BY fetched_at DESC, key DESC, row DESC) = 1"""


def _clock(path: str, source: str = "record") -> str:
    return (
        f"{_j(f'{path}.minutes', 'INTEGER', source)} * 60 "
        f"+ {_j(f'{path}.seconds', 'INTEGER', source)}"
    )


def team_games(s: Staging) -> str:
    """CFBD /games/teams box scores: one row per game and team from the game's newest pull.
    `stats` is CFBD's category -> stat as JSON text, as sent (e.g. "completionAttempts":
    "23-31"); typed columns wait for their first reader."""
    latest = s.latest("games_teams", "id")
    return f"""
    WITH sides AS (
        SELECT {_j("id")} AS game_source_id, fetched_at,
            unnest(CAST(json_extract(record, '$.teams') AS JSON[])) AS side
        FROM {latest}
    )
    SELECT game_source_id, {_j("teamId", source="side")} AS team_source_id,
        {_j("team", source="side")} AS team, {_j("conference", source="side")} AS conference,
        {_j("homeAway", source="side")} AS home_away,
        {_j("points", "INTEGER", "side")} AS points,
        CAST((
            SELECT json_group_object(
                json_extract_string(st, '$.category'), json_extract_string(st, '$.stat'))
            FROM unnest(CAST(json_extract(side, '$.stats') AS JSON[])) AS u(st)
        ) AS VARCHAR) AS stats,
        fetched_at
    FROM sides
    ORDER BY game_source_id, home_away DESC
    """


def team_game_advanced(s: Staging) -> str:
    """CFBD /stats/game/advanced: one row per game and team, from the newest pull that has it,
    for games in staged `games` (the endpoint takes no classification, so FCS-only games are
    dropped and counted, as lines are). The team is matched by its own name, else by its
    opponent's, and rows are deduped on that id, so a school renamed between pulls stays one
    row. `garbage_time_excluded` is read from the pull's params (D-119)."""
    raw = s.raw("stats_game_advanced")
    metrics = ",\n            ".join(
        f"{_j(f'{side}.{path}', cast)} AS {prefix}_{suffix}"
        for side, prefix in (("offense", "off"), ("defense", "def"))
        for suffix, (path, cast) in ADVANCED.items()
    )
    s.con.execute(
        f"""CREATE OR REPLACE TEMP VIEW advanced_latest AS
        WITH g AS ({_game_names(s)})
        SELECT * FROM (
            SELECT r.*, coalesce({_side_id(_j("team"))},
                CASE {_j("opponent")} WHEN g.home THEN g.away_id WHEN g.away THEN g.home_id END)
                AS team_source_id
            FROM (SELECT *, {_j("gameId")} AS game_source_id FROM {raw}) r
            LEFT JOIN g USING (game_source_id)
        )
        QUALIFY row_number() OVER (
            PARTITION BY game_source_id, coalesce(team_source_id, {_j("team")})
            ORDER BY fetched_at DESC, key DESC, row DESC) = 1"""
    )
    row = s.con.execute(
        "SELECT count(*) FROM advanced_latest WHERE game_source_id NOT IN "
        "(SELECT source_id FROM games)"
    ).fetchone()
    s.dropped_advanced = row[0] if row else 0
    return f"""
    SELECT game_source_id, team_source_id, {_j("team")} AS team,
        {_j("opponent")} AS opponent, {_j("season", "INTEGER")} AS season,
        {_j("week", "INTEGER")} AS week, {_j("seasonType")} AS season_type,
        coalesce(json_extract_string(params, '$.excludeGarbageTime') = 'true', false)
            AS garbage_time_excluded,
        {metrics},
        fetched_at
    FROM advanced_latest
    WHERE game_source_id IN (SELECT source_id FROM games)
    ORDER BY game_source_id, team
    """


def talent(s: Staging) -> str:
    """CFBD /talent (247 team talent composite), the newest pull per season and team."""
    return f"""
    SELECT season, t.source_id AS team_source_id, {_j("team")} AS team,
        {_j("talent", "DOUBLE")} AS talent, fetched_at
    FROM ({_newest_per_team(s.raw("talent"))}) r
    LEFT JOIN {_SCHOOL_IDS} t ON t.school = {_j("team")}
    ORDER BY season, team
    """


_RETURNING = {
    "conference": ("conference", None),
    "total_ppa": ("totalPPA", "DOUBLE"),
    "total_passing_ppa": ("totalPassingPPA", "DOUBLE"),
    "total_receiving_ppa": ("totalReceivingPPA", "DOUBLE"),
    "total_rushing_ppa": ("totalRushingPPA", "DOUBLE"),
    "percent_ppa": ("percentPPA", "DOUBLE"),
    "percent_passing_ppa": ("percentPassingPPA", "DOUBLE"),
    "percent_receiving_ppa": ("percentReceivingPPA", "DOUBLE"),
    "percent_rushing_ppa": ("percentRushingPPA", "DOUBLE"),
    "usage": ("usage", "DOUBLE"),
    "passing_usage": ("passingUsage", "DOUBLE"),
    "receiving_usage": ("receivingUsage", "DOUBLE"),
    "rushing_usage": ("rushingUsage", "DOUBLE"),
}


def returning_production(s: Staging) -> str:
    """CFBD /player/returning, the newest pull per season and team."""
    columns = ", ".join(f"{_j(path, cast)} AS {name}" for name, (path, cast) in _RETURNING.items())
    return f"""
    SELECT season, t.source_id AS team_source_id, {_j("team")} AS team, {columns}, fetched_at
    FROM ({_newest_per_team(s.raw("player_returning"))}) r
    LEFT JOIN {_SCHOOL_IDS} t ON t.school = {_j("team")}
    ORDER BY season, team
    """


def recruiting(s: Staging) -> str:
    """CFBD /recruiting/teams (the class signed for that season), the newest pull per season
    and team."""
    return f"""
    SELECT season, t.source_id AS team_source_id, {_j("team")} AS team,
        {_j("rank", "INTEGER")} AS rank, {_j("points", "DOUBLE")} AS points, fetched_at
    FROM ({_newest_per_team(s.raw("recruiting_teams"))}) r
    LEFT JOIN {_SCHOOL_IDS} t ON t.school = {_j("team")}
    ORDER BY season, team
    """


def benchmark_ratings(s: Staging) -> str:
    """SP+, FPI and Elo: every pull kept, one row per system, season, team and `fetched_at`
    (SP+'s `nationalAverages` row dropped). `season_final` is true when the pull came at or
    after the end of the season's last staged calendar week, false before it, NULL when the
    season has no calendar; `known_at` is `fetched_at` for a pull before the season's end, so
    a baseline (M3.4) reads only rows with `known_at` before kickoff (D-119)."""
    parts = " UNION ALL ".join(
        f"""SELECT '{system}' AS system, season, {_j("team")} AS team,
            {_j("conference")} AS conference, {_j(field, "DOUBLE")} AS rating, fetched_at
        FROM {s.raw(endpoint)}
        WHERE {_j("team")} <> 'nationalAverages'
        QUALIFY row_number() OVER (
            PARTITION BY season, {_j("team")}, fetched_at ORDER BY key DESC, row DESC) = 1"""
        for system, (endpoint, field) in BENCHMARKS.items()
    )
    return f"""
    WITH b AS ({parts}),
    ends AS (SELECT season, max(end_at) AS season_end FROM calendar GROUP BY season)
    SELECT b.system, b.season, t.source_id AS team_source_id, b.team, b.conference, b.rating,
        b.fetched_at,
        CASE WHEN e.season_end IS NULL THEN NULL ELSE b.fetched_at >= e.season_end END
            AS season_final,
        CASE WHEN b.fetched_at < e.season_end THEN b.fetched_at END AS known_at
    FROM b
    LEFT JOIN ends e USING (season)
    LEFT JOIN {_SCHOOL_IDS} t ON t.school = b.team
    ORDER BY b.system, b.season, b.team, b.fetched_at
    """


def _newest_pull_per_game(raw: str) -> str:
    """Each game's rows from the newest pull that has the game, one per id. A week is pulled
    again until it's final, and a later pull can drop a play or renumber drives, so rows are
    never merged across pulls (schema review R1)."""
    return f"""SELECT * FROM (
            SELECT *, {_j("gameId")} AS game_source_id FROM {raw}
            QUALIFY dense_rank() OVER (
                PARTITION BY {_j("gameId")} ORDER BY fetched_at DESC, key DESC) = 1
        )
        QUALIFY row_number() OVER (PARTITION BY {_j("id")} ORDER BY row DESC) = 1"""


def plays(s: Staging, season: int) -> str:
    """One season of CFBD /plays, each game from its newest pull. Season, week and season type
    come from the raw file's key."""
    raw = s.raw("plays", season)
    return f"""
    WITH g AS ({_game_names(s)})
    SELECT p.game_source_id, {_j("id")} AS play_id, {_j("driveId")} AS drive_id,
        season, week, season_type,
        {_j("driveNumber", "INTEGER")} AS drive_number,
        {_j("playNumber", "INTEGER")} AS play_number,
        {_j("period", "INTEGER")} AS period, {_clock("clock")} AS clock_seconds,
        {_j("offense")} AS offense, {_side_id(_j("offense"))} AS offense_source_id,
        {_j("defense")} AS defense, {_side_id(_j("defense"))} AS defense_source_id,
        {_j("offenseScore", "INTEGER")} AS offense_score,
        {_j("defenseScore", "INTEGER")} AS defense_score,
        {_j("yardline", "INTEGER")} AS yardline,
        {_j("yardsToGoal", "INTEGER")} AS yards_to_goal,
        {_j("down", "INTEGER")} AS down, {_j("distance", "INTEGER")} AS distance,
        {_j("yardsGained", "INTEGER")} AS yards_gained,
        {_j("scoring", "BOOLEAN")} AS scoring, {_j("playType")} AS play_type,
        {_j("playText")} AS play_text, {_j("ppa", "DOUBLE")} AS ppa,
        {_j("wallclock", "TIMESTAMPTZ")} AS wallclock, fetched_at
    FROM ({_newest_pull_per_game(raw)}) p
    LEFT JOIN g USING (game_source_id)
    ORDER BY p.game_source_id, drive_number, play_number, play_id
    """


def drives(s: Staging, season: int) -> str:
    """One season of CFBD /drives, each game from its newest pull."""
    raw = s.raw("drives", season)
    return f"""
    WITH g AS ({_game_names(s)})
    SELECT d.game_source_id, {_j("id")} AS drive_id, season, week, season_type,
        {_j("driveNumber", "INTEGER")} AS drive_number,
        {_j("offense")} AS offense, {_side_id(_j("offense"))} AS offense_source_id,
        {_j("defense")} AS defense, {_side_id(_j("defense"))} AS defense_source_id,
        {_j("isHomeOffense", "BOOLEAN")} AS is_home_offense,
        {_j("scoring", "BOOLEAN")} AS scoring, {_j("driveResult")} AS drive_result,
        {_j("plays", "INTEGER")} AS plays, {_j("yards", "INTEGER")} AS yards,
        {_j("startPeriod", "INTEGER")} AS start_period,
        {_j("startYardsToGoal", "INTEGER")} AS start_yards_to_goal,
        {_clock("startTime")} AS start_clock_seconds,
        {_j("endPeriod", "INTEGER")} AS end_period,
        {_j("endYardsToGoal", "INTEGER")} AS end_yards_to_goal,
        {_clock("endTime")} AS end_clock_seconds,
        {_clock("elapsed")} AS elapsed_seconds,
        {_j("startOffenseScore", "INTEGER")} AS start_offense_score,
        {_j("startDefenseScore", "INTEGER")} AS start_defense_score,
        {_j("endOffenseScore", "INTEGER")} AS end_offense_score,
        {_j("endDefenseScore", "INTEGER")} AS end_defense_score,
        fetched_at
    FROM ({_newest_pull_per_game(raw)}) d
    LEFT JOIN g USING (game_source_id)
    ORDER BY d.game_source_id, drive_number, drive_id
    """


def unmatched_teams(con: duckdb.DuckDBPyConnection) -> list[str]:
    """`<table>: <name>` for each team name a name-keyed table couldn't resolve to an id."""
    return [
        f"{table}: {name}"
        for table in NAME_KEYED
        for (name,) in con.execute(
            f"SELECT DISTINCT team FROM {table} WHERE team_source_id IS NULL ORDER BY team"
        ).fetchall()
    ]


def unmatched_sides(con: duckdb.DuckDBPyConnection, relation: str, label: str) -> list[str]:
    """`<label>: <name>` for each offense or defense name in a plays or drives relation that
    didn't resolve to an id."""
    sql = f"""SELECT DISTINCT name FROM (
        SELECT offense AS name FROM {relation} WHERE offense_source_id IS NULL
        UNION ALL
        SELECT defense FROM {relation} WHERE defense_source_id IS NULL
    ) WHERE name IS NOT NULL ORDER BY name"""
    return [f"{label}: {name}" for (name,) in con.execute(sql).fetchall()]
