"""`engine job scores` (TASK-074, D-178): near-live scores during game windows, about every 30
minutes, so the record strip and contest results grade picks as games finish. In order:

1. **CFB** (skipped by an NFL-only run, `sport="nfl"`): one counted CFBD `/scoreboard` call (the
   current week, FBS by default), saved as a new raw file, `raw/cfbd/scoreboard/season=Y/`
   (append-only: each pull is its own file, never reused). The budget is spent before the call,
   so a spent budget stops the run (exit 3) before anything is saved or written.
2. **NFL check**: whether a live contest (not deleted) has an NFL game on its slate that kicked off
   in the last `NFL_WINDOW` and isn't `final` or `canceled`. The window keeps a game nflverse
   never scores (a canceled NFL game stays `scheduled`, D-169) from pulling every run.
3. **NFL pull**, only then: TASK-069's nflverse download (`nflverse.pull`, no CFBD call), staged
   in memory (`transform.nfl.stage`). A failed download is recorded and the CFB updates still go
   ahead; the run then raises `NflverseFailed` (exit 1), as `lines` does.
4. **Write**, in one transaction: each scoreboard record matched to its game by
   `(cfb, cfbd, id)`, never inserted. In progress: `in_progress` with the points, period and
   clock; completed: `final` with the points and the clock cleared; scheduled: nothing, since the
   job only moves games that have started. A game already `final` is never touched (the
   `results` job's box scores own corrections), and a row changes only when a value differs, so a
   rerun on the same scoreboard changes nothing. Then the season's NFL games, through the NFL
   publish with no lines: this job writes `games` (and the teams and venues they need) only, and
   the pull's lines reach `line_snapshots` at the next `lines` run.

Grading stays in the views (hard rule 1). The raw scoreboard files are kept, but `transform
--rebuild` doesn't read them: a rebuild reproduces final scores from `/games` once `results` has
pulled the week, not the passing in-progress status and clock (D-178)."""

from __future__ import annotations

import csv
import json
from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Literal

import httpx
from sqlalchemy import Connection, text

from db.session import make_engine
from engine import clock
from engine.ingest import endpoints, nflverse
from engine.ingest.cfbd import MONTHLY_LIMIT, CallBudget, CfbdClient
from engine.ingest.lake import Lake, decode_raw
from engine.jobs import NflverseFailed, current_season

Sport = Literal["all", "nfl"]
SPORTS: tuple[Sport, ...] = ("all", "nfl")
# How long after kickoff a contest's unfinished NFL game keeps the job pulling nflverse.
NFL_WINDOW = timedelta(hours=12)
# CFBD's scoreboard status -> games.status. "scheduled" writes nothing.
STATUSES = {"in_progress": "in_progress", "completed": "final"}


@dataclass(frozen=True, slots=True)
class Update:
    """What one scoreboard record writes to its game."""

    source_id: str
    status: str
    home_points: int | None
    away_points: int | None
    period: int | None
    clock: str | None


def _label(record: Mapping[str, Any]) -> str:
    return f"{record['id']}: {record['awayTeam']['name']} at {record['homeTeam']['name']}"


def updates(records: Iterable[Mapping[str, Any]]) -> tuple[list[Update], list[str]]:
    """The writes a scoreboard asks for, one per game (a game listed twice takes its last
    record, so the write never depends on which row Postgres's UPDATE … FROM picks), and the
    completed records with no score (not written: a final game needs both points)."""
    out: dict[str, Update] = {}
    unscored: list[str] = []
    for r in records:
        status = STATUSES.get(r["status"])
        if status is None:
            continue
        home, away = r["homeTeam"].get("points"), r["awayTeam"].get("points")
        if status == "final" and (home is None or away is None):
            unscored.append(_label(r))
            continue
        live = status == "in_progress"
        out[str(r["id"])] = Update(
            str(r["id"]),
            status,
            home,
            away,
            r.get("period") if live else None,
            r.get("clock") if live else None,
        )
    return list(out.values()), sorted(unscored)


