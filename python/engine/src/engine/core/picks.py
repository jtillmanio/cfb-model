"""Pick and tier rules, applied exactly as a spec's `picks` says (docs/04-model.md § 4, D-055).
The backtest tunes them (`engine.backtest.pick_rules`); this only applies them.

The prediction is first shrunk toward the market by `market_shrinkage_k`, and everything after
reads the blended margin: a pick needs `|edge| ≥ min_edge_pts` and a cover probability of at
least `min_prob`, and its tier is the highest whose threshold the edge reaches. Under an
empirical margin the side the model likes can be the one the edge leans against (home by 2.4
against −2.5, when home by 3 is common, D-139): the edge for that side is negative, so it's a
pass. A game is picked through `pick_game`, which asks the sport whether it may be picked at all
(CFB: no game with an FCS team, D-047).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from engine.core.interfaces import GameContext
from engine.core.probability import MarginDistribution, Side, blended_margin, cover_probability
from engine.core.spec import PickRules, UnresolvedSettingError, fixed

__all__ = ["Pick", "Tier", "UnresolvedSettingError", "pick", "pick_game"]

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
    if (cover.edge >= 0) != (cover.side == "home"):
        return None  # the liked side's own edge is negative: it's a pass (D-139)
    if size == 0 or size < min_edge or cover.prob < min_prob:
        return None
    reached: list[Tier] = [t for t, at in thresholds if size >= at]
    return Pick(cover.side, cover.edge, cover.prob, reached[0] if reached else None, margin)


def pick_game(
    game: GameContext,
    pred_margin: float,
    spread_home: float,
    rules: PickRules,
    dist: MarginDistribution,
    pickable: Callable[[GameContext], bool],
) -> Pick | None:
    """`pick()` for a game, or None when the sport's `pickable` says the game is never picked
    (CFB: one with an FCS team, D-047). The live pick path calls this, not `pick()`."""
    return pick(pred_margin, spread_home, rules, dist) if pickable(game) else None
