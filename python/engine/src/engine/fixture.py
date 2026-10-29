"""`engine seed fixture`: load python/db/seeds/fixture/ into the test DB only (D-089).

Refuses any target but TEST_DATABASE_URL (through the one guard) and refuses under LIVE=true.
Every reference row has source = 'fixture', so it can never collide with a real CFBD row. The
model registry has no source column; its rows are found by sport, market, name and version.
Re-seeding changes nothing: reference rows are upserted, line snapshots, ratings, predictions and
picks skip a key already stored, and a version or run that exists is reused. picks.json is written
by its generator, generate_picks.py, beside it (TASK-040).
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import Connection, text

from db.config import refuse_if_live, repo_root, resolve_test_database_url
from db.session import make_engine
from engine.core.spec import ModelSpec
from engine.publish.reference import (
    insert_line_snapshots,
    upsert_games,
    upsert_season,
    upsert_sportsbooks,
    upsert_team_seasons,
    upsert_teams,
    upsert_venues,
)

FIXTURE_DIR = repo_root() / "python" / "db" / "seeds" / "fixture"
SOURCE = "fixture"
SPORT = "cfb"
WEEK = 6
BOOK = "consensus"


def _load(name: str) -> dict[str, Any]:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def load_teams() -> dict[str, Any]:
    return _load("teams.json")


def _seed_teams(conn: Connection, data: dict[str, Any]) -> dict[str, int]:
    teams = data["teams"]
    ids = upsert_teams(
        conn,
        SPORT,
        SOURCE,
        [{k: t[k] for k in ("source_id", "school", "abbreviation", "color")} for t in teams],
    )
    upsert_team_seasons(
        conn,
        [
            {
                "team_id": ids[t["source_id"]],
                "season": data["season"],
                "conference": t["conference"],
                "division": t["division"],
            }
            for t in teams
        ],
    )
    return ids


def _upsert_games(
    conn: Connection,
    season: int,
    games: list[dict[str, Any]],
    team_ids: dict[str, int],
    venue_ids: dict[str, int],
) -> dict[str, int]:
    """Games of `season`; a game with no `week` is week 6's. Returns ids by source id."""
    return upsert_games(
        conn,
        SPORT,
        SOURCE,
        [
            {
                "source_id": g["source_id"],
                "season": season,
                "week": g.get("week", WEEK),
                "season_type": "regular",
                "game_date": date.fromisoformat(g["game_date"]),
                "kickoff_at": datetime.fromisoformat(g["kickoff_at"]),
                "neutral_site": g["neutral_site"],
                "conference_game": g["conference_game"],
                "venue_id": None if g.get("venue") is None else venue_ids[g["venue"]],
                "home_team_id": team_ids[g["home"]],
                "away_team_id": team_ids[g["away"]],
                "home_points": g["home_points"],
                "away_points": g["away_points"],
                "status": g["status"],
            }
            for g in games
        ],
    )


def _insert_lines(
    conn: Connection, games: list[dict[str, Any]], game_ids: dict[str, int], book_id: int
) -> int:
    """The games' line snapshots from the one fixture book. Returns how many were new."""
    return insert_line_snapshots(
        conn,
        SOURCE,
        [
            {
                "game_id": game_ids[g["source_id"]],
                "book_id": book_id,
                "kind": line["kind"],
                "captured_at": _ts(line["captured_at"]),
                "spread_home": line["spread_home"],
            }
            for g in games
            for line in g["lines"]
        ],
    )


def _seed_week(
    conn: Connection, data: dict[str, Any], team_ids: dict[str, int]
) -> tuple[dict[str, int], int, int]:
    """Week 6: the season row, the book, the venue, the slate games and their lines. Returns
    the game ids by source id, the number of new line snapshots and the book's id."""
    season = data["season"]
    upsert_season(
        conn,
        {
            "sport_id": SPORT,
            "year": season["year"],
            "source": SOURCE,
            "start_date": date.fromisoformat(season["start_date"]),
            "end_date": date.fromisoformat(season["end_date"]),
            "current_week": season["current_week"],
            "weeks": season["weeks"],
        },
    )
    book_id = upsert_sportsbooks(conn, SOURCE, data["sportsbooks"])[BOOK]
    venue_ids = upsert_venues(conn, SOURCE, data["venues"])
    game_ids = _upsert_games(conn, season["year"], data["games"], team_ids, venue_ids)
    return game_ids, _insert_lines(conn, data["games"], game_ids, book_id), book_id


