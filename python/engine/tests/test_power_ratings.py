"""Rung 1's least-squares power ratings (TASK-033; docs/04-model.md § 2 Rung 1 and Preseason
priors): the fit, the margin cap and recency weights, the prior from last season, and a golden
backtest on the TASK-030 fixture.
"""

from __future__ import annotations

import io
import json
import os
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq
import pytest
from lake_fixture import engine, staged, write_backtest_seasons

from engine import backtest
from engine.backtest import harness
from engine.core.interfaces import GameResult
from engine.core.spec import ModelSpec
from engine.ingest.lake import LocalLake
from engine.models.power import PowerRatings, UnsupportedSpecError
from engine.sports.cfb.teams import RULES, pool_of, season_of
from engine.transform import rebuild

PICKS = {"min_edge_pts": 3.0, "min_prob": 0.55, "tiers": {"A": 5.0, "B": 3.5, "C": 2.5}}
GOLDEN = Path(__file__).parent / "fixtures" / "backtest_power_golden.csv"
FCS_TEAM = 50


def model(**spec: Any) -> PowerRatings:
    return PowerRatings(ModelSpec.model_validate({"base": "power", "picks": PICKS, **spec}), RULES)


def game(
    season: int,
    week: int,
    home: int,
    away: int,
    margin: int,
    *,
    neutral: bool = False,
    game_id: int | None = None,
) -> GameResult:
    """A final regular-season game on a Saturday of `week`, the FCS team classified as such."""
    kickoff = datetime(season, 9, 2, 19, tzinfo=UTC) + timedelta(weeks=week - 1)
    return GameResult(
        game_id=game_id if game_id is not None else season * 10_000 + week * 100 + home,
        season=season,
        season_type="regular",
        week=week,
        kickoff=kickoff,
        home_team=home,
        away_team=away,
        neutral_site=neutral,
        home_classification="fcs" if home == FCS_TEAM else "fbs",
        away_classification="fcs" if away == FCS_TEAM else "fbs",
        home_points=40 + margin,
        away_points=40,
    )


def after(games: list[GameResult]) -> datetime:
    """An as_of once every game has finished (four hours after kickoff)."""
    return max(g.kickoff for g in games) + timedelta(hours=5)


# AC-1

TRUE = {1: 7.0, 2: 3.0, 3: -2.0, 4: -8.0}
HFA = 3.0


def noiseless(season: int = 2023) -> list[GameResult]:
    """Every pairing at both teams' grounds and once at a neutral site, margins exactly
    rating_home − rating_away + HFA."""
    games = []
    week = 1
    for home in TRUE:
        for away in TRUE:
            if home == away:
                continue
            margin = TRUE[home] - TRUE[away] + HFA
            games.append(game(season, week, home, away, int(margin)))
            if home < away:
                neutral = int(TRUE[home] - TRUE[away])
                games.append(game(season, week, home, away, neutral, neutral=True, game_id=week))
            week += 1
    return games


def test_noiseless_fixture_recovers_ratings_and_home_field() -> None:
    games = noiseless()
    ratings = model().fit(games, after(games))

    assert ratings.teams.keys() == TRUE.keys()
    for team, rating in TRUE.items():
        assert ratings.teams[team] == pytest.approx(rating, abs=0.01)
    assert ratings.params["home_field"] == pytest.approx(HFA, abs=0.01)
    assert sum(ratings.teams.values()) / len(ratings.teams) == pytest.approx(0.0, abs=1e-9)


# AC-2

CAPPED = [
    game(2023, 1, 1, 2, 10),
    game(2023, 2, 2, 3, 4),
    game(2023, 3, 3, 4, -6),
    game(2023, 4, 4, 1, -14),
    game(2023, 5, 1, 3, 17),
]


@pytest.mark.parametrize("blowout", [29, 45, 70])
@pytest.mark.parametrize("sign", [1, -1])
def test_margin_beyond_the_cap_fits_like_the_cap(blowout: int, sign: int) -> None:
    at_cap = [*CAPPED, game(2023, 6, 2, 4, sign * 28)]
    beyond = [*CAPPED, game(2023, 6, 2, 4, sign * blowout)]
    fit = model(hyperparameters={"margin_cap": 28}).fit
    assert fit(beyond, after(beyond)).teams == pytest.approx(fit(at_cap, after(at_cap)).teams)
    # Uncapped, the blowout moves the ratings.
    plain = model().fit
    assert plain(beyond, after(beyond)).teams != pytest.approx(plain(at_cap, after(at_cap)).teams)


@pytest.mark.parametrize("half_life", [2.0, 4.0, 8.0])
def test_a_game_one_half_life_older_has_half_the_weight(half_life: float) -> None:
    as_of = datetime(2023, 11, 30, tzinfo=UTC)
    newer = game(2023, 10, 1, 2, 3)
    older = game(2023, 10, 3, 4, 3)
    older = replace(older, kickoff=newer.kickoff - timedelta(weeks=half_life))
    power = model(hyperparameters={"recency_half_life_weeks": half_life})
    new_weight, old_weight = power.game_weights([newer, older], as_of)
    assert old_weight / new_weight == pytest.approx(0.5)
    assert model().game_weights([newer, older], as_of) == [1.0, 1.0]


