"""The § 9.4 metrics and gates (TASK-031, docs/04-model.md § 9.3-9.4, D-077): records and units
at −110, margin errors against the closing line, the logistic edge trend, calibration bins and
the consistency rule, each on a fixture built so the answer is known.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from typing import Any

import pytest

from engine.backtest import metrics as m
from engine.backtest.metrics import Result

W: Result = "W"
L: Result = "L"
P: Result = "P"


def results(wins: int, losses: int, pushes: int = 0) -> list[Result]:
    counts: dict[Result, int] = {"W": wins, "L": losses, "P": pushes}
    return [r for r, n in counts.items() for _ in range(n)]


# AC-1: records, units, ROI and margin errors


def test_record_units_roi_and_errors() -> None:
    record = m.Record.of([W, L, W, P, W])

    assert (record.wins, record.losses, record.pushes) == (3, 1, 1)
    assert str(record) == "3-1-1"
    assert record.win_pct == 0.75  # 3 / 4: the push is out of win %
    assert record.units == pytest.approx(1.9)  # +1.0u a win, −1.1u a loss, 0 a push
    assert record.risked == pytest.approx(4.4)  # 1.1u a win or loss; a push is refunded
    assert record.roi == pytest.approx(1.9 / 4.4)

    # (pred_margin, spread_home, margin): the closing line's prediction is −spread_home.
    games = [(7.0, -6.0, 10), (-3.0, 4.0, -7), (10.0, -3.0, 3), (0.0, -1.0, 1), (14.0, -10.0, 14)]
    accuracy = m.accuracy(games)

    assert accuracy.games == 5
    assert accuracy.mae == pytest.approx(3.0)  # |−3|, |4|, |7|, |−1|, 0
    assert accuracy.closing_mae == pytest.approx(2.2)  # |−4|, |3|, 0, 0, |−4|
    assert accuracy.gap == pytest.approx(0.8)
    assert accuracy.rmse == pytest.approx(math.sqrt((9 + 16 + 49 + 1) / 5))
    assert accuracy.gate.status == "fail"  # the gap is over +0.5 (04 § 9.4)


def test_the_mae_gate_passes_within_half_a_point() -> None:
    accuracy = m.accuracy([(10.5, -10.0, 10), (-0.5, 0.0, 0)])  # model 0.5, closing 0.0

    assert accuracy.gap == pytest.approx(0.5)
    assert accuracy.gate.status == "pass"


@pytest.mark.parametrize(
    ("side", "margin", "spread_home", "expected"),
    [
        ("home", 11, -10.0, "W"),
        ("home", 10, -10.0, "P"),
        ("home", 9, -10.0, "L"),
        ("away", 9, -10.0, "W"),
        ("away", 3, 3.5, "L"),  # home +3.5 loses by 3: home covers
        ("away", -4, 3.5, "W"),
    ],
)
def test_grading_follows_the_cover_rule(
    side: m.Side, margin: int, spread_home: float, expected: Result
) -> None:
    assert m.grade(side, margin, spread_home) == expected


# AC-2: the edge trend


def at(prob: float, wins: int, losses: int) -> list[tuple[float, Result]]:
    return [(prob, r) for r in results(wins, losses)]


def trend(rate: Callable[[float], float], n: int = 40) -> list[tuple[float, Result]]:
    """`n` games at each edge from 0.25 to 7.75 points, `rate(edge)` of them covering."""
    points: list[tuple[float, Result]] = []
    for i in range(16):
        edge = 0.25 + 0.5 * i
        wins = round(n * rate(edge))
        points += at(edge, wins, n - wins)
    return points


def test_edge_trend_passes_on_a_trend() -> None:
    pushes: list[tuple[float, Result]] = [(4.0, P) for _ in range(50)]
    fit = m.edge_trend(trend(lambda e: 0.42 + 0.03 * e) + pushes)

    assert fit.slope is not None and fit.slope_low is not None and fit.slope_high is not None
    assert 0 < fit.slope_low < fit.slope < fit.slope_high
    assert fit.gate.status == "pass"
    assert fit.games == 640  # the pushes are left out
    assert [b.label for b in fit.buckets] == ["0–1.5", "1.5–3", "3–5", "5+"]
    assert [b.record.wins + b.record.losses for b in fit.buckets] == [120, 120, 160, 240]
    pcts = [b.record.win_pct or 0.0 for b in fit.buckets]
    assert pcts == sorted(pcts)


def test_edge_trend_fails_with_no_relationship() -> None:
    fit = m.edge_trend(trend(lambda e: 0.5))

    assert fit.slope_low is not None and fit.slope_high is not None
    assert fit.slope_low < 0 < fit.slope_high
    assert fit.gate.status == "fail"
    assert len(fit.buckets) == 4


def test_the_logistic_fit_matches_the_closed_form() -> None:
    """With the edge only 0 or 1 the fit has a closed form: the slope is the difference of the
    two log-odds, and its standard error is √(1/(n₀p₀q₀) + 1/(n₁p₁q₁))."""
    fit = m.edge_trend(at(0.0, 50, 50) + at(1.0, 60, 40))

    se = math.sqrt(1 / (100 * 0.5 * 0.5) + 1 / (100 * 0.6 * 0.4))
    assert fit.intercept == pytest.approx(0.0, abs=1e-9)
    assert fit.slope == pytest.approx(math.log(1.5))
    assert fit.slope_low == pytest.approx(math.log(1.5) - 1.959963984540054 * se)
    assert fit.slope_high == pytest.approx(math.log(1.5) + 1.959963984540054 * se)


def test_edge_trend_is_not_available_without_both_outcomes() -> None:
    every_one_covers: list[tuple[float, Result]] = [(1.0, W), (3.0, W), (6.0, W)]
    fit = m.edge_trend(every_one_covers)

    assert fit.slope is None
    assert fit.gate.status == "n/a"


# AC-3: calibration


def test_calibration_bins() -> None:
    points = (
        at(0.51, 3, 2)
        + at(0.56, 1, 0)
        + at(0.58, 0, 1)
        + [(0.70, W), (0.66, W), (0.65, L), (0.66, P)]
    )

    cal = m.calibration(points)

    assert [b.label for b in cal.bins] == [
        "50–52.5%",
        "52.5–55%",
        "55–57.5%",
        "57.5–60%",
        "60–62.5%",
        "62.5–65%",
        "65%+",
    ]
    counts = [b.count for b in cal.bins]
    assert counts == [5, 0, 1, 1, 0, 0, 3]  # the push is left out
    first, empty, last = cal.bins[0], cal.bins[1], cal.bins[6]
    assert (first.mean_prob, first.hit_rate) == (pytest.approx(0.51), 0.6)
    assert (empty.mean_prob, empty.hit_rate) == (None, None)
    assert last.mean_prob == pytest.approx((0.70 + 0.66 + 0.65) / 3)
    assert last.hit_rate == pytest.approx(2 / 3)
    assert cal.gate.status == "n/a"  # no bin holds 100 picks yet


@pytest.mark.parametrize(
    ("points", "status"),
    [
        (at(0.58, 55, 45), "pass"),  # exactly 3 points off
        (at(0.5801, 55, 45), "fail"),  # 3.01 points off
        (at(0.53, 57, 43), "fail"),  # underconfident by 4 points
        (at(0.58, 55, 45) + at(0.62, 40, 59), "pass"),  # 22 points off, but only 99 picks
        (at(0.58, 55, 45) + at(0.62, 40, 60), "fail"),
    ],
)
def test_calibration_gate_fails_exactly_on_a_full_bin_over_3_points(
    points: list[tuple[float, Result]], status: str
) -> None:
    assert m.calibration(points).gate.status == status


# AC-4: consistency (D-077)


def test_consistency_passes_with_two_seasons_below_50() -> None:
    by_season = {2016: results(45, 55), 2017: results(48, 52)}
    by_season |= {y: results(60, 40) for y in range(2018, 2024)}

    c = m.consistency(by_season)

    assert c.below_50 == 2
    assert c.best_season == 2018  # the first of the tied best
    assert c.without_best is not None and str(c.without_best) == "393-307-0"
    assert c.gate.status == "pass"


def test_consistency_fails_with_three_seasons_below_50() -> None:
    by_season = {y: results(45, 55) for y in (2016, 2017, 2018)}
    by_season |= {y: results(65, 35) for y in range(2019, 2024)}

    c = m.consistency(by_season)

    assert c.below_50 == 3
    assert c.without_best is not None and c.without_best.win_pct is not None
    assert c.without_best.win_pct > m.BREAK_EVEN  # fails on the count alone
    assert c.gate.status == "fail"


def test_consistency_fails_when_the_best_season_carries_the_pool() -> None:
    by_season = {2016: results(80, 20)} | {y: results(51, 49) for y in range(2017, 2024)}

    c = m.consistency(by_season)

    assert c.below_50 == 0
    assert (m.Record.of(r for rs in by_season.values() for r in rs).win_pct or 0) > m.BREAK_EVEN
    assert c.best_season == 2016
    assert c.without_best is not None and c.without_best.win_pct == pytest.approx(357 / 700)
    assert c.gate.status == "fail"


def test_consistency_needs_two_seasons() -> None:
    assert m.consistency({2016: results(60, 40)}).gate.status == "n/a"


def test_break_even_is_110_over_210() -> None:
    assert math.isclose(m.BREAK_EVEN, 110 / 210)


# The conference-tier breakdown (TASK-036; 04 § 9.4 › Breakdowns, § 10.4)


def tier_row(game: int, home: tuple[str, str], away: tuple[str, str], pred: float) -> dict:
    """A results row: each side's (team id, conference) in 2023."""
    return {
        "season": 2023,
        "season_type": "regular",
        "week": 1 + game % 3,
        "game_source_id": str(game),
        "home_source_id": home[0],
        "away_source_id": away[0],
        "home_group": home[1],
        "away_group": away[1],
        "pred_margin": pred,
        "margin_sd": 14.0,
        "home_win_prob": 0.6,
        "spread_home": -3.0,
        "spread_home_open": None,
        "spread_home_open_close": None,
        "margin": 7,
    }


