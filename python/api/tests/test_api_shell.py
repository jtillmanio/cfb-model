"""The app shell's block on every screen endpoint (TASK-053): season and coming week, the shown
version and its record, lines updated and stale, the week's picks.

The route tests read the fixture CI loads before pytest (`pnpm db:seed`, D-089) at a fixture time
(FIXTURE_NOW, honored with APP_ENV=test). The `load` tests build rows under model_rows' throwaway
sport inside db_conn's rolled-back transaction."""

from __future__ import annotations

import threading
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import model_rows as m  # pyright: ignore[reportMissingImports]  (on sys.path via conftest)
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Connection, event, text

from api import clock, shell, wave

MakeToken = Callable[..., str]

SLATE_NOW = "2026-10-10T14:15:00-04:00"  # Sat 2:15 PM ET, the slate's fixture time
OFFSEASON_NOW = "2027-02-08T06:00:00-05:00"  # Mon 6:00 AM ET, no game still to come

SEEDED_V1 = (
    "SELECT id FROM model_versions WHERE sport_id = 'cfb' AND market = 'spread'"
    " AND name = 'power' AND version = 'v1.0' AND deleted_at IS NULL"
)


def _get_shell(
    client: TestClient, make_token: MakeToken, monkeypatch: pytest.MonkeyPatch, at: str
) -> dict[str, Any]:
    monkeypatch.setenv("FIXTURE_NOW", at)
    response = client.get("/api/py/teams", headers={"Authorization": f"Bearer {make_token()}"})
    assert response.status_code == 200, response.text
    return response.json()["shell"]


# AC-1


def test_the_slate_shell_on_the_fixture(
    client: TestClient, make_token: MakeToken, monkeypatch: pytest.MonkeyPatch, db_conn: Connection
):
    """Week 6 of 2026, v1.0's record through week 6 (32-24-1, Tulane @ Memphis won), the Sat
    9:00 AM ET pull 5 h 15 m old, so not stale, and the 9 week-6 picks."""
    body = _get_shell(client, make_token, monkeypatch, SLATE_NOW)

    expected = db_conn.execute(
        text(
            "SELECT wins, losses, pushes, win_pct, units, avg_clv FROM model_record"
            f" WHERE model_version_id = ({SEEDED_V1}) AND season = 2026"
            " AND breakdown = 'to_date' AND season_type = 'regular' AND week = 6"
        )
    ).one()
    assert (expected.wins, expected.losses, expected.pushes) == (32, 24, 1)

    assert {k: body[k] for k in ("season", "season_type", "week")} == {
        "season": 2026,
        "season_type": "regular",
        "week": 6,
    }
    assert body["model"] == {"name": "power", "version": "v1.0"}
    record = body["record"]
    assert (record["wins"], record["losses"], record["pushes"]) == (32, 24, 1)
    assert record["win_pct"] == pytest.approx(float(expected.win_pct))
    assert record["units"] == pytest.approx(float(expected.units))
    assert record["avg_clv"] == pytest.approx(float(expected.avg_clv))
    assert body["record_label"] == "live"
    updated = datetime.fromisoformat(body["lines_updated_at"])
    assert updated == datetime(2026, 10, 10, 13, tzinfo=UTC)
    assert body["stale"] is False
    assert body["picks"] == 9


# AC-2

NOW = m.utc(m.SEASON, 9, 1, 12)


def _version(conn: Connection, name: str, status: str, created_at: datetime) -> int:
    return conn.execute(
        text(
            "INSERT INTO model_versions (sport_id, market, name, version, spec,"
            " spec_schema_version, created_by, status, created_at)"
            " VALUES (:sport, 'spread', :name, 'v1', '{}', 1, 'user', :status, :at) RETURNING id"
        ),
        {"sport": m.SPORT, "name": name, "status": status, "at": created_at},
    ).scalar_one()


def _coming_game(
    conn: Connection, *, season: int = m.SEASON, kickoff: datetime | None = None
) -> int:
    m.sport(conn)
    home, away = m.team(conn, f"home-{season}"), m.team(conn, f"away-{season}")
    return m.game(conn, home, away, kickoff or NOW + timedelta(days=6), week=1,
                  status="scheduled", season=season)  # fmt: skip


