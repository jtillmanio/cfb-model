"""The walk-forward, rolling-origin backtest (TASK-030; docs/04-model.md § 5, § 9.1-9.3; D-076).

A run replays seasons week by week in (season, `as_of`, season type, week) order, a week being a
feature-table week with its `as_of` (D-127). Entering each week the model is fit on every final
game, this season's and earlier ones', that finished (kickoff + `GAME_HOURS`) by `as_of`, and the
harness asserts it did; then it predicts each of the week's eligible games once: FBS vs FBS,
final, with a closing line (04 § 9.3, D-121's `closing_lines()`).

**Settings.** Scored season Y's tuned settings are chosen by a `Tuner` from seasons `tune_from`
to Y-1, never a holdout season (04 § 9.1); the default grid-searches `spec.tunables()` on pooled
margin MAE (§ 9.2). Each (choices, season) walk-forward runs once, shared by the tuning of later
seasons and the scoring.

**Postseason.** CFBD files every bowl and CFP round under postseason week 1, so it's one week
with one `as_of`, the first bowl's kickoff: a later CFP round is predicted from the ratings
entering the bowls. That's leak-free and slightly stale (D-127's revisit).

**Inputs.** A model declares what it reads (`reads`). Only `FIT_INPUTS` are given; hindsight
ratings and market lines are refused by name (D-056, 04 § 9.2). Learned weights are the model's
own: it's fit with `fit(games, as_of)` each week, and refits what it learns once a season itself.
"""

from __future__ import annotations

import hashlib
import io
import itertools
import json
import math
from bisect import bisect_right
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Literal, Protocol, cast

from engine.backtest.holdout import HOLDOUT_SEASONS
from engine.core.interfaces import GameContext, GamePredictor, GameResult, RatingModel
from engine.core.spec import ModelSpec
from engine.ingest.lake import Lake
from engine.transform.features import GAME_HOURS, KICKOFF, PointInTimeError, check_point_in_time

TUNE_FROM = 2015  # 2014 is warm-up only (04 § 9.1)

FIT_INPUTS = frozenset({"games"})
_LINES = "market lines are targets and pick-time inputs, never fitting inputs (04 § 9.2)"
REFUSED_INPUTS = {
    "hindsight_ratings": "hindsight ratings are computed from the whole season (D-056)",
    "lines": _LINES,
    "line_snapshots": _LINES,
    "closing_lines": _LINES,
}

_FINISHED = timedelta(hours=GAME_HOURS)
# How long after kickoff a game is selected for a fit. The leak test loosens it to prove
# `_check_fit` catches a game that hadn't finished.
SELECT_LAG = _FINISHED


class BacktestModel(RatingModel, GamePredictor, Protocol):
    reads: frozenset[str]  # the data it's fit on: names in FIT_INPUTS


ModelFactory = Callable[[ModelSpec], BacktestModel]  # built from a resolved spec
Choices = Mapping[str, float]  # tuned setting path -> its chosen candidate
Row = dict[str, Any]  # one results row, keyed as in SCHEMA
Evaluate = Callable[[Choices, int], Sequence[Row]]  # a season's walk-forward under choices


class Tuner(Protocol):
    def __call__(self, spec: ModelSpec, tuning: Sequence[int], evaluate: Evaluate) -> Choices:
        """One candidate for each of `spec.tunables()`, chosen on the `tuning` seasons."""
        ...


class RefusedError(ValueError):
    """The run can't start: a season it can't score or tune, or a model input it may not read."""


@dataclass(frozen=True, slots=True)
class Eligible:
    """A game the backtest predicts and scores."""

    context: GameContext
    source_id: str
    kickoff_at: datetime | None
    home_source_id: str
    away_source_id: str
    home_points: int
    away_points: int
    spread_home: float
    spread_source: str
    closing_from: str


@dataclass(frozen=True, slots=True)
class Week:
    season: int
    season_type: str
    week: int
    as_of: datetime
    games: tuple[Eligible, ...]

    @property
    def label(self) -> str:
        return f"{self.season} {self.season_type} week {self.week}"


