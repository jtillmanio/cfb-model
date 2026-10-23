"""`engine backfill`: every CFBD endpoint the model uses, for a range of seasons, pulled into the
lake in an order that a stopped run resumes from without re-fetching anything final (TASK-021).

Each season goes in three stages, each planned from what the lake holds when it starts:
1. season-level `/games` (regular, then postseason) and `/calendar`;
2. `/games/teams`, `/plays` and `/drives` for every week whose games are all done (completed, or
   canceled), by the saved season `/games` file (the current week waits for the jobs);
3. season-level `/lines` and `/stats/game/advanced` for each season type, then `/teams`, talent,
   returning production, recruiting and SP+/FPI/Elo; `/venues` and `/conferences` once, under the
   last season (they take no year).
`/games` comes first because every other file is final only once a `/games` file saved before
it shows the games done (`endpoints._is_final`). A pull whose saved file is final is
skipped, so the dry run, a resumed run and a finished one count only what's left. `teams_fbs`
(staging uses `/teams`) and `ppa_predicted` (M3) aren't pulled.

`engine lake sync` copies every `raw/cfbd/` file one lake has and the other lacks, and never
overwrites one: the backfill writes to R2, and the local `./data` mirror feeds the rebuild.
"""

from __future__ import annotations

import os
import re
from collections import Counter
from collections.abc import Collection, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime

from engine.clock import now
from engine.ingest.cfbd import CallBudget, CfbdClient
from engine.ingest.endpoints import ENDPOINTS, fetch, saved_final, week_complete
from engine.ingest.lake import Lake, decode_raw, fetched_at_of, latest_raw, raw_folder

RAW = "raw/cfbd"
_SEASON = re.compile(rf"{RAW}/[^/]+/season=(\d+)/")
WEEKLY = ("games_teams", "plays", "drives")
BY_SEASON_TYPE = ("lines", "stats_game_advanced")
SEASON = (
    "teams",
    "talent",
    "player_returning",
    "recruiting_teams",
    "ratings_sp",
    "ratings_fpi",
    "ratings_elo",
)
ONCE = ("venues", "conferences")
# Weeks counted for a season with no saved /games file: CFBD's calendar has 15 or 16 regular
# weeks and one postseason week.
ESTIMATED_WEEKS = {"regular": 15, "postseason": 1}


@dataclass(frozen=True)
class Pull:
    endpoint: str
    season: int
    week: int | None = None
    season_type: str = "regular"
    estimated: bool = False  # a week counted before its season's /games file was saved


class Stopped(RuntimeError):
    """`--max-calls` reached before the next call."""


class _GamesCache:
    """The lake, with each `/games` raw file read once: every other file's final check reads
    them, and a raw file never changes."""

    def __init__(self, lake: Lake) -> None:
        self.lake = lake
        self.games: dict[str, bytes] = {}

    def read(self, key: str) -> bytes:
        if not key.startswith(f"{RAW}/games/"):
            return self.lake.read(key)
        if key not in self.games:
            self.games[key] = self.lake.read(key)
        return self.games[key]

    def write_new(self, key: str, data: bytes) -> None:
        self.lake.write_new(key, data)

    def list(self, folder: str) -> list[str]:
        return self.lake.list(folder)

    def read_text(self, key: str) -> str | None:
        return self.lake.read_text(key)

    def write_text(self, key: str, text: str) -> None:
        self.lake.write_text(key, text)

    def walk(self, prefix: str) -> list[str]:
        return self.lake.walk(prefix)

    def replace(self, key: str, data: bytes) -> None:
        self.lake.replace(key, data)


def season_types(lake: Lake, season: int) -> tuple[str, ...]:
    """Both season types once the postseason has started: by the saved calendar for the
    current season, always for an earlier one."""
    if season < now().year:
        return ("regular", "postseason")
    calendar = latest_raw(lake, raw_folder("calendar", season))
    started = calendar is not None and any(
        w.get("seasonType") == "postseason" and datetime.fromisoformat(w["startDate"]) <= now()
        for w in decode_raw(lake.read(calendar))
    )
    return ("regular", "postseason") if started else ("regular",)


def _estimated_weeks(season: int, season_type: str) -> list[int]:
    if season < now().year:
        return list(range(1, ESTIMATED_WEEKS[season_type] + 1))
    if season_type == "postseason":
        return [1]
    played = (now() - datetime(season, 9, 1, tzinfo=UTC)).days // 7  # weeks finished so far
    return list(range(1, max(0, min(played, ESTIMATED_WEEKS["regular"])) + 1))


