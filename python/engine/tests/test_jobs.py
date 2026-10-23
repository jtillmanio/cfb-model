"""`engine job results|lines` and their workflows (TASK-022): which weeks a job pulls, staging the
season in a scratch lake, never publishing past a failed check, and the workflow files' triggers.
CFBD is an httpx.MockTransport serving the lake fixture's 2025 week-1 records; Postgres is faked,
since publishing itself is TASK-020's (test_publish_staging.py)."""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest
from lake_fixture import FIXTURE, engine, write_fixture

from db.config import repo_root
from engine import jobs
from engine.ingest import backfill
from engine.ingest.cfbd import CallBudget, CfbdClient
from engine.ingest.endpoints import ENDPOINTS
from engine.ingest.lake import LocalLake

SUNDAY = "2025-08-24T10:00:00Z"  # 06:00 ET, the morning after the fixture's week-1 games
PROD = "postgresql://jobs:secret@ep-prod.example.neon.tech/cfb"
WORKFLOWS = repo_root() / ".github" / "workflows"
# The fixture's week-1 files a job pulls: written by the fake CFBD instead.
PULLED = {"games", "games_teams", "stats_game_advanced", "plays", "drives", "lines"}


def records(endpoint: str) -> list[Any]:
    (raw,) = [v for k, v in FIXTURE.items() if k.startswith(f"raw/cfbd/{endpoint}/")]
    return raw["records"]


PATHS = {e.path: name for name, e in ENDPOINTS.items()}


@pytest.fixture
def r2(empty_lake: LocalLake, monkeypatch: pytest.MonkeyPatch) -> LocalLake:
    """The shared lake: the fixture minus the files the job pulls, on the Sunday after week 1."""
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("FIXTURE_NOW", SUNDAY)
    monkeypatch.setenv("CFBD_API_KEY", "")
    write_fixture(
        empty_lake,
        {k: v for k, v in FIXTURE.items() if k.split("/")[2] not in PULLED},
    )
    return empty_lake


def serve(
    lake: LocalLake, monkeypatch: pytest.MonkeyPatch, games: Callable[[list[Any]], list[Any]]
) -> list[str]:
    """Route the job's CFBD client to the fixture's records, `/games` passed through `games`."""
    requests: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        name = PATHS[request.url.path]
        requests.append(f"{name} week={request.url.params.get('week')}")
        body = games(records("games")) if name == "games" else records(name)
        return httpx.Response(200, json=body)

    http = httpx.Client(base_url="https://cfbd.test", transport=httpx.MockTransport(handler))
    client = CfbdClient("key", CallBudget(lake), http)
    monkeypatch.setattr(backfill, "client_for", lambda _lake: client)
    return requests


class Published:
    def __init__(self) -> None:
        self.staging: list[str] = []
        self.opened: list[str] = []


def fake_postgres(monkeypatch: pytest.MonkeyPatch, published: Published) -> None:
    @contextmanager
    def begin() -> Iterator[str]:
        yield "conn"

    class Engine:
        def begin(self) -> Any:
            return begin()

    def make_engine(url: str) -> Engine:
        published.opened.append(url)
        return Engine()

    def publish_lake(lake: LocalLake, conn: str, *, report: Any) -> dict[str, int]:
        assert report.ok
        published.staging = lake.walk("staging")
        return {"teams": 9, "games": 5, "line_snapshots": 12}

    monkeypatch.setattr(jobs, "make_engine", make_engine)
    monkeypatch.setattr(jobs, "publish_lake", publish_lake)


