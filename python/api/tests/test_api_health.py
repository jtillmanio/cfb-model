"""The API against the migrated, seeded test DB (APP_ENV=test routes it through the guard)."""

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch, test_db_url: str) -> TestClient:
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("GIT_COMMIT_SHA", "abc1234")
    from api import main

    main.engine.cache_clear()
    return TestClient(main.app)


def test_health_reports_commit_db_and_migration_head(client: TestClient):
    body = client.get("/api/py/health").json()
    assert body == {"commit": "abc1234", "db_reachable": True, "migration_head": "0001"}


def test_teams_returns_the_seeded_fixture_season(client: TestClient):
    body = client.get("/api/py/teams").json()
    assert body["season"] == 2026
    ohio_state = next(t for t in body["teams"] if t["school"] == "Ohio State")
    assert ohio_state == {
        "id": ohio_state["id"],
        "school": "Ohio State",
        "abbreviation": "OSU",
        "conference": "Big Ten",
        "color": "#BB0000",
    }
