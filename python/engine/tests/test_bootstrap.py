"""The week-level paired bootstrap (TASK-031, docs/04-model.md § 9.5, D-091): model A beats B
when the middle 95% of 10,000 week resamples of the mean error difference lies below zero.
"""

from __future__ import annotations

import math
from typing import Any

import pytest

from engine.backtest import bootstrap as b
from engine.backtest.metrics import Result

WITHIN_WEEK = (-3.0, 1.0, -1.0, -2.0, 0.0)  # a week's game-by-game differences: mean −1


def run(errors: dict[tuple[int, int], float]) -> list[dict[str, Any]]:
    """Results rows whose absolute error is `errors[(week, game)]`, the actual margin 0."""
    return [
        {
            "season": 2020,
            "season_type": "regular",
            "week": week,
            "game_source_id": f"{week}-{game}",
            "pred_margin": error,
            "margin": 0,
        }
        for (week, game), error in errors.items()
    ]


BASE = {(w, g): 3.0 + w + g for w in range(1, 11) for g in range(5)}


def test_constant_weekly_gain_beats() -> None:
    """A's error is lower than B's by 1 point on average every week, though not every game."""
    better = {(w, g): e + WITHIN_WEEK[g] for (w, g), e in BASE.items()}

    interval = b.compare(run(better), run(BASE))

    assert interval.resamples == b.RESAMPLES == 10_000
    assert interval.estimate == pytest.approx(-1.0)
    assert interval.low == pytest.approx(-1.0) and interval.high == pytest.approx(-1.0)
    assert interval.high < 0
    assert interval.beats


def test_identical_models_do_not_beat() -> None:
    interval = b.compare(run(BASE), run(BASE))

    assert interval.low <= 0 <= interval.high
    assert not interval.beats


NOISY = {(w, g): e + 2 * math.sin(1.7 * w) - 0.5 for (w, g), e in BASE.items()}  # by week


def test_the_same_seed_gives_the_same_interval() -> None:
    first = b.compare(run(NOISY), run(BASE))
    second = b.compare(run(NOISY), run(BASE))
    other = b.compare(run(NOISY), run(BASE), seed=b.SEED + 1)

    assert first == second
    assert first.low < first.estimate < first.high  # the weeks differ, so the interval is wide
    assert (other.low, other.high) != (first.low, first.high)


def test_whole_weeks_are_resampled() -> None:
    """Every game in a week shares its week's draw: a week whose games cancel out adds nothing,
    so swapping games between weeks (same game-level differences) changes the interval."""
    diffs = [((2020, "regular", w), d) for w in range(1, 11) for d in (5.0, -5.0)]
    shuffled = [((2020, "regular", w), d) for w in range(1, 6) for d in (5.0, 5.0)]
    shuffled += [((2020, "regular", w), d) for w in range(6, 11) for d in (-5.0, -5.0)]

    paired = b.mean_difference(diffs)
    split = b.mean_difference(shuffled)

    assert (paired.low, paired.high) == (0.0, 0.0)
    assert split.low < -1 and split.high > 1


def test_ats_difference_on_win_pct() -> None:
    won: Result = "W"
    lost: Result = "L"
    outcomes: list[tuple[b.WeekKey, Result | None, Result | None]] = [
        ((2020, "regular", w), won, lost) for w in range(1, 11)
    ]

    interval = b.ats_difference(outcomes)

    assert interval.estimate == 1.0  # A won every graded game, B none
    assert interval.low == interval.high == 1.0
    assert interval.low > 0


def test_compare_refuses_runs_on_different_games() -> None:
    fewer = dict(list(BASE.items())[1:])

    with pytest.raises(ValueError, match="same games"):
        b.compare(run(BASE), run(fewer))
