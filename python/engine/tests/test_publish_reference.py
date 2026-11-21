"""Publishing a /games batch is idempotent: upserts by (source, source_id) keep IDs stable."""

import json
from pathlib import Path

from sqlalchemy import Connection, text

from engine.publish.reference import publish_games_batch
from engine.sports.cfb.games import map_games

SAMPLE = json.loads(
    (Path(__file__).parent / "fixtures" / "cfbd_games_sample.json").read_text(encoding="utf-8")
)
SOURCE = "pytest"  # never 'cfbd' or 'fixture', and rolled back by db_conn


def _ids(conn: Connection, table: str) -> dict[str, int]:
    rows = conn.execute(text(f"SELECT source_id, id FROM {table} WHERE source = :s"), {"s": SOURCE})
    return {source_id: id_ for source_id, id_ in rows}


def test_publishing_the_same_week_twice_keeps_ids_and_counts(db_conn: Connection):
    assert publish_games_batch(db_conn, "cfb", SOURCE, map_games(SAMPLE)) == 3
    first = {t: _ids(db_conn, t) for t in ("teams", "venues", "games")}

    assert publish_games_batch(db_conn, "cfb", SOURCE, map_games(SAMPLE)) == 3
    second = {t: _ids(db_conn, t) for t in ("teams", "venues", "games")}

    assert first == second
    assert (len(first["teams"]), len(first["venues"]), len(first["games"])) == (5, 2, 3)


def test_republishing_updates_a_changed_score_in_place(db_conn: Connection):
    publish_games_batch(db_conn, "cfb", SOURCE, map_games(SAMPLE))
    before = _ids(db_conn, "games")

    corrected = [{**SAMPLE[0], "homePoints": 17}]
    publish_games_batch(db_conn, "cfb", SOURCE, map_games(corrected))

    row = db_conn.execute(
        text("SELECT id, home_points FROM games WHERE source = :s AND source_id = '401752677'"),
        {"s": SOURCE},
    ).one()
    assert (row.id, row.home_points) == (before["401752677"], 17)


def test_a_publish_that_ends_a_live_game_clears_its_clock(db_conn: Connection):
    """TASK-074 (D-178): only the scores job writes a live clock. A /games or staged publish that
    moves a game out of `in_progress` clears `period` and `clock`, so it never trips
    `ck_games_clock_only_in_progress` or leaves a stale clock behind."""
    publish_games_batch(db_conn, "cfb", SOURCE, map_games(SAMPLE))
    final = next(g for g in SAMPLE if g["completed"])
    db_conn.execute(
        text(
            "UPDATE games SET status = 'in_progress', period = 4, clock = '01:10'"
            " WHERE source = :s AND source_id = :id"
        ),
        {"s": SOURCE, "id": str(final["id"])},
    )

    publish_games_batch(db_conn, "cfb", SOURCE, map_games([final]))

    row = db_conn.execute(
        text("SELECT status, period, clock FROM games WHERE source = :s AND source_id = :id"),
        {"s": SOURCE, "id": str(final["id"])},
    ).one()
    assert tuple(row) == ("final", None, None)
