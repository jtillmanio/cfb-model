"""Market and reference tables (TASK-016): seasons, team_aliases, sportsbooks, line_snapshots.

The constraint tests write rows with throwaway sources and roll back (db_conn). The seed tests
read the fixture that CI loads before pytest (`pnpm db:seed`, D-089)."""

from decimal import Decimal

import pytest
from psycopg import errors
from sqlalchemy import Connection, inspect, text
from sqlalchemy.exc import DBAPIError, IntegrityError

NEW_TABLES = ("seasons", "team_aliases", "sportsbooks", "line_snapshots")
SOURCE = "pytest"  # never 'cfbd' or 'fixture'; line_snapshots allows only its CHECK list
LINE_SOURCE = "manual"
KEY = "(game_id, book_id, source, kind, captured_at)"


def _team(conn: Connection, source_id: str) -> int:
    return conn.execute(
        text(
            "INSERT INTO teams (sport_id, source, source_id, school)"
            " VALUES ('cfb', :s, :sid, :sid) RETURNING id"
        ),
        {"s": SOURCE, "sid": source_id},
    ).scalar_one()


def _game(conn: Connection) -> int:
    home, away = _team(conn, "home"), _team(conn, "away")
    return conn.execute(
        text(
            "INSERT INTO games (sport_id, source, source_id, season, week, season_type, game_date,"
            " neutral_site, conference_game, home_team_id, away_team_id, status)"
            " VALUES ('cfb', :s, 'g1', 2026, 6, 'regular', '2026-10-10', false, false,"
            " :home, :away, 'scheduled') RETURNING id"
        ),
        {"s": SOURCE, "home": home, "away": away},
    ).scalar_one()


def _book(conn: Connection) -> int:
    return conn.execute(
        text(
            "INSERT INTO sportsbooks (source, source_id, name)"
            " VALUES (:s, 'book', 'Book') RETURNING id"
        ),
        {"s": SOURCE},
    ).scalar_one()


def _alias(conn: Connection, team_id: int, source: str, alias: str) -> None:
    conn.execute(
        text("INSERT INTO team_aliases (team_id, source, alias) VALUES (:t, :s, :a)"),
        {"t": team_id, "s": source, "a": alias},
    )


def _snapshots(conn: Connection, rows: list[dict]) -> int:
    """Insert through the idempotency key, as a re-publish does. Returns rows inserted."""
    result = conn.execute(
        text(
            "INSERT INTO line_snapshots (game_id, book_id, source, kind, captured_at, spread_home)"
            " VALUES (:game_id, :book_id, :source, :kind, :captured_at, :spread_home)"
            f" ON CONFLICT {KEY} DO NOTHING"
        ),
        rows,
    )
    return result.rowcount


def _count(conn: Connection, game_id: int) -> int:
    return conn.execute(
        text("SELECT count(*) FROM line_snapshots WHERE game_id = :g"), {"g": game_id}
    ).scalar_one()


def test_the_four_tables_exist(db_conn: Connection):
    insp = inspect(db_conn)
    assert set(NEW_TABLES) <= set(insp.get_table_names())

    columns = {c["name"] for c in insp.get_columns("line_snapshots")}
    assert columns == {
        "id", "game_id", "book_id", "source", "kind", "captured_at", "spread_home", "total",
        "spread_home_price", "spread_away_price", "over_price", "under_price", "ml_home",
        "ml_away", "created_at",
    }  # fmt: skip
    indexes = insp.get_indexes("line_snapshots")
    assert [i["column_names"] for i in indexes if "duplicates_constraint" not in i] == [
        ["game_id", "captured_at"]
    ]
    nulls_not_distinct = db_conn.execute(
        text(
            "SELECT i.indnullsnotdistinct FROM pg_index i JOIN pg_class c ON c.oid = i.indexrelid"
            " WHERE c.relname = 'uq_line_snapshots_game_id_book_id_source_kind_captured_at'"
        )
    ).scalar_one()
    assert nulls_not_distinct is True


def test_an_alias_is_unique_per_source(db_conn: Connection):
    first, second = _team(db_conn, "a"), _team(db_conn, "b")
    _alias(db_conn, first, "splash", "Ohio St")

    for team_id in (first, second):
        with pytest.raises(IntegrityError) as err, db_conn.begin_nested():
            _alias(db_conn, team_id, "splash", "Ohio St")
        assert isinstance(err.value.orig, errors.UniqueViolation)

    _alias(db_conn, second, "cfbd", "Ohio St")
    count = db_conn.execute(
        text("SELECT count(*) FROM team_aliases WHERE alias = 'Ohio St' AND team_id IN (:a, :b)"),
        {"a": first, "b": second},
    ).scalar_one()
    assert count == 2


