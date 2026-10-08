"""Alembic environment. The target database comes from `python -m db` (config.attributes["url"])
or, for plain `alembic`, from `-x target=dev|test` resolved through db.config."""

from typing import cast

from alembic import context

from db.config import MigrationTarget, direct_url, load_env
from db.models import Base
from db.session import make_engine

config = context.config
target_metadata = Base.metadata


def _url() -> str:
    url = config.attributes.get("url")
    if url:
        return url
    load_env()
    target = context.get_x_argument(as_dictionary=True).get("target", "dev")
    if target not in ("dev", "test"):
        raise SystemExit(f"Unknown migration target {target!r}; use dev or test.")
    return direct_url(cast(MigrationTarget, target))


def run_migrations_online() -> None:
    with make_engine(_url()).connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    raise SystemExit("Offline (--sql) migrations aren't supported; run against a database.")
run_migrations_online()