def test_a_candidate_with_a_scheduled_run_this_season_is_shown(db_conn: Connection):
    _coming_game(db_conn)
    candidate = _version(db_conn, "paper", "candidate", m.utc(2030, 8, 1))
    m.run(db_conn, candidate, 1, m.utc(2030, 8, 30), run_type="scheduled")

    got = shell.load(db_conn, NOW, m.SPORT)

    assert got.model is not None and got.model.name == "paper"
    assert (got.season, got.week, got.picks) == (m.SEASON, 1, 0)


def test_the_newest_qualifying_candidate_is_shown(db_conn: Connection):
    _coming_game(db_conn)
    for name, created in (("older", m.utc(2030, 7, 1)), ("newer", m.utc(2030, 8, 1))):
        version_id = _version(db_conn, name, "candidate", created)
        m.run(db_conn, version_id, 1, m.utc(2030, 8, 30), run_type="scheduled")

    got = shell.load(db_conn, NOW, m.SPORT)

    assert got.model is not None and got.model.name == "newer"


def test_a_production_version_wins_over_a_candidate(db_conn: Connection):
    _coming_game(db_conn)
    candidate = _version(db_conn, "paper", "candidate", m.utc(2030, 8, 1))
    m.run(db_conn, candidate, 1, m.utc(2030, 8, 30), run_type="scheduled")
    _version(db_conn, "live", "production", m.utc(2030, 6, 1))

    got = shell.load(db_conn, NOW, m.SPORT)

    assert got.model is not None and got.model.name == "live"


@pytest.mark.parametrize(
    ("run_type", "run_status"),
    [("backtest", "succeeded"), ("adhoc", "succeeded"), ("scheduled", "failed")],
)
def test_a_candidate_without_a_succeeded_scheduled_run_is_not_shown(
    db_conn: Connection, run_type: str, run_status: str
):
    _coming_game(db_conn)
    candidate = _version(db_conn, "paper", "candidate", m.utc(2030, 8, 1))
    m.run(db_conn, candidate, 1, m.utc(2030, 8, 30), run_type=run_type, status=run_status)

    got = shell.load(db_conn, NOW, m.SPORT)

    assert (got.model, got.record, got.record_label, got.picks) == (None, None, None, None)


def test_a_candidate_whose_scheduled_run_is_last_season_is_not_shown(db_conn: Connection):
    """The run is in 2030 (model_rows' season); the coming game is in 2031."""
    _coming_game(db_conn, season=m.SEASON + 1, kickoff=m.utc(2031, 9, 6, 16))
    candidate = _version(db_conn, "paper", "candidate", m.utc(2030, 8, 1))
    m.run(db_conn, candidate, 1, m.utc(2030, 8, 30), run_type="scheduled")

    got = shell.load(db_conn, NOW, m.SPORT)

    assert got.season == m.SEASON + 1
    assert got.model is None


