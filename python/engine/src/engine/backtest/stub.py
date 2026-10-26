"""A smoke-test model for the harness (TASK-030): a team's rating is its recency-weighted mean
margin to date, each margin capped and adjusted for home field. It isn't a baseline (TASK-032)
or Rung 1 (TASK-033); it lets `engine backtest --model stub` run end to end before they land.

It reads `hyperparameters.margin_cap` and `recency_half_life_weeks` from the resolved spec (so
tuning has something to choose), and `home_field`: a fixed number, or `fit` for the mean margin
of the non-neutral games so far.
"""

from __future__ import annotations

import math
from collections import defaultdict
from datetime import datetime, timedelta

from engine.core.interfaces import GameContext, GameHistory, Prediction, Ratings
from engine.core.probability import NormalMargin, win_probability
from engine.core.spec import ModelSpec, fixed

DEFAULT_SD = 14.0  # the margin σ before there are two games to measure it on
_WEEK = timedelta(weeks=1)


class MeanMargin:
    reads = frozenset({"games"})

    def __init__(self, spec: ModelSpec) -> None:
        hp = spec.hyperparameters
        self.cap = None if hp.margin_cap is None else fixed(hp.margin_cap, "margin_cap")
        self.half_life = (
            None
            if hp.recency_half_life_weeks is None
            else fixed(hp.recency_half_life_weeks, "recency_half_life_weeks")
        )
        self.home_field = spec.home_field

    def _capped(self, margin: float) -> float:
        return margin if self.cap is None else max(-self.cap, min(self.cap, margin))

    def fit(self, games: GameHistory, as_of: datetime) -> Ratings:
        home_games = [self._capped(g.margin) for g in games if not g.neutral_site]
        if isinstance(self.home_field, str):  # "fit"
            hfa = math.fsum(home_games) / len(home_games) if home_games else 0.0
        else:
            hfa = self.home_field
        sums: dict[int, list[float]] = defaultdict(list)
        weights: dict[int, list[float]] = defaultdict(list)
        residuals = []
        for g in games:
            adjusted = self._capped(g.margin) - (0.0 if g.neutral_site else hfa)
            residuals.append(adjusted)
            w = 1.0
            if self.half_life is not None:
                w = 0.5 ** ((as_of - g.kickoff) / _WEEK / self.half_life)
            for team, sign in ((g.home_team, 1.0), (g.away_team, -1.0)):
                sums[team].append(w * sign * adjusted)
                weights[team].append(w)
        teams = {t: math.fsum(sums[t]) / math.fsum(weights[t]) for t in sorted(sums)}
        sd = DEFAULT_SD
        if len(residuals) >= 2:
            mean = math.fsum(residuals) / len(residuals)
            sd = math.sqrt(math.fsum((r - mean) ** 2 for r in residuals) / (len(residuals) - 1))
        return Ratings(as_of, teams, {"home_field": hfa, "margin_sd": sd or DEFAULT_SD})

    def predict(self, game: GameContext, ratings: Ratings, as_of: datetime) -> Prediction:
        hfa = 0.0 if game.neutral_site else ratings.params["home_field"]
        home = ratings.teams.get(game.home_team, 0.0)
        away = ratings.teams.get(game.away_team, 0.0)
        sd = ratings.params["margin_sd"]
        margin = hfa + home - away
        drivers = (("Home field", hfa), ("Home rating", home), ("Away rating", -away))
        return Prediction(margin, sd, win_probability(margin, NormalMargin(sd)), drivers)
