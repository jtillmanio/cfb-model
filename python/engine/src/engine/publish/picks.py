"""`engine pick`: a model run's predictions turned into spread picks against the newest posted
line, re-evaluated when the line moves (TASK-045; D-140, D-142, D-148).

Everything is read from the database, so the `lines` job re-evaluates without refitting: the
version's newest succeeded run for the week (`adhoc` or `scheduled`, by `finished_at`, then id),
its predictions, the pick rules (the version's spec resolved with the `choices` the run stored),
the margin distribution (the run's `fitted_params`: the empirical weights, else a normal margin at
the prediction's σ) and each team's division that season. A game is picked through
`core.picks.pick_game` with CFB's `pickable`, so no game with an FCS team is (D-047).

**The line.** A pick points at one book's row of the newest pull (`kind = 'snapshot'`) that
quoted a spread, captured before the game's cutoff and no later than the writer's clock. Of that
pull's books it takes `consensus`, else DraftKings, else Bovada, else the first by name (`BOOKS`,
D-148): one book a bettor could take, the same one from pull to pull while it keeps quoting. The
price is the picked side's, −110 when the row quotes none (D-132).

**When a row is written.** Only when the side or tier differs from the game's current pick
(`current_picks`), so a pick keeps the line it was made at while the line drifts; a pass row
(no side, no tier, 0 units) when a current pick stops qualifying, describing the side the
blended edge favours; nothing for a game that was never picked and still isn't.

**Point in time** (hard rule 4, D-142). No row for a game at or after its cutoff (kickoff, or
the end of `game_date` in Eastern time when TBA): the views would ignore it. Every row's
`created_at` is the writer's clock, the same instant the cutoff was checked against.

Insert-only (hard rule 2): the writer never updates or deletes a pick. `write_picks` runs in the
caller's transaction, holding a lock on the version until it commits; `publish_picks` opens one
on the target's direct URL. A clock earlier than a pick already made for the week's games is
refused, as is a run that finished after it.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any, cast

from pydantic import ValidationError
from sqlalchemy import Connection, text

from db.session import make_engine
from engine.core.interfaces import GameContext
from engine.core.picks import displayed_prob, pick_game
from engine.core.probability import (
    EmpiricalMargin,
    MarginDistribution,
    NormalMargin,
    Side,
    blended_margin,
    expected_value,
)
from engine.core.spec import ModelSpec, PickRules, fixed
from engine.publish.lines import cutoff
from engine.sports.cfb import teams
from engine.transform.features import PointInTimeError

SPORT = "cfb"
MARKET = "spread"
NO_PRICE = -110  # D-132
BOOKS = ("consensus", "DraftKings", "Bovada")  # D-148: the first of these the pull quotes
RUN_TYPES = ("adhoc", "scheduled")  # a backtest run spans seasons and has no week
LOCK = "engine.publish.picks"  # the advisory lock's first key; the second is the version id


class PicksRefused(ValueError):
    """There is nothing to pick from, and nothing was written."""


@dataclass(frozen=True, slots=True)
class PickSummary:
    run_id: int
    picks: int
    passes: int


@dataclass(frozen=True, slots=True)
class Snapshot:
    """One book's spread in one pull."""

    id: int
    book: str
    captured_at: datetime
    spread_home: float
    home_price: int | None
    away_price: int | None

    def price(self, side: Side) -> int:
        quoted = self.home_price if side == "home" else self.away_price
        return NO_PRICE if quoted is None else quoted


def choose_snapshot(rows: Iterable[Snapshot], cut: datetime, now: datetime) -> Snapshot | None:
    """The row a pick uses: the newest pull before `cut` and no later than `now`, and of its
    books the first in `BOOKS`, else the first by name, then the lowest id (two sources can
    quote one book in a pull); None when there's no such pull."""
    seen = [r for r in rows if r.captured_at < cut and r.captured_at <= now]
    if not seen:
        return None
    newest = max(r.captured_at for r in seen)
    pull = [r for r in seen if r.captured_at == newest]
    rank = {book: i for i, book in enumerate(BOOKS)}
    return min(pull, key=lambda r: (rank.get(r.book, len(BOOKS)), r.book, r.id))


def _run(conn: Connection, version_id: int, season: int, week: int, now: datetime) -> Any:
    """The version's newest succeeded run for the week that had finished by `now`."""
    run = conn.execute(
        text(
            "SELECT r.id, r.as_of, r.fitted_params, v.spec FROM model_runs r"
            " JOIN model_versions v ON v.id = r.model_version_id"
            " WHERE r.model_version_id = :v AND r.season = :season AND r.week = :week"
            " AND r.status = 'succeeded' AND r.run_type = ANY(:types) AND r.finished_at <= :now"
            " ORDER BY r.finished_at DESC, r.id DESC LIMIT 1"
        ),
        {"v": version_id, "season": season, "week": week, "types": list(RUN_TYPES), "now": now},
    ).one_or_none()
    if run is None:
        raise PicksRefused(
            f"version {version_id} has no succeeded run for {season} week {week} finished by "
            f"{now}: run engine rate first"
        )
    return run


