"""`engine seed fixture`: load python/db/seeds/fixture/ into the test DB only (D-089).

Refuses any target but TEST_DATABASE_URL (through the one guard) and refuses under LIVE=true.
Every row has source = 'fixture', so it can never collide with a real CFBD row. Re-seeding
changes nothing: reference rows are upserted and line snapshots skip a key already stored.
"""

from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any

from sqlalchemy import Connection

from db.config import refuse_if_live, repo_root, resolve_test_database_url
from db.session import make_engine
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


def _seed_week(conn: Connection, data: dict[str, Any], team_ids: dict[str, int]) -> int:
    """Week 6: the season row, the book, the venue, the slate games and their lines."""
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
    book_ids = upsert_sportsbooks(conn, SOURCE, data["sportsbooks"])
    venue_ids = upsert_venues(conn, SOURCE, data["venues"])
    games = data["games"]
    game_ids = upsert_games(
        conn,
        SPORT,
        SOURCE,
        [
            {
                "source_id": g["source_id"],
                "season": season["year"],
                "week": WEEK,
                "season_type": "regular",
                "game_date": date.fromisoformat(g["game_date"]),
                "kickoff_at": datetime.fromisoformat(g["kickoff_at"]),
                "neutral_site": g["neutral_site"],
                "conference_game": g["conference_game"],
                "venue_id": None if g["venue"] is None else venue_ids[g["venue"]],
                "home_team_id": team_ids[g["home"]],
                "away_team_id": team_ids[g["away"]],
                "home_points": g["home_points"],
                "away_points": g["away_points"],
                "status": g["status"],
            }
            for g in games
        ],
    )
    return insert_line_snapshots(
        conn,
        SOURCE,
        [
            {
                "game_id": game_ids[g["source_id"]],
                "book_id": book_ids[BOOK],
                "kind": line["kind"],
                "captured_at": None
                if line["captured_at"] is None
                else datetime.fromisoformat(line["captured_at"]),
                "spread_home": line["spread_home"],
            }
            for g in games
            for line in g["lines"]
        ],
    )


def seed_fixture() -> None:
    refuse_if_live("seed the fixture")
    url = resolve_test_database_url()
    teams = load_teams()
    week = _load("week6.json")
    with make_engine(url).begin() as conn:
        team_ids = _seed_teams(conn, teams)
        lines = _seed_week(conn, week, team_ids)
    print(
        f"Seeded {len(teams['teams'])} fixture teams for {teams['season']}, "
        f"{len(week['games'])} week {WEEK} games and {lines} new line snapshots into the test DB."
    )
