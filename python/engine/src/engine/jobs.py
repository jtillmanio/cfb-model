"""`engine job results|lines` (TASK-022): the scheduled jobs' one entry point. In order:

1. **Pull** into the lake the jobs share (R2): `results`, every week of the current season with a
   game that started in the last `RECENT` (6 endpoints a week); `lines`, the earliest week with a
   game not yet kicked off (`/games` and `/lines`). Weeks come from the newest record of each game
   across the season's saved `/games` files; the season `/games` and `/calendar` files are pulled
   only when missing. A pull whose saved file is final makes no call (`endpoints.pull`).
2. **Stage** the season alone: its raw files are copied into a scratch lake on the runner, which
   is rebuilt. R2 `staging/` is never touched, and upserts never delete, so publishing one season
   leaves the others as they are.
3. **Check** the scratch staging; any failure raises `JobFailed` before a database is opened.
4. **Publish** it to the target in one transaction (`publish_lake`).

`Summary` is what the run did: the calls spent, the month's total, rows staged and new per table,
and the games counted as done only because they're unscored a week after their start (D-121):
a postponed game CFBD left under its old week would otherwise go unnoticed when it's played.
"""

from __future__ import annotations

import tempfile
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Literal

from db.session import make_engine
from engine import clock
from engine.ingest import endpoints
from engine.ingest.backfill import RAW, season_types, sync_raw
from engine.ingest.cfbd import MONTHLY_LIMIT, CallBudget, CfbdClient
from engine.ingest.lake import Lake, LocalLake, decode_raw, fetched_at_of, latest_raw, raw_folder
from engine.publish.staging import TABLES as PUBLISHED
from engine.publish.staging import publish_lake
from engine.transform import quality, rebuild

Kind = Literal["results", "lines"]
KINDS: tuple[Kind, ...] = ("results", "lines")
PULLS: dict[Kind, tuple[str, ...]] = {
    # /games first: every other week file is final only once a /games file saved no later than
    # it shows the week complete (endpoints._is_final).
    "results": ("games", "games_teams", "stats_game_advanced", "plays", "drives", "lines"),
    "lines": ("games", "lines"),
}
# Weeks `results` revisits: a Monday game (Labor Day) or the month-long bowl week settles after
# the week's own Sunday run.
RECENT = timedelta(days=14)
# Postgres table -> the staged table its rows come from.
STAGED = {
    "teams": "teams",
    "team_seasons": "team_seasons",
    "venues": "venues",
    "games": "games",
    "line_snapshots": "lines",
}

Week = tuple[str, int]  # (season_type, week)


class JobFailed(RuntimeError):
    def __init__(self, report: quality.Report) -> None:
        super().__init__(f"Data-quality checks failed: {', '.join(report.failures)}.")
        self.report = report


@dataclass
class Summary:
    kind: Kind
    season: int
    target: str
    weeks: list[Week] = field(default_factory=list)
    calls: int = 0
    month: str = ""
    month_calls: int = 0
    staged: dict[str, int] = field(default_factory=dict)
    new: dict[str, int] = field(default_factory=dict)
    canceled: list[str] = field(default_factory=list)
    report: quality.Report | None = None

    def render(self) -> str:
        weeks = ", ".join(f"{t} week {w}" for t, w in self.weeks) or "none due"
        out = [
            f"### `{self.kind}` {self.season} → {self.target}",
            "",
            f"- Weeks pulled: {weeks}",
            f"- CFBD calls this run: {self.calls}",
            f"- CFBD calls in {self.month}: {self.month_calls}/{MONTHLY_LIMIT}",
        ]
        if self.report is not None and not self.report.ok:
            out += ["", "**Nothing published: a data-quality check failed.**", "", "```"]
            out += [self.report.render(), "```"]
            return "\n".join(out)
        out += [
            "",
            "Every staged reference row is upserted; line snapshots are insert-only, so only new "
            "ones are written.",
            "",
            "| Table | Staged rows | New rows |",
            "|---|---|---|",
        ]
        for table in PUBLISHED:
            staged = self.staged.get(STAGED.get(table, ""))
            sent = "—" if staged is None else staged
            out.append(f"| {table} | {sent} | {self.new.get(table, 0)} |")
        if self.canceled:
            out += [
                "",
                f"Unscored, not completed and counted as done ({len(self.canceled)}): CFBD may "
                "have postponed one under its old week (D-121).",
            ]
            out += [f"- {item}" for item in self.canceled]
        return "\n".join(out)


