"""This Week's data (TASK-055): every game of a week with its market, the model's line, edge,
cover and win probability, the current pick and how it's doing, the week's counts and the shown
version's pick rules, plus the shell block. One wave of `QUERIES` (docs/02-architecture.md ›
Non-functional requirements: ≤ 6).

- **Week:** the one asked for, else the coming week (`shell.COMING`, D-150); with neither (the
  off-season) no games and `offseason`.
- **Version and run:** the shell's shown version (`shell.SHOWN`, TASK-053), and its newest
  succeeded `scheduled` or `adhoc` run for the week finished by now, as `engine pick` reads it
  (D-140). Each game's prediction is that run's.
- **Edge, side and cover** are against the current line, for every game, through `engine.core`:
  the spec's pick rules resolved with the run's `choices`, and the run's empirical margin weights,
  else a normal margin at the prediction's σ, as `engine.publish.picks` picks with. The side is
  the one the blended edge favours and the cover probability is that side's as displayed
  (D-143), as a pass row describes a game. Rules the run never resolved leave all three null.
- **Pick:** the version's current market pick (`pick_outcomes` where `is_current`, the row
  `current_picks` shows), with the line it was made at, its own edge and probability, its result,
  units, CLV against the close and `clv_so_far` against the current line (D-142, D-140's sign).
- **Line history:** one entry per pull (`kind = 'snapshot'`) captured by now, priced like
  `game_market` (consensus, else the median of the pull's books).
- **Cover** on a final game is the side that covered the close (the current line when there's
  none), or `push`.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel
from sqlalchemy import Connection, Row, text

from engine.core import (
    EmpiricalMargin,
    MarginDistribution,
    ModelSpec,
    NormalMargin,
    PickRules,
    blended_margin,
    displayed_prob,
)
from engine.core.spec import fixed

from . import shell
from .shell import ShellOut
from .wave import Query

SeasonType = Literal["regular", "postseason"]
Side = Literal["home", "away"]
QUERIES = ("shell", "games", "lines", "picks", "rules")


class SlateTeamOut(BaseModel):
    id: int
    school: str
    abbreviation: str | None
    color: str | None
    logo_url: str | None  # D-146
    division: str | None  # `fbs`, `fcs`, … that season (D-047)
    rank: int | None  # the shown version's rank entering the week; FBS only


class SlateVenueOut(BaseModel):
    name: str
    city: str | None
    state: str | None


class SlateLineOut(BaseModel):
    captured_at: datetime
    spread_home: float


class SlateMarketOut(BaseModel):
    opening_spread_home: float | None
    current_spread_home: float | None
    closing_spread_home: float | None
    snapshots: list[SlateLineOut]  # pulls captured by now, oldest first


class SlateModelOut(BaseModel):
    pred_margin: float  # home − away
    home_win_prob: float
    edge: float | None  # against the current line: > 0 likes home
    side: Side | None  # the side the edge favours
    cover_prob: float | None  # P(side covers), as displayed (D-143)


class SlatePickOut(BaseModel):
    side: Side
    line: float  # spread_home it was picked at
    price: int
    edge: float  # at the line picked at
    cover_prob: float
    tier: Literal["A", "B", "C"] | None
    picked_at: datetime
    result: Literal["won", "lost", "push", "pending", "void"]
    units: float | None  # None while pending
    clv: float | None  # against the close, None until it exists
    clv_so_far: float | None  # against the current line


class SlateGameOut(BaseModel):
    id: int
    kickoff_at: datetime | None  # None: TBA
    game_date: date
    status: Literal["scheduled", "in_progress", "final", "canceled", "postponed"]
    neutral_site: bool
    venue: SlateVenueOut | None
    away: SlateTeamOut
    home: SlateTeamOut
    away_points: int | None
    home_points: int | None
    cover: Literal["home", "away", "push"] | None  # final games only
    market: SlateMarketOut
    model: SlateModelOut | None  # None: the run made no prediction for the game
    pick: SlatePickOut | None


class SlateTiersOut(BaseModel):
    A: float
    B: float
    C: float


class SlateRulesOut(BaseModel):
    """The shown version's pick rules (D-055), so the UI never hard-codes a threshold."""

    min_edge_pts: float
    min_prob: float
    tiers: SlateTiersOut


