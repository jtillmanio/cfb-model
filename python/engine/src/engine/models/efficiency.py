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

**Prior.** Last season's final per-stat ratings, regressed toward the anchor by `prior.regression`
(toward zero, or toward the tier's level last season), blended in with Rung 1's linear decay. A
team that hasn't played keeps its prior; a team with no rating last season starts from the
newcomer pool's prior; with no prior, an unseen team rates at its anchor.

**Margin model.** Turns ratings into points:

    pred_margin = HFA·(not neutral) + Σₖ b_offₖ·(offₖ,home − offₖ,away)
                                    + Σₖ b_defₖ·(defₖ,home − defₖ,away)

fit by ordinary least squares on the FBS-vs-FBS games of every season before the one predicted,
from the ratings entering each game's week, and refit once a season (04 § 9.2). It's symmetric,
so it collapses to one rating per team in points, `Σ b_off·off + b_def·def`, and a prediction is
Rung 1's: HFA plus the home rating minus the away rating. σ is the margin model's residual RMSE.

**Inputs.** Per-game stats come from the harness's `team_game_stats` input, only through
`finished_by(as_of)`, which asserts the point-in-time rule.
"""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Protocol

import numpy as np

from engine.core.inputs import INPUTS
from engine.core.interfaces import GameContext, GameHistory, GameResult, Prediction, Ratings
from engine.core.probability import NormalMargin, win_probability
from engine.core.spec import LinearDecay, ModelSpec, fixed
from engine.models.power import UnsupportedSpecError
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


@dataclass(frozen=True, slots=True)
class _Fit:
    """Ratings entering a date: a vector per unit, each stat's offense then each stat's defense."""

    units: dict[Unit, np.ndarray]
    levels: dict[str, np.ndarray]  # tier -> its level (under `tier` only)
    tiers: dict[Unit, str]  # unit -> its tier (under `tier` only)
    prior_weight: float
    pooled: dict[int, str]  # team id -> its pool, for teams rated as one
    newcomer: np.ndarray | None  # the prior of a team the fit hasn't seen; None: no prior


@dataclass(frozen=True, slots=True)
class MatchupRow:
    """One FBS-vs-FBS game for the margin model: its rating gaps entering its week."""

    game_id: int
    season: int
    home: float  # 1 at the home team's ground, 0 at a neutral site
    gaps: np.ndarray  # home ratings minus away ratings
    margin: float


@dataclass(frozen=True, slots=True)
class MarginModel:
    home_field: float
    coefficients: np.ndarray  # one per rating: b_off for each stat, then b_def
    sd: float
    games: int


def _unit_order(unit: Unit) -> tuple[int, int, str]:
    return (1, 0, unit) if isinstance(unit, str) else (0, unit, "")


class EfficiencyRatings:
    reads = frozenset({"games", "team_game_stats"})

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
        self.regression = 0.0
        self.zero_at_week: float | None = None  # None: no prior
        prior = spec.prior
        if prior is not None:
            if prior.components != ("last_season",):
                raise UnsupportedSpecError(
                    "Rung 2's prior is last season's rating (M4.2 adds more)"
                )
            if prior.weights != "fit":
                raise UnsupportedSpecError("a one-component prior has no weights to set")
            if not isinstance(prior.decay, LinearDecay):
                raise UnsupportedSpecError("Rung 2's prior decays linearly (the backtest tunes Z)")
            self.regression = fixed(prior.regression, "prior.regression")
            self.zero_at_week = fixed(prior.decay.zero_at_week, "prior.decay.zero_at_week")
            if self.zero_at_week <= 1:
                raise UnsupportedSpecError("prior.decay.zero_at_week must be after week 1")
        self._zeros = np.zeros(2 * len(self.stats))
        self._stats: StatInput | None = None
        self._reset()

    def _reset(self) -> None:
        self._final: dict[int, _Fit | None] = {}
        self._rows: dict[int, list[MatchupRow]] = {}
        self._margin: dict[int, MarginModel] = {}

    def use(self, inputs: Mapping[str, Any]) -> None:
        """The harness's fit inputs; new ones invalidate everything learned from the old."""
        stats = inputs["team_game_stats"]
        if stats is not self._stats:
            self._stats = stats
            self._reset()

    # The pieces each AC checks.

    def capped(self, margin: float) -> float:
        return margin if self.cap is None else max(-self.cap, min(self.cap, margin))

    def prior_weight(self, weeks_played: int) -> float:
        """w(N), N = weeks_played + 1: 1 entering week 1, 0 from week Z on."""
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

    def _rate(
        self, by_season: Mapping[int, list[GameResult]], season: int, as_of: datetime
    ) -> _Fit:
        """The ratings entering `as_of`, a date in `season`: this season's games that finished by
        then, blended with the prior from last season's final ratings."""
        played = [g for g in by_season.get(season, []) if g.kickoff + _FINISHED <= as_of]
        last = self._final_of(by_season, season - 1)

        prior: dict[Unit, np.ndarray] = {}
        prior_levels: dict[str, np.ndarray] = {}
        tiers: dict[Unit, str] = {}
        newcomer = None
        pooled: dict[int, str] = {}
        if last is not None and self.zero_at_week is not None:
            keep = 1.0 - self.regression
            for u, v in last.units.items():
                anchor = last.levels.get(last.tiers.get(u, ""), self._zeros)
                prior[u] = anchor + keep * (v - anchor)
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
        w = self.prior_weight(weeks) if prior else 0.0
        units = dict(prior)
        levels = dict(prior_levels)
        solved = self._solve(season, as_of, played) if played else None
        if solved is not None:
            current, current_levels, current_tiers = solved
            start = self._zeros if newcomer is None else newcomer
            for u, v in current.items():
                units[u] = w * prior.get(u, start) + (1 - w) * v if prior else v
            for t, v in current_levels.items():
                levels[t] = w * prior_levels[t] + (1 - w) * v if t in prior_levels else v
            tiers |= current_tiers
        return _Fit(units, levels, tiers, w, pooled, newcomer)

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
                fit = self._rate(by_season, season, as_of)
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
                    rows.append(
                        MatchupRow(
                            g.game_id,
                            season,
                            0.0 if g.neutral_site else 1.0,
                            home - away,
                            self.capped(g.margin),
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
        if self.home_field == "fit":
            x = np.column_stack([home, gaps])
        else:
            x = gaps
            y = y - float(self.home_field) * home
        coef, *_ = np.linalg.lstsq(x, y, rcond=None)
        residual = y - x @ coef
        dof = max(len(rows) - x.shape[1], 1)
        sd = math.sqrt(math.fsum(residual**2) / dof)
        if self.home_field == "fit":
            return MarginModel(float(coef[0]), coef[1:], sd, len(rows))
        return MarginModel(float(self.home_field), coef, sd, len(rows))

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
