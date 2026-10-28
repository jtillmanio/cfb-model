"""From a predicted margin and a line to an edge, a cover probability and an expected value
(docs/04-model.md § 1, § 3, § 4). Pure math: the API runs it for hypothetical matchups.

Signs follow CLAUDE.md: `margin = home − away`, `spread_home` is negative when home is favored,
and home covers when `margin + spread_home > 0`.

Every probability goes through a `MarginDistribution`, so the empirical distribution (D-053,
TASK-038) and a per-game σ (M19.2) replace `NormalMargin` without changing a caller. It asks for
`P(margin > t)`, `P(margin < t)` and `P(margin = t)` separately because an empirical distribution
puts mass on whole numbers: on a whole-number line the first two don't sum to 1, and the rest is
the push. A displayed cover or win probability leaves the push out, `P(cover | no push)`: that's
what an ATS win % and the calibration bins measure, since a push is refunded.

**The empirical distribution** (04 § 3). Margins come in whole numbers, and they pile up on 3
and 7 because scores come in 3s and 7s. `EmpiricalMargin` puts a probability on each whole-number
margin: the normal curve's density there, times a key-number weight for the margin's size,
renormalized. A weight is how much more often earlier seasons' games ended at that margin, either
way, than a plain normal curve around their predictions expected, shrunk toward 1 as if
`KEY_PSEUDO_GAMES` more games had agreed with the curve.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from functools import lru_cache
from statistics import NormalDist
from typing import Literal, Protocol

Side = Literal["home", "away"]

_PHI = NormalDist().cdf  # Φ, the standard normal CDF

KEY_RANGE = 50  # margins up to this size get their own weight; larger ones weigh 1
KEY_PSEUDO_GAMES = 25.0
_TAILS = 10.0  # σ either side of the prediction the pmf spans: beyond is under 1e-22


class MarginDistribution(Protocol):
    """How actual margins scatter around a predicted one."""

    def prob_above(self, pred_margin: float, threshold: float) -> float:
        """P(margin > threshold)."""
        ...

    def prob_below(self, pred_margin: float, threshold: float) -> float:
        """P(margin < threshold)."""
        ...

    def prob_at(self, pred_margin: float, threshold: float) -> float:
        """P(margin = threshold): the push on a line at `threshold`."""
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

    def prob_at(self, pred_margin: float, threshold: float) -> float:
        return 0.0


def _weight_key(size: int) -> str:
    return f"margin_weight_{size}"


@dataclass(frozen=True, slots=True)
class EmpiricalMargin:
    """Margin on whole numbers: P(m) ∝ φ((m − pred_margin) / sd) × weight(|m|)."""

    sd: float
    weights: tuple[float, ...]  # weight of |margin| = 0 … KEY_RANGE; 1 beyond

    def __post_init__(self) -> None:
        if not self.sd > 0:
            raise ValueError(f"margin sd must be positive, got {self.sd}")
        if len(self.weights) != KEY_RANGE + 1:
            raise ValueError(f"{KEY_RANGE + 1} key-number weights, got {len(self.weights)}")
        if not all(math.isfinite(w) and w >= 0 for w in self.weights):
            raise ValueError("key-number weights must be finite and not negative")

    @classmethod
    def fit(
        cls, games: Iterable[tuple[int, float, float]], season: int, sd: float
    ) -> EmpiricalMargin:
        """The weights for `season` from earlier seasons' games, each (season, predicted
        margin, actual margin), around predictions at the sd the season predicts with."""
        import numpy as np

        rows = list(games)
        late = sorted({s for s, _, _ in rows if s >= season})
        if late:
            raise ValueError(
                f"the margin distribution for {season} was given games of "
                f"{', '.join(map(str, late))}: it's fit on earlier seasons only (04 § 9.2)"
            )
        if not rows:
            raise ValueError(f"no game before {season} to fit the margin distribution on")
        pred = np.array([p for _, p, _ in rows], dtype=float)
        actual = np.array([m for _, _, m in rows], dtype=float)
        if not np.array_equal(actual, np.round(actual)):
            raise ValueError("actual margins must be whole numbers")
        low = math.floor(float(pred.min()) - _TAILS * sd)
        high = math.ceil(float(pred.max()) + _TAILS * sd)
        margins = np.arange(low, high + 1)
        density = np.exp(-0.5 * ((margins[None, :] - pred[:, None]) / sd) ** 2)
        density /= density.sum(axis=1, keepdims=True)
        sizes = np.minimum(np.abs(margins), KEY_RANGE + 1)
        expected = np.bincount(sizes, weights=density.sum(axis=0), minlength=KEY_RANGE + 2)
        seen = np.minimum(np.abs(actual).astype(int), KEY_RANGE + 1)
        observed = np.bincount(seen, minlength=KEY_RANGE + 2)
        weights = (observed + KEY_PSEUDO_GAMES) / (expected + KEY_PSEUDO_GAMES)
        return cls(sd, tuple(float(w) for w in weights[: KEY_RANGE + 1]))

    @classmethod
    def from_params(cls, params: Mapping[str, float]) -> EmpiricalMargin | None:
        """The distribution a run's `fitted_params` hold, or None if they hold none."""
        if _weight_key(0) not in params:
            return None
        weights = tuple(params[_weight_key(n)] for n in range(KEY_RANGE + 1))
        return cls(params["margin_sd"], weights)

    def params(self) -> dict[str, float]:
        """The weights as `fitted_params` entries (the sd is `margin_sd` already)."""
        return {_weight_key(n): w for n, w in enumerate(self.weights)}

    def _sum(self, pred_margin: float, keep: Callable[[int], bool]) -> float:
        low, probs = _pmf(self.sd, self.weights, pred_margin)
        return math.fsum(p for i, p in enumerate(probs) if keep(low + i))

    def prob_above(self, pred_margin: float, threshold: float) -> float:
        return self._sum(pred_margin, lambda m: m > threshold)

    def prob_below(self, pred_margin: float, threshold: float) -> float:
        return self._sum(pred_margin, lambda m: m < threshold)

    def prob_at(self, pred_margin: float, threshold: float) -> float:
        if threshold != math.floor(threshold):
            return 0.0
        low, probs = _pmf(self.sd, self.weights, pred_margin)
        i = int(threshold) - low
        return probs[i] if 0 <= i < len(probs) else 0.0