# A scheduled run starts just before 6:00 AM ET on the Sunday its week begins and finishes at
# 6:00, after the previous week's games and before the M4.5 fixture pick at Sun 6:10 AM.
RUN_STARTS_AFTER = timedelta(hours=5, minutes=55)
RUN_FINISHES_AFTER = timedelta(hours=6)


def _ts(value: str | None) -> datetime | None:
    return None if value is None else datetime.fromisoformat(value)


def _jsonb(value: Any) -> str | None:
    """A bind value for `CAST(:x AS jsonb)`: NULL stays SQL NULL, not JSON null."""
    return None if value is None else json.dumps(value)


def _seed_versions(conn: Connection, data: dict[str, Any]) -> dict[str, int]:
    """Versions in parent-first order; an existing one is reused, never changed."""
    ids: dict[str, int] = {}
    for v in data["versions"]:
        spec = ModelSpec.model_validate(v["spec"])  # refuse a spec the engine can't build
        key = {
            "sport": data["sport"],
            "market": data["market"],
            "name": data["name"],
            "version": v["version"],
        }
        conn.execute(
            text(
                "INSERT INTO model_versions (sport_id, market, name, version, description, spec,"
                " spec_schema_version, parent_version_id, created_by, status, created_at)"
                " VALUES (:sport, :market, :name, :version, :description, CAST(:spec AS jsonb),"
                " :schema, :parent, 'system', :status, :created_at)"
                " ON CONFLICT (sport_id, market, name, version) WHERE deleted_at IS NULL"
                " DO NOTHING"
            ),
            {
                **key,
                "description": v["description"],
                "spec": _jsonb(v["spec"]),
                "schema": spec.spec_schema_version,
                "parent": None if v["parent"] is None else ids[v["parent"]],
                "status": v["status"],
                "created_at": _ts(v["created_at"]),
            },
        )
        ids[v["version"]] = conn.execute(
            text(
                "SELECT id FROM model_versions WHERE sport_id = :sport AND market = :market"
                " AND name = :name AND version = :version AND deleted_at IS NULL"
            ),
            key,
        ).scalar_one()
    return ids


def _seed_run(conn: Connection, version_id: int, run: dict[str, Any]) -> int:
    """The version's run of this type for this season and week, inserted if missing."""
    found = conn.execute(
        text(
            "SELECT id FROM model_runs WHERE model_version_id = :version_id"
            " AND run_type = :run_type AND season IS NOT DISTINCT FROM CAST(:season AS int)"
            " AND week IS NOT DISTINCT FROM CAST(:week AS int)"
        ),
        {"version_id": version_id, **{k: run[k] for k in ("run_type", "season", "week")}},
    ).scalar_one_or_none()
    if found is not None:
        return found
    return conn.execute(
        text(
            "INSERT INTO model_runs (model_version_id, run_type, season, week, as_of, status,"
            " requested_at, started_at, finished_at, fitted_params, metrics)"
            " VALUES (:version_id, :run_type, :season, :week, :as_of, :status, :requested_at,"
            " :started_at, :finished_at, CAST(:fitted_params AS jsonb), CAST(:metrics AS jsonb))"
            " RETURNING id"
        ),
        {
            "version_id": version_id,
            **run,
            "fitted_params": _jsonb(run["fitted_params"]),
            "metrics": _jsonb(run["metrics"]),
        },
    ).scalar_one()


def _week_starts(week_data: dict[str, Any]) -> dict[int, datetime]:
    return {
        w["week"]: datetime.fromisoformat(w["start"])
        for w in week_data["season"]["weeks"]
        if w["season_type"] == "regular"
    }


def _scheduled_run(
    conn: Connection, version_id: int, season: int, week: int, as_of: datetime
) -> tuple[int, datetime]:
    """The version's weekly run, entering `week`. Returns its id and finish time."""
    finished = as_of + RUN_FINISHES_AFTER
    run_id = _seed_run(
        conn,
        version_id,
        {
            "run_type": "scheduled",
            "season": season,
            "week": week,
            "as_of": as_of,
            "status": "succeeded",
            "requested_at": as_of + RUN_STARTS_AFTER,
            "started_at": as_of + RUN_STARTS_AFTER,
            "finished_at": finished,
            "fitted_params": None,
            "metrics": None,
        },
    )
    return run_id, finished


