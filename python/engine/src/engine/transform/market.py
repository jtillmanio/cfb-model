"""Each game's closing line from the staged lake, by the rule the `game_market` view applies to
the published snapshots (D-120), so a backtest grades against the line the app shows (TASK-021;
notebook #1's benchmark, M3.4's baseline).

The line kinds come from `publish.lines.map_lines`, as published. A game's closing line is its
untimed `closing` rows (each book's first pull at or after the cutoff: CFBD's close), else its
last pull before the cutoff, and there is none until the cutoff has passed. The spread and the
total are chosen separately, each from the closing rows that quoted that price, else the last
pull before the cutoff that did, so a pull with only a total never blanks the spread (D-162,
TASK-064). Each is the `consensus` book's when it quoted that price, else the median across the
books (04 § 9.3).

The opening line, which a backtest grades opening-line picks and measures CLV on, comes from the
books that quoted both an opener and a close for the game: their opener (`spread_home_open`) and
their close (`spread_home_open_close`), each by the same consensus-else-median rule. CLV then
compares one set of books with itself; only some books quote openers (consensus never does), so
the main close would mix sources (TASK-031, D-132).
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from datetime import datetime
from statistics import median
from typing import Any

import pyarrow as pa

from engine.clock import now
from engine.publish.lines import cutoff, map_lines

SCHEMA = pa.schema(
    [
        ("game_source_id", pa.string()),
        ("spread_home", pa.float64()),
        ("spread_home_open", pa.float64()),  # NULL: no book quoted both an opener and a close
        ("spread_home_open_close", pa.float64()),  # those same books' close, for CLV
        ("total", pa.float64()),
        ("source", pa.string()),  # which rule gave the spread: consensus or median
        ("closing_from", pa.string()),  # cfbd_close or last_snapshot, as in game_market
    ]
)


def _price(rows: Sequence[dict[str, Any]], name: str) -> tuple[float | None, str | None]:
    consensus = [r[name] for r in rows if r["provider"] == "consensus" and r[name] is not None]
    if consensus:
        return min(consensus), "consensus"
    quoted = [r[name] for r in rows if r[name] is not None]
    return (median(quoted), "median") if quoted else (None, None)


def _closing_group(
    rows: Sequence[dict[str, Any]], at: datetime, name: str
) -> tuple[list[dict[str, Any]], str | None]:
    """The pull that closes price `name`: CFBD's untimed `closing` rows that quoted it, else the
    latest snapshot before the cutoff `at` that did. `([], None)` when no pull quoted it."""
    close = [r for r in rows if r["kind"] == "closing" and r[name] is not None]
    if close:
        return close, "cfbd_close"
    before = [
        r for r in rows if r["kind"] == "snapshot" and r["captured_at"] < at and r[name] is not None
    ]
    if not before:
        return [], None
    last = max(r["captured_at"] for r in before)
    return [r for r in before if r["captured_at"] == last], "last_snapshot"


def closing_lines(games: pa.Table, lines: pa.Table, at: datetime | None = None) -> pa.Table:
    """One row per game whose closing line exists at `at` (default now), from staged `games`
    (`source_id`, `kickoff_at`, `game_date`) and staged `lines`. A game has a row when it has a
    closing spread or a closing total; `spread_home`, `source` and `closing_from` are NULL when
    only the total was quoted."""
    at = at or now()
    game_rows = games.select(["source_id", "kickoff_at", "game_date"]).to_pylist()
    cutoffs = {g["source_id"]: cutoff(g["kickoff_at"], g["game_date"]) for g in game_rows}
    by_game: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in map_lines(lines.to_pylist(), game_rows):
        by_game[row["game_source_id"]].append(row)

    out: list[dict[str, Any]] = []
    for game, rows in sorted(by_game.items()):
        if at < cutoffs[game]:
            continue
        # The spread and the total each take their own closing pull (D-162): a pull that quoted
        # only one of them never blanks the other.
        group, closing_from = _closing_group(rows, cutoffs[game], "spread_home")
        total_group, _ = _closing_group(rows, cutoffs[game], "total")
        if not group and not total_group:
            continue
        spread, source = _price(group, "spread_home")
        total, _ = _price(total_group, "total")
        openers = [r for r in rows if r["kind"] == "opening" and r["spread_home"] is not None]
        opened = {r["provider"]: r for r in openers}
        both = [r for r in group if r["provider"] in opened and r["spread_home"] is not None]
        opening, _ = _price([opened[r["provider"]] for r in both], "spread_home")
        open_close, _ = _price(both, "spread_home")
        out.append(
            {
                "game_source_id": game,
                "spread_home": spread,
                "spread_home_open": opening,
                "spread_home_open_close": open_close,
                "total": total,
                "source": source,
                "closing_from": closing_from,
            }
        )
    return pa.Table.from_pylist(out, SCHEMA)
