"""Staging box scores, advanced stats, plays, drives, preseason inputs and benchmark ratings
(TASK-018, D-119), on the lake fixture described in `lake_fixture.py`. No test opens a socket
or a database."""

from __future__ import annotations

import copy
import io
import json
from datetime import datetime
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from lake_fixture import FIXTURE, engine, fixture_key, staged, write, write_fixture

from engine.ingest.lake import LocalLake, fetched_at_of
from engine.transform import rebuild, season_key

KANSAS_GAME = "401756847"  # Kansas (2305, home) - Fresno State (278)
UNLV_GAME = "401760371"  # UNLV (2439, home) - Idaho State (304, FCS)


def records(endpoint: str) -> list[dict[str, Any]]:
    return FIXTURE[fixture_key(endpoint)]["records"]


def staged_season(lake: LocalLake, name: str, season: int) -> pa.Table:
    return pq.read_table(io.BytesIO(lake.read(season_key(name, season))))


def stats_params(week: int, season: int = 2025) -> dict[str, Any]:
    return {"excludeGarbageTime": "true", "seasonType": "regular", "week": week, "year": season}


def advanced(lake: LocalLake) -> dict[tuple[str, str], dict[str, Any]]:
    rows = staged(lake, "team_game_advanced").to_pylist()
    return {(r["game_source_id"], r["team_source_id"]): r for r in rows}


def test_each_staged_table_matches_its_raw_record_count(lake: LocalLake) -> None:
    """AC-1: one assertion per table, against the raw fixture's records after dedupe."""
    rebuild(lake)
    games_teams = records("games_teams")
    assert all(len(g["teams"]) == 2 for g in games_teams)
    assert staged(lake, "team_games").num_rows == 2 * len(games_teams)
    assert staged(lake, "team_game_advanced").num_rows == len(records("stats_game_advanced"))
    assert staged_season(lake, "plays", 2025).num_rows == len(records("plays"))
    assert staged_season(lake, "drives", 2025).num_rows == len(records("drives"))
    assert staged(lake, "talent").num_rows == len(records("talent"))
    assert staged(lake, "returning_production").num_rows == len(records("player_returning"))
    assert staged(lake, "recruiting").num_rows == len(records("recruiting_teams"))
    assert any(r["team"] == "nationalAverages" for r in records("ratings_sp"))
    benchmarks = [
        r
        for endpoint in ("ratings_sp", "ratings_fpi", "ratings_elo")
        for r in records(endpoint)
        if r["team"] != "nationalAverages"
    ]
    assert staged(lake, "benchmark_ratings").num_rows == len(benchmarks)


def test_staged_rows_carry_the_raw_values(lake: LocalLake) -> None:
    rebuild(lake)
    kansas_box = next(
        r
        for r in staged(lake, "team_games").to_pylist()
        if (r["game_source_id"], r["team_source_id"]) == (KANSAS_GAME, "2305")
    )
    assert (kansas_box["home_away"], kansas_box["points"]) == ("home", 31)
    raw_game = next(g for g in records("games_teams") if str(g["id"]) == KANSAS_GAME)
    raw_team = next(t for t in raw_game["teams"] if t["teamId"] == 2305)
    assert json.loads(kansas_box["stats"]) == {s["category"]: s["stat"] for s in raw_team["stats"]}

    row = advanced(lake)[(KANSAS_GAME, "2305")]
    raw = next(
        r
        for r in records("stats_game_advanced")
        if str(r["gameId"]) == KANSAS_GAME and r["team"] == "Kansas"
    )
    assert row["off_ppa"] == raw["offense"]["ppa"]
    assert row["off_success_rate"] == raw["offense"]["successRate"]
    assert row["off_rush_explosiveness"] == raw["offense"]["rushingPlays"]["explosiveness"]
    assert row["def_pass_success_rate"] == raw["defense"]["passingPlays"]["successRate"]
    assert row["def_line_yards"] == raw["defense"]["lineYards"]
    assert advanced(lake)[(KANSAS_GAME, "278")]["team"] == "Fresno State"

    talent = {r["team"]: r for r in staged(lake, "talent").to_pylist()}
    assert talent["Kansas"]["team_source_id"] == "2305"
    assert talent["Florida International"]["team_source_id"] is None  # not a fixture team

    plays = staged_season(lake, "plays", 2025).to_pylist()
    assert {r["game_source_id"] for r in plays} == {KANSAS_GAME, UNLV_GAME}
    kansas_offense = [r for r in plays if r["offense"] == "Kansas"]
    assert kansas_offense
    assert {(r["offense_source_id"], r["defense_source_id"]) for r in kansas_offense} == {
        ("2305", "278")
    }
    drives = staged_season(lake, "drives", 2025).to_pylist()
    assert {r["offense_source_id"] for r in drives} == {"2305", "278", "2439", "304"}


