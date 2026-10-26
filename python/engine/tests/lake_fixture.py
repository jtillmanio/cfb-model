"""The lake fixture of recorded CFBD responses, and helpers to write to it and run the CLI.

`fixtures/lake.json` maps raw keys to `{params, records}`, trimmed from real 2025 pulls: five
week-1 games, their lines (plus Colgate-Monmouth, a game with no FBS team), /teams without Idaho
State and /venues without UNLV's stadium (both filled in from /games), and four calendar weeks
(TASK-017). TASK-018 adds the five games' box scores and advanced stats, the plays and drives of
two of them (Kansas-Fresno State and UNLV-Idaho State), and the 2025 talent, returning
production, recruiting and SP+/FPI/Elo rows of the fixture teams, plus FIU's talent (not a
fixture team, so its `team_source_id` stays NULL) and SP+'s `nationalAverages` row.

`write_season` adds weeks 2-8 for the feature tables (TASK-019): the same five pairings every
week, a week apart, with their advanced stats and post-kickoff lines.
"""

from __future__ import annotations

import copy
import io
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from engine import cli
from engine.ingest.lake import LocalLake, encode_raw, fetched_at_of, raw_folder, raw_key

FIXTURE: dict[str, Any] = json.loads(
    (Path(__file__).parent / "fixtures" / "lake.json").read_text("utf-8")
)


def write(lake: LocalLake, key: str, records: list[Any], params: dict[str, Any]) -> None:
    lake.write_new(key, encode_raw(records, params, fetched_at_of(key)))


def write_fixture(lake: LocalLake, fixture: dict[str, Any] = FIXTURE) -> None:
    for key, raw in fixture.items():
        write(lake, key, raw["records"], raw["params"])


def fixture_key(endpoint: str) -> str:
    """The fixture's one raw key for `endpoint`."""
    (key,) = [k for k in FIXTURE if k.startswith(f"raw/cfbd/{endpoint}/")]
    return key


def staged(lake: LocalLake, name: str) -> pa.Table:
    return pq.read_table(io.BytesIO(lake.read(f"staging/{name}.parquet")))


def featured(lake: LocalLake, name: str) -> pa.Table:
    return pq.read_table(io.BytesIO(lake.read(f"features/{name}.parquet")))


# The season fixture: Kansas State-Iowa State (the week's first kickoff) has a bye in week 5.
BYE = (5, "401756846")
SEASON_WEEKS = 8


def season_game_id(week: int, week1_id: str) -> str:
    """The id `write_season` gives the week's copy of a week-1 fixture game."""
    games = FIXTURE[fixture_key("games")]["records"]
    index = next(i for i, g in enumerate(games) if str(g["id"]) == week1_id)
    return str(900100000 + week * 10 + index)


def _shift(start: str, days: int) -> str:
    moved = datetime.fromisoformat(start) + timedelta(days=days)
    return moved.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def _pulled(week: int, hours: int = 0) -> str:
    """A pull two days after the week's games (week 1's Saturday is 2025-08-23)."""
    at = datetime(2025, 8, 25, 12, tzinfo=UTC) + timedelta(days=7 * (week - 1), hours=hours)
    return at.strftime("%Y-%m-%dT%H%M%SZ")


def _params(endpoint: str, week: int) -> dict[str, Any]:
    extra = {
        "games": {"classification": "fbs"},
        "stats_game_advanced": {"excludeGarbageTime": "true"},
    }.get(endpoint, {})
    return {**extra, "seasonType": "regular", "week": week, "year": 2025}


def season_records(
    week: int, without_stats: tuple[int, str] | None = None
) -> dict[str, list[dict[str, Any]]]:
    """Week `week`'s copies of the week-1 games, advanced stats and lines: each game moved
    7 days per week, its home side scoring `week` more points. `without_stats` (week, week-1
    game id) leaves that game's advanced stats out, as CFBD does for some games (D-121)."""
    games, stats, lines = [], [], []
    for game in FIXTURE[fixture_key("games")]["records"]:
        if (week, str(game["id"])) == BYE:
            continue
        new_id = int(season_game_id(week, str(game["id"])))
        has_stats = (week, str(game["id"])) != without_stats
        games.append(
            {
                **copy.deepcopy(game),
                "id": new_id,
                "week": week,
                "startDate": _shift(game["startDate"], 7 * (week - 1)),
                "homePoints": game["homePoints"] + week,
            }
        )
        stats += [
            {**copy.deepcopy(r), "gameId": new_id, "week": week}
            for r in FIXTURE[fixture_key("stats_game_advanced")]["records"]
            if r["gameId"] == game["id"] and has_stats
        ]
        lines += [
            {**copy.deepcopy(r), "id": new_id, "week": week}
            for r in FIXTURE[fixture_key("lines")]["records"]
            if r["id"] == game["id"]
        ]
    return {"games": games, "stats_game_advanced": stats, "lines": lines}


def week_key(endpoint: str, week: int, hours: int = 0) -> str:
    folder = f"raw/cfbd/{endpoint}/season=2025/week={week:02d}"
    return f"{folder}/fetched_at={_pulled(week, hours)}.parquet"