@dataclass(frozen=True, slots=True)
class History:
    results: tuple[GameResult, ...]  # every final game with both teams, by kickoff
    kickoffs: tuple[datetime, ...]  # `results`' kickoffs, for bisecting
    weeks: tuple[Week, ...]  # in run order

    def season_weeks(self, season: int) -> list[Week]:
        return [w for w in self.weeks if w.season == season]

    def scored_seasons(self) -> set[int]:
        return {w.season for w in self.weeks if w.games}


def _read(lake: Lake, key: str) -> Any:
    import pyarrow.parquet as pq

    folder = key.rpartition("/")[0]
    if key not in lake.list(folder):
        raise RefusedError(f"{key} isn't in the lake: run engine transform --rebuild first")
    return pq.read_table(io.BytesIO(lake.read(key)))


def load(lake: Lake) -> History:
    """Staged games and lines and the feature tables, checked against the point-in-time rule."""
    from engine.transform import FEATURE_TABLES, feature_key, staging_key
    from engine.transform.market import closing_lines
    from engine.transform.staging import connect

    tables = {name: _read(lake, staging_key(name)) for name in ("games", "lines")}
    tables |= {name: _read(lake, feature_key(name)) for name in FEATURE_TABLES}
    con = connect()
    for name, table in tables.items():
        con.register(name, table)
    check_point_in_time(con)
    closing = {
        r["game_source_id"]: r for r in closing_lines(tables["games"], tables["lines"]).to_pylist()
    }
    games = (
        con.execute(f"""
            SELECT g.*, f.as_of FROM (SELECT *, {KICKOFF} AS kickoff FROM games) g
            JOIN game_features f ON f.game_source_id = g.source_id
            ORDER BY g.kickoff, g.source_id""")
        .arrow()
        .read_all()
        .to_pylist()
    )

    results: list[GameResult] = []
    by_week: dict[tuple[int, str, int], tuple[datetime, list[Eligible]]] = {}
    for g in games:
        teams = g["home_source_id"] is not None and g["away_source_id"] is not None
        final = g["status"] == "final" and None not in (g["home_points"], g["away_points"])
        context = None
        if teams:
            context = GameContext(
                game_id=int(g["source_id"]),
                season=g["season"],
                season_type=cast(Literal["regular", "postseason"], g["season_type"]),
                week=g["week"],
                kickoff=g["kickoff"],
                home_team=int(g["home_source_id"]),
                away_team=int(g["away_source_id"]),
                neutral_site=bool(g["neutral_site"]),
            )
        if context is not None and final:
            results.append(
                GameResult(
                    **_fields(context), home_points=g["home_points"], away_points=g["away_points"]
                )
            )
        _, week_games = by_week.setdefault(
            (g["season"], g["season_type"], g["week"]), (g["as_of"], [])
        )
        line = closing.get(g["source_id"])
        fbs = g["home_classification"] == g["away_classification"] == "fbs"
        if context is None or not final or not fbs or line is None:
            continue
        if line["spread_home"] is None:
            continue
        week_games.append(
            Eligible(
                context=context,
                source_id=g["source_id"],
                kickoff_at=g["kickoff_at"],
                home_source_id=g["home_source_id"],
                away_source_id=g["away_source_id"],
                home_points=g["home_points"],
                away_points=g["away_points"],
                spread_home=line["spread_home"],
                spread_source=line["source"],
                closing_from=line["closing_from"],
            )
        )

    weeks = [
        Week(season, season_type, week, as_of, tuple(sorted(eligible, key=lambda e: e.source_id)))
        for (season, season_type, week), (as_of, eligible) in by_week.items()
    ]
    weeks.sort(key=lambda w: (w.season, w.as_of, w.season_type, w.week))
    return History(tuple(results), tuple(r.kickoff for r in results), tuple(weeks))


def _fields(context: GameContext) -> dict[str, Any]:
    return {name: getattr(context, name) for name in GameContext.__slots__}


def fit_games(history: History, as_of: datetime) -> tuple[GameResult, ...]:
    """The final games that finished by `as_of`: what a fit entering that week may see."""
    return history.results[: bisect_right(history.kickoffs, as_of - SELECT_LAG)]


