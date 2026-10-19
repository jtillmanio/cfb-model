"""`engine transform --rebuild` and `engine check` on a lake fixture of recorded CFBD responses
(TASK-017, D-116). No test opens a socket or a database.

`fixtures/lake.json` maps raw keys to `{params, records}`, trimmed from real 2025 pulls: five
week-1 games, their lines (plus Colgate-Monmouth, a game with no FBS team), /teams without Idaho
State and /venues without UNLV's stadium (both filled in from /games), and four calendar weeks.
"""

from __future__ import annotations

import copy
import io
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from engine import cli
from engine.ingest import cfbd
from engine.ingest.lake import LocalLake, encode_raw, fetched_at_of
from engine.sports.cfb.games import map_games
from engine.transform import TABLES, rebuild

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "lake.json").read_text("utf-8"))
GAMES_KEY = "raw/cfbd/games/season=2025/week=01/fetched_at=2025-09-02T120000Z.parquet"
LINES_KEY = "raw/cfbd/lines/season=2025/week=01/fetched_at=2026-10-18T061546Z.parquet"
NO_FBS_GAME = "401767256"  # Colgate-Monmouth: in /lines, not in /games
BOTH_FBS = "401756847"  # Kansas-Fresno State, 2025-08-23T22:30Z


def write(lake: LocalLake, key: str, records: list[Any], params: dict[str, Any]) -> None:
    lake.write_new(key, encode_raw(records, params, fetched_at_of(key)))


