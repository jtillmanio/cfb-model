"""Point-in-time feature tables (TASK-019, D-042, D-127): each team's form entering every week,
and a home-vs-away row per game, built from staged `games` and `team_game_advanced` alone.

A week's `as_of` is the earliest kickoff among its staged games (a TBA game counts as the start
of its Eastern `game_date`, so `as_of` is never late). A `team_week_features` row aggregates the
team's final games that season that finished before `as_of`, a game counting as finished
`GAME_HOURS` after kickoff (a TBA game kicks off at the end of its date, so it's never early).
The cutoff is a time, not a week number, so postseason follows the regular season and a
rescheduled game can't leak into the week it was moved past. Every row carries
`last_game_kickoff`, its newest source game, and `check_point_in_time` fails the build if any
didn't finish before `as_of`. So every feature must aggregate the included games `s`; a feature
read from another source needs its own timestamp in the check.

**Rounds** (TASK-048). CFBD files every bowl and CFP round under postseason week 1, so a week can
hold games that depend on each other's results. A postseason game's `round` is 1 + the highest
round of any earlier game of its week either team played (bowls and the first CFP round are 1;
the bracket's later rounds follow), and every other game is round 1. `team_week_features` has a
row per team for each round of a week, `as_of` the round's earliest kickoff; round 1's is the
week's, so a week with one round is unchanged. `game_features` keeps the week's `as_of` and the
features entering it (round 1), and adds the game's `round` and its round's `as_of`
(`round_as_of`), for the backtest's `postseason: rounds` (docs/04-model.md § 9.2).

Efficiency columns are season-to-date means of the per-game values (one game, one observation),
named `<side>_<split><metric>` as `team_game_advanced` names them, so later metrics and splits
extend the set without renames. A team-game with no advanced-stats row (CFBD never computed some,
D-121) counts in `games_played` and points but not in the means; `advanced_games` counts the
games with a row. Unknown is NULL: with no games yet, the counts and sums are 0 and the means
NULL.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import duckdb

# How long after kickoff a game counts as finished: a game runs about 3.5 hours. The closest
# 2014-2026 gap between a game and the next week's first kickoff is 5 hours (Army-Navy 2025).
GAME_HOURS = 4

# The point-in-time rule: a source game `s` feeds week `w`'s row only if it finished before the
# week's `as_of`. The leakage tests loosen it to prove `check_point_in_time` catches a leak.
INCLUDED = f"s.kickoff + INTERVAL {GAME_HOURS} HOURS <= w.as_of"

# A staged game's kickoff for the point-in-time rule: a TBA game kicks off at the end of its
# Eastern `game_date`, so it's never early (the backtest harness reads it too).
KICKOFF = "coalesce(kickoff_at, timezone('America/New_York', CAST(game_date + 1 AS TIMESTAMP)))"

_RATES = [
    f"{side}_{split}{metric}"
    for side in ("off", "def")
    for split in ("", "rush_", "pass_")
    for metric in ("ppa", "success_rate", "explosiveness")
]

# team_week_features column -> its aggregate over the included source games `s`.
FEATURES: dict[str, str] = {
    "last_game_kickoff": "max(s.kickoff)",
    "games_played": "CAST(count(s.game_source_id) AS INTEGER)",
    "points_for": "CAST(coalesce(sum(s.points_for), 0) AS INTEGER)",
    "points_against": "CAST(coalesce(sum(s.points_against), 0) AS INTEGER)",
    "points_for_per_game": "avg(s.points_for)",
    "points_against_per_game": "avg(s.points_against)",
    "margin_per_game": "avg(s.points_for - s.points_against)",
    "advanced_games": "CAST(count(s.advanced_game) AS INTEGER)",
    "off_plays": "CAST(coalesce(sum(s.off_plays), 0) AS INTEGER)",
    "def_plays": "CAST(coalesce(sum(s.def_plays), 0) AS INTEGER)",
} | {rate: f"avg(s.{rate})" for rate in _RATES}

KEYS = ("team_source_id", "season", "season_type", "week", "round")

# Each postseason game's round (`rounds`), from `g`, the staged games with their `kickoff`: a
# chain of games sharing a team, each kicking off after the last, within one week. A game that
# won't be played starts no chain. Needs `WITH RECURSIVE`.
ROUNDS = """
    post AS (
        SELECT source_id, season, season_type, week, kickoff, home_source_id, away_source_id
        FROM g WHERE season_type = 'postseason' AND status NOT IN ('canceled', 'postponed')
    ),
    chain (source_id, round) AS (
        SELECT source_id, 1 FROM post
        UNION
        SELECT later.source_id, c.round + 1
        FROM chain c
        JOIN post earlier ON earlier.source_id = c.source_id
        JOIN post later
          ON later.season = earlier.season AND later.season_type = earlier.season_type
         AND later.week = earlier.week AND later.kickoff > earlier.kickoff
         AND (later.home_source_id IN (earlier.home_source_id, earlier.away_source_id)
              OR later.away_source_id IN (earlier.home_source_id, earlier.away_source_id))
    ),
    rounds AS (SELECT source_id, max(round) AS round FROM chain GROUP BY source_id)"""


class PointInTimeError(RuntimeError):
    """A feature row read a game that didn't finish before its `as_of`, or has no `as_of`."""


