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
ratings and market lines are refused by name (D-056, 04 § 9.2). `games` arrive through
`fit(games, as_of)`; any other fit input it declared arrives once through `use(inputs)` and hands
out only what finished by an `as_of`, asserting it (`TeamGameStats.finished_by`). A Rung 0
baseline (`baseline = True`, D-133) may also read `BASELINE_INPUTS`, the closing lines and the
staged benchmark ratings: it's a bar to beat, never a fitted model, and it gets them through
`use(inputs)` too, only those it declared. Learned weights are the model's own: it's fit with
`fit(games, as_of)` each week, and refits what it learns once a season itself.

**Preseason.** A prior that reads more than last season's rating gets the `preseason` input:
each preseason source's staged values (CFB's are `engine.sports.cfb.preseason`), handed out only
by `Preseason.for_season`, which asserts every value it gives season Y was assumed published
before Y's first `as_of` (04 § 9.2, TASK-037).

**Groups.** Each game carries each team's conference that season from staged `team_seasons`
(`home_group`, `away_group`), for a model that shrinks toward a team's tier and for the report's
conference-tier breakdown (TASK-036). A season's conferences are set before it starts.
"""

from __future__ import annotations

import hashlib
import io
import itertools
import json
import math
from bisect import bisect_right
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, Literal, Protocol, cast

from engine.backtest.holdout import HOLDOUT_SEASONS
from engine.core.inputs import INPUTS
from engine.core.interfaces import GameContext, GamePredictor, GameResult, RatingModel
from engine.core.spec import ModelSpec
from engine.ingest.lake import Lake
from engine.transform.features import GAME_HOURS, KICKOFF, PointInTimeError, check_point_in_time

TUNE_FROM = 2015  # 2014 is warm-up only (04 § 9.1)

# The earliest a staged game could have kicked off: a TBA game's date starts at Eastern midnight
# (the start of its week's `as_of`, D-127), where `KICKOFF` puts it at the end of its date. The
# same expression as `earliest` in the features SQL (`transform/features.py`): keep them equal.
EARLIEST = "coalesce(kickoff_at, timezone('America/New_York', CAST(game_date AS TIMESTAMP)))"

# `team_game_stats`: each team-game's offense in staged `team_game_advanced` (TASK-036);
# `preseason`: talent, returning production and recruiting (TASK-037).
FIT_INPUTS = frozenset({"games", "team_game_stats", "preseason"})
# What only a baseline may read (D-133): the closing spread of every staged game with a line, by
# game id, and the staged benchmark ratings. Each baseline filters them to what it may know.
BASELINE_INPUTS = frozenset({"closing_lines", "benchmark_ratings"})
_LINES = "market lines are targets and pick-time inputs, never fitting inputs (04 § 9.2)"
REFUSED_INPUTS = {
    "hindsight_ratings": "hindsight ratings are computed from the whole season (D-056)",
    "lines": _LINES,
    "line_snapshots": _LINES,
    "closing_lines": _LINES,
    "benchmark_ratings": "published ratings are a benchmark to beat, not a fit input (04 § 9.2)",
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
    spread_home_open: float | None
    spread_home_open_close: float | None
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
class Benchmark:
    """A staged SP+/FPI/Elo rating: `known_at` is when it was published if that was before the
    season ended, otherwise None (season-final, or a season with no staged calendar: hindsight
    for a game of that season either way)."""

    system: str
    season: int
    team: int
    rating: float
    fetched_at: datetime
    known_at: datetime | None


@dataclass(frozen=True, slots=True)
class BenchmarkInput:
    """What a benchmark baseline is given: the staged ratings, and each game's earliest possible
    kickoff, so a rating published on a TBA game's date never counts as known before it."""

    rows: tuple[Benchmark, ...]
    earliest: Mapping[int, datetime]  # game id -> kickoff, or the start of a TBA game's date


