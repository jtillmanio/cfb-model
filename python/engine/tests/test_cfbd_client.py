"""The CFBD client: the call budget, never re-fetching a completed week, and the endpoint
registry (D-027, D-112). No test opens a socket: CFBD is an httpx.MockTransport."""

import json
import re
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import httpx
import pytest

from db.config import repo_root
from engine import cli
from engine.ingest import endpoints, games
from engine.ingest.cfbd import BudgetExceededError, CallBudget, CfbdClient
from engine.ingest.endpoints import ENDPOINTS, pull
from engine.ingest.lake import LocalLake, encode_raw, raw_folder, raw_key
from engine.sports.cfb.games import map_games

FIXTURES = Path(__file__).parent / "fixtures"
GAMES = json.loads((FIXTURES / "cfbd_games_sample.json").read_text(encoding="utf-8"))
LEDGER = "cfbd_calls.json"


@pytest.fixture(autouse=True)
def isolated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A fixed clock, and no way to reach CFBD, the real lake or .env.local, even if the code
    under test ignores the fakes. An empty key is "set", so load_env can't fill it in."""
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("FIXTURE_NOW", "2025-09-02T12:00:00Z")
    monkeypatch.setenv("CFBD_API_KEY", "")
    monkeypatch.setenv("LAKE_URI", str(tmp_path / "env-lake"))
    monkeypatch.setattr(cli, "load_env", lambda: None)


def fake_cfbd(
    lake: LocalLake, response: Any = None
) -> tuple[CfbdClient, list[httpx.Request]]:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=[] if response is None else response)

    http = httpx.Client(base_url="https://cfbd.test", transport=httpx.MockTransport(handler))
    return CfbdClient("key", CallBudget(lake), http), requests


def save(lake: LocalLake, endpoint: str, week: int | None, at: datetime, records: Any) -> str:
    key = raw_key(raw_folder(endpoint, 2025, week), at)
    lake.write_new(key, encode_raw(records, {"year": 2025}, at))
    return key


def all_completed(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{**g, "completed": True} for g in records]


# AC-1: the budget


