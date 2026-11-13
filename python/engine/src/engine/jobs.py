"""`engine job results|lines` (TASK-022): the scheduled jobs' one entry point. In order:

1. **Pull** into the lake the jobs share (R2): `results`, every week of the current season with a
   game that started in the last `RECENT` (6 endpoints a week); `lines`, the week of the earliest
   kickoff still to come (`/games` and `/lines`), so a game CFBD moved to a later date under its
   old week doesn't hold `lines` on that week (TASK-047). Weeks come from the newest record of
   each game across the season's saved `/games` files; the season `/games` and `/calendar` files
   are pulled only when missing. A pull whose saved file is final makes no call (`endpoints.pull`).
   Once the season is over (its postseason has started and no saved game is still to come), the
   next season's `/calendar` alone, once, so the off-season app names that season and its
   kickoff (D-164, TASK-065); in July, when the jobs move to that season, they pull its
   calendar once more (`_pull_missing`).
2. **Stage** the season and the next one (off-season, only its calendar is saved): their raw
   files, plus every season's `/venues` and `/conferences` (pulled once, filed under the
   backfill's last season), are copied into a scratch lake on the runner, which is rebuilt.
   The season's `/teams` is pulled when missing too. Teams and venues aren't per season, and
   the publish rewrites every column of a reference row (D-120): staged from `/games` alone,
   they'd overwrite production's mascots, colors and venue details with NULL.
   R2 `staging/` is never touched, and upserts never delete, so the other seasons' games and lines
   stay as they are.
3. **Check** the scratch staging; any failure raises `JobFailed` before a database is opened.
4. **Publish** it to the target in one transaction (`publish_lake`).

`lines` also pulls the season's NFL schedule, scores and lines from nflverse first (TASK-069,
`ingest.nflverse`), and both jobs stage and publish the season's saved nflverse files with the CFB
rows. A failed nflverse download doesn't stop the CFBD pull or the publish: the run carries on
with the nflverse files already saved, names the failure in its summary, and then raises
`NflverseFailed` (exit 1).


`lines` then re-evaluates picks (TASK-045's writer) in a second transaction, once the snapshots
are committed: for each version, its newest `scheduled` run in the season, and when that run is
a postseason one, the newest of every postseason round, since bowls still to come belong to round
1's run after round 2 is rated (D-161); at the job's clock. A pick that fails rolls back the picks
alone and the run exits 1; the snapshots stay published.

`Summary` is what the run did: the calls spent, the month's total, rows staged and new per table,
and the games counted as done only because they're unscored a week after their start (D-121):
a postponed game CFBD left under its old week would otherwise go unnoticed when it's played.

`engine job rate-and-predict` (TASK-046, `rate_and_predict`) is the weekly cycle, and makes no
CFBD call: it reads the lake the morning's `results` and `lines` filled. It takes the week
`lines` would pull (the week of the earliest kickoff still to come) and stops, writing nothing,
when no game is still to come. From the first bowl to the title game that's postseason week 1,
every bowl and CFP game: each Sunday rates it again at the same `as_of`, the first bowl's
kickoff, so the ratings don't change and the CFP games are predicted once their teams are known
(D-131, D-150). A `rounds` version rates a CFP round instead: once the rebuild has placed each
game in its round, the highest round with a game still to come whose teams are both known, at the
round's `as_of`; with none it writes nothing (D-161). `lines` keeps pulling CFBD's week, which is
postseason week 1 whichever round is rated. The job resolves the season's settings from a
backtest's `run.json`, copies every
season's raw files into a scratch lake and rebuilds it (the prior and the margin model read every
earlier season), checks it, and fits the week before opening the database; then one transaction
inserts a `scheduled` run with its ratings and predictions (creating the named version as
`candidate` the first time) and the picks from it. When the week is postseason the summary also
names the postseason games still to come that no succeeded run of the version predicted: a
`rounds` version doesn't rate a round again once it has moved past it, so a bowl whose teams
appeared after that Sunday is never predicted (D-161, TASK-063). A dry run does all of it and
rolls the transaction back.
"""