def test_recency_weighting_moves_the_fit_toward_recent_games() -> None:
    # Team 1 beat team 2 by 20 early and lost by 20 late: weighted toward the late game, 2 leads.
    games = [game(2023, 1, 1, 2, 20, neutral=True), game(2023, 9, 1, 2, -20, neutral=True)]
    ratings = model(hyperparameters={"recency_half_life_weeks": 2}).fit(games, after(games))
    assert ratings.teams[2] > ratings.teams[1]
    even = model().fit(games, after(games))
    assert even.teams[1] == pytest.approx(even.teams[2])


# AC-3

LAST = [
    game(2022, 1, 1, 2, 14),
    game(2022, 2, 2, 3, 3),
    game(2022, 3, 3, 4, 10),
    game(2022, 4, 4, 1, -21),
    game(2022, 5, 1, FCS_TEAM, 35),
    game(2022, 6, 3, FCS_TEAM, 17),
    game(2022, 7, 2, 4, 7),
]
THIS = [
    game(2023, 1, 4, 1, 10),
    game(2023, 1, 2, 3, -6),
    game(2023, 2, 1, 3, 3),
    game(2023, 2, 4, 2, 2),
    game(2023, 3, 1, 2, -7),
    game(2023, 3, 3, 4, 1),
    game(2023, 4, 2, FCS_TEAM, 24),
    game(2023, 5, 3, 1, 9),
]
PRIOR = {"components": ["last_season"], "regression": 0.3}
WEEK_ONE = datetime(2023, 8, 26, tzinfo=UTC)


def with_prior(zero_at_week: float = 4, **spec: Any) -> PowerRatings:
    prior = {**PRIOR, "decay": {"type": "linear", "zero_at_week": zero_at_week}}
    return model(prior=prior, **spec)


def test_week_one_is_last_season_regressed() -> None:
    final = with_prior().fit(LAST, after(LAST))
    assert final.params["prior_weight"] == 0.0  # 2022's own games, no 2021 to lean on
    week_one = with_prior().fit(LAST, WEEK_ONE)

    assert week_one.params["prior_weight"] == 1.0
    assert week_one.teams.keys() == final.teams.keys()
    for team, rating in final.teams.items():
        assert week_one.teams[team] == pytest.approx(0.7 * rating), team
    assert week_one.params["pool_fcs"] == pytest.approx(0.7 * final.params["pool_fcs"])
    assert week_one.params["home_field"] == pytest.approx(final.params["home_field"])
    # The FCS team is rated as its pool.
    assert week_one.teams[FCS_TEAM] == week_one.params["pool_fcs"]


def test_a_new_team_gets_the_pool_prior() -> None:
    power = with_prior()
    final = with_prior().fit(LAST, after(LAST))
    week_one = power.fit(LAST, WEEK_ONE)
    pool_prior = 0.7 * final.params["pool_fcs"]

    assert week_one.params["new_team"] == pytest.approx(pool_prior)
    # A team new to FBS (every one since 2014 came up from FCS) and a new FCS team.
    assert power.rating(week_one, 99, "fbs") == pytest.approx(pool_prior)
    assert power.rating(week_one, 98, "fcs") == pytest.approx(pool_prior)

    # Once a new FBS team plays, its prior is still the pool's.
    games = [*LAST, game(2023, 1, 99, 1, 10)]
    week_two = with_prior().fit(games, after(games))
    plain = model().fit(games[-1:], after(games))
    w = week_two.params["prior_weight"]
    expected = w * pool_prior + (1 - w) * plain.teams[99]
    assert week_two.teams[99] == pytest.approx(expected)


def test_the_prior_weight_falls_as_weeks_pass() -> None:
    games = [*LAST, *THIS]
    final = with_prior().fit(LAST, after(LAST))
    weights = []
    for week in range(1, 7):
        as_of = datetime(2023, 8, 30, tzinfo=UTC) + timedelta(weeks=week - 1)
        ratings = with_prior(zero_at_week=4).fit(
            [g for g in games if g.kickoff < as_of - timedelta(hours=4)], as_of
        )
        w = ratings.params["prior_weight"]
        weights.append(w)
        # Each rating is that weight on the prior and the rest on this season's games alone.
        played = [g for g in THIS if g.kickoff < as_of]
        if played:
            plain = model().fit(played, as_of)
            for team, rating in plain.teams.items():
                prior = 0.7 * final.teams[team]
                assert ratings.teams[team] == pytest.approx(w * prior + (1 - w) * rating)
    # w(N) = (Z - N) / (Z - 1) entering week N, N = 1 + weeks played; 0 from week Z on.
    assert weights == pytest.approx([1.0, 2 / 3, 1 / 3, 0.0, 0.0, 0.0])


