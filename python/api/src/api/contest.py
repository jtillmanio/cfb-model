"""The Contest page (TASK-071, D-174): one contest week's slate ranked against the contest's lines,
your entries, results and standing, plus the routes that take your picks and your standing.

**The page** is one wave of `QUERIES` (docs/02-architecture.md › Non-functional requirements: ≤ 6),
for the contest week asked for, else its newest week with lines by the API's clock.

- **Games:** each game's contest line is its newest snapshot captured by the API's clock and
  before the game's cutoff (the import's rule, as `current_contest_lines`). The market's line is
  the newest pull by the clock, priced like `/slate` (consensus, else the pull's median), else
  `game_market`'s close once the game has started, else its open. `differs` is true exactly when
  the two spreads differ.
- **The model** is the shell's shown version (`shell.SHOWN`, for the contest's season): each CFB
  game's newest prediction from a succeeded run finished by the clock and made before the cutoff.
  Edge, side and cover probability are against the contest line through `engine.core`, the way
  `/slate` computes them against the current line (D-158, D-143). A game with no prediction (an
  NFL game: no model yet, D-170) carries the market gap instead (`engine.core.contest`).
- **Ranking, top N and next best:** `engine.core.contest.rank` (04 § 4 › Contest mode, D-095).
- **Entries:** your live entries for the week, each at its contest line, made by the clock.
- **Results:** `contest_record` for you and the shown version (D-171): the season to date through
  the week, the weeks before it, and the week itself.
- **Standing:** your newest standing entered by the clock (`current_contest_standing`'s rule).

**Writes** run on the request's one connection (`main.connection`), upsert the caller's `users`
row first and lock the contest row, so two requests can't both take the last pick. A pick or a
removal on a game at or past its cutoff (`kickoff_at`, else the end of `game_date` in Eastern
time) is a 409 and writes nothing; so is a new pick past the contest's `picks_per_period`. A
change of side soft-deletes the live entry and inserts one at the current contest line (D-033).
Every row is stamped with the API's clock, as the import's snapshots are.
"""

from __future__ import annotations

from collections.abc import Hashable, Mapping, Sequence
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy import Connection, Row, text

from engine.core import (
    MarketGap,
    PickRules,
    RankRow,
    blended_margin,
    displayed_prob,
    market_gap,
    rank,
)
from engine.core.contest_rules import ContestRules
from engine.core.spec import fixed

from . import shell, slate
from .contest_import import github_id, upsert_user
from .shell import ShellOut
from .slate import SlateTeamOut, SlateVenueOut
from .wave import Query

Side = Literal["home", "away"]
QUERIES = ("shell", "contest", "games", "rules", "entries", "record")


# Requests


class EntryIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    game_id: int
    side: Side


class StandingIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    period: int = Field(ge=1)  # the contest week it was entered after
    position: int = Field(ge=1)
    field_size: int = Field(ge=1)
    points_behind_leader: float | None = Field(default=None, ge=0, le=9999.9)
    note: str | None = Field(default=None, max_length=500)

    @field_validator("points_behind_leader")
    @classmethod
    def _one_decimal(cls, value: float | None) -> float | None:
        """`contest_standings.points_behind_leader` is numeric(5,1): refuse what it would round."""
        if value is not None and abs(value * 10 - round(value * 10)) > 1e-9:
            raise ValueError("points behind the leader take at most one decimal place")
        return value

    @model_validator(mode="after")
    def _position_in_field(self) -> StandingIn:
        if self.position > self.field_size:
            raise ValueError("position can't be past the field size")
        return self


# Responses


class ContestModelOut(BaseModel):
    """The model's view against the contest line (a game it predicts: CFB)."""

    pred_margin: float  # home − away
    edge: float  # pred + contest spread, on the blended margin: > 0 likes home
    side: Side
    cover_prob: float  # P(side covers the contest line), as displayed (D-143)


class ContestMarketGapOut(BaseModel):
    """A game with no model ("no model yet"): the contest line against the market's."""

    points: float  # 0 when the lines agree
    side: Side | None  # the side the contest line gives more than the market does
    implied_prob: float  # P(that side covers) with the market's line as the median (D-174)