from __future__ import annotations

import csv
import tempfile
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Literal, cast

import httpx
from sqlalchemy import Connection, text

from db.session import make_engine
from engine import clock
from engine.backtest import harness
from engine.core.spec import ModelSpec
from engine.ingest import endpoints, nflverse
from engine.ingest.backfill import ONCE, RAW, season_types, sync_raw
from engine.ingest.cfbd import MONTHLY_LIMIT, CallBudget, CfbdClient
from engine.ingest.lake import Lake, LocalLake, decode_raw, fetched_at_of, latest_raw, raw_folder
from engine.publish import models, picks
from engine.publish.lines import cutoff
from engine.publish.staging import NFL_KEYS, publish_lake
from engine.publish.staging import TABLES as PUBLISHED
from engine.transform import quality, rebuild
from engine.transform.features import PointInTimeError

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
# How long an off-season pull of the next season's calendar that came back with no weeks is kept
# before it's tried again (`_pull_next_calendar`): about one call a day until CFBD has the schedule.
EMPTY_RETRY = timedelta(days=1)
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


class NflverseFailed(RuntimeError):
    """The nflverse download failed; the rest of the run went ahead without it."""


class PicksFailed(RuntimeError):
    """`lines` published its snapshots, but re-evaluating the picks failed and was rolled back."""


SCHEDULED = ("scheduled",)  # the run type the jobs write, and the only one they pick from


@dataclass(frozen=True, slots=True)
class Repicked:
    """One week's picks of a version re-evaluated by `lines`: the week of its newest scheduled
    run, or one of its postseason weeks when that run is postseason (D-161)."""

    version_id: int
    version: str
    week: Week
    summary: picks.PickSummary


def _picked(s: picks.PickSummary) -> str:
    return (
        f"{s.picks} picks, {s.passes} passes written; {s.games} predicted games, "
        f"{s.open} before their cutoff"
    )


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
    repicked: list[Repicked] | None = None
    repick_error: str | None = None
    # Off-season only: the next season and the weeks its saved calendar holds.
    next_calendar: tuple[int, int] | None = None
    # `lines` only: why the nflverse download failed, else None.
    nfl_error: str | None = None

    def _nfl(self) -> list[str]:
        if self.nfl_error is not None:
            return [
                "",
                f"- **NFL (nflverse) download failed:** {self.nfl_error}. The run went on with "
                "the nflverse files already saved.",
            ]
        if not any(key in self.new for key in NFL_KEYS):
            return []
        return [
            "",
            f"- NFL (nflverse): {self.staged.get('nfl_games', 0)} games staged; new: "
            f"{self.new.get('nfl_games', 0)} games, "
            f"{self.new.get('nfl_line_snapshots', 0)} line rows",
        ]

    def _repicks(self) -> list[str]:
        out = ["", "Picks re-evaluated against the newest lines (each version's newest scheduled "
               "run this season, and in the postseason each round's):"]
        if self.repick_error is not None:
            out.append(
                f"- **Not re-evaluated; the picks were rolled back:** {self.repick_error}. The "
                "snapshots above were published."
            )
        elif not self.repicked:
            out.append("- none: no version has a scheduled run this season")
        for r in self.repicked or []:
            s = r.summary
            out.append(f"- {r.version}, {r.week[0]} week {r.week[1]}, run {s.run_id}: {_picked(s)}")
        return out

    def render(self) -> str:
        weeks = ", ".join(f"{t} week {w}" for t, w in self.weeks) or "none due"
        out = [
            f"### `{self.kind}` {self.season} → {self.target}",
            "",
            f"- Weeks pulled: {weeks}",
            f"- CFBD calls this run: {self.calls}",
            f"- CFBD calls in {self.month}: {self.month_calls}/{MONTHLY_LIMIT}",
        ]
        if self.next_calendar is not None:
            year, weeks = self.next_calendar
            held = f"{weeks} weeks" if weeks else "no weeks yet (tried again a day after the pull)"
            out.append(f"- Next season's calendar: {year}, {held}")
        if self.report is not None and not self.report.ok:
            out += ["", "**Nothing published: a data-quality check failed.**", "", "```"]
            out += [self.report.render(), "```"]
            return "\n".join(out + self._nfl())
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
        out += self._nfl()
        if self.canceled:
            out += [
                "",
                f"Unscored, not completed and counted as done ({len(self.canceled)}): CFBD may "
                "have postponed one under its old week (D-121).",
            ]
            out += [f"- {item}" for item in self.canceled]
        if self.repicked is not None or self.repick_error is not None:
            out += self._repicks()
        return "\n".join(out)


