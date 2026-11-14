"""Writes contest_history.json: the Splash work league's weeks 1-5 contest lines, your entries
and the model's contest picks, with the two week-2 games they need (TASK-067, TASK-068).

Run from python/: `uv run python db/seeds/fixture/generate_contest.py`. The test DB only (D-089);
db/tests/test_contest_schema.py checks the file is exactly what `build()` returns.

design/handoff/designs/contest-data.js gives only the weekly totals: you went W1 3-1, W2 2-2,
W3 3-1, W4 1-3, W5 3-1 (12-8), and the model's top 4 W1 2-2, W2 3-1, W3 2-2, W4 2-2, W5 2-2
(11-9). Each week's slate is 5 final FBS games drawn with a fixed seed from picks.json's games of
that week, plus EXTRA's, so every one has a v1.0 prediction. A contest line is the game's closing
line moved to the nearest half point when it is whole (up or down by the seed), so nothing
pushes. A draw is kept only when the model's top 4 grades to its week's result with no tie at the
4th/5th cut; week 1's first draw does, so its slate is TASK-067's.

The lines are captured the Thursday before the week's Saturday at 9:10 PM ET, as week 6's paste
was. The model picks every slate game a minute later (D-170: CFB only), at the side it likes
against the contest line: the normal cover probability with v1.0's σ and the edge unshrunk, as
picks.json's (D-140), `expected_value` per unit at even money (a contest has no vig), no tier.
Your 4 entries follow from 9:14 PM, two minutes apart, each on the side its hand-set result needs
against the final score. Week 6's lines, entries and the standing are hand-written in
contest.json.

EXTRA: picks.json's week 2 has 5 final games, and the model's side covers 2 of them at any
contest line near the close, so its W2 3-1 needs a third win, and a fifth game it likes less than
Arizona State at Wisconsin (58.6%) so that win makes the top 4. Wake Forest at Clemson is the
win (Clemson −7.5, won by 14, the model Clemson by 12.4: 63.9%), Navy at SMU the weaker loss
(SMU −10.5, won by 6, the model SMU by 11.6: 53.2%). Both teams of each are idle in week 2 and
outside the design's top ten, and the games carry the same opening, Sun 6:00 AM and closing
lines as picks.json's.
"""

from __future__ import annotations

import json
import random
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from engine.core.probability import NormalMargin, cover_probability, expected_value, win_probability

HERE = Path(__file__).parent
SEED = 20261008
SLATE = 5
TOP_N = 4  # the Splash preset's picks_per_period
# Your results each week, in entry order (contest-data.js `results.weeks`).
RESULTS = {1: "WWWL", 2: "WWLL", 3: "WWWL", 4: "WLLL", 5: "WWWL"}
# The model's top-4 wins each week (contest-data.js `results.weeks`, `m`).
MODEL_WINS = {1: 2, 2: 3, 3: 2, 4: 2, 5: 2}
EDT = timedelta(hours=4)  # September and October 2026 are EDT, UTC−4
CAPTURED = timedelta(hours=21, minutes=10)  # Thu 9:10 PM ET
MODEL_PICK = timedelta(minutes=1)
FIRST_ENTRY = timedelta(minutes=4)
BETWEEN_ENTRIES = timedelta(minutes=2)
EVEN_MONEY = 100

# (away, home, kickoff UTC, (away, home) points, opening, Sun 6:00 AM, closing, pred_margin)
EXTRA = [
    ("wake", "clem", "2026-09-12T19:30:00Z", (20, 34), -6.5, -6.5, -7.5, 12.4),
    ("navy", "smu", "2026-09-12T23:30:00Z", (21, 27), -10.0, -10.5, -10.5, 11.6),
]
EXTRA_WEEK = 2
SUNDAY_6AM = "2026-09-06T10:00:00Z"  # week 2's Sun 6:00 AM ET snapshot, as picks.json's


def _iso(at: datetime) -> str:
    return at.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _closing(game: dict[str, Any]) -> float:
    return next(line["spread_home"] for line in game["lines"] if line["kind"] == "closing")


