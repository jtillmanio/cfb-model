"""Rung 1: least-squares power ratings (TASK-033; docs/04-model.md § 2 Rung 1 and Preseason
priors, D-049).

Every team gets one number, so that for any game

    predicted_margin = rating_home − rating_away + HFA × (not neutral_site)

**In-season fit.** Entering a week, each of this season's finished games is one equation, solved
by weighted least squares: the ratings (and HFA, when `home_field` is `fit`) with the smallest
total squared error. A margin counts up to `margin_cap` points either way; a game's weight halves
every `recency_half_life_weeks` before `as_of`. Ratings have no natural zero (adding 5 to every
team changes no prediction), so FBS ratings are shifted to average zero: a rating is points
better than the average FBS team.

**Prior.** Last season's final rating, regressed toward zero by `prior.regression`, blended in as

    rating = w·prior + (1 − w)·in_season,   w = clamp((Z − N) / (Z − 1), 0, 1)

N being 1 + this season's weeks played and Z `prior.decay.zero_at_week`; HFA blends the same way
from last season's. A team that hasn't played yet keeps its prior. Last season's final rating is
the model's own rating after that season's last game.

**Pools.** Teams of a level the sport can't rate one at a time (CFB: FCS) share one rating per
pool; which levels pool, which season a date belongs to and which pool a newcomer starts in are
the sport's `Rules` (`engine.sports.cfb.teams`).

**σ.** The root-mean-square error of the model's own week-by-week predictions of last season's
games between two separately rated teams: out of sample, refit once a season (04 § 9.2).
"""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

import numpy as np

from engine.core.interfaces import GameContext, GameHistory, GameResult, Prediction, Ratings
from engine.core.probability import NormalMargin, win_probability
from engine.core.spec import LinearDecay, ModelSpec, fixed
from engine.transform.features import GAME_HOURS

DEFAULT_SD = 14.0  # σ before there's a season to measure it on
_WEEK = timedelta(weeks=1)
_FINISHED = timedelta(hours=GAME_HOURS)

Unit = int | str  # what's rated: a team id, or a pool's name


class UnsupportedSpecError(ValueError):
    """The spec asks for something Rung 1 doesn't do."""


@dataclass(frozen=True, slots=True)
class Rules:
    """What the power model needs to know about a sport."""

    pool: Callable[[str | None], str | None]  # a classification's pool; None: rated on its own
    season: Callable[[datetime], int]  # the season a date belongs to
    newcomer_pool: str  # whose prior a team with no rating last season starts from


@dataclass(frozen=True, slots=True)
class _Fit:
    units: dict[Unit, float]  # rating by team id or pool name
    home_field: float
    prior_weight: float
    pooled: dict[int, str]  # team id -> its pool, for teams rated as one
    newcomer: float  # the rating of a team the fit hasn't seen


def _unit_order(unit: Unit) -> tuple[int, int, str]:
    return (1, 0, unit) if isinstance(unit, str) else (0, unit, "")


