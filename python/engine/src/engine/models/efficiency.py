"""Rung 2: opponent-adjusted efficiency ratings and the margin model (TASK-036; docs/04-model.md
§ 2 Rung 2, § 9.2, § 10.2, § 10.4, D-049).

**Per-stat ratings.** For each spec input (a registry stat, e.g. EPA/play), every team-game's
offense is one observation:

    stat = μ + off_O − def_D + h·s + tier_O − tier_D + ε

`s` is +1 when the offense is at home, −1 away and 0 at a neutral site, so `h` is the home edge in
the stat's own units and a home-heavy schedule doesn't flatter a team. Ridge regression penalizes
each team's offense and defense by `ridge_alpha` (weighted by recency, as in Rung 1) and leaves
`μ`, `h` and the tier terms free: a team with few games is pulled toward its anchor, one with many
barely. The anchor is the average team under `shrink_toward: zero`, and the team's tier (CFB:
Power 4, G5, FCS) under `tier`, whose levels the cross-tier games estimate. Every stat shares one
design matrix, so one least-squares solve rates them all. Ratings are then shifted so FBS teams
average zero, per stat and side: a defense rating is how much less than average it allows.

**Prior.** Last season's final per-stat ratings, regressed toward the anchor (zero, or the
tier's level last season). With `components: [last_season]` the regression is the setting
`prior.regression` (D-137); with more components (returning production, talent, recruiting)
every weight, the regression included, is fit on earlier seasons (`priors.py`, TASK-037), and
`prior.regression` only serves a season with no earlier one to fit on. It's blended in as
`w·prior + (1 − w)·in_season`, `w` decaying linearly (Rung 1's) or by the fitted curve
`k / (k + N − 1)`, whose `k` is fit with the margin model. A team that hasn't played keeps its
prior; a team with no rating last season starts from the newcomer pool's prior; with no prior,
an unseen team rates at its anchor.

**Margin model.** Turns ratings into points:

    pred_margin = HFA·(not neutral) + Σₖ b_offₖ·(offₖ,home − offₖ,away)
                                    + Σₖ b_defₖ·(defₖ,home − defₖ,away)

fit by ordinary least squares on the FBS-vs-FBS games of every season before the one predicted,
from the ratings entering each game's week, and refit once a season (04 § 9.2). Under fitted
decay each candidate `k` re-blends those games' prior and in-season gaps, and the `k` whose fit
leaves the smallest squared error is kept, with its coefficients. It's symmetric,
so it collapses to one rating per team in points, `Σ b_off·off + b_def·def`, and a prediction is
Rung 1's: HFA plus the home rating minus the away rating. σ is the margin model's residual RMSE.

**Inputs.** Per-game stats come from the harness's `team_game_stats` input, only through
`finished_by(as_of)`, and preseason values from its `preseason` input, only through
`for_season(season)`: each asserts the point-in-time rule.
"""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from typing import Any, Protocol

import numpy as np

from engine.core.inputs import INPUTS
from engine.core.interfaces import GameContext, GameHistory, GameResult, Prediction, Ratings
from engine.core.probability import NormalMargin, win_probability
from engine.core.spec import LinearDecay, ModelSpec, fixed
from engine.models.power import UnsupportedSpecError
from engine.models.priors import (
    DECAY_GRID,
    DEFAULT_PRIOR_WEEKS,
    PriorRow,
    PriorWeights,
    centred,
    decay_weight,
    fit_prior,
)
from engine.transform.features import GAME_HOURS, PointInTimeError

_WEEK = timedelta(weeks=1)
_FINISHED = timedelta(hours=GAME_HOURS)
_FEATURES = {d.id: d.feature for d in INPUTS}

Unit = int | str  # what's rated: a team id, or a pool's name


class NoEarlierSeasonError(ValueError):
    """The margin model has no season before the one predicted to be fit on."""


@dataclass(frozen=True, slots=True)
class Rules:
    """What the efficiency model needs to know about a sport."""

    pool: Callable[[str | None], str | None]  # a classification's pool; None: rated on its own
    season: Callable[[datetime], int]  # the season a date belongs to
    newcomer_pool: str  # whose prior a team with no rating last season starts from
    tier: Callable[[int, int, str | None, str | None], str]  # (season, team, group, class.)
    pool_tier: str  # the tier the pools sit in