def _seed_models(
    conn: Connection,
    data: dict[str, Any],
    week_data: dict[str, Any],
    team_ids: dict[str, int],
    game_ids: dict[str, int],
) -> tuple[int, int, dict[str, int]]:
    """The registry, its backtests, the weekly ratings and the week-6 predictions. Returns the
    number of new ratings and predictions, and the version ids by version."""
    version_ids = _seed_versions(conn, data)
    for b in data["backtests"]:
        _seed_run(
            conn,
            version_ids[b["version"]],
            {
                "run_type": "backtest",
                "season": None,
                "week": None,
                "as_of": None,
                "status": b["status"],
                "requested_at": _ts(b["requested_at"]),
                "started_at": _ts(b["started_at"]),
                "finished_at": _ts(b["finished_at"]),
                "fitted_params": b["fitted_params"],
                "metrics": b["metrics"],
            },
        )

    starts = _week_starts(week_data)
    ratings = data["ratings"]
    version_id = version_ids[ratings["version"]]
    prior = next(
        b["fitted_params"]["prior_weight_by_week"]
        for b in data["backtests"]
        if b["version"] == ratings["version"]
    )
    units = ratings["units"]
    rating_rows: list[dict[str, Any]] = []
    runs: dict[int, tuple[int, datetime]] = {}
    for i, week in enumerate(ratings["weeks"]):
        runs[week] = _scheduled_run(conn, version_id, ratings["season"], week, starts[week])
        run_id, finished = runs[week]
        for team, by_week in ratings["teams"].items():
            unit = units["teams"].get(team, {}) if week == units["week"] else {}
            rating_rows.append(
                {
                    "run_id": run_id,
                    "version_id": version_id,
                    "team_id": team_ids[team],
                    "season": ratings["season"],
                    "week": week,
                    "as_of": starts[week],
                    "rating": by_week[i],
                    "off": unit.get("off"),
                    "def": unit.get("def"),
                    "prior_weight": prior[str(week)],
                    "created_at": finished,
                }
            )
    new_ratings = conn.execute(
        text(
            "INSERT INTO team_ratings (model_run_id, model_version_id, team_id, season, week,"
            " as_of, rating, off_rating, def_rating, prior_weight, created_at)"
            " VALUES (:run_id, :version_id, :team_id, :season, :week, :as_of, :rating, :off,"
            " :def, :prior_weight, :created_at) ON CONFLICT DO NOTHING"
        ),
        rating_rows,
    ).rowcount

    preds = data["predictions"]
    run_id, finished = runs[preds["week"]]
    new_predictions = conn.execute(
        text(
            "INSERT INTO predictions (model_run_id, model_version_id, game_id, created_at,"
            " pred_margin, pred_total, home_win_prob, margin_sd, drivers)"
            " VALUES (:run_id, :version_id, :game_id, :created_at, :pred_margin, :pred_total,"
            " :home_win_prob, :margin_sd, CAST(:drivers AS jsonb))"
            " ON CONFLICT (model_run_id, game_id) DO NOTHING"
        ),
        [
            {
                "run_id": run_id,
                "version_id": version_ids[preds["version"]],
                "game_id": game_ids[p["game"]],
                "created_at": finished,
                "pred_margin": p["pred_margin"],
                "pred_total": p.get("pred_total"),
                "home_win_prob": p["home_win_prob"],
                "margin_sd": preds["margin_sd"],
                "drivers": _jsonb(p.get("drivers")),
            }
            for p in preds["games"]
        ],
    ).rowcount
    return new_ratings, new_predictions, version_ids


