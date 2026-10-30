"""Pick and tier rules read from a spec's `picks` (TASK-029, docs/04-model.md § 4)."""

from datetime import UTC, datetime

import pytest

from engine.core.interfaces import GameContext
from engine.core.picks import UnresolvedSettingError, pick, pick_game
from engine.core.probability import (
    KEY_RANGE,
    EmpiricalMargin,
    NormalMargin,
    blended_margin,
    cover_probability,
    edge,
)
from engine.core.spec import PickRules
from engine.sports.cfb.teams import pickable

RULES = PickRules.model_validate(
    {"min_edge_pts": 2.5, "min_prob": 0.55, "tiers": {"A": 5.0, "B": 3.5, "C": 2.5}}
)
SIGMA = NormalMargin(sd=16.0)
SPREAD = -3.0


def tier_at(edge_pts: float, dist: NormalMargin = SIGMA) -> str | None:
    made = pick(edge_pts - SPREAD, SPREAD, RULES, dist)
    return None if made is None else made.tier


@pytest.mark.parametrize(("edge_pts", "tier"), [(5.0, "A"), (3.6, "B"), (2.5, "C"), (2.4, None)])
def test_the_edge_sets_the_tier(edge_pts: float, tier: str | None) -> None:
    assert tier_at(edge_pts) == tier


def test_an_edge_clearing_min_edge_is_no_pick_below_min_prob() -> None:
    wide = NormalMargin(sd=40.0)  # Φ(3/40) ≈ 0.530

    assert tier_at(3.0) == "C"
    assert tier_at(3.0, wide) is None


def test_an_away_edge_picks_the_away_side() -> None:
    made = pick(-9.0, 3.0, RULES, SIGMA)

    assert made is not None
    assert (made.side, made.edge, made.tier) == ("away", -6.0, "A")


def test_shrinkage_picks_on_the_blended_margin() -> None:
    rules = RULES.model_copy(update={"market_shrinkage_k": 0.5})
    made = pick(8.0, SPREAD, rules, SIGMA)  # raw edge 5.0, blended 2.5

    assert made is not None
    assert made.blended_margin == pytest.approx(blended_margin(8.0, SPREAD, 0.5))
    assert made.edge == pytest.approx(edge(made.blended_margin, SPREAD)) == pytest.approx(2.5)
    assert made.tier == "C"


def test_k_of_one_leaves_the_edge_unchanged() -> None:
    made = pick(8.0, SPREAD, RULES, SIGMA)

    assert RULES.market_shrinkage_k == 1.0
    assert made is not None
    assert (made.edge, made.blended_margin, made.tier) == (5.0, 8.0, "A")


def test_an_unresolved_rule_is_refused() -> None:
    tuned = PickRules.model_validate(RULES.model_dump() | {"min_edge_pts": {"tune": [2.5, 3.0]}})

    with pytest.raises(UnresolvedSettingError, match="min_edge_pts"):
        pick(8.0, SPREAD, tuned, SIGMA)


# AC-3 (TASK-039): D-047 on the pick path, and the liked side under an empirical margin.


def game(home: str | None, away: str | None) -> GameContext:
    return GameContext(
        game_id=1,
        season=2026,
        season_type="regular",
        week=6,
        kickoff=datetime(2026, 10, 10, 19, tzinfo=UTC),
        home_team=10,
        away_team=20,
        neutral_site=False,
        home_classification=home,
        away_classification=away,
    )


@pytest.mark.parametrize(
    ("home", "away"), [("fbs", "fcs"), ("fcs", "fbs"), ("fbs", None), (None, "fbs")]
)
def test_a_game_with_an_fcs_team_gets_no_pick(home: str | None, away: str | None) -> None:
    fcs = game(home, away)
    edge_over_every_threshold = 20.0 - SPREAD

    assert not pickable(fcs)
    assert pick_game(fcs, edge_over_every_threshold, SPREAD, RULES, SIGMA, pickable) is None


def test_an_fbs_game_is_picked_as_pick_says() -> None:
    fbs = game("fbs", "fbs")

    assert pickable(fbs)
    assert pick_game(fbs, 8.0, SPREAD, RULES, SIGMA, pickable) == pick(8.0, SPREAD, RULES, SIGMA)


def key_number_weights() -> tuple[float, ...]:
    """Margin 3 lands far more often than the bell curve says (D-139's fitted 2.45x, made
    stronger so the case is plain)."""
    return tuple(6.0 if size == 3 else 1.0 for size in range(KEY_RANGE + 1))


def test_no_pick_when_the_liked_side_is_the_one_the_edge_leans_against() -> None:
    rules = RULES.model_copy(update={"min_edge_pts": 0.0, "min_prob": 0.5})
    dist = EmpiricalMargin(4.0, key_number_weights())
    # Home by 2.4 against home -2.5: the edge leans away (-0.1), but home by 3 is so common
    # that home is likelier to cover.
    cover = cover_probability(2.4, -2.5, dist)
    assert (cover.edge < 0, cover.side) == (True, "home")

    assert pick(2.4, -2.5, rules, dist) is None


def test_under_an_empirical_margin_a_liked_side_the_edge_agrees_with_is_picked() -> None:
    rules = RULES.model_copy(update={"min_edge_pts": 0.0, "min_prob": 0.5})
    dist = EmpiricalMargin(4.0, key_number_weights())

    made = pick(2.6, -2.5, rules, dist)

    assert made is not None
    assert made.side == "home"
