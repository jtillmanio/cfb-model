"""The contest tables (TASK-067, migration 0007): users, contests, contest_lines, contest_entries
and contest_standings, their keys and append-only rules, and the seeded Splash work league.

The constraint tests write rows under the throwaway sport in `model_rows` and roll back (db_conn).
The seed tests read the fixture CI loads before pytest (`pnpm db:seed`, D-089). The round trip
runs the migrations in a scratch schema, so the seeded test DB is never migrated down."""

from __future__ import annotations

import importlib.util
import json
import uuid
from collections import Counter
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import model_rows as m
import pytest
from alembic import command
from psycopg import errors
from sqlalchemy import Connection, inspect, make_url, text
from sqlalchemy.exc import DBAPIError

from db.config import repo_root
from db.migrate import alembic_config, apply_views
from db.session import make_engine, sqlalchemy_url
from engine.core.contest_rules import SPLASH_PRESET, ContestRules

SEEDS = repo_root() / "python" / "db" / "seeds" / "fixture"
TABLES = {"users", "contests", "contest_lines", "contest_entries", "contest_standings"}


# ─── Constructed rows ─────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Rows:
    user_id: int
    contest_id: int
    game_id: int
    line_id: int


def _game(conn: Connection) -> int:
    tag = uuid.uuid4().hex[:8]
    home, away = m.team(conn, f"home-{tag}"), m.team(conn, f"away-{tag}")
    return m.game(conn, home, away, m.utc(2030, 9, 7, 16), week=1, status="scheduled")


def _rows(conn: Connection) -> Rows:
    m.sport(conn)
    user_id = m.user(conn)
    contest_id = m.contest(conn, user_id)
    game_id = _game(conn)
    line_id = m.contest_line(conn, contest_id, game_id, -3.5, m.utc(2030, 9, 4, 1))
    return Rows(user_id, contest_id, game_id, line_id)


def _entry(conn: Connection, rows: Rows, **override: Any) -> int:
    values: dict[str, Any] = {
        "user_id": rows.user_id,
        "contest_id": rows.contest_id,
        "game_id": rows.game_id,
        "contest_line_id": rows.line_id,
        "side": "home",
        **override,
    }
    return conn.execute(
        text(
            f"INSERT INTO contest_entries ({', '.join(values)})"
            f" VALUES ({', '.join(':' + c for c in values)}) RETURNING id"
        ),
        values,
    ).scalar_one()


def _standing(conn: Connection, contest_id: int, **override: Any) -> int:
    values: dict[str, Any] = {
        "contest_id": contest_id,
        "period": 1,
        "position": 3,
        "field_size": 14,
        "points_behind_leader": 1,
        **override,
    }
    return conn.execute(
        text(
            f"INSERT INTO contest_standings ({', '.join(values)})"
            f" VALUES ({', '.join(':' + c for c in values)}) RETURNING id"
        ),
        values,
    ).scalar_one()


def _refused(conn: Connection, sql: str, params: dict[str, Any], error: type) -> DBAPIError:
    with pytest.raises(DBAPIError) as err, conn.begin_nested():
        conn.execute(text(sql), params)
    assert isinstance(err.value.orig, error), sql
    return err.value


# ─── AC-1: the tables and their keys ──────────────────────────────────────────────────────────


def _fks(conn: Connection, table: str) -> set[tuple[tuple[str, ...], str, tuple[str, ...]]]:
    return {
        (tuple(fk["constrained_columns"]), fk["referred_table"], tuple(fk["referred_columns"]))
        for fk in inspect(conn).get_foreign_keys(table)
    }


def test_the_contest_tables_have_their_columns(db_conn: Connection):
    insp = inspect(db_conn)
    assert set(insp.get_table_names()) >= TABLES
    columns = {t: {c["name"] for c in insp.get_columns(t)} for t in TABLES}
    assert columns == {
        "users": {"id", "github_id", "email", "name", "created_at"},
        "contests": {
            "id", "user_id", "name", "platform", "season", "rules", "created_at", "deleted_at",
        },
        "contest_lines": {
            "id", "contest_id", "period", "game_id", "spread_home", "captured_at", "source",
            "created_at",
        },
        "contest_entries": {
            "id", "user_id", "contest_id", "game_id", "contest_line_id", "side", "confidence",
            "created_at", "deleted_at",
        },
        "contest_standings": {
            "id", "contest_id", "period", "position", "field_size", "points_behind_leader",
            "note", "entered_at",
        },
    }  # fmt: skip


