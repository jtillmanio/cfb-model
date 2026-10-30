"""`current_picks` (TASK-041): the newest pick per game, model version, market and line source,
or none when the newest row is a pass (D-140).

The constructed rows use the throwaway sport in `model_rows` and roll back (db_conn); the seeded
test reads the fixture CI loads before pytest (`pnpm db:seed`, D-089)."""

from __future__ import annotations

from dataclasses import dataclass

import model_rows as m
from sqlalchemy import Connection, text

# design/handoff/designs/picks-data.js `current`: This Week's 9 picks.
WEEK6_GAMES = {
    "2026-w6-tex-ou",
    "2026-w6-miss-lsu",
    "2026-w6-pur-osu",
    "2026-w6-isu-cin",
    "2026-w6-colo-byu",
    "2026-w6-nd-stan",
    "2026-w6-asu-bay",
    "2026-w6-tuln-mem",
    "2026-w6-iowa-wis",
}

SEEDED_V1 = (
    "SELECT id FROM model_versions WHERE sport_id = 'cfb' AND market = 'spread'"
    " AND name = 'power' AND version = 'v1.0' AND deleted_at IS NULL"
)


@dataclass(frozen=True)
class Game:
    id: int
    version_id: int
    prediction_id: int
    book_id: int


def _game(conn: Connection, name: str = "views") -> Game:
    m.sport(conn)
    home, away = m.team(conn, f"home-{name}"), m.team(conn, f"away-{name}")
    game_id = m.game(conn, home, away, m.utc(2030, 9, 7, 16), week=1, status="scheduled")
    version_id = m.version(conn, name)
    run_id = m.run(conn, version_id, 1, m.utc(2030, 9, 1, 10))
    return Game(
        id=game_id,
        version_id=version_id,
        prediction_id=m.prediction(conn, run_id, version_id, game_id),
        book_id=m.book(conn),
    )


def _current(conn: Connection, game_id: int) -> list[dict[str, object]]:
    rows = conn.execute(
        text("SELECT * FROM current_picks WHERE game_id = :g ORDER BY id"), {"g": game_id}
    )
    return [dict(r._mapping) for r in rows]


def test_a_later_pick_replaces_the_earlier_one(db_conn: Connection):
    """AC-1: the second pick, made later at a new line snapshot, is the only current one."""
    g = _game(db_conn)
    sunday = m.line(db_conn, g.id, g.book_id, m.utc(2030, 9, 1, 10), -1.0)
    thursday = m.line(db_conn, g.id, g.book_id, m.utc(2030, 9, 5, 1), -2.0)
    m.pick(db_conn, g.prediction_id, g.version_id, g.id, sunday, m.utc(2030, 9, 1, 10, 10),
           side="home", line=-1.0, edge_pts=3.5, tier="B")  # fmt: skip
    second = m.pick(db_conn, g.prediction_id, g.version_id, g.id, thursday, m.utc(2030, 9, 5, 1),
                    side="home", line=-2.0, edge_pts=2.5, tier="C")  # fmt: skip

    rows = _current(db_conn, g.id)

    assert [(r["id"], r["model_version_id"], r["market"], r["line_source"]) for r in rows] == [
        (second, g.version_id, "spread", "market")
    ]
    assert (rows[0]["line_snapshot_id"], rows[0]["tier"]) == (thursday, "C")


def test_each_version_has_its_own_current_pick(db_conn: Connection):
    """AC-1: a second version's pick on the same game is its own row."""
    g = _game(db_conn)
    at = m.line(db_conn, g.id, g.book_id, m.utc(2030, 9, 1, 10), -1.0)
    first = m.pick(db_conn, g.prediction_id, g.version_id, g.id, at, m.utc(2030, 9, 1, 10, 10),
                   side="home", line=-1.0)  # fmt: skip
    other = m.version(db_conn, "other")
    run_id = m.run(db_conn, other, 1, m.utc(2030, 9, 1, 10))
    prediction_id = m.prediction(db_conn, run_id, other, g.id)
    second = m.pick(db_conn, prediction_id, other, g.id, at, m.utc(2030, 9, 1, 10, 20),
                    side="away", line=-1.0, edge_pts=-4.0)  # fmt: skip

    rows = _current(db_conn, g.id)

    assert {(r["model_version_id"], r["id"]) for r in rows} == {
        (g.version_id, first),
        (other, second),
    }


def test_a_pass_as_the_latest_row_means_no_pick(db_conn: Connection):
    """D-140: a re-evaluation that drops the pick is a pass row, and the game has no current
    pick; the pick made after it is current again."""
    g = _game(db_conn)
    sunday = m.line(db_conn, g.id, g.book_id, m.utc(2030, 9, 1, 10), -1.0)
    tuesday = m.line(db_conn, g.id, g.book_id, m.utc(2030, 9, 3, 10), -3.5)
    thursday = m.line(db_conn, g.id, g.book_id, m.utc(2030, 9, 5, 1), -1.5)
    m.pick(db_conn, g.prediction_id, g.version_id, g.id, sunday, m.utc(2030, 9, 1, 10, 10),
           side="home", line=-1.0)  # fmt: skip
    m.pick(db_conn, g.prediction_id, g.version_id, g.id, tuesday, m.utc(2030, 9, 3, 10),
           side=None, line=-3.5, edge_pts=1.0)  # fmt: skip

    assert _current(db_conn, g.id) == []

    again = m.pick(db_conn, g.prediction_id, g.version_id, g.id, thursday, m.utc(2030, 9, 5, 1),
                   side="home", line=-1.5, edge_pts=3.0, tier="C")  # fmt: skip

    assert [r["id"] for r in _current(db_conn, g.id)] == [again]


def test_seeded_week_6_has_nine_current_picks(db_conn: Connection):
    """AC-1: v1.0 has This Week's 9 current picks for 2026 week 6."""
    rows = db_conn.execute(
        text(
            "SELECT g.source_id FROM current_picks c JOIN games g ON g.id = c.game_id"
            f" WHERE c.model_version_id = ({SEEDED_V1}) AND g.season = 2026 AND g.week = 6"
            " AND g.season_type = 'regular'"
        )
    ).scalars()

    games = list(rows)
    assert len(games) == 9
    assert set(games) == WEEK6_GAMES


def assert_one_game_read_uses_an_index(conn: Connection, view: str) -> None:
    """AC-6: one game's picks are read through an index on picks that names the game, never a
    sequential scan of every pick (sequential scans priced out, so one that remains is forced)."""
    game_id = conn.execute(
        text(
            "SELECT p.game_id FROM picks p JOIN games g ON g.id = p.game_id"
            " WHERE g.source_id = '2026-w6-miss-lsu'"
        )
    ).scalar_one()

    plan = m.explain(conn, f"SELECT * FROM {view} WHERE game_id = :g", {"g": game_id})

    scans = m.scans(plan, "picks")
    assert scans
    for node in scans:
        assert node["Node Type"] != "Seq Scan", node
        assert "game_id" in (node.get("Index Cond") or node.get("Recheck Cond") or ""), node


def test_one_game_read_uses_an_index(db_conn: Connection):
    """AC-6."""
    assert_one_game_read_uses_an_index(db_conn, "current_picks")
