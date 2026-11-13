"""The NFL: only what a contest slate needs, the schedule, scores and lines from nflverse (D-039,
TASK-069). No model yet (Phase 8).

nflverse names a team by its code alone, so `TEAMS` gives each code the name the app shows: the
design's short name (`design/handoff/designs/contest-data.js`: "Buffalo", "NY Jets", "Kansas
City") and the nickname, as a CFB team's school and mascot. The codes no longer used (OAK, SD,
STL) stay so an older season still publishes with names.
"""

from __future__ import annotations

SPORT = "nfl"
SOURCE = "nflverse"

# nflverse code -> (school: the short name shown, mascot: the nickname)
TEAMS: dict[str, tuple[str, str]] = {
    "ARI": ("Arizona", "Cardinals"),
    "ATL": ("Atlanta", "Falcons"),
    "BAL": ("Baltimore", "Ravens"),
    "BUF": ("Buffalo", "Bills"),
    "CAR": ("Carolina", "Panthers"),
    "CHI": ("Chicago", "Bears"),
    "CIN": ("Cincinnati", "Bengals"),
    "CLE": ("Cleveland", "Browns"),
    "DAL": ("Dallas", "Cowboys"),
    "DEN": ("Denver", "Broncos"),
    "DET": ("Detroit", "Lions"),
    "GB": ("Green Bay", "Packers"),
    "HOU": ("Houston", "Texans"),
    "IND": ("Indianapolis", "Colts"),
    "JAX": ("Jacksonville", "Jaguars"),
    "KC": ("Kansas City", "Chiefs"),
    "LA": ("LA Rams", "Rams"),
    "LAC": ("LA Chargers", "Chargers"),
    "LV": ("Las Vegas", "Raiders"),
    "MIA": ("Miami", "Dolphins"),
    "MIN": ("Minnesota", "Vikings"),
    "NE": ("New England", "Patriots"),
    "NO": ("New Orleans", "Saints"),
    "NYG": ("NY Giants", "Giants"),
    "NYJ": ("NY Jets", "Jets"),
    "PHI": ("Philadelphia", "Eagles"),
    "PIT": ("Pittsburgh", "Steelers"),
    "SEA": ("Seattle", "Seahawks"),
    "SF": ("San Francisco", "49ers"),
    "TB": ("Tampa Bay", "Buccaneers"),
    "TEN": ("Tennessee", "Titans"),
    "WAS": ("Washington", "Commanders"),
    "OAK": ("Oakland", "Raiders"),
    "SD": ("San Diego", "Chargers"),
    "STL": ("St. Louis", "Rams"),
}

# nflverse `game_type` -> games.season_type; any other type (none in the file today) is dropped.
SEASON_TYPES: dict[str, str] = {
    "REG": "regular",
    "WC": "postseason",
    "DIV": "postseason",
    "CON": "postseason",
    "SB": "postseason",
}


def team_row(code: str) -> dict[str, str | None]:
    """A `teams` row for an nflverse code. An unknown code is its own name, so a new team still
    publishes (the publish prints it)."""
    school, mascot = TEAMS.get(code, (code, None))
    return {
        "source_id": code,
        "school": school,
        "mascot": mascot,
        "abbreviation": code,
        "color": None,
        "alt_color": None,
        "logo_url": None,
    }
