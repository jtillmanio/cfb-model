"""The locked holdout seasons (docs/04-model.md § 6, § 9.1): the final exam, opened only at
promotion. A backtest that scores one needs `--holdout` and a written reason, and every such run
leaves a record under `backtests/holdout/` in the lake, so the Lab can count how often the exam
has been opened. Records are only ever added (TASK-034 moves them to `model_runs`).
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from engine.ingest.lake import Lake

HOLDOUT_SEASONS = (2024, 2025)
PREFIX = "backtests/holdout"


class HoldoutRefusedError(ValueError):
    """A holdout season without the flag and a reason, or the flag without a holdout season."""


def guard(seasons: Sequence[int], flagged: bool, reason: str | None) -> bool:
    """Whether the run opens the holdout; refuses it unless flagged with a reason."""
    locked = sorted(set(seasons) & set(HOLDOUT_SEASONS))
    if not locked:
        if flagged:
            raise HoldoutRefusedError(
                "--holdout given, but no holdout season "
                f"({', '.join(map(str, HOLDOUT_SEASONS))}) is scored"
            )
        return False
    if not flagged or not (reason or "").strip():
        raise HoldoutRefusedError(
            f"{', '.join(map(str, locked))} is a holdout season, locked for promotion "
            '(04 § 9.1): pass --holdout --reason "<why now>" to open it'
        )
    return True


def record(
    lake: Lake, at: datetime, spec_hash: str, seasons: Sequence[int], reason: str, model: str
) -> str:
    """Add one holdout record and return its key."""
    stamp = at.astimezone(UTC)
    name = f"{PREFIX}/{stamp:%Y%m%dT%H%M%S%fZ}-{spec_hash[:12]}"
    taken = set(lake.list(PREFIX))
    key, n = f"{name}.json", 1
    while key in taken:  # two runs in one instant (a fixed test clock)
        n += 1
        key = f"{name}-{n}.json"
    body = {
        "at": stamp.isoformat(),
        "spec_hash": spec_hash,
        "seasons": list(seasons),
        "reason": reason.strip(),
        "model": model,
    }
    lake.write_new(key, json.dumps(body, indent=2).encode("utf-8"))
    return key


def records(lake: Lake) -> list[dict[str, Any]]:
    return [json.loads(lake.read(k)) for k in lake.walk(PREFIX) if k.endswith(".json")]


def count(lake: Lake) -> int:
    return len(records(lake))
