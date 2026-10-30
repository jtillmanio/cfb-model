"""`current_picks` (TASK-041): the newest pick per game, model version, market and line source,
or none when the newest row is a pass (D-140).

The constructed rows use the throwaway sport in `model_rows` and roll back (db_conn); the seeded
test reads the fixture CI loads before pytest (`pnpm db:seed`, D-089)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any

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


def _frozen_game(conn: Connection, kickoff: datetime | None, game_date: str | None = None) -> Game:
    m.sport(conn)
    home, away = m.team(conn, "home-frozen"), m.team(conn, "away-frozen")
    game_id = m.game(conn, home, away, kickoff, week=1, points=(24, 20), game_date=game_date)
    version_id = m.version(conn, "frozen")
    run_id = m.run(conn, version_id, 1, m.utc(2030, 9, 1, 10))
    return Game(
        id=game_id,
        version_id=version_id,
        prediction_id=m.prediction(conn, run_id, version_id, game_id),
        book_id=m.book(conn),
    )


def _graded(conn: Connection, g: Game) -> tuple[list[Any], list[Any], list[Any]]:
    """(current pick ids, pick_outcomes (id, is_current, result), to-date record rows)."""
    current = conn.execute(
        text("SELECT id FROM current_picks WHERE game_id = :g"), {"g": g.id}
    ).scalars()
    outcomes = conn.execute(
        text(
            "SELECT pick_id, is_current, result FROM pick_outcomes WHERE game_id = :g"
            " ORDER BY pick_id"
        ),
        {"g": g.id},
    ).all()
    record = conn.execute(
        text(
            "SELECT picks, wins, losses, units FROM model_record"
            " WHERE model_version_id = :v AND season = :s AND breakdown = 'to_date'"
        ),
        {"v": g.version_id, "s": m.SEASON},
    ).all()
    return list(current), [tuple(o) for o in outcomes], [tuple(r) for r in record]


def test_a_row_written_after_kickoff_changes_nothing(db_conn: Connection):
    """D-142, hard rule 4: the pick is frozen at kickoff. A pass and a flipped side written after
    kickoff (when the result can be known) leave the current pick, the graded rows and the
    record as they were: the home pick at −1, home by 4, a win."""
    kickoff = m.utc(2030, 9, 7, 16)
    g = _frozen_game(db_conn, kickoff)
    sunday = m.line(db_conn, g.id, g.book_id, m.utc(2030, 9, 1, 10), -1.0)
    late = m.line(db_conn, g.id, g.book_id, m.utc(2030, 9, 7, 18), -6.0)
    pick = m.pick(db_conn, g.prediction_id, g.version_id, g.id, sunday, m.utc(2030, 9, 1, 10, 10),
                  side="home", line=-1.0)  # fmt: skip
    before = _graded(db_conn, g)
    assert before == ([pick], [(pick, True, "won")], [(1, 1, 0, Decimal("1.0"))])

    m.pick(db_conn, g.prediction_id, g.version_id, g.id, late, kickoff,
           side=None, line=-6.0, edge_pts=0.5)  # fmt: skip
    later = m.line(db_conn, g.id, g.book_id, m.utc(2030, 9, 7, 19), -6.5)
    m.pick(db_conn, g.prediction_id, g.version_id, g.id, later, m.utc(2030, 9, 7, 19, 5),
           side="away", line=-6.5, edge_pts=-3.0, tier="C")  # fmt: skip

    assert _graded(db_conn, g) == before


def test_a_tba_kickoff_freezes_at_the_end_of_its_eastern_day(db_conn: Connection):
    """With no kickoff time the cutoff is the end of game_date in Eastern time (game_market's):
    a pass at 11:30 PM ET on game day counts, a pick at 12:30 AM ET the next day doesn't."""
    g = _frozen_game(db_conn, None, game_date="2030-09-07")
    sunday = m.line(db_conn, g.id, g.book_id, m.utc(2030, 9, 1, 10), -1.0)
    m.pick(db_conn, g.prediction_id, g.version_id, g.id, sunday, m.utc(2030, 9, 1, 10, 10),
           side="home", line=-1.0)  # fmt: skip
    night = m.line(db_conn, g.id, g.book_id, m.utc(2030, 9, 8, 3), -2.0)
    m.pick(db_conn, g.prediction_id, g.version_id, g.id, night, m.utc(2030, 9, 8, 3, 30),
           side=None, line=-2.0, edge_pts=0.5)  # 11:30 PM EDT on the 7th  # fmt: skip

    assert _current(db_conn, g.id) == []

    after = m.line(db_conn, g.id, g.book_id, m.utc(2030, 9, 8, 4, 30), -2.5)
    m.pick(db_conn, g.prediction_id, g.version_id, g.id, after, m.utc(2030, 9, 8, 4, 30),
           side="home", line=-2.5)  # 12:30 AM EDT on the 8th  # fmt: skip

    assert _current(db_conn, g.id) == []


def test_current_picks_are_pick_outcomes_current_rows(db_conn: Connection):
    """The window is written in both views (050, 060): they must pick the same rows, on the
    seed, on a game with a superseded pick and a pass before kickoff and a pick after the pass,
    and on one with a pass and a flipped side after kickoff."""
    test_a_pass_as_the_latest_row_means_no_pick(db_conn)
    test_a_row_written_after_kickoff_changes_nothing(db_conn)
    current = set(db_conn.execute(text("SELECT id FROM current_picks")).scalars())
    outcomes = set(
        db_conn.execute(text("SELECT pick_id FROM pick_outcomes WHERE is_current")).scalars()
    )

    assert len(current) >= 67
    assert current == outcomes