class PowerRatings:
    reads = frozenset({"games"})

    def __init__(self, spec: ModelSpec, rules: Rules) -> None:
        if spec.base != "power":
            raise UnsupportedSpecError(f"power ratings need a power spec, not {spec.base}")
        hp = spec.hyperparameters
        if hp.ridge_alpha is not None and fixed(hp.ridge_alpha, "ridge_alpha") != 0:
            raise UnsupportedSpecError("Rung 1 is plain least squares: ridge_alpha is Rung 2's")
        if spec.shrink_toward != "zero":
            raise UnsupportedSpecError("Rung 1 has no ridge: shrink_toward is Rung 2's")
        if spec.distribution != "normal":
            raise UnsupportedSpecError("Rung 1's margin is normal: the empirical one is Rung 2's")
        self.rules = rules
        self.cap = None if hp.margin_cap is None else fixed(hp.margin_cap, "margin_cap")
        self.half_life = (
            None
            if hp.recency_half_life_weeks is None
            else fixed(hp.recency_half_life_weeks, "recency_half_life_weeks")
        )
        self.home_field = spec.home_field  # "fit" or a fixed number
        self.regression = 0.0
        self.zero_at_week: float | None = None  # None: no prior
        prior = spec.prior
        if prior is not None:
            if prior.components != ("last_season",):
                raise UnsupportedSpecError("Rung 1's only prior is last season's rating")
            if prior.weights != "fit":
                raise UnsupportedSpecError("a one-component prior has no weights to set")
            if not isinstance(prior.decay, LinearDecay):
                raise UnsupportedSpecError("Rung 1's prior decays linearly (the backtest tunes Z)")
            self.regression = fixed(prior.regression, "prior.regression")
            self.zero_at_week = fixed(prior.decay.zero_at_week, "prior.decay.zero_at_week")
            if self.zero_at_week <= 1:
                raise UnsupportedSpecError("prior.decay.zero_at_week must be after week 1")
        self._final: dict[int, _Fit | None] = {}
        self._sd: dict[int, float] = {}

    # The pieces each AC checks.

    def capped(self, margin: float) -> float:
        return margin if self.cap is None else max(-self.cap, min(self.cap, margin))

    def game_weights(self, games: Sequence[GameResult], as_of: datetime) -> list[float]:
        """Each game's weight in a fit entering `as_of`: halved every half-life before it."""
        if self.half_life is None:
            return [1.0] * len(games)
        return [0.5 ** ((as_of - g.kickoff) / _WEEK / self.half_life) for g in games]

    def prior_weight(self, weeks_played: int) -> float:
        """w(N), N = weeks_played + 1: 1 entering week 1, 0 from week Z on."""
        if self.zero_at_week is None:
            return 0.0
        z = self.zero_at_week
        return min(1.0, max(0.0, (z - (weeks_played + 1)) / (z - 1)))

    def unit(self, team: int, classification: str | None) -> Unit:
        return self.rules.pool(classification) or team

    # Fitting.

    def _solve(
        self, games: Sequence[GameResult], as_of: datetime
    ) -> tuple[dict[Unit, float], float | None]:
        """The in-season least-squares ratings, FBS averaging zero, and the fitted HFA (None
        when HFA is fixed or no game was at a home site)."""
        homes = [self.unit(g.home_team, g.home_classification) for g in games]
        aways = [self.unit(g.away_team, g.away_classification) for g in games]
        units = sorted(set(homes) | set(aways), key=_unit_order)
        index = {u: i for i, u in enumerate(units)}
        fit_hfa = self.home_field == "fit" and any(not g.neutral_site for g in games)
        x = np.zeros((len(games), len(units) + fit_hfa))
        y = np.empty(len(games))
        for row, (g, home, away) in enumerate(zip(games, homes, aways, strict=True)):
            x[row, index[home]] = 1.0
            x[row, index[away]] = -1.0
            y[row] = self.capped(g.margin)
            if not g.neutral_site:
                if fit_hfa:
                    x[row, -1] = 1.0
                elif self.home_field != "fit":
                    y[row] -= float(self.home_field)
        root = np.sqrt(np.asarray(self.game_weights(games, as_of)))
        # Minimum norm: a week where some teams aren't yet linked by games still solves.
        solution = np.linalg.lstsq(x * root[:, None], y * root, rcond=None)[0]
        ratings = {u: float(solution[index[u]]) for u in units}
        teams = [r for u, r in ratings.items() if isinstance(u, int)]
        shift = math.fsum(teams) / len(teams) if teams else 0.0
        return {u: r - shift for u, r in ratings.items()}, float(solution[-1]) if fit_hfa else None

    def _rate(
        self, by_season: Mapping[int, list[GameResult]], season: int, as_of: datetime
    ) -> _Fit:
        """The ratings entering `as_of`, a date in `season`: this season's games that finished by
        then, blended with the prior from last season's final ratings."""
        played = [g for g in by_season.get(season, []) if g.kickoff + _FINISHED <= as_of]
        last = self._final_of(by_season, season - 1)
        fixed_hfa = None if self.home_field == "fit" else float(self.home_field)

        prior: dict[Unit, float] = {}
        prior_hfa = fixed_hfa if fixed_hfa is not None else 0.0
        newcomer = 0.0
        pooled: dict[int, str] = {}
        if last is not None and self.zero_at_week is not None:
            keep = 1.0 - self.regression
            prior = {u: keep * r for u, r in last.units.items()}
            prior_hfa = last.home_field if fixed_hfa is None else fixed_hfa
            newcomer = prior.get(self.rules.newcomer_pool, 0.0)
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
        w = self.prior_weight(weeks) if prior else 0.0
        units = dict(prior)
        hfa = prior_hfa
        if played:
            current, fitted_hfa = self._solve(played, as_of)
            for u, r in current.items():
                units[u] = w * prior.get(u, newcomer) + (1 - w) * r if prior else r
            if fitted_hfa is not None:
                hfa = w * prior_hfa + (1 - w) * fitted_hfa if prior else fitted_hfa
        return _Fit(units, hfa, w, pooled, newcomer)

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

    def _margin_sd(self, by_season: Mapping[int, list[GameResult]], season: int) -> float:
        """σ for `season`: the RMSE of last season's week-by-week predictions."""
        if season not in self._sd:
            weeks: dict[tuple[str, int], list[GameResult]] = defaultdict(list)
            for g in by_season.get(season - 1, []):
                weeks[(g.season_type, g.week)].append(g)
            errors = []
            for games in sorted(weeks.values(), key=lambda gs: min(g.kickoff for g in gs)):
                as_of = min(g.kickoff for g in games)
                fit = self._rate(by_season, season - 1, as_of)
                for g in games:
                    home = self.unit(g.home_team, g.home_classification)
                    away = self.unit(g.away_team, g.away_classification)
                    if isinstance(home, int) and isinstance(away, int):
                        hfa = 0.0 if g.neutral_site else fit.home_field
                        margin = hfa + fit.units.get(home, fit.newcomer) - fit.units.get(
                            away, fit.newcomer
                        )
                        errors.append((g.margin - margin) ** 2)
            self._sd[season] = math.sqrt(math.fsum(errors) / len(errors)) if errors else DEFAULT_SD
        return self._sd[season]

    def fit(self, games: GameHistory, as_of: datetime) -> Ratings:
        by_season: dict[int, list[GameResult]] = defaultdict(list)
        for g in games:
            by_season[g.season].append(g)
        season = self.rules.season(as_of)
        fit = self._rate(by_season, season, as_of)
        teams = {u: r for u, r in fit.units.items() if isinstance(u, int)}
        for team, pool in fit.pooled.items():
            if team not in teams and pool in fit.units:
                teams[team] = fit.units[pool]
        params = {
            "home_field": fit.home_field,
            "margin_sd": self._margin_sd(by_season, season),
            "prior_weight": fit.prior_weight,
            "new_team": fit.newcomer,
        }
        params |= {f"pool_{u}": r for u, r in fit.units.items() if isinstance(u, str)}
        return Ratings(as_of, dict(sorted(teams.items())), params)

    def rating(self, ratings: Ratings, team: int, classification: str | None) -> float:
        """A team's rating: its pool's if it's pooled, else its own, else a newcomer's."""
        pool = self.rules.pool(classification)
        if pool is not None:
            return ratings.params.get(f"pool_{pool}", ratings.params["new_team"])
        return ratings.teams.get(team, ratings.params["new_team"])

    def predict(self, game: GameContext, ratings: Ratings, as_of: datetime) -> Prediction:
        hfa = 0.0 if game.neutral_site else ratings.params["home_field"]
        home = self.rating(ratings, game.home_team, game.home_classification)
        away = self.rating(ratings, game.away_team, game.away_classification)
        sd = ratings.params["margin_sd"]
        margin = hfa + home - away
        drivers = (("Home field", hfa), ("Home rating", home), ("Away rating", -away))
        return Prediction(margin, sd, win_probability(margin, NormalMargin(sd)), drivers)
