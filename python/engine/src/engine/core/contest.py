"""Contest mode's ranking (docs/04-model.md § 4 › Contest mode; TASK-071, D-174).

A pick'em contest takes a fixed number of picks a week at its own lines, with no vig, so the slate
is ranked by the probability each game's side covers the contest's line, and the model's picks
are the top `picks_per_period`.

- **Games the model covers** (CFB) are ranked on the displayed cover probability against the
  contest line (`core.picks.displayed_prob`, D-143); the caller computes it as `/slate` does.
- **Games it doesn't** (NFL until Phase 8, "no model yet") are ranked on the contest line's gap to
  the market's: `market_gap` treats the market's line as the expected margin and prices the
  contest line on a normal curve at `NFL_MARGIN_SD`, so the probability is Φ(gap / 13.5). It is
  an approximation: NFL margins cluster on 3 and 7, which a normal curve ignores.
- **Order:** cover probability, highest first; ties by edge (0 for a game with no model, as the
  design's `rank`), then kickoff, then game. A locked game (kicked off) leaves the open ranking
  until every game is locked (D-095); then the whole slate is ranked as it stood.
- **Top N:** the first `picks_per_period` games with a model, since the model's contest picks are
  CFB only (D-170) and `contest_results` grades exactly those. **Next best** is the first open
  game ranked below the Nth.
"""

from __future__ import annotations

from collections.abc import Hashable, Sequence
from dataclasses import dataclass
from datetime import datetime

from engine.core.probability import MarginDistribution, NormalMargin, Side, cover_probability

__all__ = ["NFL_MARGIN_SD", "MarketGap", "RankRow", "Ranked", "market_gap", "rank"]

# The spread of NFL margins around the market's line, in points: the σ that turns the design's
# gaps into its "~54%" (1.5 points), "~53%" (1) and "~51%" (0.5).
NFL_MARGIN_SD = 13.5


@dataclass(frozen=True, slots=True)
class MarketGap:
    points: float  # |contest − market| on the home line; 0 when they agree
    side: Side | None  # the side the contest's line gives more than the market does
    prob: float  # P(that side covers the contest line) with the market's line as the median


def market_gap(
    contest_spread_home: float,
    market_spread_home: float,
    dist: MarginDistribution | None = None,
) -> MarketGap:
    """The contest line against the market's: with the market's line as the expected margin
    (−market_spread_home), the side the contest line favours and how often it covers it."""
    gap = contest_spread_home - market_spread_home
    if gap == 0:
        return MarketGap(0.0, None, 0.5)
    cover = cover_probability(
        -market_spread_home, contest_spread_home, dist or NormalMargin(NFL_MARGIN_SD)
    )
    return MarketGap(abs(gap), cover.side, cover.prob)


@dataclass(frozen=True, slots=True)
class RankRow:
    key: Hashable  # the caller's id for the game
    prob: float  # the cover probability it ranks on
    edge: float | None  # points; None for a game with no model (ranks as 0 on a tie)
    has_model: bool  # may be one of the model's top N
    locked: bool  # at or past its cutoff
    cutoff: datetime  # kickoff, or the end of a TBA game's date


@dataclass(frozen=True, slots=True)
class Ranked:
    key: Hashable
    rank: int  # 1 = best: in the open ranking, or for a locked game where it stood before kickoff
    locked: bool
    top_n: bool
    next_best: bool


def _order(rows: Sequence[RankRow]) -> list[RankRow]:
    return sorted(rows, key=lambda r: (-r.prob, -abs(r.edge or 0.0), r.cutoff, str(r.key)))


def rank(rows: Sequence[RankRow], picks_per_period: int) -> list[Ranked]:
    """Every row once: the open games in rank order, then the locked ones by where they stood.
    Once every game is locked, the whole slate is the ranking and its top N stand."""
    everything = _order(rows)
    open_rows = [r for r in everything if not r.locked]
    all_locked = not open_rows
    ranking = everything if all_locked else open_rows

    top: set[Hashable] = set()
    last = -1
    for i, r in enumerate(ranking):
        if len(top) == picks_per_period:
            break
        if r.has_model:
            top.add(r.key)
            last = i
    next_key = None
    if not all_locked and len(top) == picks_per_period and last + 1 < len(ranking):
        next_key = ranking[last + 1].key

    standing = {r.key: i + 1 for i, r in enumerate(everything)}
    out = [
        Ranked(r.key, i + 1, r.locked, r.key in top, r.key == next_key)
        for i, r in enumerate(ranking)
    ]
    if not all_locked:
        out += [Ranked(r.key, standing[r.key], True, False, False) for r in everything if r.locked]
    return out