class SlateCountsOut(BaseModel):
    games: int
    picks: int


class SlateOut(BaseModel):
    season: int | None
    season_type: SeasonType | None
    week: int | None
    offseason: bool  # no week asked for and none to come
    rules: SlateRulesOut | None
    counts: SlateCountsOut
    games: list[SlateGameOut]
    shell: ShellOut


Week = tuple[int, SeasonType, int]

# The week, the shown version and its run for the week; each statement starts with it, so the
# wave needs nothing from a statement before it. CTEs a statement doesn't read aren't run.
_PREFIX = f"""
    WITH {shell.COMING},
    slate_week AS (
        SELECT
            coalesce(CAST(:season AS integer), c.season) AS season,
            coalesce(CAST(:season_type AS text), c.season_type) AS season_type,
            coalesce(CAST(:week AS integer), c.week) AS week
        FROM (SELECT 1) one
        LEFT JOIN coming c ON true
    ),
    season AS (SELECT season FROM slate_week),
    {shell.SHOWN},
    week_run AS (
        SELECT r.id, r.fitted_params
        FROM model_runs r
        JOIN slate_week w
            ON r.season = w.season AND r.season_type = w.season_type AND r.week = w.week
        WHERE r.model_version_id = (SELECT id FROM shown)
            AND r.status = 'succeeded'
            AND r.run_type IN ('scheduled', 'adhoc')
            AND r.finished_at <= :now
        ORDER BY r.finished_at DESC, r.id DESC
        LIMIT 1
    )"""

_WEEK_GAMES = """games g
    JOIN slate_week w
        ON g.season = w.season AND g.season_type = w.season_type AND g.week = w.week"""


def _team_columns(side: str, team: str, season: str, rank: str) -> str:
    return (
        f"{team}.id AS {side}_id, {team}.school AS {side}_school,"
        f" {team}.abbreviation AS {side}_abbreviation, {team}.color AS {side}_color,"
        f" {team}.logo_url AS {side}_logo_url, {season}.division AS {side}_division,"
        f" {rank}.rank AS {side}_rank"
    )


GAMES_SQL = text(
    f"""{_PREFIX},
    ranks AS (
        SELECT r.team_id, r.rank
        FROM team_rankings r
        JOIN slate_week w
            ON r.season = w.season AND r.season_type = w.season_type AND r.week = w.week
        WHERE r.model_version_id = (SELECT id FROM shown)
    )
    SELECT
        g.id, g.kickoff_at, g.game_date, g.status, g.neutral_site, g.home_points, g.away_points,
        vn.name AS venue_name, vn.city AS venue_city, vn.state AS venue_state,
        {_team_columns("home", "ht", "hs", "hr")},
        {_team_columns("away", "awt", "aws", "ar")},
        gm.opening_spread_home, gm.current_spread_home, gm.closing_spread_home,
        p.pred_margin, p.home_win_prob, p.margin_sd
    FROM {_WEEK_GAMES}
    JOIN teams ht ON ht.id = g.home_team_id
    JOIN teams awt ON awt.id = g.away_team_id
    LEFT JOIN team_seasons hs ON hs.team_id = g.home_team_id AND hs.season = g.season
    LEFT JOIN team_seasons aws ON aws.team_id = g.away_team_id AND aws.season = g.season
    LEFT JOIN ranks hr ON hr.team_id = g.home_team_id
    LEFT JOIN ranks ar ON ar.team_id = g.away_team_id
    LEFT JOIN venues vn ON vn.id = g.venue_id
    LEFT JOIN game_market gm ON gm.game_id = g.id
    LEFT JOIN predictions p ON p.model_run_id = (SELECT id FROM week_run) AND p.game_id = g.id
    WHERE g.sport_id = :sport
    ORDER BY {shell.CUTOFF}, g.id
    """
)

