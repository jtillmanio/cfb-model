"""Writes contest_history.json: the Splash work league's weeks 1-5 contest lines and entries
(TASK-067).

Run from python/: `uv run python db/seeds/fixture/generate_contest.py`. The test DB only (D-089);
db/tests/test_contest_schema.py checks the file is exactly what `build()` returns.

design/handoff/designs/contest-data.js gives only the weekly totals: you went W1 3-1, W2 2-2,
W3 3-1, W4 1-3, W5 3-1 (12-8). Each week's slate is 5 final FBS games drawn with a fixed seed
from picks.json's games of that week, so every one has a v1.0 prediction (TASK-068 grades the
model's top 4 on them). A contest line is the game's closing line moved to the nearest half point
when it is whole (up or down by the seed), so no entry pushes. The lines are captured the
Thursday before the week's Saturday at 9:10 PM ET, as week 6's paste was, and 4 entries follow
from 9:14 PM, two minutes apart, each on the side its hand-set result needs against the final
score. week 6's lines, entries and the standing are hand-written in contest.json.
"""

from __future__ import annotations

import json
import random
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

HERE = Path(__file__).parent
SEED = 20261008
SLATE = 5
# Your results each week, in entry order (contest-data.js `results.weeks`).
RESULTS = {1: "WWWL", 2: "WWLL", 3: "WWWL", 4: "WLLL", 5: "WWWL"}
EDT = timedelta(hours=4)  # September and October 2026 are EDT, UTC−4
CAPTURED = timedelta(hours=21, minutes=10)  # Thu 9:10 PM ET
FIRST_ENTRY = timedelta(minutes=4)
BETWEEN_ENTRIES = timedelta(minutes=2)


def _iso(at: datetime) -> str:
    return at.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _closing(game: dict[str, Any]) -> float:
    return next(line["spread_home"] for line in game["lines"] if line["kind"] == "closing")


def build() -> dict[str, Any]:
    picks = json.loads((HERE / "picks.json").read_text(encoding="utf-8"))
    rng = random.Random(SEED)
    lines: list[dict[str, Any]] = []
    entries: list[dict[str, Any]] = []
    for week, results in RESULTS.items():
        games = sorted(
            (g for g in picks["games"] if g["week"] == week and g["status"] == "final"),
            key=lambda g: g["source_id"],
        )
        slate = sorted(rng.sample(games, SLATE), key=lambda g: (g["kickoff_at"], g["source_id"]))
        first_kickoff = datetime.fromisoformat(slate[0]["kickoff_at"])
        thursday = datetime.combine(
            first_kickoff.date() - timedelta(days=2), datetime.min.time(), UTC
        )
        captured_at = thursday + CAPTURED + EDT
        assert captured_at < first_kickoff, week

        spreads = {}
        for g in slate:
            close = _closing(g)
            spread = close + rng.choice((-0.5, 0.5)) if close % 1 == 0 else close
            spreads[g["source_id"]] = spread
            lines.append(
                {
                    "period": week,
                    "game": g["source_id"],
                    "spread_home": spread,
                    "captured_at": _iso(captured_at),
                }
            )

        chosen = rng.sample(slate, len(results))
        for i, (g, result) in enumerate(zip(chosen, results, strict=True)):
            margin = g["home_points"] - g["away_points"]
            home_covers = margin + spreads[g["source_id"]] > 0
            side = "home" if home_covers == (result == "W") else "away"
            entries.append(
                {
                    "period": week,
                    "game": g["source_id"],
                    "side": side,
                    "created_at": _iso(captured_at + FIRST_ENTRY + i * BETWEEN_ENTRIES),
                }
            )
    return {
        "_source": (
            "Written by generate_contest.py (TASK-067): the Splash work league's weeks 1-5"
            " contest lines and your entries, graded W1 3-1, W2 2-2, W3 3-1, W4 1-3, W5 3-1"
            " (12-8) per contest-data.js. Games are picks.json's. Test DB only (D-089)."
        ),
        "lines": lines,
        "entries": entries,
    }


def dump(data: dict[str, Any]) -> str:
    """One list element per line, so a regenerated file diffs by row."""

    def text(value: Any) -> str:
        return json.dumps(value, ensure_ascii=False)

    out = ["{"]
    for i, (key, value) in enumerate(data.items()):
        end = "," if i < len(data) - 1 else ""
        if isinstance(value, list):
            out.append(f"  {text(key)}: [")
            last = len(value) - 1
            out += [f"    {text(x)}{',' if j < last else ''}" for j, x in enumerate(value)]
            out.append(f"  ]{end}")
        else:
            out.append(f"  {text(key)}: {text(value)}{end}")
    return "\n".join([*out, "}"]) + "\n"


if __name__ == "__main__":
    (HERE / "contest_history.json").write_text(dump(build()), encoding="utf-8", newline="\n")
