"""Shared pytest fixtures. Database tests get their URL only through the test-DB guard."""

import uuid
from collections.abc import Callable, Iterator

import pytest
from sqlalchemy import Connection, make_url, text

from db.config import load_env, resolve_test_database_url
from db.session import make_engine, sqlalchemy_url


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


@pytest.fixture
def stamped_url(test_db_url: str) -> Iterator[Callable[[str | None], str]]:
    """A database that says it's migrated to `revision`: a new schema of the test DB holding only
    Alembic's `alembic_version` table with that one row (None: no row, an empty database), and a
    URL whose search_path is that schema. A revision the migrations don't know stands in for a
    production a release has migrated ahead of the code. Each schema is dropped afterwards.

    The search_path goes in the URL's `options`, replacing any already there, so this needs
    TEST_DATABASE_URL to be a direct host (local Postgres in CI), not a pooled one."""
    admin = make_engine(test_db_url)
    schemas: list[str] = []

    def stamp(revision: str | None) -> str:
        schema = f"pytest_{uuid.uuid4().hex[:12]}"
        with admin.begin() as conn:
            conn.execute(text(f'CREATE SCHEMA "{schema}"'))
            conn.execute(
                text(
                    f'CREATE TABLE "{schema}".alembic_version '
                    "(version_num VARCHAR(32) PRIMARY KEY)"
                )
            )
            if revision is not None:
                conn.execute(
                    text(f'INSERT INTO "{schema}".alembic_version VALUES (:rev)'),
                    {"rev": revision},
                )
        schemas.append(schema)  # only once it exists, so a failed stamp leaves nothing to drop
        url = make_url(sqlalchemy_url(test_db_url)).update_query_dict(
            {"options": f"-csearch_path={schema}"}
        )
        return url.render_as_string(hide_password=False)

    try:
        yield stamp
    finally:
        with admin.begin() as conn:
            for schema in schemas:
                conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
