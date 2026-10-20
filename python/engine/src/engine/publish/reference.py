"""Reference rows are upserted by (source, source_id): never truncated and reloaded, and
IDs never derived from load order (CLAUDE.md hard rule 3). Re-running a publish is a no-op
apart from refreshed values.

Each statement takes at most `CHUNK` rows, so a season of games or lines stays under Postgres's
65,535 bind parameters. A caller that passes `new` gets the rows each table gained, by table
name (`xmax = 0` marks a row the upsert inserted rather than updated)."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterator, Mapping, Sequence
from typing import Any

from sqlalchemy import Connection, func, literal_column
from sqlalchemy.dialects.postgresql import insert

from db.models import Game, LineSnapshot, Season, Sportsbook, Team, TeamSeason, Venue
from engine.sports.cfb.games import GamesBatch

CHUNK = 1000
INSERTED = literal_column("xmax = 0").label("inserted")


def _keys(rows: Sequence[Mapping[str, Any]]) -> list[str]:
    keys = list(rows[0])
    if any(list(r) != keys for r in rows):
        raise ValueError("Every row in one upsert must have the same columns.")
    return keys


def _chunks(rows: Sequence[Mapping[str, Any]]) -> Iterator[Sequence[Mapping[str, Any]]]:
    for start in range(0, len(rows), CHUNK):
        yield rows[start : start + CHUNK]


def _count(new: Counter[str] | None, table: str, inserted: int) -> None:
    if new is not None:
        new[table] += inserted


def _upsert_ids(
    conn: Connection,
    model: type[Team | Venue | Game | Sportsbook],
    rows: Sequence[Mapping[str, Any]],
    fixed: Mapping[str, Any],
    index_elements: list[str],
    new: Counter[str] | None,
    touch: bool = False,
) -> dict[str, int]:
    """Upsert by `index_elements`, setting every column but source_id (and `updated_at` when
    `touch`). Returns source_id -> id."""
    if not rows:
        return {}
    keys = _keys(rows)
    ids: dict[str, int] = {}
    for chunk in _chunks(rows):
        stmt = insert(model).values([{**r, **fixed} for r in chunk])
        updates: dict[str, Any] = {k: stmt.excluded[k] for k in keys if k != "source_id"}
        if touch:
            updates["updated_at"] = func.now()
        stmt = stmt.on_conflict_do_update(index_elements=index_elements, set_=updates).returning(
            model.source_id, model.id, INSERTED
        )
        result = conn.execute(stmt).all()
        ids.update((source_id, id_) for source_id, id_, _ in result)
        _count(new, model.__tablename__, sum(inserted for *_, inserted in result))
    return ids


def upsert_teams(
    conn: Connection,
    sport_id: str,
    source: str,
    rows: Sequence[Mapping[str, Any]],
    new: Counter[str] | None = None,
) -> dict[str, int]:
    """Rows carry source_id plus the columns to set. Returns source_id -> teams.id."""
    fixed = {"sport_id": sport_id, "source": source}
    return _upsert_ids(conn, Team, rows, fixed, ["sport_id", "source", "source_id"], new)


def upsert_team_seasons(
    conn: Connection, rows: Sequence[Mapping[str, Any]], new: Counter[str] | None = None
) -> None:
    """Rows carry team_id, season, conference, division."""
    for chunk in _chunks(rows):
        stmt = insert(TeamSeason).values(list(chunk))
        stmt = stmt.on_conflict_do_update(
            index_elements=["team_id", "season"],
            set_={"conference": stmt.excluded.conference, "division": stmt.excluded.division},
        ).returning(INSERTED)
        _count(new, "team_seasons", sum(conn.execute(stmt).scalars()))


def upsert_venues(
    conn: Connection,
    source: str,
    rows: Sequence[Mapping[str, Any]],
    new: Counter[str] | None = None,
) -> dict[str, int]:
    return _upsert_ids(conn, Venue, rows, {"source": source}, ["source", "source_id"], new)


def upsert_games(
    conn: Connection,
    sport_id: str,
    source: str,
    rows: Sequence[Mapping[str, Any]],
    new: Counter[str] | None = None,
) -> dict[str, int]:
    fixed = {"sport_id": sport_id, "source": source}
    return _upsert_ids(
        conn, Game, rows, fixed, ["sport_id", "source", "source_id"], new, touch=True
    )


def upsert_season(
    conn: Connection, row: Mapping[str, Any], new: Counter[str] | None = None
) -> None:
    """One seasons row by (sport_id, year): source, start_date, end_date, current_week, weeks."""
    stmt = insert(Season).values(dict(row))
    updates: dict[str, Any] = {k: stmt.excluded[k] for k in row if k not in ("sport_id", "year")}
    updates["updated_at"] = func.now()
    stmt = stmt.on_conflict_do_update(index_elements=["sport_id", "year"], set_=updates)
    _count(new, "seasons", conn.execute(stmt.returning(INSERTED)).scalar_one())


def upsert_sportsbooks(
    conn: Connection,
    source: str,
    rows: Sequence[Mapping[str, Any]],
    new: Counter[str] | None = None,
) -> dict[str, int]:
    """Rows carry source_id and name. Returns source_id -> sportsbooks.id."""
    return _upsert_ids(conn, Sportsbook, rows, {"source": source}, ["source", "source_id"], new)


def insert_line_snapshots(
    conn: Connection,
    source: str,
    rows: Sequence[Mapping[str, Any]],
    new: Counter[str] | None = None,
) -> int:
    """Append-only (D-037): a row whose key (game, book, source, kind, captured_at) is already
    stored is skipped, so re-publishing one raw file inserts nothing. Returns rows inserted."""
    if not rows:
        return 0
    _keys(rows)
    inserted = 0
    for chunk in _chunks(rows):
        stmt = insert(LineSnapshot).values([{**r, "source": source} for r in chunk])
        stmt = stmt.on_conflict_do_nothing(
            index_elements=["game_id", "book_id", "source", "kind", "captured_at"]
        ).returning(LineSnapshot.id)
        inserted += len(conn.execute(stmt).all())
    _count(new, "line_snapshots", inserted)
    return inserted


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
