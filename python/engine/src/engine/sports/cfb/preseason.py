"""College football's preseason inputs for Rung 2's prior (TASK-037; docs/04-model.md § 2
Preseason priors, § 9.2, D-119).

Each source is a staged season table: which of its seasons season Y's prior reads, how they
become one number per team, and when a value is **assumed** to have been published. CFBD gives
these values no publication date, and the backfill pulled them after each season (D-121), so the
lake can't prove when they were known; the backtest asserts against these assumptions instead
(hard rule 4), and the decision row records them.

- **Returning production** for Y: CFBD's `percentPPA`, the share of last season's offensive PPA
  that returns, computed from last season's stats and Y's roster. Assumed published July 1 of Y,
  after the spring transfer window. It's clipped to [0, 1]: a team whose total PPA last season
  was near zero or negative gets a ratio outside it (32 of 1,691 staged rows) that means
  nothing as a share.
- **Talent** of season S: the 247 composite of S's roster, which CFBD can't date and may reflect
  the season itself, so it's assumed published only after S, on February 1 of S + 1. Season Y
  therefore reads Y − 1's talent; the four recruiting classes cover the incoming freshmen. CFBD
  sends 0 for a team it has no composite for (Air Force, Army and Navy in 2022-2024): that's
  missing, not a value, here and in Postgres.
- **Recruiting**: the class signed for season S, assumed published February 15 of S (after
  National Signing Day). Season Y reads the mean `points` of classes Y − 3 to Y, those the team
  has.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass(frozen=True, slots=True)
class Source:
    table: str  # the staged table
    column: str  # its value column
    seasons: Callable[[int], tuple[int, ...]]  # season Y -> the value seasons Y's prior reads
    published: Callable[[int], datetime]  # a value's season -> when it's assumed published
    combine: Callable[[Sequence[float]], float]  # a team's values for Y -> one number
    # Whether a staged value is a real one; one that isn't counts as missing.
    usable: Callable[[float], bool] = lambda _value: True


def _mean(values: Sequence[float]) -> float:
    return sum(values) / len(values)


def _clipped(values: Sequence[float]) -> float:
    return min(1.0, max(0.0, values[0]))


SOURCES: dict[str, Source] = {
    "returning_production": Source(
        "returning_production",
        "percent_ppa",
        lambda y: (y,),
        lambda s: datetime(s, 7, 1, tzinfo=UTC),
        _clipped,
    ),
    "talent": Source(
        "talent",
        "talent",
        lambda y: (y - 1,),
        lambda s: datetime(s + 1, 2, 1, tzinfo=UTC),
        lambda values: values[0],
        lambda value: value > 0,  # CFBD sends 0 for a team it has no composite for
    ),
    "recruiting": Source(
        "recruiting",
        "points",
        lambda y: tuple(range(y - 3, y + 1)),
        lambda s: datetime(s, 2, 15, tzinfo=UTC),
        _mean,
    ),
}
