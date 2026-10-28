"""Publish the staged lake to Postgres (TASK-020): teams, team seasons, venues, seasons, games,
sportsbooks and line snapshots, in the caller's one transaction.

`publish_lake` runs the data-quality checks first and raises `DataQualityFailed` before writing
a row when any fails (docs/02-architecture.md › Data correctness). Staged columns are mapped by
meaning: `team_seasons.classification` is Postgres's `division`, CFBD's `elevation` is meters,
and the staging-only `closing_line_missing` and `cfbd_division` aren't published. Staged talent
and returning production (`percent_ppa`) fill `team_seasons.talent` and `returning_ppa_pct`
(TASK-037); other stats, plays and features stay in the lake.
"""

from __future__ import annotations

import io
import re
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Connection

from engine import clock
from engine.ingest.lake import Lake
from engine.publish.lines import EASTERN, map_lines, publish_lines
from engine.publish.reference import (
    upsert_games,
    upsert_season,
    upsert_team_seasons,
    upsert_teams,
    upsert_venues,
)
from engine.transform import quality, staging_key

SPORT = "cfb"
# The tables a publish writes, in order; `publish_lake` returns the rows each gained.
TABLES = (
    "teams",
    "team_seasons",
    "venues",
    "seasons",
    "games",
    "sportsbooks",
    "line_snapshots",
)
COLOR = re.compile(r"#[0-9A-Fa-f]{6}")


class DataQualityFailed(RuntimeError):
    def __init__(self, report: quality.Report) -> None:
        super().__init__(f"Data-quality checks failed: {', '.join(report.failures)}.")
        self.report = report


def _read(lake: Lake, name: str) -> list[dict[str, Any]]:
    import pyarrow.parquet as pq

    return pq.read_table(io.BytesIO(lake.read(staging_key(name)))).to_pylist()


def _by_team_season(rows: Sequence[Mapping[str, Any]], column: str) -> dict[tuple[str, int], Any]:
    """A staged season table's `column` by (team source id, season); unmatched names dropped."""
    return {
        (r["team_source_id"], r["season"]): r[column]
        for r in rows
        if r["team_source_id"] is not None and r[column] is not None
    }


def _scaled(value: float | None, places: int) -> Decimal | None:
    """A staged float at a Numeric column's scale: talent to 2 places, CFBD's `percentPPA` (a
    fraction, 0.69 for 69%, kept as sent even outside 0-1) to 4."""
    return None if value is None else round(Decimal(str(value)), places)


def _color(value: str | None) -> str | None:
    return value if value is not None and COLOR.fullmatch(value) else None


def _text(value: str | None) -> str | None:
    return value or None


def current_week(calendar: Sequence[Mapping[str, Any]], now: datetime) -> int | None:
    """The regular-season week whose span contains `now`, else None (gate E)."""
    for w in calendar:
        if w["season_type"] == "regular" and w["start_at"] <= now <= w["end_at"]:
            return w["week"]
    return None


def _iso(value: datetime) -> str:
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _season(year: int, weeks: list[dict[str, Any]], source: str, now: datetime) -> dict:
    weeks = sorted(weeks, key=lambda w: w["start_at"])
    return {
        "sport_id": SPORT,
        "year": year,
        "source": source,
        "start_date": min(w["start_at"] for w in weeks).astimezone(EASTERN).date(),
        "end_date": max(w["end_at"] for w in weeks).astimezone(EASTERN).date(),
        "current_week": current_week(weeks, now),
        "weeks": [
            {
                "week": w["week"],
                "season_type": w["season_type"],
                "start": _iso(w["start_at"]),
                "end": _iso(w["end_at"]),
            }
            for w in weeks
        ],
    }


def publish_lake(
    lake: Lake,
    conn: Connection,
    source: str = "cfbd",
    *,
    report: quality.Report | None = None,
) -> dict[str, int]:
    """Upsert every staged reference row and insert new line snapshots; returns the new rows per
    table in `TABLES`. A caller that already ran the checks passes their `report`. The caller
    owns the transaction, so a failure part-way leaves nothing behind."""
    report = quality.run(lake) if report is None else report
    if not report.ok:
        raise DataQualityFailed(report)

    staged = {
        name: _read(lake, name)
        for name in (
            "teams",
            "team_seasons",
            "venues",
            "calendar",
            "games",
            "lines",
            "talent",
            "returning_production",
        )
    }
    new: Counter[str] = Counter()
    talent = _by_team_season(staged["talent"], "talent")
    returning = _by_team_season(staged["returning_production"], "percent_ppa")

    team_ids = upsert_teams(
        conn,
        SPORT,
        source,
        [
            {
                "source_id": t["source_id"],
                "school": t["school"],
                "mascot": t["mascot"],
                "abbreviation": t["abbreviation"],
                "color": _color(t["color"]),
                "alt_color": _color(t["alt_color"]),
                "logo_url": t["logo_url"],
            }
            for t in staged["teams"]
        ],
        new,
    )
    upsert_team_seasons(
        conn,
        [
            {
                "team_id": team_ids[s["team_source_id"]],
                "season": s["season"],
                "conference": s["conference"],
                "division": s["classification"],
                "talent": _scaled(talent.get((s["team_source_id"], s["season"])), 2),
                "returning_ppa_pct": _scaled(returning.get((s["team_source_id"], s["season"])), 4),
            }
            for s in staged["team_seasons"]
        ],
        new,
    )
    venue_ids = upsert_venues(
        conn,
        source,
        [
            {
                "source_id": v["source_id"],
                "name": v["name"],
                "city": _text(v["city"]),
                "state": _text(v["state"]),
                "lat": v["lat"],
                "lon": v["lon"],
                "elevation_m": v["elevation"],
                "dome": v["dome"],
                "grass": v["grass"],
                "timezone": _text(v["timezone"]),
                "capacity": v["capacity"],
            }
            for v in staged["venues"]
            if v["name"]  # venues.name is NOT NULL; a /games fill-in can lack one
        ],
        new,
    )

    by_season: defaultdict[int, list[dict[str, Any]]] = defaultdict(list)
    for week in staged["calendar"]:
        by_season[week["season"]].append(week)
    now = clock.now()
    for year, weeks in sorted(by_season.items()):
        upsert_season(conn, _season(year, weeks, source, now), new)

    games = staged["games"]
    unplaced = [
        g["source_id"]
        for g in games
        if g["venue_source_id"] is not None and g["venue_source_id"] not in venue_ids
    ]
    game_ids = upsert_games(
        conn,
        SPORT,
        source,
        [
            {
                "source_id": g["source_id"],
                "season": g["season"],
                "week": g["week"],
                "season_type": g["season_type"],
                "game_date": g["game_date"],
                "kickoff_at": g["kickoff_at"],
                "neutral_site": g["neutral_site"],
                "conference_game": g["conference_game"],
                "venue_id": venue_ids.get(g["venue_source_id"] or ""),
                "home_team_id": team_ids[g["home_source_id"]],
                "away_team_id": team_ids[g["away_source_id"]],
                "home_points": g["home_points"],
                "away_points": g["away_points"],
                "status": g["status"],
            }
            for g in games
        ],
        new,
    )
    if unplaced:
        print(
            f"{len(unplaced)} games published without a venue (their venue has no name): "
            + ", ".join(unplaced[:20])
            + (" …" if len(unplaced) > 20 else "")
        )

    publish_lines(conn, source, map_lines(staged["lines"], games), game_ids, new)
    return {name: new[name] for name in TABLES}
