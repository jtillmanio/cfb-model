"""The point-in-time feature tables (TASK-019, D-042) on the season fixture: the lake fixture's
week 1 plus weeks 2-8 (`lake_fixture.write_season`). No test opens a socket or a database."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
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
    keyed = {(r["team_source_id"], r["season_type"], r["week"]): r for r in rows}
    assert len(keyed) == len(rows)  # one row per team, season type and week
    return keyed


def games_params(week: int, season_type: str = "regular") -> dict[str, Any]:
    return {"classification": "fbs", "seasonType": season_type, "week": week, "year": 2025}


def kansas_game(game_id: int, week: int, start: str, **changes: Any) -> dict[str, Any]:
    game = next(
        g for g in FIXTURE[fixture_key("games")]["records"] if str(g["id"]) == KANSAS_GAME
    )
    return {**game, "id": game_id, "week": week, "startDate": start, **changes}


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
        # Counted from the staged games, independently of the feature SQL: only games finished
        # (4 hours after kickoff) by as_of, so never the week's own game.
        before = [
            k
            for h, a, _, k in games.values()
            if team in (h, a) and k + timedelta(hours=4) <= row["as_of"]
        ]
        assert row["games_played"] == len(before), (team, week)
        assert row["last_game_kickoff"] == (max(before) if before else None)

    for game in featured(season, "game_features").to_pylist():
        assert game["as_of"] is not None
        for side in ("home", "away"):
            last = game[f"{side}_last_game_kickoff"]
            assert last is None or last + timedelta(hours=4) <= game["as_of"]
            assert game["as_of"] <= game["kickoff_at"]


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
    """The assertion on its own: a row whose newest source game kicked off less than 4 hours
    before as_of (so may not have finished), or that has no as_of, is named; one exactly 4
    hours before isn't."""
    rebuild(season)
    from engine.transform.staging import connect

    con = connect()
    for name in ("team_week_features", "game_features"):
        con.register(f"{name}_ok", featured(season, name))
        con.execute(f"CREATE TABLE {name} AS SELECT * FROM {name}_ok")
    features.check_point_in_time(con)  # the real build passes

    def set_last(week: int, before_as_of: str) -> None:
        con.execute(
            f"UPDATE team_week_features SET last_game_kickoff = as_of - INTERVAL {before_as_of} "
            f"WHERE team_source_id = '{KANSAS}' AND week = {week}"
        )

    set_last(4, "3 HOURS")  # kicked off, not finished
    set_last(6, "4 HOURS")  # finished at as_of: allowed
    con.execute(
        "UPDATE team_week_features SET as_of = NULL "
        f"WHERE team_source_id = '{KANSAS}' AND week = 5"
    )
    with pytest.raises(features.PointInTimeError) as e:
        features.check_point_in_time(con)
    message = str(e.value)
    assert f"team {KANSAS}, 2025 regular week 4: its newest source game kicked off" in message
    assert "less than 4 hours before as_of" in message
    assert f"team {KANSAS}, 2025 regular week 5: as_of is NULL" in message
    assert f"team {KANSAS}, 2025 regular week 6" not in message
    assert message.startswith("2 feature rows")


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


def test_a_game_counts_only_once_finished(season: LocalLake) -> None:
    """A game counts as finished 4 hours after kickoff (D-127): one that kicked off 3 hours
    before the next week's first kickoff isn't in that week's rows; 4 hours before, it is."""
    starts = {9: "2025-10-25T16:00:00.000Z", 10: "2025-10-25T19:00:00.000Z"}
    starts[11] = "2025-10-25T23:00:00.000Z"
    for week, start in starts.items():
        game = kansas_game(900199000 + week, week, start)
        write(season, week_key("games", week), [game], games_params(week))
    rebuild(season)
    rows = team_weeks(season)
    assert rows[(KANSAS, "regular", 10)]["games_played"] == 8  # week 9's game: 3 h before
    assert rows[(KANSAS, "regular", 11)]["games_played"] == 10  # week 10's: 4 h before


def test_tba_kickoffs_and_postseason_follow_the_clock(season: LocalLake) -> None:
    """A TBA game sets its week's as_of at the start of its Eastern date, and counts in a
    later row only once its whole date is over. Postseason week 1 comes after every regular
    week, so its rows hold the whole regular season."""
    tba = kansas_game(
        900199009, 9, "2025-10-25T04:00:00.000Z", startTimeTBD=True, homePoints=40
    )
    # A week-10 game the same Eastern day, at 7 PM: the TBA game may not be over yet.
    same_day = {
        **next(
            g for g in FIXTURE[fixture_key("games")]["records"] if str(g["id"]) == "401756846"
        ),
        "id": 900199010,
        "week": 10,
        "startDate": "2025-10-25T23:00:00.000Z",
    }
    write(season, week_key("games", 9), [tba], games_params(9))
    write(season, week_key("games", 10), [same_day], games_params(10))
    bowl = kansas_game(900199101, 1, "2025-12-20T20:00:00.000Z", seasonType="postseason")
    write(
        season,
        "raw/cfbd/games/season=2025/season_type=postseason/week=01/"
        "fetched_at=2025-12-22T120000Z.parquet",
        [bowl],
        games_params(1, "postseason"),
    )
    rebuild(season)
    rows = team_weeks(season)

    week9 = rows[(KANSAS, "regular", 9)]
    assert week9["as_of"] == datetime(2025, 10, 25, 4, tzinfo=UTC)  # midnight Eastern (EDT)
    assert week9["games_played"] == 8
    week10 = rows[(KANSAS, "regular", 10)]
    assert week10["as_of"] == datetime(2025, 10, 25, 23, tzinfo=UTC)
    assert week10["games_played"] == 8  # the TBA game counts as kicking off at day's end

    bowl_row = rows[(KANSAS, "postseason", 1)]
    regular = [r["as_of"] for (_, kind, _), r in rows.items() if kind == "regular"]
    assert bowl_row["as_of"] > max(regular)
    assert bowl_row["games_played"] == 9  # weeks 1-8 and the TBA game; no week-10 game
    assert bowl_row["points_for"] == 31 + sum(31 + w for w in range(2, 9)) + 40
    assert rows[(KANSAS_STATE, "postseason", 1)]["games_played"] == 7 + 1  # bye week 5


def test_a_game_with_no_team_id_keeps_its_row(season: LocalLake) -> None:
    """A staged game with a NULL side still gets a game_features row (NULL on that side), and
    no team row is keyed NULL."""
    write(
        season,
        week_key("games", 9),
        [kansas_game(900199020, 9, "2025-10-25T22:30:00.000Z", awayId=None)],
        games_params(9),
    )
    rebuild(season)
    assert None not in {k[0] for k in team_weeks(season)}
    rows = {r["game_source_id"]: r for r in featured(season, "game_features").to_pylist()}
    row = rows["900199020"]
    assert row["away_source_id"] is None
    assert row["away_games_played"] is None
    assert row["home_games_played"] == 8
    assert row["as_of"] == datetime(2025, 10, 25, 22, 30, tzinfo=UTC)


def test_one_game_row_per_staged_game_with_target(season: LocalLake) -> None:
    # A week-9 game not yet played: in game_features with a NULL target.
    unplayed = kansas_game(
        900199999,
        9,
        "2025-10-25T22:30:00.000Z",
        completed=False,
        homePoints=None,
        awayPoints=None,
    )
    write(season, week_key("games", 9), [unplayed], games_params(9))
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
