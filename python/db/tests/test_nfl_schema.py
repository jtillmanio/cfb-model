"""The NFL as a sport (TASK-069, migration 0006): the `nfl` sports row, `nflverse` as a line
source, the seeded contest-slate NFL games (sample-data § 3), and the migration's round trip.

The seeded tests read the fixture `db:seed` loads. The round trip runs in a scratch schema, so the
seeded test DB is never migrated down."""

import uuid
from collections.abc import Iterator
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from alembic import command
from psycopg import errors
from sqlalchemy import Connection, make_url, text
from sqlalchemy.exc import IntegrityError

from db.migrate import alembic_config, apply_views
from db.session import make_engine, sqlalchemy_url

# ─── The seeded NFL games (AC-5) ───────────────────────────────────────────────────────────────

SLATE = text(
    "SELECT g.source_id, a.abbreviation AS away, h.abbreviation AS home, g.season, g.week,"
    " g.season_type, g.kickoff_at, g.status, m.current_spread_home"
    " FROM games g JOIN teams a ON a.id = g.away_team_id JOIN teams h ON h.id = g.home_team_id"
    " JOIN game_market m ON m.game_id = g.id"
    " WHERE g.sport_id = 'nfl' AND g.source = 'fixture' ORDER BY g.kickoff_at, g.source_id"
)


def test_the_nfl_is_a_sport(db_conn: Connection):
    name = db_conn.execute(text("SELECT name FROM sports WHERE id = 'nfl'")).scalar_one()
    assert name == "NFL"


def test_the_seed_has_the_contest_slates_nfl_teams(db_conn: Connection):
    teams = db_conn.execute(
        text(
            "SELECT abbreviation, school FROM teams WHERE sport_id = 'nfl' AND source = 'fixture'"
            " ORDER BY abbreviation"
        )
    ).all()
    assert [tuple(t) for t in teams] == [
        ("BAL", "Baltimore"),
        ("BUF", "Buffalo"),
        ("HOU", "Houston"),
        ("JAX", "Jacksonville"),
        ("KC", "Kansas City"),
        ("NYG", "NY Giants"),
        ("NYJ", "NY Jets"),
        ("PHI", "Philadelphia"),
    ]


def test_the_seed_has_the_four_week_6_nfl_games_with_their_market_lines(db_conn: Connection):
    def sunday(hour: int, minute: int = 0) -> datetime:  # Sun 2026-10-11, EDT is UTC-4
        return datetime(2026, 10, 11, hour + 4, minute, tzinfo=UTC)

    games = [tuple(r[1:]) for r in db_conn.execute(SLATE)]
    assert games == [
        ("BUF", "NYJ", 2026, 6, "regular", sunday(13), "scheduled", Decimal("4.5")),
        ("HOU", "JAX", 2026, 6, "regular", sunday(13), "scheduled", Decimal("1.5")),
        ("KC", "BAL", 2026, 6, "regular", sunday(16, 25), "scheduled", Decimal("-2.5")),
        # 8:20 PM EDT is 00:20 UTC on Monday.
        ("NYG", "PHI", 2026, 6, "regular", datetime(2026, 10, 12, 0, 20, tzinfo=UTC),
         "scheduled", Decimal("-7.0")),
    ]  # fmt: skip


def test_an_nflverse_line_is_accepted_and_an_unknown_source_refused(db_conn: Connection):
    game_id, book_id = db_conn.execute(
        text(
            "SELECT g.id, b.id FROM games g, sportsbooks b"
            " WHERE g.sport_id = 'nfl' AND g.source = 'fixture' AND b.source = 'fixture'"
            " ORDER BY g.id LIMIT 1"
        )
    ).one()
    insert = text(
        "INSERT INTO line_snapshots (game_id, book_id, source, kind, captured_at, spread_home)"
        " VALUES (:g, :b, :source, 'snapshot', '2026-10-10T12:00Z', 4.5)"
    )
    db_conn.execute(insert, {"g": game_id, "b": book_id, "source": "nflverse"})
    with pytest.raises(IntegrityError) as err, db_conn.begin_nested():
        db_conn.execute(insert, {"g": game_id, "b": book_id, "source": "espn"})
    assert isinstance(err.value.orig, errors.CheckViolation)
    assert err.value.orig.diag.constraint_name == "ck_line_snapshots_source"


# ─── The round trip (AC-6) ─────────────────────────────────────────────────────────────────────


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


def _state(url: str) -> tuple[list[tuple], str]:
    """The sports rows and the line source CHECK, on a scratch schema only."""
    with make_engine(url).connect() as conn:
        assert conn.execute(text("SELECT current_schema()")).scalar_one().startswith("pytest_")
        sports = [tuple(r) for r in conn.execute(text("SELECT id, name FROM sports ORDER BY id"))]
        check = conn.execute(
            text(
                "SELECT pg_get_constraintdef(oid) FROM pg_constraint"
                " WHERE conname = 'ck_line_snapshots_source'"
                " AND connamespace = current_schema()::regnamespace"
            )
        ).scalar_one()
    return sports, check


def test_the_migration_runs_up_down_up(scratch_url: str):
    cfg = alembic_config(scratch_url)
    command.upgrade(cfg, "0005")
    before = _state(scratch_url)
    assert before[0] == [("cfb", "College football")]
    assert "nflverse" not in before[1]

    command.upgrade(cfg, "head")
    apply_views(scratch_url)
    after = _state(scratch_url)
    assert after[0] == [("cfb", "College football"), ("nfl", "NFL")]
    assert "'nflverse'" in after[1]

    command.downgrade(cfg, "0005")
    assert _state(scratch_url) == before
    command.upgrade(cfg, "head")
    assert _state(scratch_url) == after


def test_the_downgrade_refuses_while_nfl_rows_exist(scratch_url: str):
    cfg = alembic_config(scratch_url)
    command.upgrade(cfg, "head")
    with make_engine(scratch_url).begin() as conn:
        assert conn.execute(text("SELECT current_schema()")).scalar_one().startswith("pytest_")
        conn.execute(
            text(
                "INSERT INTO teams (sport_id, source, source_id, school)"
                " VALUES ('nfl', 'nflverse', 'BUF', 'Buffalo')"
            )
        )

    with pytest.raises(RuntimeError, match="1 NFL teams, games or nflverse line snapshots"):
        command.downgrade(cfg, "0005")
    assert ("nfl", "NFL") in _state(scratch_url)[0]