LINES_SQL = text(
    f"""{_PREFIX}
    SELECT
        ls.game_id,
        ls.captured_at,
        coalesce(
            min(ls.spread_home) FILTER (WHERE b.source_id = 'consensus'),
            (percentile_cont(0.5) WITHIN GROUP (ORDER BY ls.spread_home))::numeric
        ) AS spread_home
    FROM {_WEEK_GAMES}
    JOIN line_snapshots ls ON ls.game_id = g.id
    JOIN sportsbooks b ON b.id = ls.book_id
    WHERE g.sport_id = :sport
        AND ls.kind = 'snapshot'
        AND ls.spread_home IS NOT NULL
        AND ls.captured_at <= :now
    GROUP BY ls.game_id, ls.captured_at
    ORDER BY ls.game_id, ls.captured_at
    """
)

# pick_outcomes' window partition holds the version, so the filter applies at the picks scan.
PICKS_SQL = text(
    f"""{_PREFIX}
    SELECT
        o.game_id, o.side, o.line, o.price, o.model_prob, o.edge_pts, o.tier, o.created_at,
        o.result, o.units, o.clv, o.clv_so_far
    FROM pick_outcomes o
    JOIN slate_week w
        ON o.season = w.season AND o.season_type = w.season_type AND o.week = w.week
    WHERE o.model_version_id = (SELECT id FROM shown)
        AND o.is_current
        AND o.line_source = 'market'
    """
)

RULES_SQL = text(
    f"""{_PREFIX}
    SELECT v.spec, r.fitted_params
    FROM shown s
    JOIN model_versions v ON v.id = s.id
    LEFT JOIN week_run r ON true
    """
)


def queries(now: datetime, sport: str = shell.SPORT, week: Week | None = None) -> dict[str, Query]:
    """The wave's statements by name, in `QUERIES` order."""
    season, season_type, number = week or (None, None, None)
    params = {"now": now, "sport": sport, "season": season, "season_type": season_type,
              "week": number}  # fmt: skip
    return {
        "shell": shell.query(now, sport),
        "games": (GAMES_SQL, params),
        "lines": (LINES_SQL, params),
        "picks": (PICKS_SQL, params),
        "rules": (RULES_SQL, params),
    }


def _float(value: Decimal | float | None) -> float | None:
    return None if value is None else float(value)


def _rules(spec: Any, params: Mapping[str, Any]) -> PickRules | None:
    """The version's pick rules resolved with the run's choices; None when the spec is invalid
    or the run left a pick setting unresolved."""
    try:
        resolved = ModelSpec.model_validate(spec).resolve(params.get("choices") or {})
    except ValueError:  # pydantic's ValidationError is one
        return None
    if any(path.startswith("picks.") for path in resolved.tunables()):
        return None
    return resolved.picks


def _distribution(params: Mapping[str, Any], sd: float | None) -> MarginDistribution | None:
    try:
        weights = EmpiricalMargin.from_params(params)
    except (KeyError, ValueError):
        return None
    if weights is not None:
        return weights
    return NormalMargin(sd) if sd is not None and sd > 0 else None


def _model(
    row: Row[Any], rules: PickRules | None, params: Mapping[str, Any]
) -> SlateModelOut | None:
    if row.pred_margin is None:
        return None
    pred = float(row.pred_margin)
    line = _float(row.current_spread_home)
    dist = _distribution(params, _float(row.margin_sd))
    edge = side = prob = None
    if rules is not None and dist is not None and line is not None:
        k = fixed(rules.market_shrinkage_k, "picks.market_shrinkage_k")
        edge = blended_margin(pred, line, k) + line
        side = "home" if edge >= 0 else "away"
        prob = displayed_prob(pred, line, side, rules, dist)
    return SlateModelOut(
        pred_margin=pred,
        home_win_prob=float(row.home_win_prob),
        edge=edge,
        side=side,
        cover_prob=prob,
    )


