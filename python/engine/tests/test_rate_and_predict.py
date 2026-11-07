"""`engine job rate-and-predict` and the `lines` job's pick re-evaluation (TASK-046), against the
test DB.

The weekly job reads the shared lake (here a local one holding the backtest fixture's 2022-2023
raw files, with no `staging/`), rebuilds it in a scratch lake and writes through `jobs.make_engine`,
routed to a savepoint on the rolled-back `db_conn`. Reference rows are published from a separate
rebuild as `PUBLISH`, a source no real publish uses, with `models.SOURCE` pointed at it, as
test_publish_models.py does. The re-evaluation tests reuse test_publish_picks.py's world (a version
and FBS teams in the `pytest` sport) with a `scheduled` run of their own."""

from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from lake_fixture import (
    FIXTURE,
    backtest_game,
    engine,
    fixture_key,
    rematch_game_id,
    write_backtest_repull,
    write_backtest_seasons,
)
from sqlalchemy import Connection, text
from test_publish_picks import KICKOFF, World, _line
from test_publish_picks import SEASON as PICK_SEASON
from test_publish_picks import WEEK as PICK_WEEK

from engine import jobs
from engine.backtest import harness
from engine.core.spec import ModelSpec
from engine.ingest import backfill
from engine.ingest.backfill import sync_raw
from engine.ingest.lake import LocalLake, decode_raw, fetched_at_of, latest_raw, raw_folder
from engine.publish import models
from engine.publish.staging import publish_lake
from engine.transform import rebuild

PUBLISH = "manual"
NAME = "pytest-weekly"
SEASON, WEEK = 2023, 5
CANCELED = "401756847"  # Kansas-Fresno State's week-1 id: its week-5 copy is canceled
SPEC_FILE = Path(__file__).parents[1] / "specs" / "power-v1.json"
SPEC = ModelSpec.model_validate_json(SPEC_FILE.read_text("utf-8"))
CHOICES = {path: values[0] for path, values in SPEC.tunables().items()}
DEV = "postgresql://dev-host/cfb_dev"
WEEK1_IDS = [str(g["id"]) for g in FIXTURE[fixture_key("games")]["records"]]


def _first_kickoff(week: int) -> datetime:
    return min(
        datetime.fromisoformat(backtest_game(SEASON, "regular", week, i)["startDate"])
        for i in WEEK1_IDS
    )


def _sunday_before(moment: datetime) -> datetime:
    """09:00 ET (13:00 UTC) on the last Sunday before `moment`."""
    back = (moment.weekday() - 6) % 7 or 7
    return (moment - timedelta(days=back)).replace(hour=13, minute=0, second=0, microsecond=0)


NOW = _sunday_before(_first_kickoff(WEEK))


class Opened:
    def __init__(self) -> None:
        self.urls: list[str] = []
        self.transactions = 0
        self.isolation: list[str] = []  # each engine's isolation level, as the job asked for it


def _savepoint_engine(conn: Connection, opened: Opened) -> Any:
    """The job's engine: each transaction a savepoint on the rolled-back test connection."""

    class _Engine:
        def execution_options(self, isolation_level: str) -> _Engine:
            opened.isolation.append(isolation_level)
            return self

        @contextmanager
        def begin(self) -> Iterator[Connection]:
            opened.transactions += 1
            with conn.begin_nested():
                yield conn

        def dispose(self) -> None:
            pass

    return _Engine()


