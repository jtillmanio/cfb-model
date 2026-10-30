"""Tuning a spec's pick rules on earlier seasons (TASK-039; docs/04-model.md § 4, § 9.1, § 9.2,
D-055).

Pick rules don't change a prediction, only which games become picks and the probability shown,
so they're tuned after the model's settings, on the tuning seasons' rows those settings produce
(`harness.run` calls `tune` with the model's choices and the same guarded `evaluate`, so a
season's rules never read its own games).

- **`market_shrinkage_k`** is the candidate with the lowest cover Brier score on every eligible
  tuning-season game (`metrics.cover_brier`, pushes left out); a tie goes to the larger k. On ATS
  it couldn't be told apart from `min_edge_pts`: the blended edge is `k × edge`, so "blended ≥ 3
  at k = 0.5" picks the games "edge ≥ 6 at k = 1" does. What k does change is how honest the
  displayed cover probability is.
- **The other pick fields** (`min_edge_pts`, `min_prob`, a tier) take the grid combination with
  the best ATS win % against the close at the chosen k, graded as the report grades
  (`metrics.grade_rows`, D-132), among those with at least `FLOOR` graded picks (pushes left out)
  pooled over the tuning seasons; a tie goes to more picks, then to grid order. With no
  candidate at `FLOOR`, the one with the most picks is chosen and flagged. A tier never changes
  which games are picked, so a tuned tier takes the first valid candidate in grid order.
"""

from __future__ import annotations

import itertools
import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from engine.backtest import metrics
from engine.core.spec import ModelSpec

PICKS = "picks."
SHRINKAGE = "picks.market_shrinkage_k"
FLOOR = 200  # graded picks a threshold's ATS must rest on (04 § 9.2)

Choices = Mapping[str, float]
Evaluate = Callable[[Choices, int], Sequence[Mapping[str, Any]]]


@dataclass(frozen=True, slots=True)
class PickTuning:
    choices: dict[str, float]  # tuned pick setting path -> its chosen candidate
    picks: int  # graded picks (W + L) on the tuning seasons under the chosen rules
    floor_met: bool  # False: no candidate reached FLOOR, so the one with the most picks


PickTuner = Callable[[ModelSpec, Choices, Sequence[int], Evaluate], PickTuning | None]


def is_pick_setting(path: str) -> bool:
    return path.startswith(PICKS)


def tune(
    spec: ModelSpec, model: Choices, tuning: Sequence[int], evaluate: Evaluate
) -> PickTuning | None:
    """The tuned pick settings for a season whose model settings are `model`, chosen on the
    `tuning` seasons; None when the spec tunes no pick setting."""
    tunables = {p: c for p, c in spec.tunables().items() if is_pick_setting(p)}
    if not tunables:
        return None
    rows = [r for season in tuning for r in evaluate(model, season)]

    def grade(candidate: Choices) -> list[metrics.Graded]:
        choices = {**model, **candidate}
        return metrics.grade_rows(rows, spec, {season: choices for season in tuning})

    rest = {p: c for p, c in tunables.items() if p != SHRINKAGE}
    chosen: dict[str, float] = {}
    if SHRINKAGE in tunables:
        first = {p: c[0] for p, c in rest.items()}

        def brier(k: float) -> float:
            score = metrics.cover_brier(grade({**first, SHRINKAGE: k}))
            return math.inf if score is None else score

        chosen[SHRINKAGE] = min(tunables[SHRINKAGE], key=lambda k: (brier(k), -k))

    best: tuple[tuple[float, int], dict[str, float], int] | None = None
    most: tuple[int, dict[str, float]] | None = None
    for values in itertools.product(*rest.values()):
        candidate = {**chosen, **dict(zip(rest, values, strict=True))}
        try:
            record = metrics.Record.of(g.result for g in grade(candidate) if g.pick is not None)
        except ValidationError:
            continue  # tiers out of order (A ≥ B ≥ C)
        if most is None or record.graded > most[0]:
            most = (record.graded, candidate)
        if record.graded >= FLOOR and record.win_pct is not None:
            score = (record.win_pct, record.graded)
            if best is None or score > best[0]:
                best = (score, candidate, record.graded)
    if most is None:
        raise ValueError(f"no combination of {', '.join(rest)} is a valid set of pick rules")
    if best is not None:
        return PickTuning(best[1], best[2], True)
    return PickTuning(most[1], most[0], False)
