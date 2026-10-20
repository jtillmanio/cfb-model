"""`game_market` (TASK-020): each game's opening, current and closing line, from the `consensus`
book when it quoted one, else the median across books.

The constructed games use throwaway sources and roll back (db_conn); line snapshots use
'manual', which the source CHECK allows. The seeded tests read the fixture that CI loads before
pytest (`pnpm db:seed`, D-089)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Connection, text

SOURCE = "pytest"
LINE_SOURCE = "manual"


def _team(conn: Connection, source_id: str) -> int:
    return conn.execute(
        text(
            "INSERT INTO teams (sport_id, source, source_id, school)"
            " VALUES ('cfb', :s, :sid, :sid) RETURNING id"
        ),
        {"s": SOURCE, "sid": source_id},
    ).scalar_one()


def _game(conn: Connection, game_date: str, kickoff_at: datetime | None) -> int:
    home, away = _team(conn, f"home-{game_date}"), _team(conn, f"away-{game_date}")
    return conn.execute(
        text(
            "INSERT INTO games (sport_id, source, source_id, season, week, season_type, game_date,"
            " kickoff_at, neutral_site, conference_game, home_team_id, away_team_id, status)"
            " VALUES ('cfb', :s, :sid, 2025, 7, 'regular', :d, :k, false, false, :home, :away,"
            " 'scheduled') RETURNING id"
        ),
        {
            "s": SOURCE,
            "sid": f"g-{game_date}",
            "d": game_date,
            "k": kickoff_at,
            "home": home,
            "away": away,
        },
    ).scalar_one()


def _book(conn: Connection, source_id: str) -> int:
    return conn.execute(
        text(
            "INSERT INTO sportsbooks (source, source_id, name) VALUES (:s, :sid, :sid)"
            " ON CONFLICT (source, source_id) DO UPDATE SET name = EXCLUDED.name RETURNING id"
        ),
        {"s": SOURCE, "sid": source_id},
    ).scalar_one()


def _line(
    conn: Connection,
    game: int,
    spread: float,
    at: datetime | None,
    kind: str = "snapshot",
    book: str = "consensus",
    total: float | None = None,
) -> None:
    conn.execute(
        text(
            "INSERT INTO line_snapshots (game_id, book_id, source, kind, captured_at, spread_home,"
            " total) VALUES (:g, :b, :s, :k, :at, :spread, :total)"
        ),
        {
            "g": game,
            "b": _book(conn, book),
            "s": LINE_SOURCE,
            "k": kind,
            "at": at,
            "spread": spread,
            "total": total,
        },
    )


def _market(conn: Connection, game: int) -> dict[str, Any]:
    row = conn.execute(text("SELECT * FROM game_market WHERE game_id = :g"), {"g": game}).one()
    return dict(row._mapping)


def _utc(*args: int) -> datetime:
    return datetime(*args, tzinfo=UTC)


def test_closing_is_last_snapshot_before_kickoff(db_conn: Connection):
    """AC-3: Sat 2025-10-11 kickoff; snapshots Sun, Tue, Thu, Sat before it and one after."""
    game = _game(db_conn, "2025-10-11", _utc(2025, 10, 11, 23, 30))
    _line(db_conn, game, -3, _utc(2025, 10, 5, 10), total=55)  # Sun
    _line(db_conn, game, -3.5, _utc(2025, 10, 7, 16))  # Tue
    _line(db_conn, game, -4, _utc(2025, 10, 9, 16))  # Thu
    _line(db_conn, game, -4.5, _utc(2025, 10, 11, 13), total=53.5)  # Sat
    _line(db_conn, game, -7, _utc(2025, 10, 12, 1))  # in-game

    m = _market(db_conn, game)

    assert (m["opening_spread_home"], m["opening_total"]) == (Decimal("-3"), Decimal("55"))
    assert m["opening_captured_at"] == _utc(2025, 10, 5, 10)
    assert (m["closing_spread_home"], m["closing_total"]) == (Decimal("-4.5"), Decimal("53.5"))
    assert m["closing_from"] == "last_snapshot"
    assert m["current_spread_home"] == Decimal("-7")
    assert m["current_captured_at"] == _utc(2025, 10, 12, 1)
    assert (m["opening_source"], m["current_source"], m["closing_source"]) == (
        "consensus",
        "consensus",
        "consensus",
    )


def test_opening_row_and_cfbd_close_win_over_snapshots(db_conn: Connection):
    game = _game(db_conn, "2025-10-11", _utc(2025, 10, 11, 23, 30))
    _line(db_conn, game, -2.5, None, kind="opening")
    _line(db_conn, game, -3, _utc(2025, 10, 5, 10))
    _line(db_conn, game, -4, _utc(2025, 10, 11, 13))
    _line(db_conn, game, -5, None, kind="closing")

    m = _market(db_conn, game)

    assert m["opening_spread_home"] == Decimal("-2.5")
    assert m["opening_captured_at"] is None
    assert (m["closing_spread_home"], m["closing_from"]) == (Decimal("-5"), "cfbd_close")
    assert m["current_spread_home"] == Decimal("-4")


def test_closing_null_before_kickoff(db_conn: Connection):
    game = _game(db_conn, "2099-10-10", _utc(2099, 10, 10, 23, 30))
    _line(db_conn, game, -3, _utc(2099, 10, 4, 10))
    _line(db_conn, game, -3.5, _utc(2099, 10, 8, 10))

    m = _market(db_conn, game)

    assert (m["opening_spread_home"], m["current_spread_home"]) == (Decimal("-3"), Decimal("-3.5"))
    assert m["closing_spread_home"] is None
    assert m["closing_from"] is None


def test_tba_closing_uses_end_of_eastern_date(db_conn: Connection):
    """AC-4: kickoff_at NULL on Sat 2025-10-11. 23:30 ET (03:30Z Sun) is still Saturday in
    Eastern time; 00:30 ET (04:30Z) is not."""
    game = _game(db_conn, "2025-10-11", None)
    _line(db_conn, game, -1, _utc(2025, 10, 10, 12))
    _line(db_conn, game, -2, _utc(2025, 10, 12, 3, 30))
    _line(db_conn, game, -9, _utc(2025, 10, 12, 4, 30))

    m = _market(db_conn, game)

    assert (m["closing_spread_home"], m["closing_from"]) == (Decimal("-2"), "last_snapshot")
    assert m["current_spread_home"] == Decimal("-9")


def test_median_without_consensus(db_conn: Connection):
    """AC-4: no consensus line, three providers: the median, marked as one."""
    game = _game(db_conn, "2025-10-11", _utc(2025, 10, 11, 23, 30))
    at = _utc(2025, 10, 9, 16)
    for book, spread, total in (("Bovada", -3, 50), ("DraftKings", -4, 52), ("ESPN Bet", -6, 51)):
        _line(db_conn, game, spread, at, book=book, total=total)

    m = _market(db_conn, game)

    for line in ("opening", "current", "closing"):
        assert m[f"{line}_spread_home"] == Decimal("-4")
        assert m[f"{line}_total"] == Decimal("51")
        assert m[f"{line}_source"] == "median"


def test_consensus_wins_over_the_median(db_conn: Connection):
    game = _game(db_conn, "2025-10-11", _utc(2025, 10, 11, 23, 30))
    at = _utc(2025, 10, 9, 16)
    # The median of the three is -3, so only the consensus rule gives -3.5.
    for book, spread in (("consensus", -3.5), ("Bovada", -3), ("DraftKings", -2)):
        _line(db_conn, game, spread, at, book=book)

    m = _market(db_conn, game)

    assert (m["current_spread_home"], m["current_source"]) == (Decimal("-3.5"), "consensus")


def _seeded(conn: Connection, source_id: str) -> int:
    return conn.execute(
        text("SELECT id FROM games WHERE source = 'fixture' AND source_id = :sid"),
        {"sid": source_id},
    ).scalar_one()


def test_seeded_texas_oklahoma_and_furman(db_conn: Connection):
    """AC-5."""
    tex_ou = _market(db_conn, _seeded(db_conn, "2026-w6-tex-ou"))
    assert tex_ou["opening_spread_home"] == Decimal("7")
    assert tex_ou["current_spread_home"] == Decimal("6.5")

    furman = _market(db_conn, _seeded(db_conn, "2026-w6-fur-clem"))
    prices = {k: v for k, v in furman.items() if k != "game_id"}
    assert prices and all(v is None for v in prices.values())


def _scans(plan: dict[str, Any]) -> list[dict[str, Any]]:
    found = [plan] if plan.get("Relation Name") == "line_snapshots" else []
    for child in plan.get("Plans", []):
        found += _scans(child)
    return found


def test_single_game_read_uses_index(db_conn: Connection):
    """AC-6: every read of line_snapshots for one game is an index lookup on game_id. With
    sequential scans priced out, a view that aggregated the whole table first would still show a
    Seq Scan, or an index scan with no game_id condition."""
    game = _seeded(db_conn, "2026-w6-tex-ou")
    db_conn.execute(text("SET LOCAL enable_seqscan = off"))
    raw = db_conn.execute(
        text("EXPLAIN (FORMAT JSON) SELECT * FROM game_market WHERE game_id = :g"), {"g": game}
    ).scalar_one()
    plan = (json.loads(raw) if isinstance(raw, str) else raw)[0]["Plan"]

    scans = _scans(plan)
    assert scans
    for node in scans:
        assert node["Node Type"] != "Seq Scan"
        cond = node.get("Index Cond") or node.get("Recheck Cond") or ""
        assert "game_id" in cond, node