def test_an_entry_is_held_to_its_contests_line_and_the_users_contest(db_conn: Connection):
    """Settled at the plan gate: the entry carries `game_id`, so its line must be its contest's
    line for its game, and its contest the user's."""
    assert _fks(db_conn, "contest_entries") == {
        (("contest_line_id", "contest_id", "game_id"), "contest_lines",
         ("id", "contest_id", "game_id")),
        (("contest_id", "user_id"), "contests", ("id", "user_id")),
        (("user_id",), "users", ("id",)),
    }  # fmt: skip
    rows = _rows(db_conn)
    other_game = _game(db_conn)
    other_contest = m.contest(db_conn, rows.user_id, "other league")
    other_user = m.user(db_conn)
    for override in (
        {"game_id": other_game},  # the line is another game's
        {"contest_id": other_contest},  # the line is another contest's
        {"user_id": other_user},  # the contest is another user's
    ):
        with pytest.raises(DBAPIError) as err, db_conn.begin_nested():
            _entry(db_conn, rows, **override)
        assert isinstance(err.value.orig, errors.ForeignKeyViolation), override


def test_a_users_github_id_is_unique(db_conn: Connection):
    db_conn.execute(text("INSERT INTO users (github_id) VALUES (99000000001)"))
    _refused(
        db_conn, "INSERT INTO users (github_id) VALUES (99000000001)", {}, errors.UniqueViolation
    )


def test_a_contest_line_source_outside_its_values_is_refused(db_conn: Connection):
    rows = _rows(db_conn)
    sql = (
        "INSERT INTO contest_lines (contest_id, period, game_id, spread_home, captured_at, source)"
        " VALUES (:c, 1, :g, -3.5, :at, :source)"
    )
    for i, source in enumerate(("paste", "manual", "fixture")):
        db_conn.execute(
            text(sql),
            {"c": rows.contest_id, "g": rows.game_id, "at": m.utc(2030, 9, 5, i), "source": source},
        )
    err = _refused(
        db_conn,
        sql,
        {"c": rows.contest_id, "g": rows.game_id, "at": m.utc(2030, 9, 6), "source": "splash"},
        errors.CheckViolation,
    )
    assert isinstance(err.orig, errors.Error)
    assert err.orig.diag.constraint_name == "ck_contest_lines_source"


def test_a_period_must_be_positive(db_conn: Connection):
    """Schema review R1: a contest week counts from 1, on lines and standings alike."""
    rows = _rows(db_conn)
    for period in (0, -1):
        with pytest.raises(DBAPIError) as err, db_conn.begin_nested():
            m.contest_line(db_conn, rows.contest_id, rows.game_id, -3.5, m.utc(2030, 9, 6),
                           period=period)  # fmt: skip
        assert isinstance(err.value.orig, errors.CheckViolation)
        assert err.value.orig.diag.constraint_name == "ck_contest_lines_period_positive"
        with pytest.raises(DBAPIError) as err, db_conn.begin_nested():
            _standing(db_conn, rows.contest_id, period=period)
        assert isinstance(err.value.orig, errors.CheckViolation)
        assert err.value.orig.diag.constraint_name == "ck_contest_standings_period_positive"


def test_a_standing_inside_its_field_is_stored_and_outside_refused(db_conn: Connection):
    contest_id = _rows(db_conn).contest_id
    _standing(db_conn, contest_id)
    for override in (
        {"position": 15},
        {"position": 0},
        {"field_size": 0, "position": 0},
        {"points_behind_leader": -1},
    ):
        with pytest.raises(DBAPIError) as err, db_conn.begin_nested():
            _standing(db_conn, contest_id, **override)
        assert isinstance(err.value.orig, errors.CheckViolation), override


@pytest.fixture
def scratch_url(test_db_url: str) -> Iterator[str]:
    """The test DB with search_path set to a new, empty schema, dropped afterwards."""
    schema = f"pytest_{uuid.uuid4().hex[:12]}"
    admin = make_engine(test_db_url)
    with admin.begin() as conn:
        conn.execute(text(f'CREATE SCHEMA "{schema}"'))
    url = make_url(sqlalchemy_url(test_db_url)).update_query_dict(
        {"options": f"-csearch_path={schema}"}
    )
    try:
        yield url.render_as_string(hide_password=False)
    finally:
        with admin.begin() as conn:
            conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))


