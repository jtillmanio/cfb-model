"""Writes week6_filler.json: the 40 Week 6 games behind "54 games" that the slate shows but the
design doesn't draw (TASK-055; docs/02-architecture.md › Seed data, "filler games with edges under
1.0").

Run from python/: `uv run python db/seeds/fixture/generate_filler.py`. The test DB only (D-089);
db/tests/test_filler_schema.py checks the file is exactly what `build()` returns.

- **Teams:** the 18 fixture teams that play no Week 6 game and whose schedules the design doesn't
  fix (not the top ten, not Ohio State's opponents, as generate_picks.py), and 62 more FBS teams.
  The new teams are rated entering weeks 1-6 (every FBS team is, 02 › Seed data › Ratings), always
  below Utah and tied with no team in any week, so the seeded ranks of the fixture's top ten
  don't move.
- **Games:** drawn with a fixed seed. Each kicks off Saturday at 3:30 PM ET or later, so at the
  slate's fixture time (Sat 2:15 PM ET) every one is still to play: no score, and no team's
  record or ATS line changes.
- **Lines and predictions:** an untimed open, the Sun 6:00 AM snapshot at the open and the Thu
  9:02 PM snapshot (the slate's "Updated" pull) up to a point away. v1.0's prediction is within
  0.9 points of the Thursday line, so the edge against the current line is under 1.0 and the game
  is never picked; `home_win_prob` is the normal win probability at v1.0's σ.
"""

from __future__ import annotations

import importlib.util
import json
import random
from pathlib import Path
from typing import Any

from engine.core.probability import NormalMargin, win_probability

HERE = Path(__file__).parent
SEED = 20261010
VERSION = "v1.0"
WEEK = 6
SUN = "2026-10-04T10:00:00Z"  # week 6's Sun 6:00 AM ET snapshot (generate_picks.py)
THU = "2026-10-09T01:02:00Z"  # "Updated Thu 9:02 PM ET"
GAME_DATE = "2026-10-10"
# Saturday 3:30, 7:00, 7:30 and 10:30 PM ET (UTC), all after the slate's 2:15 PM ET.
KICKOFFS = (
    "2026-10-10T19:30:00Z", "2026-10-10T23:00:00Z", "2026-10-10T23:30:00Z", "2026-10-11T02:30:00Z",
)  # fmt: skip
HOME_FIELD = 2.3  # sample-data.md › Conventions
MAX_GAP = 0.9  # the most a prediction is away from the current line

# Fixture teams generate_picks.py also keeps out of drawn games: their 2026 schedules are the
# design's.
TOP_TEN = {"osu", "tex", "ore", "ou", "uga", "miss", "nd", "psu", "lsu", "utah"}
OSU_OPPONENTS = {"akr", "ohio", "rutg", "minn", "uw"}

