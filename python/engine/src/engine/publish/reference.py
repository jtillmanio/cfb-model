"""Reference rows are upserted by (source, source_id): never truncated and reloaded, and
IDs never derived from load order (CLAUDE.md hard rule 3). Re-running a publish is a no-op
apart from refreshed values."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from sqlalchemy import Connection, func
from sqlalchemy.dialects.postgresql import insert

from db.models import Game, Team, TeamSeason, Venue
from engine.sports.cfb.games import GamesBatch


def _keys(rows: Sequence[Mapping[str, Any]]) -> list[str]:
    keys = list(rows[0])
    if any(list(r) != keys for r in rows):
        raise ValueError("Every row in one upsert must have the same columns.")
    return keys


def upsert_teams(
    conn: Connection, sport_id: str, source: str, rows: Sequence[Mapping[str, Any]]
) -> dict[str, int]:
    """Rows carry source_id plus the columns to set. Returns source_id -> teams.id."""
    if not rows:
        return {}
    values = [{**r, "sport_id": sport_id, "source": source} for r in rows]
    stmt = insert(Team).values(values)
    updates = {k: stmt.excluded[k] for k in _keys(rows) if k != "source_id"}
    stmt = stmt.on_conflict_do_update(
        index_elements=["sport_id", "source", "source_id"], set_=updates
    ).returning(Team.source_id, Team.id)
    return {source_id: id_ for source_id, id_ in conn.execute(stmt)}


def upsert_team_seasons(conn: Connection, rows: Sequence[Mapping[str, Any]]) -> None:
    """Rows carry team_id, season, conference, division."""
    if not rows:
        return
    stmt = insert(TeamSeason).values(list(rows))
    stmt = stmt.on_conflict_do_update(
        index_elements=["team_id", "season"],
        set_={"conference": stmt.excluded.conference, "division": stmt.excluded.division},
    )
    conn.execute(stmt)


def upsert_venues(
    conn: Connection, source: str, rows: Sequence[Mapping[str, Any]]
) -> dict[str, int]:
    if not rows:
        return {}
    stmt = insert(Venue).values([{**r, "source": source} for r in rows])
    updates = {k: stmt.excluded[k] for k in _keys(rows) if k != "source_id"}
    stmt = stmt.on_conflict_do_update(
        index_elements=["source", "source_id"], set_=updates
    ).returning(Venue.source_id, Venue.id)
    return {source_id: id_ for source_id, id_ in conn.execute(stmt)}


def upsert_games(
    conn: Connection, sport_id: str, source: str, rows: Sequence[Mapping[str, Any]]
) -> dict[str, int]:
    if not rows:
        return {}
    stmt = insert(Game).values([{**r, "sport_id": sport_id, "source": source} for r in rows])
    updates: dict[str, Any] = {k: stmt.excluded[k] for k in _keys(rows) if k != "source_id"}
    updates["updated_at"] = func.now()
    stmt = stmt.on_conflict_do_update(
        index_elements=["sport_id", "source", "source_id"], set_=updates
    ).returning(Game.source_id, Game.id)
    return {source_id: id_ for source_id, id_ in conn.execute(stmt)}


def publish_games_batch(conn: Connection, sport_id: str, source: str, batch: GamesBatch) -> int:
    """Upsert one mapped /games response. The caller owns the transaction."""
    team_ids = upsert_teams(
        conn,
        sport_id,
        source,
        [{"source_id": t.source_id, "school": t.school} for t in batch.teams],
    )
    upsert_team_seasons(
        conn,
        [
            {
                "team_id": team_ids[s.team_source_id],
                "season": s.season,
                "conference": s.conference,
                "division": s.division,
            }
            for s in batch.team_seasons
        ],
    )
    venue_ids = upsert_venues(
        conn, source, [{"source_id": v.source_id, "name": v.name} for v in batch.venues]
    )
    game_ids = upsert_games(
        conn,
        sport_id,
        source,
        [
            {
                "source_id": g.source_id,
                "season": g.season,
                "week": g.week,
                "season_type": g.season_type,
                "game_date": g.game_date,
                "kickoff_at": g.kickoff_at,
                "neutral_site": g.neutral_site,
                "conference_game": g.conference_game,
                "venue_id": None if g.venue_source_id is None else venue_ids[g.venue_source_id],
                "home_team_id": team_ids[g.home_source_id],
                "away_team_id": team_ids[g.away_source_id],
                "home_points": g.home_points,
                "away_points": g.away_points,
                "status": g.status,
            }
            for g in batch.games
        ],
    )
    return len(game_ids)