@dataclass(frozen=True, slots=True)
class TeamGameStat:
    """One team's offense in one final game, garbage time excluded: the observation a defense
    is rated on too (its opponent's offense)."""

    game_id: int
    season: int
    kickoff: datetime  # as `GameResult.kickoff` takes it
    team: int  # the offense
    opponent: int  # the defense
    site: int  # +1 the offense is at home, -1 away, 0 neutral
    values: Mapping[str, float | None]  # registry `feature` stem -> the offense's value


@dataclass(frozen=True, slots=True)
class TeamGameStats:
    """The `team_game_stats` fit input: a model sees rows only through `finished_by`."""

    by_season: Mapping[int, tuple[TeamGameStat, ...]] = field(default_factory=dict)  # by kickoff

    def finished_by(self, as_of: datetime, season: int) -> tuple[TeamGameStat, ...]:
        """`season`'s rows whose game finished (kickoff + `GAME_HOURS`) by `as_of`, asserting
        each did (point-in-time rule, 04 § 9.2)."""
        rows = self.by_season.get(season, ())
        rows = rows[: bisect_right([r.kickoff for r in rows], as_of - SELECT_LAG)]
        late = [r for r in rows if r.kickoff + _FINISHED > as_of]
        if late:
            shown = ", ".join(f"{r.game_id} ({r.team})" for r in late[:5])
            raise PointInTimeError(
                f"the fit entering {as_of.isoformat()} was given {len(late)} advanced-stat "
                f"row(s) of games that hadn't finished (point-in-time rule, 04 § 9.2): {shown}"
            )
        return rows


class PreseasonSource(Protocol):
    """How a season's prior reads one source (`engine.sports.cfb.preseason.Source`)."""

    @property
    def seasons(self) -> Callable[[int], tuple[int, ...]]: ...
    @property
    def combine(self) -> Callable[[Sequence[float]], float]: ...


@dataclass(frozen=True, slots=True)
class PreseasonTable:
    """One source's staged values: each value season's numbers by team, and when that season's
    values are assumed published."""

    by_season: Mapping[int, Mapping[int, float]]  # value season -> team id -> value
    known_at: Mapping[int, datetime]  # value season -> its assumed publication


@dataclass(frozen=True, slots=True)
class Preseason:
    """The `preseason` fit input: a model sees values only through `for_season`."""

    sources: Mapping[str, PreseasonSource] = field(default_factory=dict)
    tables: Mapping[str, PreseasonTable] = field(default_factory=dict)
    first_as_of: Mapping[int, datetime] = field(default_factory=dict)  # season -> first `as_of`

    def for_season(self, season: int) -> dict[str, dict[int, float]]:
        """Each source's number per team for `season`'s prior, asserting every value read was
        published before the season's first `as_of` (point-in-time rule, 04 § 9.2). A team
        with no value is absent."""
        start = self.first_as_of.get(season)
        if start is None:
            raise PointInTimeError(f"season {season} has no week to place its preseason values")
        out: dict[str, dict[int, float]] = {}
        for name, source in self.sources.items():
            table = self.tables.get(name, PreseasonTable({}, {}))
            read = [s for s in source.seasons(season) if s in table.by_season]
            late = [s for s in read if table.known_at[s] > start]
            if late:
                raise PointInTimeError(
                    f"{name} of season {late[0]} is assumed published "
                    f"{table.known_at[late[0]].isoformat()}, after {season}'s first as_of "
                    f"{start.isoformat()}: a prior may read only what was known before its "
                    "season (04 § 9.2)"
                )
            values: dict[int, list[float]] = {}
            for s in read:
                for team, value in table.by_season[s].items():
                    values.setdefault(team, []).append(value)
            out[name] = {team: source.combine(vs) for team, vs in sorted(values.items())}
        return out