def test_the_tier_breakdown_counts_add_up_to_the_games() -> None:
    from engine import backtest
    from engine.core.spec import ModelSpec

    sec, sun, nd = ("333", "SEC"), ("2026", "Sun Belt"), ("87", "FBS Independents")
    rows = [
        tier_row(1, sec, sun, 10.0),
        tier_row(2, sun, sec, -4.0),
        tier_row(3, sec, nd, 1.0),  # Notre Dame is Power 4
        tier_row(4, sun, sun, 3.0),
        tier_row(5, sun, ("1", "Big East"), 3.0),  # a conference the map doesn't know
    ]
    spec = ModelSpec.model_validate(
        {
            "base": "power",
            "picks": {"min_edge_pts": 3.0, "min_prob": 0.55, "tiers": {"A": 5, "B": 3.5, "C": 2.5}},
        }
    )

    scored = m.compute(rows, spec, {}, tier=(backtest.matchup_tier, backtest.TIER_MATCHUPS))
    (tiers,) = [b for b in scored.breakdowns if b.name == m.TIER_BREAKDOWN]

    assert [(g.label, g.games) for g in tiers.groups] == [
        ("Power 4 vs Power 4", 1),
        ("Power 4 vs G5", 2),
        ("G5 vs G5", 1),
        (backtest.UNMAPPED, 1),
    ]
    assert sum(g.games for g in tiers.groups) == scored.games == len(rows)
    vs_g5 = tiers.groups[1]
    assert vs_g5.mae == pytest.approx((abs(10.0 - 7) + abs(-4.0 - 7)) / 2)
    # Without the sport's labeller there's no tier breakdown.
    assert m.TIER_BREAKDOWN not in [b.name for b in m.compute(rows, spec, {}).breakdowns]