def _open_weekly(
    lake: LocalLake,
    db_conn: Connection,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    cfp_rematch: bool = False,
) -> Opened:
    write_backtest_seasons(lake, cfp_rematch=cfp_rematch)
    game = backtest_game(SEASON, "regular", WEEK, CANCELED)
    start = datetime.fromisoformat(game["startDate"])
    unplayed = {**game, "completed": False, "homePoints": None, "awayPoints": None}
    write_backtest_repull(lake, SEASON, "regular", WEEK, [unplayed], start + timedelta(days=8))
    published = LocalLake(tmp_path / "published")
    sync_raw(lake, published)
    rebuild(published)
    publish_lake(published, db_conn, PUBLISH)

    opened = Opened()

    def make_engine(url: str) -> Any:
        opened.urls.append(url)
        return _savepoint_engine(db_conn, opened)

    def no_cfbd(_lake: Any) -> Any:
        raise AssertionError("rate-and-predict built a CFBD client")

    monkeypatch.setattr(jobs, "make_engine", make_engine)
    monkeypatch.setattr(backfill, "client_for", no_cfbd)
    monkeypatch.setattr(models, "SOURCE", PUBLISH)
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("FIXTURE_NOW", NOW.isoformat())
    monkeypatch.setenv("DATABASE_URL_UNPOOLED", DEV)
    return opened