@dataclass
class WeeklySummary:
    """What `rate_and_predict` did: the week it rated (or why none), the run and its picks."""

    season: int
    target: str
    version: str
    dry_run: bool = False
    week: Week | None = None
    note: str = ""
    staged: dict[str, int] = field(default_factory=dict)
    report: quality.Report | None = None
    run: models.RunSummary | None = None
    picks: picks.PickSummary | None = None
    # Postseason weeks only: "Away at Home (date)" for each game still to come with no prediction.
    unpredicted: list[str] | None = None

    def render(self) -> str:
        rated = f"{self.week[0]} week {self.week[1]}" if self.week else f"none: {self.note}"
        out = [
            f"### `rate-and-predict` {self.season} → {self.target}",
            "",
            f"- Version: {self.version}",
            f"- Week rated: {rated}",
            "- CFBD calls this run: 0",
        ]
        if self.report is not None and not self.report.ok:
            out += ["", "**Nothing written: a data-quality check failed.**", "", "```"]
            out += [self.report.render(), "```"]
            return "\n".join(out)
        if self.run is not None:
            run = self.run
            out.append(
                f"- Run {run.run_id} {run.status}: {run.ratings} ratings, "
                f"{run.predictions} predictions"
            )
            if run.error:
                out.append(f"- **The fit failed** (recorded as a failed run): {run.error}")
        if self.picks is not None:
            out.append(f"- Picks: {_picked(self.picks)}")
        if self.unpredicted == []:
            out.append("- Postseason games still to come with no prediction: none")
        elif self.unpredicted:
            out.append(
                "- **Postseason games still to come with no prediction** (a round the job has "
                f"moved past isn't rated again, D-161): {'; '.join(self.unpredicted)}"
            )
        if self.dry_run and self.run is not None:
            out += ["", "**Dry run: the transaction was rolled back, so nothing was written.**"]
        return "\n".join(out)


def _engine(url: str) -> Any:
    """The target's engine at READ COMMITTED, pinned rather than left to the server's default: a
    transaction reads before `write_picks` takes D-148's lock on the version, and only under READ
    COMMITTED does the read after the lock see the other writer's committed pick."""
    return make_engine(url).execution_options(isolation_level="READ COMMITTED")


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
    """`results`: weeks with a game that started in the last `RECENT`; `lines`: the week of the
    earliest kickoff still to come. A game postponed to a later date keeps its old week, so the
    earliest week with a game to come could be one already played, every week until it's made up
    (TASK-047)."""
    games = list(games)
    if kind == "results":
        found = {(g["seasonType"], g["week"]) for g in games if now - RECENT <= _start(g) <= now}
        return sorted(found, key=_order)
    upcoming = [g for g in games if _start(g) > now]
    if not upcoming:
        return []
    first = min(upcoming, key=lambda g: (_start(g), _order((g["seasonType"], g["week"]))))
    return [(first["seasonType"], first["week"])]