# TASK-038 AC-4: under `distribution: empirical` each row is graded with its own distribution.

KEYED = tuple(8.0 if n == 3 else 5.0 if n == 7 else 0.0 if n == 0 else 1.0 for n in range(51))
PICKY = {"min_edge_pts": 0.5, "min_prob": 0.56, "tiers": {"A": 5.0, "B": 3.5, "C": 2.5}}


def graded_spec(distribution: str) -> Any:
    from engine.core.spec import ModelSpec

    return ModelSpec.model_validate(
        {
            "base": "efficiency",
            "inputs": [{"stat": "epa_per_play"}],
            "distribution": distribution,
            "picks": PICKY,
        }
    )


def keyed_row(game: str, pred: float, spread: float, margin: int) -> dict[str, Any]:
    """A 2023 week-1 game, its distribution's key-number weights on the row."""
    return {
        "season": 2023,
        "season_type": "regular",
        "week": 1,
        "game_source_id": game,
        "pred_margin": pred,
        "margin_sd": 14.0,
        "home_win_prob": 0.6,
        "margin_weights": list(KEYED),
        "spread_home": spread,
        "spread_home_open": None,
        "spread_home_open_close": None,
        "margin": margin,
    }


# Picked so the two curves disagree: A changes side, probability, pick and bin; B changes bin;
# the week's top 4 by cover probability drops A for E.
KEYED_ROWS = [
    keyed_row("A", 6.5, -3.5, 10),
    keyed_row("B", 1.0, -3.5, -7),
    keyed_row("C", 5.5, -2.5, 3),
    keyed_row("D", 3.0, -0.5, 7),
    keyed_row("E", 10.0, -7.5, 14),
]


