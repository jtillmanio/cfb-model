"""The CFBD endpoint registry, and `pull`: one counted call for one endpoint, season and week,
saved raw to the lake (D-112).

Every endpoint in docs/03-data-model.md › Data sources › CFBD is here, with the CFBD path, the
query params a call must send, and its granularity:
- `season`: one call per season (`/conferences` and `/venues` send no year but still file under
  `season=Y`);
- `week`: one call per week;
- `season_or_week`: either (`/games`, `/lines`, `/stats/game/advanced`);
- `static`: no season in the query (`/ppa/predicted`), filed under the season it was pulled for.

A week's file is never fetched again once it was saved after every game in that week completed
(CLAUDE.md: never re-fetch completed CFBD weeks); a season's file, once it was saved after every
game of its season type completed (TASK-021).
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Literal

from engine.clock import now
from engine.ingest.cfbd import CallBudget, CfbdClient
from engine.ingest.lake import (
    Lake,
    decode_raw,
    encode_raw,
    fetched_at_of,
    latest_raw,
    raw_folder,
    raw_key,
)

Granularity = Literal["season", "week", "season_or_week", "static"]
SEASON_TYPES = ("regular", "postseason")

# Every game with an FBS team; a flag and a partition in D-098, fixed here (D-112).
_FBS: Mapping[str, str] = {"classification": "fbs"}
# A season-level file is final only this long after the season type's last game, and an unscored
# game is done (canceled) this long after its start: CFBD can answer empty or partial just after
# the games (D-114, D-121).
SETTLE = timedelta(days=7)


@dataclass(frozen=True)
class Endpoint:
    path: str
    granularity: Granularity
    required: tuple[str, ...]
    fixed: Mapping[str, str] = field(default_factory=dict)
    season_type: bool = False  # sends seasonType, so postseason pulls are allowed


ENDPOINTS: dict[str, Endpoint] = {
    "teams": Endpoint("/teams", "season", ("year",)),
    "teams_fbs": Endpoint("/teams/fbs", "season", ("year",)),
    "conferences": Endpoint("/conferences", "season", ()),
    "venues": Endpoint("/venues", "season", ()),
    "games": Endpoint("/games", "season_or_week", ("year",), _FBS, season_type=True),
    "games_teams": Endpoint("/games/teams", "week", ("year", "week"), _FBS, season_type=True),
    # Garbage time excluded, the only variant pulled; staging reads it back from `params` (D-119)
    "stats_game_advanced": Endpoint(
        "/stats/game/advanced",
        "season_or_week",
        ("year",),
        {"excludeGarbageTime": "true"},
        season_type=True,
    ),
    "plays": Endpoint("/plays", "week", ("year", "week"), _FBS, season_type=True),
    "drives": Endpoint("/drives", "week", ("year", "week"), _FBS, season_type=True),
    "lines": Endpoint("/lines", "season_or_week", ("year",), season_type=True),
    "talent": Endpoint("/talent", "season", ("year",)),
    "player_returning": Endpoint("/player/returning", "season", ("year",)),
    "recruiting_teams": Endpoint("/recruiting/teams", "season", ("year",)),
    "ratings_sp": Endpoint("/ratings/sp", "season", ("year",)),
    "ratings_fpi": Endpoint("/ratings/fpi", "season", ("year",)),
    "ratings_elo": Endpoint("/ratings/elo", "season", ("year",)),
    "ppa_predicted": Endpoint("/ppa/predicted", "static", ("down", "distance")),
    "calendar": Endpoint("/calendar", "season", ("year",)),
}


def query(
    name: str,
    season: int,
    week: int | None = None,
    season_type: str = "regular",
    extra: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """The query a pull sends. Raises ValueError for a combination the endpoint can't take."""
    endpoint = ENDPOINTS[name]
    if endpoint.granularity == "week" and week is None:
        raise ValueError(f"{name} is pulled one week at a time: pass --week.")
    if endpoint.granularity in ("season", "static") and week is not None:
        raise ValueError(f"{name} is pulled for a whole season: drop --week.")
    if season_type not in SEASON_TYPES:
        raise ValueError(f"Unknown season type {season_type!r}.")
    if season_type != "regular" and not endpoint.season_type:
        raise ValueError(f"{name} has no season type: drop --season-type.")

    params: dict[str, Any] = {}
    if "year" in endpoint.required:
        params["year"] = season
    if week is not None:
        params["week"] = week
    if endpoint.season_type:
        params["seasonType"] = season_type
    params |= endpoint.fixed
    # --param only fills a required param no flag sets (ppa_predicted's down and distance).
    # Anything else (a year, a week, a filter) would file a different response under this
    # endpoint's season and week folder.
    allowed = set(endpoint.required) - set(params)
    refused = sorted(set(extra or {}) - allowed)
    if refused:
        raise ValueError(f"{name} doesn't take --param {', '.join(refused)}.")
    params |= extra or {}
    missing = [p for p in endpoint.required if p not in params]
    if missing:
        flags = " ".join(f"--param {p}=…" for p in missing)
        raise ValueError(f"{name} needs {flags}.")
    return params