def write_season(lake: LocalLake, without_stats: tuple[int, str] | None = None) -> None:
    """Weeks 2-8 on top of the fixture's week 1."""
    for week in range(2, SEASON_WEEKS + 1):
        for endpoint, records in season_records(week, without_stats).items():
            write(lake, week_key(endpoint, week), records, _params(endpoint, week))


def write_repull(lake: LocalLake, endpoint: str, week: int, records: list[dict[str, Any]]) -> None:
    """A later pull of one season-fixture week, a day after its first."""
    write(lake, week_key(endpoint, week, hours=24), records, _params(endpoint, week))


# The backtest fixture (TASK-030): two seasons of the week-1 pairings, weeks 1-8 a week apart,
# then a postseason week 1 holding a December game and a January one (CFBD files every bowl and
# CFP round there, D-127). Western Kentucky-Sam Houston has no line in week 3, so that FBS game
# gets no results row; UNLV-Idaho State (FCS) never gets one.
BACKTEST_SEASONS = (2022, 2023)
NO_LINE = (3, "401757218")
# week-1 game id -> its postseason kickoff, days after the season's December 17.
POSTSEASON = {"401756847": 0, "401754516": 24}

Rescore = tuple[int, str, int, str]  # season, season type, week, week-1 game id


def backtest_game_id(season: int, season_type: str, week: int, week1_id: str) -> str:
    """The id `write_backtest_seasons` gives a season's copy of a week-1 fixture game."""
    games = FIXTURE[fixture_key("games")]["records"]
    index = next(i for i, g in enumerate(games) if str(g["id"]) == week1_id)
    kind = 1 if season_type == "postseason" else 0
    return f"9{season % 100:02d}{kind}{week:02d}{index}"


def _backtest_week(
    season: int, season_type: str, week: int, rescore: Rescore | None, unplayed: Rescore | None
) -> dict[str, list[dict[str, Any]]]:
    games, stats, lines = [], [], []
    post = season_type == "postseason"
    for game in FIXTURE[fixture_key("games")]["records"]:
        week1_id = str(game["id"])
        if post and week1_id not in POSTSEASON:
            continue
        new_id = int(backtest_game_id(season, season_type, week, week1_id))
        start = datetime.fromisoformat(game["startDate"]).replace(year=season)
        if post:
            start = start.replace(month=12, day=17) + timedelta(days=POSTSEASON[week1_id])
        else:
            start += timedelta(days=7 * (week - 1))
        # Scores move with the week, and differently each season, so ratings change weekly.
        step = 9 if post else week
        home_points = game["homePoints"] + step + (season - BACKTEST_SEASONS[0]) * (step % 3)
        away_points = game["awayPoints"]
        offense_ppa = None
        if rescore == (season, season_type, week, week1_id):
            home_points, away_points, offense_ppa = 3, 45, -0.9
        played = unplayed != (season, season_type, week, week1_id)
        at = {"season": season, "seasonType": season_type, "week": week}
        games.append(
            {
                **copy.deepcopy(game),
                **at,
                "id": new_id,
                "startDate": start.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
                "completed": played,
                "homePoints": home_points,
                "awayPoints": away_points,
            }
        )
        for r in FIXTURE[fixture_key("stats_game_advanced")]["records"]:
            if r["gameId"] == game["id"]:
                row = {**copy.deepcopy(r), **at, "gameId": new_id}
                if offense_ppa is not None:
                    row["offense"] = {**row["offense"], "ppa": offense_ppa, "successRate": 0.1}
                stats.append(row)
        if (week, week1_id) != NO_LINE or post:
            lines += [
                {**copy.deepcopy(r), **at, "id": new_id}
                for r in FIXTURE[fixture_key("lines")]["records"]
                if r["id"] == game["id"]
            ]
    return {"games": games, "stats_game_advanced": stats, "lines": lines}


def write_backtest_seasons(
    lake: LocalLake,
    seasons: tuple[int, ...] = BACKTEST_SEASONS,
    rescore: Rescore | None = None,
    unplayed: Rescore | None = None,
) -> None:
    """Each season's games, advanced stats and lines, each pulled after its week's games.
    `rescore` gives that game a 3-45 score and a poor offense instead; `unplayed` leaves that
    game uncompleted, as CFBD shows one in progress: its score and line are still there."""
    for season in seasons:
        weeks = [("regular", w) for w in range(1, SEASON_WEEKS + 1)] + [("postseason", 1)]
        for season_type, week in weeks:
            if season_type == "postseason":
                pulled = datetime(season + 1, 1, 20, 12, tzinfo=UTC)
            else:
                pulled = datetime(season, 8, 25, 12, tzinfo=UTC) + timedelta(days=7 * (week - 1))
            records = _backtest_week(season, season_type, week, rescore, unplayed)
            for endpoint, rows in records.items():
                extra = {
                    "games": {"classification": "fbs"},
                    "stats_game_advanced": {"excludeGarbageTime": "true"},
                }.get(endpoint, {})
                params = {**extra, "seasonType": season_type, "week": week, "year": season}
                key = raw_key(raw_folder(endpoint, season, week, season_type), pulled)
                write(lake, key, rows, params)


def by_id(table: pa.Table, column: str = "source_id") -> dict[str, dict[str, Any]]:
    return {row[column]: row for row in table.to_pylist()}


def engine(*argv: str) -> int:
    try:
        cli.main(list(argv))
    except SystemExit as e:
        return int(e.code or 0)
    return 0