@pytest.fixture
def weekly(
    lake: LocalLake, db_conn: Connection, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> Opened:
    """The shared lake with two seasons and week 5's canceled game, its reference rows published,
    the clock on the Sunday before week 5, and the job's database the test connection."""
    return _open_weekly(lake, db_conn, monkeypatch, tmp_path)


def _run_file(
    tmp_path: Path, choices: dict[str, Any] | None = None, spec: ModelSpec = SPEC
) -> Path:
    path = tmp_path / "run.json"
    chosen = {str(SEASON): CHOICES} if choices is None else choices
    path.write_text(json.dumps({"spec_hash": harness.spec_hash(spec), "choices": chosen}), "utf-8")
    return path


def _job(run_file: Path, *extra: str, spec_file: Path = SPEC_FILE) -> int:
    return engine(
        "job",
        "rate-and-predict",
        *("--target", "dev", "--spec", str(spec_file), "--choices", str(run_file)),
        *("--name", NAME),
        *extra,
    )


def _week_games(conn: Connection) -> dict[str, Any]:
    """Week 5's published games by CFBD id, with each team's division."""
    rows = conn.execute(
        text(
            "SELECT g.id, g.source_id, g.status, hs.division AS home, aws.division AS away"
            " FROM games g"
            " LEFT JOIN team_seasons hs ON hs.team_id = g.home_team_id AND hs.season = g.season"
            " LEFT JOIN team_seasons aws ON aws.team_id = g.away_team_id AND aws.season = g.season"
            " WHERE g.source = :s AND g.season = :season AND g.season_type = 'regular'"
            " AND g.week = :week"
        ),
        {"s": PUBLISH, "season": SEASON, "week": WEEK},
    ).all()
    return {r.source_id: r for r in rows}


def _lines(conn: Connection, spread_home: float, at: datetime = NOW - timedelta(days=1)) -> None:
    """A DraftKings snapshot for each week-5 game, before the clock."""
    for game in _week_games(conn).values():
        _line(conn, game.id, "DraftKings", at, spread_home)


def _version(conn: Connection) -> Any:
    return conn.execute(
        text("SELECT id, status FROM model_versions WHERE name = :n AND version = 'v1.0'"),
        {"n": NAME},
    ).one_or_none()


def _runs(conn: Connection) -> list[Any]:
    return list(
        conn.execute(
            text(
                "SELECT r.* FROM model_runs r JOIN model_versions v ON v.id = r.model_version_id"
                " WHERE v.name = :n ORDER BY r.id"
            ),
            {"n": NAME},
        ).all()
    )


def _predicted(conn: Connection, run_id: int) -> set[str]:
    return set(
        conn.execute(
            text(
                "SELECT g.source_id FROM predictions p JOIN games g ON g.id = p.game_id"
                " WHERE p.model_run_id = :r"
            ),
            {"r": run_id},
        ).scalars()
    )


def _picks(conn: Connection) -> list[Any]:
    return list(
        conn.execute(
            text(
                "SELECT p.*, g.source_id FROM picks p JOIN games g ON g.id = p.game_id"
                " JOIN model_versions v ON v.id = p.model_version_id WHERE v.name = :n"
                " ORDER BY p.id"
            ),
            {"n": NAME},
        ).all()
    )


# AC-1: one transaction writes a scheduled run, its ratings, predictions and picks


def test_weekly_run_writes_run_ratings_predictions_and_picks(
    weekly: Opened, lake: LocalLake, db_conn: Connection, tmp_path: Path
) -> None:
    _lines(db_conn, 40.0)  # home +40: every pickable game clears the threshold on the home side
    ledger = lake.read_text("cfbd_calls.json")
    summary = tmp_path / "summary.md"

    code = _job(_run_file(tmp_path), "--summary", str(summary))

    assert code == 0, summary.read_text("utf-8") if summary.exists() else ""
    assert (weekly.urls, weekly.transactions) == ([DEV], 1)
    # D-148's advisory lock serializes two pick writers only under READ COMMITTED: pinned, not
    # left to the server's default.
    assert weekly.isolation == ["READ COMMITTED"]
    version = _version(db_conn)
    assert version.status == "candidate"  # created from the spec file: v1 is paper-traded (D-144)
    (run,) = _runs(db_conn)
    assert (run.run_type, run.status, run.season, run.week) == ("scheduled", "succeeded", 2023, 5)
    assert run.as_of == _first_kickoff(WEEK)
    assert run.fitted_params["choices"] == CHOICES
    ratings = db_conn.execute(
        text("SELECT count(*) FROM team_ratings WHERE model_run_id = :r"), {"r": run.id}
    ).scalar_one()
    assert ratings > 0
    games = _week_games(db_conn)
    assert games[str(backtest_game(SEASON, "regular", WEEK, CANCELED)["id"])].status == "canceled"
    playable = {sid for sid, g in games.items() if g.status != "canceled"}
    assert len(games) == 5 and len(playable) == 4
    assert _predicted(db_conn, run.id) == playable
    fbs = {sid for sid in playable if (games[sid].home, games[sid].away) == ("fbs", "fbs")}
    picked = _picks(db_conn)
    assert fbs and {p.source_id for p in picked} == fbs
    assert all((p.side, p.created_at) == ("home", NOW) for p in picked)
    assert lake.read_text("cfbd_calls.json") == ledger  # zero CFBD calls
    assert lake.walk("staging") == []  # rebuilt in a scratch lake, never the shared one
    text_ = summary.read_text("utf-8")
    assert "regular week 5" in text_
    assert f"Run {run.id} succeeded: {ratings} ratings, 4 predictions" in text_
    assert f"{len(fbs)} picks, 0 passes" in text_


def test_a_dry_run_writes_nothing(weekly: Opened, db_conn: Connection, tmp_path: Path) -> None:
    _lines(db_conn, 40.0)
    summary = tmp_path / "summary.md"

    assert _job(_run_file(tmp_path), "--dry-run", "--summary", str(summary)) == 0

    assert weekly.transactions == 1
    assert (_version(db_conn), _runs(db_conn), _picks(db_conn)) == (None, [], [])
    assert "Dry run" in summary.read_text("utf-8")


# AC-2: refusals write nothing; a failed check stops before the database; a re-run


def test_settings_for_the_season_unresolved_exits_2(
    weekly: Opened, db_conn: Connection, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = _job(_run_file(tmp_path, {"2022": CHOICES}))

    assert code == 2
    assert "didn't score 2023" in capsys.readouterr().err
    assert weekly.urls == []
    assert (_version(db_conn), _runs(db_conn)) == (None, [])


def test_a_version_with_another_spec_exits_2(
    weekly: Opened, db_conn: Connection, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    other = SPEC.model_copy(update={"home_field": 3.0})
    db_conn.execute(
        text(
            "INSERT INTO model_versions (sport_id, market, name, version, spec,"
            " spec_schema_version, created_by, status)"
            " VALUES ('cfb', 'spread', :n, 'v1.0', CAST(:spec AS jsonb), 1, 'system', 'candidate')"
        ),
        {"n": NAME, "spec": json.dumps(other.model_dump(mode="json"))},
    )

    code = _job(_run_file(tmp_path))

    assert code == 2
    assert "different spec" in capsys.readouterr().err
    assert _runs(db_conn) == []


def test_failed_check_exits_1_before_the_database(
    weekly: Opened, lake: LocalLake, tmp_path: Path
) -> None:
    game = backtest_game(SEASON, "regular", 4, WEEK1_IDS[1])
    unscored = {**game, "homePoints": None}  # completed with no score: final_has_score fails
    write_backtest_repull(lake, SEASON, "regular", 4, [unscored], NOW - timedelta(hours=1))
    summary = tmp_path / "summary.md"

    assert _job(_run_file(tmp_path), "--summary", str(summary)) == 1

    assert weekly.urls == []
    assert "FAIL final_has_score" in summary.read_text("utf-8")


def test_second_run_adds_a_run_but_no_unchanged_pick(
    weekly: Opened, db_conn: Connection, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _lines(db_conn, 40.0)
    run_file = _run_file(tmp_path)
    assert _job(run_file) == 0
    first = _picks(db_conn)
    monkeypatch.setenv("FIXTURE_NOW", (NOW + timedelta(hours=1)).isoformat())

    assert _job(run_file) == 0

    runs = _runs(db_conn)
    assert len(runs) == 2 and all(r.run_type == "scheduled" for r in runs)
    assert _predicted(db_conn, runs[1].id) == _predicted(db_conn, runs[0].id)
    assert first and _picks(db_conn) == first


# TASK-047 AC-1: postseason week 1 is rated, predicted and picked beside regular week 1

BOWLS = [backtest_game(SEASON, "postseason", 1, i) for i in ("401756847", "401754516")]


def _postseason_games(conn: Connection) -> dict[str, Any]:
    rows = conn.execute(
        text(
            "SELECT id, source_id FROM games WHERE source = :s AND season = :season"
            " AND season_type = 'postseason' AND week = 1"
        ),
        {"s": PUBLISH, "season": SEASON},
    ).all()
    return {r.source_id: r for r in rows}


def test_postseason_week_1_is_rated_beside_regular_week_1(
    weekly: Opened, db_conn: Connection, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_file = _run_file(tmp_path)
    monkeypatch.setenv("FIXTURE_NOW", _sunday_before(_first_kickoff(1)).isoformat())
    assert _job(run_file) == 0  # regular week 1 first
    first_bowl = min(datetime.fromisoformat(g["startDate"]) for g in BOWLS)
    bowls_now = _sunday_before(first_bowl)
    bowls = _postseason_games(db_conn)
    assert set(bowls) == {str(g["id"]) for g in BOWLS}
    for game in bowls.values():  # home +40: both FBS bowls clear the threshold at home
        _line(db_conn, game.id, "DraftKings", bowls_now - timedelta(days=1), 40.0)
    monkeypatch.setenv("FIXTURE_NOW", bowls_now.isoformat())
    summary = tmp_path / "summary.md"

    code = _job(run_file, "--summary", str(summary))

    assert code == 0, summary.read_text("utf-8") if summary.exists() else ""
    assert weekly.transactions == 2  # one per run: the run, its ratings, predictions and picks
    regular, post = _runs(db_conn)
    assert (regular.season_type, regular.week) == ("regular", 1)
    assert (post.run_type, post.status, post.season, post.season_type, post.week) == (
        "scheduled", "succeeded", SEASON, "postseason", 1,
    )  # fmt: skip
    assert post.as_of == first_bowl  # every bowl and CFP game from the ratings entering the first
    rated = dict(
        db_conn.execute(
            text(
                "SELECT model_run_id, array_agg(DISTINCT season_type) FROM team_ratings"
                " WHERE model_run_id = ANY(:r) GROUP BY model_run_id"
            ),
            {"r": [regular.id, post.id]},
        ).all()
    )
    assert rated == {regular.id: ["regular"], post.id: ["postseason"]}
    assert _predicted(db_conn, post.id) == set(bowls)
    assert not _predicted(db_conn, regular.id) & set(bowls)
    picked = [p for p in _picks(db_conn) if p.source_id in bowls]
    assert {p.source_id for p in picked} == set(bowls)
    assert all((p.side, p.created_at) == ("home", bowls_now) for p in picked)
    from_post = db_conn.execute(
        text("SELECT count(*) FROM predictions WHERE model_run_id = :r AND id = ANY(:p)"),
        {"r": post.id, "p": [p.prediction_id for p in picked]},
    ).scalar_one()
    assert from_post == len(bowls)
    text_ = summary.read_text("utf-8")
    assert "Week rated: postseason week 1" in text_
    assert f"Run {post.id} succeeded" in text_ and f"{len(bowls)} predictions" in text_
    assert f"{len(bowls)} picks, 0 passes" in text_


# TASK-058: a `rounds` version rates each CFP round from the rounds before it. The rematch
# fixture: two December games (round 1) and the January game between their winners (round 2).

ROUNDS = SPEC.model_copy(update={"postseason": "rounds"})
JANUARY = rematch_game_id(SEASON)


@pytest.fixture
def rounds_weekly(
    lake: LocalLake, db_conn: Connection, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> Path:
    """`weekly` on the rematch fixture; the `rounds` spec's file."""
    _open_weekly(lake, db_conn, monkeypatch, tmp_path, cfp_rematch=True)
    spec_file = tmp_path / "rounds.json"
    spec_file.write_text(ROUNDS.model_dump_json(), "utf-8")
    return spec_file


def _january_kickoff(conn: Connection) -> datetime:
    return conn.execute(
        text("SELECT kickoff_at FROM games WHERE source = :s AND source_id = :g"),
        {"s": PUBLISH, "g": JANUARY},
    ).scalar_one()


def _rows_of(conn: Connection, run_id: int) -> tuple[list[Any], list[Any]]:
    ratings = conn.execute(
        text("SELECT * FROM team_ratings WHERE model_run_id = :r ORDER BY team_id"), {"r": run_id}
    ).all()
    predictions = conn.execute(
        text("SELECT * FROM predictions WHERE model_run_id = :r ORDER BY game_id"), {"r": run_id}
    ).all()
    return list(ratings), list(predictions)


def test_rounds_version_rates_the_next_round(
    rounds_weekly: Path, db_conn: Connection, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC-1: with round 1 final and both teams of the January game known, the job inserts a
    scheduled round-2 run: `as_of` its kickoff, ratings counting round 1, predictions for that
    game, and a pick from them. The round-1 run and its rows stay as they were."""
    run_file = _run_file(tmp_path, spec=ROUNDS)
    fits: list[set[int]] = []
    fit_games = harness.fit_games

    def recording(history: harness.History, as_of: datetime) -> Any:
        found = fit_games(history, as_of)
        fits.append({g.game_id for g in found})
        return found

    monkeypatch.setattr(harness, "fit_games", recording)
    # The fixture holds the January game's teams from the start, so round 1 comes from the job's
    # own writer: on the Sunday before the first bowl they aren't known yet.
    fitted = models.fit_week(
        LocalLake(tmp_path / "published"),
        ROUNDS,
        CHOICES,
        season=SEASON,
        week=1,
        season_type="postseason",
    )
    models.write(
        db_conn, fitted, ROUNDS, name=NAME, version="v1.0", run_type="scheduled", status="candidate"
    )
    first = _runs(db_conn)[-1]
    assert (first.season_type, first.week) == ("postseason", 1)
    december = _predicted(db_conn, first.id)
    assert JANUARY not in december and len(december) == 2
    before = _rows_of(db_conn, first.id)

    kickoff = _january_kickoff(db_conn)
    now = _sunday_before(kickoff)
    january = _postseason_games(db_conn)[JANUARY]
    _line(db_conn, january.id, "DraftKings", now - timedelta(days=1), 40.0)
    monkeypatch.setenv("FIXTURE_NOW", now.isoformat())
    summary = tmp_path / "summary.md"

    assert _job(run_file, "--summary", str(summary), spec_file=rounds_weekly) == 0

    second = _runs(db_conn)[-1]
    assert (second.run_type, second.status, second.season_type, second.week) == (
        "scheduled", "succeeded", "postseason", 2,
    )  # fmt: skip
    assert second.as_of == kickoff
    assert _predicted(db_conn, second.id) == {JANUARY}
    assert {int(g) for g in december} <= fits[-1] and int(JANUARY) not in fits[-1]
    assert not {int(g) for g in december} & fits[0]
    rated, predicted = _rows_of(db_conn, second.id)
    assert {(r.season_type, r.week) for r in rated} == {("postseason", 2)}
    moved = {r.team_id: r.rating for r in before[0]}
    assert any(moved[r.team_id] != r.rating for r in rated)
    (pick,) = [p for p in _picks(db_conn) if p.source_id == JANUARY]
    assert pick.prediction_id == predicted[0].id
    assert _rows_of(db_conn, first.id) == before  # hard rule 2
    assert "Week rated: postseason week 2" in summary.read_text("utf-8")


def test_a_known_round_is_rated_past_a_bowl_still_to_come(
    rounds_weekly: Path, db_conn: Connection, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC-3: the earliest game to come is a round-1 game, but the January game's teams are both
    known, so the job rates round 2. The round of the earliest kickoff would rate round 1, and
    the 12-team quarterfinals would never be rated before they're played."""
    first_bowl = min(datetime.fromisoformat(g["startDate"]) for g in BOWLS)
    second_game = first_bowl + timedelta(hours=1)  # after the first's kickoff, before the next's
    monkeypatch.setenv("FIXTURE_NOW", second_game.isoformat())
    assert jobs.due_weeks(
        "lines", (g for g, _ in jobs._games(LocalLake(tmp_path / "published"), SEASON).values()),
        second_game,
    ) == [("postseason", 1)]  # fmt: skip

    assert _job(_run_file(tmp_path, spec=ROUNDS), spec_file=rounds_weekly) == 0

    (run,) = _runs(db_conn)
    assert (run.season_type, run.week) == ("postseason", 2)
    assert _predicted(db_conn, run.id) == {JANUARY}


def test_no_round_with_both_teams_writes_nothing(
    rounds_weekly: Path,
    lake: LocalLake,
    db_conn: Connection,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC-3: the title game is still to come and one of its teams isn't known: nothing to rate,
    so no run, and the summary says why."""
    pulled = latest_raw(lake, raw_folder("games", SEASON, 1, "postseason"))
    assert pulled is not None
    saved = fetched_at_of(pulled) + timedelta(days=1)
    start = saved + timedelta(days=10)  # after the pull, so it's staged scheduled, not canceled
    unknown = {
        "awayId": None,
        "awayTeam": None,
        "homePoints": None,
        "awayPoints": None,
        "completed": False,
        "startDate": start.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
    }
    repull = [
        {**g, **unknown} if str(g["id"]) == JANUARY else g for g in decode_raw(lake.read(pulled))
    ]
    write_backtest_repull(lake, SEASON, "postseason", 1, repull, saved)
    monkeypatch.setenv("FIXTURE_NOW", _sunday_before(start).isoformat())
    summary = tmp_path / "summary.md"

    code = _job(
        _run_file(tmp_path, spec=ROUNDS), "--summary", str(summary), spec_file=rounds_weekly
    )

    assert code == 0, summary.read_text("utf-8") if summary.exists() else ""
    assert _runs(db_conn) == []
    assert "both teams" in summary.read_text("utf-8")


# AC-3: the `lines` job re-evaluates each version's newest scheduled run


def _scheduled(
    world: World, *, finished_at: datetime, week: int = PICK_WEEK, season_type: str = "regular"
) -> int:
    run = world.conn.execute(
        text(
            "INSERT INTO model_runs (model_version_id, run_type, season, season_type, week, as_of,"
            " status, started_at, finished_at, fitted_params)"
            " SELECT model_version_id, 'scheduled', season, :season_type, :week, as_of, status,"
            " started_at, :finished, fitted_params FROM model_runs WHERE id = :r RETURNING id"
        ),
        {"r": world.run, "finished": finished_at, "week": week, "season_type": season_type},
    ).scalar_one()
    world.run = run
    return run


LINES_NOW = datetime(2030, 10, 8, 12, tzinfo=UTC)


def _reevaluate(world: World, now: datetime) -> list[jobs.Repicked]:
    return jobs.reevaluate(world.conn, PICK_SEASON, now)


def _pick_rows(world: World, game_id: int) -> list[Any]:
    return list(
        world.conn.execute(
            text("SELECT * FROM picks WHERE model_version_id = :v AND game_id = :g ORDER BY id"),
            {"v": world.version, "g": game_id},
        ).all()
    )


def test_lines_gains_a_pick_when_the_line_crosses(world: World) -> None:
    _scheduled(world, finished_at=LINES_NOW - timedelta(days=2))
    game = world.game(10.0)
    _line(world.conn, game, "DraftKings", LINES_NOW - timedelta(days=1), -9.0)  # edge 1: no pick
    assert [r.summary.picks for r in _reevaluate(world, LINES_NOW)] == [0]
    moved = LINES_NOW + timedelta(hours=6)
    _line(world.conn, game, "DraftKings", moved - timedelta(hours=1), -5.0)  # edge 5: a pick

    (result,) = _reevaluate(world, moved)

    assert (result.version_id, result.week, result.summary.picks) == (
        world.version, ("regular", PICK_WEEK), 1
    )
    (pick,) = _pick_rows(world, game)
    assert (pick.side, pick.line, pick.created_at) == ("home", -5.0, moved)


def test_lines_writes_nothing_when_nothing_changes(world: World) -> None:
    _scheduled(world, finished_at=LINES_NOW - timedelta(days=2))
    game = world.game(10.0)
    _line(world.conn, game, "DraftKings", LINES_NOW - timedelta(days=1), -3.0)
    _reevaluate(world, LINES_NOW)
    before = _pick_rows(world, game)

    (result,) = _reevaluate(world, LINES_NOW + timedelta(hours=6))

    assert (result.summary.picks, result.summary.passes, result.summary.games) == (0, 0, 1)
    assert len(before) == 1 and _pick_rows(world, game) == before


def test_lines_writes_nothing_after_kickoff(world: World) -> None:
    _scheduled(world, finished_at=LINES_NOW - timedelta(days=2))
    game = world.game(10.0)
    _line(world.conn, game, "DraftKings", KICKOFF - timedelta(hours=2), -3.0)

    (result,) = _reevaluate(world, KICKOFF + timedelta(minutes=1))

    assert (result.summary.picks, result.summary.open) == (0, 0)
    assert _pick_rows(world, game) == []


def test_lines_reads_scheduled_runs_only(world: World) -> None:
    # The world's own run is `adhoc` (an `engine rate` by hand): the job leaves it alone.
    game = world.game(10.0)
    _line(world.conn, game, "DraftKings", LINES_NOW - timedelta(days=1), -3.0)

    assert [r for r in _reevaluate(world, LINES_NOW) if r.version_id == world.version] == []
    assert _pick_rows(world, game) == []


def test_lines_skips_a_retired_version(world: World) -> None:
    _scheduled(world, finished_at=LINES_NOW - timedelta(days=2))
    game = world.game(10.0)
    _line(world.conn, game, "DraftKings", LINES_NOW - timedelta(days=1), -3.0)
    world.conn.execute(
        text("UPDATE model_versions SET status = 'retired' WHERE id = :v"), {"v": world.version}
    )

    assert [r for r in _reevaluate(world, LINES_NOW) if r.version_id == world.version] == []
    assert _pick_rows(world, game) == []


def test_lines_reevaluates_the_newest_scheduled_weeks_run(world: World) -> None:
    _scheduled(world, finished_at=LINES_NOW - timedelta(days=9), week=PICK_WEEK - 1)
    _scheduled(world, finished_at=LINES_NOW - timedelta(days=2))
    game = world.game(10.0)
    _line(world.conn, game, "DraftKings", LINES_NOW - timedelta(days=1), -3.0)

    results = [r for r in _reevaluate(world, LINES_NOW) if r.version_id == world.version]

    assert [(r.week, r.summary.run_id, r.summary.picks) for r in results] == [
        (("regular", PICK_WEEK), world.run, 1)
    ]


def test_lines_reevaluates_the_postseason_week(world: World) -> None:
    """TASK-047 AC-3: once the weekly job has rated the bowls, `lines` re-picks postseason week 1
    from that run, as it does a regular week's, and its summary names the week. The season's
    regular week 1, rated earlier, isn't re-picked: the newest scheduled run is the bowls'."""
    _scheduled(world, finished_at=LINES_NOW - timedelta(days=60), week=1)
    opener = world.game(10.0, week=1)
    _line(world.conn, opener, "DraftKings", LINES_NOW - timedelta(days=1), -3.0)
    post = _scheduled(
        world, finished_at=LINES_NOW - timedelta(days=2), week=1, season_type="postseason"
    )
    bowl = world.game(10.0, season_type="postseason", week=1)
    _line(world.conn, bowl, "DraftKings", LINES_NOW - timedelta(days=1), -3.0)

    results = [r for r in _reevaluate(world, LINES_NOW) if r.version_id == world.version]

    assert [(r.week, r.summary.run_id, r.summary.picks) for r in results] == [
        (("postseason", 1), post, 1)
    ]
    (row,) = _pick_rows(world, bowl)
    assert row.side == "home"
    picked_from = world.conn.execute(
        text("SELECT model_run_id FROM predictions WHERE id = :p"), {"p": row.prediction_id}
    ).scalar_one()
    assert picked_from == post
    assert _pick_rows(world, opener) == []
    report = jobs.Summary("lines", PICK_SEASON, "test", repicked=results).render()
    assert f"pytest-picks v1.0, postseason week 1, run {post}: 1 picks" in report
    _line(world.conn, bowl, "DraftKings", LINES_NOW + timedelta(hours=1), -12.0)
    later = [
        r for r in _reevaluate(world, LINES_NOW + timedelta(hours=2))
        if r.version_id == world.version
    ]  # fmt: skip
    assert [(r.week, r.summary.passes) for r in later] == [(("postseason", 1), 1)]


def test_lines_reevaluates_every_open_round(world: World) -> None:
    """TASK-058 AC-3: bowls run past the quarterfinals, so once round 2 is rated the bowls still
    to come stay re-picked from round 1's run, each round from its own newest run; a regular
    week rated earlier isn't."""
    _scheduled(world, finished_at=LINES_NOW - timedelta(days=30), week=1)
    opener = world.game(10.0, week=1)
    _line(world.conn, opener, "DraftKings", LINES_NOW - timedelta(days=1), -3.0)
    _scheduled(world, finished_at=LINES_NOW - timedelta(days=9), week=1, season_type="postseason")
    first = _scheduled(
        world, finished_at=LINES_NOW - timedelta(days=8), week=1, season_type="postseason"
    )
    bowl = world.game(10.0, season_type="postseason", week=1)
    second = _scheduled(
        world, finished_at=LINES_NOW - timedelta(days=2), week=2, season_type="postseason"
    )
    quarterfinal = world.game(10.0, season_type="postseason", week=1)
    for game in (bowl, quarterfinal):
        _line(world.conn, game, "DraftKings", LINES_NOW - timedelta(days=1), -3.0)

    results = [r for r in _reevaluate(world, LINES_NOW) if r.version_id == world.version]

    assert [(r.week, r.summary.run_id, r.summary.picks) for r in results] == [
        (("postseason", 1), first, 1),
        (("postseason", 2), second, 1),
    ]
    assert _pick_rows(world, opener) == []


@pytest.fixture
def world(db_conn: Connection) -> World:
    return World(db_conn)