def canceled(games: Iterable[tuple[dict[str, Any], datetime]]) -> list[str]:
    """Games done only by D-121's rule: unscored, not completed, a week past their start."""
    return sorted(
        f"{g['id']}: {g.get('awayTeam')} at {g.get('homeTeam')}, "
        f"{g['seasonType']} week {g['week']}, started {g['startDate']}"
        for g, saved_at in games
        if not g.get("completed") and endpoints.done(g, saved_at)
    )


def _pull_missing(lake: Lake, season: int, client: CfbdClient) -> None:
    """The season files the week choice and the publish need, when nothing is saved yet. A
    calendar saved before the season became the jobs' season is the off-season copy
    (`_pull_next_calendar`), pulled once more: CFBD may have added weeks since, and
    `season_types` reads it to start the bowl pulls."""
    for name in ("calendar", "teams"):
        saved = latest_raw(lake, raw_folder(name, season))
        early = name == "calendar" and saved and current_season(fetched_at_of(saved)) < season
        if saved is None or early:
            endpoints.fetch(lake, name, season, client=client)
    for season_type in season_types(lake, season):
        if latest_raw(lake, raw_folder("games", season, None, season_type)) is None:
            endpoints.fetch(lake, "games", season, None, season_type, client=client)


def _pull_next_calendar(
    lake: Lake, season: int, games: Iterable[dict[str, Any]], now: datetime, client: CfbdClient
) -> tuple[int, int] | None:
    """Once `season` is over, the next season's `/calendar` alone, so the off-season shell can
    name it and its kickoff (D-164) before July, when the jobs move to it and pull its games.
    Over: the season's last calendar week (the postseason) has started, so its bowls are among
    the saved games (`season_types`), and no saved game is still to come, the title game too.
    Saved once: a saved calendar costs no call, unless it has no weeks (pulled before CFBD had
    the schedule) and is `EMPTY_RETRY` old, then it's pulled again. Returns the next season and
    its saved weeks, or None while `season` is still going."""
    calendar = latest_raw(lake, raw_folder("calendar", season))
    starts = [_start(w) for w in decode_raw(lake.read(calendar))] if calendar else []
    games = list(games)
    if not starts or max(starts) > now or not games or due_weeks("lines", games, now):
        return None
    following = season + 1
    saved = latest_raw(lake, raw_folder("calendar", following))
    weeks = decode_raw(lake.read(saved)) if saved else []
    if saved is None or (not weeks and now - fetched_at_of(saved) >= EMPTY_RETRY):
        weeks = decode_raw(lake.read(endpoints.fetch(lake, "calendar", following, client=client)))
    return following, len(weeks)


def run(
    kind: Kind,
    lake: Lake,
    url: str,
    *,
    target: str,
    client: CfbdClient,
    summary: Summary | None = None,
    nfl_http: httpx.Client | None = None,
) -> Summary:
    """Pull, stage, check and publish one job; see the module docstring. Raises `JobFailed`
    before opening `url` when a check fails, with `summary` filled in so far, and
    `NflverseFailed` once the rest is done when `lines` couldn't download nflverse's file."""
    now = clock.now()
    season = current_season(now)
    summary = summary or Summary(kind, season, target)
    if kind == "lines":
        try:
            nflverse.pull(lake, season, nfl_http)
        except (httpx.HTTPError, csv.Error, ValueError) as e:
            summary.nfl_error = f"{type(e).__name__}: {e}"
            print(f"nflverse download failed: {summary.nfl_error}")
    budget = CallBudget(lake)
    before = budget.used()
    try:
        _pull_missing(lake, season, client)
        summary.weeks = due_weeks(kind, (g for g, _ in _games(lake, season).values()), now)
        for season_type, week in summary.weeks:
            for name in PULLS[kind]:
                endpoints.pull(lake, name, season, week, season_type, client=client)
        games = (g for g, _ in _games(lake, season).values())
        summary.next_calendar = _pull_next_calendar(lake, season, games, now, client)
    finally:
        summary.month = clock.now().strftime("%Y-%m")
        summary.month_calls = budget.used()
        summary.calls = summary.month_calls - before

    with tempfile.TemporaryDirectory(prefix="cfb-job-") as tmp:
        scratch = LocalLake(Path(tmp))
        # The next season's raw files too: off-season that's only its calendar, staged so the
        # publish writes its `seasons` row.
        sync_raw(lake, scratch, seasons={season, season + 1}, every_season=ONCE)
        summary.canceled = canceled(_games(scratch, season).values())
        summary.staged = rebuild(scratch)
        report = quality.run(scratch)
        print(report.render())
        if not report.ok:
            summary.report = report
            raise JobFailed(report)
        db = _engine(url)
        try:
            with db.begin() as conn:
                summary.new = publish_lake(scratch, conn, report=report)
            if kind == "lines":
                _repick(db, season, summary)
        finally:
            db.dispose()
    if summary.nfl_error is not None:
        raise NflverseFailed(summary.nfl_error)
    return summary


