"""The leakage test (TASK-019, docs/02-architecture.md › Testing strategy): changing a game after
week N leaves every week-N feature row unchanged. Rows "entering week N" may read only games
that finished (4 hours after kickoff) before that week's `as_of`, so a week-7 game can change
week 8's rows and no earlier ones.
"""

from __future__ import annotations

from typing import Any

from lake_fixture import featured, season_game_id, season_records, write_repull, write_season

from engine.ingest.lake import LocalLake
from engine.transform import rebuild

KANSAS = "2305"
KANSAS_GAME = "401756847"  # Kansas-Fresno State


def by_key(lake: LocalLake, name: str, *key: str) -> dict[tuple[Any, ...], dict[str, Any]]:
    return {tuple(r[k] for k in key): r for r in featured(lake, name).to_pylist()}


def by_game(lake: LocalLake) -> dict[str, dict[str, Any]]:
    return {r["game_source_id"]: r for r in featured(lake, "game_features").to_pylist()}


def test_changing_a_week7_game_leaves_weeks_through_7_unchanged(lake: LocalLake) -> None:
    write_season(lake)
    rebuild(lake)
    teams_before = by_key(lake, "team_week_features", "team_source_id", "season_type", "week")
    games_before = by_game(lake)

    # A later pull of week 7 rescores Kansas-Fresno State and changes both teams' stats.
    changed = season_game_id(7, KANSAS_GAME)
    week7 = season_records(7)
    (game,) = [g for g in week7["games"] if str(g["id"]) == changed]
    write_repull(lake, "games", 7, [{**game, "homePoints": 3, "awayPoints": 45}])
    stats = [r for r in week7["stats_game_advanced"] if str(r["gameId"]) == changed]
    for r in stats:
        r["offense"] = {**r["offense"], "ppa": -0.9, "successRate": 0.1}
        r["defense"] = {**r["defense"], "ppa": 0.9}
    write_repull(lake, "stats_game_advanced", 7, stats)
    rebuild(lake)
    teams_after = by_key(lake, "team_week_features", "team_source_id", "season_type", "week")
    games_after = by_game(lake)

    assert teams_after.keys() == teams_before.keys()
    for key, row in teams_before.items():
        if key[2] <= 7:
            assert teams_after[key] == row, key
    week8 = teams_after[(KANSAS, "regular", 8)]
    assert week8 != teams_before[(KANSAS, "regular", 8)]
    assert week8["points_for"] == teams_before[(KANSAS, "regular", 8)]["points_for"] - 38 + 3

    assert games_after.keys() == games_before.keys()
    for game_id, row in games_before.items():
        if row["week"] > 7:
            continue
        after = games_after[game_id]
        if game_id == changed:
            # The changed game's own target is the one thing that moves (plan, AC-2 reading).
            assert after["margin"] == 3 - 45 != row["margin"]
            after = {**after, "margin": row["margin"]}
        assert after == row, game_id
    week8_game = games_after[season_game_id(8, KANSAS_GAME)]
    assert week8_game != games_before[season_game_id(8, KANSAS_GAME)]
