"""`engine seed fixture`: load python/db/seeds/fixture/ into the test DB only (D-089).

Refuses any target but TEST_DATABASE_URL (through the one guard) and refuses under LIVE=true.
Every row has source = 'fixture', so it can never collide with a real CFBD row.
"""

from __future__ import annotations

import json
from typing import Any

from db.config import refuse_if_live, repo_root, resolve_test_database_url
from db.session import make_engine
from engine.publish.reference import upsert_team_seasons, upsert_teams

FIXTURE_DIR = repo_root() / "python" / "db" / "seeds" / "fixture"
SOURCE = "fixture"


def load_teams() -> dict[str, Any]:
    return json.loads((FIXTURE_DIR / "teams.json").read_text(encoding="utf-8"))


def seed_fixture() -> None:
    refuse_if_live("seed the fixture")
    url = resolve_test_database_url()
    data = load_teams()
    season = data["season"]
    teams = data["teams"]
    with make_engine(url).begin() as conn:
        ids = upsert_teams(
            conn,
            "cfb",
            SOURCE,
            [{k: t[k] for k in ("source_id", "school", "abbreviation", "color")} for t in teams],
        )
        upsert_team_seasons(
            conn,
            [
                {
                    "team_id": ids[t["source_id"]],
                    "season": season,
                    "conference": t["conference"],
                    "division": t["division"],
                }
                for t in teams
            ],
        )
    print(f"Seeded {len(teams)} fixture teams for {season} into the test DB.")
