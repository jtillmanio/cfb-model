"""From a predicted margin and a line to an edge, a cover probability and an expected value
(docs/04-model.md § 1, § 4). Pure math: the API runs it for hypothetical matchups.

Signs follow CLAUDE.md: `margin = home − away`, `spread_home` is negative when home is favored,
and home covers when `margin + spread_home > 0`.

Every probability goes through a `MarginDistribution`, so the empirical distribution (D-053,
M4.3) and a per-game σ (M19.2) replace `NormalMargin` without changing a caller. It asks for
`P(margin > t)` and `P(margin < t)` separately because an empirical distribution puts mass on
whole numbers: on a whole-number line the two don't sum to 1, and the rest is the push.
"""

from __future__ import annotations

from dataclasses import dataclass
from statistics import NormalDist
from typing import Literal, Protocol

Side = Literal["home", "away"]

_PHI = NormalDist().cdf  # Φ, the standard normal CDF


class MarginDistribution(Protocol):
    """How actual margins scatter around a predicted one."""

    def prob_above(self, pred_margin: float, threshold: float) -> float:
        """P(margin > threshold)."""
        ...

    def prob_below(self, pred_margin: float, threshold: float) -> float:
        """P(margin < threshold)."""
        ...


@dataclass(frozen=True, slots=True)
class NormalMargin:
    """Margin ~ Normal(pred_margin, sd): the plain bell curve of 04 § 1."""

    sd: float

    def __post_init__(self) -> None:
        if not self.sd > 0:
            raise ValueError(f"margin sd must be positive, got {self.sd}")

    def prob_above(self, pred_margin: float, threshold: float) -> float:
        return _PHI((pred_margin - threshold) / self.sd)

    def prob_below(self, pred_margin: float, threshold: float) -> float:
        return _PHI((threshold - pred_margin) / self.sd)


@dataclass(frozen=True, slots=True)
class Cover:
    side: Side  # the side the edge favors; home when the edge is exactly 0
    edge: float  # pred_margin + spread_home: > 0 likes home, < 0 likes away
    prob: float  # P(that side covers)


def edge(pred_margin: float, spread_home: float) -> float:
    return pred_margin + spread_home


def cover_probability(pred_margin: float, spread_home: float, dist: MarginDistribution) -> Cover:
    """The side the model likes against `spread_home` and the probability it covers."""
    e = edge(pred_margin, spread_home)
    if e >= 0:
        return Cover("home", e, dist.prob_above(pred_margin, -spread_home))
    return Cover("away", e, dist.prob_below(pred_margin, -spread_home))


def win_probability(pred_margin: float, dist: MarginDistribution) -> float:
    """P(home wins outright)."""
    return dist.prob_above(pred_margin, 0.0)


def payout(price: int = -110) -> float:
    """Units won per unit risked at American odds `price`."""
    if price <= -100:
        return 100 / -price
    if price >= 100:
        return price / 100
    raise ValueError(f"American odds are ≤ -100 or ≥ +100, got {price}")


def break_even(price: int = -110) -> float:
    """The win rate at which a bet at `price` returns nothing: 110/210 at -110."""
    return 1 / (1 + payout(price))


def expected_value(prob: float, price: int = -110) -> float:
    """Units returned per unit risked: `p × payout − (1 − p)`."""
    return prob * payout(price) - (1 - prob)


def blended_margin(pred_margin: float, spread_home: float, k: float) -> float:
    """Shrink toward the market (04 § 4): `k × model + (1 − k) × market`, where the market's
    margin is `−spread_home`. k = 1 is the model alone."""
    return k * pred_margin + (1 - k) * -spread_home
