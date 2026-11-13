"""Staged nflverse rows to Postgres under `sport_id 'nfl'`, source `nflverse` (TASK-069, D-039).

Teams, venues and games are upserted by `(source, source_id)` (nflverse's team code, `stadium_id`
and `game_id`), so publishing again inserts nothing and changes no ID; lines are inserted
append-only through the CFBD path's `map_lines` and `publish_lines`: a pull before the cutoff is a
`snapshot` at its fetch time, the first pull at or after it the untimed `closing` row (D-120).
Nothing here touches a `cfb` row. NFL teams get no `team_seasons` row: nflverse's schedule has no
conference.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any

from sqlalchemy import Connection

from engine.publish.lines import map_lines, publish_lines
from engine.publish.reference import upsert_games, upsert_teams, upsert_venues
from engine.sports.nfl import SOURCE, SPORT, TEAMS, team_row

# The tables an NFL publish writes, in order; `publish_nfl` returns the rows each gained.
TABLES = ("teams", "venues", "games", "sportsbooks", "line_snapshots")
# nflverse `roof` -> venues.dome; `open` and `closed` (a retractable roof) and blank are unknown.
DOME = {"dome": True, "outdoors": False}


def _grass(surface: str | None) -> bool | None:
    return None if surface is None else surface.strip().lower() == "grass"


def publish_nfl(
    conn: Connection,
    games: Sequence[Mapping[str, Any]],
    lines: Sequence[Mapping[str, Any]],
    venues: Sequence[Mapping[str, Any]],
) -> dict[str, int]:
    """Upsert the staged NFL teams, venues and games and insert their new line rows, in the
    caller's transaction. Returns the new rows per table in `TABLES`."""
    new: Counter[str] = Counter()
    codes = sorted({g["home_source_id"] for g in games} | {g["away_source_id"] for g in games})
    unknown = [c for c in codes if c not in TEAMS]
    if unknown:
        print(f"NFL team codes with no name, published as the code: {', '.join(unknown)}")
    team_ids = upsert_teams(conn, SPORT, SOURCE, [team_row(c) for c in codes], new)
    venue_ids = upsert_venues(
        conn,
        SOURCE,
        [
            {
                "source_id": v["source_id"],
                "name": v["name"],
                "dome": DOME.get(v["roof"] or ""),
                "grass": _grass(v["surface"]),
            }
            for v in venues
            if v["name"]  # venues.name is NOT NULL
        ],
        new,
    )
    game_ids = upsert_games(
        conn,
        SPORT,
        SOURCE,
        [
            {
                "source_id": g["source_id"],
                "season": g["season"],
                "week": g["week"],
                "season_type": g["season_type"],
                "game_date": g["game_date"],
                "kickoff_at": g["kickoff_at"],
                "neutral_site": g["neutral_site"],
                "conference_game": g["conference_game"],
                "venue_id": venue_ids.get(g["venue_source_id"] or ""),
                "home_team_id": team_ids[g["home_source_id"]],
                "away_team_id": team_ids[g["away_source_id"]],
                "home_points": g["home_points"],
                "away_points": g["away_points"],
                "status": g["status"],
            }
            for g in games
        ],
        new,
    )
    publish_lines(conn, SOURCE, map_lines(lines, games), game_ids, new)
    return {name: new[name] for name in TABLES}