def test_an_empirical_spec_grades_each_row_with_its_own_distribution() -> None:
    from engine.core.picks import pick
    from engine.core.probability import EmpiricalMargin, NormalMargin, cover_probability

    empirical = {
        g.game_source_id: g for g in m.grade_rows(KEYED_ROWS, graded_spec("empirical"), {})
    }
    normal = {g.game_source_id: g for g in m.grade_rows(KEYED_ROWS, graded_spec("normal"), {})}
    rules = graded_spec("empirical").picks

    for r in KEYED_ROWS:
        dist = EmpiricalMargin(14.0, KEYED)
        cover = cover_probability(r["pred_margin"], r["spread_home"], dist)
        g = empirical[r["game_source_id"]]
        assert (g.side, g.prob) == (cover.side, cover.prob)
        assert g.result == m.grade(cover.side, r["margin"], r["spread_home"])
        assert g.pick == pick(r["pred_margin"], r["spread_home"], rules, dist)
        bell = cover_probability(r["pred_margin"], r["spread_home"], NormalMargin(14.0))
        assert normal[r["game_source_id"]].prob == bell.prob

    # A: home at 58.5% and a pick on a bell curve; away at 53.8% and no pick empirically.
    assert (normal["A"].side, normal["A"].pick is not None) == ("home", True)
    assert (empirical["A"].side, empirical["A"].pick) == ("away", None)


def bin_of(calibration: m.Calibration, game: m.Graded) -> int:
    return next(
        i
        for i, b in enumerate(calibration.bins)
        if b.low <= game.prob + 1e-9 and (b.high is None or game.prob < b.high - 1e-9)
    )


def test_calibration_and_the_contest_top_n_follow_the_empirical_distribution() -> None:
    games = m.grade_rows(KEYED_ROWS, graded_spec("empirical"), {})
    bells = m.grade_rows(KEYED_ROWS, graded_spec("normal"), {})
    by_id = {g.game_source_id: g for g in games}
    scored = m.compute(KEYED_ROWS, graded_spec("empirical"), {})

    counts = [0] * len(scored.calibration.bins)
    for g in games:
        if g.result != "P":
            counts[bin_of(scored.calibration, g)] += 1
    assert [b.count for b in scored.calibration.bins] == counts
    # B sits in the 65%+ bin empirically and 55-57.5% on a bell curve.
    assert bin_of(scored.calibration, by_id["B"]) == len(m.CALIBRATION_BINS) - 1
    assert bin_of(scored.calibration, {g.game_source_id: g for g in bells}["B"]) == 2

    top = sorted(games, key=lambda g: (-g.prob, g.game_source_id))[: m.CONTEST_PICKS]
    assert {g.game_source_id for g in top} == {"B", "C", "D", "E"}
    graded = [g for g in top if g.result != "P"]
    assert scored.contest.mean_prob == pytest.approx(
        math.fsum(g.prob for g in graded) / len(graded)
    )
    assert m.compute(KEYED_ROWS, graded_spec("normal"), {}).contest.mean_prob != pytest.approx(
        scored.contest.mean_prob
    )


