"""The raw lake: every API response saved exactly as fetched, append-only.

Local only for now (LAKE_URI unset or a path; default ./data at the repo root).
R2 (s3://…) arrives with the Phase 1 ingest.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from db.config import repo_root


def lake_root() -> Path:
    uri = os.environ.get("LAKE_URI", "").strip()
    if uri.startswith("s3://"):
        raise RuntimeError("An s3:// lake isn't supported yet; unset LAKE_URI to use ./data.")
    return Path(uri) if uri else repo_root() / "data"


def partition(source: str, endpoint: str, **keys: str) -> Path:
    path = lake_root() / "raw" / source / endpoint
    for name, value in keys.items():
        path /= f"{name}={value}"
    return path


def write_raw(folder: Path, fetched_at: datetime, payload: Any) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f"fetched_at={fetched_at.strftime('%Y-%m-%dT%H%M%SZ')}.json"
    if target.exists():
        raise FileExistsError(f"Raw files are never overwritten: {target}")
    target.write_text(json.dumps(payload), encoding="utf-8")
    return target


def latest_raw(folder: Path) -> Path | None:
    files = sorted(folder.glob("fetched_at=*.json"))
    return files[-1] if files else None
