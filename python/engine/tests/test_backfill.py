"""`engine backfill` and `engine lake sync` (TASK-021): the dry run, the budget stop and resume,
the season-level final rule, and copying raw files between lakes. CFBD is an httpx.MockTransport
serving a small world: each season has 15 regular weeks with one game each and one bowl."""

import json
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest
from lake_fixture import engine

from engine.ingest import backfill, endpoints
from engine.ingest.cfbd import CallBudget, CfbdClient
from engine.ingest.endpoints import pull, saved_final
from engine.ingest.lake import LocalLake, encode_raw, raw_folder, raw_key

LEDGER = "cfbd_calls.json"
NOW = datetime(2016, 3, 1, 12, tzinfo=UTC)  # after the 2015 bowls
# Per season: 3 (games x2, calendar) + 16 weeks x 3 + 11 season-level; venues and conferences once.
ESTIMATE = 2 * (3 + 16 * 3 + 11) + 2


@pytest.fixture(autouse=True)
def clock(monkeypatch: pytest.MonkeyPatch) -> None:
    """NOW for every module, and a pull clock that ticks a minute per saved file, so files saved
    in one run never share a timestamp. CFBD can't be reached without the fakes below."""
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("FIXTURE_NOW", NOW.isoformat())
    monkeypatch.setenv("CFBD_API_KEY", "")
    ticks: Iterator[int] = iter(range(10_000))
    monkeypatch.setattr(endpoints, "now", lambda: NOW + timedelta(minutes=next(ticks)))


def week_start(season: int, week: int) -> str:
    return (datetime(season, 9, 1, tzinfo=UTC) + timedelta(weeks=week - 1)).isoformat()


def world(request: httpx.Request) -> Any:
    """CFBD's answer for one request: every game completed, every other endpoint non-empty."""
    params = request.url.params
    path = request.url.path
    year = int(params.get("year", "2015"))
    if path == "/games":
        if params["seasonType"] == "postseason":
            return [
                {
                    "id": year * 100,
                    "week": 1,
                    "seasonType": "postseason",
                    "completed": True,
                    "startDate": f"{year + 1}-01-01T20:00:00+00:00",
                }
            ]
        return [
            {
                "id": year * 100 + w,
                "week": w,
                "seasonType": "regular",
                "completed": True,
                "startDate": week_start(year, w),
            }
            for w in range(1, 16)
        ]
    if path == "/calendar":
        return [
            {
                "season": year,
                "week": w,
                "seasonType": "regular",
                "startDate": week_start(year, w),
                "endDate": week_start(year, w + 1),
            }
            for w in range(1, 16)
        ] + [
            {
                "season": year,
                "week": 1,
                "seasonType": "postseason",
                "startDate": f"{year}-12-15T00:00:00+00:00",
                "endDate": f"{year + 1}-01-15T00:00:00+00:00",
            }
        ]
    return [{"id": 1}]


def fake_client(lake: LocalLake, requests: list[str], limit: int = 5000) -> CfbdClient:
    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(f"{request.url.path}?{request.url.params}")
        return httpx.Response(200, json=world(request))

    http = httpx.Client(base_url="https://cfbd.test", transport=httpx.MockTransport(handler))
    return CfbdClient("key", CallBudget(lake, limit), http)


def use_client(monkeypatch: pytest.MonkeyPatch, client: CfbdClient) -> None:
    monkeypatch.setattr(backfill, "client_for", lambda _lake: client)


def refuse_clients(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*_args: Any, **_kwargs: Any) -> CfbdClient:
        raise AssertionError("a dry run must not construct a CFBD client")

    monkeypatch.setattr(backfill, "client_for", refuse)
    monkeypatch.setattr(endpoints, "CfbdClient", refuse)


def ledger_total(lake: LocalLake) -> int:
    return sum(json.loads(lake.read_text(LEDGER) or "{}").values())


def dry_run_total(out: str) -> int:
    (line,) = [line for line in out.splitlines() if line.strip().startswith("total")]
    return int(line.split()[1])


# AC-1: the dry run


