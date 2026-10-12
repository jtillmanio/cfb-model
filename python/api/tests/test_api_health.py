"""The API against the migrated, seeded test DB (fixtures in conftest.py)."""

from collections.abc import Callable

from fastapi.testclient import TestClient


def test_health_reports_commit_db_and_migration_head(client: TestClient):
    # No token: health is the one open route (TASK-004).
    body = client.get("/api/py/health").json()
    assert body == {"commit": "abc1234", "db_reachable": True, "migration_head": "0001"}


def test_teams_returns_the_seeded_fixture_season(
    client: TestClient, make_token: Callable[..., str]
):
    headers = {"Authorization": f"Bearer {make_token()}"}
    body = client.get("/api/py/teams", headers=headers).json()
    assert body["season"] == 2026
    ohio_state = next(t for t in body["teams"] if t["school"] == "Ohio State")
    assert ohio_state == {
        "id": ohio_state["id"],
        "school": "Ohio State",
        "abbreviation": "OSU",
        "conference": "Big Ten",
        "color": "#BB0000",
    }
