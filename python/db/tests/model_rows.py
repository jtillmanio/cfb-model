"""Constructed model rows for the view tests (TASK-035): teams with a season's division, a
version, runs and their ratings, and games, all under the throwaway sport `pytest`, so the
fixture's `cfb` versions never interfere. Every test that uses them rolls back (db_conn)."""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta

from sqlalchemy import Connection, text

SPORT = "pytest"
SEASON = 2030


def utc(*args: int) -> datetime:
    return datetime(*args, tzinfo=UTC)


def sport(conn: Connection) -> None:
    conn.execute(
        text("INSERT INTO sports (id, name) VALUES (:s, 'pytest') ON CONFLICT DO NOTHING"),
        {"s": SPORT},
    )


def team(conn: Connection, source_id: str, division: str | None = "fbs") -> int:
    team_id = conn.execute(
        text(
            "INSERT INTO teams (sport_id, source, source_id, school)"
            " VALUES (:sport, 'pytest', :sid, :sid) RETURNING id"
        ),
        {"sport": SPORT, "sid": source_id},
    ).scalar_one()
    if division is not None:
        conn.execute(
            text(
                "INSERT INTO team_seasons (team_id, season, division) VALUES (:t, :season, :d)"
            ),
            {"t": team_id, "season": SEASON, "d": division},
        )
    return team_id


def version(conn: Connection, name: str = "views") -> int:
    return conn.execute(
        text(
            "INSERT INTO model_versions (sport_id, market, name, version, spec,"
            " spec_schema_version, created_by, status)"
            " VALUES (:sport, 'spread', :name, 'v1', '{}', 1, 'user', 'dev') RETURNING id"
        ),
        {"sport": SPORT, "name": name},
    ).scalar_one()


def run(
    conn: Connection,
    version_id: int,
    week: int,
    as_of: datetime,
    *,
    status: str = "succeeded",
    finished_at: datetime | None = None,
    home_field: float | None = 3.0,
) -> int:
    params = None if home_field is None else json.dumps({"home_field": home_field})
    return conn.execute(
        text(
            "INSERT INTO model_runs (model_version_id, run_type, season, week, as_of, status,"
            " started_at, finished_at, fitted_params)"
            " VALUES (:v, 'adhoc', :season, :week, :as_of, :status, :as_of, :finished,"
            " CAST(:params AS jsonb)) RETURNING id"
        ),
        {
            "v": version_id,
            "season": SEASON,
            "week": week,
            "as_of": as_of,
            "status": status,
            "finished": finished_at or as_of + timedelta(minutes=5),
            "params": params,
        },
    ).scalar_one()


def ratings(
    conn: Connection,
    run_id: int,
    version_id: int,
    week: int,
    as_of: datetime,
    by_team: Mapping[int, float],
) -> None:
    conn.execute(
        text(
            "INSERT INTO team_ratings (model_run_id, model_version_id, team_id, season, week,"
            " as_of, rating) VALUES (:r, :v, :t, :season, :week, :as_of, :rating)"
        ),
        [
            {
                "r": run_id,
                "v": version_id,
                "t": t,
                "season": SEASON,
                "week": week,
                "as_of": as_of,
                "rating": rating,
            }
            for t, rating in by_team.items()
        ],
    )


def game(
    conn: Connection,
    home: int,
    away: int,
    kickoff_at: datetime | None,
    *,
    week: int,
    neutral: bool = False,
    status: str = "final",
    game_date: str | None = None,
    season: int = SEASON,
) -> int:
    final = status == "final"
    return conn.execute(
        text(
            "INSERT INTO games (sport_id, source, source_id, season, week, season_type, game_date,"
            " kickoff_at, neutral_site, conference_game, home_team_id, away_team_id, home_points,"
            " away_points, status)"
            " VALUES (:sport, 'pytest', :sid, :season, :week, 'regular', :d, :k, :n, false, :h,"
            " :a, :hp, :ap, :status) RETURNING id"
        ),
        {
            "sport": SPORT,
            "sid": f"{home}-{away}-{season}-{week}",
            "season": season,
            "week": week,
            "d": game_date or (kickoff_at.date().isoformat() if kickoff_at else None),
            "k": kickoff_at,
            "n": neutral,
            "h": home,
            "a": away,
            "hp": 30 if final else None,
            "ap": 20 if final else None,
            "status": status,
        },
    ).scalar_one()
