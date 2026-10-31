"""`engine transform --rebuild` and `engine check` on a lake fixture of recorded CFBD responses
(TASK-017, D-116). No test opens a socket or a database. The fixture is described in
`lake_fixture.py`.
"""

from __future__ import annotations

import copy
import io
from datetime import datetime
from typing import Any

import httpx
import pyarrow.parquet as pq
import pytest
from lake_fixture import (
    FIXTURE,
    STATUS_GAMES,
    by_id,
    engine,
    staged,
    write,
    write_status_games,
)

from engine.ingest import cfbd
from engine.ingest.lake import LocalLake, fetched_at_of
from engine.sports.cfb.games import map_games
from engine.transform import (
    FEATURE_TABLES,
    SEASON_TABLES,
    TABLES,
    feature_key,
    rebuild,
    season_key,
)

GAMES_KEY = "raw/cfbd/games/season=2025/week=01/fetched_at=2025-09-02T120000Z.parquet"
LINES_KEY = "raw/cfbd/lines/season=2025/week=01/fetched_at=2026-10-18T061546Z.parquet"
STATS_KEY = (
    "raw/cfbd/stats_game_advanced/season=2025/week=01/fetched_at=2026-10-20T060735Z.parquet"
)
NO_FBS_GAME = "401767256"  # Colgate-Monmouth: in /lines, not in /games
BOTH_FBS = "401756847"  # Kansas-Fresno State, 2025-08-23T22:30Z


def fixture_game(source_id: str) -> dict[str, Any]:
    games = FIXTURE[GAMES_KEY]["records"]
    return copy.deepcopy(next(g for g in games if str(g["id"]) == source_id))


def games_params(week: int) -> dict[str, Any]:
    return {"classification": "fbs", "seasonType": "regular", "week": week, "year": 2025}


def lines_params(week: int) -> dict[str, Any]:
    return {"seasonType": "regular", "week": week, "year": 2025}


def stats_params(week: int) -> dict[str, Any]:
    return {"excludeGarbageTime": "true", "seasonType": "regular", "week": week, "year": 2025}


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
        "team_games": 10,
        "team_game_advanced": 10,
        "talent": 10,
        "returning_production": 9,
        "recruiting": 10,
        "benchmark_ratings": 27,  # 9 teams x SP+, FPI, Elo; SP+'s nationalAverages is dropped
        "skipped_raw": 0,
        "plays": 334,
        "drives": 48,
        "team_week_features": 10,  # 10 teams entering week 1
        "game_features": 5,
    }
    assert set(counts) == set(TABLES) | set(SEASON_TABLES) | set(FEATURE_TABLES)
    keys = [f"staging/{name}.parquet" for name in TABLES]
    keys += [season_key(name, 2025) for name in SEASON_TABLES]
    assert sorted(lake.walk("staging")) == sorted(keys)
    assert sorted(lake.walk("features")) == sorted(feature_key(n) for n in FEATURE_TABLES)
    keys += [feature_key(name) for name in FEATURE_TABLES]
    first = {key: lake.read(key) for key in keys}

    assert engine("transform", "--rebuild") == 0
    for key in keys:
        again = pq.read_table(io.BytesIO(lake.read(key)))
        assert again.equals(pq.read_table(io.BytesIO(first[key]))), key

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
    # Postgres team_seasons.division is fbs/fcs, so it's staged as `classification`; CFBD's own
    # division (East/West) is `cfbd_division` (schema review R1).
    rows = staged(lake, "team_seasons").to_pylist()
    seasons = {(r["team_source_id"], r["season"]): r for r in rows}
    assert seasons[("2305", 2025)]["classification"] == "fbs"
    assert seasons[("304", 2025)]["classification"] == "fcs"  # filled in from /games
    assert seasons[("304", 2025)]["cfbd_division"] is None
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


def test_unscored_game_a_week_past_its_start_is_staged_canceled(
    lake: LocalLake, capsys: pytest.CaptureFixture[str]
) -> None:
    """TASK-044 AC-1: D-121's rule. A game CFBD still lists as uncompleted and unscored by a pull
    `SETTLE` (7 days) after its start is canceled; inside the window it stays scheduled, as does
    a game that hasn't started. The data-quality checks list it and still pass."""
    write_status_games(lake)
    assert engine("transform", "--rebuild") == 0
    games = by_id(staged(lake, "games"))
    assert {g: games[g]["status"] for g in STATUS_GAMES} == STATUS_GAMES
    out = capsys.readouterr().out
    assert "2025: final 5, scheduled 2, canceled 1" in out
    assert "PASS not_played" in out
    assert "900000060" in out.split("PASS not_played")[1]
    assert "900000061" not in out.split("PASS not_played")[1]