class ContestGameOut(BaseModel):
    id: int
    sport_id: str
    kickoff_at: datetime | None  # None: TBA
    game_date: date
    locks_at: datetime  # the cutoff: kickoff, else the end of game_date in Eastern time
    status: Literal["scheduled", "in_progress", "final", "canceled", "postponed"]
    neutral_site: bool
    venue: SlateVenueOut | None
    away: SlateTeamOut
    home: SlateTeamOut
    away_points: int | None
    home_points: int | None
    contest_line_id: int
    contest_spread_home: float
    contest_captured_at: datetime
    market_spread_home: float | None
    differs: bool  # the contest's and the market's spreads differ
    locked: bool  # at or past the cutoff by the API's clock
    rank: int  # in the open ranking; a locked game: where it stood before kickoff
    top_n: bool  # one of the model's top `picks_per_period`
    next_best: bool  # the first open game ranked below the top N
    no_model: bool  # no prediction: ranked on the market gap
    model: ContestModelOut | None
    market_gap: ContestMarketGapOut | None  # no-model games only


class ContestEntryOut(BaseModel):
    id: int
    game_id: int
    side: Side
    contest_line_id: int
    line: float  # the contest's spread_home it was made at
    created_at: datetime


class ContestTallyOut(BaseModel):
    wins: int
    losses: int
    pushes: int
    voids: int
    pending: int
    points: float


class ContestRecordOut(BaseModel):
    you: ContestTallyOut
    model: ContestTallyOut | None  # None: the shown version has no contest picks here


class ContestWeekRecordOut(ContestRecordOut):
    period: int


class ContestResultsOut(BaseModel):
    season: ContestRecordOut  # to date, through the page's week
    weeks: list[ContestWeekRecordOut]  # the weeks before the page's, oldest first
    this_week: ContestRecordOut


class ContestStandingOut(BaseModel):
    id: int
    period: int
    position: int
    field_size: int
    points_behind_leader: float | None
    note: str | None
    entered_at: datetime


class ContestRulesOut(BaseModel):
    sports: list[str]  # e.g. ["cfb", "nfl"]
    picks_per_period: int
    picks_exact: bool
    scoring: Literal["point_per_win", "confidence"]
    push: Literal["zero", "half", "void"]
    lock: Literal["per_game_kickoff", "fixed_time"]


class ContestOut(BaseModel):
    id: int
    name: str
    platform: str
    season: int
    rules: ContestRulesOut


class ContestCountsOut(BaseModel):
    games: int
    entries: int
    differs: int


class ContestPageOut(BaseModel):
    contest: ContestOut
    period: int | None  # None: no lines yet
    periods: list[int]  # every contest week with lines by now, oldest first
    games: list[ContestGameOut]  # the open games in rank order, then the locked ones
    entries: list[ContestEntryOut]  # yours this week, oldest first
    counts: ContestCountsOut
    results: ContestResultsOut | None  # None: no lines yet
    standing: ContestStandingOut | None
    shell: ShellOut


class ContestRefusalOut(BaseModel):
    code: Literal["locked", "full", "not_on_slate", "no_entry"]
    message: str


class ContestRefusalBody(BaseModel):
    detail: ContestRefusalOut


# The page's statements. Each starts with `_PREFIX`: the caller's contest (none when it isn't
# theirs or is deleted, so every statement reads nothing), the week and the shown version. With no
# contest id (the screen's `GET /contest`, TASK-072) it is the caller's first live contest, the
# default until `user_settings` names one (M8.7, D-175).

CUTOFF = shell.CUTOFF

_PREFIX = f"""
    WITH mine AS (
        SELECT c.id, c.season
        FROM contests c
        WHERE c.user_id = (SELECT u.id FROM users u WHERE u.github_id = :github)
            AND (CAST(:contest AS bigint) IS NULL OR c.id = :contest)
            AND c.deleted_at IS NULL
        ORDER BY c.id
        LIMIT 1
    ),
    page AS (
        SELECT coalesce(
            CAST(:period AS integer),
            (SELECT max(l.period) FROM contest_lines l
             WHERE l.contest_id = (SELECT id FROM mine) AND l.captured_at <= :now)
        ) AS period
    ),
    season AS (SELECT season FROM mine),
    {shell.SHOWN}"""