def _scratch(url: str) -> tuple[set[str], dict[str, bool], list[tuple[Any, ...]]]:
    """The scratch schema's contest tables, picks' columns (name: nullable) and its pick rows."""
    with make_engine(url).connect() as conn:
        schema = conn.execute(text("SELECT current_schema()")).scalar_one()
        assert schema.startswith("pytest_")  # never public
        insp = inspect(conn)
        tables = TABLES & set(insp.get_table_names(schema=schema))
        picks = {c["name"]: c["nullable"] for c in insp.get_columns("picks", schema=schema)}
        rows = [
            tuple(r)
            for r in conn.execute(
                text(
                    "SELECT id, game_id, line_snapshot_id, side, line, price, tier, stake_units"
                    " FROM picks ORDER BY id"
                )
            )
        ]
    return tables, picks, rows


def _market_pick(url: str) -> None:
    """One market pick in the scratch schema, so the round trip can check it survives."""
    with make_engine(url).begin() as conn:
        assert conn.execute(text("SELECT current_schema()")).scalar_one().startswith("pytest_")
        m.sport(conn)
        game_id = _game(conn)
        version_id = m.version(conn)
        run_id = m.run(conn, version_id, 1, m.utc(2030, 9, 1, 10))
        snapshot = m.line(conn, game_id, m.book(conn), m.utc(2030, 9, 1, 10), -2.5)
        m.pick(conn, m.prediction(conn, run_id, version_id, game_id), version_id, game_id,
               snapshot, m.utc(2030, 9, 1, 11), side="home", line=-2.5)  # fmt: skip


def test_migration_0007_round_trips(scratch_url: str):
    cfg = alembic_config(scratch_url)
    command.upgrade(cfg, "0006")
    _market_pick(scratch_url)
    before = _scratch(scratch_url)
    assert before[0] == set()
    assert "contest_line_id" not in before[1]
    assert (before[1]["line_snapshot_id"], before[1]["price"]) == (False, False)
    assert len(before[2]) == 1

    command.upgrade(cfg, "head")
    apply_views(scratch_url)
    after = _scratch(scratch_url)
    assert after[0] == TABLES
    assert after[1]["contest_line_id"] and after[1]["line_snapshot_id"] and after[1]["price"]
    assert after[2] == before[2]

    command.downgrade(cfg, "0006")
    assert _scratch(scratch_url) == before
    command.upgrade(cfg, "head")
    apply_views(scratch_url)
    assert _scratch(scratch_url) == after


def test_the_downgrade_refuses_while_contest_rows_exist(scratch_url: str):
    cfg = alembic_config(scratch_url)
    command.upgrade(cfg, "head")
    with make_engine(scratch_url).begin() as conn:
        assert conn.execute(text("SELECT current_schema()")).scalar_one().startswith("pytest_")
        conn.execute(text("INSERT INTO users (github_id) VALUES (4242)"))

    with pytest.raises(RuntimeError, match="1 users, contests or contest picks exist"):
        command.downgrade(cfg, "0006")
    assert _scratch(scratch_url)[0] == TABLES


# ─── AC-2: append-only lines and standings; soft-deleted entries ──────────────────────────────


@pytest.mark.parametrize("table", ["contest_lines", "contest_standings"])
def test_contest_lines_and_standings_refuse_update_delete_and_truncate(
    db_conn: Connection, table: str
):
    rows = _rows(db_conn)
    key = rows.line_id if table == "contest_lines" else _standing(db_conn, rows.contest_id)
    column = "period" if table == "contest_lines" else "position"
    for sql in (
        f"UPDATE {table} SET {column} = 2 WHERE id = :k",
        f"DELETE FROM {table} WHERE id = :k",
        f"TRUNCATE {table} CASCADE",
    ):
        err = _refused(db_conn, sql, {"k": key}, errors.RaiseException)
        assert f"{table} is append-only" in str(err.orig), sql

    stored = db_conn.execute(text(f"SELECT {column} FROM {table} WHERE id = :k"), {"k": key})
    assert stored.scalar_one() in (1, 3)


def test_entries_cannot_be_hard_deleted_or_truncated(db_conn: Connection):
    rows = _rows(db_conn)
    entry_id = _entry(db_conn, rows)
    for sql in ("DELETE FROM contest_entries WHERE id = :e", "TRUNCATE contest_entries"):
        err = _refused(db_conn, sql, {"e": entry_id}, errors.RaiseException)
        assert "contest_entries can't be deleted" in str(err.orig), sql
    assert db_conn.execute(
        text("SELECT count(*) FROM contest_entries WHERE id = :e"), {"e": entry_id}
    ).scalar_one() == 1