def _check_fit(games: Sequence[GameResult], week: Week) -> None:
    late = [g for g in games if g.kickoff + _FINISHED > week.as_of]
    if late:
        shown = ", ".join(str(g.game_id) for g in late[:5])
        raise PointInTimeError(
            f"{week.label}: the fit was given {len(late)} game(s) that hadn't finished by its "
            f"as_of {week.as_of.isoformat()} (point-in-time rule, 04 § 9.2): {shown}"
        )


def check_reads(model: BacktestModel) -> None:
    """Refuse a model that reads anything but `FIT_INPUTS`, naming the input."""
    for name in sorted(model.reads):
        if name in REFUSED_INPUTS:
            raise RefusedError(
                f"the model asks for {name!r} as a fitting input: {REFUSED_INPUTS[name]}"
            )
        if name not in FIT_INPUTS:
            known = ", ".join(sorted(FIT_INPUTS))
            raise RefusedError(
                f"the model asks for {name!r}, which isn't a backtest input (known: {known})"
            )


def predict_season(model: BacktestModel, history: History, season: int) -> list[Row]:
    """Walk one season forward: fit entering each week, then predict its eligible games."""
    check_reads(model)
    rows: list[Row] = []
    for week in history.season_weeks(season):
        if not week.games:
            continue
        games = fit_games(history, week.as_of)
        _check_fit(games, week)
        ratings = model.fit(games, week.as_of)
        for e in week.games:
            p = model.predict(e.context, ratings, week.as_of)
            rows.append(
                {
                    "season": week.season,
                    "season_type": week.season_type,
                    "week": week.week,
                    "as_of": week.as_of,
                    "game_source_id": e.source_id,
                    "kickoff_at": e.kickoff_at,
                    "home_source_id": e.home_source_id,
                    "away_source_id": e.away_source_id,
                    "neutral_site": e.context.neutral_site,
                    "pred_margin": p.pred_margin,
                    "margin_sd": p.margin_sd,
                    "home_win_prob": p.home_win_prob,
                    "spread_home": e.spread_home,
                    "spread_source": e.spread_source,
                    "closing_from": e.closing_from,
                    "home_points": e.home_points,
                    "away_points": e.away_points,
                    "margin": e.home_points - e.away_points,
                }
            )
    return rows


def grid_tuner(spec: ModelSpec, tuning: Sequence[int], evaluate: Evaluate) -> Choices:
    """Every combination of the candidates, scored by margin MAE pooled over the tuning
    seasons' eligible games; a tie goes to the first in grid order."""
    tunables = spec.tunables()
    if not tunables:
        return {}
    best: tuple[float, dict[str, float]] | None = None
    for values in itertools.product(*tunables.values()):
        choices = dict(zip(tunables, values, strict=True))
        errors = [abs(r["pred_margin"] - r["margin"]) for s in tuning for r in evaluate(choices, s)]
        mae = math.fsum(errors) / len(errors)
        if best is None or mae < best[0]:
            best = (mae, choices)
    assert best is not None
    return best[1]


def tuning_seasons(season: int, tune_from: int) -> tuple[int, ...]:
    return tuple(y for y in range(tune_from, season) if y not in HOLDOUT_SEASONS)


def prepare(
    spec: ModelSpec,
    factory: ModelFactory,
    history: History,
    seasons: Sequence[int],
    tune_from: int = TUNE_FROM,
) -> dict[int, tuple[int, ...]]:
    """Each scored season's tuning seasons, refusing a run that can't be scored honestly."""
    if not seasons:
        raise RefusedError("no season to score")
    present = history.scored_seasons()
    tuned = spec.tunables()
    plan: dict[int, tuple[int, ...]] = {}
    for season in sorted(seasons):
        if season not in present:
            raise RefusedError(
                f"season {season} has no eligible games in the lake "
                "(FBS vs FBS, final, with a closing line)"
            )
        tuning = tuning_seasons(season, tune_from)
        if tuned and not tuning:
            raise RefusedError(
                f"season {season} has no tuning season before it: its tuned settings "
                f"({', '.join(tuned)}) are chosen on {tune_from} to {season - 1} (04 § 9.1)"
            )
        missing = [y for y in tuning if y not in present] if tuned else []
        if missing:
            raise RefusedError(
                f"tuning season {missing[0]} (for {season}) has no eligible games in the lake"
            )
        plan[season] = tuning
    first = spec.resolve({path: candidates[0] for path, candidates in tuned.items()})
    check_reads(factory(first))
    return plan


