"""Connections. Neon's pooled endpoint runs PgBouncer in transaction mode, so prepared
statements stay off and SQLAlchemy keeps no pool of its own (serverless)."""

from __future__ import annotations

from sqlalchemy import Engine, create_engine
from sqlalchemy.pool import NullPool


def sqlalchemy_url(url: str) -> str:
    """Neon and CI hand out libpq URLs; SQLAlchemy needs the psycopg 3 driver named."""
    for prefix in ("postgresql://", "postgres://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url.removeprefix(prefix)
    return url


def make_engine(url: str) -> Engine:
    return create_engine(
        sqlalchemy_url(url),
        poolclass=NullPool,
        connect_args={"prepare_threshold": None},
    )
