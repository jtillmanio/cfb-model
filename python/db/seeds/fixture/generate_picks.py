"""Writes picks.json: v1.0's 2026 picks with the games, lines and predictions they need (TASK-040).

Run from python/: `uv run python db/seeds/fixture/generate_picks.py`. The test DB only (D-089);
db/tests/test_picks_schema.py checks the file is exactly what `build()` returns.

Weeks 5 and 6 are design/handoff/designs/picks-data.js row for row: the 15 week-5 rows (teams,
line picked at, close, score, tier) and the 9 This Week picks. Weeks 1-4 give only totals (its
`weeks` rows and sample-data.md § 7), so each pick there gets a hand-set result, tier and CLV that
add up to them exactly, and its teams, line, edge and score are drawn with a fixed seed (02 › Seed
data › Generated rows). Every game is FBS vs FBS (D-047); weeks 1-4 leave out the top ten and
Ohio State's § 6 opponents, whose records and schedules the design fixes.

A week's picks are made at its Sun 6:00 AM ET snapshot, 10 minutes after the week's v1.0 run
finishes, unless the design names another time. A line move during the week is its own snapshot,
and that pick is made at it. Edges are against the line picked at and unshrunk, as the design
shows them: `edge_pts = pred_margin + spread_home`, > 0 likes home. `model_prob` is the normal
cover probability with v1.0's σ and `expected_value` its return per unit risked at −110.
"""

from __future__ import annotations

import json
import random
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from engine.core.probability import (
    NormalMargin,
    cover_probability,
    expected_value,
    win_probability,
)
from engine.core.spec import ModelSpec, fixed

HERE = Path(__file__).parent
SEED = 20261006
VERSION = "v1.0"
PRICE = -110
SNAPSHOT_AFTER = timedelta(hours=6)  # Sun 6:00 AM ET, the week's run just finished
PICK_AFTER = timedelta(hours=6, minutes=10)  # Sun 6:10 AM ET
KICKOFF_SLOTS = ((16, 0), (19, 30), (23, 30))  # Saturday noon, 3:30 and 7:30 PM ET (UTC)

# Teams whose 2026 records and schedules the design fixes (sample-data.md § 4, § 6).
TOP_TEN = {"osu", "tex", "ore", "ou", "uga", "miss", "nd", "psu", "lsu", "utah"}
OSU_OPPONENTS = {"akr", "ohio", "rutg", "minn", "uw"}

# Weeks 1-4: each tier's results per week, from picks-data.js `weeks` (W-L-P per week) and
# § 7's tiers less week 5's rows: A 6-2, B 9-7-1, C 7-9.
PLAN = {
    1: {"A": "WW", "B": "WL", "C": "WL"},
    2: {"A": "L", "B": "WL", "C": "WL"},
    3: {"A": "WWWL", "B": "WWWWLL", "C": "WWLLL"},
    4: {"A": "W", "B": "WWWLLLP", "C": "WWWLLLL"},
}
# Each week's CLV per pick (shuffled across its picks), summing to the week's average × picks:
# 0.8 × 6 (5.0 rounds to it), 0.4 × 5, 1.2 × 15, 0.6 × 15.
CLV = {
    1: [1.5, 1.0, 1.0, 0.5, 0.5, 0.5],
    2: [1.0, 0.5, 0.5, 0.0, 0.0],
    3: [2.0, 1.5, 1.5, 1.5, 1.5] + [1.0] * 10,
    4: [1.5, 1.5, 1.5, 1.0, 1.0, 1.0, 1.0, 0.5, 0.5, 0.5, 0.0, 0.0, 0.0, -0.5, -0.5],
}