def test_an_entry_update_may_only_soft_delete_it_once(db_conn: Connection):
    """The line you got never changes: an UPDATE may only set `deleted_at`, and only once."""
    rows = _rows(db_conn)
    entry_id = _entry(db_conn, rows)
    moved = m.contest_line(db_conn, rows.contest_id, rows.game_id, -4.5, m.utc(2030, 9, 5, 1))
    for sql in (
        "UPDATE contest_entries SET side = 'away' WHERE id = :e",
        f"UPDATE contest_entries SET contest_line_id = {moved} WHERE id = :e",
        "UPDATE contest_entries SET side = 'away', deleted_at = now() WHERE id = :e",
    ):
        err = _refused(db_conn, sql, {"e": entry_id}, errors.RaiseException)
        assert "only setting deleted_at" in str(err.orig), sql

    db_conn.execute(
        text("UPDATE contest_entries SET deleted_at = :at WHERE id = :e"),
        {"e": entry_id, "at": m.utc(2030, 9, 5, 2)},
    )
    for sql in (
        "UPDATE contest_entries SET deleted_at = now() WHERE id = :e",  # again
        "UPDATE contest_entries SET deleted_at = NULL WHERE id = :e",  # undone
    ):
        _refused(db_conn, sql, {"e": entry_id}, errors.RaiseException)
    stored = db_conn.execute(
        text("SELECT side, contest_line_id, deleted_at FROM contest_entries WHERE id = :e"),
        {"e": entry_id},
    ).one()
    assert tuple(stored) == ("home", rows.line_id, m.utc(2030, 9, 5, 2))


def test_two_live_entries_for_one_game_are_refused(db_conn: Connection):
    rows = _rows(db_conn)
    _entry(db_conn, rows)
    with pytest.raises(DBAPIError) as err, db_conn.begin_nested():
        _entry(db_conn, rows, side="away")
    assert isinstance(err.value.orig, errors.UniqueViolation)
    assert err.value.orig.diag.constraint_name == "uq_contest_entries_live"


def test_a_soft_deleted_entry_can_be_re_added(db_conn: Connection):
    """D-033: remove a pick and make it again, at a new line."""
    rows = _rows(db_conn)
    first = _entry(db_conn, rows)
    db_conn.execute(
        text("UPDATE contest_entries SET deleted_at = now() WHERE id = :e"), {"e": first}
    )
    moved = m.contest_line(db_conn, rows.contest_id, rows.game_id, -4.5, m.utc(2030, 9, 5, 1))
    second = _entry(db_conn, rows, contest_line_id=moved, side="away")
    live = db_conn.execute(
        text(
            "SELECT id FROM contest_entries WHERE contest_id = :c AND game_id = :g"
            " AND deleted_at IS NULL"
        ),
        {"c": rows.contest_id, "g": rows.game_id},
    ).scalars()
    assert list(live) == [second]


# ─── AC-5: the seeded Splash work league ──────────────────────────────────────────────────────

SEEDED_CONTEST = (
    "SELECT c.id FROM contests c JOIN users u ON u.id = c.user_id"
    " WHERE u.github_id = 4242 AND c.name = 'Splash work league' AND c.deleted_at IS NULL"
)


def _et(month: int, day: int, hour: int, minute: int) -> datetime:
    """An October 2026 Eastern time (EDT, UTC−4) as UTC."""
    return datetime(2026, month, day, hour, minute, tzinfo=UTC) + timedelta(hours=4)


THU_914 = _et(10, 8, 21, 14)  # the OU +7 entry, Thu 9:14 PM ET

# contest-data.js's paste, `spread_home` from the home side (its `hl`).
WEEK6_LINES = {
    "2026-w6-unlv-bsu": Decimal("-10.0"),
    "2026-w6-pur-osu": Decimal("-27.0"),
    "2026-w6-miss-lsu": Decimal("-3.0"),
    "2026-w6-nd-stan": Decimal("17.5"),
    "2026-w6-tex-ou": Decimal("7.0"),
    "2026-w6-colo-byu": Decimal("-5.5"),
    "2026-w6-buf-nyj": Decimal("3.0"),
    "2026-w6-hou-jax": Decimal("1.0"),
    "2026-w6-kc-bal": Decimal("-2.5"),
    "2026-w6-nyg-phi": Decimal("-6.0"),
}