def reevaluate(conn: Connection, season: int, now: datetime) -> list[Repicked]:
    """Each live, unretired version's picks, from its newest succeeded `scheduled` run in
    `season` finished by `now` (the week the weekly job last rated), against the newest
    snapshots, in the caller's transaction. When that run is postseason, every postseason week
    the version rated is re-picked from its own newest run: a `rounds` version's bowls are round
    1's, still to come after round 2 is rated (D-161). The writer skips games already past their
    cutoff."""
    rows = conn.execute(
        text(
            "SELECT DISTINCT model_version_id, season_type, week, name, version FROM ("
            "SELECT r.model_version_id, r.season_type, r.week, v.name, v.version,"
            " first_value(r.season_type) OVER newest AS newest_type,"
            " first_value(r.week) OVER newest AS newest_week"
            " FROM model_runs r JOIN model_versions v ON v.id = r.model_version_id"
            " WHERE v.sport_id = :sport AND v.market = :market AND v.deleted_at IS NULL"
            " AND v.status <> 'retired'"
            " AND r.run_type = ANY(:types) AND r.status = 'succeeded' AND r.season = :season"
            " AND r.finished_at <= :now"
            " WINDOW newest AS (PARTITION BY r.model_version_id"
            " ORDER BY r.finished_at DESC, r.id DESC)"
            ") runs WHERE season_type = newest_type"
            " AND (season_type = 'postseason' OR week = newest_week)"
            " ORDER BY model_version_id, week"
        ),
        {
            "sport": picks.SPORT,
            "market": picks.MARKET,
            "types": list(SCHEDULED),
            "season": season,
            "now": now,
        },
    ).all()
    return [
        Repicked(
            r.model_version_id,
            f"{r.name} {r.version}",
            (r.season_type, r.week),
            picks.write_picks(
                conn,
                r.model_version_id,
                season,
                r.week,
                now,
                run_types=SCHEDULED,
                season_type=r.season_type,
            ),
        )
        for r in rows
    ]


def _repick(db: Any, season: int, summary: Summary) -> None:
    """`reevaluate` in its own transaction, after the snapshots are committed."""
    try:
        with db.begin() as conn:
            summary.repicked = reevaluate(conn, season, clock.now())
    except (picks.PicksRefused, PointInTimeError) as e:
        summary.repick_error = f"{type(e).__name__}: {e}"
        raise PicksFailed(summary.repick_error) from e


class _DryRun(Exception):
    """Raised inside a dry run's transaction so it rolls back."""