class StatRow(Protocol):
    """One team-game offense (`harness.TeamGameStat`)."""

    @property
    def game_id(self) -> int: ...
    @property
    def team(self) -> int: ...
    @property
    def opponent(self) -> int: ...
    @property
    def site(self) -> int: ...
    @property
    def kickoff(self) -> datetime: ...
    @property
    def values(self) -> Mapping[str, float | None]: ...


class StatInput(Protocol):
    def finished_by(self, as_of: datetime, season: int) -> Sequence[StatRow]: ...


class PreseasonInput(Protocol):
    """`harness.Preseason`: each source's number per team for a season's prior."""

    def for_season(self, season: int) -> Mapping[str, Mapping[int, float]]: ...


@dataclass(frozen=True, slots=True)
class _Fit:
    """Ratings entering a date: a vector per unit, each stat's offense then each stat's defense."""

    units: dict[Unit, np.ndarray]
    levels: dict[str, np.ndarray]  # tier -> its level (under `tier` only)
    tiers: dict[Unit, str]  # unit -> its tier (under `tier` only)
    prior_weight: float
    pooled: dict[int, str]  # team id -> its pool, for teams rated as one
    newcomer: np.ndarray | None  # the prior of a team the fit hasn't seen; None: no prior
    missing: dict[str, int]  # prior component -> rated FBS teams without it (with a prior)
    weights: PriorWeights | None  # the fitted prior's weights; None: regression by setting


@dataclass(frozen=True, slots=True)
class _Parts:
    """What a fit entering a date blends: the prior and this season's in-season ratings."""

    prior: dict[Unit, np.ndarray]
    prior_levels: dict[str, np.ndarray]
    current: dict[Unit, np.ndarray]
    current_levels: dict[str, np.ndarray]
    tiers: dict[Unit, str]
    pooled: dict[int, str]
    newcomer: np.ndarray | None
    weeks: int  # this season's weeks played
    missing: dict[str, int]
    weights: PriorWeights | None


@dataclass(frozen=True, slots=True)
class MatchupRow:
    """One FBS-vs-FBS game for the margin model: its rating gaps entering its week."""

    game_id: int
    season: int
    home: float  # 1 at the home team's ground, 0 at a neutral site
    gaps: np.ndarray  # home ratings minus away ratings, as blended entering the week
    margin: float
    # Under fitted decay, in a season with a prior: the gaps of the prior alone and of the
    # in-season ratings alone, and the weeks played, so another k can re-blend them.
    prior: np.ndarray | None = None
    current: np.ndarray | None = None
    weeks: int = 0


@dataclass(frozen=True, slots=True)
class MarginModel:
    home_field: float
    coefficients: np.ndarray  # one per rating: b_off for each stat, then b_def
    sd: float
    games: int
    decay_k: float | None = None  # the fitted decay's k; None under linear decay


def _unit_order(unit: Unit) -> tuple[int, int, str]:
    return (1, 0, unit) if isinstance(unit, str) else (0, unit, "")