# Every write is filtered twice: never a `final` row, and only when a value differs.
_UPDATE = text(
    """
    UPDATE games g
    SET status = v.status, home_points = v.home_points, away_points = v.away_points,
        period = v.period, clock = v.clock, updated_at = now()
    FROM jsonb_to_recordset(CAST(:rows AS jsonb)) AS v(
        source_id text, status text, home_points int, away_points int, period smallint, clock text)
    WHERE g.sport_id = 'cfb' AND g.source = 'cfbd' AND g.source_id = v.source_id
        AND g.status <> 'final'
        AND (g.status, g.home_points, g.away_points, g.period, g.clock)
            IS DISTINCT FROM (v.status, v.home_points, v.away_points, v.period, v.clock)
    RETURNING v.status
    """
)

_MATCHED = text(
    "SELECT source_id FROM games"
    " WHERE sport_id = 'cfb' AND source = 'cfbd' AND source_id = ANY(:ids)"
)


def apply(conn: Connection, writes: list[Update]) -> tuple[dict[str, int], set[str]]:
    """Write `writes` to their games, in the caller's transaction. Returns the games changed by
    new status, and the source ids that matched a game."""
    if not writes:
        return {}, set()
    ids = [w.source_id for w in writes]
    matched = set(conn.execute(_MATCHED, {"ids": ids}).scalars())
    rows = json.dumps(
        [
            {
                "source_id": w.source_id,
                "status": w.status,
                "home_points": w.home_points,
                "away_points": w.away_points,
                "period": w.period,
                "clock": w.clock,
            }
            for w in writes
        ]
    )
    changed = Counter(conn.execute(_UPDATE, {"rows": rows}).scalars())
    return dict(changed), matched


_NFL_LIVE = text(
    """
    SELECT EXISTS (
        SELECT 1
        FROM contest_lines l
        JOIN contests c ON c.id = l.contest_id
        JOIN games g ON g.id = l.game_id
        WHERE c.deleted_at IS NULL
            AND g.sport_id = 'nfl'
            AND g.status NOT IN ('final', 'canceled')
            AND g.kickoff_at <= :now
            AND g.kickoff_at > :since
    )
    """
)


def nfl_live(conn: Connection, now: datetime) -> bool:
    """Whether a live contest's slate has an NFL game kicked off in the last `NFL_WINDOW` that
    isn't final or canceled."""
    return bool(conn.execute(_NFL_LIVE, {"now": now, "since": now - NFL_WINDOW}).scalar_one())


_NFL_SCORES = text(
    "SELECT source_id, status, home_points, away_points FROM games"
    " WHERE sport_id = 'nfl' AND source = 'nflverse' AND season = :season"
)


def _nfl_scores(conn: Connection, season: int) -> dict[str, tuple[Any, ...]]:
    return {r[0]: tuple(r[1:]) for r in conn.execute(_NFL_SCORES, {"season": season})}


def publish_nfl_games(
    conn: Connection, staged: Mapping[str, list[dict[str, Any]]], season: int
) -> int:
    """The season's staged NFL games (with their teams and venues; no lines), in the caller's
    transaction. Returns how many existing games changed status or score."""
    from engine.publish.nfl import publish_nfl

    before = _nfl_scores(conn, season)
    games = [g for g in staged["nfl_games"] if g["season"] == season]
    publish_nfl(conn, games, [], staged["nfl_venues"])
    after = _nfl_scores(conn, season)
    return sum(1 for sid, row in before.items() if after.get(sid) != row)