# The week's games: those with a contest line by the clock before their cutoff.
_LINES = f"""lines AS (
        SELECT DISTINCT ON (l.game_id) l.id, l.game_id, l.spread_home, l.captured_at
        FROM contest_lines l
        JOIN games g ON g.id = l.game_id
        WHERE l.contest_id = (SELECT id FROM mine)
            AND l.period = (SELECT period FROM page)
            AND l.captured_at <= :now
            AND l.captured_at < {CUTOFF}
        ORDER BY l.game_id, l.captured_at DESC, l.id DESC
    )"""

CONTEST_SQL = text(
    f"""{_PREFIX}
    SELECT c.id, c.name, c.platform, c.season, c.rules, (SELECT period FROM page) AS period,
        ARRAY(
            SELECT DISTINCT l.period FROM contest_lines l
            WHERE l.contest_id = c.id AND l.captured_at <= :now ORDER BY l.period
        ) AS periods,
        s.id AS standing_id, s.period AS standing_period, s.position, s.field_size,
        s.points_behind_leader, s.note, s.entered_at
    FROM mine m
    JOIN contests c ON c.id = m.id
    LEFT JOIN LATERAL (
        SELECT * FROM contest_standings s
        WHERE s.contest_id = c.id AND s.entered_at <= :now
        ORDER BY s.entered_at DESC, s.id DESC
        LIMIT 1
    ) s ON true
    """
)

# The predictions: each game's newest from the shown version's succeeded runs finished by the
# clock, made before its cutoff. A team's rank is entering its game's run's week.
GAMES_SQL = text(
    f"""{_PREFIX},
    {_LINES},
    preds AS (
        SELECT DISTINCT ON (p.game_id)
            p.game_id, p.pred_margin, p.margin_sd, p.model_run_id, r.week AS run_week,
            r.season_type AS run_season_type
        FROM predictions p
        JOIN model_runs r ON r.id = p.model_run_id
        JOIN games g ON g.id = p.game_id
        WHERE p.model_version_id = (SELECT id FROM shown)
            AND p.game_id = ANY(ARRAY(SELECT game_id FROM lines))
            AND r.model_version_id = (SELECT id FROM shown)
            AND r.status = 'succeeded'
            AND r.run_type IN ('scheduled', 'adhoc')
            AND r.finished_at <= :now
            AND p.created_at < {CUTOFF}
        ORDER BY p.game_id, r.finished_at DESC, r.id DESC
    ),
    ranks AS (
        SELECT r.team_id, r.season_type, r.week, r.rank
        FROM team_rankings r
        WHERE r.model_version_id = (SELECT id FROM shown)
            AND r.season = (SELECT season FROM season)
            AND r.week = ANY(ARRAY(SELECT run_week FROM preds))
    )
    SELECT
        g.id, g.sport_id, g.kickoff_at, g.game_date, g.status, g.neutral_site,
        g.home_points, g.away_points,
        {CUTOFF} AS cutoff,
        {CUTOFF} <= :now AS started,
        l.id AS contest_line_id, l.spread_home AS contest_spread_home,
        l.captured_at AS contest_captured_at,
        vn.name AS venue_name, vn.city AS venue_city, vn.state AS venue_state,
        {slate._team_columns("home", "ht", "hs", "hr")},
        {slate._team_columns("away", "awt", "aws", "ar")},
        mk.spread_home AS pulled_spread_home,
        gm.opening_spread_home, gm.closing_spread_home,
        p.pred_margin, p.margin_sd, p.model_run_id
    FROM lines l
    JOIN games g ON g.id = l.game_id
    JOIN teams ht ON ht.id = g.home_team_id
    JOIN teams awt ON awt.id = g.away_team_id
    LEFT JOIN team_seasons hs ON hs.team_id = g.home_team_id AND hs.season = g.season
    LEFT JOIN team_seasons aws ON aws.team_id = g.away_team_id AND aws.season = g.season
    LEFT JOIN preds p ON p.game_id = g.id
    LEFT JOIN ranks hr ON hr.team_id = g.home_team_id
        AND hr.week = p.run_week AND hr.season_type = p.run_season_type
    LEFT JOIN ranks ar ON ar.team_id = g.away_team_id
        AND ar.week = p.run_week AND ar.season_type = p.run_season_type
    LEFT JOIN venues vn ON vn.id = g.venue_id
    LEFT JOIN game_market gm ON gm.game_id = g.id
    LEFT JOIN LATERAL (
        SELECT coalesce(
            min(ls.spread_home) FILTER (WHERE b.source_id = 'consensus'),
            (percentile_cont(0.5) WITHIN GROUP (ORDER BY ls.spread_home))::numeric
        ) AS spread_home
        FROM line_snapshots ls
        JOIN sportsbooks b ON b.id = ls.book_id
        WHERE ls.game_id = g.id
            AND ls.kind = 'snapshot'
            AND ls.spread_home IS NOT NULL
            AND ls.captured_at = (
                SELECT max(x.captured_at) FROM line_snapshots x
                WHERE x.game_id = g.id AND x.kind = 'snapshot' AND x.spread_home IS NOT NULL
                    AND x.captured_at <= :now
            )
    ) mk ON true
    ORDER BY g.id
    """
)