@dataclass(frozen=True, slots=True)
class BacktestRun:
    rows: tuple[Row, ...]  # every scored season's predictions, in run order
    choices: Mapping[int, Choices]  # scored season -> the settings it ran with
    tuned_on: Mapping[int, tuple[int, ...]]  # scored season -> the seasons they were chosen on


def run(
    spec: ModelSpec,
    factory: ModelFactory,
    history: History,
    seasons: Sequence[int],
    tune_from: int = TUNE_FROM,
    tuner: Tuner = grid_tuner,
) -> BacktestRun:
    plan = prepare(spec, factory, history, seasons, tune_from)
    cache: dict[tuple[tuple[tuple[str, float], ...], int], list[Row]] = {}

    def evaluate(choices: Choices, season: int) -> list[Row]:
        key = (tuple(sorted(choices.items())), season)
        if key not in cache:
            cache[key] = predict_season(factory(spec.resolve(choices)), history, season)
        return cache[key]

    rows: list[Row] = []
    chosen: dict[int, Choices] = {}
    for season, tuning in plan.items():
        choices = dict(tuner(spec, tuning, evaluate))
        if not spec.resolve(choices).is_resolved:
            raise RefusedError(
                f"the tuner left {', '.join(spec.resolve(choices).tunables())} "
                f"unresolved for {season}"
            )
        chosen[season] = choices
        rows += evaluate(choices, season)
    return BacktestRun(tuple(rows), chosen, plan)


def spec_hash(spec: ModelSpec) -> str:
    """sha256 of the spec's canonical JSON: the same spec always hashes the same."""
    text = json.dumps(spec.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def schema() -> Any:
    import pyarrow as pa

    stamp = pa.timestamp("us", tz="UTC")
    return pa.schema(
        [
            ("season", pa.int32()),
            ("season_type", pa.string()),
            ("week", pa.int32()),
            ("as_of", stamp),
            ("game_source_id", pa.string()),
            ("kickoff_at", stamp),  # NULL for a TBA kickoff
            ("home_source_id", pa.string()),
            ("away_source_id", pa.string()),
            ("neutral_site", pa.bool_()),
            ("pred_margin", pa.float64()),
            ("margin_sd", pa.float64()),
            ("home_win_prob", pa.float64()),
            ("spread_home", pa.float64()),  # the closing line
            ("spread_source", pa.string()),  # consensus or median (04 § 9.3)
            ("closing_from", pa.string()),  # cfbd_close or last_snapshot (D-120)
            ("home_points", pa.int32()),
            ("away_points", pa.int32()),
            ("margin", pa.int32()),
        ]
    )


def write(
    lake: Lake,
    result: BacktestRun,
    *,
    spec: ModelSpec,
    model: str,
    tune_from: int,
    holdout: bool,
    at: datetime,
) -> str:
    """Write `predictions.parquet` and `run.json` under a new `backtests/<run>/` folder and
    return it. The results carry nothing about when they ran, so a re-run is byte-identical."""
    import pyarrow as pa
    import pyarrow.parquet as pq

    digest = spec_hash(spec)
    base = folder = f"backtests/{at.astimezone(UTC):%Y%m%dT%H%M%S%fZ}-{digest[:12]}"
    n = 1
    while lake.list(folder):
        n += 1
        folder = f"{base}-{n}"
    buffer = io.BytesIO()
    pq.write_table(pa.Table.from_pylist(list(result.rows), schema()), buffer)
    lake.write_new(f"{folder}/predictions.parquet", buffer.getvalue())
    meta = {
        "created_at": at.astimezone(UTC).isoformat(),
        "spec_hash": digest,
        "spec": spec.model_dump(mode="json"),
        "model": model,
        "seasons": list(result.choices),
        "tune_from": tune_from,
        "holdout": holdout,
        "choices": {str(s): dict(c) for s, c in result.choices.items()},
        "tuned_on": {str(s): list(t) for s, t in result.tuned_on.items()},
        "games": len(result.rows),
    }
    lake.write_new(f"{folder}/run.json", json.dumps(meta, indent=2).encode("utf-8"))
    return folder