def _first(lake: Lake, season: int, last: bool) -> Iterator[Pull]:
    for season_type in season_types(lake, season):
        yield Pull("games", season, None, season_type)
    yield Pull("calendar", season)


def _weekly(lake: Lake, season: int, last: bool) -> Iterator[Pull]:
    for season_type in season_types(lake, season):
        games = latest_raw(lake, raw_folder("games", season, None, season_type))
        if games is None:
            weeks, estimated = _estimated_weeks(season, season_type), True
        else:
            records = decode_raw(lake.read(games))
            weeks = sorted({g["week"] for g in records if g.get("seasonType") == season_type})
            saved_at = fetched_at_of(games)
            weeks = [w for w in weeks if week_complete(records, w, season_type, saved_at)]
            estimated = False
        for week in weeks:
            for name in WEEKLY:
                yield Pull(name, season, week, season_type, estimated)


def _last(lake: Lake, season: int, last: bool) -> Iterator[Pull]:
    for name in BY_SEASON_TYPE:
        for season_type in season_types(lake, season):
            yield Pull(name, season, None, season_type)
    for name in SEASON:
        yield Pull(name, season)
    if last:
        for name in ONCE:
            yield Pull(name, season)


STAGES = (_first, _weekly, _last)


def _missing(lake: Lake, pulls: Iterator[Pull]) -> list[Pull]:
    return [p for p in pulls if not saved_final(lake, p.endpoint, p.season, p.week, p.season_type)]


def plan(lake: Lake, first: int, last: int) -> list[Pull]:
    """Every pull a run would make now, one CFBD call each. No client is constructed."""
    lake = _GamesCache(lake)
    return [
        pull
        for season in range(first, last + 1)
        for stage in STAGES
        for pull in _missing(lake, stage(lake, season, season == last))
    ]


def render(pulls: list[Pull], first: int, last: int, budget: CallBudget) -> str:
    counts = Counter(p.endpoint for p in pulls)
    out = [f"Backfill {first}-{last}: pulls not final in the lake yet, one CFBD call each"]
    out += [f"  {name:<20} {counts[name]:>5}" for name in ENDPOINTS if counts[name]]
    out.append(f"  {'total':<20} {len(pulls):>5}")
    estimated = sum(p.estimated for p in pulls)
    if estimated:
        out.append(
            f"{estimated} estimated: weekly pulls for seasons with no saved /games file, counted "
            f"at {ESTIMATED_WEEKS['regular']} regular weeks and 1 postseason week (this season: "
            "the weeks played so far)."
        )
    out.append(f"CFBD calls this month: {budget.used()}/{budget.limit}")
    return "\n".join(out)


def client_for(lake: Lake) -> CfbdClient:
    return CfbdClient(os.environ.get("CFBD_API_KEY", ""), CallBudget(lake))


def run(lake: Lake, first: int, last: int, client: CfbdClient, max_calls: int | None = None) -> int:
    """Pull everything `plan` lists except estimated weeks, re-planning each stage from what's
    saved by then, and return the calls made. The client's budget raises BudgetExceededError
    before a call that would exceed the month's; `max_calls` raises Stopped before call
    `max_calls + 1`."""
    lake = _GamesCache(lake)
    calls = 0
    for season in range(first, last + 1):
        for stage in STAGES:
            for p in _missing(lake, stage(lake, season, season == last)):
                if p.estimated:
                    continue  # no saved /games file shows the week complete (the dry run counts it)
                if max_calls is not None and calls >= max_calls:
                    raise Stopped(f"Stopped at --max-calls {max_calls}.")
                fetch(lake, p.endpoint, p.season, p.week, p.season_type, client=client)
                calls += 1
    return calls


def _in(key: str, seasons: Collection[int] | None) -> bool:
    return seasons is None or ((m := _SEASON.match(key)) is not None and int(m[1]) in seasons)


def sync_raw(src: Lake, dst: Lake, seasons: Collection[int] | None = None) -> list[str]:
    """Copy every raw CFBD file `src` has and `dst` lacks, only those filed under `seasons` when
    it's given; return their keys. Nothing else (the ledger, staging/) is copied, and no file in
    `dst` is overwritten."""
    have = set(dst.walk(RAW))
    missing = [key for key in src.walk(RAW) if key not in have and _in(key, seasons)]
    for key in missing:
        dst.write_new(key, src.read(key))
    return missing
