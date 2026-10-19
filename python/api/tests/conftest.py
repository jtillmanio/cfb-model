"""API fixtures: a client against the migrated, seeded test DB and a factory for API tokens."""

import time
from collections.abc import Callable
from typing import Any

import jwt
import pytest
from fastapi.testclient import TestClient

# Test-only key, set per test so a value in .env.local or CI's job env never decides a result.
TEST_SECRET = "pytest-only-api-jwt-secret-never-used-anywhere-0001"

MakeToken = Callable[..., str]


def make_token(
    *,
    secret: str = TEST_SECRET,
    algorithm: str = "HS256",
    drop: tuple[str, ...] = (),
    **claims: Any,
) -> str:
    """A token shaped like web/lib/api-token.ts mints (D-105); keyword claims override it."""
    now = int(time.time())
    payload = {
        "sub": "4242",
        "iss": "cfb-model-web",
        "aud": "cfb-model-api",
        "iat": now,
        "exp": now + 60,
    } | claims
    for name in drop:
        del payload[name]
    return jwt.encode(payload, secret, algorithm=algorithm)


@pytest.fixture(name="make_token")
def make_token_fixture() -> MakeToken:
    return make_token


@pytest.fixture
def api_jwt_secret() -> str:
    """The secret the `client` fixture gives the API."""
    return TEST_SECRET


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch, test_db_url: str) -> TestClient:
    """APP_ENV=test routes the API's database through the test-DB guard."""
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("GIT_COMMIT_SHA", "abc1234")
    monkeypatch.setenv("API_JWT_SECRET", TEST_SECRET)
    from api import main

    main.engine.cache_clear()
    return TestClient(main.app)
