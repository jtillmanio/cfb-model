"""`engine rate`: fit a model entering one week and publish the run, its ratings and its
predictions to Postgres (TASK-035, D-136).

The week is the feature week of D-127: its `as_of` is its first kickoff, and the fit is the
backtest's (`harness.fit_games`: every final game that finished, kickoff + 4 h, by `as_of`), so a
published week is the week the backtest scored. Its predictions are the week's staged contexts as
`harness.load` keeps them (`Week.contexts`): every regular-season game of the week with both teams
that isn't canceled or postponed, played or not, its TBA kickoff placed as `features.KICKOFF`
places it. The transform stages a game `canceled` when CFBD still lists it unscored and
uncompleted a week after its start (D-121, TASK-044).

The lake is read and the model fit before any database transaction opens (`fit_week`); `write`
then inserts in one short transaction. Outputs are insert-only (hard rule 2): a re-run adds a new
`model_runs` row and its own ratings and predictions. A fit that raises, or gives a number the
tables can't hold (NaN, ±Infinity, σ ≤ 0, a share outside 0–1), is recorded as a `failed` run
with its error and nothing else; a refusal (an unstaged week, an unpublished team, a version with
another spec) writes nothing. The model's team and game ids are CFBD's; they're mapped to
`teams.id` and `games.id` by `(source, source_id)`. Regular season only: `team_ratings` has no
season type, so postseason week 1 would collide with regular week 1.

A model that rates units (Rung 2, TASK-038) also writes each team's `off_rating` and `def_rating`
in points, summing to `rating`, and `components`, `{input id: {"off": pts, "def": pts}}`;
`st_rating` stays NULL until special teams is rated. A model that rates a team as one number
(Rung 1) leaves all four NULL.
"""

from __future__ import annotations

import json
import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

from pydantic import ValidationError
from sqlalchemy import Connection, text

from db.session import make_engine
from engine import clock
from engine.backtest import MODELS, harness
from engine.core.interfaces import GameContext, Prediction, Ratings
from engine.core.spec import ModelSpec
from engine.ingest.lake import Lake

SPORT = "cfb"
MARKET = "spread"
SOURCE = "cfbd"  # whose ids the lake's teams and games carry
SEASON_TYPE = "regular"


class RateRefused(ValueError):
    """The run can't start, and nothing was written."""


@dataclass(frozen=True, slots=True)
class RunSummary:
    run_id: int
    status: Literal["succeeded", "failed"]
    ratings: int
    predictions: int
    error: str | None = None


Predicted = list[tuple[GameContext, Prediction]]


@dataclass(frozen=True, slots=True)
class FittedWeek:
    """A fit entering one week, ready to insert: its ratings and predictions, or its error."""

    season: int
    week: int
    as_of: datetime
    started: datetime
    finished: datetime
    choices: Mapping[str, float]
    outputs: tuple[Ratings, Predicted] | None
    error: str | None


def settings(spec: ModelSpec, run: Mapping[str, Any] | None, season: int) -> dict[str, float]:
    """The tuned settings `season` runs with: none for a resolved spec, else what the backtest
    run (its `run.json`) chose for that season, so the published week is the one it scored."""
    if spec.is_resolved:
        return {}
    if run is None:
        raise RateRefused(
            f"the spec still tunes {', '.join(spec.tunables())}: pass --choices with the run.json "
            "of a backtest of this spec that scored the season"
        )
    if not isinstance(run, Mapping) or not isinstance(run.get("choices", {}), Mapping):
        raise RateRefused("--choices isn't a backtest run.json (an object with choices by season)")
    if run.get("spec_hash") != harness.spec_hash(spec):
        raise RateRefused("the backtest run in --choices was of a different spec")
    chosen = run.get("choices", {}).get(str(season))
    if chosen is None:
        raise RateRefused(
            f"the backtest run in --choices didn't score {season}: run engine backtest "
            f"--seasons {season} with this spec first"
        )
    if not isinstance(chosen, Mapping):
        raise RateRefused(f"--choices isn't a backtest run.json: choices[{season}] isn't an object")
    try:
        return {path: float(value) for path, value in chosen.items()}
    except (TypeError, ValueError) as e:
        raise RateRefused(f"a setting in --choices for {season} isn't a number: {e}") from e


