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
from engine.ingest.lake import LocalLake, encode_raw, fetched_at_of

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


def by_id(table: pa.Table, column: str = "source_id") -> dict[str, dict[str, Any]]:
    return {row[column]: row for row in table.to_pylist()}


def engine(*argv: str) -> int:
    try:
        cli.main(list(argv))
    except SystemExit as e:
        return int(e.code or 0)
    return 0
