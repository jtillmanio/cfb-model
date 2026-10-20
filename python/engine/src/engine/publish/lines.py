"""Staged `/lines` pulls to `sportsbooks` and append-only `line_snapshots` (TASK-020, D-115).

Staging keeps one row per (game, provider, pull). Which kind each becomes:
- a pull before the game's cutoff is a `snapshot` at its `fetched_at`;
- the first pull at or after the cutoff is the untimed `closing` row (CFBD's close);
- the first pull with a `spread_home_open` or `total_open` gives the untimed `opening` row;
- a row with no spread, total or moneyline is skipped.
The cutoff is `kickoff_at`, or the end of `game_date` in Eastern time when the kickoff is TBA.
An untimed row keeps the first value published: the key skips a later one (the lake keeps it).
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC, date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import Connection

from engine.publish.reference import insert_line_snapshots, upsert_sportsbooks

EASTERN = ZoneInfo("America/New_York")
PRICES = ("spread_home", "total", "ml_home", "ml_away")


def cutoff(kickoff_at: datetime | None, game_date: date) -> datetime:
    if kickoff_at is not None:
        return kickoff_at
    return datetime.combine(game_date + timedelta(days=1), time(), EASTERN).astimezone(UTC)


def map_lines(
    lines: Iterable[Mapping[str, Any]], games: Iterable[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    """Staged lines and games to line rows keyed by game_source_id and provider."""
    cutoffs = {g["source_id"]: cutoff(g["kickoff_at"], g["game_date"]) for g in games}
    rows: list[dict[str, Any]] = []
    untimed: set[tuple[str, str, str]] = set()

    def add(line: Mapping[str, Any], kind: str, at: datetime | None, prices: dict) -> None:
        if at is None:
            key = (line["game_source_id"], line["provider"], kind)
            if key in untimed:
                return
            untimed.add(key)
        rows.append(
            {
                "game_source_id": line["game_source_id"],
                "provider": line["provider"],
                "kind": kind,
                "captured_at": at,
                **prices,
            }
        )

    for line in sorted(lines, key=lambda r: r["fetched_at"]):
        if line["spread_home_open"] is not None or line["total_open"] is not None:
            opening = {"spread_home": line["spread_home_open"], "total": line["total_open"]}
            add(line, "opening", None, {**opening, "ml_home": None, "ml_away": None})
        prices = {p: line[p] for p in PRICES}
        if all(v is None for v in prices.values()):
            continue
        if line["fetched_at"] < cutoffs[line["game_source_id"]]:
            add(line, "snapshot", line["fetched_at"], prices)
        else:
            add(line, "closing", None, prices)
    return rows


def publish_lines(
    conn: Connection,
    source: str,
    rows: Sequence[Mapping[str, Any]],
    game_ids: Mapping[str, int],
    new: Counter[str] | None = None,
) -> int:
    """Upsert each provider as a sportsbook, then insert the rows. Returns snapshots inserted."""
    providers = sorted({r["provider"] for r in rows})
    book_ids = upsert_sportsbooks(
        conn, source, [{"source_id": p, "name": p} for p in providers], new
    )
    return insert_line_snapshots(
        conn,
        source,
        [
            {
                "game_id": game_ids[r["game_source_id"]],
                "book_id": book_ids[r["provider"]],
                "kind": r["kind"],
                "captured_at": r["captured_at"],
                **{p: r[p] for p in PRICES},
            }
            for r in rows
        ],
        new,
    )
