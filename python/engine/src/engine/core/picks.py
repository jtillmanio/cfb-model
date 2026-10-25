"""Pick and tier rules, applied exactly as a spec's `picks` says (docs/04-model.md § 4, D-055).
Tuning the rules is M4.4; this only applies them.

The prediction is first shrunk toward the market by `market_shrinkage_k`, and everything after
reads the blended margin: a pick needs `|edge| ≥ min_edge_pts` and a cover probability of at
least `min_prob`, and its tier is the highest whose threshold the edge reaches.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from engine.core.probability import MarginDistribution, Side, blended_margin, cover_probability
from engine.core.spec import PickRules, UnresolvedSettingError, fixed

__all__ = ["Pick", "Tier", "UnresolvedSettingError", "pick"]

Tier = Literal["A", "B", "C"]


@dataclass(frozen=True, slots=True)
class Pick:
    side: Side
    edge: float  # on the blended margin
    prob: float  # P(side covers), on the blended margin
    tier: Tier | None  # None: the edge clears min_edge_pts but not tier C
    blended_margin: float


def pick(
    pred_margin: float, spread_home: float, rules: PickRules, dist: MarginDistribution
) -> Pick | None:
    """The pick against `spread_home`, or None when the rules say pass."""
    min_edge = fixed(rules.min_edge_pts, "picks.min_edge_pts")
    min_prob = fixed(rules.min_prob, "picks.min_prob")
    k = fixed(rules.market_shrinkage_k, "picks.market_shrinkage_k")
    tiers = rules.tiers
    thresholds: tuple[tuple[Tier, float], ...] = (
        ("A", fixed(tiers.A, "picks.tiers.A")),
        ("B", fixed(tiers.B, "picks.tiers.B")),
        ("C", fixed(tiers.C, "picks.tiers.C")),
    )

    margin = blended_margin(pred_margin, spread_home, k)
    cover = cover_probability(margin, spread_home, dist)
    size = abs(cover.edge)
    if size == 0 or size < min_edge or cover.prob < min_prob:
        return None
    reached: list[Tier] = [t for t, at in thresholds if size >= at]
    return Pick(cover.side, cover.edge, cover.prob, reached[0] if reached else None, margin)