# Week 5 (picks-data.js `w5`): away, home, side picked, tier, spread_home picked at and at the
# close, away and home points, result.
WEEK5 = [
    ("uga", "aub", "away", "A", 3.5, 5.0, 31, 17, "W"),
    ("lou", "nd", "home", "A", -7.0, -8.0, 20, 24, "L"),
    ("utah", "ariz", "away", "B", -1.0, 0.0, 27, 20, "W"),
    ("miz", "lsu", "home", "B", -2.5, -4.0, 24, 34, "W"),
    ("tcu", "bay", "away", "B", -6.5, -5.0, 24, 38, "L"),
    ("minn", "mich", "away", "B", -10.0, -9.0, 20, 23, "W"),
    ("asu", "ksu", "home", "B", -2.0, -3.0, 30, 27, "L"),
    ("ncst", "clem", "away", "C", -4.0, -3.0, 27, 28, "W"),
    ("wake", "mia", "away", "C", -13.0, -12.0, 20, 31, "W"),
    ("cin", "ucf", "home", "C", -3.0, -3.0, 26, 24, "L"),
    ("tlsa", "army", "home", "C", -7.0, -8.5, 13, 35, "W"),
    ("wsu", "fres", "away", "C", -3.5, -2.5, 21, 33, "L"),
    ("duke", "smu", "home", "C", -10.0, -11.0, 24, 45, "W"),
    ("ttu", "hou", "away", "C", -2.5, -1.5, 17, 28, "L"),
    ("navy", "mem", "away", "C", -6.0, -4.5, 27, 30, "W"),
]

SUN = "2026-10-04T10:00:00Z"  # week 6's Sun 6:00 AM ET snapshot
SUN_PICK = "2026-10-04T10:10:00Z"
THU = "2026-10-09T01:02:00Z"  # "Updated Thu 9:02 PM ET"

# The three week-6 games of This Week's picks the slate doesn't show. pred_margin is the edge at
# the line picked at less that line (picks-data.js `edgeAt`, `at`); the close or current line is
# its `now`. Tulane @ Memphis was played Thursday night.
WEEK6_GAMES = [
    {
        "source_id": "2026-w6-tuln-mem", "away": "tuln", "home": "mem",
        "game_date": "2026-10-08", "kickoff_at": "2026-10-08T23:30:00Z",
        "away_points": 27, "home_points": 24, "status": "final", "pred_margin": 0.7,
        "lines": [("opening", None, -4.0), ("snapshot", SUN, -4.0), ("closing", None, -3.5)],
    },
    {
        "source_id": "2026-w6-isu-cin", "away": "isu", "home": "cin",
        "game_date": "2026-10-10", "kickoff_at": "2026-10-10T23:00:00Z",
        "away_points": None, "home_points": None, "status": "scheduled", "pred_margin": -7.1,
        "lines": [("opening", None, 3.0), ("snapshot", SUN, 3.0), ("snapshot", THU, 3.5)],
    },
    {
        "source_id": "2026-w6-asu-bay", "away": "asu", "home": "bay",
        "game_date": "2026-10-10", "kickoff_at": "2026-10-10T20:00:00Z",
        "away_points": None, "home_points": None, "status": "scheduled", "pred_margin": -0.4,
        "lines": [("opening", None, -3.0), ("snapshot", SUN, -3.0), ("snapshot", THU, -2.5)],
    },
]  # fmt: skip

# This Week's 9 picks (picks-data.js `current`): the game, the snapshot picked at, when it was
# made, and the design's tier. Ohio State and Notre Dame are at Thursday's lines (−27.5, +17),
# where their tiers hold; the design's Sun 6:10 AM is at −28 and +16.5 (the decision log).
WEEK6_PICKS = [
    ("2026-w6-tex-ou", "2026-10-05T13:40:00Z", "2026-10-05T13:40:00Z", "A"),
    ("2026-w6-miss-lsu", SUN, SUN_PICK, "B"),
    ("2026-w6-pur-osu", THU, THU, "B"),
    ("2026-w6-isu-cin", SUN, SUN_PICK, "B"),
    ("2026-w6-colo-byu", "2026-10-07T23:04:00Z", "2026-10-07T23:04:00Z", "C"),
    ("2026-w6-nd-stan", THU, THU, "C"),
    ("2026-w6-asu-bay", SUN, SUN_PICK, "C"),
    ("2026-w6-tuln-mem", SUN, SUN_PICK, "C"),
    ("2026-w6-iowa-wis", "2026-10-06T15:20:00Z", "2026-10-06T15:20:00Z", "C"),
]


def _load(name: str) -> dict[str, Any]:
    return json.loads((HERE / name).read_text(encoding="utf-8"))