class EfficiencyRatings:
    def __init__(self, spec: ModelSpec, rules: Rules) -> None:
        if spec.base != "efficiency":
            raise UnsupportedSpecError(
                f"efficiency ratings need an efficiency spec, not {spec.base}"
            )
        stats = []
        for i in spec.inputs:
            if i.weight == "fit":
                stats.append(i.stat)
            elif i.weight != 0:
                raise UnsupportedSpecError(
                    f"{i.stat}: Rung 2 fits every input's weight (0 leaves it out)"
                )
        if not stats:
            raise UnsupportedSpecError("every input has weight 0: nothing to rate")
        self.stats = tuple(stats)
        self.features = tuple(_FEATURES[s] for s in stats)
        self.rules = rules
        hp = spec.hyperparameters
        self.alpha = 0.0 if hp.ridge_alpha is None else fixed(hp.ridge_alpha, "ridge_alpha")
        self.cap = None if hp.margin_cap is None else fixed(hp.margin_cap, "margin_cap")
        self.half_life = (
            None
            if hp.recency_half_life_weeks is None
            else fixed(hp.recency_half_life_weeks, "recency_half_life_weeks")
        )
        self.home_field = spec.home_field  # "fit" or a fixed number
        self.by_tier = spec.shrink_toward == "tier"
        self.has_prior = spec.prior is not None
        self.regression = 0.0
        self.zero_at_week: float | None = None  # linear decay's Z
        self.decay_fitted = False
        self.components: tuple[str, ...] = ()  # the prior's components besides last season
        prior = spec.prior
        if prior is not None:
            if "last_season" not in prior.components:
                raise UnsupportedSpecError("Rung 2's prior starts from last season's rating")
            if prior.weights != "fit":
                raise UnsupportedSpecError("Rung 2 fits the prior's weights")
            self.components = tuple(c for c in prior.components if c != "last_season")
            self.regression = fixed(prior.regression, "prior.regression")
            if isinstance(prior.decay, LinearDecay):
                self.zero_at_week = fixed(prior.decay.zero_at_week, "prior.decay.zero_at_week")
                if self.zero_at_week <= 1:
                    raise UnsupportedSpecError("prior.decay.zero_at_week must be after week 1")
            else:
                self.decay_fitted = True
        reads = {"games", "team_game_stats"} | ({"preseason"} if self.components else set())
        self.reads = frozenset(reads)
        self._zeros = np.zeros(2 * len(self.stats))
        self._stats: StatInput | None = None
        self._preseason: PreseasonInput | None = None
        self._reset()

    def _reset(self) -> None:
        self._final: dict[int, _Fit | None] = {}
        self._pure: dict[int, dict[Unit, np.ndarray] | None] = {}
        self._prior_rows: dict[int, list[PriorRow]] = {}
        self._weights: dict[int, PriorWeights | None] = {}
        self._rows: dict[int, list[MatchupRow]] = {}
        self._margin: dict[int, MarginModel] = {}

    def use(self, inputs: Mapping[str, Any]) -> None:
        """The harness's fit inputs; new ones invalidate everything learned from the old."""
        stats = inputs["team_game_stats"]
        preseason = inputs.get("preseason")
        if stats is not self._stats or preseason is not self._preseason:
            self._stats = stats
            self._preseason = preseason
            self._reset()

    # The pieces each AC checks.

    def capped(self, margin: float) -> float:
        return margin if self.cap is None else max(-self.cap, min(self.cap, margin))

    def prior_weight(self, weeks_played: int, k: float | None = None) -> float:
        """w(N), N = weeks_played + 1. Linear: 1 entering week 1, 0 from week Z on; fitted:
        k / (k + N − 1), given the season's k."""
        if self.decay_fitted:
            if k is None:
                raise ValueError("fitted decay needs the season's k")
            return decay_weight(k, weeks_played)
        if self.zero_at_week is None:
            return 0.0
        z = self.zero_at_week
        return min(1.0, max(0.0, (z - (weeks_played + 1)) / (z - 1)))

    def unit(self, team: int, classification: str | None) -> Unit:
        return self.rules.pool(classification) or team

    def tier(self, season: int, unit: Unit, group: str | None, cls: str | None) -> str:
        return (
            self.rules.pool_tier
            if isinstance(unit, str)
            else self.rules.tier(season, unit, group, cls)
        )

    def stat_ratings(self, games: GameHistory, as_of: datetime) -> dict[int | str, dict[str, Any]]:
        """Each unit's per-stat ratings entering `as_of` (stat id -> (offense, defense)), and
        each tier's level under `tier`, keyed `tier:<name>`: what the ACs inspect."""
        fit = self._rate(_by_season(games), self.rules.season(as_of), as_of)
        k = len(self.stats)
        out: dict[int | str, dict[str, Any]] = {}
        for u, v in fit.units.items():
            out[u] = {s: (float(v[i]), float(v[k + i])) for i, s in enumerate(self.stats)}
        for t, v in fit.levels.items():
            out[f"tier:{t}"] = {s: (float(v[i]), float(v[k + i])) for i, s in enumerate(self.stats)}
        return out

    # Per-stat ratings.

    def _solve(
        self, season: int, as_of: datetime, played: Sequence[GameResult]
    ) -> tuple[dict[Unit, np.ndarray], dict[str, np.ndarray], dict[Unit, str]] | None:
        """This season's ridge ratings entering `as_of` (FBS averaging zero), each tier's level
        and each unit's tier; None with no observation."""
        if self._stats is None:
            raise RuntimeError("efficiency ratings were fit before the harness gave them stats")
        info: dict[int, tuple[str | None, str | None]] = {}
        for g in played:
            info[g.home_team] = (g.home_classification, g.home_group)
            info[g.away_team] = (g.away_classification, g.away_group)
        rows = [
            r
            for r in self._stats.finished_by(as_of, season)
            if all(r.values.get(f) is not None for f in self.features)
        ]
        if not rows:
            return None

        def unit_of(team: int) -> Unit:
            return self.unit(team, info.get(team, (None, None))[0])

        offense = [unit_of(r.team) for r in rows]
        defense = [unit_of(r.opponent) for r in rows]
        units = sorted(set(offense) | set(defense), key=_unit_order)
        index = {u: i for i, u in enumerate(units)}
        n, m = len(rows), len(units)
        tiers: dict[Unit, str] = {}
        names: list[str] = []
        if self.by_tier:
            for u in units:
                cls, group = (None, None) if isinstance(u, str) else info.get(u, (None, None))
                tiers[u] = self.tier(season, u, group, cls)
            names = sorted(set(tiers.values()))
        t_index = {t: i for i, t in enumerate(names)}
        width = 2 + 2 * m + 2 * len(names)
        x = np.zeros((n, width))
        rows_at = np.arange(n)
        x[:, 0] = 1.0
        x[:, 1] = [r.site for r in rows]
        off_cols = np.array([2 + index[u] for u in offense])
        def_cols = np.array([2 + m + index[u] for u in defense])
        x[rows_at, off_cols] = 1.0
        x[rows_at, def_cols] = -1.0
        if names:
            base = 2 + 2 * m
            x[rows_at, [base + t_index[tiers[u]] for u in offense]] = 1.0
            x[rows_at, [base + len(names) + t_index[tiers[u]] for u in defense]] = -1.0
        y = np.array([[r.values[f] for f in self.features] for r in rows], dtype=float)
        if self.half_life is not None:
            ages = np.array([(as_of - r.kickoff) / _WEEK for r in rows])
            root = np.sqrt(0.5 ** (ages / self.half_life))
            x, y = x * root[:, None], y * root[:, None]
        if self.alpha > 0:
            penalty = np.zeros((2 * m, width))
            penalty[np.arange(2 * m), 2 + np.arange(2 * m)] = math.sqrt(self.alpha)
            x = np.vstack([x, penalty])
            y = np.vstack([y, np.zeros((2 * m, y.shape[1]))])
        # Minimum norm: unlinked groups, or alpha 0 where only differences are identified.
        coef = np.linalg.lstsq(x, y, rcond=None)[0]

        k = len(self.features)
        off = coef[2 : 2 + m]
        dfn = coef[2 + m : 2 + 2 * m]
        off_levels = coef[2 + 2 * m : 2 + 2 * m + len(names)]
        def_levels = coef[2 + 2 * m + len(names) :]
        if names:
            off = off + np.array([off_levels[t_index[tiers[u]]] for u in units])
            dfn = dfn + np.array([def_levels[t_index[tiers[u]]] for u in units])
        fbs = [index[u] for u in units if isinstance(u, int)]
        off_shift = off[fbs].mean(axis=0) if fbs else np.zeros(k)
        def_shift = dfn[fbs].mean(axis=0) if fbs else np.zeros(k)
        ratings = {
            u: np.concatenate([off[index[u]] - off_shift, dfn[index[u]] - def_shift]) for u in units
        }
        levels = {
            t: np.concatenate([off_levels[i] - off_shift, def_levels[i] - def_shift])
            for t, i in t_index.items()
        }
        return ratings, levels, tiers

    def _parts(
        self, by_season: Mapping[int, list[GameResult]], season: int, as_of: datetime
    ) -> _Parts:
        """What the fit entering `as_of`, a date in `season`, blends: the prior from last
        season's final ratings, and this season's games that finished by then."""
        played = [g for g in by_season.get(season, []) if g.kickoff + _FINISHED <= as_of]
        last = self._final_of(by_season, season - 1)

        prior: dict[Unit, np.ndarray] = {}
        prior_levels: dict[str, np.ndarray] = {}
        tiers: dict[Unit, str] = {}
        newcomer = None
        pooled: dict[int, str] = {}
        weights = None
        values: Mapping[str, Mapping[int, float]] = {}
        if last is not None and self.has_prior:
            prior, weights, values = self._prior(by_season, season, last)
            prior_levels = dict(last.levels)
            tiers = dict(last.tiers)
            newcomer = prior.get(self.rules.newcomer_pool, self._zeros)
            pooled = dict(last.pooled)
        for g in played:
            sides = ((g.home_team, g.home_classification), (g.away_team, g.away_classification))
            for team, cls in sides:
                pool = self.rules.pool(cls)
                if pool is None:
                    pooled.pop(team, None)
                else:
                    pooled[team] = pool

        weeks = len({(g.season_type, g.week) for g in played})
        current: dict[Unit, np.ndarray] = {}
        current_levels: dict[str, np.ndarray] = {}
        solved = self._solve(season, as_of, played) if played else None
        if solved is not None:
            current, current_levels, current_tiers = solved
            tiers |= current_tiers
        missing: dict[str, int] = {}
        if prior:
            rated = [u for u in {*prior, *current} if isinstance(u, int)]
            missing["last_season"] = sum(u not in prior for u in rated)
            for c in self.components:
                missing[c] = sum(u not in values.get(c, {}) for u in rated)
        return _Parts(
            prior,
            prior_levels,
            current,
            current_levels,
            tiers,
            pooled,
            newcomer,
            weeks,
            missing,
            weights,
        )

    def _blend(self, parts: _Parts, w: float) -> _Fit:
        """`w`·prior + (1 − `w`)·in-season: a unit that hasn't played keeps its prior, one with
        no prior starts from a newcomer's."""
        prior, prior_levels = parts.prior, parts.prior_levels
        units = dict(prior)
        levels = dict(prior_levels)
        start = self._zeros if parts.newcomer is None else parts.newcomer
        for u, v in parts.current.items():
            units[u] = w * prior.get(u, start) + (1 - w) * v if prior else v
        for t, v in parts.current_levels.items():
            levels[t] = w * prior_levels[t] + (1 - w) * v if t in prior_levels else v
        return _Fit(
            units,
            levels,
            dict(parts.tiers),
            w,
            dict(parts.pooled),
            parts.newcomer,
            parts.missing,
            parts.weights,
        )

    def _weight(self, by_season: Mapping[int, list[GameResult]], season: int, weeks: int) -> float:
        """The prior's weight in `season` after `weeks` weeks played."""
        if self.decay_fitted:
            return self.prior_weight(weeks, self.decay(by_season, season))
        return self.prior_weight(weeks)

    def _rate(
        self, by_season: Mapping[int, list[GameResult]], season: int, as_of: datetime
    ) -> _Fit:
        """The ratings entering `as_of`, a date in `season`: this season's games that finished by
        then, blended with the prior from last season's final ratings."""
        parts = self._parts(by_season, season, as_of)
        w = self._weight(by_season, season, parts.weeks) if parts.prior else 0.0
        return self._blend(parts, w)

    # The prior.

    def _anchor(self, last: _Fit, unit: Unit) -> np.ndarray:
        return last.levels.get(last.tiers.get(unit, ""), self._zeros)

    def _values(self, season: int) -> Mapping[str, Mapping[int, float]]:
        """The preseason values `season`'s prior may read (the harness asserts when each was
        published)."""
        if not self.components:
            return {}
        if self._preseason is None:
            raise RuntimeError("the prior was fit before the harness gave it preseason values")
        return self._preseason.for_season(season)

    def _centred(
        self, values: Mapping[str, Mapping[int, float]], last: _Fit
    ) -> dict[int, np.ndarray]:
        """Each FBS team with a rating last season: its components, centred on its anchor
        group's mean (its tier last season under `tier`, all of FBS under `zero`)."""
        groups = {
            u: last.tiers.get(u, "") if self.by_tier else ""
            for u in last.units
            if isinstance(u, int)
        }
        by_component = [centred(values.get(c, {}), groups) for c in self.components]
        return {u: np.array([c[u] for c in by_component]) for u in groups}

    def _prior(
        self, by_season: Mapping[int, list[GameResult]], season: int, last: _Fit
    ) -> tuple[dict[Unit, np.ndarray], PriorWeights | None, Mapping[str, Mapping[int, float]]]:
        """`season`'s prior per unit, the fitted weights it used (None: regression by setting),
        and the preseason values it read."""
        values = self._values(season)
        weights = self.prior_weights(by_season, season) if self.components else None
        keep: float | np.ndarray = 1.0 - self.regression if weights is None else weights.keep
        components = self._centred(values, last) if weights is not None else {}
        prior: dict[Unit, np.ndarray] = {}
        for u, v in last.units.items():
            anchor = self._anchor(last, u)
            prior[u] = anchor + keep * (v - anchor)
            if weights is not None and isinstance(u, int):
                prior[u] = prior[u] + components[u] @ weights.components
        return prior, weights, values

    def _pure_final(
        self, by_season: Mapping[int, list[GameResult]], season: int
    ) -> dict[Unit, np.ndarray] | None:
        """`season`'s ratings from its own games alone after its last game: the prior's
        target."""
        if season not in self._pure:
            games = by_season.get(season)
            solved = None
            if games:
                end = max(g.kickoff for g in games) + _FINISHED
                solved = self._solve(season, end, games)
            self._pure[season] = None if solved is None else solved[0]
        return self._pure[season]

    def prior_rows(self, by_season: Mapping[int, list[GameResult]], season: int) -> list[PriorRow]:
        """`season` as a target for the prior fit: each FBS team rated last season and this one,
        its ratings relative to its anchor."""
        if season not in self._prior_rows:
            last = self._final_of(by_season, season - 1)
            pure = self._pure_final(by_season, season)
            rows = []
            if last is not None and pure is not None:
                components = self._centred(self._values(season), last)
                for u in sorted(components):
                    if u in pure:
                        anchor = self._anchor(last, u)
                        last_dev, target = last.units[u] - anchor, pure[u] - anchor
                        rows.append(PriorRow(season, u, last_dev, components[u], target))
            self._prior_rows[season] = rows
        return self._prior_rows[season]

    def prior_weights(
        self, by_season: Mapping[int, list[GameResult]], season: int
    ) -> PriorWeights | None:
        """The prior's weights for `season`, fit on every earlier target season; None when
        there's none (the prior regresses by `prior.regression` instead)."""
        if season not in self._weights:
            rows = [
                r for s in sorted(by_season) if s < season for r in self.prior_rows(by_season, s)
            ]
            self._weights[season] = fit_prior(rows, season) if rows else None
        return self._weights[season]

    def decay(self, by_season: Mapping[int, list[GameResult]], season: int) -> float:
        """The fitted decay's k for `season`, fit with its margin model."""
        k = self._margin_for(by_season, season).decay_k
        if k is None:
            raise ValueError("the prior decays linearly: there's no k")
        return k

    def _final_of(self, by_season: Mapping[int, list[GameResult]], season: int) -> _Fit | None:
        """The ratings after `season`'s last game (None before the first season)."""
        if season not in self._final:
            games = by_season.get(season)
            if not games:
                self._final[season] = None
            else:
                end = max(g.kickoff for g in games) + _FINISHED
                self._final[season] = self._rate(by_season, season, end)
        return self._final[season]

    def _vector(
        self, fit: _Fit, season: int, team: int, cls: str | None, group: str | None
    ) -> np.ndarray:
        """A team's ratings: its pool's if it's pooled, else its own, else an unseen team's."""
        unit = self.unit(team, cls)
        if unit in fit.units:
            return fit.units[unit]
        if fit.newcomer is not None:
            return fit.newcomer
        if self.by_tier:
            return fit.levels.get(self.tier(season, unit, group, cls), self._zeros)
        return self._zeros

    # The margin model.

    def matchup_rows(
        self, by_season: Mapping[int, list[GameResult]], season: int
    ) -> list[MatchupRow]:
        """`season`'s FBS-vs-FBS games, each with the rating gaps entering its week."""
        if season not in self._rows:
            weeks: dict[tuple[str, int], list[GameResult]] = defaultdict(list)
            for g in by_season.get(season, []):
                weeks[(g.season_type, g.week)].append(g)
            rows = []
            for games in sorted(weeks.values(), key=lambda gs: min(g.kickoff for g in gs)):
                as_of = min(g.kickoff for g in games)
                parts = self._parts(by_season, season, as_of)
                w = self._weight(by_season, season, parts.weeks) if parts.prior else 0.0
                fit = self._blend(parts, w)
                # Under fitted decay, the prior alone and the in-season ratings alone.
                sides = ()
                if self.decay_fitted and parts.prior:
                    sides = (self._blend(parts, 1.0), self._blend(parts, 0.0))
                for g in games:
                    if self.rules.pool(g.home_classification) or self.rules.pool(
                        g.away_classification
                    ):
                        continue
                    home = self._vector(
                        fit, season, g.home_team, g.home_classification, g.home_group
                    )
                    away = self._vector(
                        fit, season, g.away_team, g.away_classification, g.away_group
                    )
                    gaps = [
                        self._vector(f, season, g.home_team, g.home_classification, g.home_group)
                        - self._vector(f, season, g.away_team, g.away_classification, g.away_group)
                        for f in sides
                    ]
                    rows.append(
                        MatchupRow(
                            g.game_id,
                            season,
                            0.0 if g.neutral_site else 1.0,
                            home - away,
                            self.capped(g.margin),
                            *gaps,
                            weeks=parts.weeks,
                        )
                    )
            self._rows[season] = rows
        return self._rows[season]

    def fit_margin(self, rows: Sequence[MatchupRow], season: int) -> MarginModel:
        """The margin model for `season`, by least squares on games of earlier seasons only."""
        late = [r for r in rows if r.season >= season]
        if late:
            shown = ", ".join(f"{r.game_id} ({r.season})" for r in late[:5])
            raise PointInTimeError(
                f"the margin model for {season} was given {len(late)} game(s) of {season} or "
                f"later: its weights are fit on earlier seasons only (04 § 9.2): {shown}"
            )
        if not rows:
            raise NoEarlierSeasonError(
                f"no season before {season} to fit the margin model on: an efficiency backtest "
                "starts a season after the first one in the lake"
            )
        gaps = np.array([r.gaps for r in rows])
        home = np.array([r.home for r in rows])
        y = np.array([r.margin for r in rows])
        if not self.decay_fitted:
            return self._least_squares(gaps, home, y)[0]
        # Each candidate k re-blends the rows that had a prior; the others stay as they are.
        prior = np.array([r.gaps if r.prior is None else r.prior for r in rows])
        current = np.array([r.gaps if r.current is None else r.current for r in rows])
        weeks = np.array([r.weeks for r in rows], dtype=float)
        has_prior = any(r.prior is not None for r in rows)
        best: tuple[float, MarginModel] | None = None
        for k in DECAY_GRID if has_prior else (DEFAULT_PRIOR_WEEKS,):
            w = (k / (k + weeks))[:, None]
            model, sse = self._least_squares(w * prior + (1 - w) * current, home, y)
            if best is None or sse < best[0]:
                best = (sse, replace(model, decay_k=k))
        assert best is not None
        return best[1]

    def _least_squares(
        self, gaps: np.ndarray, home: np.ndarray, y: np.ndarray
    ) -> tuple[MarginModel, float]:
        """The margin model fit on these gaps, and its sum of squared residuals."""
        if self.home_field == "fit":
            x = np.column_stack([home, gaps])
        else:
            x = gaps
            y = y - float(self.home_field) * home
        coef, *_ = np.linalg.lstsq(x, y, rcond=None)
        residual = y - x @ coef
        sse = math.fsum(residual**2)
        sd = math.sqrt(sse / max(len(y) - x.shape[1], 1))
        if self.home_field == "fit":
            return MarginModel(float(coef[0]), coef[1:], sd, len(y)), sse
        return MarginModel(float(self.home_field), coef, sd, len(y)), sse

    def _margin_for(self, by_season: Mapping[int, list[GameResult]], season: int) -> MarginModel:
        if season not in self._margin:
            rows = [
                r for s in sorted(by_season) if s < season for r in self.matchup_rows(by_season, s)
            ]
            self._margin[season] = self.fit_margin(rows, season)
        return self._margin[season]

    # The model interface.

    def fit(self, games: GameHistory, as_of: datetime) -> Ratings:
        by_season = _by_season(games)
        season = self.rules.season(as_of)
        margin = self._margin_for(by_season, season)
        fit = self._rate(by_season, season, as_of)
        b = margin.coefficients
        points = {u: float(b @ v) for u, v in fit.units.items()}
        teams = {u: r for u, r in points.items() if isinstance(u, int)}
        for team, pool in fit.pooled.items():
            if team not in teams and pool in points:
                teams[team] = points[pool]
        k = len(self.stats)
        params = {
            "home_field": margin.home_field,
            "margin_sd": margin.sd,
            "prior_weight": fit.prior_weight,
        }
        if fit.newcomer is not None:
            params["new_team"] = float(b @ fit.newcomer)
        params |= {f"pool_{u}": r for u, r in points.items() if isinstance(u, str)}
        params |= {f"tier_{t}": float(b @ v) for t, v in sorted(fit.levels.items())}
        params |= {f"b_off_{s}": float(b[i]) for i, s in enumerate(self.stats)}
        params |= {f"b_def_{s}": float(b[k + i]) for i, s in enumerate(self.stats)}
        if margin.decay_k is not None:
            params["decay_k"] = margin.decay_k
        if fit.weights is not None:
            keep = fit.weights.keep
            params |= {f"prior_keep_off_{s}": float(keep[i]) for i, s in enumerate(self.stats)}
            params |= {f"prior_keep_def_{s}": float(keep[k + i]) for i, s in enumerate(self.stats)}
            params |= {
                f"prior_points_{c}": float(b @ fit.weights.components[i])
                for i, c in enumerate(self.components)
            }
        params |= {f"prior_missing_{c}": float(n) for c, n in fit.missing.items()}
        return Ratings(as_of, dict(sorted(teams.items())), params)

    def rating(
        self, ratings: Ratings, season: int, team: int, cls: str | None, group: str | None
    ) -> float:
        """A team's rating in points: its pool's, its own, or an unseen team's."""
        unit = self.unit(team, cls)
        if isinstance(unit, str) and f"pool_{unit}" in ratings.params:
            return ratings.params[f"pool_{unit}"]
        if isinstance(unit, int) and unit in ratings.teams:
            return ratings.teams[unit]
        if "new_team" in ratings.params:
            return ratings.params["new_team"]
        if self.by_tier:
            return ratings.params.get(f"tier_{self.tier(season, unit, group, cls)}", 0.0)
        return 0.0

    def predict(self, game: GameContext, ratings: Ratings, as_of: datetime) -> Prediction:
        hfa = 0.0 if game.neutral_site else ratings.params["home_field"]
        home = self.rating(
            ratings, game.season, game.home_team, game.home_classification, game.home_group
        )
        away = self.rating(
            ratings, game.season, game.away_team, game.away_classification, game.away_group
        )
        sd = ratings.params["margin_sd"]
        margin = hfa + home - away
        drivers = (("Home field", hfa), ("Home rating", home), ("Away rating", -away))
        return Prediction(margin, sd, win_probability(margin, NormalMargin(sd)), drivers)


def _by_season(games: GameHistory) -> dict[int, list[GameResult]]:
    by_season: dict[int, list[GameResult]] = defaultdict(list)
    for g in games:
        by_season[g.season].append(g)
    return by_season