# source_id, school, abbreviation, colour, conference (2026 alignment, as teams.json).
NEW_TEAMS = [
    ("ala", "Alabama", "ALA", "#9E1B32", "SEC"),
    ("tenn", "Tennessee", "TENN", "#FF8200", "SEC"),
    ("fla", "Florida", "FLA", "#0021A5", "SEC"),
    ("tamu", "Texas A&M", "TAMU", "#500000", "SEC"),
    ("scar", "South Carolina", "SC", "#73000A", "SEC"),
    ("ark", "Arkansas", "ARK", "#9D2235", "SEC"),
    ("msst", "Mississippi State", "MSST", "#660000", "SEC"),
    ("van", "Vanderbilt", "VAN", "#866D4B", "SEC"),
    ("ill", "Illinois", "ILL", "#E84A27", "Big Ten"),
    ("ind", "Indiana", "IND", "#990000", "Big Ten"),
    ("md", "Maryland", "MD", "#E03A3E", "Big Ten"),
    ("msu", "Michigan State", "MSU", "#18453B", "Big Ten"),
    ("neb", "Nebraska", "NEB", "#E41C38", "Big Ten"),
    ("ucla", "UCLA", "UCLA", "#2D68C4", "Big Ten"),
    ("usc", "USC", "USC", "#990000", "Big Ten"),
    ("bc", "Boston College", "BC", "#98002E", "ACC"),
    ("cal", "California", "CAL", "#003262", "ACC"),
    ("fsu", "Florida State", "FSU", "#782F40", "ACC"),
    ("gt", "Georgia Tech", "GT", "#B3A369", "ACC"),
    ("unc", "North Carolina", "UNC", "#7BAFD4", "ACC"),
    ("pitt", "Pittsburgh", "PITT", "#003594", "ACC"),
    ("syr", "Syracuse", "SYR", "#F76900", "ACC"),
    ("uva", "Virginia", "UVA", "#232D4B", "ACC"),
    ("vt", "Virginia Tech", "VT", "#630031", "ACC"),
    ("ku", "Kansas", "KU", "#0051BA", "Big 12"),
    ("okst", "Oklahoma State", "OKST", "#FF7300", "Big 12"),
    ("wvu", "West Virginia", "WVU", "#002855", "Big 12"),
    ("orst", "Oregon State", "ORST", "#DC4405", "Pac-12"),
    ("sdsu", "San Diego State", "SDSU", "#A6192E", "Pac-12"),
    ("csu", "Colorado State", "CSU", "#1E4D2B", "Pac-12"),
    ("usu", "Utah State", "USU", "#0F2439", "Pac-12"),
    ("af", "Air Force", "AF", "#003087", "Mountain West"),
    ("haw", "Hawai'i", "HAW", "#024731", "Mountain West"),
    ("nev", "Nevada", "NEV", "#003366", "Mountain West"),
    ("unm", "New Mexico", "UNM", "#BA0C2F", "Mountain West"),
    ("sjsu", "San José State", "SJSU", "#0055A2", "Mountain West"),
    ("wyo", "Wyoming", "WYO", "#492F24", "Mountain West"),
    ("ecu", "East Carolina", "ECU", "#592A8A", "American"),
    ("fau", "Florida Atlantic", "FAU", "#003366", "American"),
    ("clt", "Charlotte", "CLT", "#046A38", "American"),
    ("unt", "North Texas", "UNT", "#00853E", "American"),
    ("rice", "Rice", "RICE", "#00205B", "American"),
    ("usf", "South Florida", "USF", "#006747", "American"),
    ("tem", "Temple", "TEM", "#9D2235", "American"),
    ("uab", "UAB", "UAB", "#1E6B52", "American"),
    ("utsa", "UTSA", "UTSA", "#0C2340", "American"),
    ("ball", "Ball State", "BALL", "#BA0C2F", "MAC"),
    ("bgsu", "Bowling Green", "BGSU", "#FE5000", "MAC"),
    ("buff", "Buffalo", "BUFF", "#005BBB", "MAC"),
    ("cmu", "Central Michigan", "CMU", "#6A0032", "MAC"),
    ("emu", "Eastern Michigan", "EMU", "#006633", "MAC"),
    ("kent", "Kent State", "KENT", "#003976", "MAC"),
    ("moh", "Miami (OH)", "MOH", "#C3142D", "MAC"),
    ("niu", "Northern Illinois", "NIU", "#BA0C2F", "MAC"),
    ("tol", "Toledo", "TOL", "#15397F", "MAC"),
    ("wmu", "Western Michigan", "WMU", "#6C4023", "MAC"),
    ("app", "Appalachian State", "APP", "#222222", "Sun Belt"),
    ("ccu", "Coastal Carolina", "CCU", "#006F71", "Sun Belt"),
    ("gaso", "Georgia Southern", "GASO", "#011E41", "Sun Belt"),
    ("jmu", "James Madison", "JMU", "#450084", "Sun Belt"),
    ("mrsh", "Marshall", "MRSH", "#00B140", "Sun Belt"),
    ("odu", "Old Dominion", "ODU", "#003057", "Sun Belt"),
]


def _load(name: str) -> dict[str, Any]:
    return json.loads((HERE / name).read_text(encoding="utf-8"))