# The shown version's spec, with the fitted params of each run that predicted a game of the week.
RULES_SQL = text(
    f"""{_PREFIX},
    {_LINES}
    SELECT v.spec, r.id AS run_id, r.fitted_params
    FROM shown s
    JOIN model_versions v ON v.id = s.id
    LEFT JOIN model_runs r ON r.model_version_id = s.id
        AND r.status = 'succeeded'
        AND r.finished_at <= :now
        AND r.id = ANY(ARRAY(
            SELECT DISTINCT p.model_run_id FROM predictions p
            WHERE p.model_version_id = (SELECT id FROM shown)
                AND p.game_id = ANY(ARRAY(SELECT game_id FROM lines))
        ))
    ORDER BY r.finished_at DESC NULLS LAST, r.id DESC
    """
)

ENTRIES_SQL = text(
    f"""{_PREFIX}
    SELECT e.id, e.game_id, e.side, e.contest_line_id, l.spread_home AS line, e.created_at
    FROM contest_entries e
    JOIN contest_lines l ON l.id = e.contest_line_id
    WHERE e.contest_id = (SELECT id FROM mine)
        AND e.deleted_at IS NULL
        AND l.period = (SELECT period FROM page)
        AND e.created_at <= :now
    ORDER BY e.created_at, e.id
    """
)

# contest_record reads no clock: under a fixture time an entry or contest pick stamped after the
# API's clock counts here but not in ENTRIES_SQL. With the real clock they agree (D-174).
RECORD_SQL = text(
    f"""{_PREFIX}
    SELECT r.picker, r.period, r.breakdown, r.wins, r.losses, r.pushes, r.voids, r.pending,
        r.points
    FROM contest_record r
    WHERE r.contest_id = (SELECT id FROM mine)
        AND r.period <= (SELECT period FROM page)
        AND (r.picker = 'you' OR r.model_version_id = (SELECT id FROM shown))
    ORDER BY r.period
    """
)


def queries(
    now: datetime, contest_id: int | None, subject: str, period: int | None
) -> dict[str, Query]:
    """The wave's statements by name, in `QUERIES` order."""
    params = {
        "now": now,
        "contest": contest_id,
        "github": github_id(subject),
        "period": period,
        "sport": shell.SPORT,  # the shown version's sport: the model covers CFB alone
    }
    return {
        "shell": shell.query(now, shell.SPORT),
        "contest": (CONTEST_SQL, params),
        "games": (GAMES_SQL, params),
        "rules": (RULES_SQL, params),
        "entries": (ENTRIES_SQL, params),
        "record": (RECORD_SQL, params),
    }


def _float(value: Decimal | float | None) -> float | None:
    return None if value is None else float(value)


def _market(row: Row[Any]) -> float | None:
    """`/slate`'s current line: the newest pull by the clock, else the close once started, else
    the open. game_market's open is its earliest snapshot, which under a fixture time can be
    captured after the API's clock; with the real clock it never is."""
    if row.pulled_spread_home is not None:
        return float(row.pulled_spread_home)
    if row.started and row.closing_spread_home is not None:
        return float(row.closing_spread_home)
    return _float(row.opening_spread_home)


def _model(
    row: Row[Any], line: float, rules: PickRules | None, params: Mapping[str, Any]
) -> ContestModelOut | None:
    if row.pred_margin is None or rules is None:
        return None
    dist = slate._distribution(params, _float(row.margin_sd))
    if dist is None:
        return None
    pred = float(row.pred_margin)
    k = fixed(rules.market_shrinkage_k, "picks.market_shrinkage_k")
    edge = blended_margin(pred, line, k) + line
    side: Side = "home" if edge >= 0 else "away"
    prob = displayed_prob(pred, line, side, rules, dist)
    return ContestModelOut(pred_margin=pred, edge=edge, side=side, cover_prob=prob)