def test_no_version_still_answers_200(
    client: TestClient, make_token: MakeToken, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(shell, "SPORT", "no-such-sport")
    body = _get_shell(client, make_token, monkeypatch, SLATE_NOW)

    assert (body["model"], body["record"], body["record_label"], body["picks"]) == (
        None,
        None,
        None,
        None,
    )


# AC-3


@pytest.mark.parametrize(("hours", "stale"), [(23, False), (24, False), (25, True)])
def test_lines_are_stale_after_24_hours(db_conn: Connection, hours: int, stale: bool):
    game_id = _coming_game(db_conn)
    book_id = m.book(db_conn)
    m.line(db_conn, game_id, book_id, NOW - timedelta(days=3), -3.0)
    m.line(db_conn, game_id, book_id, NOW - timedelta(hours=hours), -3.5)

    got = shell.load(db_conn, NOW, m.SPORT)

    assert got.lines_updated_at == NOW - timedelta(hours=hours)
    assert got.stale is stale


def test_a_closing_line_is_not_a_pull(db_conn: Connection):
    """CFBD's untimed close isn't a `lines` pull, so it never counts as an update."""
    game_id = _coming_game(db_conn)
    book_id = m.book(db_conn)
    m.line(db_conn, game_id, book_id, NOW - timedelta(hours=30), -3.0)
    m.line(db_conn, game_id, book_id, NOW - timedelta(hours=1), -3.5, kind="closing")

    got = shell.load(db_conn, NOW, m.SPORT)

    assert got.lines_updated_at == NOW - timedelta(hours=30)
    assert got.stale is True


def test_another_seasons_pull_is_not_this_seasons_update(db_conn: Connection):
    """Lines updated reads the shown season's games only."""
    game_id = _coming_game(db_conn)
    old_season = _coming_game(db_conn, season=m.SEASON - 1, kickoff=m.utc(2029, 9, 8, 16))
    book_id = m.book(db_conn)
    m.line(db_conn, game_id, book_id, NOW - timedelta(hours=30), -3.0)
    m.line(db_conn, old_season, book_id, NOW - timedelta(hours=1), -7.0)

    got = shell.load(db_conn, NOW, m.SPORT)

    assert got.lines_updated_at == NOW - timedelta(hours=30)
    assert got.stale is True


def test_a_pull_after_now_is_not_an_update_yet(db_conn: Connection):
    """At a fixture time before a stored pull, that pull hasn't happened: the shell reads the
    newest one up to now."""
    game_id = _coming_game(db_conn)
    book_id = m.book(db_conn)
    m.line(db_conn, game_id, book_id, NOW - timedelta(hours=30), -3.0)
    m.line(db_conn, game_id, book_id, NOW + timedelta(hours=2), -3.5)

    got = shell.load(db_conn, NOW, m.SPORT)

    assert got.lines_updated_at == NOW - timedelta(hours=30)
    assert got.stale is True


# AC-4


def test_the_offseason_shell_names_the_last_season(
    client: TestClient, make_token: MakeToken, monkeypatch: pytest.MonkeyPatch
):
    body = _get_shell(client, make_token, monkeypatch, OFFSEASON_NOW)

    assert (body["season"], body["season_type"], body["week"]) == (2026, None, None)
    assert body["record_label"] == "final"
    assert body["record"] is not None and body["record"]["wins"] == 32
    assert (body["stale"], body["picks"]) == (False, None)


def test_after_the_last_game_the_shell_names_the_latest_season(db_conn: Connection):
    """Every game of 2030 and 2031 has started: the season is 2031, with no week, and the shown
    version's 2031 record is final."""
    m.sport(db_conn)
    home, away = m.team(db_conn, "home-final"), m.team(db_conn, "away-final")
    m.game(db_conn, home, away, m.utc(2030, 9, 7, 16), week=1, season=2030)
    last = m.game(db_conn, home, away, m.utc(2031, 9, 6, 16), week=1, season=2031,
                  points=(31, 10))  # fmt: skip
    version_id = _version(db_conn, "live", "production", m.utc(2030, 6, 1))
    run_id = m.run(db_conn, version_id, 1, m.utc(2031, 9, 1, 10))
    prediction_id = m.prediction(db_conn, run_id, version_id, last)
    snapshot = m.line(db_conn, last, m.book(db_conn), m.utc(2031, 9, 1, 10), -3.0)
    m.pick(db_conn, prediction_id, version_id, last, snapshot, m.utc(2031, 9, 1, 10, 10),
           side="home", line=-3.0)  # fmt: skip

    got = shell.load(db_conn, m.utc(2031, 12, 1), m.SPORT)

    assert (got.season, got.season_type, got.week, got.picks) == (2031, None, None, None)
    assert got.record is not None and (got.record.wins, got.record.losses) == (1, 0)
    assert (got.record_label, got.stale) == ("final", False)


def _postseason_game(conn: Connection, home: int, away: int, kickoff: datetime) -> int:
    return conn.execute(
        text(
            "INSERT INTO games (sport_id, source, source_id, season, week, season_type, game_date,"
            " kickoff_at, neutral_site, conference_game, home_team_id, away_team_id, status)"
            " VALUES (:sport, 'pytest', 'bowl', :season, 1, 'postseason', :d, :k, true, false,"
            " :h, :a, 'scheduled') RETURNING id"
        ),
        {"sport": m.SPORT, "season": m.SEASON, "d": kickoff.date(), "k": kickoff, "h": home,
         "a": away},
    ).scalar_one()  # fmt: skip


def test_a_regular_and_a_postseason_game_at_one_time_name_the_regular_week(db_conn: Connection):
    """D-150: on a tie for the earliest kickoff to come, the regular season's week."""
    kickoff = NOW + timedelta(days=3)
    m.sport(db_conn)
    home, away = m.team(db_conn, "home-tie"), m.team(db_conn, "away-tie")
    _postseason_game(db_conn, home, away, kickoff)
    m.game(db_conn, home, away, kickoff, week=15, status="scheduled")

    got = shell.load(db_conn, NOW, m.SPORT)

    assert (got.season_type, got.week) == ("regular", 15)


# AC-5


def test_teams_runs_its_queries_in_one_concurrent_wave(
    client: TestClient, make_token: MakeToken, monkeypatch: pytest.MonkeyPatch
):
    """Every statement waits at a barrier for the other: run one after the other, the first
    breaks the barrier and the request fails. A warm call first keeps the driver's first-connect
    queries out of the count."""
    from api import main

    _get_shell(client, make_token, monkeypatch, SLATE_NOW)
    statements: list[str] = []
    barrier = threading.Barrier(2, timeout=5)
    lock = threading.Lock()

    def counted(conn, cursor, statement, parameters, context, executemany):
        with lock:
            statements.append(statement)
        barrier.wait()

    engine = main.engine()
    event.listen(engine, "before_cursor_execute", counted)
    try:
        _get_shell(client, make_token, monkeypatch, SLATE_NOW)
    finally:
        event.remove(engine, "before_cursor_execute", counted)

    assert len(statements) == 2
    assert len(statements) <= wave.QUERY_BUDGET


def test_a_wave_over_budget_is_refused():
    queries = {str(i): (text("SELECT 1"), {}) for i in range(wave.QUERY_BUDGET + 1)}
    with pytest.raises(wave.OverBudget):
        wave.run_wave(None, queries)  # type: ignore[arg-type]


def test_the_shell_grades_only_the_shown_version(db_conn: Connection):
    """The record and pick reads apply the version at every picks scan, through an index, so
    the views never grade another version's picks first."""
    sql, params = shell.query(datetime.fromisoformat(SLATE_NOW))
    plan = m.explain(db_conn, sql.text, params)

    scans = m.scans(plan, "picks")
    assert scans
    for node in scans:
        assert node["Node Type"] != "Seq Scan", node
        applied = " ".join(node.get(k, "") for k in ("Index Cond", "Recheck Cond", "Filter"))
        assert "model_version_id" in applied, node


# AC-6


def test_fixture_now_needs_app_env_test(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("FIXTURE_NOW", SLATE_NOW)
    monkeypatch.delenv("APP_ENV", raising=False)
    assert abs(clock.now() - datetime.now(UTC)) < timedelta(minutes=1)

    monkeypatch.setenv("APP_ENV", "production")
    assert abs(clock.now() - datetime.now(UTC)) < timedelta(minutes=1)

    monkeypatch.setenv("APP_ENV", "test")
    assert clock.now() == datetime(2026, 10, 10, 18, 15, tzinfo=UTC)


def test_the_record_keeps_decimals_out_of_the_response():
    """`win_pct` and `units` come back from Postgres as Decimal; the response carries numbers."""
    row = type("R", (), {})()
    for name, value in {
        "season": 2026, "season_type": "regular", "week": 6, "model_name": "power",
        "model_version": "v1.0", "wins": 1, "losses": 0, "pushes": 0,
        "win_pct": Decimal("100.0"), "units": Decimal("1.0"), "avg_clv": None, "picks": 1,
        "lines_updated_at": datetime(2026, 10, 10, 13, tzinfo=UTC),
    }.items():  # fmt: skip
        setattr(row, name, value)

    got = shell.shell_from(row, datetime(2026, 10, 10, 18, 15, tzinfo=UTC))  # type: ignore[arg-type]

    assert got.record is not None
    assert (got.record.win_pct, got.record.units, got.record.avg_clv) == (100.0, 1.0, None)