def _team(row: Row[Any], side: str) -> SlateTeamOut:
    return SlateTeamOut(**{
        name: getattr(row, f"{side}_{name}")
        for name in ("id", "school", "abbreviation", "color", "logo_url", "division", "rank")
    })  # fmt: skip


def _cover(row: Row[Any]) -> Literal["home", "away", "push"] | None:
    if row.status != "final" or row.home_points is None or row.away_points is None:
        return None
    line = _float(row.closing_spread_home)
    line = _float(row.current_spread_home) if line is None else line
    if line is None:
        return None
    margin = row.home_points - row.away_points + line
    return "home" if margin > 0 else "away" if margin < 0 else "push"


def _pick(row: Row[Any]) -> SlatePickOut:
    return SlatePickOut(
        side=row.side,
        line=float(row.line),
        price=row.price,
        edge=float(row.edge_pts),
        cover_prob=float(row.model_prob),
        tier=row.tier,
        picked_at=row.created_at,
        result=row.result,
        units=_float(row.units),
        clv=_float(row.clv),
        clv_so_far=_float(row.clv_so_far),
    )


def _rules_out(rules: PickRules | None) -> SlateRulesOut | None:
    if rules is None:
        return None
    tiers = rules.tiers
    return SlateRulesOut(
        min_edge_pts=fixed(rules.min_edge_pts, "picks.min_edge_pts"),
        min_prob=fixed(rules.min_prob, "picks.min_prob"),
        tiers=SlateTiersOut(
            A=fixed(tiers.A, "picks.tiers.A"),
            B=fixed(tiers.B, "picks.tiers.B"),
            C=fixed(tiers.C, "picks.tiers.C"),
        ),
    )


def slate_from(
    found: Mapping[str, list[Row[Any]]], now: datetime, week: Week | None = None
) -> SlateOut:
    shell_out = shell.shell_from(found["shell"][0], now)
    version = found["rules"][0] if found["rules"] else None
    params: Mapping[str, Any] = (version.fitted_params or {}) if version else {}
    rules = _rules(version.spec, params) if version else None

    lines: dict[int, list[SlateLineOut]] = {}
    for r in found["lines"]:
        lines.setdefault(r.game_id, []).append(
            SlateLineOut(captured_at=r.captured_at, spread_home=float(r.spread_home))
        )
    picks = {r.game_id: _pick(r) for r in found["picks"]}
    games = [
        SlateGameOut(
            id=r.id,
            kickoff_at=r.kickoff_at,
            game_date=r.game_date,
            status=r.status,
            neutral_site=r.neutral_site,
            venue=None if r.venue_name is None else SlateVenueOut(
                name=r.venue_name, city=r.venue_city, state=r.venue_state
            ),
            away=_team(r, "away"),
            home=_team(r, "home"),
            away_points=r.away_points,
            home_points=r.home_points,
            cover=_cover(r),
            market=SlateMarketOut(
                opening_spread_home=_float(r.opening_spread_home),
                current_spread_home=_float(r.current_spread_home),
                closing_spread_home=_float(r.closing_spread_home),
                snapshots=lines.get(r.id, []),
            ),
            model=_model(r, rules, params),
            pick=picks.get(r.id),
        )
        for r in found["games"]
    ]  # fmt: skip

    if week is not None:
        season, season_type, number = week
    elif shell_out.week is not None:
        season, season_type, number = shell_out.season, shell_out.season_type, shell_out.week
    else:
        season = season_type = number = None
    return SlateOut(
        season=season,
        season_type=season_type,
        week=number,
        offseason=week is None and shell_out.week is None,
        rules=_rules_out(rules),
        counts=SlateCountsOut(games=len(games), picks=sum(g.pick is not None for g in games)),
        games=games,
        shell=shell_out,
    )


def load(
    conn: Connection, now: datetime, sport: str = shell.SPORT, week: Week | None = None
) -> SlateOut:
    """The slate on one connection (tests read it inside their rolled-back transaction)."""
    found = {
        name: list(conn.execute(sql, dict(params)).all())
        for name, (sql, params) in queries(now, sport, week).items()
    }
    return slate_from(found, now, week)