def _gap(gap: MarketGap) -> ContestMarketGapOut:
    return ContestMarketGapOut(points=gap.points, side=gap.side, implied_prob=gap.prob)


def _tally(row: Row[Any] | None) -> ContestTallyOut:
    if row is None:
        return ContestTallyOut(wins=0, losses=0, pushes=0, voids=0, pending=0, points=0.0)
    return ContestTallyOut(
        wins=row.wins,
        losses=row.losses,
        pushes=row.pushes,
        voids=row.voids,
        pending=row.pending,
        points=float(row.points),
    )


def _results(rows: Sequence[Row[Any]], period: int) -> ContestResultsOut:
    by = {(r.picker, r.period, r.breakdown): r for r in rows}
    has_model = any(r.picker == "model" for r in rows)

    def record(p: int, breakdown: str) -> ContestRecordOut:
        you = _tally(by.get(("you", p, breakdown)))
        model = _tally(by.get(("model", p, breakdown))) if has_model else None
        return ContestRecordOut(you=you, model=model)

    periods = sorted({r.period for r in rows if r.period < period})
    weeks = [ContestWeekRecordOut(period=p, **record(p, "week").model_dump()) for p in periods]
    return ContestResultsOut(
        season=record(period, "to_date"), weeks=weeks, this_week=record(period, "week")
    )


def _standing(row: Row[Any]) -> ContestStandingOut | None:
    if row.standing_id is None:
        return None
    return ContestStandingOut(
        id=row.standing_id,
        period=row.standing_period,
        position=row.position,
        field_size=row.field_size,
        points_behind_leader=_float(row.points_behind_leader),
        note=row.note,
        entered_at=row.entered_at,
    )


def _no_contest() -> HTTPException:
    return HTTPException(404, "No such contest")


def page_from(found: Mapping[str, list[Row[Any]]], now: datetime) -> ContestPageOut:
    if not found["contest"]:
        raise _no_contest()
    c = found["contest"][0]
    rules = ContestRules.model_validate(c.rules)

    runs: dict[int, tuple[Mapping[str, Any], PickRules | None]] = {}
    for r in found["rules"]:
        if r.run_id is not None:
            run_params: Mapping[str, Any] = r.fitted_params or {}
            runs[r.run_id] = (run_params, slate._rules(r.spec, run_params))
    version = found["rules"][0] if found["rules"] else None
    params: Mapping[str, Any] = (version.fitted_params or {}) if version else {}
    version_rules = slate._rules(version.spec, params) if version else None

    built: dict[Hashable, dict[str, Any]] = {}
    ranking: list[RankRow] = []
    for r in found["games"]:
        line = float(r.contest_spread_home)
        market = _market(r)
        run_params, run_rules = runs.get(r.model_run_id, (params, version_rules))
        model = _model(r, line, run_rules, run_params)
        gap = None if model is not None or market is None else market_gap(line, market)
        locked = bool(r.started)
        built[r.id] = {
            "id": r.id,
            "sport_id": r.sport_id,
            "kickoff_at": r.kickoff_at,
            "game_date": r.game_date,
            "locks_at": r.cutoff,
            "status": r.status,
            "neutral_site": r.neutral_site,
            "venue": None
            if r.venue_name is None
            else SlateVenueOut(name=r.venue_name, city=r.venue_city, state=r.venue_state),
            "away": slate._team(r, "away"),
            "home": slate._team(r, "home"),
            "away_points": r.away_points,
            "home_points": r.home_points,
            "contest_line_id": r.contest_line_id,
            "contest_spread_home": line,
            "contest_captured_at": r.contest_captured_at,
            "market_spread_home": market,
            "differs": market is not None and market != line,
            "locked": locked,
            "no_model": model is None,
            "model": model,
            "market_gap": None if gap is None else _gap(gap),
        }
        prob = model.cover_prob if model else gap.prob if gap else 0.5
        ranking.append(
            RankRow(r.id, prob, model.edge if model else None, model is not None, locked, r.cutoff)
        )

    games = [
        ContestGameOut(**built[x.key], rank=x.rank, top_n=x.top_n, next_best=x.next_best)
        for x in rank(ranking, rules.picks_per_period)
    ]
    entries = [
        ContestEntryOut(
            id=e.id,
            game_id=e.game_id,
            side=e.side,
            contest_line_id=e.contest_line_id,
            line=float(e.line),
            created_at=e.created_at,
        )
        for e in found["entries"]
    ]
    return ContestPageOut(
        contest=ContestOut(
            id=c.id,
            name=c.name,
            platform=c.platform,
            season=c.season,
            rules=ContestRulesOut(
                sports=list(rules.sports),
                picks_per_period=rules.picks_per_period,
                picks_exact=rules.picks_exact,
                scoring=rules.scoring,
                push=rules.push,
                lock=rules.lock,
            ),
        ),
        period=c.period,
        periods=list(c.periods),
        games=games,
        entries=entries,
        counts=ContestCountsOut(
            games=len(games), entries=len(entries), differs=sum(g.differs for g in games)
        ),
        results=None if c.period is None else _results(found["record"], c.period),
        standing=_standing(c),
        shell=shell.shell_from(found["shell"][0], now),
    )