def test_rebuild_refuses_under_live_with_only_features(
    lake: LocalLake, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    lake.replace("features/game_features.parquet", b"sentinel")
    monkeypatch.setenv("LIVE", "true")
    assert engine("transform", "--rebuild") == 2
    assert "LIVE" in capsys.readouterr().err
    assert lake.read("features/game_features.parquet") == b"sentinel"
    assert lake.walk("staging") == []


def test_rebuild_refuses_under_live(
    lake: LocalLake, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    lake.replace("staging/games.parquet", b"sentinel")
    monkeypatch.setenv("LIVE", "true")
    assert engine("transform", "--rebuild") == 2
    assert "LIVE" in capsys.readouterr().err
    assert lake.read("staging/games.parquet") == b"sentinel"
    assert lake.walk("staging") == ["staging/games.parquet"]


def test_rebuild_into_empty_lake_allowed_under_live(
    lake: LocalLake, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The jobs' scratch lake (TASK-022): no staging/ yet, so nothing is overwritten.
    monkeypatch.setenv("LIVE", "true")
    assert engine("transform", "--rebuild") == 0
    assert "staging/games.parquet" in lake.walk("staging")


def test_check_passes_on_clean_fixture(
    lake: LocalLake, capsys: pytest.CaptureFixture[str]
) -> None:
    rebuild(lake)
    capsys.readouterr()
    assert engine("check") == 0
    out = capsys.readouterr().out
    assert "6 passed, 0 failed" in out
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
    # X is a final FBS game in a backtest season, so it needs its advanced stats too.
    kansas = [r for r in FIXTURE[STATS_KEY]["records"] if str(r["gameId"]) == BOTH_FBS]
    write(
        lake,
        "raw/cfbd/stats_game_advanced/season=2025/week=02/fetched_at=2025-09-08T120000Z.parquet",
        [{**r, "gameId": 900000010, "week": 2} for r in kansas],
        stats_params(2),
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


def test_empty_post_kickoff_pull_is_not_coverage(
    lake: LocalLake, capsys: pytest.CaptureFixture[str]
) -> None:
    """CFBD can answer empty just after the games (D-114), so an empty /lines pull marks nothing:
    the game stays unmarked and the check fails (schema review R1)."""
    y = _week_game(900000040, 3, "2025-09-13T19:00:00.000Z")
    write(
        lake,
        "raw/cfbd/games/season=2025/week=03/fetched_at=2025-09-15T120000Z.parquet",
        [y],
        games_params(3),
    )
    write(
        lake,
        "raw/cfbd/lines/season=2025/week=03/fetched_at=2025-09-14T120000Z.parquet",
        [],
        lines_params(3),
    )
    assert engine("transform", "--rebuild") == 1
    assert by_id(staged(lake, "games"))["900000040"]["closing_line_missing"] is None
    assert "900000040" in capsys.readouterr().out.split("FAIL closing_line")[1]


def test_tba_kickoff_needs_a_pull_after_its_date(lake: LocalLake) -> None:
    """A TBA game's start is CFBD's midnight placeholder, so only a pull after the end of its
    Eastern game_date counts as after kickoff (schema review R1)."""
    tba = {**_week_game(900000050, 3, "2025-09-13T04:00:00.000Z"), "startTimeTBD": True}
    write(
        lake,
        "raw/cfbd/games/season=2025/week=03/fetched_at=2025-09-15T120000Z.parquet",
        [tba],
        games_params(3),
    )
    quote = {**FIXTURE[LINES_KEY]["records"][0], "id": 900000050}
    # Game day, 4 PM Eastern: possibly before kickoff, so it doesn't count.
    write(
        lake,
        "raw/cfbd/lines/season=2025/week=03/fetched_at=2025-09-13T200000Z.parquet",
        [quote],
        lines_params(3),
    )
    rebuild(lake)
    game = by_id(staged(lake, "games"))["900000050"]
    assert game["kickoff_at"] is None
    assert str(game["game_date"]) == "2025-09-13"
    assert game["closing_line_missing"] is None

    write(  # just after midnight Eastern: the game is over
        lake,
        "raw/cfbd/lines/season=2025/week=03/fetched_at=2025-09-14T041000Z.parquet",
        [quote],
        lines_params(3),
    )
    rebuild(lake)
    assert by_id(staged(lake, "games"))["900000050"]["closing_line_missing"] is False
