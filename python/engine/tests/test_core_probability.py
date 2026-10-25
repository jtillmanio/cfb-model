"""The probability math in `engine.core` (TASK-029): edge, cover probability, expected value and
market shrinkage (docs/04-model.md § 1, § 4)."""

import pytest

from engine.core.probability import (
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
