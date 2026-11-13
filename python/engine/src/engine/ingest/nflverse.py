"""`engine ingest nflverse`: the NFL schedule, scores and lines from nflverse's `games.csv`
(nfldata) into the raw lake (D-039, TASK-069).

The file is a free download outside CFBD's call budget, one row per game since 1999. A pull keeps
the requested season's rows, each as the CSV gives it (every value a string, empty when unknown),
and saves them as a new raw file `raw/nflverse/games/season=Y/fetched_at=….parquet` with params
`{"season": Y}`, so the lake stays append-only: a second pull is a second file. The pull time is
the line's capture time (D-120), so every pull is kept.

A season whose newest saved file holds the Super Bowl and has every game scored is over, and
isn't downloaded again.
"""

from __future__ import annotations

import csv
import io
from typing import Any

import httpx

from engine import clock
from engine.ingest.lake import Lake, decode_raw, encode_raw, latest_raw, raw_key

URL = "https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv"
RAW = "raw/nflverse"
DATASET = "games"


def raw_folder(season: int) -> str:
    return f"{RAW}/{DATASET}/season={season}"


def _client() -> httpx.Client:
    """The client a pull uses when none is given (the tests replace it, so none downloads)."""
    return httpx.Client(timeout=60, follow_redirects=True)


def download(http: httpx.Client | None = None) -> str:
    """The whole file's text. Raises `httpx.HTTPError` on a failed download."""
    client = http or _client()
    try:
        response = client.get(URL)
        response.raise_for_status()
        return response.text
    finally:
        if http is None:
            client.close()


def season_rows(text: str, season: int) -> list[dict[str, Any]]:
    """The file's rows for `season`, in file order. Refuses a file without the columns the
    staging reads, so a renamed column fails the pull rather than staging NULLs."""
    reader = csv.DictReader(io.StringIO(text))
    missing = sorted(REQUIRED - set(reader.fieldnames or ()))
    if missing:
        raise ValueError(f"nflverse games.csv lacks {', '.join(missing)}")
    return [dict(row) for row in reader if row["season"] == str(season)]


REQUIRED = {
    "game_id",
    "season",
    "game_type",
    "week",
    "gameday",
    "gametime",
    "away_team",
    "home_team",
    "away_score",
    "home_score",
    "location",
    "spread_line",
    "total_line",
    "away_moneyline",
    "home_moneyline",
    "roof",
    "surface",
    "stadium_id",
    "stadium",
}


def _scored(row: dict[str, Any]) -> bool:
    return bool(row.get("home_score")) and bool(row.get("away_score"))


def season_over(lake: Lake, season: int) -> bool:
    """The newest saved file has the Super Bowl and every game scored."""
    key = latest_raw(lake, raw_folder(season))
    if key is None:
        return False
    rows = decode_raw(lake.read(key))
    return any(r.get("game_type") == "SB" for r in rows) and all(_scored(r) for r in rows)


def pull(lake: Lake, season: int, http: httpx.Client | None = None) -> str | None:
    """Download the file and save `season`'s rows as a new raw file; returns its key, or None
    when the season is over and nothing was downloaded."""
    if season_over(lake, season):
        print(f"nflverse {season}: the saved file is final; not downloaded again.")
        return None
    rows = season_rows(download(http), season)
    fetched_at = clock.now()
    key = raw_key(raw_folder(season), fetched_at)
    lake.write_new(key, encode_raw(rows, {"season": season}, fetched_at))
    print(f"nflverse {season}: saved {len(rows)} games to {key}.")
    return key
