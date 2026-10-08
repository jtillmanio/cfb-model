"""The engine's one source of "now". FIXTURE_NOW is honored only when APP_ENV=test
(docs/02-architecture.md › Test-only sign-in and clock)."""

from __future__ import annotations

import os
from datetime import UTC, datetime


def now() -> datetime:
    fixed = os.environ.get("FIXTURE_NOW")
    if fixed and os.environ.get("APP_ENV") == "test":
        return datetime.fromisoformat(fixed).astimezone(UTC)
    return datetime.now(UTC)
