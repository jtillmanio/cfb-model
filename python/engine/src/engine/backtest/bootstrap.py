"""What "beats" means (TASK-031; docs/04-model.md § 9.5, D-091): a week-level paired bootstrap.

Two models are scored on the same games and differenced game by game. Whole weeks are then
resampled with replacement `RESAMPLES` times, recomputing the statistic each time; A beats B when
the middle 95% of those values lies entirely on A's side of zero. Weeks, not games, are the unit
because games in one week share news, weather and line moves, so resampling single games would
overstate how sure we are.

The seed is fixed, so the same inputs always give the same interval.
"""

from __future__ import annotations

import random
from collections import defaultdict
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from engine.backtest.metrics import Result

SEED = 20261007  # the day the evaluation protocol was fixed (04 § 9)
RESAMPLES = 10_000
LEVEL = 0.95

WeekKey = tuple[int, str, int]  # (season, season type, week)


@dataclass(frozen=True, slots=True)
class Interval:
    estimate: float  # the statistic on every week, once
    low: float
    high: float
    resamples: int
    better: Literal["lower", "higher"]  # which side of zero favors A

    @property
    def beats(self) -> bool:
        """The whole 95% interval is on A's side of zero."""
        return self.high < 0 if self.better == "lower" else self.low > 0


def _quantile(ordered: Sequence[float], q: float) -> float:
    """Linear interpolation between the closest ranks."""
    at = q * (len(ordered) - 1)
    below = int(at)
    above = min(below + 1, len(ordered) - 1)
    return ordered[below] + (ordered[above] - ordered[below]) * (at - below)


def resample(
    weeks: Mapping[WeekKey, Sequence[float]],
    statistic: Callable[[Sequence[float]], float | None],
    better: Literal["lower", "higher"],
    *,
    resamples: int = RESAMPLES,
    seed: int = SEED,
) -> Interval:
    """`weeks` maps each week to its sums (the same components for every week); `statistic`
    turns summed components into the number compared, or None where it's undefined (that
    resample is dropped)."""
    keys = sorted(weeks)
    if not keys:
        raise ValueError("no weeks to resample")
    columns = list(zip(*(weeks[k] for k in keys), strict=True))
    estimate = statistic([sum(c) for c in columns])
    if estimate is None:
        raise ValueError("the statistic is undefined on the full sample")
    rng = random.Random(seed)
    population = range(len(keys))
    values: list[float] = []
    for _ in range(resamples):
        drawn = rng.choices(population, k=len(keys))
        value = statistic([sum(c[i] for i in drawn) for c in columns])
        if value is not None:
            values.append(value)
    values.sort()
    tail = (1 - LEVEL) / 2
    return Interval(
        estimate, _quantile(values, tail), _quantile(values, 1 - tail), len(values), better
    )


def mean_difference(
    diffs: Iterable[tuple[WeekKey, float]], *, seed: int = SEED, resamples: int = RESAMPLES
) -> Interval:
    """The mean of per-game differences (A − B), weeks resampled; below zero favors A."""
    weeks: dict[WeekKey, list[float]] = defaultdict(lambda: [0.0, 0.0])
    for week, diff in diffs:
        weeks[week][0] += diff
        weeks[week][1] += 1
    return resample(weeks, lambda s: s[0] / s[1], "lower", seed=seed, resamples=resamples)


def _week(row: Mapping[str, Any]) -> WeekKey:
    return (row["season"], row["season_type"], row["week"])


def compare(
    a: Sequence[Mapping[str, Any]],
    b: Sequence[Mapping[str, Any]],
    *,
    seed: int = SEED,
    resamples: int = RESAMPLES,
) -> Interval:
    """Run A's absolute margin error minus run B's, paired by game: A beats B on MAE when the
    interval is entirely below zero (04 § 9.6's bar for each phase)."""
    by_game = {r["game_source_id"]: r for r in b}
    if len(by_game) != len(a) or any(r["game_source_id"] not in by_game for r in a):
        raise ValueError("compare needs two runs scored on the same games")
    diffs = []
    for r in a:
        other = by_game[r["game_source_id"]]
        diff = abs(r["pred_margin"] - r["margin"]) - abs(other["pred_margin"] - other["margin"])
        diffs.append((_week(r), diff))
    return mean_difference(diffs, seed=seed, resamples=resamples)


def ats_difference(
    outcomes: Iterable[tuple[WeekKey, Result | None, Result | None]],
    *,
    seed: int = SEED,
    resamples: int = RESAMPLES,
) -> Interval:
    """A's ATS win % minus B's, on each game's result for each model's pick (None: no pick;
    pushes are out of win %); above zero favors A (04 § 9.5)."""
    weeks: dict[WeekKey, list[float]] = defaultdict(lambda: [0.0, 0.0, 0.0, 0.0])
    for week, mine, theirs in outcomes:
        sums = weeks[week]
        for offset, result in ((0, mine), (2, theirs)):
            if result in ("W", "L"):
                sums[offset] += result == "W"
                sums[offset + 1] += 1

    def statistic(s: Sequence[float]) -> float | None:
        if not s[1] or not s[3]:
            return None
        return s[0] / s[1] - s[2] / s[3]

    return resample(weeks, statistic, "higher", seed=seed, resamples=resamples)
