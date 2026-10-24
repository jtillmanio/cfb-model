"""The point-in-time feature tables (TASK-019, D-042) on the season fixture: the lake fixture's
week 1 plus weeks 2-8 (`lake_fixture.write_season`). No test opens a socket or a database."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import pytest
from lake_fixture import (
    BYE,
    FIXTURE,
    engine,
    featured,
    fixture_key,
    season_game_id,
    staged,
    week_key,
    write,
    write_season,
)

from engine.ingest.lake import LocalLake
from engine.transform import features, rebuild

KANSAS = "2305"  # home in Kansas-Fresno State (401756847) every week, never a bye
KANSAS_STATE = "2306"  # plays the week's first kickoff; bye in week 5
KANSAS_GAME = "401756847"


@pytest.fixture
def season(lake: LocalLake) -> LocalLake:
    write_season(lake)
    return lake


def team_weeks(lake: LocalLake) -> dict[tuple[str, str, int], dict[str, Any]]:
    rows = featured(lake, "team_week_features").to_pylist()
    return {(r["team_source_id"], r["season_type"], r["week"]): r for r in rows}


def kickoffs(lake: LocalLake) -> dict[str, tuple[str, str, int, datetime]]:
    """Each final staged game's teams, week and kickoff (no TBA games in the fixture)."""
    return {
        g["source_id"]: (g["home_source_id"], g["away_source_id"], g["week"], g["kickoff_at"])
        for g in staged(lake, "games").to_pylist()
        if g["status"] == "final"
    }


def test_every_row_has_as_of_after_its_sources(season: LocalLake) -> None:
    rebuild(season)
    games = kickoffs(season)
    first = {}
    for _, _, week, kickoff in games.values():
        first[week] = min(first.get(week, kickoff), kickoff)

    rows = team_weeks(season)
    assert {week for _, _, week in rows} == set(range(1, 9))
    for (team, _, week), row in rows.items():
        assert row["as_of"] is not None
        assert row["as_of"] == first[week]
        # Counted from the staged games, independently of the feature SQL: only games that
        # kicked off before as_of, so never the week's own game.
        before = [k for h, a, _, k in games.values() if team in (h, a) and k < row["as_of"]]
        assert row["games_played"] == len(before), (team, week)
        assert row["last_game_kickoff"] == (max(before) if before else None)

    for game in featured(season, "game_features").to_pylist():
        assert game["as_of"] is not None
        for side in ("home", "away"):
            last = game[f"{side}_last_game_kickoff"]
            assert last is None or last < game["as_of"] <= game["kickoff_at"]


