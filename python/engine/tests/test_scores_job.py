"""`engine job scores` and its workflow (TASK-074): one CFBD `/scoreboard` call per run, saved as a
new raw file, updating the matched CFB games' status, points and live clock by source key; never
a new game, never a final game moved back, a rerun changing nothing; the NFL refresh through
nflverse only while a contest's NFL game is live; the summary and the budget's exit 3.

CFBD is an httpx.MockTransport serving `fixtures/cfbd_scoreboard_sample.json` (CFBD's documented
`ScoreboardGame` shape); nflverse is the recorded `fixtures/nflverse/games.csv` (conftest). The
writes go to the rolled-back test connection."""

from __future__ import annotations

import copy
import json
import re
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import httpx
import pytest
from lake_fixture import engine
from sqlalchemy import Connection, text

from db.config import repo_root
from db.release import script_directory, single_head
from engine import scores
from engine.ingest import backfill, nflverse
from engine.ingest.cfbd import MONTHLY_LIMIT, CallBudget, CfbdClient
from engine.ingest.lake import LocalLake

SATURDAY = "2026-10-10T21:00:00Z"  # 17:00 ET, week 6
SUNDAY = "2026-10-18T21:00:00Z"  # 17:00 ET: TEN @ IND (13:00 ET) has kicked off
PROD = "postgresql://jobs:secret@ep-prod.example.neon.tech/cfb"
BOARD: list[dict[str, Any]] = json.loads(
    (Path(__file__).parent / "fixtures" / "cfbd_scoreboard_sample.json").read_text("utf-8")
)
WORKFLOW = repo_root() / ".github" / "workflows" / "scores.yml"
# Rows only other jobs write: the scores job must leave every one of these counts alone.
UNTOUCHED = ("line_snapshots", "team_ratings", "predictions", "picks", "contest_lines", "teams")


@pytest.fixture
def r2(empty_lake: LocalLake, monkeypatch: pytest.MonkeyPatch) -> LocalLake:
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("FIXTURE_NOW", SATURDAY)
    monkeypatch.setenv("CFBD_API_KEY", "")
    return empty_lake


def serve(
    lake: LocalLake, monkeypatch: pytest.MonkeyPatch, board: list[dict[str, Any]] | None = None
) -> list[str]:
    """Route the job's CFBD client to `board` (the fixture by default); returns the request log."""
    requests: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(f"{request.url.path}?{request.url.query.decode()}")
        return httpx.Response(200, json=BOARD if board is None else board)

    http = httpx.Client(base_url="https://cfbd.test", transport=httpx.MockTransport(handler))
    client = CfbdClient("key", CallBudget(lake), http)
    monkeypatch.setattr(backfill, "client_for", lambda _lake: client)
    return requests


def into(monkeypatch: pytest.MonkeyPatch, conn: Connection) -> None:
    """The job's writes go to the rolled-back test connection."""

    @contextmanager
    def begin() -> Iterator[Connection]:
        yield conn

    class Engine:
        def begin(self) -> Any:
            return begin()

        def dispose(self) -> None:
            pass

    monkeypatch.setattr(scores, "make_engine", lambda _url: Engine())


def live(monkeypatch: pytest.MonkeyPatch) -> None:
    """Production at PROD, its schema at the code's head (the guard's own test is below)."""
    monkeypatch.setenv("LIVE", "true")
    monkeypatch.setenv("PRODUCTION_DATABASE_URL_UNPOOLED", PROD)
    monkeypatch.setattr(scores, "require_schema", lambda _url: None)


def job(tmp_path: Path, *args: str) -> tuple[int, str]:
    summary = tmp_path / "summary.md"
    code = engine("job", "scores", "--target", "live", "--summary", str(summary), *args)
    return code, summary.read_text("utf-8") if summary.exists() else ""


def ledger(lake: LocalLake) -> dict[str, int]:
    return json.loads(lake.read_text("cfbd_calls.json") or "{}")


# ─── CFB games in the test DB ──────────────────────────────────────────────────────────────────


def _team(conn: Connection, sport: str, source: str, source_id: str, school: str) -> int:
    return conn.execute(
        text(
            "INSERT INTO teams (sport_id, source, source_id, school)"
            " VALUES (:sport, :source, :id, :school)"
            " ON CONFLICT (sport_id, source, source_id) DO UPDATE SET school = EXCLUDED.school"
            " RETURNING id"
        ),
        {"sport": sport, "source": source, "id": source_id, "school": school},
    ).scalar_one()