# The season's postseason games, not canceled, that no succeeded run of the version predicted,
# read in the job's transaction so its own run counts. Whether each is still to come is its
# cutoff (`lines.cutoff`, as the pick writer reads it) against the clock, not its status.
_UNPREDICTED = text(
    """
    SELECT g.kickoff_at, g.game_date, awt.school AS away, ht.school AS home
    FROM games g
    JOIN teams ht ON ht.id = g.home_team_id
    JOIN teams awt ON awt.id = g.away_team_id
    WHERE g.sport_id = :sport
        AND g.season = :season
        AND g.season_type = 'postseason'
        AND g.status <> 'canceled'
        AND NOT EXISTS (
            SELECT 1
            FROM predictions p
            JOIN model_runs r ON r.id = p.model_run_id
            WHERE p.game_id = g.id
                AND p.model_version_id = :version
                AND r.status = 'succeeded'
                AND r.run_type IN ('scheduled', 'adhoc')
        )
    ORDER BY g.game_date, g.kickoff_at NULLS LAST, g.id
    """
)


def _unpredicted(conn: Connection, version_id: int, season: int, now: datetime) -> list[str]:
    """Each postseason game still to come that the version never predicted, as "Away at Home
    (date)"."""
    rows = conn.execute(
        _UNPREDICTED, {"sport": models.SPORT, "season": season, "version": version_id}
    ).all()
    return [
        f"{r.away} at {r.home} ({r.game_date.isoformat()})"
        for r in rows
        if cutoff(r.kickoff_at, r.game_date) > now
    ]


def coming_week(lake: Lake, season: int, now: datetime) -> Week | None:
    """The week `lines` would pull: the week of the earliest kickoff still to come."""
    due = due_weeks("lines", (g for g, _ in _games(lake, season).values()), now)
    return due[0] if due else None


def rate_and_predict(
    lake: Lake,
    url: str,
    *,
    spec: ModelSpec,
    run: Mapping[str, Any] | None,
    name: str,
    version: str,
    target: str,
    dry_run: bool = False,
    summary: WeeklySummary | None = None,
) -> WeeklySummary:
    """The weekly cycle; see the module docstring. Raises `JobFailed` before opening `url` when
    a check fails, `models.RateRefused` or `picks.PicksRefused` on a refusal (nothing written),
    and `PointInTimeError` from the fit or the picks (nothing written)."""
    now = clock.now()
    season = current_season(now)
    summary = summary or WeeklySummary(season, target, f"{name} {version}", dry_run)
    week = coming_week(lake, season, now)
    if week is None:
        summary.note = f"no game of {season} is still to be played"
        return summary
    season_type = cast(models.SeasonType, week[0])
    summary.week = week
    choices = models.settings(spec, run, season)

    with tempfile.TemporaryDirectory(prefix="cfb-job-") as tmp:
        scratch = LocalLake(Path(tmp))
        sync_raw(lake, scratch)
        summary.staged = rebuild(scratch)
        report = quality.run(scratch)
        print(report.render())
        if not report.ok:
            summary.report = report
            raise JobFailed(report)
        history = None
        if season_type == "postseason" and spec.postseason == "rounds":
            history = harness.load(scratch)
            coming = models.coming_round(history, season, now)
            if coming is None:
                summary.week = None
                summary.note = "no postseason game still to come has both teams known"
                return summary
            week = (week[0], coming)
            summary.week = week
        fitted = models.fit_week(
            scratch,
            spec,
            choices,
            season=season,
            week=week[1],
            season_type=season_type,
            history=history,
        )

    db = _engine(url)
    try:
        with db.begin() as conn:
            summary.run = models.write(
                conn,
                fitted,
                spec,
                name=name,
                version=version,
                run_type="scheduled",
                status="candidate",
            )
            if summary.run.status == "succeeded":
                summary.picks = picks.write_picks(
                    conn,
                    picks.version_id(conn, name, version),
                    season,
                    week[1],
                    clock.now(),
                    run_types=SCHEDULED,
                    season_type=season_type,
                )
            if season_type == "postseason":
                summary.unpredicted = _unpredicted(
                    conn, picks.version_id(conn, name, version), season, clock.now()
                )
            if dry_run:
                raise _DryRun
    except _DryRun:
        pass
    finally:
        db.dispose()
    return summary