def load(
    conn: Connection,
    now: datetime,
    contest_id: int | None,
    subject: str,
    period: int | None = None,
) -> ContestPageOut:
    """The page on one connection (tests read it inside their rolled-back transaction)."""
    found = {
        name: list(conn.execute(sql, dict(params)).all())
        for name, (sql, params) in queries(now, contest_id, subject, period).items()
    }
    return page_from(found, now)


# Writes


def _refuse(code: str, message: str, status: int = 409) -> HTTPException:
    return HTTPException(status, {"code": code, "message": message})


def _lock_contest(conn: Connection, contest_id: int, subject: str) -> Row[Any]:
    """The caller's live contest, locked for the request's transaction; else 404."""
    row = conn.execute(
        text(
            "SELECT c.id, c.user_id, c.rules FROM contests c JOIN users u ON u.id = c.user_id"
            " WHERE c.id = :c AND u.github_id = :g AND c.deleted_at IS NULL FOR UPDATE OF c"
        ),
        {"c": contest_id, "g": github_id(subject)},
    ).one_or_none()
    if row is None:
        raise _no_contest()
    return row


# The game on the contest's slate, its cutoff, and its newest contest line by the clock.
_GAME_SQL = text(
    f"""
    SELECT g.id, {CUTOFF} <= :now AS started, l.id AS line_id, l.period, l.spread_home,
        EXISTS (
            SELECT 1 FROM contest_lines x
            WHERE x.contest_id = :c AND x.game_id = g.id AND x.captured_at <= :now
        ) AS on_slate
    FROM games g
    LEFT JOIN LATERAL (
        SELECT l.id, l.period, l.spread_home FROM contest_lines l
        WHERE l.contest_id = :c AND l.game_id = g.id AND l.captured_at <= :now
            AND l.captured_at < {CUTOFF}
        ORDER BY l.captured_at DESC, l.id DESC
        LIMIT 1
    ) l ON true
    WHERE g.id = :game
    """
)

_LIVE_ENTRY_SQL = text(
    "SELECT e.id, e.side, e.contest_line_id, e.created_at, l.spread_home AS line"
    " FROM contest_entries e JOIN contest_lines l ON l.id = e.contest_line_id"
    " WHERE e.user_id = :u AND e.contest_id = :c AND e.game_id = :game AND e.deleted_at IS NULL"
)


def _game(conn: Connection, contest_id: int, game_id: int, now: datetime) -> Row[Any]:
    row = conn.execute(_GAME_SQL, {"c": contest_id, "game": game_id, "now": now}).one_or_none()
    if row is None or not row.on_slate:
        raise _refuse("not_on_slate", "That game isn't on this contest's slate.", 404)
    if row.started:
        raise _refuse("locked", "That game has kicked off; its pick is final.")
    if row.line_id is None:  # only lines captured after the cutoff: none to pick at
        raise _refuse("not_on_slate", "That game isn't on this contest's slate.", 404)
    return row