def test_advanced_stats_one_row_per_game_team_newest_wins(lake: LocalLake) -> None:
    """AC-2: a newer pull that repeats a (game, team) replaces its values; an older one
    doesn't."""
    original = [r for r in records("stats_game_advanced") if str(r["gameId"]) == KANSAS_GAME]
    kansas, fresno = (copy.deepcopy(r) for r in original)
    assert {kansas["team"], fresno["team"]} == {"Kansas", "Fresno State"}
    if kansas["team"] != "Kansas":
        kansas, fresno = fresno, kansas
    kansas["offense"]["ppa"] = 0.999
    fresno["offense"]["ppa"] = -0.999
    write(  # newer than the fixture's 2026-10-20 pull
        lake,
        "raw/cfbd/stats_game_advanced/season=2025/fetched_at=2026-10-21T120000Z.parquet",
        [kansas],
        {"excludeGarbageTime": "true", "seasonType": "regular", "year": 2025},
    )
    write(  # older
        lake,
        "raw/cfbd/stats_game_advanced/season=2025/week=01/fetched_at=2025-08-25T120000Z.parquet",
        [fresno],
        stats_params(1),
    )
    rebuild(lake)
    rows = staged(lake, "team_game_advanced").to_pylist()
    keys = [(r["game_source_id"], r["team_source_id"]) for r in rows]
    assert len(keys) == len(set(keys)) == len(records("stats_game_advanced"))
    by_key = advanced(lake)
    assert by_key[(KANSAS_GAME, "2305")]["off_ppa"] == 0.999
    assert by_key[(KANSAS_GAME, "2305")]["fetched_at"] == datetime.fromisoformat(
        "2026-10-21T12:00:00+00:00"
    )
    assert by_key[(KANSAS_GAME, "278")]["off_ppa"] != -0.999
    assert all(r["garbage_time_excluded"] is True for r in rows)


def test_renamed_school_stays_one_row(lake: LocalLake) -> None:
    """An older pull naming Kansas differently still resolves (by its opponent), so the newest
    pull replaces it instead of adding a second row for the side (schema review R1)."""
    kansas = next(
        r
        for r in records("stats_game_advanced")
        if str(r["gameId"]) == KANSAS_GAME and r["team"] == "Kansas"
    )
    write(
        lake,
        "raw/cfbd/stats_game_advanced/season=2025/week=01/fetched_at=2025-08-25T120000Z.parquet",
        [{**copy.deepcopy(kansas), "team": "Kansas Jayhawks"}],
        stats_params(1),
    )
    rebuild(lake)
    rows = [
        r
        for r in staged(lake, "team_game_advanced").to_pylist()
        if r["game_source_id"] == KANSAS_GAME
    ]
    assert sorted((r["team_source_id"], r["team"]) for r in rows) == [
        ("2305", "Kansas"),
        ("278", "Fresno State"),
    ]


def test_plays_come_from_each_games_newest_pull(
    lake: LocalLake, capsys: pytest.CaptureFixture[str]
) -> None:
    """A week is pulled again until it's final; a play the newer pull dropped isn't staged,
    and a game only the older pull has keeps its plays (schema review R1)."""
    unlv_play = next(r for r in records("plays") if str(r["gameId"]) == UNLV_GAME)
    extra = {**copy.deepcopy(unlv_play), "id": "401760371999999999"}
    older_only = {
        **copy.deepcopy(unlv_play),
        "id": "900000090000000001",
        "gameId": 900000090,
        "offense": "Nowhere State",
    }
    write(  # older than the fixture's 2026-10-20 pull
        lake,
        "raw/cfbd/plays/season=2025/week=01/fetched_at=2025-08-24T120000Z.parquet",
        [unlv_play, extra, older_only],
        {"classification": "fbs", "seasonType": "regular", "week": 1, "year": 2025},
    )
    counts = rebuild(lake)
    ids = staged_season(lake, "plays", 2025).column("play_id").to_pylist()
    assert "401760371999999999" not in ids
    assert "900000090000000001" in ids
    assert counts["plays"] == len(records("plays")) + 1
    # 900000090 isn't a staged game, so its offense has no id and is listed.
    assert "plays 2025: Nowhere State" in capsys.readouterr().out


