"""The app shell's data, carried in every screen endpoint's response (TASK-054 draws it): the
season and coming week, the shown model version and its season record, when lines were last
pulled and whether they're stale, and the week's pick count. One statement, so a screen spends
one query of its budget on it (docs/02-architecture.md › Components › 2).

- **Coming week:** the week of the earliest game cutoff still to come (`kickoff_at`, or the end
  of `game_date` in Eastern time when the kickoff is TBA, as `current_picks`), the regular season
  first on a tie (D-150's `due_weeks`). None once every stored game has started: the season is
  then the last one with games and its record is `final`.
- **Shown version:** the (sport, `spread`) `production` version, else the newest `candidate` with
  a `succeeded` `scheduled` run that season (production's v1.0 is paper-traded as `candidate`,
  D-144). M23's model switcher replaces this (D-147).
- **Record:** `model_record`'s newest `to_date` row for the version and season (D-142: the newest
  week's to-date row is the season; `win_pct` 0–100).
- **Lines updated:** the newest `snapshot` `captured_at` up to now on the season's games (each
  `lines` pull inserts a row per book at its `captured_at`; a later one, at a fixture time before
  it, hasn't happened yet). **Stale:** more than 24 h before now while a week
  is still to come (docs/02 › Non-functional requirements, D-096); exactly 24 h is not stale.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel
from sqlalchemy import Connection, Row, TextClause, text

SPORT = "cfb"
STALE_AFTER = timedelta(hours=24)


class ShellModelOut(BaseModel):
    name: str
    version: str


class ShellRecordOut(BaseModel):
    wins: int
    losses: int
    pushes: int
    win_pct: float | None
    units: float
    avg_clv: float | None


class ShellOut(BaseModel):
    season: int | None
    season_type: Literal["regular", "postseason"] | None
    week: int | None
    model: ShellModelOut | None
    record: ShellRecordOut | None
    record_label: Literal["live", "final"] | None
    lines_updated_at: datetime | None
    stale: bool
    picks: int | None
    # The off-season (no coming week): the next season and its first week still ahead, from
    # `seasons.weeks` (D-164). None in season, or when no later season's calendar is stored.
    next_season: int | None
    next_week: int | None


# Each CTE reads only the ones before it, and each is one row at most. The record and pick reads
# filter the views by scalar subqueries, which Postgres applies at the picks scan (the views'
# partitions and GROUP BY hold the version and season), so only the shown version is graded.
CUTOFF = "coalesce(g.kickoff_at, (g.game_date + 1)::timestamp AT TIME ZONE 'America/New_York')"

# The coming week and the shown version, shared with the other screens' statements (slate.py) so
# every screen agrees with its shell. `SHOWN` reads `SEASON`, which reads `COMING`.
COMING = f"""coming AS (
        SELECT g.season, g.season_type, g.week
        FROM games g
        WHERE g.sport_id = :sport AND {CUTOFF} > :now
        ORDER BY {CUTOFF}, g.season_type = 'postseason', g.week
        LIMIT 1
    )"""

# The season the shown version is chosen for: the coming week's, else the latest with games.
SEASON = """season AS (
        SELECT coalesce(
            (SELECT season FROM coming),
            (SELECT max(season) FROM games WHERE sport_id = :sport)
        ) AS season
    )"""

SHOWN = """shown AS (
        SELECT v.id, v.name, v.version
        FROM model_versions v
        WHERE v.sport_id = :sport
            AND v.market = 'spread'
            AND v.deleted_at IS NULL
            AND (
                v.status = 'production'
                OR (
                    v.status = 'candidate'
                    AND EXISTS (
                        SELECT 1
                        FROM model_runs r
                        WHERE r.model_version_id = v.id
                            AND r.run_type = 'scheduled'
                            AND r.status = 'succeeded'
                            AND r.season = (SELECT season FROM season)
                    )
                )
            )
        ORDER BY v.status = 'production' DESC, v.created_at DESC, v.id DESC
        LIMIT 1
    )"""

# The earliest week still ahead in a season after `season`, only with no coming week (D-164).
# CFBD's calendar `start` is UTC ISO text; weeks are numbered as CFBD does (opening Saturday: 1).
NEXT_WEEK = """next_week AS (
        SELECT s.year AS season, (w.value ->> 'week')::int AS week,
            (w.value ->> 'start')::timestamptz AS start
        FROM seasons s
        CROSS JOIN LATERAL jsonb_array_elements(s.weeks) AS w
        WHERE s.sport_id = :sport
            AND s.year > (SELECT season FROM season)
            AND (w.value ->> 'start')::timestamptz > :now
            AND NOT EXISTS (SELECT 1 FROM coming)
        ORDER BY start, s.year
        LIMIT 1
    )"""

SHELL_SQL = text(
    f"""
    WITH {COMING},
    {SEASON},
    {SHOWN},
    {NEXT_WEEK},
    record AS (
        SELECT r.wins, r.losses, r.pushes, r.win_pct, r.units, r.avg_clv
        FROM model_record r
        WHERE r.model_version_id = (SELECT id FROM shown)
            AND r.season = (SELECT season FROM season)
            AND r.breakdown = 'to_date'
        ORDER BY r.season_type = 'postseason' DESC, r.week DESC
        LIMIT 1
    ),
    week_picks AS (
        SELECT count(*) AS n
        FROM current_picks c
        JOIN games g ON g.id = c.game_id
        WHERE c.model_version_id = (SELECT id FROM shown)
            AND c.line_source = 'market'
            AND (g.season, g.season_type, g.week)
                = (SELECT season, season_type, week FROM coming)
    ),
    lines AS (
        SELECT max(l.captured_at) AS at
        FROM line_snapshots l
        JOIN games g ON g.id = l.game_id
        WHERE l.kind = 'snapshot'
            AND l.captured_at <= :now
            AND g.sport_id = :sport
            AND g.season = (SELECT season FROM season)
    )
    SELECT
        s.season,
        c.season_type,
        c.week,
        sh.name AS model_name,
        sh.version AS model_version,
        rec.wins,
        rec.losses,
        rec.pushes,
        rec.win_pct,
        rec.units,
        rec.avg_clv,
        (SELECT n FROM week_picks) AS picks,
        (SELECT at FROM lines) AS lines_updated_at,
        nw.season AS next_season,
        nw.week AS next_week,
        nw.start AS next_start
    FROM season s
    LEFT JOIN coming c ON true
    LEFT JOIN shown sh ON true
    LEFT JOIN record rec ON true
    LEFT JOIN next_week nw ON true
    """
)


def query(now: datetime, sport: str = SPORT) -> tuple[TextClause, dict[str, Any]]:
    """The statement and its parameters, for a screen's wave (wave.run_wave)."""
    return SHELL_SQL, {"now": now, "sport": sport}


def _float(value: Decimal | float | None) -> float | None:
    return None if value is None else float(value)


def shell_from(row: Row[Any], now: datetime) -> ShellOut:
    has_week = row.week is not None
    has_model = row.model_name is not None
    record = None
    if row.wins is not None:
        record = ShellRecordOut(
            wins=row.wins,
            losses=row.losses,
            pushes=row.pushes,
            win_pct=_float(row.win_pct),
            units=float(row.units),
            avg_clv=_float(row.avg_clv),
        )
    updated = row.lines_updated_at
    return ShellOut(
        season=row.season,
        season_type=row.season_type,
        week=row.week,
        model=ShellModelOut(name=row.model_name, version=row.model_version) if has_model else None,
        record=record,
        record_label=None if record is None else ("live" if has_week else "final"),
        lines_updated_at=updated,
        stale=has_week and updated is not None and now - updated > STALE_AFTER,
        picks=row.picks if has_week and has_model else None,
        next_season=row.next_season,
        next_week=row.next_week,
    )


def load(conn: Connection, now: datetime, sport: str = SPORT) -> ShellOut:
    """The shell on one connection (tests read it inside their rolled-back transaction)."""
    sql, params = query(now, sport)
    return shell_from(conn.execute(sql, params).one(), now)