@lru_cache(maxsize=4096)
def _pmf(
    sd: float, weights: tuple[float, ...], pred_margin: float
) -> tuple[int, tuple[float, ...]]:
    """The first whole-number margin of the prediction ± `_TAILS` σ, and each one's
    probability from there."""
    low = math.floor(pred_margin - _TAILS * sd)
    high = math.ceil(pred_margin + _TAILS * sd)
    raw = [
        math.exp(-0.5 * ((m - pred_margin) / sd) ** 2)
        * (weights[abs(m)] if abs(m) <= KEY_RANGE else 1.0)
        for m in range(low, high + 1)
    ]
    total = math.fsum(raw)
    return low, tuple(r / total for r in raw)


@dataclass(frozen=True, slots=True)
class Cover:
    side: Side  # the side the model likes (see cover_probability); home at an edge of 0
    edge: float  # pred_margin + spread_home: > 0 likes home, < 0 likes away
    prob: float  # P(that side covers | no push)
    push: float = 0.0  # P(push): 0 off a whole number, and always under a normal margin


def edge(pred_margin: float, spread_home: float) -> float:
    return pred_margin + spread_home


def _without_push(prob: float, push: float) -> float:
    """P(… | no push): exactly `prob` when there's no push mass."""
    return prob if push == 0 else prob / (1 - push)


def cover_probability(pred_margin: float, spread_home: float, dist: MarginDistribution) -> Cover:
    """The side the model likes against `spread_home` and the probability it covers, the push
    left out. That's the side the edge favors, unless a key number makes the other side the
    likelier to cover (home by 2 against −2.5, when home by 3 is common): never under a normal
    margin, where the edge's side is always at least 50%."""
    e = edge(pred_margin, spread_home)
    push = dist.prob_at(pred_margin, -spread_home)
    home = _without_push(dist.prob_above(pred_margin, -spread_home), push)
    away = _without_push(dist.prob_below(pred_margin, -spread_home), push)
    side: Side = "home" if e >= 0 else "away"
    if (home if side == "home" else away) < 0.5:
        side = "away" if side == "home" else "home"
    return Cover(side, e, home if side == "home" else away, push)


def win_probability(pred_margin: float, dist: MarginDistribution) -> float:
    """P(home wins outright), a tie left out."""
    return _without_push(dist.prob_above(pred_margin, 0.0), dist.prob_at(pred_margin, 0.0))


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
