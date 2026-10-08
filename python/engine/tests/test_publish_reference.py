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