def _seed_picks(
    conn: Connection,
    data: dict[str, Any],
    week_data: dict[str, Any],
    team_ids: dict[str, int],
    game_ids: dict[str, int],
    book_id: int,
    version_id: int,
) -> tuple[int, int, int]:
    """picks.json: the weeks 1-5 games and the week-6 games the slate doesn't show, their lines
    and the version's predictions under its weekly runs, then every pick at the snapshot it was
    made at. Returns the number of new line snapshots, predictions and picks."""
    season = data["season"]
    game_ids = {**game_ids, **_upsert_games(conn, season, data["games"], team_ids, {})}
    new_lines = _insert_lines(conn, data["games"], game_ids, book_id)

    starts = _week_starts(week_data)
    runs = {
        week: _scheduled_run(conn, version_id, season, week, starts[week])
        for week in sorted({p["week"] for p in data["predictions"] + data["picks"]})
    }
    new_predictions = conn.execute(
        text(
            "INSERT INTO predictions (model_run_id, model_version_id, game_id, created_at,"
            " pred_margin, home_win_prob, margin_sd)"
            " VALUES (:run_id, :version_id, :game_id, :created_at, :pred_margin, :home_win_prob,"
            " :margin_sd) ON CONFLICT (model_run_id, game_id) DO NOTHING"
        ),
        [
            {
                "run_id": runs[p["week"]][0],
                "version_id": version_id,
                "game_id": game_ids[p["game"]],
                "created_at": runs[p["week"]][1],
                "pred_margin": p["pred_margin"],
                "home_win_prob": p["home_win_prob"],
                "margin_sd": data["margin_sd"],
            }
            for p in data["predictions"]
        ],
    ).rowcount

    picked = [game_ids[p["game"]] for p in data["picks"]]
    prediction_ids = {
        (r.model_run_id, r.game_id): r.id
        for r in conn.execute(
            text(
                "SELECT id, model_run_id, game_id FROM predictions"
                " WHERE model_version_id = :v AND game_id = ANY(:games)"
            ),
            {"v": version_id, "games": picked},
        )
    }
    snapshot_ids = {
        (r.game_id, r.captured_at): r.id
        for r in conn.execute(
            text(
                "SELECT id, game_id, captured_at FROM line_snapshots"
                " WHERE source = :source AND book_id = :book AND kind = 'snapshot'"
                " AND game_id = ANY(:games)"
            ),
            {"source": SOURCE, "book": book_id, "games": picked},
        )
    }
    rows = []
    for p in data["picks"]:
        game_id = game_ids[p["game"]]
        rows.append(
            {
                "prediction_id": prediction_ids[(runs[p["week"]][0], game_id)],
                "version_id": version_id,
                "game_id": game_id,
                "snapshot_id": snapshot_ids[(game_id, _ts(p["snapshot"]["captured_at"]))],
                **{
                    k: p[k]
                    for k in (
                        "market", "side", "line", "price", "model_prob", "edge_pts",
                        "expected_value", "tier", "stake_units",
                    )
                },  # fmt: skip
                "created_at": _ts(p["created_at"]),
            }
        )
    new_picks = conn.execute(
        text(
            "INSERT INTO picks (prediction_id, model_version_id, game_id, line_snapshot_id,"
            " market, side, line, price, model_prob, edge_pts, expected_value, tier,"
            " stake_units, created_at)"
            " VALUES (:prediction_id, :version_id, :game_id, :snapshot_id, :market, :side, :line,"
            " :price, :model_prob, :edge_pts, :expected_value, :tier, :stake_units, :created_at)"
            " ON CONFLICT (prediction_id, market, line_snapshot_id) DO NOTHING"
        ),
        rows,
    ).rowcount
    return new_lines, new_predictions, new_picks


def seed_fixture() -> None:
    refuse_if_live("seed the fixture")
    url = resolve_test_database_url()
    teams = load_teams()
    week = _load("week6.json")
    models = _load("models.json")
    picks = _load("picks.json")
    with make_engine(url).begin() as conn:
        team_ids = _seed_teams(conn, teams)
        game_ids, lines, book_id = _seed_week(conn, week, team_ids)
        ratings, predictions, version_ids = _seed_models(conn, models, week, team_ids, game_ids)
        more_lines, more_predictions, new_picks = _seed_picks(
            conn, picks, week, team_ids, game_ids, book_id, version_ids[picks["version"]]
        )
    print(
        f"Seeded {len(teams['teams'])} fixture teams for {teams['season']}, "
        f"{len(week['games']) + len(picks['games'])} games and {lines + more_lines} new line"
        f" snapshots, {len(models['versions'])} model versions, {ratings} new ratings,"
        f" {predictions + more_predictions} new predictions and {new_picks} new picks into the"
        " test DB."
    )
