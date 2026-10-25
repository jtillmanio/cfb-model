"""Pick and tier rules read from a spec's `picks` (TASK-029, docs/04-model.md § 4)."""

import pytest

from engine.core.picks import UnresolvedSettingError, pick
from engine.core.probability import NormalMargin, blended_margin, edge
from engine.core.spec import PickRules

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