def refuse_postgres(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("a failed check must stop the job before Postgres")

    monkeypatch.setattr(jobs, "make_engine", refuse)
    monkeypatch.setattr(jobs, "publish_lake", refuse)


def live(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LIVE", "true")
    monkeypatch.setenv("PRODUCTION_DATABASE_URL_UNPOOLED", PROD)


def ledger(lake: LocalLake) -> dict[str, int]:
    return json.loads(lake.read_text("cfbd_calls.json") or "{}")


# AC-2: ingest → transform → check → publish, and a failed check never publishes


def test_failed_check_never_publishes(
    r2: LocalLake, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def unscored_final(games: list[Any]) -> list[Any]:
        return [{**games[0], "homePoints": None}, *games[1:]]

    serve(r2, monkeypatch, unscored_final)
    refuse_postgres(monkeypatch)
    live(monkeypatch)
    summary = tmp_path / "summary.md"

    assert engine("job", "results", "--target", "live", "--summary", str(summary)) == 1

    text = summary.read_text(encoding="utf-8")
    assert "Nothing published" in text
    assert "FAIL final_has_score" in text
    assert r2.walk("staging") == []


def test_job_publishes_scratch_staging_under_live(
    r2: LocalLake, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    requests = serve(r2, monkeypatch, lambda games: games)
    published = Published()
    fake_postgres(monkeypatch, published)
    live(monkeypatch)
    summary = tmp_path / "summary.md"

    assert engine("job", "results", "--target", "live", "--summary", str(summary)) == 0

    # The season /games file was missing, then the week's six endpoints, /games first.
    assert requests == [
        "games week=None",
        *(f"{name} week=1" for name in jobs.PULLS["results"]),
    ]
    assert ledger(r2) == {"2025-08": 7}
    assert published.opened == [PROD]
    assert "staging/games.parquet" in published.staging
    assert r2.walk("staging") == []  # the shared lake's staging/ is never written
    text = summary.read_text(encoding="utf-8")
    assert "CFBD calls this run: 7" in text
    assert "CFBD calls in 2025-08: 7/5000" in text
    assert "| teams | 10 | 9 |" in text  # /games fills in a team /teams lacks
    assert "| line_snapshots |" in text


def test_a_second_run_reuses_final_files(
    r2: LocalLake, monkeypatch: pytest.MonkeyPatch
) -> None:
    requests = serve(r2, monkeypatch, lambda games: games)
    fake_postgres(monkeypatch, Published())
    live(monkeypatch)
    assert engine("job", "results", "--target", "live") == 0
    monkeypatch.setenv("FIXTURE_NOW", "2025-08-25T10:00:00Z")  # Monday: the week has settled
    assert engine("job", "results", "--target", "live") == 0
    assert engine("job", "results", "--target", "live") == 0

    week_pulls = [r for r in requests if r.endswith("week=1")]
    assert len(week_pulls) == 2 * len(jobs.PULLS["results"])  # Sunday's and Monday's, not the third


def test_lines_pulls_next_unplayed_week(r2: LocalLake, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FIXTURE_NOW", "2025-08-21T23:00:00Z")  # Thursday 19:00 ET

    def scheduled(games: list[Any]) -> list[Any]:
        return [
            {**g, "completed": False, "homePoints": None, "awayPoints": None} for g in games
        ]

    requests = serve(r2, monkeypatch, scheduled)
    fake_postgres(monkeypatch, Published())
    live(monkeypatch)

    assert engine("job", "lines", "--target", "live") == 0
    assert requests == ["games week=None", "games week=1", "lines week=1"]


def test_a_job_refuses_production_without_live(
    r2: LocalLake, monkeypatch: pytest.MonkeyPatch
) -> None:
    serve(r2, monkeypatch, lambda games: games)
    refuse_postgres(monkeypatch)
    monkeypatch.setenv("PRODUCTION_DATABASE_URL_UNPOOLED", PROD)
    assert engine("job", "results", "--target", "live") == 2
    assert ledger(r2) == {}


# E: which weeks a job pulls


def game(week: int, start: datetime, season_type: str = "regular") -> dict[str, Any]:
    return {"id": week, "week": week, "seasonType": season_type, "startDate": start.isoformat()}


def test_results_pulls_unsettled_weeks_in_last_14_days() -> None:
    now = datetime(2025, 9, 7, 10, tzinfo=UTC)  # Sunday after week 2
    games = [
        game(0, now - timedelta(days=20)),
        game(1, now - timedelta(days=13)),  # Labor Day Monday: a week whose Sunday run was early
        game(2, now - timedelta(hours=12)),
        game(3, now + timedelta(days=5)),
    ]
    assert jobs.due_weeks("results", games, now) == [("regular", 1), ("regular", 2)]


def test_results_keeps_pulling_the_bowl_week() -> None:
    now = datetime(2026, 1, 4, 11, tzinfo=UTC)
    bowls = [
        {**game(1, datetime(2025, 12, 13, tzinfo=UTC), "postseason"), "id": 10},
        {**game(1, datetime(2026, 1, 1, tzinfo=UTC), "postseason"), "id": 11},
        {**game(1, datetime(2026, 1, 19, tzinfo=UTC), "postseason"), "id": 12},
    ]
    assert jobs.due_weeks("results", bowls, now) == [("postseason", 1)]
    assert jobs.due_weeks("lines", bowls, now) == [("postseason", 1)]
    assert jobs.current_season(now) == 2025


def test_lines_picks_the_earliest_week_not_kicked_off() -> None:
    now = datetime(2025, 11, 30, 13, tzinfo=UTC)
    games = [
        game(14, now - timedelta(days=1)),
        game(15, now + timedelta(days=6)),
        {**game(1, now + timedelta(days=20), "postseason"), "id": 99},
    ]
    assert jobs.due_weeks("lines", games, now) == [("regular", 15)]


def test_canceled_lists_unscored_games_counted_as_done() -> None:
    start = datetime(2025, 10, 4, 16, tzinfo=UTC)
    played = {**game(6, start), "completed": True, "homePoints": 21, "awayPoints": 7}
    unplayed = {**game(6, start), "id": 7, "completed": False, "homeTeam": "A", "awayTeam": "B"}
    later = start + timedelta(days=8)
    assert jobs.canceled([(played, later), (unplayed, later)]) == [
        f"7: B at A, regular week 6, started {start.isoformat()}"
    ]
    assert jobs.canceled([(unplayed, start + timedelta(days=2))]) == []


# AC-1: the workflows


def workflow(name: str) -> str:
    return (WORKFLOWS / name).read_text(encoding="utf-8")


@pytest.mark.parametrize("name", ["results.yml", "lines.yml"])
def test_workflows_dispatch_schedule_and_share_concurrency(name: str) -> None:
    text = workflow(name)
    assert re.search(r"^on:\n  workflow_dispatch:\n  schedule:\n", text, re.M)
    concurrency = r"^concurrency:\n  group: lake-publish\n  cancel-in-progress: false$"
    assert re.search(concurrency, text, re.M)
    assert "timeout-minutes: 10" in text
    assert 'LIVE: "true"' in text
    assert "--no-dev" not in text  # engine ingest needs the dev group (D-114)
    assert "uses: ./.github/actions/skip-if-dispatched" in text
    secrets = ("CFBD_API_KEY", "R2_DATA_LAKE_ACCESS_KEY_ID", "PRODUCTION_DATABASE_URL_UNPOOLED")
    for secret in secrets:
        assert re.search(rf"^\s+{secret}: \$\{{\{{ secrets\.{secret} \}}\}}$", text, re.M), secret


def crons(name: str) -> list[tuple[str, str]]:
    """Each schedule cron with the comment line above it."""
    lines = workflow(name).splitlines()
    return [
        (re.findall(r'cron: "([^"]+)"', line)[0], lines[i - 1])
        for i, line in enumerate(lines)
        if "cron:" in line
    ]


@pytest.mark.parametrize(
    ("name", "expected"),
    [("results.yml", ["0 12 * * 0,1"]), ("lines.yml", ["0 14 * * *", "0 1 * * 5,6"])],
)
def test_fallback_crons_have_dst_comment(name: str, expected: list[str]) -> None:
    found = crons(name)
    assert [cron for cron, _ in found] == expected
    for _, comment in found:
        assert re.search(r"#.*ET.*EDT.*EST", comment), comment