def _game(
    conn: Connection,
    source_id: str,
    home: int,
    away: int,
    *,
    status: str = "scheduled",
    points: tuple[int, int] | None = None,
    sport: str = "cfb",
    source: str = "cfbd",
    kickoff: str = "2026-10-10T19:30:00Z",
    week: int = 6,
) -> int:
    return conn.execute(
        text(
            "INSERT INTO games (sport_id, source, source_id, season, week, season_type,"
            " game_date, kickoff_at, neutral_site, conference_game, home_team_id, away_team_id,"
            " home_points, away_points, status)"
            " VALUES (:sport, :source, :id, 2026, :week, 'regular', CAST(:kickoff AS timestamptz)"
            " AT TIME ZONE 'America/New_York', CAST(:kickoff AS timestamptz), false, false,"
            " :home, :away, :hp, :ap, :status) RETURNING id"
        ),
        {
            "sport": sport,
            "source": source,
            "id": source_id,
            "week": week,
            "kickoff": kickoff,
            "home": home,
            "away": away,
            "hp": points[0] if points else None,
            "ap": points[1] if points else None,
            "status": status,
        },
    ).scalar_one()


@pytest.fixture
def week6(db_conn: Connection) -> Connection:
    """CFBD's ids for five of the scoreboard's six games (401790004, Iowa at Wisconsin, has no
    game row). Tulane at Memphis is already final, published 27-24 by `results`."""
    team = {
        sid: _team(db_conn, "cfb", "cfbd", sid, name)
        for sid, name in (
            ("194", "Ohio State"), ("2509", "Purdue"), ("68", "Boise State"), ("2439", "UNLV"),
            ("62", "Hawai'i"), ("2440", "Nevada"), ("235", "Memphis"), ("2655", "Tulane"),
            ("66", "Iowa State"), ("2132", "Cincinnati"),
        )
    }  # fmt: skip
    _game(db_conn, "401790001", team["194"], team["2509"])
    _game(db_conn, "401790002", team["68"], team["2439"], kickoff="2026-10-10T16:00:00Z")
    _game(db_conn, "401790003", team["62"], team["2440"], kickoff="2026-10-11T02:30:00Z")
    _game(
        db_conn,
        "401790005",
        team["235"],
        team["2655"],
        status="final",
        points=(24, 27),
        kickoff="2026-10-09T23:30:00Z",
    )
    _game(db_conn, "401790006", team["66"], team["2132"], kickoff="2026-10-10T16:00:00Z")
    return db_conn


GAMES = text(
    "SELECT source_id, status, home_points, away_points, period, clock FROM games"
    " WHERE sport_id = 'cfb' AND source = 'cfbd' AND source_id LIKE '4017900%'"
    " ORDER BY source_id"
)


def games(conn: Connection) -> list[tuple[Any, ...]]:
    return [tuple(r) for r in conn.execute(GAMES)]


def versions(conn: Connection) -> list[tuple[Any, ...]]:
    """Each game row's physical version: any UPDATE, even to the same values, moves its ctid."""
    sql = GAMES.text.replace("SELECT source_id,", "SELECT source_id, ctid::text,")
    return [tuple(r[:2]) for r in conn.execute(text(sql))]


def counts(conn: Connection) -> dict[str, int]:
    return {t: conn.execute(text(f"SELECT count(*) FROM {t}")).scalar_one() for t in UNTOUCHED}


def nfl_and_fixture_games(conn: Connection) -> int:
    return conn.execute(text("SELECT count(*) FROM games WHERE source <> 'cfbd'")).scalar_one()


def run(lake: LocalLake, monkeypatch: pytest.MonkeyPatch, sport: scores.Sport = "all") -> Any:
    monkeypatch.setattr(scores, "require_schema", lambda _url: None)  # schema at the head
    client = backfill.client_for(lake)
    return scores.run(lake, PROD, target="live", sport=sport, client=client)


# ─── AC-1: one call, a new raw file, matched games updated by source key ──────────────────────