def test_advanced_stats_for_games_not_staged_are_dropped(
    lake: LocalLake, capsys: pytest.CaptureFixture[str]
) -> None:
    """/stats/game/advanced takes no classification, so FCS-only games are dropped and counted,
    as lines are (plan revision 1)."""
    fcs = {**copy.deepcopy(records("stats_game_advanced")[0]), "gameId": 900000070}
    write(
        lake,
        "raw/cfbd/stats_game_advanced/season=2025/week=01/fetched_at=2026-10-21T120000Z.parquet",
        [fcs],
        stats_params(1),
    )
    counts = rebuild(lake)
    assert counts["team_game_advanced"] == len(records("stats_game_advanced"))
    staged_games = staged(lake, "team_game_advanced").column("game_source_id").to_pylist()
    assert "900000070" not in staged_games
    assert "Dropped 1 advanced-stats rows" in capsys.readouterr().out


def test_filtered_plays_file_is_skipped_and_listed(lake: LocalLake) -> None:
    """Plays load after the other tables, so `skipped_raw` is built after them to list a plays
    file pulled with a filter (the local lake's 2025 week 1 has one, D-116)."""
    bad_key = "raw/cfbd/plays/season=2025/week=01/fetched_at=2025-09-02T120000Z.parquet"
    params = {"classification": "fbs", "seasonType": "regular", "week": 1, "year": 2025}
    write(lake, bad_key, records("plays")[:3], {**params, "team": "Ohio State"})
    counts = rebuild(lake)
    assert counts["plays"] == len(records("plays"))
    assert staged(lake, "skipped_raw").column("key").to_pylist() == [bad_key]


def _without(game: str, team: str) -> dict[str, Any]:
    fixture = copy.deepcopy(FIXTURE)
    raw = fixture[fixture_key("stats_game_advanced")]
    before = len(raw["records"])
    raw["records"] = [
        r for r in raw["records"] if not (str(r["gameId"]) == game and r["team"] == team)
    ]
    assert len(raw["records"]) == before - 1
    return fixture


def _pulled_at(fixture: dict[str, Any], stamp: str) -> dict[str, Any]:
    """The fixture with its advanced-stats pull fetched at `stamp` instead."""
    key = fixture_key("stats_game_advanced")
    fixture = dict(fixture)
    fixture[key.split("fetched_at=")[0] + f"fetched_at={stamp}.parquet"] = fixture.pop(key)
    return fixture


@pytest.mark.parametrize("present", [True, False])
def test_advanced_stats_check_names_missing_game(
    present: bool, empty_lake: LocalLake, capsys: pytest.CaptureFixture[str]
) -> None:
    """AC-3: a final FBS game in a backtest season with no advanced-stats row fails the check,
    named by `source_id`, while CFBD may still fill it in (the pull came within 7 days of
    kickoff); with the row present everything passes."""
    fixture = FIXTURE if present else _without(KANSAS_GAME, "Kansas")
    write_fixture(empty_lake, _pulled_at(fixture, "2025-08-25T120000Z"))
    code = engine("transform", "--rebuild")
    out = capsys.readouterr().out
    if present:
        assert code == 0
        assert "PASS advanced_stats" in out
        return
    assert code == 1
    section = out.split("FAIL advanced_stats")[1].split("PASS")[0]
    assert KANSAS_GAME in section
    assert "2305" in section
    assert engine("check") == 1


def test_game_cfbd_never_filled_in_is_a_note(
    empty_lake: LocalLake, capsys: pytest.CaptureFixture[str]
) -> None:
    """TASK-021: a pull 7+ days after kickoff that covers the week but not the game means CFBD
    has no advanced stats for it (some 2014-2016 games have no play-by-play), so it's a note."""
    write_fixture(empty_lake, _without(KANSAS_GAME, "Kansas"))  # pulled 2026-10-20

    assert engine("transform", "--rebuild") == 0

    out = capsys.readouterr().out
    notes = out.split("PASS advanced_stats")[1].split("PASS")[0]
    assert (
        f"{KANSAS_GAME} (2025 regular week 1, 278 at 2305): no advanced stats for team 2305"
        in notes
    )
    assert "CFBD has none" in notes


