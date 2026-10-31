"""CFBD /games (API v2) -> reference rows. Pure: no network, no database."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

from engine.ingest.endpoints import done

# CFB's calendar day is the Eastern one: a 8 PM ET kickoff is 00:00Z the next day,
# and CFBD sends a TBA kickoff as midnight Eastern.
EASTERN = ZoneInfo("America/New_York")


@dataclass(frozen=True)
class TeamRow:
    source_id: str
    school: str


@dataclass(frozen=True)
class TeamSeasonRow:
    team_source_id: str
    season: int
    conference: str | None
    division: str | None


@dataclass(frozen=True)
class VenueRow:
    source_id: str
    name: str


@dataclass(frozen=True)
class GameRow:
    source_id: str
    season: int
    week: int
    season_type: str
    game_date: date
    kickoff_at: datetime | None
    neutral_site: bool
    conference_game: bool
    venue_source_id: str | None
    home_source_id: str
    away_source_id: str
    home_points: int | None
    away_points: int | None
    status: str


@dataclass
class GamesBatch:
    teams: list[TeamRow] = field(default_factory=list)
    team_seasons: list[TeamSeasonRow] = field(default_factory=list)
    venues: list[VenueRow] = field(default_factory=list)
    games: list[GameRow] = field(default_factory=list)


def _start(raw: str) -> datetime:
    return datetime.fromisoformat(raw.replace("Z", "+00:00"))


def _status(g: Mapping[str, Any], saved_at: datetime | None) -> str:
    """The transform's rule (D-145): completed is final; unscored and uncompleted on a file saved
    7+ days after its start is canceled (D-121's `endpoints.done`); else scheduled."""
    if g["completed"]:
        return "final"
    return "canceled" if saved_at is not None and done(g, saved_at) else "scheduled"


def _game(g: Mapping[str, Any], saved_at: datetime | None) -> GameRow:
    start = _start(g["startDate"])
    completed = bool(g["completed"])
    home_points, away_points = g.get("homePoints"), g.get("awayPoints")
    if completed and (home_points is None or away_points is None):
        raise ValueError(f"CFBD game {g['id']} is completed but has no final score.")
    return GameRow(
        source_id=str(g["id"]),
        season=int(g["season"]),
        week=int(g["week"]),
        season_type=str(g["seasonType"]),
        game_date=start.astimezone(EASTERN).date(),
        kickoff_at=None if g.get("startTimeTBD") else start,
        neutral_site=bool(g["neutralSite"]),
        conference_game=bool(g["conferenceGame"]),
        venue_source_id=None if g.get("venueId") is None else str(g["venueId"]),
        home_source_id=str(g["homeId"]),
        away_source_id=str(g["awayId"]),
        home_points=home_points,
        away_points=away_points,
        status=_status(g, saved_at),
    )


def map_games(
    payload: Iterable[Mapping[str, Any]], saved_at: datetime | None = None
) -> GamesBatch:
    """`saved_at` is when the response's file was saved: without it no game is canceled."""
    batch = GamesBatch()
    teams: dict[str, TeamRow] = {}
    seasons: dict[tuple[str, int], TeamSeasonRow] = {}
    venues: dict[str, VenueRow] = {}
    for g in payload:
        game = _game(g, saved_at)
        batch.games.append(game)
        for side in ("home", "away"):
            source_id = str(g[f"{side}Id"])
            teams[source_id] = TeamRow(source_id, g[f"{side}Team"])
            seasons[(source_id, game.season)] = TeamSeasonRow(
                source_id, game.season, g.get(f"{side}Conference"), g.get(f"{side}Classification")
            )
        if game.venue_source_id is not None:
            venues[game.venue_source_id] = VenueRow(game.venue_source_id, g["venue"])
    batch.teams = list(teams.values())
    batch.team_seasons = list(seasons.values())
    batch.venues = list(venues.values())
    return batch