@dataclass
class Summary:
    season: int
    target: str
    sport: Sport = "all"
    calls: int = 0
    month: str = ""
    month_calls: int = 0
    scoreboard: str | None = None
    records: int = 0
    cfb_updated: dict[str, int] = field(default_factory=dict)
    unmatched: list[str] = field(default_factory=list)
    unscored: list[str] = field(default_factory=list)
    nfl_live: bool = False
    nfl_updated: int = 0
    nfl_error: str | None = None

    def _cfb(self) -> list[str]:
        if self.sport == "nfl":
            return ["- CFB: not pulled (an NFL-only run)"]
        if self.scoreboard is None:
            return ["- CFB: the scoreboard wasn't pulled"]
        live, final = self.cfb_updated.get("in_progress", 0), self.cfb_updated.get("final", 0)
        out = [
            f"- Scoreboard: {self.records} games ({self.scoreboard})",
            f"- CFB games updated: {live + final} ({live} in progress, {final} final)",
        ]
        if self.unmatched:
            out.append(
                f"- Not matched to a game, so not written ({len(self.unmatched)}): "
                + "; ".join(self.unmatched)
            )
        if self.unscored:
            out.append(
                f"- Completed with no score, not written ({len(self.unscored)}): "
                + "; ".join(self.unscored)
            )
        return out

    def _nfl(self) -> list[str]:
        if self.nfl_error is not None:
            return [
                f"- **NFL (nflverse) download failed:** {self.nfl_error}. The CFB updates were "
                "still written."
            ]
        if not self.nfl_live:
            return ["- NFL: no contest NFL game is live; nflverse not pulled"]
        return [
            f"- NFL games updated: {self.nfl_updated} (a contest's NFL game is live; nflverse "
            "pulled)"
        ]

    def render(self) -> str:
        return "\n".join(
            [
                f"### `scores` {self.season} → {self.target}",
                "",
                f"- CFBD calls this run: {self.calls}",
                f"- CFBD calls in {self.month}: {self.month_calls}/{MONTHLY_LIMIT}",
                *self._cfb(),
                *self._nfl(),
            ]
        )


def run(
    lake: Lake,
    url: str,
    *,
    target: str,
    sport: Sport = "all",
    client: CfbdClient | None = None,
    summary: Summary | None = None,
    nfl_http: httpx.Client | None = None,
) -> Summary:
    """See the module docstring. Raises `BudgetExceededError` before anything is saved or written
    when the month's budget is spent, and `NflverseFailed` once the CFB updates are committed when
    the nflverse download failed."""
    now = clock.now()
    season = current_season(now)
    summary = summary or Summary(season, target, sport)
    summary.sport = sport

    writes: list[Update] = []
    labels: dict[str, str] = {}
    if sport == "all":
        budget = CallBudget(lake)
        before = budget.used()
        try:
            summary.scoreboard = endpoints.fetch(lake, "scoreboard", season, client=client)
        finally:
            summary.month = clock.now().strftime("%Y-%m")
            summary.month_calls = budget.used()
            summary.calls = summary.month_calls - before
        records = decode_raw(lake.read(summary.scoreboard))
        summary.records = len(records)
        writes, summary.unscored = updates(records)
        labels = {str(r["id"]): _label(r) for r in records}
    else:
        summary.month = clock.now().strftime("%Y-%m")
        summary.month_calls = CallBudget(lake).used()

    db = make_engine(url)
    try:
        with db.begin() as conn:
            summary.nfl_live = nfl_live(conn, now)
        staged = None
        if summary.nfl_live:
            try:
                nflverse.pull(lake, season, nfl_http)
                from engine.transform.nfl import stage

                staged = stage(lake)
            except (httpx.HTTPError, csv.Error, ValueError) as e:
                summary.nfl_error = f"{type(e).__name__}: {e}"
                print(f"nflverse download failed: {summary.nfl_error}")
        with db.begin() as conn:
            if writes:
                summary.cfb_updated, matched = apply(conn, writes)
                summary.unmatched = sorted(
                    labels[w.source_id] for w in writes if w.source_id not in matched
                )
            if staged is not None:
                summary.nfl_updated = publish_nfl_games(conn, staged, season)
    finally:
        db.dispose()
    if summary.nfl_error is not None:
        raise NflverseFailed(summary.nfl_error)
    return summary