def test_without_a_prior_a_season_stands_alone() -> None:
    games = [*LAST, *THIS]
    alone = model().fit(games, after(games))
    only_this = model().fit(THIS, after(games))
    assert alone.teams.keys() >= only_this.teams.keys()
    for team, rating in only_this.teams.items():
        assert alone.teams[team] == pytest.approx(rating)


def test_sigma_is_last_seasons_out_of_sample_error() -> None:
    power = with_prior(zero_at_week=4)
    games = [*LAST, *THIS]
    sd = power.fit(games, WEEK_ONE).params["margin_sd"]
    # Replay 2022 week by week, as the model does, from ratings entering each week.
    errors = []
    for g in LAST:
        if FCS_TEAM in (g.home_team, g.away_team):
            continue
        entering = with_prior(zero_at_week=4).fit([x for x in LAST if x.week < g.week], g.kickoff)
        predicted = with_prior().predict(g, entering, g.kickoff).pred_margin
        errors.append((g.margin - predicted) ** 2)
    assert sd == pytest.approx((sum(errors) / len(errors)) ** 0.5)


def test_a_fixed_home_field_is_used_as_given() -> None:
    games = noiseless()
    ratings = model(home_field=3.0).fit(games, after(games))
    assert ratings.params["home_field"] == 3.0
    for team, rating in TRUE.items():
        assert ratings.teams[team] == pytest.approx(rating, abs=0.01)


@pytest.mark.parametrize(
    ("spec", "message"),
    [
        ({"hyperparameters": {"ridge_alpha": 5}}, "ridge_alpha"),
        ({"prior": {**PRIOR, "decay": {"type": "fitted"}}}, "linearly"),
        (
            {"prior": {**PRIOR, "components": ["talent"], "decay": {"type": "fitted"}}},
            "last season",
        ),
        ({"prior": {**PRIOR, "decay": {"type": "linear", "zero_at_week": 1}}}, "after week 1"),
        ({"distribution": "empirical"}, "empirical"),  # TASK-038: Rung 2's
    ],
)
def test_what_rung_1_doesnt_do_is_refused(spec: dict[str, Any], message: str) -> None:
    with pytest.raises(UnsupportedSpecError, match=message):
        model(**spec)


def test_the_cfb_rules() -> None:
    assert pool_of("fbs") is None
    assert pool_of("fcs") == pool_of("ii") == pool_of(None) == "fcs"
    assert season_of(datetime(2023, 8, 26, tzinfo=UTC)) == 2023
    assert season_of(datetime(2024, 1, 9, tzinfo=UTC)) == 2023
    assert backtest.MODELS["power"](ModelSpec.model_validate({"base": "power", "picks": PICKS}))


# The golden backtest on the TASK-030 fixture.

SPEC = {
    "base": "power",
    "hyperparameters": {"margin_cap": {"tune": [14, 28]}, "recency_half_life_weeks": 4},
    "prior": {**PRIOR, "decay": {"type": "linear", "zero_at_week": 4}},
    "picks": PICKS,
}


def render(data: bytes) -> str:
    """The results as CSV text, numbers rounded to 8 decimals: LAPACK's last bits differ between
    Windows and Linux (CI), and a rating that should be exactly zero mustn't flip sign."""
    table = pq.read_table(io.BytesIO(data))
    lines = [",".join(table.column_names)]
    for row in table.to_pylist():
        cells = []
        for value in row.values():
            if isinstance(value, float):
                cells.append(f"{round(value, 8) + 0.0:.10g}")
            else:
                cells.append("" if value is None else str(value))
        lines.append(",".join(cells))
    return "\n".join(lines) + "\n"


@pytest.fixture
def backtest_lake(empty_lake: LocalLake) -> LocalLake:
    write_backtest_seasons(empty_lake)
    rebuild(empty_lake)
    return empty_lake


def test_power_backtest_matches_the_golden_file(backtest_lake: LocalLake, tmp_path: Path) -> None:
    spec = tmp_path / "spec.json"
    spec.write_text(json.dumps(SPEC), "utf-8")
    argv = ["backtest", "--spec", str(spec), "--seasons", "2023", "--tune-from", "2022"]

    assert engine(*argv) == 0
    assert engine(*argv) == 0

    keys = [k for k in backtest_lake.walk("backtests") if k.endswith("/predictions.parquet")]
    first, second = (backtest_lake.read(k) for k in keys)
    assert first == second
    text = render(first)
    if os.environ.get("UPDATE_GOLDEN") == "1":
        GOLDEN.write_text(text, "utf-8", newline="\n")
    assert text == GOLDEN.read_text("utf-8")


def test_the_harness_gives_the_power_model_each_teams_classification(
    backtest_lake: LocalLake,
) -> None:
    history = harness.load(backtest_lake)
    games = {int(g["source_id"]): g for g in staged(backtest_lake, "games").to_pylist()}
    for result in history.results:
        row = games[result.game_id]
        assert result.home_classification == row["home_classification"]
        assert result.away_classification == row["away_classification"]
    assert "fcs" in {g.away_classification for g in history.results}
