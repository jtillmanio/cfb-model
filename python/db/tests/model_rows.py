"""Constructed model rows for the view tests (TASK-035): teams with a season's division, a
version, runs and their ratings, and games, all under the throwaway sport `pytest`, so the
fixture's `cfb` versions never interfere. Every test that uses them rolls back (db_conn)."""

from __future__ import annotations

import json
import uuid
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from typing import Any

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
            text("INSERT INTO team_seasons (team_id, season, division) VALUES (:t, :season, :d)"),
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
    run_type: str = "adhoc",
) -> int:
    params = None if home_field is None else json.dumps({"home_field": home_field})
    return conn.execute(
        text(
            "INSERT INTO model_runs (model_version_id, run_type, season, week, as_of, status,"
            " started_at, finished_at, fitted_params)"
            " VALUES (:v, :run_type, :season, :week, :as_of, :status, :as_of, :finished,"
            " CAST(:params AS jsonb)) RETURNING id"
        ),
        {
            "v": version_id,
            "run_type": run_type,
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
    points: tuple[int, int] = (30, 20),
) -> int:
    """`points` is (home, away), kept only for a final game."""
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
            "hp": points[0] if final else None,
            "ap": points[1] if final else None,
            "status": status,
        },
    ).scalar_one()


def book(conn: Connection) -> int:
    return conn.execute(
        text(
            "INSERT INTO sportsbooks (source, source_id, name)"
            " VALUES ('pytest', :sid, 'Pytest') RETURNING id"
        ),
        {"sid": uuid.uuid4().hex},
    ).scalar_one()


def line(
    conn: Connection,
    game_id: int,
    book_id: int,
    captured_at: datetime | None,
    spread_home: float,
    kind: str = "snapshot",
) -> int:
    """One book's line for a game; an untimed (`captured_at` None) `closing` row is CFBD's close."""
    return conn.execute(
        text(
            "INSERT INTO line_snapshots (game_id, book_id, source, kind, captured_at, spread_home)"
            " VALUES (:g, :b, 'manual', :kind, :c, :s) RETURNING id"
        ),
        {"g": game_id, "b": book_id, "kind": kind, "c": captured_at, "s": spread_home},
    ).scalar_one()


def prediction(conn: Connection, run_id: int, version_id: int, game_id: int) -> int:
    return conn.execute(
        text(
            "INSERT INTO predictions (model_run_id, model_version_id, game_id, pred_margin,"
            " home_win_prob, margin_sd) VALUES (:r, :v, :g, 4.5, 0.63, 13.8) RETURNING id"
        ),
        {"r": run_id, "v": version_id, "g": game_id},
    ).scalar_one()


def pick(
    conn: Connection,
    prediction_id: int,
    version_id: int,
    game_id: int,
    snapshot_id: int,
    created_at: datetime,
    *,
    side: str | None,
    line: float,
    edge_pts: float = 3.5,
    tier: str | None = "B",
    **override: Any,
) -> int:
    """A spread pick at −110 for 1 unit, or a pass (`side` None: no tier, 0 units)."""
    values: dict[str, Any] = {
        "prediction_id": prediction_id,
        "model_version_id": version_id,
        "game_id": game_id,
        "line_snapshot_id": snapshot_id,
        "market": "spread",
        "side": side,
        "line": line,
        "price": -110,
        "model_prob": 0.6,
        "edge_pts": edge_pts,
        "expected_value": 0.145,
        "tier": tier if side is not None else None,
        "stake_units": 1.0 if side is not None else 0.0,
        "created_at": created_at,
        **override,
    }
    return conn.execute(
        text(
            f"INSERT INTO picks ({', '.join(values)})"
            f" VALUES ({', '.join(':' + c for c in values)}) RETURNING id"
        ),
        values,
    ).scalar_one()


def scans(plan: dict[str, Any], relation: str) -> list[dict[str, Any]]:
    """Every node of an `EXPLAIN (FORMAT JSON)` plan that reads `relation`."""
    found = [plan] if plan.get("Relation Name") == relation else []
    for child in plan.get("Plans", []):
        found += scans(child, relation)
    return found


def explain(conn: Connection, sql: str, params: Mapping[str, Any]) -> dict[str, Any]:
    """The plan of `sql` with sequential scans priced out, so any that remain are forced."""
    conn.execute(text("SET LOCAL enable_seqscan = off"))
    raw = conn.execute(text(f"EXPLAIN (FORMAT JSON) {sql}"), params).scalar_one()
    return (json.loads(raw) if isinstance(raw, str) else raw)[0]["Plan"]
