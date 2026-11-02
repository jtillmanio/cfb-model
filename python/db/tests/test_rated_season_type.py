"""The season type of a rated week (TASK-047, D-150): `model_runs.season_type` and
`team_ratings.season_type`, so postseason week 1 is a week of its own.

The constraint tests write under a throwaway sport and roll back (db_conn). The round trip runs
the migrations in a scratch schema, so the seeded test DB is never dropped: it writes a run and a
rating at 0004, then checks the backfill and that every value survives down and up again."""

import uuid
from collections.abc import Iterator

import pytest
from alembic import command
from psycopg import errors
from sqlalchemy import Connection, inspect, make_url, text
from sqlalchemy.exc import IntegrityError

from db.migrate import alembic_config
from db.session import make_engine, sqlalchemy_url

SPORT = "pytest"
AS_OF = "2026-10-04T04:00Z"


def _version(conn: Connection) -> int:
    conn.execute(text("INSERT INTO sports (id, name) VALUES (:s, 'pytest')"), {"s": SPORT})
    return conn.execute(
        text(
            "INSERT INTO model_versions (sport_id, market, name, version, spec,"
            " spec_schema_version, created_by, status)"
            " VALUES (:sport, 'spread', 'm', 'v1', '{}', 1, 'user', 'dev') RETURNING id"
        ),
        {"sport": SPORT},
    ).scalar_one()


def _team(conn: Connection) -> int:
    return conn.execute(
        text(
            "INSERT INTO teams (sport_id, source, source_id, school)"
            " VALUES (:sport, 'pytest', 'osu', 'Ohio State') RETURNING id"
        ),
        {"sport": SPORT},
    ).scalar_one()


def _run(conn: Connection, version_id: int, season_type: str | None, run_type: str = "adhoc"):
    return conn.execute(
        text(
            "INSERT INTO model_runs (model_version_id, run_type, season, season_type, week,"
            " as_of, status) VALUES (:v, :t, 2026, :st, 1, :as_of, 'succeeded') RETURNING id"
        ),
        {"v": version_id, "t": run_type, "st": season_type, "as_of": AS_OF},
    ).scalar_one()


def _rating(conn: Connection, run_id: int, version_id: int, team_id: int, season_type: str):
    conn.execute(
        text(
            "INSERT INTO team_ratings (model_run_id, model_version_id, team_id, season,"
            " season_type, week, as_of, rating)"
            " VALUES (:r, :v, :t, 2026, :st, 1, :as_of, 7.5)"
        ),
        {"r": run_id, "v": version_id, "t": team_id, "st": season_type, "as_of": AS_OF},
    )


def _violation(err: pytest.ExceptionInfo[IntegrityError]) -> str:
    assert isinstance(err.value.orig, errors.CheckViolation | errors.NotNullViolation)
    return str(err.value.orig.diag.constraint_name or err.value.orig.diag.column_name)


# ─── The columns and the index ────────────────────────────────────────────────────────────────


def test_runs_and_ratings_carry_a_season_type(db_conn: Connection):
    insp = inspect(db_conn)
    runs = {c["name"]: c for c in insp.get_columns("model_runs")}
    ratings = {c["name"]: c for c in insp.get_columns("team_ratings")}
    assert runs["season_type"]["nullable"]  # a backtest spans seasons
    assert not ratings["season_type"]["nullable"]
    assert ratings["season_type"]["default"] is None  # every writer names it
    indexes = [i["column_names"] for i in insp.get_indexes("team_ratings")]
    assert ["model_version_id", "season", "season_type", "week"] in indexes
    assert ["model_version_id", "season", "week"] not in indexes


def test_a_live_run_must_name_its_season_type(db_conn: Connection):
    version_id = _version(db_conn)
    for run_type in ("adhoc", "scheduled"):
        with pytest.raises(IntegrityError) as err, db_conn.begin_nested():
            _run(db_conn, version_id, None, run_type)
        assert _violation(err) == "ck_model_runs_live_run_has_week"
    db_conn.execute(
        text(
            "INSERT INTO model_runs (model_version_id, run_type, status)"
            " VALUES (:v, 'backtest', 'succeeded')"
        ),
        {"v": version_id},
    )