def _week(history: harness.History, season: int, week: int) -> harness.Week:
    """The harness's week: its `as_of` and its staged games that will be played (`contexts`)."""
    found = next(
        (
            w
            for w in history.weeks
            if (w.season, w.season_type, w.week) == (season, SEASON_TYPE, week)
        ),
        None,
    )
    if found is None:
        raise RateRefused(f"no staged games in {season} {SEASON_TYPE} week {week}")
    return found


def _fit(
    model: harness.BacktestModel,
    history: harness.History,
    week: harness.Week,
    games: list[GameContext],
) -> tuple[Ratings, Predicted] | str:
    """The ratings entering `week` and its games' predictions, fit as the backtest fits them;
    or, if the fit raises or gives a number the tables can't hold, the error to record. A
    point-in-time violation isn't a failed fit: it raises (hard rule 4), and nothing is written."""
    fit_on = harness.fit_games(history, week.as_of)
    harness._check_fit(fit_on, week)
    try:
        ratings = model.fit(fit_on, week.as_of)
        predicted = [(g, model.predict(g, ratings, week.as_of)) for g in games]
    except Exception as e:  # a failed fit is recorded as a failed run, not raised
        return f"{type(e).__name__}: {e}"
    return _unstorable(ratings, predicted) or (ratings, predicted)


def _unstorable(ratings: Ratings, predictions: Predicted) -> str | None:
    """The first number the run would store that its table refuses (NaN, ±Infinity, or outside
    0003's CHECKs: σ > 0, shares 0–1), named; None if there's none."""
    for name, value in ratings.params.items():
        if not math.isfinite(value):
            return f"fitted param {name} is {value}"
    if not 0 <= ratings.params.get("prior_weight", 0) <= 1:
        return f"prior_weight {ratings.params['prior_weight']} isn't between 0 and 1"
    for team, value in ratings.teams.items():
        if not math.isfinite(value):
            return f"rating of team {team} is {value}"
    for team, units in ratings.units.items():
        for stat, (off, dfn) in units.items():
            if not (math.isfinite(off) and math.isfinite(dfn)):
                return f"{stat} unit of team {team} is ({off}, {dfn})"
    for game, p in predictions:
        for name in ("pred_margin", "margin_sd", "home_win_prob"):
            value = getattr(p, name)
            if not math.isfinite(value):
                return f"{name} of game {game.game_id} is {value}"
        if p.margin_sd <= 0:
            return f"margin_sd of game {game.game_id} is {p.margin_sd}, not above 0"
        if not 0 <= p.home_win_prob <= 1:
            return f"home_win_prob of game {game.game_id} is {p.home_win_prob}, not 0-1"
        for label, points in p.drivers:
            if not math.isfinite(points):
                return f"driver {label!r} of game {game.game_id} is {points}"
    return None


def fit_week(
    lake: Lake, spec: ModelSpec, choices: Mapping[str, float], *, season: int, week: int
) -> FittedWeek:
    """Read the lake and fit `spec` (resolved with `choices`) entering `week`; no database is
    opened. A fit that fails is returned with its error, to be recorded; a refusal raises."""
    try:
        resolved = spec.resolve(choices)
    except ValueError as e:
        raise RateRefused(str(e)) from e
    if not resolved.is_resolved:
        raise RateRefused(f"no setting chosen for {', '.join(resolved.tunables())}")
    factory = MODELS.get(spec.base)
    if factory is None:
        raise RateRefused(f"no model is registered as {spec.base!r}")
    history = harness.load(lake)
    found = _week(history, season, week)
    model = factory(resolved)
    harness.check_reads(model)
    harness.give_inputs(model, history)

    started = clock.now()
    fitted = _fit(model, history, found, list(found.contexts))
    finished = clock.now()
    return FittedWeek(
        season,
        week,
        found.as_of,
        started,
        finished,
        dict(choices),
        None if isinstance(fitted, str) else fitted,
        fitted if isinstance(fitted, str) else None,
    )


