"""Migrate, re-apply views, and check the migration history."""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text

from db.session import make_engine

# python/db/src/db/migrate.py -> python/db
DB_DIR = Path(__file__).resolve().parents[2]
VIEWS_DIR = DB_DIR / "views"


def alembic_config(url: str) -> Config:
    cfg = Config(str(DB_DIR / "alembic.ini"))
    cfg.attributes["url"] = url
    return cfg


def upgrade(url: str) -> None:
    """Apply migrations to head, then re-apply every view (views/*.sql, in name order)."""
    command.upgrade(alembic_config(url), "head")
    apply_views(url)


def apply_views(url: str) -> list[str]:
    applied = []
    with make_engine(url).begin() as conn:
        for sql_file in sorted(VIEWS_DIR.glob("*.sql")):
            conn.execute(text(sql_file.read_text(encoding="utf-8")))
            applied.append(sql_file.name)
    print(f"Views applied: {len(applied)}" + (f" ({', '.join(applied)})" if applied else ""))
    return applied


def heads() -> list[str]:
    return list(ScriptDirectory.from_config(Config(str(DB_DIR / "alembic.ini"))).get_heads())


def check(url: str) -> None:
    """Exactly one head, and no drift between the models and a migrated database."""
    found = heads()
    if len(found) != 1:
        raise SystemExit(f"Expected exactly one Alembic head, found {len(found)}: {found}")
    print(f"One head: {found[0]}")
    command.check(alembic_config(url))
