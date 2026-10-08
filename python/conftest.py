"""Shared pytest fixtures. Database tests get their URL only through the test-DB guard."""

from collections.abc import Iterator

import pytest
from sqlalchemy import Connection

from db.config import load_env, resolve_test_database_url
from db.session import make_engine


@pytest.fixture(scope="session")
def test_db_url() -> str:
    load_env()
    return resolve_test_database_url()


@pytest.fixture
def db_conn(test_db_url: str) -> Iterator[Connection]:
    """A connection to the migrated test DB whose writes are rolled back afterwards."""
    with make_engine(test_db_url).connect() as conn:
        tx = conn.begin()
        try:
            yield conn
        finally:
            tx.rollback()