def test_the_4000th_call_is_counted_and_warns(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    lake = LocalLake(tmp_path)
    lake.write_text(LEDGER, json.dumps({"2025-09": 3999}))
    client, requests = fake_cfbd(lake)

    client.get("/calendar", {"year": 2025})

    assert json.loads(lake.read_text(LEDGER) or "{}") == {"2025-09": 4000}
    assert "4000/5000" in capsys.readouterr().out
    assert len(requests) == 1


def test_a_spent_budget_raises_before_any_request(tmp_path: Path) -> None:
    lake = LocalLake(tmp_path)
    lake.write_text(LEDGER, json.dumps({"2025-09": 5000}))
    client, requests = fake_cfbd(lake)

    with pytest.raises(BudgetExceededError, match="5000/5000"):
        client.get("/calendar", {"year": 2025})

    assert requests == []
    assert json.loads(lake.read_text(LEDGER) or "{}") == {"2025-09": 5000}


def test_the_ledger_sits_at_the_lake_root(tmp_path: Path) -> None:
    lake = LocalLake(tmp_path)
    client, _ = fake_cfbd(lake)
    client.get("/calendar", {"year": 2025})
    assert json.loads((tmp_path / LEDGER).read_text(encoding="utf-8")) == {"2025-09": 1}


# AC-3: a completed week is never fetched again


def test_a_completed_weeks_saved_file_is_used_without_a_call(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    lake = LocalLake(tmp_path)
    save(lake, "games", 1, datetime(2025, 9, 1, 8, tzinfo=UTC), all_completed(GAMES))
    lines = save(lake, "lines", 1, datetime(2025, 9, 1, 9, tzinfo=UTC), [{"id": 1}])
    lake.write_text(LEDGER, json.dumps({"2025-09": 7}))
    client, requests = fake_cfbd(lake)

    key = pull(lake, "lines", 2025, week=1, client=client)

    assert key == lines
    assert requests == []
    assert json.loads(lake.read_text(LEDGER) or "{}") == {"2025-09": 7}
    assert f"Using saved {lines}" in capsys.readouterr().out


def test_a_season_level_games_file_also_completes_the_week(tmp_path: Path) -> None:
    lake = LocalLake(tmp_path)
    week_2 = {**GAMES[0], "id": 9, "week": 2, "completed": False}
    save(lake, "games", None, datetime(2025, 9, 1, 8, tzinfo=UTC), [*all_completed(GAMES), week_2])
    lines = save(lake, "lines", 1, datetime(2025, 9, 1, 9, tzinfo=UTC), [{"id": 1}])
    client, requests = fake_cfbd(lake)

    assert pull(lake, "lines", 2025, week=1, client=client) == lines
    assert requests == []


def test_a_file_saved_before_the_games_completed_is_fetched_again(tmp_path: Path) -> None:
    lake = LocalLake(tmp_path)
    save(lake, "lines", 1, datetime(2025, 8, 30, 9, tzinfo=UTC), [{"id": 1}])
    save(lake, "games", 1, datetime(2025, 9, 1, 8, tzinfo=UTC), all_completed(GAMES))
    client, requests = fake_cfbd(lake, [{"id": 1}, {"id": 2}])

    key = pull(lake, "lines", 2025, week=1, client=client)

    assert len(requests) == 1
    assert key.endswith("fetched_at=2025-09-02T120000Z.parquet")


def test_an_empty_file_saved_after_the_week_completed_is_fetched_again(tmp_path: Path) -> None:
    # CFBD may not have filled the week in yet; a zero-row file must not freeze it forever.
    lake = LocalLake(tmp_path)
    save(lake, "games", 1, datetime(2025, 9, 1, 8, tzinfo=UTC), all_completed(GAMES))
    save(lake, "lines", 1, datetime(2025, 9, 1, 9, tzinfo=UTC), [])
    client, requests = fake_cfbd(lake, [{"id": 1}])

    pull(lake, "lines", 2025, week=1, client=client)

    assert len(requests) == 1


def test_a_week_with_an_unfinished_game_is_fetched_again(tmp_path: Path) -> None:
    lake = LocalLake(tmp_path)
    save(lake, "games", 1, datetime(2025, 9, 1, 8, tzinfo=UTC), GAMES)  # one game not completed
    client, requests = fake_cfbd(lake, all_completed(GAMES))

    pull(lake, "games", 2025, week=1, client=client)

    assert len(requests) == 1


def test_a_completed_games_week_is_used_without_a_call(tmp_path: Path) -> None:
    lake = LocalLake(tmp_path)
    saved = save(lake, "games", 1, datetime(2025, 9, 1, 8, tzinfo=UTC), all_completed(GAMES))
    client, requests = fake_cfbd(lake)

    assert pull(lake, "games", 2025, week=1, client=client) == saved
    assert requests == []


def test_sunday_file_not_final_monday_file_final(tmp_path: Path) -> None:
    # The week's last kickoff is 2025-08-31 00:00 UTC: a file saved 10 hours later may be missing
    # plays or box scores CFBD fills in overnight, so only one saved 24 hours later is final.
    lake = LocalLake(tmp_path)
    save(lake, "games", 1, datetime(2025, 8, 31, 10, tzinfo=UTC), all_completed(GAMES))
    save(lake, "plays", 1, datetime(2025, 8, 31, 10, 5, tzinfo=UTC), [{"id": 1}])
    client, requests = fake_cfbd(lake, [{"id": 1}])

    pull(lake, "plays", 2025, week=1, client=client)
    pull(lake, "games", 2025, week=1, client=client)
    assert len(requests) == 2

    lake = LocalLake(tmp_path / "monday")
    games = save(lake, "games", 1, datetime(2025, 9, 1, 10, tzinfo=UTC), all_completed(GAMES))
    plays = save(lake, "plays", 1, datetime(2025, 9, 1, 10, 5, tzinfo=UTC), [{"id": 1}])
    client, requests = fake_cfbd(lake)

    assert pull(lake, "plays", 2025, week=1, client=client) == plays
    assert pull(lake, "games", 2025, week=1, client=client) == games
    assert requests == []


# AC-5: the registry and the CLI


def endpoints_in_03() -> set[str]:
    """Every `/path` in the first column of 03 › Data sources › CFBD's endpoint table."""
    doc = (repo_root() / "docs" / "03-data-model.md").read_text(encoding="utf-8")
    section = doc.split("### CollegeFootballData", 1)[1].split("\n### ", 1)[0]
    rows = [line for line in section.splitlines() if line.startswith("| `/")]
    return {path for row in rows for path in re.findall(r"`(/[^`]+)`", row.split("|")[1])}


# 03's "Granularity → calls" column, as pulled: name -> (path, granularity, required params).
EXPECTED = {
    "teams": ("/teams", "season", ("year",)),
    "teams_fbs": ("/teams/fbs", "season", ("year",)),
    "conferences": ("/conferences", "season", ()),
    "venues": ("/venues", "season", ()),
    "games": ("/games", "season_or_week", ("year",)),
    "games_teams": ("/games/teams", "week", ("year", "week")),
    "stats_game_advanced": ("/stats/game/advanced", "season_or_week", ("year",)),
    "plays": ("/plays", "week", ("year", "week")),
    "drives": ("/drives", "week", ("year", "week")),
    "lines": ("/lines", "season_or_week", ("year",)),
    "talent": ("/talent", "season", ("year",)),
    "player_returning": ("/player/returning", "season", ("year",)),
    "recruiting_teams": ("/recruiting/teams", "season", ("year",)),
    "ratings_sp": ("/ratings/sp", "season", ("year",)),
    "ratings_fpi": ("/ratings/fpi", "season", ("year",)),
    "ratings_elo": ("/ratings/elo", "season", ("year",)),
    "ppa_predicted": ("/ppa/predicted", "static", ("down", "distance")),
    "calendar": ("/calendar", "season", ("year",)),
    "scoreboard": ("/scoreboard", "season", ()),
}


@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_each_endpoint_names_its_path_params_and_granularity(name: str) -> None:
    endpoint = ENDPOINTS[name]
    assert (endpoint.path, endpoint.granularity, endpoint.required) == EXPECTED[name]


def test_registry_covers_every_endpoint_in_03() -> None:
    paths = endpoints_in_03()
    assert len(paths) == 19
    assert {e.path for e in ENDPOINTS.values()} == paths
    for name, endpoint in ENDPOINTS.items():
        assert endpoint.path.startswith("/"), name
        assert endpoint.granularity in {"season", "week", "season_or_week", "static"}, name
        assert isinstance(endpoint.required, tuple), name
        if endpoint.granularity == "week":
            assert {"year", "week"} <= set(endpoint.required), name
        if endpoint.granularity == "static":
            assert endpoint.required, name


def cli_args(name: str) -> list[str]:
    granularity = ENDPOINTS[name].granularity
    args = ["ingest", name, "--season", "2025"]
    if granularity == "week":
        args += ["--week", "3"]
    if granularity == "static":
        args += [arg for p in ENDPOINTS[name].required for arg in ("--param", f"{p}=1")]
    return args


def test_the_cli_accepts_every_registry_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    pulled: list[str] = []

    def fake_pull(_lake: Any, name: str, *_args: Any) -> str:
        pulled.append(name)
        return "key"

    # No dev DB: pytest reads only TEST_DATABASE_URL (CLAUDE.md).
    monkeypatch.setattr(cli, "direct_url", lambda _target: "postgresql://dev")
    monkeypatch.setattr(endpoints, "pull", fake_pull)
    monkeypatch.setattr(games, "ingest_games", lambda *_args: pulled.append("games"))
    for name in ENDPOINTS:
        cli.main(cli_args(name))
    assert sorted(pulled) == sorted(ENDPOINTS)


def test_the_cli_refuses_a_week_endpoint_without_a_week() -> None:
    with pytest.raises(SystemExit):
        cli.main(["ingest", "plays", "--season", "2025"])


@pytest.mark.parametrize(
    ("name", "param"),
    [("lines", "year=2019"), ("lines", "week=2"), ("games", "classification=fcs"),
     ("lines", "seasonType=postseason"), ("plays", "team=Ohio State")],
)
def test_the_cli_refuses_a_param_that_would_misfile_the_response(name: str, param: str) -> None:
    # The folder says season=2025/week=01: a query for anything else must not land there.
    with pytest.raises(SystemExit):
        cli.main(["ingest", name, "--season", "2025", "--week", "1", "--param", param])


def test_ingest_games_publishes_what_it_read_back_from_parquet(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    lake = LocalLake(tmp_path)
    reads: list[str] = []
    real_read = lake.read
    monkeypatch.setattr(lake, "read", lambda key: reads.append(key) or real_read(key))
    published: list[Any] = []

    @contextmanager
    def begin() -> Any:
        yield "conn"

    monkeypatch.setattr(games, "make_engine", lambda _url: SimpleNamespace(begin=begin))
    monkeypatch.setattr(
        games,
        "publish_games_batch",
        lambda conn, sport, source, batch: published.append((conn, sport, source, batch)) or 3,
    )
    client, requests = fake_cfbd(lake, GAMES)

    games.ingest_games(2025, 1, "regular", "postgresql://dev", lake=lake, client=client)

    assert len(requests) == 1
    assert requests[0].url.params["classification"] == "fbs"
    assert [k for k in reads if k.endswith(".parquet")] == [
        "raw/cfbd/games/season=2025/week=01/fetched_at=2025-09-02T120000Z.parquet"
    ]
    assert published == [("conn", "cfb", "cfbd", map_games(GAMES))]


def test_ingest_games_publishes_a_game_unscored_a_week_on_as_canceled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """TASK-044 (D-145): the dev ingest applies the transform's status rule with the saved file's
    time, so re-ingesting a week never turns a canceled game back to scheduled."""
    lake = LocalLake(tmp_path)
    published: list[Any] = []

    @contextmanager
    def begin() -> Any:
        yield "conn"

    monkeypatch.setattr(games, "make_engine", lambda _url: SimpleNamespace(begin=begin))
    monkeypatch.setattr(
        games,
        "publish_games_batch",
        lambda conn, sport, source, batch: published.append(batch) or 3,
    )
    # Unscored and uncompleted, started 8 days before the pull (the clock is 2025-09-02 12:00Z).
    week_old = {**GAMES[1], "startDate": "2025-08-25T04:00:00.000Z"}
    client, _ = fake_cfbd(lake, [GAMES[0], week_old, GAMES[2]])

    games.ingest_games(2025, 1, "regular", "postgresql://dev", lake=lake, client=client)

    (batch,) = published
    assert [g.status for g in batch.games] == ["final", "canceled", "final"]