def team_week_features() -> str:
    """One row per team in the season's staged games and round of a week with a staged game."""
    side = """SELECT season, source_id AS game_source_id, kickoff, {team} AS team_source_id,
            {us} AS points_for, {them} AS points_against
        FROM g WHERE status = 'final' AND home_points IS NOT NULL AND away_points IS NOT NULL"""
    played = " UNION ALL ".join(
        side.format(team=f"{a}_source_id", us=f"{a}_points", them=f"{b}_points")
        for a, b in (("home", "away"), ("away", "home"))
    )
    metrics = ", ".join(f"a.{c}" for c in ("off_plays", "def_plays", *_RATES))
    features = ",\n        ".join(f"{sql} AS {name}" for name, sql in FEATURES.items())
    return f"""
    WITH RECURSIVE g AS (
        SELECT *,
            {KICKOFF} AS kickoff,
            coalesce(kickoff_at, timezone('America/New_York',
                CAST(game_date AS TIMESTAMP))) AS earliest
        FROM games
    ),{ROUNDS},
    weeks AS (
        SELECT g.season, g.season_type, g.week, coalesce(r.round, 1) AS round,
            min(g.earliest) AS as_of
        FROM g LEFT JOIN rounds r ON r.source_id = g.source_id
        GROUP BY ALL
    ),
    teams AS (
        SELECT season, home_source_id AS team_source_id FROM g
        UNION SELECT season, away_source_id FROM g
    ),
    s AS (
        SELECT p.*, a.game_source_id AS advanced_game, {metrics}
        FROM ({played}) p
        LEFT JOIN team_game_advanced a
          ON a.game_source_id = p.game_source_id AND a.team_source_id = p.team_source_id
         AND a.garbage_time_excluded  -- the only variant pulled (D-119); never mix in another
    )
    SELECT t.team_source_id, w.season, w.season_type, w.week, w.round, w.as_of,
        {features}
    FROM weeks w
    JOIN teams t USING (season)
    LEFT JOIN s ON s.season = w.season AND s.team_source_id = t.team_source_id AND {INCLUDED}
    WHERE t.team_source_id IS NOT NULL
    GROUP BY ALL
    ORDER BY w.season, w.as_of, w.season_type, w.week, w.round, t.team_source_id
    """


def game_features() -> str:
    """One row per staged game: both teams' features entering its week (round 1), `neutral_site`,
    the game's `round` and its round's `as_of` (`round_as_of`), and the target `margin =
    home_points - away_points` (NULL until the game is final). A side with no team row (a NULL
    team id) leaves its columns NULL, and with both missing `as_of` is NULL, which
    `check_point_in_time` names, so a game is never silently dropped."""
    sides = ",\n        ".join(
        f"{alias}.{name} AS {side}_{name}"
        for side, alias in (("home", "h"), ("away", "a"))
        for name in FEATURES
    )
    week = " AND ".join(f"{{t}}.{k} = g.{k}" for k in KEYS[1:4])
    on = f"{week} AND {{t}}.round = 1"
    return f"""
    WITH RECURSIVE g AS (SELECT *, {KICKOFF} AS kickoff FROM games),{ROUNDS},
    round_weeks AS (
        SELECT DISTINCT season, season_type, week, round, as_of FROM team_week_features
    )
    SELECT g.source_id AS game_source_id, g.season, g.season_type, g.week,
        coalesce(h.as_of, a.as_of) AS as_of,
        coalesce(r.round, 1) AS round, rw.as_of AS round_as_of,
        g.kickoff_at, g.neutral_site, g.home_source_id, g.away_source_id,
        {sides},
        CASE WHEN g.status = 'final' THEN g.home_points - g.away_points END AS margin
    FROM g
    LEFT JOIN rounds r ON r.source_id = g.source_id
    LEFT JOIN round_weeks rw ON {week.format(t="rw")} AND rw.round = coalesce(r.round, 1)
    LEFT JOIN team_week_features h ON h.team_source_id = g.home_source_id AND {on.format(t="h")}
    LEFT JOIN team_week_features a ON a.team_source_id = g.away_source_id AND {on.format(t="a")}
    ORDER BY g.season, coalesce(h.as_of, a.as_of), g.season_type, g.week, g.source_id
    """


def check_point_in_time(con: duckdb.DuckDBPyConnection) -> None:
    """Fail unless every feature row has an `as_of` and its newest source game finished
    (`GAME_HOURS` after kickoff) by then (docs/04-model.md § 9.2). The error names each
    offending team, season and week, and the round of a team row past round 1."""

    def offenders(table: str, team: str, last: str, label: str = "''", rnd: str = "''") -> str:
        return f"""SELECT concat({label}, 'team ', {team}, ', ', season, ' ', season_type,
                ' week ', week, {rnd}, CASE WHEN as_of IS NULL THEN ': as_of is NULL'
                ELSE concat(': its newest source game kicked off at ', {last},
                    ', less than {GAME_HOURS} hours before as_of ', as_of) END)
            FROM {table}
            WHERE as_of IS NULL OR {last} + INTERVAL {GAME_HOURS} HOURS > as_of"""

    rnd = "CASE WHEN round > 1 THEN concat(' round ', round) ELSE '' END"
    parts = [offenders("team_week_features", "team_source_id", "last_game_kickoff", rnd=rnd)] + [
        offenders(
            "game_features",
            f"{side}_source_id",
            f"{side}_last_game_kickoff",
            f"concat('game ', game_source_id, ' ({side}): ')",
        )
        for side in ("home", "away")
    ]
    sql = " UNION ALL ".join(parts)
    rows = [r[0] for r in con.execute(f"SELECT DISTINCT * FROM ({sql}) ORDER BY 1").fetchall()]
    if rows:
        shown = "\n".join(f"  {r}" for r in rows[:20])
        more = f"\n  … and {len(rows) - 20} more" if len(rows) > 20 else ""
        raise PointInTimeError(
            f"{len(rows)} feature rows read a game that didn't finish before their as_of "
            f"(point-in-time rule, D-042, D-127):\n{shown}{more}"
        )