def _dump_module() -> Any:
    """generate_picks.py's `dump`, so both generated files share one layout."""
    spec = importlib.util.spec_from_file_location("generate_picks", HERE / "generate_picks.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _half(x: float) -> float:
    """To the nearest half point, never 0 (a pick'em line would make the side ambiguous)."""
    line = round(x * 2) / 2
    return line if line != 0 else 0.5


def _ratings(
    rng: random.Random, weeks: list[int], seeded: dict[str, list[float]]
) -> dict[str, list[float]]:
    """Each new team's rating entering each week: a drawn level that drifts, below Utah's rating
    that week and equal to no other team's."""
    utah = seeded["utah"]
    taken = [{r[i] for r in seeded.values()} for i in range(len(weeks))]
    out: dict[str, list[float]] = {}
    for source_id, *_ in NEW_TEAMS:
        level = rng.uniform(-16.0, 10.0)
        by_week: list[float] = []
        for i in range(len(weeks)):
            level += rng.uniform(-0.8, 0.8)
            value = round(min(level, utah[i] - 1.0), 1)
            while value in taken[i]:
                value = round(value - 0.1, 1)
            taken[i].add(value)
            by_week.append(value)
        out[source_id] = by_week
    return out


def build() -> dict[str, Any]:
    rng = random.Random(SEED)
    teams = _load("teams.json")
    week6 = _load("week6.json")
    models = _load("models.json")
    picks = _load("picks.json")
    season = teams["season"]
    ratings = models["ratings"]
    assert ratings["version"] == VERSION and ratings["weeks"][-1] == WEEK
    dist = NormalMargin(models["predictions"]["margin_sd"])

    playing = {g[side] for g in week6["games"] for side in ("away", "home")}
    playing |= {g[side] for g in picks["games"] if g["week"] == WEEK for side in ("away", "home")}
    idle = sorted(
        t["source_id"]
        for t in teams["teams"]
        if t["division"] == "fbs" and t["source_id"] not in playing | TOP_TEN | OSU_OPPONENTS
    )
    new_ratings = _ratings(rng, ratings["weeks"], ratings["teams"])
    week6_rating = {t: r[-1] for t, r in {**ratings["teams"], **new_ratings}.items()}
    conference = {t["source_id"]: t["conference"] for t in teams["teams"]}
    conference |= {t[0]: t[4] for t in NEW_TEAMS}

    pool = idle + [t[0] for t in NEW_TEAMS]
    rng.shuffle(pool)
    games: list[dict[str, Any]] = []
    predictions: list[dict[str, Any]] = []
    for i in range(0, len(pool), 2):
        away, home = pool[i], pool[i + 1]
        fair = week6_rating[home] - week6_rating[away] + HOME_FIELD
        sun = _half(-fair + rng.uniform(-2.0, 2.0))
        thu = _half(sun + rng.choice((-1.0, -0.5, 0.0, 0.0, 0.5, 1.0)))
        pred_margin = round(-thu + rng.uniform(-MAX_GAP, MAX_GAP), 1)
        source_id = f"{season}-w{WEEK}-{away}-{home}"
        games.append({
            "source_id": source_id,
            "game_date": GAME_DATE,  # Eastern: the 10:30 PM kickoff is 02:30 UTC on Sunday
            "kickoff_at": KICKOFFS[i // 2 % len(KICKOFFS)],
            "neutral_site": False,
            "conference_game": conference[away] == conference[home] != "Ind",
            "venue": None,
            "away": away,
            "home": home,
            "away_points": None,
            "home_points": None,
            "status": "scheduled",
            "lines": [
                {"kind": "opening", "captured_at": None, "spread_home": sun},
                {"kind": "snapshot", "captured_at": SUN, "spread_home": sun},
                {"kind": "snapshot", "captured_at": THU, "spread_home": thu},
            ],
        })  # fmt: skip
        predictions.append({
            "game": source_id,
            "pred_margin": pred_margin,
            "home_win_prob": round(win_probability(pred_margin, dist), 2),
        })  # fmt: skip

    return {
        "_source": (
            "Written by generate_filler.py (TASK-055); never edit by hand. The 40 Week 6 games"
            " behind '54 games' the design doesn't draw, drawn with a fixed seed between the 18"
            " fixture teams with no Week 6 game whose schedules the design doesn't fix and 62 more"
            " FBS teams (rated entering weeks 1-6 below Utah, with no ties), all kicking off after"
            " the slate's fixture time, with v1.0 predictions within 0.9 points of the current"
            " line. Spreads are home-side (negative = home favored); times are UTC. Test DB only"
            " (D-089)."
        ),
        "season": season,
        "version": VERSION,
        "week": WEEK,
        "teams": [
            {"source_id": s, "school": n, "abbreviation": a, "color": c, "conference": conf,
             "division": "fbs"}
            for s, n, a, c, conf in NEW_TEAMS
        ],  # fmt: skip
        "ratings": [{"team": t, "by_week": r} for t, r in new_ratings.items()],
        "games": games,
        "predictions": predictions,
    }


if __name__ == "__main__":
    text = _dump_module().dump(build())
    (HERE / "week6_filler.json").write_text(text, encoding="utf-8", newline="\n")