@dataclass(frozen=True, slots=True)
class History:
    results: tuple[GameResult, ...]  # every final game with both teams, by kickoff
    kickoffs: tuple[datetime, ...]  # `results`' kickoffs, for bisecting
    weeks: tuple[Week, ...]  # in run order
    closing_spreads: Mapping[int, float] = field(default_factory=dict)  # game id -> spread_home
    benchmarks: tuple[Benchmark, ...] = ()
    earliest: Mapping[int, datetime] = field(default_factory=dict)  # game id -> earliest kickoff
    stats: TeamGameStats = field(default_factory=TeamGameStats)
    # (season, team id) -> its conference that season, from staged `team_seasons`: what each
    # game's `home_group`/`away_group` hold, for any code that builds a `GameContext` itself.
    groups: Mapping[tuple[int, int], str] = field(default_factory=dict)
    preseason: Preseason = field(default_factory=Preseason)

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
    from engine.sports.cfb.preseason import SOURCES
    from engine.transform import FEATURE_TABLES, feature_key, staging_key
    from engine.transform.market import closing_lines
    from engine.transform.staging import connect

    staged = ("games", "lines", "team_seasons", "team_game_advanced")
    staged += tuple(s.table for s in SOURCES.values())
    tables = {name: _read(lake, staging_key(name)) for name in staged}
    tables |= {name: _read(lake, feature_key(name)) for name in FEATURE_TABLES}
    con = connect()
    for name, table in tables.items():
        con.register(name, table)
    check_point_in_time(con)
    games = (
        con.execute(f"""
            SELECT g.*, f.as_of, f.game_source_id IS NOT NULL AS featured,
                hs.conference AS home_group, aws.conference AS away_group
            FROM (SELECT *, {KICKOFF} AS kickoff, {EARLIEST} AS earliest FROM games) g
            LEFT JOIN game_features f ON f.game_source_id = g.source_id
            LEFT JOIN team_seasons hs
              ON hs.team_source_id = g.home_source_id AND hs.season = g.season
            LEFT JOIN team_seasons aws
              ON aws.team_source_id = g.away_source_id AND aws.season = g.season
            ORDER BY g.kickoff, g.source_id""")
        .arrow()
        .read_all()
        .to_pylist()
    )
    # game_features has a row per staged game, so a missing one means features/ is older than
    # staging/ (a rebuild that stopped between them): refuse rather than drop the game.
    stale = [g["source_id"] for g in games if not g["featured"]]
    if stale:
        raise RefusedError(
            f"{len(stale)} staged games have no game_features row ({', '.join(stale[:5])}): "
            "features/ is older than staging/; run engine transform --rebuild"
        )
    undated = [g["source_id"] for g in games if g["kickoff"] is None]
    if undated:
        raise RefusedError(
            f"{len(undated)} staged games have no kickoff time or date ({', '.join(undated[:5])}),"
            " so the point-in-time rule can't place them"
        )
    closing = {
        r["game_source_id"]: r for r in closing_lines(tables["games"], tables["lines"]).to_pylist()
    }

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
                home_classification=g["home_classification"],
                away_classification=g["away_classification"],
                home_group=g["home_group"],
                away_group=g["away_group"],
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
                spread_home_open=line["spread_home_open"],
                spread_home_open_close=line["spread_home_open_close"],
                spread_source=line["source"],
                closing_from=line["closing_from"],
            )
        )

    weeks = [
        Week(season, season_type, week, as_of, tuple(sorted(eligible, key=lambda e: e.source_id)))
        for (season, season_type, week), (as_of, eligible) in by_week.items()
    ]
    weeks.sort(key=lambda w: (w.season, w.as_of, w.season_type, w.week))
    spreads = {
        int(game): line["spread_home"]
        for game, line in closing.items()
        if line["spread_home"] is not None
    }
    return History(
        tuple(results),
        tuple(r.kickoff for r in results),
        tuple(weeks),
        spreads,
        _benchmarks(lake),
        {int(g["source_id"]): g["earliest"] for g in games if g["earliest"] is not None},
        _team_game_stats(con),
        {
            (r["season"], int(r["team_source_id"])): r["conference"]
            for r in tables["team_seasons"].to_pylist()
            if r["team_source_id"] is not None and r["conference"] is not None
        },
        _preseason(tables, weeks),
    )