def test_a_run_makes_one_call_saves_it_and_updates_matched_games(
    r2: LocalLake, monkeypatch: pytest.MonkeyPatch, week6: Connection
) -> None:
    requests = serve(r2, monkeypatch)
    into(monkeypatch, week6)
    before = counts(week6)
    others = nfl_and_fixture_games(week6)

    summary = run(r2, monkeypatch)

    assert requests == ["/scoreboard?"]
    assert ledger(r2) == {"2026-10": 1}
    (raw,) = r2.walk("raw/cfbd/scoreboard")
    assert raw.startswith("raw/cfbd/scoreboard/season=2026/fetched_at=")
    assert games(week6) == [
        ("401790001", "in_progress", 24, 3, 3, "09:12"),
        ("401790002", "final", 31, 24, None, None),
        ("401790003", "scheduled", None, None, None, None),  # not started: left alone
        ("401790005", "final", 24, 27, None, None),  # already final: never touched
        ("401790006", "scheduled", None, None, None, None),  # completed, no score: not written
    ]
    # 401790004 has no game: never created.
    assert week6.execute(
        text("SELECT count(*) FROM games WHERE source_id = '401790004'")
    ).scalar_one() == 0
    assert nfl_and_fixture_games(week6) == others
    assert counts(week6) == before  # no lines, ratings, predictions, picks or teams
    assert summary.cfb_updated == {"in_progress": 1, "final": 1}
    assert summary.unmatched == ["401790004: Iowa at Wisconsin"]
    assert summary.unscored == ["401790006: Cincinnati at Iowa State"]


def test_a_second_run_saves_another_file(
    r2: LocalLake, monkeypatch: pytest.MonkeyPatch, week6: Connection
) -> None:
    """Each pull is a new raw file, never a reuse of a saved one: the raw lake is append-only."""
    serve(r2, monkeypatch)
    into(monkeypatch, week6)
    run(r2, monkeypatch)
    monkeypatch.setenv("FIXTURE_NOW", "2026-10-10T21:30:00Z")
    run(r2, monkeypatch)
    assert len(r2.walk("raw/cfbd/scoreboard")) == 2
    assert ledger(r2) == {"2026-10": 2}


# ─── AC-2: the clock while in progress, NULL once final ───────────────────────────────────────