def _ids(conn: Connection, table: str, source: str, wanted: Iterable[int]) -> dict[int, int]:
    """CFBD id -> serving id, refusing any the database doesn't hold."""
    keys = sorted({str(w) for w in wanted})
    found = {
        int(source_id): row_id
        for source_id, row_id in conn.execute(
            text(
                f"SELECT source_id, id FROM {table}"
                " WHERE sport_id = :sport AND source = :source AND source_id = ANY(:keys)"
            ),
            {"sport": SPORT, "source": source, "keys": keys},
        ).all()
    }
    missing = [k for k in keys if int(k) not in found]
    if missing:
        raise RateRefused(
            f"{len(missing)} {table} aren't published under source {source!r} "
            f"({', '.join(missing[:5])}): run engine publish first"
        )
    return found


def _version(conn: Connection, spec: ModelSpec, name: str, version: str) -> int | None:
    """The live version with this name, or None; refused if its spec isn't this one."""
    row = conn.execute(
        text(
            "SELECT id, spec FROM model_versions WHERE sport_id = :sport AND market = :market"
            " AND name = :name AND version = :version AND deleted_at IS NULL"
        ),
        {"sport": SPORT, "market": MARKET, "name": name, "version": version},
    ).one_or_none()
    if row is None:
        return None
    try:
        stored = ModelSpec.model_validate(row.spec)
    except ValidationError as e:
        raise RateRefused(f"{name} {version}'s stored spec isn't a valid ModelSpec: {e}") from e
    if harness.spec_hash(stored) != harness.spec_hash(spec):
        raise RateRefused(f"{name} {version} already exists with a different spec")
    return row.id


def _create_version(conn: Connection, spec: ModelSpec, name: str, version: str) -> int:
    return conn.execute(
        text(
            "INSERT INTO model_versions (sport_id, market, name, version, spec,"
            " spec_schema_version, created_by, status)"
            " VALUES (:sport, :market, :name, :version, CAST(:spec AS jsonb), :schema, 'system',"
            " 'dev') RETURNING id"
        ),
        {
            "sport": SPORT,
            "market": MARKET,
            "name": name,
            "version": version,
            "spec": json.dumps(spec.model_dump(mode="json")),
            "schema": spec.spec_schema_version,
        },
    ).scalar_one()


def _insert_run(
    conn: Connection,
    version_id: int,
    fitted: FittedWeek,
    params: Mapping[str, Any] | None = None,
) -> int:
    """An ad-hoc run of one week: `succeeded` with its fitted params, or `failed` with its
    error. Inserted finished, so it never sits `running` (a failed fit writes nothing else)."""
    return conn.execute(
        text(
            "INSERT INTO model_runs (model_version_id, run_type, season, week, as_of, status,"
            " requested_at, started_at, finished_at, fitted_params, error)"
            " VALUES (:v, 'adhoc', :season, :week, :as_of, :status, :started, :started,"
            " :finished, CAST(:params AS jsonb), :error) RETURNING id"
        ),
        {
            "v": version_id,
            "season": fitted.season,
            "week": fitted.week,
            "as_of": fitted.as_of,
            "status": "failed" if fitted.error is not None else "succeeded",
            "started": fitted.started,
            "finished": fitted.finished,
            "params": None if params is None else json.dumps(params),
            "error": fitted.error,
        },
    ).scalar_one()