def _soft_delete(conn: Connection, entry_id: int, now: datetime) -> None:
    conn.execute(
        text("UPDATE contest_entries SET deleted_at = :now WHERE id = :id AND deleted_at IS NULL"),
        {"id": entry_id, "now": now},
    )


def _entry_out(row: Row[Any], game_id: int) -> ContestEntryOut:
    return ContestEntryOut(
        id=row.id,
        game_id=game_id,
        side=row.side,
        contest_line_id=row.contest_line_id,
        line=float(row.line),
        created_at=row.created_at,
    )


def add_entry(
    conn: Connection, contest_id: int, subject: str, body: EntryIn, now: datetime
) -> ContestEntryOut:
    """Your pick on a game at its current contest line. The same side again changes nothing; the
    other side replaces the live entry."""
    upsert_user(conn, subject)
    contest = _lock_contest(conn, contest_id, subject)
    game = _game(conn, contest.id, body.game_id, now)
    live = conn.execute(
        _LIVE_ENTRY_SQL, {"u": contest.user_id, "c": contest.id, "game": game.id}
    ).one_or_none()
    if live is not None and live.side == body.side:
        return _entry_out(live, game.id)
    if live is None:
        limit = ContestRules.model_validate(contest.rules).picks_per_period
        taken = conn.execute(
            text(
                "SELECT count(*) FROM contest_entries e"
                " JOIN contest_lines l ON l.id = e.contest_line_id"
                " WHERE e.contest_id = :c AND e.deleted_at IS NULL AND l.period = :p"
            ),
            {"c": contest.id, "p": game.period},
        ).scalar_one()
        if taken >= limit:
            raise _refuse("full", f"This week already has its {limit} picks; remove one first.")
    else:
        _soft_delete(conn, live.id, now)
    inserted = conn.execute(
        text(
            "INSERT INTO contest_entries"
            " (user_id, contest_id, game_id, contest_line_id, side, created_at)"
            " VALUES (:u, :c, :game, :line, :side, :now)"
            " RETURNING id, side, contest_line_id, created_at"
        ),
        {
            "u": contest.user_id,
            "c": contest.id,
            "game": game.id,
            "line": game.line_id,
            "side": body.side,
            "now": now,
        },
    ).one()
    return ContestEntryOut(
        id=inserted.id,
        game_id=game.id,
        side=inserted.side,
        contest_line_id=inserted.contest_line_id,
        line=float(game.spread_home),
        created_at=inserted.created_at,
    )


def remove_entry(
    conn: Connection, contest_id: int, subject: str, game_id: int, now: datetime
) -> None:
    """Soft-deletes your live entry on the game (D-033)."""
    upsert_user(conn, subject)
    contest = _lock_contest(conn, contest_id, subject)
    live = conn.execute(
        _LIVE_ENTRY_SQL, {"u": contest.user_id, "c": contest.id, "game": game_id}
    ).one_or_none()
    if live is None:
        raise _refuse("no_entry", "You have no pick on that game.", 404)
    started = conn.execute(
        text(f"SELECT {CUTOFF} <= :now FROM games g WHERE g.id = :game"),
        {"game": game_id, "now": now},
    ).scalar_one()
    if started:
        raise _refuse("locked", "That game has kicked off; its pick is final.")
    _soft_delete(conn, live.id, now)


def add_standing(
    conn: Connection, contest_id: int, subject: str, body: StandingIn, now: datetime
) -> ContestStandingOut:
    """Your league standing as you read it off the contest's site, at the API's clock."""
    upsert_user(conn, subject)
    contest = _lock_contest(conn, contest_id, subject)
    row = conn.execute(
        text(
            "INSERT INTO contest_standings"
            " (contest_id, period, position, field_size, points_behind_leader, note, entered_at)"
            " VALUES (:c, :period, :position, :field_size, :behind, :note, :now)"
            " RETURNING id, period, position, field_size, points_behind_leader, note, entered_at"
        ),
        {
            "c": contest.id,
            "period": body.period,
            "position": body.position,
            "field_size": body.field_size,
            "behind": body.points_behind_leader,
            "note": body.note,
            "now": now,
        },
    ).one()
    return ContestStandingOut(
        id=row.id,
        period=row.period,
        position=row.position,
        field_size=row.field_size,
        points_behind_leader=_float(row.points_behind_leader),
        note=row.note,
        entered_at=row.entered_at,
    )
