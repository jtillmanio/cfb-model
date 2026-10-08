"""`engine ingest games`: one CFBD /games call for one week (FBS games by default: every game
with an FBS team), saved raw, then published.

A week whose saved response is all completed games is never fetched again (CLAUDE.md:
never re-fetch completed CFBD weeks); it's re-published from the raw file instead.
"""

from __future__ import annotations

import json
import os

from db.session import make_engine
from engine.clock import now
from engine.ingest.cfbd import CallBudget, CfbdClient
from engine.ingest.lake import lake_root, latest_raw, partition, write_raw
from engine.publish.reference import publish_games_batch
from engine.sports.cfb.games import map_games


def ingest_games(
    season: int, week: int, season_type: str, classification: str, db_url: str
) -> None:
    folder = partition(
        "cfbd",
        "games",
        season=str(season),
        season_type=season_type,
        classification=classification,
        week=f"{week:02d}",
    )
    saved = latest_raw(folder)
    payload = json.loads(saved.read_text(encoding="utf-8")) if saved else None

    if payload and all(g.get("completed") for g in payload):
        print(f"Week complete in {saved}; publishing it with no API call.")
    else:
        client = CfbdClient(
            os.environ.get("CFBD_API_KEY", ""), CallBudget(lake_root() / "cfbd_calls.json")
        )
        params = {
            "year": season,
            "week": week,
            "seasonType": season_type,
            "classification": classification,
        }
        payload = client.get("/games", params)
        saved = write_raw(folder, now(), payload)
        print(
            f"Fetched {len(payload)} games -> {saved} (CFBD calls this month: "
            f"{client.budget.used()})"
        )

    batch = map_games(payload)
    with make_engine(db_url).begin() as conn:
        count = publish_games_batch(conn, "cfb", "cfbd", batch)
    print(f"Upserted {count} games, {len(batch.teams)} teams, {len(batch.venues)} venues.")