def test_leaky_inclusion_fails_the_build_naming_the_row(
    season: LocalLake, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A rule that lets in a game kicking off at as_of (the week's own first game) must fail
    the build, name the team, season and week, and replace no staged or feature file."""
    monkeypatch.setattr(features, "INCLUDED", "s.kickoff <= w.as_of")
    assert engine("transform", "--rebuild") == 1
    out = capsys.readouterr().out
    assert "FAIL" in out
    assert f"team {KANSAS_STATE}, 2025 regular week 2: its newest source game kicked off" in out
    assert f"game {season_game_id(2, '401756846')} (home): team {KANSAS_STATE}" in out
    assert season.walk("features") == []
    assert "staging/games.parquet" not in season.walk("staging")


def test_check_point_in_time_names_an_injected_leak(season: LocalLake) -> None:
    """The assertion on its own: a row whose newest source game is at or after as_of, or that
    has no as_of, is named."""
    rebuild(season)
    from engine.transform.staging import connect

    con = connect()
    for name in ("team_week_features", "game_features"):
        con.register(f"{name}_ok", featured(season, name))
        con.execute(f"CREATE TABLE {name} AS SELECT * FROM {name}_ok")
    features.check_point_in_time(con)  # the real build passes

    con.execute(
        "UPDATE team_week_features SET last_game_kickoff = as_of "
        f"WHERE team_source_id = '{KANSAS}' AND week = 4"
    )
    con.execute(
        "UPDATE team_week_features SET as_of = NULL "
        f"WHERE team_source_id = '{KANSAS}' AND week = 5"
    )
    with pytest.raises(features.PointInTimeError) as e:
        features.check_point_in_time(con)
    assert f"team {KANSAS}, 2025 regular week 4: its newest source game kicked off" in str(e.value)
    assert f"team {KANSAS}, 2025 regular week 5: as_of is NULL" in str(e.value)


def test_week4_counts_three_games_and_week1_is_empty(season: LocalLake) -> None:
    rebuild(season)
    rows = team_weeks(season)
    advanced = [
        r
        for r in FIXTURE[fixture_key("stats_game_advanced")]["records"]
        if str(r["gameId"]) == KANSAS_GAME and r["team"] == "Kansas"
    ][0]

    schema = featured(season, "team_week_features").schema
    for name in ("games_played", "points_for", "advanced_games", "off_plays"):
        assert str(schema.field(name).type) == "int32", name  # counts, not decimals

    week1 = rows[(KANSAS, "regular", 1)]
    assert (week1["games_played"], week1["points_for"], week1["advanced_games"]) == (0, 0, 0)
    for name in ("points_for_per_game", "points_against_per_game", "margin_per_game"):
        assert week1[name] is None, name
    for name in features.FEATURES:
        if name.startswith(("off_", "def_")) and not name.endswith("_plays"):
            assert week1[name] is None, name

    week4 = rows[(KANSAS, "regular", 4)]
    assert week4["games_played"] == 3
    # Kansas scored 31 in week 1, then 31 + week (the season fixture's home bump).
    assert week4["points_for"] == 31 + 33 + 34
    assert week4["points_against"] == 7 * 3
    assert week4["margin_per_game"] == pytest.approx((98 - 21) / 3)
    assert week4["advanced_games"] == 3
    assert week4["off_plays"] == 3 * advanced["offense"]["plays"]
    assert week4["off_ppa"] == pytest.approx(advanced["offense"]["ppa"])
    assert week4["def_pass_success_rate"] == pytest.approx(
        advanced["defense"]["passingPlays"]["successRate"]
    )

    # Kansas State's bye in week 5: games played rises by at most one a week, and not past it.
    played = [rows[(KANSAS_STATE, "regular", w)]["games_played"] for w in range(1, 9)]
    assert BYE[0] == 5
    assert played == [0, 1, 2, 3, 4, 4, 5, 6]


def test_games_without_advanced_stats_count_but_leave_the_means(lake: LocalLake) -> None:
    """D-121: CFBD never computed some games' advanced stats. They count as games played and
    in points, not in the efficiency means."""
    write_season(lake, without_stats=(3, KANSAS_GAME))
    rebuild(lake)
    week4 = team_weeks(lake)[(KANSAS, "regular", 4)]
    advanced = [
        r
        for r in FIXTURE[fixture_key("stats_game_advanced")]["records"]
        if str(r["gameId"]) == KANSAS_GAME and r["team"] == "Kansas"
    ][0]
    assert (week4["games_played"], week4["advanced_games"]) == (3, 2)
    assert week4["points_for"] == 98
    assert week4["off_plays"] == 2 * advanced["offense"]["plays"]
    assert week4["off_ppa"] == pytest.approx(advanced["offense"]["ppa"])


def test_one_game_row_per_staged_game_with_target(season: LocalLake) -> None:
    # A week-9 game not yet played: in game_features with a NULL target.
    game = next(
        g for g in FIXTURE[fixture_key("games")]["records"] if str(g["id"]) == KANSAS_GAME
    )
    unplayed = {
        **game,
        "id": 900199999,
        "week": 9,
        "startDate": "2025-10-25T22:30:00.000Z",
        "completed": False,
        "homePoints": None,
        "awayPoints": None,
    }
    write(
        season,
        week_key("games", 9),
        [unplayed],
        {"classification": "fbs", "seasonType": "regular", "week": 9, "year": 2025},
    )
    rebuild(season)

    games = {g["source_id"]: g for g in staged(season, "games").to_pylist()}
    rows = featured(season, "game_features").to_pylist()
    assert len(rows) == len(games)
    assert {r["game_source_id"] for r in rows} == set(games)

    weeks = team_weeks(season)
    for row in rows:
        g = games[row["game_source_id"]]
        assert row["neutral_site"] == g["neutral_site"]
        assert (row["home_source_id"], row["away_source_id"]) == (
            g["home_source_id"],
            g["away_source_id"],
        )
        expected = g["home_points"] - g["away_points"] if g["status"] == "final" else None
        assert row["margin"] == expected
        for side in ("home", "away"):
            entering = weeks[(g[f"{side}_source_id"], g["season_type"], g["week"])]
            assert row["as_of"] == entering["as_of"]
            for name in features.FEATURES:
                assert row[f"{side}_{name}"] == entering[name], (row["game_source_id"], name)

    week9 = next(r for r in rows if r["game_source_id"] == "900199999")
    assert week9["margin"] is None
    assert week9["home_games_played"] == 8  # Kansas, weeks 1-8
    assert next(r for r in rows if r["game_source_id"] == KANSAS_GAME)["margin"] == 31 - 7
    assert any(r["neutral_site"] for r in rows)  # Kansas State-Iowa State