def _iso(at: datetime) -> str:
    return at.strftime("%Y-%m-%dT%H:%M:%SZ")


class _Fixture:
    def __init__(self) -> None:
        teams = _load("teams.json")
        week6 = _load("week6.json")
        models = _load("models.json")
        self.season: int = teams["season"]
        self.conference = {t["source_id"]: t["conference"] for t in teams["teams"]}
        self.pool = sorted(
            t["source_id"]
            for t in teams["teams"]
            if t["division"] == "fbs" and t["source_id"] not in TOP_TEN | OSU_OPPONENTS
        )
        self.starts = {
            w["week"]: datetime.fromisoformat(w["start"])
            for w in week6["season"]["weeks"]
            if w["season_type"] == "regular"
        }
        self.slate = {g["source_id"]: g for g in week6["games"]}
        preds = models["predictions"]
        assert preds["version"] == VERSION
        self.dist = NormalMargin(preds["margin_sd"])
        self.slate_preds = {p["game"]: p["pred_margin"] for p in preds["games"]}
        spec = next(v["spec"] for v in models["versions"] if v["version"] == VERSION)
        tiers = ModelSpec.model_validate(spec).picks.tiers
        self.cutoffs = [(t, fixed(getattr(tiers, t), f"picks.tiers.{t}")) for t in "ABC"]

    def tier(self, edge: float) -> str | None:
        return next((t for t, at in self.cutoffs if abs(edge) >= at), None)

    def edge_range(self, tier: str) -> tuple[float, float]:
        """Where a drawn edge of `tier` falls: from its cutoff to just under the next one up."""
        at = dict(self.cutoffs)
        above = {"A": at["A"] + 2.5, "B": at["A"] - 0.1, "C": at["B"] - 0.1}
        return at[tier], above[tier]

    def conference_game(self, away: str, home: str) -> bool:
        return self.conference[away] == self.conference[home] != "Ind"

    def saturday(self, week: int, slot: tuple[int, int]) -> datetime:
        return (self.starts[week] + timedelta(days=6)).replace(hour=slot[0], minute=slot[1])


def _game(
    fx: _Fixture,
    week: int,
    away: str,
    home: str,
    kickoff: datetime,
    points: tuple[int | None, int | None],
    lines: list[tuple[str, str | None, float]],
    status: str = "final",
) -> dict[str, Any]:
    return {
        "source_id": f"{fx.season}-w{week}-{away}-{home}",
        "week": week,
        "game_date": kickoff.date().isoformat(),
        "kickoff_at": _iso(kickoff),
        "neutral_site": False,
        "conference_game": fx.conference_game(away, home),
        "away": away,
        "home": home,
        "away_points": points[0],
        "home_points": points[1],
        "status": status,
        "lines": [{"kind": k, "captured_at": at, "spread_home": s} for k, at, s in lines],
    }


def _prediction(fx: _Fixture, game: str, week: int, pred_margin: float) -> dict[str, Any]:
    return {
        "game": game,
        "week": week,
        "pred_margin": pred_margin,
        "home_win_prob": round(win_probability(pred_margin, fx.dist), 2),
    }


def _pick(
    fx: _Fixture,
    game: str,
    week: int,
    pred_margin: float,
    spread: float,
    snapshot_at: str,
    created_at: str,
) -> dict[str, Any]:
    cover = cover_probability(pred_margin, spread, fx.dist)
    prob = round(cover.prob, 4)
    edge = round(cover.edge, 1)
    return {
        "game": game,
        "week": week,
        "snapshot": {"kind": "snapshot", "captured_at": snapshot_at},
        "market": "spread",
        "side": cover.side,
        "line": spread,
        "price": PRICE,
        "model_prob": prob,
        "edge_pts": edge,
        "expected_value": round(expected_value(prob, PRICE), 4),
        "tier": fx.tier(edge),
        "stake_units": 1.0,
        "created_at": created_at,
    }