def current_season(now: datetime) -> int:
    """The season a job works on: bowls in January belong to the season before."""
    return now.year if now.month >= 7 else now.year - 1


def _games(lake: Lake, season: int) -> dict[Any, tuple[dict[str, Any], datetime]]:
    """Each game's newest record across the season's saved /games files, with that file's
    save time."""
    newest: dict[Any, tuple[dict[str, Any], datetime]] = {}
    for key in lake.walk(f"{RAW}/games/season={season}"):  # no trailing "/": S3Lake adds it
        if not key.endswith(".parquet"):
            continue
        saved_at = fetched_at_of(key)
        for g in decode_raw(lake.read(key)):
            if g["id"] not in newest or newest[g["id"]][1] < saved_at:
                newest[g["id"]] = (g, saved_at)
    return newest


def _start(game: dict[str, Any]) -> datetime:
    return datetime.fromisoformat(game["startDate"])


def _order(week: Week) -> tuple[int, int]:
    return (0 if week[0] == "regular" else 1, week[1])


def due_weeks(kind: Kind, games: Iterable[dict[str, Any]], now: datetime) -> list[Week]:
    """`results`: weeks with a game that started in the last `RECENT`; `lines`: the earliest
    week with a game not yet kicked off."""
    games = list(games)
    if kind == "results":
        found = {(g["seasonType"], g["week"]) for g in games if now - RECENT <= _start(g) <= now}
        return sorted(found, key=_order)
    upcoming = sorted({(g["seasonType"], g["week"]) for g in games if _start(g) > now}, key=_order)
    return upcoming[:1]


def canceled(games: Iterable[tuple[dict[str, Any], datetime]]) -> list[str]:
    """Games done only by D-121's rule: unscored, not completed, a week past their start."""
    return sorted(
        f"{g['id']}: {g.get('awayTeam')} at {g.get('homeTeam')}, "
        f"{g['seasonType']} week {g['week']}, started {g['startDate']}"
        for g, saved_at in games
        if not g.get("completed") and endpoints.done(g, saved_at)
    )


def _pull_missing(lake: Lake, season: int, client: CfbdClient) -> None:
    """The season files the week choice and the publish need, when nothing is saved yet."""
    if latest_raw(lake, raw_folder("calendar", season)) is None:
        endpoints.fetch(lake, "calendar", season, client=client)
    for season_type in season_types(lake, season):
        if latest_raw(lake, raw_folder("games", season, None, season_type)) is None:
            endpoints.fetch(lake, "games", season, None, season_type, client=client)

def run(
    kind: Kind,
    lake: Lake,
    url: str,
    *,
    target: str,
    client: CfbdClient,
    summary: Summary | None = None,
) -> Summary:
    """Pull, stage, check and publish one job; see the module docstring. Raises `JobFailed`
    before opening `url` when a check fails, with `summary` filled in so far."""
    now = clock.now()
    season = current_season(now)
    summary = summary or Summary(kind, season, target)
    budget = CallBudget(lake)
    before = budget.used()
    try:
        _pull_missing(lake, season, client)
        summary.weeks = due_weeks(kind, (g for g, _ in _games(lake, season).values()), now)
        for season_type, week in summary.weeks:
            for name in PULLS[kind]:
                endpoints.pull(lake, name, season, week, season_type, client=client)
    finally:
        summary.month = clock.now().strftime("%Y-%m")
        summary.month_calls = budget.used()
        summary.calls = summary.month_calls - before

    with tempfile.TemporaryDirectory(prefix="cfb-job-") as tmp:
        scratch = LocalLake(Path(tmp))
        sync_raw(lake, scratch, seasons={season})
        summary.canceled = canceled(_games(scratch, season).values())
        summary.staged = rebuild(scratch)
        report = quality.run(scratch)
        print(report.render())
        if not report.ok:
            summary.report = report
            raise JobFailed(report)
        with make_engine(url).begin() as conn:
            summary.new = publish_lake(scratch, conn, report=report)
    return summary