def test_a_season_type_is_regular_or_postseason(db_conn: Connection):
    version_id = _version(db_conn)
    team_id = _team(db_conn)
    with pytest.raises(IntegrityError) as err, db_conn.begin_nested():
        _run(db_conn, version_id, "bowl")
    assert _violation(err) == "ck_model_runs_season_type"
    run_id = _run(db_conn, version_id, "postseason")
    for season_type, name in (("bowl", "ck_team_ratings_season_type"), (None, "season_type")):
        with pytest.raises(IntegrityError) as err, db_conn.begin_nested():
            _rating(db_conn, run_id, version_id, team_id, season_type)  # type: ignore[arg-type]
        assert _violation(err) == name


def test_regular_and_postseason_week_1_are_kept_apart(db_conn: Connection):
    version_id = _version(db_conn)
    team_id = _team(db_conn)
    for season_type in ("regular", "postseason"):
        run_id = _run(db_conn, version_id, season_type)
        _rating(db_conn, run_id, version_id, team_id, season_type)
    rows = db_conn.execute(
        text(
            "SELECT r.season_type, t.season_type AS rated FROM model_runs r"
            " JOIN team_ratings t ON t.model_run_id = r.id"
            " WHERE r.model_version_id = :v ORDER BY r.id"
        ),
        {"v": version_id},
    ).all()
    assert [tuple(r) for r in rows] == [("regular", "regular"), ("postseason", "postseason")]


# ─── The round trip ───────────────────────────────────────────────────────────────────────────


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


def _stored(url: str) -> list[tuple]:
    """Every run's and rating's values, with the season type where the column exists."""
    with make_engine(url).connect() as conn:
        assert conn.execute(text("SELECT current_schema()")).scalar_one().startswith("pytest_")
        columns = {c["name"] for c in inspect(conn).get_columns("team_ratings")}
        typed = "season_type" in columns
        runs = conn.execute(
            text(
                "SELECT id, run_type, season, week, as_of, status"
                + (", season_type" if typed else "")
                + " FROM model_runs ORDER BY id"
            )
        ).all()
        ratings = conn.execute(
            text(
                "SELECT model_run_id, team_id, season, week, rating"
                + (", season_type" if typed else "")
                + " FROM team_ratings ORDER BY model_run_id"
            )
        ).all()
    return [tuple(r) for r in runs] + [tuple(r) for r in ratings]


def test_the_migration_backfills_and_runs_up_down_up(scratch_url: str):
    cfg = alembic_config(scratch_url)
    command.upgrade(cfg, "0004")
    with make_engine(scratch_url).begin() as conn:
        version_id = _version(conn)
        team_id = _team(conn)
        run_id = conn.execute(
            text(
                "INSERT INTO model_runs (model_version_id, run_type, season, week, as_of, status)"
                " VALUES (:v, 'scheduled', 2026, 6, :as_of, 'succeeded') RETURNING id"
            ),
            {"v": version_id, "as_of": AS_OF},
        ).scalar_one()
        conn.execute(
            text(
                "INSERT INTO model_runs (model_version_id, run_type, status)"
                " VALUES (:v, 'backtest', 'succeeded')"
            ),
            {"v": version_id},
        )
        conn.execute(
            text(
                "INSERT INTO team_ratings (model_run_id, model_version_id, team_id, season, week,"
                " as_of, rating) VALUES (:r, :v, :t, 2026, 6, :as_of, 7.5)"
            ),
            {"r": run_id, "v": version_id, "t": team_id, "as_of": AS_OF},
        )
    before = _stored(scratch_url)

    command.upgrade(cfg, "head")
    backfilled = _stored(scratch_url)
    # The live run and its rating are regular weeks; the backtest has no week.
    assert [row[-1] for row in backfilled] == ["regular", None, "regular"]
    assert [row[:-1] for row in backfilled] == before

    command.downgrade(cfg, "0004")
    assert _stored(scratch_url) == before
    command.upgrade(cfg, "head")
    assert _stored(scratch_url) == backfilled


def test_the_downgrade_refuses_a_postseason_week(scratch_url: str):
    cfg = alembic_config(scratch_url)
    command.upgrade(cfg, "head")
    with make_engine(scratch_url).begin() as conn:
        _run(conn, _version(conn), "postseason")

    with pytest.raises(RuntimeError, match="postseason runs would read as regular week 1"):
        command.downgrade(cfg, "0004")
    with make_engine(scratch_url).connect() as conn:
        assert "season_type" in {c["name"] for c in inspect(conn).get_columns("model_runs")}