def test_the_market_win_probability_uses_the_rows_distribution() -> None:
    from engine.core.probability import EmpiricalMargin, win_probability

    games = m.grade_rows(KEYED_ROWS, graded_spec("empirical"), {})
    scored = m.win_probability_score(games)
    dist = EmpiricalMargin(14.0, KEYED)
    market = [win_probability(-r["spread_home"], dist) for r in KEYED_ROWS]
    won = [1.0 if r["margin"] > 0 else 0.0 for r in KEYED_ROWS]
    expected = math.fsum((p - w) ** 2 for p, w in zip(market, won, strict=True)) / len(won)
    assert scored.market_brier == pytest.approx(expected)


def test_the_cover_brier_score_leaves_pushes_out() -> None:
    games = m.grade_rows(KEYED_ROWS, graded_spec("empirical"), {})
    graded = [g for g in games if g.result != "P"]
    expected = math.fsum((g.prob - (g.result == "W")) ** 2 for g in graded) / len(graded)

    assert m.cover_brier(games) == pytest.approx(expected)


def test_an_empirical_spec_refuses_a_row_without_its_distribution() -> None:
    row = {k: v for k, v in KEYED_ROWS[0].items() if k != "margin_weights"}
    with pytest.raises(ValueError, match="margin_weights"):
        m.grade_rows([row], graded_spec("empirical"), {})


# TASK-042 AC-2: what the calibration gate bins and the cover Brier reads is the displayed
# probability, after the display shrinkage; the side, edge and pick stay on the blended margin.


def display_spec(display_k: float) -> Any:
    from engine.core.spec import ModelSpec

    return ModelSpec.model_validate(
        {
            "base": "power",
            "picks": {
                "min_edge_pts": 3.0,
                "min_prob": 0.5,
                "display_shrinkage_k": display_k,
                "tiers": {"A": 9.0, "B": 6.0, "C": 3.0},
            },
        }
    )


def plain_row(game: str, pred: float, margin: int) -> dict[str, Any]:
    """A 2023 week-1 pick'em game the model has home by `pred`, at σ 16."""
    return {
        "season": 2023,
        "season_type": "regular",
        "week": 1,
        "game_source_id": game,
        "pred_margin": pred,
        "margin_sd": 16.0,
        "home_win_prob": 0.6,
        "spread_home": 0.0,
        "spread_home_open": None,
        "spread_home_open_close": None,
        "margin": margin,
    }


DISPLAY_ROWS = [
    plain_row(str(n), pred, margin)
    for n, (pred, margin) in enumerate(
        [(12.0, 7), (12.0, -3), (8.0, 10), (-6.0, -14), (-6.0, 3), (2.0, 1), (20.0, -1)] * 20
    )
]


def test_the_graded_probability_is_the_displayed_one() -> None:
    from statistics import NormalDist

    raw = m.grade_rows(DISPLAY_ROWS, display_spec(1.0), {})
    shown = m.grade_rows(DISPLAY_ROWS, display_spec(0.2), {})

    for r, s in zip(raw, shown, strict=True):
        assert (s.side, s.edge, s.result, called(s)) == (r.side, r.edge, r.result, called(r))
        assert r.prob == pytest.approx(NormalDist().cdf(abs(r.edge) / 16.0))
        assert s.prob == pytest.approx(NormalDist().cdf(0.2 * abs(s.edge) / 16.0))
    assert m.cover_brier(shown) == pytest.approx(
        math.fsum((g.prob - (g.result == W)) ** 2 for g in shown if g.result != P)
        / sum(g.result != P for g in shown)
    )
    assert m.cover_brier(shown) != pytest.approx(m.cover_brier(raw))
    scored = m.compute(DISPLAY_ROWS, display_spec(0.2), {})
    assert scored.calibration == m.calibration((g.prob, g.result) for g in shown)
    assert scored.calibration != m.compute(DISPLAY_ROWS, display_spec(1.0), {}).calibration
    assert scored.picks == m.compute(DISPLAY_ROWS, display_spec(1.0), {}).picks


def called(g: m.Graded) -> tuple[str, float, str | None] | None:
    """The pick's side, edge and tier: everything but the probability shown with it."""
    return None if g.pick is None else (g.pick.side, g.pick.edge, g.pick.tier)
