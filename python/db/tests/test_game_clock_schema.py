"""A live game's period and clock (TASK-074 AC-2, migration 0009): nullable columns on `games`, a
CHECK that keeps them NULL unless the game is in progress, and the migration's round trip with
row values. The round trip runs in a scratch schema, so the seeded test DB is never migrated
down."""

import uuid
from collections.abc import Iterator

import pytest
from alembic import command
from psycopg import errors
from sqlalchemy import Connection, make_url, text
from sqlalchemy.exc import IntegrityError

from db.migrate import alembic_config, apply_views
from db.session import make_engine, sqlalchemy_url

COLUMNS = text(
    "SELECT column_name, data_type, is_nullable FROM information_schema.columns"
    " WHERE table_schema = current_schema() AND table_name = 'games'"
    " AND column_name IN ('period', 'clock') ORDER BY column_name"
)


def _a_game(conn: Connection) -> int:
    return conn.execute(
        text("SELECT id FROM games WHERE sport_id = 'cfb' ORDER BY id LIMIT 1")
    ).scalar_one()


def test_games_have_nullable_period_and_clock(db_conn: Connection):
    assert [tuple(r) for r in db_conn.execute(COLUMNS)] == [
        ("clock", "text", "YES"),
        ("period", "smallint", "YES"),
    ]


def test_a_game_in_progress_takes_a_clock(db_conn: Connection):
    game = _a_game(db_conn)
    db_conn.execute(
        text(
            "UPDATE games SET status = 'in_progress', home_points = 3, away_points = 7,"
            " period = 3, clock = '09:12' WHERE id = :id"
        ),
        {"id": game},
    )
    row = db_conn.execute(
        text("SELECT status, period, clock FROM games WHERE id = :id"), {"id": game}
    ).one()
    assert tuple(row) == ("in_progress", 3, "09:12")


@pytest.mark.parametrize(
    ("status", "period", "clock"),
    [("final", 4, "00:00"), ("final", None, "00:00"), ("scheduled", 1, None)],
)
def test_a_game_not_in_progress_refuses_a_clock(
    db_conn: Connection, status: str, period: int | None, clock: str | None
):
    game = _a_game(db_conn)
    with pytest.raises(IntegrityError) as err, db_conn.begin_nested():
        db_conn.execute(
            text(
                "UPDATE games SET status = :status, home_points = 3, away_points = 7,"
                " period = :period, clock = :clock WHERE id = :id"
            ),
            {"id": game, "status": status, "period": period, "clock": clock},
        )
    assert isinstance(err.value.orig, errors.CheckViolation)
    assert err.value.orig.diag.constraint_name == "ck_games_clock_only_in_progress"


# ─── The round trip ────────────────────────────────────────────────────────────────────────────


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


GAME = (
    "SELECT source_id, status, home_points, away_points{clock} FROM games ORDER BY source_id"
)


def _state(url: str, clock: bool) -> tuple[list[tuple], list[tuple]]:
    """The game rows and the period/clock columns, on a scratch schema only."""
    with make_engine(url).connect() as conn:
        assert conn.execute(text("SELECT current_schema()")).scalar_one().startswith("pytest_")
        columns = [tuple(r) for r in conn.execute(COLUMNS)]
        sql = GAME.format(clock=", period, clock" if clock else "")
        games = [tuple(r) for r in conn.execute(text(sql))]
    return columns, games


def _seed(url: str) -> None:
    """Two teams and two games, written at 0008 (before the columns exist)."""
    with make_engine(url).begin() as conn:
        assert conn.execute(text("SELECT current_schema()")).scalar_one().startswith("pytest_")
        teams = [
            conn.execute(
                text(
                    "INSERT INTO teams (sport_id, source, source_id, school)"
                    " VALUES ('cfb', 'cfbd', :id, :school) RETURNING id"
                ),
                {"id": source_id, "school": school},
            ).scalar_one()
            for source_id, school in (("194", "Ohio State"), ("2509", "Purdue"))
        ]
        games = (("1", "scheduled", None, None), ("2", "final", 24, 3))
        for source_id, status, home, away in games:
            conn.execute(
                text(
                    "INSERT INTO games (sport_id, source, source_id, season, week, season_type,"
                    " game_date, neutral_site, conference_game, home_team_id, away_team_id,"
                    " home_points, away_points, status)"
                    " VALUES ('cfb', 'cfbd', :id, 2026, 6, 'regular', '2026-10-10', false, true,"
                    " :home_team, :away_team, :home, :away, :status)"
                ),
                {
                    "id": source_id,
                    "home_team": teams[0],
                    "away_team": teams[1],
                    "home": home,
                    "away": away,
                    "status": status,
                },
            )


def test_the_migration_runs_up_down_up(scratch_url: str):
    cfg = alembic_config(scratch_url)
    command.upgrade(cfg, "0008")
    _seed(scratch_url)
    before = _state(scratch_url, clock=False)
    assert before == ([], [("1", "scheduled", None, None), ("2", "final", 24, 3)])

    command.upgrade(cfg, "head")
    apply_views(scratch_url)
    columns, games = _state(scratch_url, clock=True)
    assert columns == [("clock", "text", "YES"), ("period", "smallint", "YES")]
    assert games == [("1", "scheduled", None, None, None, None), ("2", "final", 24, 3, None, None)]
    with make_engine(scratch_url).begin() as conn:
        conn.execute(
            text(
                "UPDATE games SET status = 'in_progress', home_points = 7, away_points = 0,"
                " period = 2, clock = '02:41' WHERE source_id = '1'"
            )
        )

    command.downgrade(cfg, "0008")
    assert _state(scratch_url, clock=False) == (
        [],
        [("1", "in_progress", 7, 0), ("2", "final", 24, 3)],
    )
    command.upgrade(cfg, "head")
    assert _state(scratch_url, clock=True)[1] == [
        ("1", "in_progress", 7, 0, None, None),
        ("2", "final", 24, 3, None, None),
    ]