def _extra(
    conference: dict[str, str], dist: NormalMargin
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """EXTRA's games, in picks.json's shape, and their v1.0 predictions."""
    games, predictions = [], []
    for away, home, kickoff, (away_pts, home_pts), opening, sunday, closing, pred in EXTRA:
        source_id = f"2026-w{EXTRA_WEEK}-{away}-{home}"
        games.append(
            {
                "source_id": source_id,
                "week": EXTRA_WEEK,
                "game_date": kickoff[:10],
                "kickoff_at": kickoff,
                "neutral_site": False,
                "conference_game": conference[away] == conference[home] != "Ind",
                "away": away,
                "home": home,
                "away_points": away_pts,
                "home_points": home_pts,
                "status": "final",
                "lines": [
                    {"kind": "opening", "captured_at": None, "spread_home": opening},
                    {"kind": "snapshot", "captured_at": SUNDAY_6AM, "spread_home": sunday},
                    {"kind": "closing", "captured_at": None, "spread_home": closing},
                ],
            }
        )
        predictions.append(
            {
                "game": source_id,
                "week": EXTRA_WEEK,
                "pred_margin": pred,
                "home_win_prob": round(win_probability(pred, dist), 2),
            }
        )
    return games, predictions


def _model_pick(pred_margin: float, spread: float, dist: NormalMargin) -> dict[str, Any]:
    cover = cover_probability(pred_margin, spread, dist)
    prob = round(cover.prob, 4)
    return {
        "side": cover.side,
        "model_prob": prob,
        "edge_pts": round(cover.edge, 1),
        "expected_value": round(expected_value(prob, EVEN_MONEY), 4),
    }


def _covers(game: dict[str, Any], spread: float, side: str) -> bool:
    home_covers = game["home_points"] - game["away_points"] + spread > 0
    return home_covers == (side == "home")


def build() -> dict[str, Any]:
    picks = json.loads((HERE / "picks.json").read_text(encoding="utf-8"))
    teams = json.loads((HERE / "teams.json").read_text(encoding="utf-8"))
    dist = NormalMargin(picks["margin_sd"])
    conference = {t["source_id"]: t["conference"] for t in teams["teams"]}
    extra_games, extra_predictions = _extra(conference, dist)
    pred_margin = {p["game"]: p["pred_margin"] for p in picks["predictions"] + extra_predictions}

    rng = random.Random(SEED)
    lines: list[dict[str, Any]] = []
    model_picks: list[dict[str, Any]] = []
    entries: list[dict[str, Any]] = []
    for week, results in RESULTS.items():
        games = sorted(
            (
                g
                for g in picks["games"] + extra_games
                if g["week"] == week and g["status"] == "final"
            ),
            key=lambda g: g["source_id"],
        )
        while True:
            slate = sorted(
                rng.sample(games, SLATE), key=lambda g: (g["kickoff_at"], g["source_id"])
            )
            spreads = {}
            for g in slate:
                close = _closing(g)
                spreads[g["source_id"]] = (
                    close + rng.choice((-0.5, 0.5)) if close % 1 == 0 else close
                )
            model = {
                sid: _model_pick(pred_margin[sid], spread, dist) for sid, spread in spreads.items()
            }
            ranked = sorted(slate, key=lambda g: -model[g["source_id"]]["model_prob"])
            probs = [model[g["source_id"]]["model_prob"] for g in ranked]
            wins = sum(
                _covers(g, spreads[g["source_id"]], model[g["source_id"]]["side"])
                for g in ranked[:TOP_N]
            )
            if probs[TOP_N - 1] != probs[TOP_N] and wins == MODEL_WINS[week]:
                break

        first_kickoff = datetime.fromisoformat(slate[0]["kickoff_at"])
        thursday = datetime.combine(
            first_kickoff.date() - timedelta(days=2), datetime.min.time(), UTC
        )
        captured_at = thursday + CAPTURED + EDT
        assert captured_at < first_kickoff, week
        for g in slate:
            lines.append(
                {
                    "period": week,
                    "game": g["source_id"],
                    "spread_home": spreads[g["source_id"]],
                    "captured_at": _iso(captured_at),
                }
            )
            model_picks.append(
                {
                    "period": week,
                    "game": g["source_id"],
                    **model[g["source_id"]],
                    "created_at": _iso(captured_at + MODEL_PICK),
                }
            )

        chosen = rng.sample(slate, len(results))
        for i, (g, result) in enumerate(zip(chosen, results, strict=True)):
            home_covers = _covers(g, spreads[g["source_id"]], "home")
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
            "Written by generate_contest.py (TASK-067, TASK-068): the Splash work league's"
            " weeks 1-5 contest lines, your entries graded W1 3-1, W2 2-2, W3 3-1, W4 1-3, W5 3-1"
            " (12-8) and the model's contest picks, its top 4 graded W1 2-2, W2 3-1, W3 2-2,"
            " W4 2-2, W5 2-2 (11-9), per contest-data.js. Games are picks.json's and the two"
            " week-2 games here, with their v1.0 predictions. Test DB only (D-089)."
        ),
        "games": extra_games,
        "predictions": extra_predictions,
        "lines": lines,
        "model_picks": model_picks,
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