def _rules(spec: Any, params: Mapping[str, Any]) -> PickRules:
    """The version's pick rules, resolved with the settings the run was fit with."""
    try:
        resolved = ModelSpec.model_validate(spec).resolve(params.get("choices") or {})
    except (ValidationError, ValueError) as e:
        raise PicksRefused(f"the run's pick rules can't be resolved: {e}") from e
    open_rules = [path for path in resolved.tunables() if path.startswith("picks.")]
    if open_rules:
        raise PicksRefused(f"the run chose no setting for {', '.join(open_rules)}")
    return resolved.picks


def _games(conn: Connection, run_id: int) -> list[Any]:
    return list(
        conn.execute(
            text(
                "SELECT p.id AS prediction_id, p.pred_margin, p.margin_sd, g.id AS game_id,"
                " g.season, g.season_type, g.week, g.kickoff_at, g.game_date, g.neutral_site,"
                " g.home_team_id, g.away_team_id, hs.division AS home_division,"
                " aws.division AS away_division"
                " FROM predictions p JOIN games g ON g.id = p.game_id"
                " LEFT JOIN team_seasons hs ON hs.team_id = g.home_team_id"
                " AND hs.season = g.season"
                " LEFT JOIN team_seasons aws ON aws.team_id = g.away_team_id"
                " AND aws.season = g.season"
                " WHERE p.model_run_id = :run ORDER BY g.id"
            ),
            {"run": run_id},
        ).all()
    )


def _snapshots(conn: Connection, game_ids: list[int], now: datetime) -> dict[int, list[Snapshot]]:
    found: dict[int, list[Snapshot]] = {}
    for r in conn.execute(
        text(
            "SELECT ls.id, ls.game_id, b.source_id AS book, ls.captured_at, ls.spread_home,"
            " ls.spread_home_price, ls.spread_away_price"
            " FROM line_snapshots ls JOIN sportsbooks b ON b.id = ls.book_id"
            " WHERE ls.game_id = ANY(:games) AND ls.kind = 'snapshot'"
            " AND ls.spread_home IS NOT NULL AND ls.captured_at <= :now"
        ),
        {"games": game_ids, "now": now},
    ):
        found.setdefault(r.game_id, []).append(
            Snapshot(
                r.id,
                r.book,
                r.captured_at,
                float(r.spread_home),
                r.spread_home_price,
                r.spread_away_price,
            )
        )
    return found


def _distribution(
    params: Mapping[str, Any], sd: float | None, prediction: int
) -> MarginDistribution:
    """The margin distribution the run predicted with: its empirical weights, else a normal margin
    at the prediction's σ."""
    try:
        weights = EmpiricalMargin.from_params(params)
    except KeyError as e:
        raise PicksRefused(f"the run's empirical weights have no {e}") from e
    if weights is not None:
        return weights
    if sd is None:
        raise PicksRefused(f"prediction {prediction} has no margin_sd to pick with")
    return NormalMargin(sd)


def _newest_pick(conn: Connection, version_id: int, game_ids: list[int]) -> datetime | None:
    return conn.execute(
        text(
            "SELECT max(created_at) FROM picks WHERE model_version_id = :v"
            " AND game_id = ANY(:games)"
        ),
        {"v": version_id, "games": game_ids},
    ).scalar_one()


def _current(conn: Connection, version_id: int, game_ids: list[int]) -> dict[int, tuple[Any, Any]]:
    """Each game's current market pick as (side, tier); a game with none is absent."""
    return {
        r.game_id: (r.side, r.tier)
        for r in conn.execute(
            text(
                "SELECT game_id, side, tier FROM current_picks WHERE model_version_id = :v"
                " AND market = :market AND line_source = 'market' AND game_id = ANY(:games)"
            ),
            {"v": version_id, "market": MARKET, "games": game_ids},
        )
    }


def _insert(conn: Connection, row: Mapping[str, Any]) -> None:
    conn.execute(
        text(
            "INSERT INTO picks (prediction_id, model_version_id, game_id, line_snapshot_id, market,"
            " side, line, price, model_prob, edge_pts, expected_value, tier, stake_units,"
            " created_at) VALUES (:prediction_id, :model_version_id, :game_id,"
            " :line_snapshot_id, :market, :side, :line, :price, :model_prob, :edge_pts,"
            " :expected_value, :tier, :stake_units, :created_at)"
        ),
        dict(row),
    )


