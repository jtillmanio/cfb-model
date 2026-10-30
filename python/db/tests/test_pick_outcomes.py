"""`pick_outcomes` (TASK-041): every pick graded against the line it was made at, with CLV
against `game_market`'s closing line (D-132's sign, 04 § 9.3).

Rows use the throwaway sport in `model_rows` and roll back (db_conn). `game_market`'s close is
NULL until the game's cutoff has passed by the database clock, so a game that has closed kicks
off in the past and one that hasn't kicks off in 2030."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

import model_rows as m
from sqlalchemy import Connection, text
from test_current_picks import assert_one_game_read_uses_an_index

PAST = m.utc(2025, 9, 6, 16)
FUTURE = m.utc(2030, 9, 7, 16)


def _graded(
    conn: Connection,
    side: str,
    line: float,
    *,
    status: str = "final",
    points: tuple[int, int] = (30, 20),
    kickoff: datetime = FUTURE,
    lines: tuple[tuple[str, datetime | None, float], ...] = (),
) -> dict[str, Any]:
    """One game with one spread pick on `side` at `line` (a snapshot the morning of the week),
    plus any other `lines` (kind, captured_at, spread_home); its pick_outcomes row."""
    m.sport(conn)
    tag = uuid.uuid4().hex[:8]
    home, away = m.team(conn, f"home-{tag}"), m.team(conn, f"away-{tag}")
    game_id = m.game(conn, home, away, kickoff, week=1, status=status, points=points)
    version_id = m.version(conn, f"views-{tag}")
    picked_at = kickoff.replace(day=kickoff.day - 5)
    run_id = m.run(conn, version_id, 1, picked_at)
    book_id = m.book(conn)
    snapshot = m.line(conn, game_id, book_id, picked_at, line)
    for kind, at, spread in lines:
        m.line(conn, game_id, book_id, at, spread, kind)
    m.pick(conn, m.prediction(conn, run_id, version_id, game_id), version_id, game_id, snapshot,
           picked_at, side=side, line=line, edge_pts=4.0 if side == "home" else -4.0)  # fmt: skip
    return dict(
        conn.execute(text("SELECT * FROM pick_outcomes WHERE game_id = :g"), {"g": game_id})
        .one()
        ._mapping
    )


def test_a_home_pick_at_minus_3_wins_pushes_and_loses(db_conn: Connection):
    """AC-2: home by 4 covers −3, by 3 pushes, by 2 doesn't; +1.0u, 0, −1.1u at −110."""
    graded = [_graded(db_conn, "home", -3.0, points=(20 + margin, 20)) for margin in (4, 3, 2)]

    assert [(g["margin"], g["result"], g["units"]) for g in graded] == [
        (4, "won", Decimal("1.0")),
        (3, "push", Decimal("0")),
        (2, "lost", Decimal("-1.1")),
    ]
    assert [g["risked"] for g in graded] == [Decimal("1.1"), Decimal("0"), Decimal("1.1")]
    assert all(g["is_current"] and g["line"] == Decimal("-3.0") for g in graded)


def test_an_away_pick_mirrors_it(db_conn: Connection):
    """AC-2: the away side at home −3 loses on home by 4, pushes on 3 and wins on 2."""
    graded = [_graded(db_conn, "away", -3.0, points=(20 + margin, 20)) for margin in (4, 3, 2)]

    assert [(g["margin"], g["result"], g["units"]) for g in graded] == [
        (4, "lost", Decimal("-1.1")),
        (3, "push", Decimal("0")),
        (2, "won", Decimal("1.0")),
    ]


def test_unplayed_games_are_pending_and_canceled_ones_void(db_conn: Connection):
    """AC-2: scheduled and in-progress games are pending with NULL units; canceled and
    postponed games are void with 0 units."""
    graded = {
        status: _graded(db_conn, "home", -3.0, status=status)
        for status in ("scheduled", "in_progress", "canceled", "postponed")
    }

    assert {s: (g["result"], g["units"], g["risked"]) for s, g in graded.items()} == {
        "scheduled": ("pending", None, None),
        "in_progress": ("pending", None, None),
        "canceled": ("void", Decimal("0"), Decimal("0")),
        "postponed": ("void", Decimal("0"), Decimal("0")),
    }


def test_clv_has_d132s_sign(db_conn: Connection):
    """AC-3: picked at home −2.5, closed at −3.5: the home side got the better number (+1.0)
    and the away side the worse one (−1.0), against CFBD's close."""
    close = (("closing", None, -3.5),)
    home = _graded(db_conn, "home", -2.5, kickoff=PAST, lines=close)
    away = _graded(db_conn, "away", -2.5, kickoff=PAST, lines=close)

    assert (home["closing_spread_home"], home["clv"]) == (Decimal("-3.5"), Decimal("1.0"))
    assert (away["closing_spread_home"], away["clv"]) == (Decimal("-3.5"), Decimal("-1.0"))


def test_clv_is_null_until_the_close(db_conn: Connection):
    """AC-3: before the cutoff `game_market` has no closing line, so CLV is NULL; the line's
    move so far is `clv_so_far`, against the current line."""
    later = (("snapshot", FUTURE.replace(day=FUTURE.day - 1), -3.5),)
    graded = _graded(db_conn, "home", -2.5, status="scheduled", lines=later)

    assert (graded["closing_spread_home"], graded["clv"]) == (None, None)
    assert (graded["current_spread_home"], graded["clv_so_far"]) == (
        Decimal("-3.5"),
        Decimal("1.0"),
    )


def test_edge_buckets_are_the_display_buckets(db_conn: Connection):
    """04 § 9.4's pick buckets on abs(edge_pts), lower bound in."""
    m.sport(db_conn)
    home, away = m.team(db_conn, "home"), m.team(db_conn, "away")
    game_id = m.game(db_conn, home, away, FUTURE, week=1, status="scheduled")
    version_id = m.version(db_conn)
    run_id = m.run(db_conn, version_id, 1, m.utc(2030, 9, 1, 10))
    prediction_id = m.prediction(db_conn, run_id, version_id, game_id)
    book_id = m.book(db_conn)
    edges = {2.4: "<2.5", 2.5: "2.5-3.5", -3.4: "2.5-3.5", 3.5: "3.5-5.0", -5.0: "5.0-7.0",
             6.9: "5.0-7.0", 7.0: "7.0+", -12.0: "7.0+"}  # fmt: skip
    for hour, edge in enumerate(edges):
        at = m.utc(2030, 9, 1, hour)
        snapshot = m.line(db_conn, game_id, book_id, at, -1.0)
        m.pick(db_conn, prediction_id, version_id, game_id, snapshot, at,
               side="home" if edge > 0 else "away", line=-1.0, edge_pts=edge)  # fmt: skip

    rows = db_conn.execute(
        text("SELECT edge_pts, edge_bucket FROM pick_outcomes WHERE game_id = :g"),
        {"g": game_id},
    ).all()

    assert {r.edge_pts: r.edge_bucket for r in rows} == edges


def test_one_game_read_uses_an_index(db_conn: Connection):
    """AC-6."""
    assert_one_game_read_uses_an_index(db_conn, "pick_outcomes")