def _done(game: Mapping[str, Any], saved_at: datetime) -> bool:
    """Completed, or unscored and started `SETTLE` before its /games file was saved: CFBD
    lists a canceled game (App State-Liberty 2024) as uncompleted forever (D-121)."""
    if game.get("completed"):
        return True
    unscored = game.get("homePoints") is None and game.get("awayPoints") is None
    return unscored and saved_at >= datetime.fromisoformat(game["startDate"]) + SETTLE


def week_complete(records: list[Any], week: int, season_type: str, saved_at: datetime) -> bool:
    """Every game of the week is done, by a /games file saved at `saved_at`."""
    games = [g for g in records if g.get("week") == week and g.get("seasonType") == season_type]
    return bool(games) and all(_done(g, saved_at) for g in games)


def _season_complete(records: list[Any], season_type: str, saved_at: datetime) -> datetime | None:
    """When the season type's last game started, if every one of its games is done."""
    games = [g for g in records if g.get("seasonType") == season_type]
    if not games or not all(_done(g, saved_at) for g in games):
        return None
    return max(datetime.fromisoformat(g["startDate"]) for g in games)


def _season_final(
    lake: Lake, name: str, season: int, season_type: str, key: str, records: list[Any]
) -> bool:
    """A season-level file is final when a saved season /games file, fetched no later than it,
    shows every game of its season type done (the postseason, for an endpoint with no
    season type), and it was saved `SETTLE` after that season type's last game, empty or not: a
    pull just after the games may not hold all of them yet. A /games file needs only itself."""
    games_type = season_type if ENDPOINTS[name].season_type else "postseason"
    if name == "games":
        return _season_complete(records, games_type, fetched_at_of(key)) is not None
    saved_at = fetched_at_of(key)
    for g in lake.list(raw_folder("games", season, None, games_type)):
        if not g.endswith(".parquet") or fetched_at_of(g) > saved_at:
            continue
        last = _season_complete(decode_raw(lake.read(g)), games_type, fetched_at_of(g))
        if last is not None and saved_at >= last + SETTLE:
            return True
    return False


def _is_final(
    lake: Lake, name: str, season: int, week: int | None, season_type: str, key: str
) -> bool:
    """A week-level file is final when it isn't empty, and a saved /games file covering that
    week (the week's own or the season's) shows every game done and was fetched no later
    than it. A season-level file follows `_season_final`."""
    records = decode_raw(lake.read(key))
    if week is None:
        return _season_final(lake, name, season, season_type, key, records)
    if name == "games":
        return week_complete(records, week, season_type, fetched_at_of(key))
    if not records:
        return False  # CFBD may not have filled the week in yet
    saved_at = fetched_at_of(key)
    games_files = [
        *lake.list(raw_folder("games", season, week, season_type)),
        *lake.list(raw_folder("games", season, None, season_type)),
    ]
    return any(
        g.endswith(".parquet")
        and fetched_at_of(g) <= saved_at
        and week_complete(decode_raw(lake.read(g)), week, season_type, fetched_at_of(g))
        for g in games_files
    )


def saved_final(
    lake: Lake, name: str, season: int, week: int | None = None, season_type: str = "regular"
) -> str | None:
    """The saved raw file a pull would reuse with no API call, if there is one."""
    saved = latest_raw(lake, raw_folder(name, season, week, season_type))
    if saved and _is_final(lake, name, season, week, season_type, saved):
        return saved
    return None


def pull(
    lake: Lake,
    name: str,
    season: int,
    week: int | None = None,
    season_type: str = "regular",
    extra: Mapping[str, str] | None = None,
    client: CfbdClient | None = None,
) -> str:
    """Pull one endpoint into the lake and return the raw file's key: the saved one if it's
    final, otherwise a new file from one counted CFBD call."""
    params = query(name, season, week, season_type, extra)
    saved = saved_final(lake, name, season, week, season_type)
    if saved:
        print(f"Using saved {saved} (complete); no API call.")
        return saved
    return fetch(lake, name, season, week, season_type, extra, client, params)


def fetch(
    lake: Lake,
    name: str,
    season: int,
    week: int | None = None,
    season_type: str = "regular",
    extra: Mapping[str, str] | None = None,
    client: CfbdClient | None = None,
    params: dict[str, Any] | None = None,
) -> str:
    """One counted CFBD call for the endpoint, saved as a new raw file, whatever is saved."""
    params = params or query(name, season, week, season_type, extra)
    client = client or CfbdClient(os.environ.get("CFBD_API_KEY", ""), CallBudget(lake))
    payload = client.get(ENDPOINTS[name].path, params)
    fetched_at = now()
    key = raw_key(raw_folder(name, season, week, season_type), fetched_at)
    lake.write_new(key, encode_raw(payload, params, fetched_at))
    count = len(payload) if isinstance(payload, list) else 1
    print(
        f"Fetched {count} records -> {key} "
        f"(CFBD calls this month: {client.budget.used()}/{client.budget.limit})"
    )
    return key
