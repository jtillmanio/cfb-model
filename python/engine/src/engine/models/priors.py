"""Fitted preseason priors and the fitted decay curve (TASK-037; docs/04-model.md § 2 Preseason
priors, § 9.2, D-130).

**The prior.** For every rating (each stat's offense and defense) a team's preseason guess is

    prior − anchor = a·(last season's final − anchor) + b·RP + c·talent + d·recruiting

the anchor being its tier's level last season under `shrink_toward: tier`, zero otherwise
(D-137). Each extra component is centred on its anchor group's mean that season, so a team
missing one counts as that group's average. The weights are fit by least squares, one small
regression per rating, on target seasons before the one predicted: the target is each team's
rating from that season's games alone (no prior blended in) after its last game, "what the team
turned out to be". **Concept: regression to the mean.** `a` below 1 pulls last season's extremes
back toward the anchor; the other weights say how much roster turnover and talent move the
guess.

**The decay.** `w(N) = k / (k + N − 1)`, N being 1 + this season's weeks played: the prior
counts as `k` weeks of games, so it's 1 in week 1 and fades as games pile up, never rising and
never leaving [0, 1]. `k` is fit with the margin model on earlier seasons (`efficiency.py`).
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import numpy as np

from engine.transform.features import PointInTimeError

# The decay before any earlier season had a prior to fit it on (only the second season in the
# lake, 2015, a tuning season): the prior counts as one week, so w(9) ≈ 0.11 (04 § 2's "about
# 0.1 by weeks 8-10"). As `DEFAULT_SD` is σ before there's a season to measure it on.
DEFAULT_PRIOR_WEEKS = 1.0
# The candidates for k: log-spaced from 0.1 to 10 weeks, 20 a decade.
DECAY_GRID = tuple(0.1 * 10 ** (i / 20) for i in range(41))


def decay_weight(k: float, weeks_played: int) -> float:
    """w(N) for N = weeks_played + 1."""
    return k / (k + weeks_played)


@dataclass(frozen=True, slots=True)
class PriorRow:
    """One team-season for the prior fit: its ratings relative to its anchor."""

    season: int  # the target season
    team: int
    last: np.ndarray  # last season's final ratings minus the anchor
    components: np.ndarray  # each extra component, centred (0 where missing)
    target: np.ndarray  # the season's in-season ratings after its last game, minus the anchor


@dataclass(frozen=True, slots=True)
class PriorWeights:
    keep: np.ndarray  # a, one per rating
    components: np.ndarray  # (components, ratings): b, c, d ...
    rows: int


def fit_prior(rows: Sequence[PriorRow], season: int) -> PriorWeights:
    """The prior's weights for `season`, by least squares on target seasons before it only."""
    late = [r for r in rows if r.season >= season]
    if late:
        shown = ", ".join(f"{r.team} ({r.season})" for r in late[:5])
        raise PointInTimeError(
            f"the prior for {season} was given {len(late)} team-season(s) of {season} or "
            f"later: its weights are fit on earlier seasons only (04 § 9.2): {shown}"
        )
    if not rows:
        raise ValueError(f"no team-season before {season} to fit the prior on")
    last = np.array([r.last for r in rows])
    components = np.array([r.components for r in rows]).reshape(len(rows), -1)
    target = np.array([r.target for r in rows])
    keep = np.empty(last.shape[1])
    weights = np.empty((components.shape[1], last.shape[1]))
    for j in range(last.shape[1]):
        x = np.column_stack([last[:, j], components])
        # Minimum norm: a component no team had yet (talent before 2015) gets weight 0.
        coef = np.linalg.lstsq(x, target[:, j], rcond=None)[0]
        keep[j], weights[:, j] = coef[0], coef[1:]
    return PriorWeights(keep, weights, len(rows))


def centred(values: Mapping[int, float], groups: Mapping[int, str]) -> dict[int, float]:
    """Each team's value minus its group's mean over the group's teams that have one; a team
    in `groups` with no value gets 0, its group's average."""
    sums: dict[str, list[float]] = {}
    for team, group in groups.items():
        if team in values:
            sums.setdefault(group, []).append(values[team])
    means = {g: math.fsum(vs) / len(vs) for g, vs in sums.items()}
    return {
        team: values[team] - means[group] if team in values else 0.0
        for team, group in groups.items()
    }