def _weekly_lines(fx: _Fixture, week: int, at: float, close: float) -> list[Any]:
    """CFBD-style untimed open and close, and the Sun 6:00 AM snapshot the pick was made at."""
    return [
        ("opening", None, at),
        ("snapshot", _iso(fx.starts[week] + SNAPSHOT_AFTER), at),
        ("closing", None, close),
    ]


def _drawn_week(
    fx: _Fixture, rng: random.Random, week: int, seen: set[frozenset[str]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    plan = [(tier, result) for tier, results in PLAN[week].items() for result in results]
    clvs = CLV[week][:]
    rng.shuffle(clvs)
    teams = fx.pool[:]
    rng.shuffle(teams)
    games, preds, picks = [], [], []
    for (tier, result), clv in zip(plan, clvs, strict=True):
        while True:
            away, home = teams.pop(), teams.pop()
            if frozenset((away, home)) not in seen:
                break
            teams[:0] = [away, home]  # a rematch: put them back at the far end
        seen.add(frozenset((away, home)))

        side = rng.choice(("home", "away"))
        whole = result == "P" or rng.random() < 0.3
        size = float(rng.randint(1, 21)) if whole else rng.randint(1, 21) - 0.5
        spread = size * rng.choice((-1, 1))
        low, high = fx.edge_range(tier)
        edge = round(rng.uniform(low, high), 1)
        pred_margin = round((edge if side == "home" else -edge) - spread, 1)
        close = spread - clv if side == "home" else spread + clv

        # The final margin against the line picked at: the picked side covers by `by` on a win.
        sign = (1 if side == "home" else -1) * {"W": 1, "L": -1, "P": 0}[result]
        while True:
            by = rng.randint(1, 17) if whole else rng.randint(1, 17) - 0.5
            margin = int(-spread + sign * by)
            if margin != 0:
                break
        loser = rng.randint(3, 31)
        points = (loser, loser + margin) if margin > 0 else (loser - margin, loser)

        game = _game(
            fx, week, away, home, fx.saturday(week, rng.choice(KICKOFF_SLOTS)), points,
            _weekly_lines(fx, week, spread, close),
        )  # fmt: skip
        games.append(game)
        preds.append(_prediction(fx, game["source_id"], week, pred_margin))
        pick = _pick(
            fx, game["source_id"], week, pred_margin, spread,
            _iso(fx.starts[week] + SNAPSHOT_AFTER), _iso(fx.starts[week] + PICK_AFTER),
        )  # fmt: skip
        assert (pick["side"], pick["tier"]) == (side, tier), pick
        picks.append(pick)
    return games, preds, picks


def _week5(
    fx: _Fixture, rng: random.Random, seen: set[frozenset[str]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    games, preds, picks = [], [], []
    for away, home, side, tier, at, close, away_pts, home_pts, result in WEEK5:
        seen.add(frozenset((away, home)))
        low, high = fx.edge_range(tier)
        edge = round(rng.uniform(low, high), 1)
        pred_margin = round((edge if side == "home" else -edge) - at, 1)
        game = _game(
            fx, 5, away, home, fx.saturday(5, rng.choice(KICKOFF_SLOTS)), (away_pts, home_pts),
            _weekly_lines(fx, 5, at, close),
        )  # fmt: skip
        games.append(game)
        preds.append(_prediction(fx, game["source_id"], 5, pred_margin))
        pick = _pick(
            fx, game["source_id"], 5, pred_margin, at,
            _iso(fx.starts[5] + SNAPSHOT_AFTER), _iso(fx.starts[5] + PICK_AFTER),
        )  # fmt: skip
        assert (pick["side"], pick["tier"]) == (side, tier), pick
        assert _grade(pick, game)[0] == result, pick
        picks.append(pick)
    return games, preds, picks


def _week6(fx: _Fixture) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[Any]]:
    games, preds = [], []
    margins = dict(fx.slate_preds)
    lines: dict[tuple[str, str | None], float] = {
        (g["source_id"], line["captured_at"]): line["spread_home"]
        for g in fx.slate.values()
        for line in g["lines"]
        if line["kind"] == "snapshot"
    }
    for g in WEEK6_GAMES:
        games.append(
            {
                "source_id": g["source_id"],
                "week": 6,
                "game_date": g["game_date"],
                "kickoff_at": g["kickoff_at"],
                "neutral_site": False,
                "conference_game": fx.conference_game(g["away"], g["home"]),
                "away": g["away"],
                "home": g["home"],
                "away_points": g["away_points"],
                "home_points": g["home_points"],
                "status": g["status"],
                "lines": [
                    {"kind": k, "captured_at": at, "spread_home": s} for k, at, s in g["lines"]
                ],
            }
        )
        preds.append(_prediction(fx, g["source_id"], 6, g["pred_margin"]))
        margins[g["source_id"]] = g["pred_margin"]
        lines.update({(g["source_id"], at): s for k, at, s in g["lines"] if k == "snapshot"})

    picks = []
    for game, snapshot_at, created_at, tier in WEEK6_PICKS:
        pick = _pick(
            fx, game, 6, margins[game], lines[(game, snapshot_at)], snapshot_at, created_at
        )
        assert pick["tier"] == tier, pick
        picks.append(pick)
    return games, preds, picks


def _grade(pick: dict[str, Any], game: dict[str, Any]) -> tuple[str, int, float]:
    """(result, units in tenths, CLV against the close), as test_picks_schema grades them."""
    margin = game["home_points"] - game["away_points"]
    home_cover = margin + pick["line"]
    cover = home_cover if pick["side"] == "home" else -home_cover
    result = "P" if cover == 0 else "W" if cover > 0 else "L"
    close = next(x["spread_home"] for x in game["lines"] if x["kind"] == "closing")
    moved = pick["line"] - close
    return result, {"W": 10, "L": -11, "P": 0}[result], moved if pick["side"] == "home" else -moved


def _check_totals(picks: list[dict[str, Any]], games: dict[str, dict[str, Any]]) -> None:
    """The § 7 totals the AC cites: 31-24-1, +4.6u, the tiers, cumulative units, CLV +0.9."""
    graded = [(p, *_grade(p, games[p["game"]])) for p in picks if p["week"] <= 5]
    assert len(graded) == 56
    assert Counter(r for _, r, _, _ in graded) == {"W": 31, "L": 24, "P": 1}
    by_tier = {t: Counter(r for p, r, _, _ in graded if p["tier"] == t) for t in "ABC"}
    assert by_tier == {
        "A": {"W": 7, "L": 3},
        "B": {"W": 12, "L": 9, "P": 1},
        "C": {"W": 12, "L": 12},
    }
    running, cumulative = 0, []
    for week in range(1, 6):
        running += sum(u for p, _, u, _ in graded if p["week"] == week)
        cumulative.append(running)
    assert cumulative == [18, 5, 29, 22, 46], cumulative
    assert round(sum(c for _, _, _, c in graded) / len(graded), 1) == 0.9


def build() -> dict[str, Any]:
    fx = _Fixture()
    rng = random.Random(SEED)
    seen = {frozenset((g["away"], g["home"])) for g in WEEK6_GAMES}
    weeks = {5: _week5(fx, rng, seen)}  # the design's rows first, so no drawn game repeats one
    for week in sorted(PLAN):
        weeks[week] = _drawn_week(fx, rng, week, seen)
    weeks[6] = _week6(fx)
    games = [g for week in sorted(weeks) for g in weeks[week][0]]
    preds = [p for week in sorted(weeks) for p in weeks[week][1]]
    picks = [k for week in sorted(weeks) for k in weeks[week][2]]
    _check_totals(picks, {g["source_id"]: g for g in games})
    return {
        "_source": (
            "Written by generate_picks.py (TASK-040); never edit by hand. v1.0's 2026 picks:"
            " weeks 1-4 drawn with a fixed seed to the totals of design/sample-data.md § 7 and"
            " design/handoff/designs/picks-data.js `weeks`, week 5 and week 6 row for row from"
            " picks-data.js. Spreads are home-side (negative = home favored); times are UTC."
            " Test DB only (D-089)."
        ),
        "season": fx.season,
        "version": VERSION,
        "margin_sd": fx.dist.sd,
        "games": games,
        "predictions": preds,
        "picks": picks,
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
    (HERE / "picks.json").write_text(dump(build()), encoding="utf-8", newline="\n")