def _units(units: Mapping[str, tuple[float, float]] | None) -> dict[str, Any]:
    """A team's `off_rating`, `def_rating` and `components`, or NULLs if it has no units."""
    if not units:
        return {"off": None, "def": None, "components": None}
    return {
        "off": math.fsum(off for off, _ in units.values()),
        "def": math.fsum(dfn for _, dfn in units.values()),
        "components": json.dumps(
            {s: {"off": off, "def": dfn} for s, (off, dfn) in units.items()}, allow_nan=False
        ),
    }


def write(
    conn: Connection,
    fitted: FittedWeek,
    spec: ModelSpec,
    *,
    name: str,
    version: str,
    source: str | None = None,
) -> RunSummary:
    """Insert the run with its ratings and predictions, in the caller's transaction. `spec` is
    the version's recipe as stored; a refusal raises before anything is inserted."""
    version_id = _version(conn, spec, name, version)
    if fitted.outputs is None:
        version_id = version_id or _create_version(conn, spec, name, version)
        run_id = _insert_run(conn, version_id, fitted)
        return RunSummary(run_id, "failed", 0, 0, fitted.error)

    ratings, predicted = fitted.outputs
    team_ids = _ids(conn, "teams", source or SOURCE, ratings.teams)
    game_ids = _ids(conn, "games", source or SOURCE, (g.game_id for g, _ in predicted))
    version_id = version_id or _create_version(conn, spec, name, version)
    run_id = _insert_run(conn, version_id, fitted, {**ratings.params, "choices": fitted.choices})
    rating_rows = [
        {
            "run": run_id,
            "v": version_id,
            "team": team_ids[team],
            "season": fitted.season,
            "week": fitted.week,
            "as_of": fitted.as_of,
            "rating": rating,
            "prior_weight": ratings.params.get("prior_weight"),
            **_units(ratings.units.get(team)),
        }
        for team, rating in ratings.teams.items()
    ]
    prediction_rows = [
        {
            "run": run_id,
            "v": version_id,
            "game": game_ids[g.game_id],
            "margin": p.pred_margin,
            "prob": p.home_win_prob,
            "sd": p.margin_sd,
            "drivers": json.dumps([{"label": label, "points": pts} for label, pts in p.drivers]),
        }
        for g, p in predicted
    ]
    if rating_rows:
        conn.execute(
            text(
                "INSERT INTO team_ratings (model_run_id, model_version_id, team_id, season, week,"
                " as_of, rating, off_rating, def_rating, prior_weight, components)"
                " VALUES (:run, :v, :team, :season, :week, :as_of, :rating, :off, :def,"
                " :prior_weight, CAST(:components AS jsonb))"
            ),
            rating_rows,
        )
    if prediction_rows:
        conn.execute(
            text(
                "INSERT INTO predictions (model_run_id, model_version_id, game_id, pred_margin,"
                " home_win_prob, margin_sd, drivers)"
                " VALUES (:run, :v, :game, :margin, :prob, :sd, CAST(:drivers AS jsonb))"
            ),
            prediction_rows,
        )
    return RunSummary(run_id, "succeeded", len(rating_rows), len(prediction_rows))


def rate(
    lake: Lake,
    conn: Connection,
    spec: ModelSpec,
    choices: Mapping[str, float],
    *,
    season: int,
    week: int,
    name: str,
    version: str,
    source: str | None = None,
) -> RunSummary:
    """`fit_week`, then `write` on `conn`."""
    fitted = fit_week(lake, spec, choices, season=season, week=week)
    return write(conn, fitted, spec, name=name, version=version, source=source)


def publish(
    lake: Lake,
    url: str,
    spec: ModelSpec,
    choices: Mapping[str, float],
    *,
    season: int,
    week: int,
    name: str,
    version: str,
) -> RunSummary:
    """Fit with no connection open, then write in one transaction on `url` (the target's direct
    URL, D-120), so the transaction lasts only as long as the inserts."""
    fitted = fit_week(lake, spec, choices, season=season, week=week)
    with make_engine(url).begin() as conn:
        return write(conn, fitted, spec, name=name, version=version)
