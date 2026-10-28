"""Rung 2's fitted preseason prior and fitted decay (TASK-037; docs/04-model.md § 2 Preseason
priors, § 9.2): the prior's weights are recovered and fit on earlier seasons only (AC-1), the
decay curve stays in [0, 1], never rises and is fit on earlier seasons only (AC-3), and a team
missing a component gets the prior built from the ones it has, counted in `fitted_params`
(AC-4). The point-in-time check on the preseason inputs is test_backtest_leakage.py (AC-2).
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any

import numpy as np
import pytest

from engine.backtest.harness import Preseason, PreseasonTable, TeamGameStat, TeamGameStats
from engine.core.interfaces import GameResult
from engine.core.spec import ModelSpec
from engine.models.efficiency import EfficiencyRatings
from engine.models.priors import PriorRow, fit_prior
from engine.sports.cfb.preseason import SOURCES
from engine.sports.cfb.teams import EFFICIENCY_RULES
from engine.transform.features import PointInTimeError

PICKS = {"min_edge_pts": 3.0, "min_prob": 0.55, "tiers": {"A": 5.0, "B": 3.5, "C": 2.5}}
STATS = ("epa_per_play", "success_rate")
FEATURES = ("ppa", "success_rate")
COMPONENTS = ["last_season", "returning_production", "talent", "recruiting"]
SEASONS = (2021, 2022, 2023)
TEAMS = tuple(range(1, 9))
MU = np.array([0.05, 0.42])


def model(components: list[str] = COMPONENTS) -> EfficiencyRatings:
    prior = {"components": components, "regression": 0.3, "decay": {"type": "fitted"}}
    spec = {
        "base": "efficiency",
        "inputs": [{"stat": s} for s in STATS],
        "hyperparameters": {"ridge_alpha": 1},
        "prior": prior,
        "picks": PICKS,
    }
    return EfficiencyRatings(ModelSpec.model_validate(spec), EFFICIENCY_RULES)


def kickoff(season: int, week: int) -> datetime:
    return datetime(season, 9, 1, 19, tzinfo=UTC) + timedelta(weeks=week - 1)


def rounds(teams: tuple[int, ...]) -> list[list[tuple[int, int]]]:
    """A double round robin by the circle method: each round every team plays once."""
    ring = list(teams)
    first: list[list[tuple[int, int]]] = []
    for _ in range(len(ring) - 1):
        first.append([(ring[i], ring[-1 - i]) for i in range(len(ring) // 2)])
        ring = [ring[0], ring[-1], *ring[1:-1]]
    return first + [[(away, home) for home, away in r] for r in first]


class League:
    """Three seasons whose true ratings carry over (0.6 of last season's plus noise), noisy
    per-game stats from them, margins that follow them, and preseason values."""

    def __init__(self, seed: int = 7) -> None:
        rng = np.random.default_rng(seed)
        truth = {SEASONS[0]: rng.normal(0, 0.1, (len(TEAMS), 4))}
        for season in SEASONS[1:]:
            truth[season] = 0.6 * truth[season - 1] + rng.normal(0, 0.06, (len(TEAMS), 4))
        self.games: list[GameResult] = []
        self.rows: dict[int, list[TeamGameStat]] = {}
        for season in SEASONS:
            t = {team: truth[season][i] for i, team in enumerate(TEAMS)}
            for week, pairs in enumerate(rounds(TEAMS), start=1):
                for home, away in pairs:
                    self.play(season, week, home, away, t, rng)
        # Values for every season a 2021-2023 prior reads (talent Y-1, recruiting Y-3..Y).
        self.values: dict[str, dict[int, dict[int, float]]] = {name: {} for name in SOURCES}
        for season in range(SEASONS[0] - 3, SEASONS[-1] + 1):
            strength = truth.get(season, truth[SEASONS[0]]) @ np.array([1.0, 1.0, -1.0, -1.0])
            self.values["talent"][season] = {
                team: float(600 + 400 * strength[i] + rng.normal(0, 20))
                for i, team in enumerate(TEAMS)
            }
            self.values["recruiting"][season] = {
                team: float(180 + 200 * strength[i] + rng.normal(0, 15))
                for i, team in enumerate(TEAMS)
            }
            self.values["returning_production"][season] = {
                team: float(rng.uniform(0.2, 0.9)) for team in TEAMS
            }

    def play(
        self,
        season: int,
        week: int,
        home: int,
        away: int,
        truth: dict[int, np.ndarray],
        rng: np.random.Generator,
    ) -> None:
        game_id = season * 1000 + len(self.games)
        at = kickoff(season, week)
        gap = (truth[home][:2] - truth[away][2:]) - (truth[away][:2] - truth[home][2:])
        margin = int(round(3 + 60 * gap[0] + 40 * gap[1] + rng.normal(0, 8)))
        self.games.append(
            GameResult(
                game_id=game_id,
                season=season,
                season_type="regular",
                week=week,
                kickoff=at,
                home_team=home,
                away_team=away,
                neutral_site=False,
                home_classification="fbs",
                away_classification="fbs",
                home_group="SEC",
                away_group="SEC",
                home_points=30 + max(margin, -30),
                away_points=30,
            )
        )
        for offense, defense, site in ((home, away, 1), (away, home, -1)):
            value = MU + truth[offense][:2] - truth[defense][2:] + 0.02 * site
            value = value + rng.normal(0, [0.05, 0.02])
            self.rows.setdefault(season, []).append(
                TeamGameStat(
                    game_id,
                    season,
                    at,
                    offense,
                    defense,
                    site,
                    dict(zip(FEATURES, map(float, value), strict=True)),
                )
            )

    def inputs(self) -> dict[str, Any]:
        stats = TeamGameStats(
            {s: tuple(sorted(r, key=lambda x: x.kickoff)) for s, r in self.rows.items()}
        )
        tables = {
            name: PreseasonTable(by_season, {s: SOURCES[name].published(s) for s in by_season})
            for name, by_season in self.values.items()
        }
        first = {s: kickoff(s, 1) for s in SEASONS}
        return {"team_game_stats": stats, "preseason": Preseason(SOURCES, tables, first)}

    def by_season(self) -> dict[int, list[GameResult]]:
        out: dict[int, list[GameResult]] = {}
        for g in self.games:
            out.setdefault(g.season, []).append(g)
        return out

    def rescore(self, season: int, index: int, home_points: int) -> None:
        """Give `season`'s `index`-th game another score and its home offense another day."""
        games = [i for i, g in enumerate(self.games) if g.season == season]
        i = games[index]
        game = self.games[i]
        self.games[i] = replace(game, home_points=home_points)
        self.rows[season] = [
            replace(r, values={f: v + 0.3 for f, v in r.values.items() if v is not None})
            if r.game_id == game.game_id and r.team == game.home_team
            else r
            for r in self.rows[season]
        ]


def fitted(league: League, components: list[str] = COMPONENTS) -> EfficiencyRatings:
    m = model(components)
    m.use(league.inputs())
    return m


# AC-1


def test_noiseless_prior_weights_are_recovered() -> None:
    rng = np.random.default_rng(1)
    keep = np.array([0.7, 0.55, 0.62, 0.48])  # a, per rating
    weights = np.array(  # b, c, d per rating: returning production, talent, recruiting
        [[0.05, 0.02, 0.04, 0.01], [0.0004, 0.0001, -0.0003, 0.0002], [0.001, 0.0, 0.0005, 0.0003]]
    )
    rows = []
    for i in range(240):
        last = rng.normal(0, 0.1, 4)
        components = np.array([rng.uniform(-0.3, 0.3), rng.normal(0, 80), rng.normal(0, 40)])
        target = keep * last + components @ weights
        rows.append(PriorRow(2020 + i % 3, i, last, components, target))

    fitted_weights = fit_prior(rows, 2023)

    assert fitted_weights.keep == pytest.approx(keep, abs=0.01)
    assert fitted_weights.components == pytest.approx(weights, abs=0.01)
    assert fitted_weights.rows == 240


def test_a_prior_fit_given_a_row_from_the_predicted_season_fails() -> None:
    rows = [PriorRow(season, 1, np.zeros(4), np.zeros(3), np.zeros(4)) for season in (2022, 2023)]
    with pytest.raises(PointInTimeError, match="earlier seasons only"):
        fit_prior(rows, 2023)
    with pytest.raises(PointInTimeError, match="earlier seasons only"):
        fit_prior([replace(rows[0], season=2024)], 2023)


def test_the_models_prior_for_a_season_is_fit_on_earlier_seasons_only() -> None:
    league = League()
    m = fitted(league)

    weights = m.prior_weights(league.by_season(), 2023)

    assert weights is not None
    # 2022 is the only target season with a last season (2021) before 2023.
    assert weights.rows == len(TEAMS)
    rows = m.prior_rows(league.by_season(), 2022)
    expected = fit_prior(rows, 2023)
    assert weights.keep == pytest.approx(expected.keep)
    assert m.prior_weights(league.by_season(), 2022) is None  # nothing before it to fit on


# AC-3


def test_the_fitted_decay_lies_in_0_1_and_never_rises() -> None:
    league = League()
    m = fitted(league)

    k = m.decay(league.by_season(), 2023)
    curve = [m.prior_weight(weeks, k) for weeks in range(20)]

    assert curve[0] == 1.0
    assert all(0.0 <= w <= 1.0 for w in curve)
    assert all(a >= b for a, b in zip(curve, curve[1:], strict=False))


def test_the_decay_and_prior_weights_for_a_season_ignore_its_own_games() -> None:
    before = League()
    m = fitted(before)
    k = m.decay(before.by_season(), 2023)
    weights = m.prior_weights(before.by_season(), 2023)
    assert weights is not None

    after = League()
    after.rescore(2023, 3, 0)  # a 2023 game: 0 points and a better home offense
    changed = fitted(after)

    assert changed.decay(after.by_season(), 2023) == k
    moved = changed.prior_weights(after.by_season(), 2023)
    assert moved is not None
    assert np.array_equal(moved.keep, weights.keep)
    assert np.array_equal(moved.components, weights.components)


def test_a_game_from_last_season_can_change_the_decay() -> None:
    before = League()
    k = fitted(before).decay(before.by_season(), 2023)

    after = League()
    after.rescore(2022, 2, 95)  # a week-1 game of 2022 won by 65, not by its usual margin
    changed = fitted(after).decay(after.by_season(), 2023)

    assert changed != k


# AC-4


def test_a_team_missing_a_component_gets_the_prior_from_the_ones_it_has() -> None:
    league = League()
    missing_team = 8
    del league.values["talent"][2022][missing_team]  # 2023 reads 2022's talent
    m = fitted(league)
    by_season = league.by_season()
    last = by_season[2022]
    seen = by_season[2021] + last  # every game before 2023
    final = m.stat_ratings(seen, max(g.kickoff for g in last) + timedelta(hours=5))
    weights = m.prior_weights(by_season, 2023)
    assert weights is not None

    week_one = kickoff(2023, 1) - timedelta(hours=1)
    entering = m.stat_ratings(seen, week_one)  # no 2023 game yet: every team at its prior

    names = COMPONENTS[1:]
    values = {
        "returning_production": {
            t: min(1.0, max(0.0, v)) for t, v in league.values["returning_production"][2023].items()
        },
        "talent": league.values["talent"][2022],
        "recruiting": {
            t: float(np.mean([league.values["recruiting"][s][t] for s in range(2020, 2024)]))
            for t in TEAMS
        },
    }
    means = {c: float(np.mean(list(values[c].values()))) for c in names}
    for team in TEAMS:
        # Centred on FBS's mean (shrink_toward zero); the missing talent counts as average.
        centred = np.array(
            [values[c][team] - means[c] if team in values[c] else 0.0 for c in names]
        )
        last_vector = np.array([final[team][s][side] for side in (0, 1) for s in STATS])
        expected = weights.keep * last_vector + centred @ weights.components
        got = np.array([entering[team][s][side] for side in (0, 1) for s in STATS])
        assert got == pytest.approx(expected, abs=1e-12), team

    ratings = m.fit(seen, week_one)
    assert ratings.params["prior_missing_talent"] == 1.0
    assert ratings.params["prior_missing_returning_production"] == 0.0
    assert ratings.params["prior_missing_recruiting"] == 0.0
    assert ratings.params["prior_missing_last_season"] == 0.0
    assert {
        "decay_k",
        "prior_points_talent",
        "prior_keep_off_epa_per_play",
    } <= ratings.params.keys()


def test_an_unmatched_name_is_a_missing_component() -> None:
    """A staged row whose name matched no team has no team id, so the harness drops it
    (`harness._preseason`): the team simply has no value, as above."""
    from engine.backtest.harness import _preseason

    class Table:
        def __init__(self, rows: list[dict[str, Any]]) -> None:
            self.rows = rows

        def to_pylist(self) -> list[dict[str, Any]]:
            return self.rows

    rows = [
        {"season": 2022, "team_source_id": "8", "talent": 650.0},
        {"season": 2022, "team_source_id": None, "talent": 700.0},  # FIU: matched no team
    ]
    tables = {s.table: Table([]) for s in SOURCES.values()} | {"talent": Table(rows)}

    preseason = _preseason(tables, [])

    assert preseason.tables["talent"].by_season == {2022: {8: 650.0}}