def _team_game_stats(con: Any) -> TeamGameStats:
    """Each final game's offenses from staged `team_game_advanced` (garbage time excluded, the
    only variant pulled, D-119), by season and kickoff: the games `History.results` holds (final,
    both teams known). A team-game CFBD has no row for (D-121) is simply absent."""
    stems = sorted({d.feature for d in INPUTS})
    columns = ", ".join(f"a.off_{s} AS {s}" for s in stems)
    rows = (
        con.execute(f"""
            SELECT g.source_id, g.season, g.kickoff, a.team_source_id AS team,
                CASE WHEN a.team_source_id = g.home_source_id
                    THEN g.away_source_id ELSE g.home_source_id END AS opponent,
                CASE WHEN g.neutral_site THEN 0
                    WHEN a.team_source_id = g.home_source_id THEN 1 ELSE -1 END AS site,
                {columns}
            FROM team_game_advanced a
            JOIN (SELECT *, {KICKOFF} AS kickoff FROM games) g
              ON g.source_id = a.game_source_id
             AND a.team_source_id IN (g.home_source_id, g.away_source_id)
            WHERE a.garbage_time_excluded AND g.status = 'final'
              AND g.home_points IS NOT NULL AND g.away_points IS NOT NULL
              AND g.home_source_id IS NOT NULL AND g.away_source_id IS NOT NULL
            ORDER BY g.season, g.kickoff, g.source_id, a.team_source_id""")
        .arrow()
        .read_all()
        .to_pylist()
    )
    by_season: dict[int, list[TeamGameStat]] = {}
    for r in rows:
        by_season.setdefault(r["season"], []).append(
            TeamGameStat(
                game_id=int(r["source_id"]),
                season=r["season"],
                kickoff=r["kickoff"],
                team=int(r["team"]),
                opponent=int(r["opponent"]),
                site=r["site"],
                values={s: r[s] for s in stems},
            )
        )
    return TeamGameStats({season: tuple(rs) for season, rs in by_season.items()})


def _preseason(tables: Mapping[str, Any], weeks: Sequence[Week]) -> Preseason:
    """Each preseason source's staged values (a name that matched no team dropped, so the team
    has no value), with each value season's assumed publication time and each season's first
    `as_of`."""
    from engine.sports.cfb.preseason import SOURCES

    out: dict[str, PreseasonTable] = {}
    for name, source in SOURCES.items():
        by_season: dict[int, dict[int, float]] = {}
        for r in tables[source.table].to_pylist():
            if r["team_source_id"] is not None and r[source.column] is not None:
                by_season.setdefault(r["season"], {})[int(r["team_source_id"])] = r[source.column]
        known_at = {s: source.published(s) for s in by_season}
        out[name] = PreseasonTable(by_season, known_at)
    first: dict[int, datetime] = {}
    for w in weeks:
        first[w.season] = min(first.get(w.season, w.as_of), w.as_of)
    return Preseason(SOURCES, out, first)


def _benchmarks(lake: Lake) -> tuple[Benchmark, ...]:
    """The staged benchmark ratings, or none if the lake hasn't staged them: only the SP+ and
    FPI baselines read them, and they refuse to run on none."""
    from engine.transform import staging_key

    key = staging_key("benchmark_ratings")
    if key not in lake.list(key.rpartition("/")[0]):
        return ()
    rows = _read(lake, key).to_pylist()
    return tuple(
        Benchmark(
            r["system"],
            r["season"],
            int(r["team_source_id"]),
            r["rating"],
            r["fetched_at"],
            r["known_at"],
        )
        for r in rows
        if r["team_source_id"] is not None and r["rating"] is not None
    )


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
    """Refuse a model that reads anything but `FIT_INPUTS` (and, for a baseline,
    `BASELINE_INPUTS`), naming the input."""
    allowed = FIT_INPUTS | BASELINE_INPUTS if getattr(model, "baseline", False) else FIT_INPUTS
    for name in sorted(model.reads - allowed):
        if name in REFUSED_INPUTS:
            raise RefusedError(
                f"the model asks for {name!r} as a fitting input: {REFUSED_INPUTS[name]}"
            )
        if name not in FIT_INPUTS:
            known = ", ".join(sorted(FIT_INPUTS))
            raise RefusedError(
                f"the model asks for {name!r}, which isn't a backtest input (known: {known})"
            )