def test_a_snapshot_needs_its_game_and_book(db_conn: Connection):
    game_id, book_id = _game(db_conn), _book(db_conn)
    base = {"source": LINE_SOURCE, "kind": "opening", "captured_at": None, "spread_home": -3}

    for bad, constraint in (
        ({"game_id": -1, "book_id": book_id}, "fk_line_snapshots_game_id_games"),
        ({"game_id": game_id, "book_id": -1}, "fk_line_snapshots_book_id_sportsbooks"),
    ):
        with pytest.raises(IntegrityError) as err, db_conn.begin_nested():
            _snapshots(db_conn, [{**base, **bad}])
        assert isinstance(err.value.orig, errors.ForeignKeyViolation)
        assert err.value.orig.diag.constraint_name == constraint


def test_a_live_snapshot_needs_its_capture_time(db_conn: Connection):
    row = {
        "game_id": _game(db_conn),
        "book_id": _book(db_conn),
        "source": LINE_SOURCE,
        "kind": "snapshot",
        "captured_at": None,
        "spread_home": -3,
    }
    with pytest.raises(IntegrityError) as err, db_conn.begin_nested():
        _snapshots(db_conn, [row])
    assert isinstance(err.value.orig, errors.CheckViolation)


def test_republishing_snapshots_is_a_no_op(db_conn: Connection):
    game_id, book_id = _game(db_conn), _book(db_conn)
    common = {"game_id": game_id, "book_id": book_id, "source": LINE_SOURCE}
    rows = [
        # A backfilled open has no capture time (D-031); the key still keeps it to one row.
        {**common, "kind": "opening", "captured_at": None, "spread_home": -3},
        {**common, "kind": "closing", "captured_at": None, "spread_home": -4},
        {**common, "kind": "snapshot", "captured_at": "2026-10-08T12:00Z", "spread_home": -3.5},
    ]
    assert _snapshots(db_conn, rows) == 3
    assert _snapshots(db_conn, rows) == 0
    assert _count(db_conn, game_id) == 3

    later = {**common, "kind": "snapshot", "captured_at": "2026-10-09T12:00Z", "spread_home": -4}
    assert _snapshots(db_conn, [later]) == 1
    assert _count(db_conn, game_id) == 4


def test_snapshots_cannot_be_updated_deleted_or_truncated(db_conn: Connection):
    game_id = _game(db_conn)
    row = {
        "game_id": game_id,
        "book_id": _book(db_conn),
        "source": LINE_SOURCE,
        "kind": "opening",
        "captured_at": None,
        "spread_home": -3,
    }
    _snapshots(db_conn, [row])

    for sql in (
        "UPDATE line_snapshots SET spread_home = -7 WHERE game_id = :g",
        "DELETE FROM line_snapshots WHERE game_id = :g",
        "TRUNCATE line_snapshots",
    ):
        with pytest.raises(DBAPIError) as err, db_conn.begin_nested():
            db_conn.execute(text(sql), {"g": game_id})
        assert isinstance(err.value.orig, errors.RaiseException)
        assert "append-only" in str(err.value.orig)

    spread = db_conn.execute(
        text("SELECT spread_home FROM line_snapshots WHERE game_id = :g"), {"g": game_id}
    ).scalar_one()
    assert spread == Decimal("-3.0")


def _fixture_game(conn: Connection, away: str, home: str) -> int:
    return conn.execute(
        text(
            "SELECT g.id FROM games g"
            " JOIN teams h ON h.id = g.home_team_id JOIN teams a ON a.id = g.away_team_id"
            " WHERE g.source = 'fixture' AND g.season = 2026 AND g.week = 6"
            " AND h.source = 'fixture' AND h.source_id = :home"
            " AND a.source = 'fixture' AND a.source_id = :away"
        ),
        {"home": home, "away": away},
    ).scalar_one()


def test_the_seeded_season_and_texas_oklahoma_lines(db_conn: Connection):
    current_week = db_conn.execute(
        text("SELECT current_week FROM seasons WHERE sport_id = 'cfb' AND year = 2026")
    ).scalar_one()
    assert current_week == 6

    # Texas @ Oklahoma: home Oklahoma, so Texas favored is a positive spread_home.
    game_id = _fixture_game(db_conn, away="tex", home="ou")
    spreads = db_conn.execute(
        text(
            "SELECT spread_home FROM line_snapshots"
            " WHERE game_id = :g AND kind = 'snapshot' ORDER BY captured_at"
        ),
        {"g": game_id},
    ).scalars()
    assert list(spreads) == [Decimal("7"), Decimal("6.5"), Decimal("6"), Decimal("6.5")]

    assert _count(db_conn, _fixture_game(db_conn, away="fur", home="clem")) == 0


def test_every_row_in_the_new_tables_is_fixture(db_conn: Connection):
    counts = {
        table: db_conn.execute(
            text(f"SELECT count(*), count(*) FILTER (WHERE source <> 'fixture') FROM {table}")
        ).one()
        for table in NEW_TABLES
    }
    assert {table: other for table, (_, other) in counts.items()} == dict.fromkeys(NEW_TABLES, 0)
    assert all(counts[t][0] > 0 for t in ("seasons", "sportsbooks", "line_snapshots"))