def finished(board: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The fixture an hour on: Ohio State-Purdue completed 38-10."""
    later = copy.deepcopy(board)
    game = later[0]
    game.update(status="completed", period=4, clock="00:00")
    game["homeTeam"]["points"], game["awayTeam"]["points"] = 38, 10
    return later


def test_the_clock_is_cleared_when_the_game_is_final(
    r2: LocalLake, monkeypatch: pytest.MonkeyPatch, week6: Connection
) -> None:
    into(monkeypatch, week6)
    serve(r2, monkeypatch)
    run(r2, monkeypatch)
    assert games(week6)[0] == ("401790001", "in_progress", 24, 3, 3, "09:12")

    serve(r2, monkeypatch, finished(BOARD))
    monkeypatch.setenv("FIXTURE_NOW", "2026-10-10T22:00:00Z")
    run(r2, monkeypatch)
    assert games(week6)[0] == ("401790001", "final", 38, 10, None, None)


# ─── AC-3: a rerun changes nothing; a final game never goes back ──────────────────────────────


def test_running_again_on_the_same_scoreboard_changes_no_row(
    r2: LocalLake, monkeypatch: pytest.MonkeyPatch, week6: Connection
) -> None:
    serve(r2, monkeypatch)
    into(monkeypatch, week6)
    run(r2, monkeypatch)
    after_first = games(week6), versions(week6)

    monkeypatch.setenv("FIXTURE_NOW", "2026-10-10T21:30:00Z")
    summary = run(r2, monkeypatch)

    assert (games(week6), versions(week6)) == after_first
    assert summary.cfb_updated == {}


def back_in_play(board: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """A stale scoreboard: Boise State-UNLV and Tulane-Memphis shown in progress, and Tulane-Memphis
    scheduled in a second record."""
    stale = copy.deepcopy(board)
    for game in stale:
        if game["id"] in (401790002, 401790005):
            game.update(status="in_progress", period=4, clock="01:00")
            game["homeTeam"]["points"], game["awayTeam"]["points"] = 17, 17
    again = copy.deepcopy(next(g for g in board if g["id"] == 401790005))
    again.update(status="scheduled", period=None, clock=None)
    return [*stale, again]


def test_a_final_game_is_never_moved_back(
    r2: LocalLake, monkeypatch: pytest.MonkeyPatch, week6: Connection
) -> None:
    into(monkeypatch, week6)
    serve(r2, monkeypatch)
    run(r2, monkeypatch)  # Boise State-UNLV goes final
    serve(r2, monkeypatch, back_in_play(BOARD))
    monkeypatch.setenv("FIXTURE_NOW", "2026-10-10T21:30:00Z")
    summary = run(r2, monkeypatch)
    rows = {r[0]: r[1:] for r in games(week6)}
    assert rows["401790002"] == ("final", 31, 24, None, None)
    assert rows["401790005"] == ("final", 24, 27, None, None)
    assert summary.cfb_updated == {}  # Ohio State-Purdue is unchanged too


# ─── AC-4: the NFL refresh, only while a contest's NFL game is live ───────────────────────────


def _contest(conn: Connection, game_id: int, deleted: bool = False) -> None:
    user = conn.execute(
        text("INSERT INTO users (github_id) VALUES (:g) RETURNING id"), {"g": 990_074 + game_id}
    ).scalar_one()
    contest = conn.execute(
        text(
            "INSERT INTO contests (user_id, name, platform, season, rules, deleted_at)"
            " VALUES (:u, 'Scores job', 'splash', 2026, '{}',"
            " CASE WHEN :deleted THEN now() END) RETURNING id"
        ),
        {"u": user, "deleted": deleted},
    ).scalar_one()
    conn.execute(
        text(
            "INSERT INTO contest_lines (contest_id, period, game_id, spread_home, captured_at,"
            " source) VALUES (:c, 7, :g, -3.5, '2026-10-16T12:00Z', 'manual')"
        ),
        {"c": contest, "g": game_id},
    )


def ten_at_ind(conn: Connection) -> int:
    """TEN @ IND, 2026 week 6, kicked off 13:00 ET Sunday: nflverse's recorded file has it
    final 26-20."""
    home = _team(conn, "nfl", "nflverse", "IND", "Indianapolis")
    away = _team(conn, "nfl", "nflverse", "TEN", "Tennessee")
    return _game(
        conn,
        "2026_06_TEN_IND",
        home,
        away,
        sport="nfl",
        source="nflverse",
        kickoff="2026-10-18T17:00:00Z",
    )


NFL_GAME = text(
    "SELECT status, home_points, away_points FROM games"
    " WHERE sport_id = 'nfl' AND source = 'nflverse' AND source_id = '2026_06_TEN_IND'"
)


@pytest.fixture
def sunday(r2: LocalLake, monkeypatch: pytest.MonkeyPatch) -> LocalLake:
    monkeypatch.setenv("FIXTURE_NOW", SUNDAY)
    return r2


def downloads(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Count nflverse downloads, still serving the recorded file."""
    made: list[str] = []
    real = nflverse.download

    def counted(http: httpx.Client | None = None) -> str:
        made.append("games.csv")
        return real(http)

    monkeypatch.setattr(nflverse, "download", counted)
    return made


def test_a_live_contest_nfl_game_refreshes_nfl_scores_with_no_cfbd_call(
    sunday: LocalLake, monkeypatch: pytest.MonkeyPatch, db_conn: Connection
) -> None:
    requests = serve(sunday, monkeypatch, [])
    into(monkeypatch, db_conn)
    _contest(db_conn, ten_at_ind(db_conn))
    made = downloads(monkeypatch)
    lines = db_conn.execute(text("SELECT count(*) FROM line_snapshots")).scalar_one()

    summary = run(sunday, monkeypatch, sport="nfl")

    assert requests == []  # an NFL-only run makes no CFBD call
    assert ledger(sunday) == {}
    assert made == ["games.csv"]
    assert len(sunday.walk("raw/nflverse/games/season=2026")) == 1
    assert tuple(db_conn.execute(NFL_GAME).one()) == ("final", 20, 26)
    # The scores job writes games only: the pull's lines wait for `lines` to publish them.
    assert db_conn.execute(text("SELECT count(*) FROM line_snapshots")).scalar_one() == lines
    assert summary.nfl_live and summary.nfl_updated == 1


def test_the_full_run_refreshes_both(
    sunday: LocalLake, monkeypatch: pytest.MonkeyPatch, db_conn: Connection
) -> None:
    requests = serve(sunday, monkeypatch, [])
    into(monkeypatch, db_conn)
    _contest(db_conn, ten_at_ind(db_conn))
    made = downloads(monkeypatch)
    summary = run(sunday, monkeypatch)
    assert requests == ["/scoreboard?"]  # the one CFBD call is CFB's
    assert made == ["games.csv"]
    assert summary.nfl_updated == 1


@pytest.mark.parametrize(
    "case",
    ["no contest", "deleted contest", "kicked off 13 hours ago", "already final", "not started"],
)
def test_no_live_contest_nfl_game_skips_the_pull(
    case: str, sunday: LocalLake, monkeypatch: pytest.MonkeyPatch, db_conn: Connection
) -> None:
    """The seeded contests' NFL games kicked off a week earlier and are still `scheduled` (a
    fixture never goes final), so the 12-hour bound alone keeps them from pulling every run."""
    serve(sunday, monkeypatch, [])
    into(monkeypatch, db_conn)
    game = ten_at_ind(db_conn)
    if case != "no contest":
        _contest(db_conn, game, deleted=case == "deleted contest")
    moves: dict[str, Callable[[], str]] = {
        "kicked off 13 hours ago": lambda: "kickoff_at = '2026-10-18T08:00Z'",
        "already final": lambda: "status = 'final', home_points = 20, away_points = 26",
        "not started": lambda: "kickoff_at = '2026-10-18T22:00Z'",
    }
    if case in moves:
        db_conn.execute(text(f"UPDATE games SET {moves[case]()} WHERE id = :id"), {"id": game})
    made = downloads(monkeypatch)

    summary = run(sunday, monkeypatch, sport="nfl")

    assert made == []
    assert sunday.walk("raw/nflverse") == []
    assert not summary.nfl_live and summary.nfl_updated == 0


# ─── AC-6: the summary, and the budget ────────────────────────────────────────────────────────


def test_the_summary_reports_calls_and_games_updated_by_sport(
    sunday: LocalLake, monkeypatch: pytest.MonkeyPatch, db_conn: Connection, tmp_path: Path
) -> None:
    live(monkeypatch)
    sunday.write_text("cfbd_calls.json", json.dumps({"2026-10": 41}))
    board = copy.deepcopy(BOARD[:1])  # Ohio State-Purdue, in progress
    serve(sunday, monkeypatch, board)
    into(monkeypatch, db_conn)
    home = _team(db_conn, "cfb", "cfbd", "194", "Ohio State")
    away = _team(db_conn, "cfb", "cfbd", "2509", "Purdue")
    _game(db_conn, "401790001", home, away)
    _contest(db_conn, ten_at_ind(db_conn))

    code, text_ = job(tmp_path)

    assert code == 0
    assert "### `scores` 2026 → live" in text_
    assert "- CFBD calls this run: 1" in text_
    assert f"- CFBD calls in 2026-10: 42/{MONTHLY_LIMIT}" in text_
    assert "- CFB games updated: 1 (1 in progress, 0 final)" in text_
    assert "- NFL games updated: 1 (a contest's NFL game is live; nflverse pulled)" in text_


def test_an_nfl_only_run_says_so(
    sunday: LocalLake, monkeypatch: pytest.MonkeyPatch, db_conn: Connection, tmp_path: Path
) -> None:
    live(monkeypatch)
    serve(sunday, monkeypatch)
    into(monkeypatch, db_conn)
    code, text_ = job(tmp_path, "--sport", "nfl")
    assert code == 0
    assert "- CFBD calls this run: 0" in text_
    assert "- CFB: not pulled (an NFL-only run)" in text_
    assert "- NFL: no contest NFL game is live; nflverse not pulled" in text_


def test_the_budget_exits_3_without_publishing(
    r2: LocalLake, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    live(monkeypatch)
    r2.write_text("cfbd_calls.json", json.dumps({"2026-10": MONTHLY_LIMIT}))
    requests = serve(r2, monkeypatch)

    def refuse(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("over budget: the database is never opened")

    monkeypatch.setattr(scores, "make_engine", refuse)
    code, text_ = job(tmp_path)
    assert code == 3
    assert requests == []
    assert r2.walk("raw/cfbd/scoreboard") == []
    assert f"- CFBD calls in 2026-10: {MONTHLY_LIMIT}/{MONTHLY_LIMIT}" in text_


def test_a_failed_nflverse_download_keeps_the_cfb_updates_and_exits_1(
    sunday: LocalLake, monkeypatch: pytest.MonkeyPatch, db_conn: Connection, tmp_path: Path
) -> None:
    live(monkeypatch)
    serve(sunday, monkeypatch, copy.deepcopy(BOARD[:1]))
    into(monkeypatch, db_conn)
    home = _team(db_conn, "cfb", "cfbd", "194", "Ohio State")
    away = _team(db_conn, "cfb", "cfbd", "2509", "Purdue")
    _game(db_conn, "401790001", home, away)
    _contest(db_conn, ten_at_ind(db_conn))

    def fail(http: httpx.Client | None = None) -> str:
        raise httpx.ConnectError("github.com unreachable")

    monkeypatch.setattr(nflverse, "download", fail)
    code, text_ = job(tmp_path)
    assert code == 1
    assert games(db_conn)[0] == ("401790001", "in_progress", 24, 3, 3, "09:12")
    assert tuple(db_conn.execute(NFL_GAME).one()) == ("scheduled", None, None)
    assert "**NFL (nflverse) download failed:** ConnectError: github.com unreachable" in text_


@pytest.mark.parametrize("sport", ["all", "nfl"])
def test_production_behind_the_code_exits_4_before_anything(
    r2: LocalLake,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    stamped_url: Callable[[str | None], str],
    sport: str,
) -> None:
    """TASK-076: a production schema older than the code's migrations stops the run before the
    CFBD call, nflverse or a write (on 2026-11-24 it was missing the clock columns this job
    writes)."""
    script = script_directory()
    below_head = script.get_revision(single_head(script)).down_revision
    assert isinstance(below_head, str)
    requests = serve(r2, monkeypatch)

    def refuse(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("the job went past the schema guard")

    monkeypatch.setattr(scores, "make_engine", refuse)
    monkeypatch.setattr(nflverse, "download", refuse)
    monkeypatch.setenv("LIVE", "true")
    monkeypatch.setenv("PRODUCTION_DATABASE_URL_UNPOOLED", stamped_url(below_head))

    code, text_ = job(tmp_path, "--sport", sport)

    assert code == 4
    assert requests == []
    assert ledger(r2) == {}
    assert r2.walk("raw") == []
    assert f"**Nothing run:** production's schema is at `{below_head}`" in text_
    assert "Run the release workflow" in text_
    assert "CFBD calls this run" not in text_


def test_the_job_refuses_production_without_live(
    r2: LocalLake, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    requests = serve(r2, monkeypatch)
    monkeypatch.setenv("PRODUCTION_DATABASE_URL_UNPOOLED", PROD)
    code, _ = job(tmp_path)
    assert code == 2
    assert requests == []


def test_sport_is_the_scores_jobs_alone(r2: LocalLake) -> None:
    assert engine("job", "lines", "--target", "dev", "--sport", "nfl") == 2


# ─── AC-5: the workflow ───────────────────────────────────────────────────────────────────────


def test_the_workflow_dispatches_in_the_publish_group_with_no_fallback() -> None:
    wf = WORKFLOW.read_text("utf-8")
    assert re.search(r"^on:\n  workflow_dispatch:\n", wf, re.M)
    assert "schedule:" not in wf  # no late fallback for a 30-minute job (D-122)
    concurrency = r"^concurrency:\n  group: lake-publish\n  cancel-in-progress: false$"
    assert re.search(concurrency, wf, re.M)
    minutes = re.search(r"timeout-minutes: (\d+)", wf)
    assert minutes and int(minutes.group(1)) <= 10
    assert 'LIVE: "true"' in wf
    assert "--no-dev" not in wf  # the engine needs the dev group (D-114)
    secrets = ("CFBD_API_KEY", "R2_DATA_LAKE_ACCESS_KEY_ID", "PRODUCTION_DATABASE_URL_UNPOOLED")
    for secret in secrets:
        assert re.search(rf"^\s+{secret}: \$\{{\{{ secrets\.{secret} \}}\}}$", wf, re.M), secret
    step = re.search(
        r"^\s+run: (uv --directory target/python run engine job scores .*)$", wf, re.M
    )
    assert step, "no engine job scores step"
    assert "--target live" in step.group(1)
    assert "--sport ${{ inputs.sport }}" in step.group(1)
    assert re.search(r"^      sport:\n(        .*\n)*        default: all$", wf, re.M)


def test_each_scoreboard_status_maps_to_one_write() -> None:
    """The mapping in isolation: scheduled writes nothing."""
    by_id = {u.source_id: u for u in scores.updates(BOARD)[0]}
    assert set(by_id) == {"401790001", "401790002", "401790004", "401790005"}
    assert by_id["401790001"].status == "in_progress"
    assert by_id["401790002"] == scores.Update("401790002", "final", 31, 24, None, None)


def test_a_game_listed_twice_writes_its_last_record() -> None:
    """Schema review: UPDATE … FROM with two rows for one game would apply either; the job
    sends one, the scoreboard's last."""
    later = finished(BOARD)[0]
    writes, _ = scores.updates([BOARD[0], later])
    assert writes == [scores.Update("401790001", "final", 38, 10, None, None)]