def test_dry_run_counts_missing_pulls_without_calls(
    empty_lake: LocalLake, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    refuse_clients(monkeypatch)

    assert engine("backfill", "--from", "2014", "--to", "2015", "--dry-run") == 0

    out = capsys.readouterr().out
    assert dry_run_total(out) == ESTIMATE
    for name, calls in [("plays", 32), ("games", 4), ("lines", 4), ("venues", 1), ("teams", 2)]:
        assert f"  {name:<20} {calls:>5}" in out, name
    assert "96 estimated" in out  # 2 seasons x 16 weeks x 3, no saved /games file yet
    assert empty_lake.read_text(LEDGER) is None
    assert empty_lake.walk("raw") == []


def test_dry_run_after_partial_run_counts_the_rest(
    empty_lake: LocalLake, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    requests: list[str] = []
    use_client(monkeypatch, fake_client(empty_lake, requests))
    assert engine("backfill", "--from", "2014", "--to", "2015", "--max-calls", "40") == 3
    assert len(requests) == 40
    capsys.readouterr()

    refuse_clients(monkeypatch)
    assert engine("backfill", "--from", "2014", "--to", "2015", "--dry-run") == 0

    out = capsys.readouterr().out
    assert dry_run_total(out) == ESTIMATE - 40
    assert "48 estimated" in out  # only 2015's weeks are still unknown


# AC-2: stop before the budget runs out, then resume without re-fetching


def test_budget_stop_then_resume_matches_estimate(
    empty_lake: LocalLake, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    refuse_clients(monkeypatch)
    engine("backfill", "--from", "2014", "--to", "2015", "--dry-run")
    estimate = dry_run_total(capsys.readouterr().out)

    requests: list[str] = []
    use_client(monkeypatch, fake_client(empty_lake, requests, limit=50))
    assert engine("backfill", "--from", "2014", "--to", "2015") == 3
    out = capsys.readouterr().out
    assert len(requests) == 50
    assert ledger_total(empty_lake) == 50  # the refused 51st call isn't counted
    assert f"Stopped by the CFBD budget. Left: {estimate - 50} calls" in out

    use_client(monkeypatch, fake_client(empty_lake, requests))
    assert engine("backfill", "--from", "2014", "--to", "2015") == 0

    assert ledger_total(empty_lake) == estimate
    assert len(requests) == estimate
    assert len(set(requests)) == len(requests)  # no query was sent twice
    use_client(monkeypatch, fake_client(empty_lake, requests))
    assert engine("backfill", "--from", "2014", "--to", "2015") == 0
    assert len(requests) == estimate  # a third run finds everything final


def test_run_pulls_no_week_without_a_saved_games_file(
    empty_lake: LocalLake, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Mid-December of the current season, the calendar pulled in stage 1 shows the postseason
    started, but no postseason /games file was pulled: its weeks are only an estimate."""
    monkeypatch.setenv("FIXTURE_NOW", "2015-12-20T12:00:00+00:00")
    requests: list[str] = []
    use_client(monkeypatch, fake_client(empty_lake, requests))

    assert engine("backfill", "--from", "2015", "--to", "2015") == 0

    weekly = [r for r in requests if r.split("?")[0] in ("/games/teams", "/plays", "/drives")]
    assert len(weekly) == 15 * 3
    assert not [r for r in weekly if "postseason" in r]


# Rule C: when a season-level file is final


def save(
    lake: LocalLake, name: str, at: datetime, records: Any, season_type: str = "regular"
) -> str:
    key = raw_key(raw_folder(name, 2015, None, season_type), at)
    lake.write_new(key, encode_raw(records, {"year": 2015}, at))
    return key


def season_games(season_type: str, completed: bool = True) -> list[dict[str, Any]]:
    start = "2016-01-01T20:00:00+00:00" if season_type == "postseason" else week_start(2015, 1)
    return [
        {"id": 1, "week": 1, "seasonType": season_type, "completed": completed, "startDate": start}
    ]


def calls_for(lake: LocalLake, name: str, season_type: str = "regular") -> int:
    requests: list[str] = []
    pull(lake, name, 2015, None, season_type, client=fake_client(lake, requests))
    return len(requests)


def test_season_file_final_after_season_completes(tmp_path: Path) -> None:
    lake = LocalLake(tmp_path)
    jan = datetime(2016, 1, 10, tzinfo=UTC)  # 9 days after the bowl
    save(lake, "games", jan, season_games("regular"))
    save(lake, "lines", jan + timedelta(hours=1), [{"id": 1}])
    save(lake, "teams", jan + timedelta(hours=1), [{"id": 1}])

    assert calls_for(lake, "games") == 0  # every game of the season type completed
    assert calls_for(lake, "lines") == 0  # saved after a /games file showing that
    assert calls_for(lake, "teams") == 1  # no season type: waits for the postseason

    save(lake, "games", jan, season_games("postseason"), "postseason")
    save(lake, "teams", jan + timedelta(hours=2), [{"id": 1}])
    assert calls_for(lake, "teams") == 0


def test_season_file_saved_before_the_games_completed_is_fetched_again(tmp_path: Path) -> None:
    lake = LocalLake(tmp_path)
    jan = datetime(2016, 1, 5, tzinfo=UTC)
    # Saved two days after the game's start, unscored: not played yet, so not done.
    save(lake, "games", datetime(2015, 9, 3, tzinfo=UTC), season_games("regular", completed=False))
    save(lake, "lines", jan - timedelta(days=1), [{"id": 1}])
    save(lake, "games", jan, season_games("regular"))

    assert calls_for(lake, "lines") == 1  # the only complete /games file is newer than it


def test_season_file_saved_just_after_the_last_game_is_not_final(tmp_path: Path) -> None:
    # A pull the morning after the bowl may not hold every game yet, empty or not.
    lake = LocalLake(tmp_path)
    last_game = datetime(2016, 1, 1, 20, tzinfo=UTC)
    games = save(
        lake, "games", last_game + timedelta(hours=6), season_games("postseason"), "postseason"
    )
    save(lake, "ratings_sp", last_game + timedelta(days=1), [{"id": 1}])
    save(lake, "stats_game_advanced", last_game + timedelta(days=1), [{"id": 1}], "postseason")
    assert saved_final(lake, "ratings_sp", 2015) is None
    assert saved_final(lake, "stats_game_advanced", 2015, None, "postseason") is None
    assert saved_final(lake, "games", 2015, None, "postseason") == games  # /games itself

    settled = save(lake, "ratings_sp", last_game + timedelta(days=7), [{"id": 1}])
    assert saved_final(lake, "ratings_sp", 2015) == settled


def test_empty_season_file_final_after_seven_days(tmp_path: Path) -> None:
    lake = LocalLake(tmp_path)
    last_game = datetime(2016, 1, 1, 20, tzinfo=UTC)
    save(lake, "games", last_game + timedelta(days=1), season_games("postseason"), "postseason")
    save(lake, "stats_game_advanced", last_game + timedelta(days=6), [], "postseason")
    assert calls_for(lake, "stats_game_advanced", "postseason") == 1

    save(lake, "stats_game_advanced", last_game + timedelta(days=7), [], "postseason")
    assert calls_for(lake, "stats_game_advanced", "postseason") == 0


def canceled(start: datetime) -> dict[str, Any]:
    """CFBD keeps a canceled game (App State-Liberty 2024, Hurricane Helene) unscored and
    uncompleted forever."""
    return {
        "id": 2,
        "week": 1,
        "seasonType": "regular",
        "completed": False,
        "homePoints": None,
        "awayPoints": None,
        "startDate": start.isoformat(),
    }


def test_a_canceled_game_settles_after_seven_days(tmp_path: Path) -> None:
    lake = LocalLake(tmp_path)
    start = datetime(2015, 9, 5, 19, tzinfo=UTC)
    games = [*season_games("regular"), canceled(start)]

    def save_week(at: datetime) -> str:
        key = raw_key(raw_folder("plays", 2015, 1), at)
        lake.write_new(key, encode_raw([{"id": 1}], {"year": 2015, "week": 1}, at))
        return key

    save(lake, "games", start + timedelta(days=6), games)
    save(lake, "lines", start + timedelta(days=6, hours=1), [{"id": 1}])
    save_week(start + timedelta(days=6, hours=1))
    # Six days on, the game may still be played: nothing is final.
    assert saved_final(lake, "games", 2015) is None
    assert saved_final(lake, "lines", 2015) is None
    assert saved_final(lake, "plays", 2015, 1) is None

    games_key = save(lake, "games", start + timedelta(days=7), games)
    lines = save(lake, "lines", start + timedelta(days=7, hours=1), [{"id": 1}])
    plays = save_week(start + timedelta(days=7, hours=1))
    assert saved_final(lake, "games", 2015) == games_key
    assert saved_final(lake, "lines", 2015) == lines
    assert saved_final(lake, "plays", 2015, 1) == plays


# AC-5: the R2 lake and the local mirror hold the same raw files


def test_sync_copies_missing_both_ways_never_overwrites(tmp_path: Path) -> None:
    r2, local = LocalLake(tmp_path / "r2"), LocalLake(tmp_path / "local")
    at = datetime(2016, 1, 5, tzinfo=UTC)
    only_r2 = save(r2, "teams", at, [{"id": 1}])
    both = save(r2, "talent", at, [{"id": 1}])
    local.write_new(both, encode_raw([{"id": 2}], {"year": 2015}, at))
    only_local = save(local, "calendar", at, [{"id": 3}])
    r2.write_text(LEDGER, "{}")
    r2.replace("staging/games.parquet", b"derived")

    assert backfill.sync_raw(r2, local) == [only_r2]
    assert backfill.sync_raw(local, r2) == [only_local]

    assert r2.walk("raw/cfbd") == local.walk("raw/cfbd") == sorted([only_r2, both, only_local])
    assert local.read(both) != r2.read(both)  # an existing file is never overwritten
    assert local.read_text(LEDGER) is None
    assert local.walk("staging") == []


def test_sync_raw_season_filter(tmp_path: Path) -> None:
    r2, scratch = LocalLake(tmp_path / "r2"), LocalLake(tmp_path / "scratch")
    at = datetime(2016, 1, 5, tzinfo=UTC)
    keep = save(r2, "teams", at, [{"id": 1}])  # season 2015
    other = raw_key(raw_folder("teams", 2014), at)
    r2.write_new(other, encode_raw([{"id": 1}], {"year": 2014}, at))

    assert backfill.sync_raw(r2, scratch, seasons={2015}) == [keep]
    assert scratch.walk("raw") == [keep]


def test_lake_sync_cli_copies_one_way(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(backfill, "client_for", lambda _lake: pytest.fail("sync makes no calls"))
    r2, local = LocalLake(tmp_path / "r2"), LocalLake(tmp_path / "local")
    key = save(r2, "teams", datetime(2016, 1, 5, tzinfo=UTC), [{"id": 1}])

    assert (
        engine("lake", "sync", "--from", str(tmp_path / "r2"), "--to", str(tmp_path / "local")) == 0
    )

    assert local.walk("raw") == [key]
    assert "Copied 1 raw file" in capsys.readouterr().out
