"""Database URLs and the guards around them.

Every database URL the Python side uses is resolved here.
`resolve_test_database_url` is the one function that decides whether a URL is safe
for tests and the fixture seed (.claude/rules/database.md): it never falls back.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from dotenv import dotenv_values, load_dotenv

# python/db/src/db/config.py -> repo root
_REPO_ROOT = Path(__file__).resolve().parents[4]

MigrationTarget = Literal["dev", "test"]


class UnsafeDatabaseError(RuntimeError):
    """A command was pointed at a database it must not touch."""


def load_env() -> None:
    """Load the repo-root `.env.local` if it exists. Variables already set win."""
    env_file = _REPO_ROOT / ".env.local"
    if env_file.is_file():
        load_dotenv(env_file, override=False)


def _env(env: Mapping[str, str] | None) -> Mapping[str, str]:
    return os.environ if env is None else env


def _identity(url: str) -> tuple[str, int, str]:
    """Host, port and database name; Neon's pooled and direct hosts compare equal."""
    parts = urlsplit(url)
    label, dot, rest = (parts.hostname or "").lower().partition(".")
    host = label.removesuffix("-pooler") + dot + rest
    return host, parts.port or 5432, parts.path.lstrip("/")


def resolve_test_database_url(env: Mapping[str, str] | None = None) -> str:
    """Return TEST_DATABASE_URL, or refuse if it's unset or names a dev database."""
    env = _env(env)
    url = env.get("TEST_DATABASE_URL", "").strip()
    if not url:
        raise UnsafeDatabaseError(
            "TEST_DATABASE_URL is not set. Tests and the fixture seed never fall back "
            "to another database."
        )
    for name in ("DATABASE_URL", "DATABASE_URL_UNPOOLED"):
        other = env.get(name, "").strip()
        if other and _identity(other) == _identity(url):
            raise UnsafeDatabaseError(f"TEST_DATABASE_URL names the same database as {name}.")
    return url


def app_database_url(env: Mapping[str, str] | None = None) -> str:
    """The URL the API reads: the guarded test DB when APP_ENV=test, else DATABASE_URL."""
    env = _env(env)
    if env.get("APP_ENV") == "test":
        return resolve_test_database_url(env)
    url = env.get("DATABASE_URL", "").strip()
    if not url:
        raise RuntimeError("DATABASE_URL is not set.")
    return url


def direct_url(target: MigrationTarget, env: Mapping[str, str] | None = None) -> str:
    """Direct (unpooled) URL for migrations and bulk publish: dev, or the guarded test DB."""
    env = _env(env)
    if target == "test":
        return resolve_test_database_url(env)
    url = env.get("DATABASE_URL_UNPOOLED", "").strip()
    if not url:
        raise RuntimeError("DATABASE_URL_UNPOOLED is not set.")
    return url


def _host(value: str) -> str:
    """A bare host or a URL's host, with Neon's "-pooler" suffix folded away."""
    return _identity(value if "://" in value else f"postgresql://{value}")[0]


def preview_migration_url(env: Mapping[str, str] | None = None) -> str | None:
    """The preview build migrates its own Neon branch (DATABASE_URL_UNPOOLED, set per preview
    by the Neon integration). None outside preview builds: production migrates only through
    the release workflow. Refuses unless it can prove the target isn't production."""
    env = _env(env)
    if env.get("VERCEL_ENV") != "preview":
        return None
    url = env.get("DATABASE_URL_UNPOOLED", "").strip()
    if not url:
        raise RuntimeError("DATABASE_URL_UNPOOLED is not set for this preview.")
    production = env.get("PRODUCTION_DATABASE_HOST", "").strip()
    if not production:
        raise UnsafeDatabaseError(
            "PRODUCTION_DATABASE_HOST is not set, so the preview build can't prove its "
            "database isn't production's. Refusing to migrate."
        )
    if _host(url) == _host(production):
        raise UnsafeDatabaseError("The preview database is production's. Refusing to migrate.")
    return url


# Production's direct URL: a repo secret for the release workflow, and the one line in .env.live.
LIVE_URL_VAR = "PRODUCTION_DATABASE_URL_UNPOOLED"


def live_url(env_file: Path | None, env: Mapping[str, str] | None = None) -> str:
    """Production's unpooled URL, from an explicit env file or the release workflow's environment.

    Nothing reads `.env.live` implicitly (`load_env` reads only `.env.local`): the caller names
    it with `--env-file`. A value in the file wins over the environment, since naming the file is
    the explicit act. Refuses Neon's pooled host: migrations need the direct one (D-016)."""
    values = dict(_env(env))
    if env_file is not None:
        if not env_file.is_file():
            raise UnsafeDatabaseError(f"{env_file} doesn't exist.")
        values.update({k: v for k, v in dotenv_values(env_file).items() if v is not None})
    url = values.get(LIVE_URL_VAR, "").strip()
    if not url:
        raise UnsafeDatabaseError(
            f"--target live needs {LIVE_URL_VAR}: pass --env-file .env.live, or set it in the "
            "environment (the release workflow does). .env.live is never read implicitly."
        )
    if (urlsplit(url).hostname or "").partition(".")[0].endswith("-pooler"):
        raise UnsafeDatabaseError(
            f"{LIVE_URL_VAR} is Neon's pooled host; migrations need the direct (unpooled) one."
        )
    return url


def refuse_if_live(action: str, env: Mapping[str, str] | None = None) -> None:
    """Destructive or fixture-loading commands refuse to run under LIVE=true."""
    if _env(env).get("LIVE", "").strip().lower() in {"1", "true", "yes"}:
        raise UnsafeDatabaseError(f"LIVE is set: refusing to {action}.")


def repo_root() -> Path:
    return _REPO_ROOT
