"""Every API route but health requires the JWT Next's server code signs (TASK-004, D-105)."""

import re
import time
from collections.abc import Callable, Iterator

import pytest
from fastapi.routing import iter_route_contexts
from fastapi.testclient import TestClient

# Tokens signed with a deliberately short or mismatched key are the point of some cases here.
pytestmark = pytest.mark.filterwarnings("ignore:The HMAC key is")

OPEN = {("GET", "/api/py/health")}
REFUSAL = {"detail": "Not authenticated"}

MakeToken = Callable[..., str]


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def registered_requests() -> Iterator[tuple[str, str]]:
    """(method, path) for every HTTP route the app registers, path parameters filled in."""
    from api.main import app

    # app.routes nests each included router; this flattens them with their prefixes.
    for route in iter_route_contexts(app.routes):
        if route.path and route.methods:
            path = re.sub(r"\{[^}]+\}", "1", route.path)
            for method in sorted(route.methods):
                yield method, path


def gated_requests() -> list[tuple[str, str]]:
    return [r for r in registered_requests() if r not in OPEN]


def test_the_route_walk_sees_the_data_routes_and_the_schema():
    paths = {path for _, path in registered_requests()}
    assert {"/api/py/teams", "/api/py/openapi.json", "/api/py/health"} <= paths


def test_every_route_but_health_requires_a_token(client: TestClient):
    # A route added later without the guard fails here.
    open_routes = [
        (method, path, response.status_code)
        for method, path in gated_requests()
        if (response := client.request(method, path)).status_code != 401
    ]
    assert open_routes == []


def test_a_non_bearer_scheme_is_refused(client: TestClient, make_token: MakeToken):
    response = client.get("/api/py/teams", headers={"Authorization": f"Basic {make_token()}"})
    assert response.status_code == 401


NOW = int(time.time())

BAD_TOKENS = {
    "expired": {"iat": NOW - 120, "exp": NOW - 60},
    "another-secret": {"secret": "another-secret-that-is-also-long-enough-0002"},
    "alg-none": {"secret": None, "algorithm": "none"},
    "alg-hs512": {"algorithm": "HS512"},
    "missing-sub": {"drop": ("sub",)},
    "empty-sub": {"sub": ""},
    "wrong-audience": {"aud": "some-other-api"},
    "wrong-issuer": {"iss": "some-other-web"},
}


@pytest.mark.parametrize("overrides", BAD_TOKENS.values(), ids=BAD_TOKENS.keys())
def test_a_bad_token_gets_401_and_no_team_data(
    client: TestClient, make_token: MakeToken, overrides: dict
):
    response = client.get("/api/py/teams", headers=bearer(make_token(**overrides)))
    assert response.status_code == 401
    assert "teams" not in response.json()


def test_a_few_seconds_past_exp_is_clock_skew_not_expiry(client: TestClient, make_token: MakeToken):
    now = int(time.time())
    token = make_token(iat=now - 62, exp=now - 2)
    response = client.get("/api/py/teams", headers=bearer(token))
    assert response.status_code == 200
    assert response.json()["season"] == 2026


def test_a_secret_shorter_than_32_characters_refuses_even_its_own_tokens(
    client: TestClient, make_token: MakeToken, monkeypatch: pytest.MonkeyPatch
):
    short = "s" * 31
    monkeypatch.setenv("API_JWT_SECRET", short)
    response = client.get("/api/py/teams", headers=bearer(make_token(secret=short)))
    assert response.status_code == 401


def test_unset_secret_fails_closed(
    client: TestClient, make_token: MakeToken, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.delenv("API_JWT_SECRET", raising=False)
    token = make_token()
    open_routes = [
        (method, path, response.status_code)
        for method, path in gated_requests()
        if (response := client.request(method, path, headers=bearer(token))).status_code != 401
    ]
    assert open_routes == []


def test_health_open_without_secret(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("API_JWT_SECRET", raising=False)
    response = client.get("/api/py/health")
    assert response.status_code == 200
    assert set(response.json()) == {"commit", "db_reachable", "migration_head"}


def test_401_body_is_fixed(client: TestClient, make_token: MakeToken, api_jwt_secret: str):
    bad = make_token(secret="another-secret-that-is-also-long-enough-0002")
    for headers in ({}, bearer(bad), bearer(make_token(aud="some-other-api"))):
        response = client.get("/api/py/teams", headers=headers)
        assert response.status_code == 401
        assert response.json() == REFUSAL
        assert response.headers["www-authenticate"] == "Bearer"
        token = headers.get("Authorization", "").removeprefix("Bearer ")
        assert not token or token not in response.text
        assert api_jwt_secret not in response.text