@pytest.fixture
def lake(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> LocalLake:
    monkeypatch.setenv("LAKE_URI", str(tmp_path))
    monkeypatch.delenv("LIVE", raising=False)
    monkeypatch.setattr(cli, "load_env", lambda: None)
    lake = LocalLake(tmp_path)
    for key, raw in FIXTURE.items():
        write(lake, key, raw["records"], raw["params"])
    return lake


def fixture_game(source_id: str) -> dict[str, Any]:
    games = FIXTURE[GAMES_KEY]["records"]
    return copy.deepcopy(next(g for g in games if str(g["id"]) == source_id))


def games_params(week: int) -> dict[str, Any]:
    return {"classification": "fbs", "seasonType": "regular", "week": week, "year": 2025}


def lines_params(week: int) -> dict[str, Any]:
    return {"seasonType": "regular", "week": week, "year": 2025}


def staged(lake: LocalLake, name: str) -> pa.Table:
    return pq.read_table(io.BytesIO(lake.read(f"staging/{name}.parquet")))


def by_id(table: pa.Table, column: str = "source_id") -> dict[str, dict[str, Any]]:
    return {row[column]: row for row in table.to_pylist()}


def engine(*argv: str) -> int:
    try:
        cli.main(list(argv))
    except SystemExit as e:
        return int(e.code or 0)
    return 0


def test_rebuild_stages_every_table_with_no_api_calls(
    lake: LocalLake, monkeypatch: pytest.MonkeyPatch
) -> None:
    def refuse(*_: Any, **__: Any) -> None:
        raise AssertionError("transform must not construct an API client")

    monkeypatch.setattr(cfbd.CfbdClient, "__init__", refuse)
    monkeypatch.setattr(httpx.Client, "__init__", refuse)
    monkeypatch.setattr(httpx.HTTPTransport, "__init__", refuse)

    counts = rebuild(lake)
    assert counts == {
        "games": 5,
        "teams": 10,  # 9 from /teams, Idaho State from /games
        "team_seasons": 10,
        "venues": 5,  # 4 from /venues, UNLV's from /games
        "calendar": 4,
        "lines": 14,  # the five games' 14 provider rows; Colgate-Monmouth's one is dropped
        "skipped_raw": 0,
    }
    assert set(counts) == set(TABLES)
    first = {name: lake.read(f"staging/{name}.parquet") for name in TABLES}

    assert engine("transform", "--rebuild") == 0
    for name in TABLES:
        assert staged(lake, name).equals(pq.read_table(io.BytesIO(first[name]))), name

    lines = staged(lake, "lines")
    assert NO_FBS_GAME not in lines.column("game_source_id").to_pylist()
    kansas = [r for r in lines.to_pylist() if r["game_source_id"] == BOTH_FBS]
    assert {r["provider"]: r["spread_home"] for r in kansas} == {
        "DraftKings": -14,
        "ESPN Bet": -14.5,
        "Bovada": -14,
    }
    assert {r["provider"]: r["spread_home_open"] for r in kansas}["ESPN Bet"] == -13.5

    games = by_id(staged(lake, "games"))
    for expected in map_games(FIXTURE[GAMES_KEY]["records"]).games:
        row = games[expected.source_id]
        for name, value in vars(expected).items():
            assert row[name] == value, (expected.source_id, name)
        assert row["closing_line_missing"] is False
        assert row["fetched_at"] == fetched_at_of(GAMES_KEY)

    teams = by_id(staged(lake, "teams"))
    assert teams["304"]["school"] == "Idaho State"
    assert teams["304"]["mascot"] is None
    assert teams["2305"]["mascot"] == "Jayhawks"
    assert by_id(staged(lake, "venues"))["6501"]["name"] == "Allegiant Stadium"
    calendar = staged(lake, "calendar").to_pylist()
    assert (calendar[0]["season_type"], calendar[0]["week"]) == ("postseason", 1)


def test_newest_pull_wins(lake: LocalLake) -> None:
    final = fixture_game(BOTH_FBS)
    scheduled = {**final, "completed": False, "homePoints": None, "awayPoints": None}
    # An earlier pull (before kickoff) and a later one (after it), the later one final.
    write(
        lake,
        "raw/cfbd/games/season=2025/week=01/fetched_at=2025-08-20T120000Z.parquet",
        [scheduled],
        games_params(1),
    )
    rebuild(lake)
    rows = [r for r in staged(lake, "games").to_pylist() if r["source_id"] == BOTH_FBS]
    assert len(rows) == 1
    assert (rows[0]["status"], rows[0]["home_points"], rows[0]["away_points"]) == ("final", 31, 7)

    write(  # a still later pull wins over the fixture's
        lake,
        "raw/cfbd/games/season=2025/fetched_at=2025-12-01T120000Z.parquet",
        [{**final, "homePoints": 30}],
        {"classification": "fbs", "seasonType": "regular", "year": 2025},
    )
    rebuild(lake)
    assert by_id(staged(lake, "games"))[BOTH_FBS]["home_points"] == 30


def test_rebuild_refuses_under_live(
    lake: LocalLake, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    lake.replace("staging/games.parquet", b"sentinel")
    monkeypatch.setenv("LIVE", "true")
    assert engine("transform", "--rebuild") == 2
    assert "LIVE" in capsys.readouterr().err
    assert lake.read("staging/games.parquet") == b"sentinel"
    assert lake.walk("staging") == ["staging/games.parquet"]


def test_check_passes_on_clean_fixture(
    lake: LocalLake, capsys: pytest.CaptureFixture[str]
) -> None:
    rebuild(lake)
    capsys.readouterr()
    assert engine("check") == 0
    out = capsys.readouterr().out
    assert "4 passed, 0 failed" in out
    assert "FAIL" not in out


def _bad_games(case: str) -> tuple[list[dict[str, Any]], list[str]]:
    if case == "final_no_score":
        game = {**fixture_game(BOTH_FBS), "id": 900000001, "homePoints": None}
        game["startDate"] = "2025-08-30T19:00:00.000Z"
        return [game], ["900000001"]
    twin = {**fixture_game(BOTH_FBS), "id": 900000002}
    # Same teams the other way round, same Eastern date.
    twin["homeId"], twin["awayId"] = twin["awayId"], twin["homeId"]
    return [twin], [BOTH_FBS, "900000002"]


@pytest.mark.parametrize("case", ["final_no_score", "duplicate"])
def test_check_names_bad_games(
    case: str, lake: LocalLake, capsys: pytest.CaptureFixture[str]
) -> None:
    records, offenders = _bad_games(case)
    write(
        lake,
        "raw/cfbd/games/season=2025/week=01/fetched_at=2025-09-03T120000Z.parquet",
        [*FIXTURE[GAMES_KEY]["records"], *records],
        games_params(1),
    )
    assert engine("transform", "--rebuild") == 1
    out = capsys.readouterr().out
    check = "final_has_score" if case == "final_no_score" else "no_duplicate_games"
    assert f"FAIL {check}" in out
    for source_id in offenders:
        assert source_id in out.split(f"FAIL {check}")[1].split("PASS")[0]

    capsys.readouterr()
    assert engine("check") == 1
    assert f"FAIL {check}" in capsys.readouterr().out


def _week_game(source_id: int, week: int, start: str) -> dict[str, Any]:
    game = {**fixture_game(BOTH_FBS), "id": source_id, "week": week, "startDate": start}
    return game


def test_marked_missing_line_passes(lake: LocalLake, capsys: pytest.CaptureFixture[str]) -> None:
    x = _week_game(900000010, 2, "2025-09-06T19:00:00.000Z")
    write(
        lake,
        "raw/cfbd/games/season=2025/week=02/fetched_at=2025-09-08T120000Z.parquet",
        [x],
        games_params(2),
    )
    # A /lines pull after X's kickoff that covers week 2 but quotes nothing for X.
    write(
        lake,
        "raw/cfbd/lines/season=2025/week=02/fetched_at=2025-09-08T120000Z.parquet",
        [{**FIXTURE[LINES_KEY]["records"][0], "id": 900000099}],
        lines_params(2),
    )
    assert engine("transform", "--rebuild") == 0
    assert by_id(staged(lake, "games"))["900000010"]["closing_line_missing"] is True
    out = capsys.readouterr().out
    assert "PASS closing_line" in out
    assert "900000010" in out.split("PASS closing_line")[1]


def test_unmarked_missing_line_fails(lake: LocalLake, capsys: pytest.CaptureFixture[str]) -> None:
    y = _week_game(900000020, 3, "2025-09-13T19:00:00.000Z")
    write(
        lake,
        "raw/cfbd/games/season=2025/week=03/fetched_at=2025-09-15T120000Z.parquet",
        [y],
        games_params(3),
    )
    # Week 3's only /lines pull is from before Y's kickoff, so nothing marks it.
    write(
        lake,
        "raw/cfbd/lines/season=2025/week=03/fetched_at=2025-09-10T120000Z.parquet",
        [],
        lines_params(3),
    )
    assert engine("transform", "--rebuild") == 1
    assert by_id(staged(lake, "games"))["900000020"]["closing_line_missing"] is None
    out = capsys.readouterr().out
    assert "FAIL closing_line" in out
    assert "900000020" in out.split("FAIL closing_line")[1].split("PASS")[0]


def test_mismatched_raw_file_is_skipped(
    lake: LocalLake, capsys: pytest.CaptureFixture[str]
) -> None:
    """Plan revision 1: a 2019 /lines response filed under 2025 week 2 adds no rows and covers
    nothing, and the report names it."""
    x = _week_game(900000030, 2, "2025-09-06T19:00:00.000Z")
    write(
        lake,
        "raw/cfbd/games/season=2025/week=02/fetched_at=2025-09-08T120000Z.parquet",
        [x],
        games_params(2),
    )
    bad_key = "raw/cfbd/lines/season=2025/week=02/fetched_at=2025-09-09T120000Z.parquet"
    write(
        lake,
        bad_key,
        [{**FIXTURE[LINES_KEY]["records"][0], "id": 900000030}],
        {"seasonType": "regular", "week": 2, "year": "2019"},
    )
    assert engine("transform", "--rebuild") == 1
    assert "900000030" not in staged(lake, "lines").column("game_source_id").to_pylist()
    assert by_id(staged(lake, "games"))["900000030"]["closing_line_missing"] is None
    assert staged(lake, "skipped_raw").column("key").to_pylist() == [bad_key]
    out = capsys.readouterr().out
    assert "FAIL closing_line" in out
    assert bad_key in out.split("raw_files")[1]


def test_check_without_staging_exits_2(
    lake: LocalLake, capsys: pytest.CaptureFixture[str]
) -> None:
    assert engine("check") == 2
    assert "transform --rebuild" in capsys.readouterr().err


def test_fetched_at_round_trips() -> None:
    assert fetched_at_of(GAMES_KEY) == datetime.fromisoformat("2025-09-02T12:00:00+00:00")