def write_picks(
    conn: Connection,
    version_id: int,
    season: int,
    week: int,
    now: datetime,
    pickable: Callable[[GameContext], bool] | None = None,
) -> PickSummary:
    """Pick the week's games from the version's newest succeeded run at `now`, in the caller's
    transaction, inserting only what changes a game's current pick. A transaction-scoped lock on
    the version makes a second writer (the weekly run against a lines pull) wait for this one to
    commit, so both never read the same current pick."""
    conn.execute(
        text("SELECT pg_advisory_xact_lock(hashtext(:lock), CAST(:v AS integer))"),
        {"lock": LOCK, "v": version_id},
    )
    run = _run(conn, version_id, season, week, now)
    params: Mapping[str, Any] = run.fitted_params or {}
    rules = _rules(run.spec, params)
    games = _games(conn, run.id)
    game_ids = [g.game_id for g in games]
    newest = _newest_pick(conn, version_id, game_ids)
    if newest is not None and newest > now:
        raise PicksRefused(
            f"a pick for these games was made at {newest}, after the clock ({now}): the current "
            "pick would be one from its future"
        )
    snapshots = _snapshots(conn, game_ids, now)
    current = _current(conn, version_id, game_ids)
    allowed = pickable or teams.pickable

    written = passes = 0
    for g in games:
        cut = cutoff(g.kickoff_at, g.game_date)
        if now >= cut:
            continue  # kicked off: a row now would be hindsight, and the views ignore it
        snap = choose_snapshot(snapshots.get(g.game_id, ()), cut, now)
        if snap is None:
            continue
        if not (snap.captured_at < cut and run.as_of <= cut):
            raise PointInTimeError(
                f"game {g.game_id}: the line at {snap.captured_at} or the run as of {run.as_of} "
                f"isn't before its cutoff {cut}"
            )
        context = GameContext(
            game_id=g.game_id,
            season=g.season,
            season_type=g.season_type,
            week=g.week,
            kickoff=cut,
            home_team=g.home_team_id,
            away_team=g.away_team_id,
            neutral_site=g.neutral_site,
            home_classification=g.home_division,
            away_classification=g.away_division,
        )
        dist = _distribution(params, g.margin_sd, g.prediction_id)
        line = snap.spread_home
        made = pick_game(context, g.pred_margin, line, rules, dist, allowed)
        held = current.get(g.game_id)
        if made is None:
            if held is None:
                continue  # never picked, and still not: no pass row
            k = fixed(rules.market_shrinkage_k, "picks.market_shrinkage_k")
            edge = blended_margin(g.pred_margin, line, k) + line
            side: Side = "home" if edge >= 0 else "away"
            prob = displayed_prob(g.pred_margin, line, side, rules, dist)
            stored: dict[str, Any] = {"side": None, "tier": None, "stake_units": 0.0}
            passes += 1
        elif held == (made.side, made.tier):
            continue  # the pick stands at the line it was made at
        else:
            side, edge, prob = made.side, made.edge, made.prob
            stored = {"side": made.side, "tier": made.tier, "stake_units": 1.0}
            written += 1
        price = snap.price(side)
        _insert(
            conn,
            {
                "prediction_id": g.prediction_id,
                "model_version_id": version_id,
                "game_id": g.game_id,
                "line_snapshot_id": snap.id,
                "market": MARKET,
                "line": line,
                "price": price,
                "model_prob": prob,
                "edge_pts": edge,
                "expected_value": expected_value(prob, price),
                "created_at": now,
                **stored,
            },
        )
    return PickSummary(cast(int, run.id), written, passes)


def version_id(conn: Connection, name: str, version: str) -> int:
    """The live (cfb, spread) version with this name, or refused."""
    found = conn.execute(
        text(
            "SELECT id FROM model_versions WHERE sport_id = :sport AND market = :market"
            " AND name = :name AND version = :version AND deleted_at IS NULL"
        ),
        {"sport": SPORT, "market": MARKET, "name": name, "version": version},
    ).scalar_one_or_none()
    if found is None:
        raise PicksRefused(f"no {SPORT} {MARKET} model version {name} {version}")
    return found


def publish_picks(
    url: str, *, name: str, version: str, season: int, week: int, now: datetime
) -> PickSummary:
    """`write_picks` for the named version in one transaction on `url` (the target's direct URL,
    D-120): a failure partway inserts no pick."""
    with make_engine(url).begin() as conn:
        return write_picks(conn, version_id(conn, name, version), season, week, now)
