"""The probability math in `engine.core` (TASK-029): edge, cover probability, expected value and
market shrinkage (docs/04-model.md § 1, § 4)."""

import math

import pytest

from engine.core.probability import (
    EmpiricalMargin,
    MarginDistribution,
    NormalMargin,
    blended_margin,
    break_even,
    cover_probability,
    edge,
    expected_value,
    win_probability,
)

SIGMA = NormalMargin(sd=16.0)
PHI_3_OVER_16 = 0.5744  # Φ(0.1875), from a normal table, not from the code under test


def test_a_six_point_favourite_against_three_is_a_three_point_home_edge() -> None:
    cover = cover_probability(6.0, -3.0, SIGMA)

    assert edge(6.0, -3.0) == 3.0
    assert (cover.side, cover.edge) == ("home", 3.0)
    assert round(cover.prob, 4) == PHI_3_OVER_16


def test_ev_at_minus_110_is_p_times_100_over_110_minus_the_loss() -> None:
    p = cover_probability(6.0, -3.0, SIGMA).prob

    assert expected_value(p) == pytest.approx(p * 100 / 110 - (1 - p), abs=1e-12)
    assert round(expected_value(110 / 210), 6) == 0
    assert break_even() == pytest.approx(110 / 210)


def test_a_negative_edge_names_the_away_side_with_the_mirrored_probability() -> None:
    home = cover_probability(6.0, -3.0, SIGMA)
    away = cover_probability(-6.0, 3.0, SIGMA)

    assert (away.side, away.edge) == ("away", -3.0)
    assert away.prob == pytest.approx(home.prob, abs=1e-12)


def test_a_pick_em_game_is_a_coin_flip_to_win() -> None:
    assert win_probability(0.0, SIGMA) == pytest.approx(0.5)
    assert win_probability(6.0, SIGMA) == pytest.approx(cover_probability(6.0, 0.0, SIGMA).prob)


def test_market_shrinkage_blends_toward_the_line() -> None:
    assert blended_margin(6.0, -3.0, 0.6) == pytest.approx(0.6 * 6.0 + 0.4 * 3.0)
    assert blended_margin(6.0, -3.0, 1.0) == 6.0
    assert edge(blended_margin(6.0, -3.0, 1.0), -3.0) == edge(6.0, -3.0)
    assert blended_margin(6.0, -3.0, 0.0) == 3.0


def test_a_margin_sd_must_be_positive() -> None:
    with pytest.raises(ValueError, match="sd"):
        NormalMargin(sd=0.0)


# AC-3 (TASK-038): the empirical margin distribution puts mass on whole numbers, more of it on
# the key numbers 3 and 7 when earlier seasons did.

SD = 14.0


def lumpy(season: int) -> list[tuple[int, float, int]]:
    """A season of games predicted at 0 whose margins follow a bell curve, except that 3 and 7
    (either way) happen three times as often as a bell curve says. No ties, as in CFB."""
    games = []
    for m in range(-60, 61):
        if m == 0:
            continue
        count = round(400 * math.exp(-0.5 * (m / SD) ** 2))
        if abs(m) in (3, 7):
            count *= 3
        games += [(season, 0.0, m)] * count
    return games


EARLIER = lumpy(2020) + lumpy(2021)


def between(dist: MarginDistribution, pred: float, low: float, high: float) -> float:
    return dist.prob_above(pred, low) - dist.prob_above(pred, high)


def test_earlier_lumps_at_3_and_7_give_those_margins_more_weight_than_their_neighbours() -> None:
    dist = EmpiricalMargin.fit(EARLIER, 2022, SD)

    for key in (3, 7):
        assert dist.weights[key] > dist.weights[key - 1]
        assert dist.weights[key] > dist.weights[key + 1]
    assert dist.weights[0] < 0.5  # no ties in the data


@pytest.mark.parametrize("pred", [-2.0, 1.3, 6.5])
def test_a_whole_number_line_has_push_mass_and_the_three_outcomes_sum_to_one(pred: float) -> None:
    dist = EmpiricalMargin.fit(EARLIER, 2022, SD)

    above, below, push = (f(pred, 3.0) for f in (dist.prob_above, dist.prob_below, dist.prob_at))
    assert push > 0
    assert above + below + push == pytest.approx(1.0, abs=1e-12)


def test_a_half_point_line_has_no_push_mass() -> None:
    dist = EmpiricalMargin.fit(EARLIER, 2022, SD)

    assert dist.prob_at(1.3, 3.5) == 0.0
    assert dist.prob_above(1.3, 3.5) + dist.prob_below(1.3, 3.5) == pytest.approx(1.0, abs=1e-12)


@pytest.mark.parametrize("pred", [0.0, 2.0, -4.5])
def test_the_margin_lands_on_3_more_often_than_under_a_bell_curve_of_the_same_sd(
    pred: float,
) -> None:
    dist = EmpiricalMargin.fit(EARLIER, 2022, SD)

    assert between(dist, pred, 2.5, 3.5) > between(NormalMargin(SD), pred, 2.5, 3.5)


def test_the_distribution_is_fit_only_on_seasons_before_the_one_predicted() -> None:
    with pytest.raises(ValueError, match="2021"):
        EmpiricalMargin.fit(EARLIER, 2021, SD)


def test_the_distribution_round_trips_through_fitted_params() -> None:
    dist = EmpiricalMargin.fit(EARLIER, 2022, SD)
    params = {"margin_sd": SD, "home_field": 2.5, **dist.params()}

    assert EmpiricalMargin.from_params(params) == dist
    assert EmpiricalMargin.from_params({"margin_sd": SD}) is None


def test_a_cover_probability_on_a_whole_number_line_leaves_the_push_out() -> None:
    dist = EmpiricalMargin.fit(EARLIER, 2022, SD)
    cover = cover_probability(6.0, -3.0, dist)

    assert cover.push == dist.prob_at(6.0, 3.0) > 0
    assert cover.prob == pytest.approx(dist.prob_above(6.0, 3.0) / (1 - cover.push))
    assert win_probability(6.0, dist) == pytest.approx(
        dist.prob_above(6.0, 0.0) / (1 - dist.prob_at(6.0, 0.0))
    )


def test_under_a_bell_curve_there_is_no_push_and_the_numbers_are_unchanged() -> None:
    cover = cover_probability(6.0, -3.0, SIGMA)

    assert cover.push == 0.0
    assert cover.prob == SIGMA.prob_above(6.0, 3.0)
    assert win_probability(6.0, SIGMA) == SIGMA.prob_above(6.0, 0.0)


def test_near_a_key_number_the_liked_side_is_the_one_more_likely_to_cover() -> None:
    """Home by 2.4 against home −2.5: the edge (−0.1) leans away, but home by 3 is common enough
    that the away side covers less than half the time, so the model likes home (owner, plan
    revision 1)."""
    weights = [1.0] * 51
    weights[3] = 8.0
    dist = EmpiricalMargin(SD, tuple(weights))
    cover = cover_probability(2.4, -2.5, dist)

    assert dist.prob_below(2.4, 2.5) < 0.5
    assert (cover.side, cover.edge) == ("home", pytest.approx(-0.1))
    assert cover.prob == pytest.approx(dist.prob_above(2.4, 2.5)) and cover.prob > 0.5
    # A bell curve never disagrees with the edge.
    assert cover_probability(2.4, -2.5, NormalMargin(SD)).side == "away"