def give_inputs(model: BacktestModel, history: History) -> None:
    """Hand a model the inputs besides `games` it declared (a baseline's `BASELINE_INPUTS` among
    them, once `check_reads` has let them through), and nothing else."""
    available: dict[str, Any] = {
        "team_game_stats": history.stats,
        "preseason": history.preseason,
        "closing_lines": history.closing_spreads,
        "benchmark_ratings": BenchmarkInput(history.benchmarks, history.earliest),
    }
    given = {name: available[name] for name in sorted(model.reads & available.keys())}
    if given:
        cast(Any, model).use(given)


def predict_season(model: BacktestModel, history: History, season: int) -> list[Row]:
    """Walk one season forward: fit entering each week, then predict its eligible games."""
    check_reads(model)
    give_inputs(model, history)
    note = getattr(model, "note", None)  # a baseline's remark on a game, e.g. a hindsight rating
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
                    "home_group": e.context.home_group,
                    "away_group": e.context.away_group,
                    "pred_margin": p.pred_margin,
                    "margin_sd": p.margin_sd,
                    "home_win_prob": p.home_win_prob,
                    "note": note(e.context, ratings) if note else None,
                    "spread_home": e.spread_home,
                    "spread_home_open": e.spread_home_open,
                    "spread_home_open_close": e.spread_home_open_close,
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
    choices: Mapping[int, Choices] | None = None,
) -> BacktestRun:
    """Walk each season forward with its tuned settings. `choices` replays settings another run
    chose (season -> choices) instead of tuning, so a model compared with that run is scored
    with the same settings (TASK-033's `--compare baselines`)."""
    plan = prepare(spec, factory, history, seasons, tune_from)
    if choices is not None:
        missing = [s for s in plan if s not in choices]
        if missing:
            raise RefusedError(f"no settings to replay for season {missing[0]}")
    cache: dict[tuple[tuple[tuple[str, float], ...], int], list[Row]] = {}

    def evaluate(choices: Choices, season: int) -> list[Row]:
        key = (tuple(sorted(choices.items())), season)
        if key not in cache:
            cache[key] = predict_season(factory(spec.resolve(choices)), history, season)
        return cache[key]

    def shown_only(season: int, tuning: tuple[int, ...]) -> Evaluate:
        """`evaluate` for season's tuner, refusing any season outside its tuning seasons."""

        def guarded(choices: Choices, asked: int) -> list[Row]:
            if asked not in tuning:
                raise PointInTimeError(
                    f"the tuner for {season} asked to evaluate {asked}, outside its tuning "
                    f"seasons {', '.join(map(str, tuning)) or '(none)'} (04 § 9.1)"
                )
            return evaluate(choices, asked)

        return guarded

    rows: list[Row] = []
    chosen: dict[int, Choices] = {}
    for season, tuning in plan.items():
        if choices is None:
            picked = dict(tuner(spec, tuning, shown_only(season, tuning)))
        else:
            picked = dict(choices[season])
        if not spec.resolve(picked).is_resolved:
            raise RefusedError(
                f"the settings left {', '.join(spec.resolve(picked).tunables())} "
                f"unresolved for {season}"
            )
        chosen[season] = picked
        rows += evaluate(picked, season)
    return BacktestRun(tuple(rows), chosen, plan)


def spec_hash(spec: ModelSpec) -> str:
    """sha256 of the spec's canonical JSON: the same spec always hashes the same."""
    text = json.dumps(spec.canonical(), sort_keys=True, separators=(",", ":"))
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
            ("home_group", pa.string()),  # each team's conference that season; NULL if unknown
            ("away_group", pa.string()),
            ("pred_margin", pa.float64()),
            ("margin_sd", pa.float64()),
            ("home_win_prob", pa.float64()),
            ("note", pa.string()),  # a baseline's remark (hindsight benchmark, unseen team)
            ("spread_home", pa.float64()),  # the closing line
            # The opener and the close of the books that quoted both (CLV); NULL if none did.
            ("spread_home_open", pa.float64()),
            ("spread_home_open_close", pa.float64()),
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
