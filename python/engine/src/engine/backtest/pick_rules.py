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
- **`display_shrinkage_k`** (TASK-042) is chosen last, at the season's other pick rules: the
  candidate with the lowest cover Brier, a tie to the larger. It shrinks only the probability
  shown, so it never changes a pick; k and the thresholds above are chosen with it at 1, as if
  the field weren't there.
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
DISPLAY = "picks.display_shrinkage_k"
FLOOR = 200  # graded picks a threshold's ATS must rest on (04 § 9.2)

Choices = Mapping[str, float]
Evaluate = Callable[[Choices, int], Sequence[Mapping[str, Any]]]


@dataclass(frozen=True, slots=True)
class PickTuning:
    choices: dict[str, float]  # tuned pick setting path -> its chosen candidate
    picks: int  # graded picks (W + L) on the tuning seasons under the chosen rules
    floor_met: bool  # False: no candidate reached FLOOR, so the one with the most picks


PickTuner = Callable[[ModelSpec, Choices, Sequence[int], Evaluate], PickTuning | None]


class NoValidRulesError(ValueError):
    """No combination of the tuned pick candidates is a valid set of pick rules."""


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
    unshown = _without_display(spec)

    def grade(candidate: Choices, graded: ModelSpec = unshown) -> list[metrics.Graded]:
        choices = {**model, **candidate}
        return metrics.grade_rows(rows, graded, {season: choices for season in tuning})

    def lowest_brier(path: str, at: Choices, graded: ModelSpec = unshown) -> float:
        """The candidate of `path` with the lowest cover Brier at `at`, a tie to the larger."""

        def brier(k: float) -> float:
            score = metrics.cover_brier(grade({**at, path: k}, graded))
            return math.inf if score is None else score

        return min(tunables[path], key=lambda k: (brier(k), -k))

    rest = {p: c for p, c in tunables.items() if p not in (SHRINKAGE, DISPLAY)}
    valid = [c for c in _combinations(rest) if _valid(spec, {**model, **c})]
    if not valid:
        raise NoValidRulesError(f"no combination of {', '.join(rest)} is a valid set of pick rules")
    chosen: dict[str, float] = {}
    if SHRINKAGE in tunables:
        # The cover Brier doesn't depend on the other pick fields.
        chosen[SHRINKAGE] = lowest_brier(SHRINKAGE, valid[0])

    best: tuple[tuple[float, int], dict[str, float], int] | None = None
    most: tuple[int, dict[str, float]] | None = None
    for combination in valid:
        candidate = {**chosen, **combination}
        record = metrics.Record.of(g.result for g in grade(candidate) if g.pick is not None)
        if most is None or record.graded > most[0]:
            most = (record.graded, candidate)
        if record.graded >= FLOOR and record.win_pct is not None:
            score = (record.win_pct, record.graded)
            if best is None or score > best[0]:
                best = (score, candidate, record.graded)
    assert most is not None
    if best is not None:
        choices, picks, floor_met = best[1], best[2], True
    else:
        choices, picks, floor_met = most[1], most[0], False
    if DISPLAY in tunables:
        choices = {**choices, DISPLAY: lowest_brier(DISPLAY, choices, spec)}
    return PickTuning(choices, picks, floor_met)


def _without_display(spec: ModelSpec) -> ModelSpec:
    """The spec with the probability shown left as the blended margin's own (display shrinkage
    1), for choosing the rules that pick: none of them may depend on what's displayed."""
    data = spec.model_dump()
    data["picks"]["display_shrinkage_k"] = 1.0
    return ModelSpec.model_validate(data)


def _combinations(rest: Mapping[str, Sequence[float]]) -> list[dict[str, float]]:
    """Every combination of the candidates, in grid order (one empty one with none)."""
    return [dict(zip(rest, values, strict=True)) for values in itertools.product(*rest.values())]


def _valid(spec: ModelSpec, choices: Choices) -> bool:
    """Whether the choices make a valid spec: tiers out of order (A ≥ B ≥ C) don't."""
    try:
        spec.resolve(choices)
    except ValidationError:
        return False
    return True