def test_live_season_game_without_a_stats_pull_is_a_note(
    lake: LocalLake, capsys: pytest.CaptureFixture[str]
) -> None:
    """A final game outside the backtest seasons fails only once a non-empty stats pull fetched
    after its kickoff covers its week; before that it's a note."""
    game = next(g for g in FIXTURE[fixture_key("games")]["records"] if str(g["id"]) == KANSAS_GAME)
    # Two 2026 week-1 games between the same teams, on different dates.
    missing = {**game, "id": 900000080, "season": 2026, "startDate": "2026-08-29T19:00:00.000Z"}
    covered = {**game, "id": 900000081, "season": 2026, "startDate": "2026-08-30T19:00:00.000Z"}
    write(
        lake,
        "raw/cfbd/games/season=2026/week=01/fetched_at=2026-08-31T120000Z.parquet",
        [missing, covered],
        {"classification": "fbs", "seasonType": "regular", "week": 1, "year": 2026},
    )
    assert engine("transform", "--rebuild") == 0
    out = capsys.readouterr().out
    assert "PASS advanced_stats" in out
    notes = out.split("PASS advanced_stats")[1]
    assert "900000080" in notes
    assert "900000081" in notes

    sides = [r for r in records("stats_game_advanced") if str(r["gameId"]) == KANSAS_GAME]
    write(  # covers 2026 week 1 after both kickoffs, with rows for 900000081 only
        lake,
        "raw/cfbd/stats_game_advanced/season=2026/week=01/fetched_at=2026-08-31T130000Z.parquet",
        [{**r, "gameId": 900000081, "season": 2026} for r in sides],
        stats_params(1, 2026),
    )
    assert engine("transform", "--rebuild") == 1
    failures = capsys.readouterr().out.split("FAIL advanced_stats")[1].split("PASS")[0]
    assert "900000080" in failures
    assert "900000081" not in failures


def _sp_rows(lake: LocalLake) -> list[dict[str, Any]]:
    return [r for r in staged(lake, "benchmark_ratings").to_pylist() if r["system"] == "sp"]


def test_season_final_sp_marked(lake: LocalLake) -> None:
    """AC-4: the fixture's SP+ was pulled after the 2025 season's last calendar week, so every
    row is season-final with no `known_at`; a mid-season pull is neither."""
    rebuild(lake)
    rows = _sp_rows(lake)
    assert len(rows) == len([r for r in records("ratings_sp") if r["team"] != "nationalAverages"])
    assert all(r["season_final"] is True and r["known_at"] is None for r in rows)
    systems = {r["system"] for r in staged(lake, "benchmark_ratings").to_pylist()}
    assert systems == {"sp", "fpi", "elo"}
    kansas = next(r for r in rows if r["team"] == "Kansas")
    assert kansas["team_source_id"] == "2305"
    raw_kansas = next(r for r in records("ratings_sp") if r["team"] == "Kansas")
    assert kansas["rating"] == raw_kansas["rating"]

    midseason = "raw/cfbd/ratings_sp/season=2025/fetched_at=2025-10-01T120000Z.parquet"
    write(lake, midseason, [raw_kansas], {"year": 2025})
    # No 2024 calendar is staged, so whether 2024's pull is season-final is unknown.
    write(
        lake,
        "raw/cfbd/ratings_sp/season=2024/fetched_at=2025-10-01T120000Z.parquet",
        [{**raw_kansas, "year": 2024}],
        {"year": 2024},
    )
    rebuild(lake)
    rows = _sp_rows(lake)
    early = [r for r in rows if r["fetched_at"] == fetched_at_of(midseason) and r["season"] == 2025]
    assert len(early) == 1
    assert early[0]["season_final"] is False
    assert early[0]["known_at"] == fetched_at_of(midseason)
    (unknown,) = [r for r in rows if r["season"] == 2024]
    assert unknown["season_final"] is None
    assert unknown["known_at"] is None