ENTRIES = """
    SELECT l.period, g.source_id AS game, g.sport_id, g.status, g.kickoff_at,
           g.home_points - g.away_points AS margin, e.side, e.created_at, e.deleted_at,
           l.spread_home, l.captured_at, e.game_id = l.game_id AS on_its_game
    FROM contest_entries e
    JOIN contest_lines l ON l.id = e.contest_line_id
    JOIN games g ON g.id = e.game_id
    WHERE e.contest_id = ({contest})
    ORDER BY l.period, e.created_at, e.id
"""


def _entries(conn: Connection) -> list[Any]:
    return list(conn.execute(text(ENTRIES.format(contest=SEEDED_CONTEST))))


def test_the_seed_has_the_allowlisted_user(db_conn: Connection):
    users = db_conn.execute(text("SELECT github_id FROM users WHERE github_id = 4242")).all()
    assert len(users) == 1


def test_the_seed_has_the_splash_work_league(db_conn: Connection):
    row = db_conn.execute(
        text(f"SELECT platform, season, rules FROM contests WHERE id = ({SEEDED_CONTEST})")
    ).one()
    assert (row.platform, row.season) == ("splash", 2026)
    assert ContestRules.model_validate(row.rules) == SPLASH_PRESET


def test_the_seed_has_the_week_6_contest_lines(db_conn: Connection):
    lines = db_conn.execute(
        text(
            "SELECT g.source_id, l.spread_home, l.captured_at, l.source FROM contest_lines l"
            " JOIN games g ON g.id = l.game_id"
            f" WHERE l.contest_id = ({SEEDED_CONTEST}) AND l.period = 6"
        )
    ).all()
    assert {r.source_id: r.spread_home for r in lines} == WEEK6_LINES
    assert len(lines) == 10
    for r in lines:
        assert r.source == "fixture", r.source_id
        # Captured Thu 2026-10-08, before the first entry at 9:14 PM ET.
        assert _et(10, 8, 0, 0) <= r.captured_at < THU_914, r.source_id


def test_the_seed_has_the_week_6_entries(db_conn: Connection):
    week6 = [r for r in _entries(db_conn) if r.period == 6]
    got = [(r.game, r.side, r.spread_home, r.created_at, r.deleted_at) for r in week6]
    assert got == [
        ("2026-w6-tex-ou", "home", Decimal("7.0"), THU_914, None),  # OU +7
        ("2026-w6-buf-nyj", "away", Decimal("3.0"), _et(10, 8, 21, 20), None),  # BUF −3
    ]
    assert all(r.on_its_game and r.captured_at < r.created_at < r.kickoff_at for r in week6)


def test_the_weeks_1_to_5_entries_grade_12_8(db_conn: Connection):
    earlier = [r for r in _entries(db_conn) if r.period <= 5]
    graded: Counter[tuple[int, str]] = Counter()
    for r in earlier:
        assert r.sport_id == "cfb" and r.status == "final" and r.deleted_at is None, r.game
        assert r.on_its_game and r.captured_at < r.created_at < r.kickoff_at, r.game
        cover = (r.margin + r.spread_home) * (1 if r.side == "home" else -1)
        graded[(r.period, "W" if cover > 0 else "L" if cover < 0 else "P")] += 1
    by_week = {w: (graded[(w, "W")], graded[(w, "L")], graded[(w, "P")]) for w in range(1, 6)}
    assert by_week == {1: (3, 1, 0), 2: (2, 2, 0), 3: (3, 1, 0), 4: (1, 3, 0), 5: (3, 1, 0)}
    assert sum(graded[(w, "W")] for w in range(1, 6)) == 12

    slates = db_conn.execute(
        text(
            "SELECT period, count(*) FROM contest_lines"
            f" WHERE contest_id = ({SEEDED_CONTEST}) AND period <= 5 GROUP BY period"
        )
    ).all()
    assert dict(slates) == dict.fromkeys(range(1, 6), 5)


def test_the_seed_has_the_standing_after_week_5(db_conn: Connection):
    row = db_conn.execute(
        text(
            "SELECT period, position, field_size, points_behind_leader FROM contest_standings"
            f" WHERE contest_id = ({SEEDED_CONTEST})"
        )
    ).one()
    assert tuple(row) == (5, 3, 14, Decimal("1.0"))


def test_contest_history_json_is_what_the_generator_writes():
    spec = importlib.util.spec_from_file_location("generate_contest", SEEDS / "generate_contest.py")
    assert spec is not None and spec.loader is not None
    generator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(generator)

    assert generator.build() == json.loads((SEEDS / "contest_history.json").read_text("utf-8"))
