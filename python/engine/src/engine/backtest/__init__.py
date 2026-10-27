"""`engine backtest`: the walk-forward, rolling-origin harness (`harness`), the holdout lock
(`holdout`), and the models it can run.

`MODELS` maps a name to a factory that builds a model from a resolved `ModelSpec`. A run uses the
spec's `base` unless `--model` names another entry: Rung 1 is `power` (`engine.models.power`,
with college football's rules, TASK-033), Rung 2 is `efficiency` (`engine.models.efficiency`,
TASK-036), the Rung 0 baselines (`baselines`, TASK-032) are registered below, and `stub` is the
harness's smoke-test model.

`efficiency` hands back the same model for the same resolved spec: the harness builds one per
(settings, season), and each would otherwise re-rate every earlier season to fit its margin
model. The model is a pure function of its inputs and spec, and forgets what it learned when
it's given new inputs, so sharing it changes no number.

`matchup_tier` labels a results row by its teams' tiers that season (04 § 9.4 › Breakdowns), for
the report's conference-tier breakdown: college football's map, from the row's conferences.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from engine.backtest.baselines import (
    BenchmarkRating,
    ClosingLine,
    FittedHomeField,
    LastSeason,
)
from engine.backtest.harness import BacktestModel, ModelFactory, RefusedError, spec_hash
from engine.backtest.stub import MeanMargin
from engine.core.spec import ModelSpec
from engine.models.efficiency import EfficiencyRatings
from engine.models.power import PowerRatings, UnsupportedSpecError
from engine.sports.cfb.teams import (
    EFFICIENCY_RULES,
    RULES,
    TIERS,
    UnmappedConferenceError,
    tier_of,
)


def _power(spec: ModelSpec) -> BacktestModel:
    try:
        return PowerRatings(spec, RULES)  # type: ignore[return-value]
    except UnsupportedSpecError as e:
        raise RefusedError(str(e)) from e


_EFFICIENCY: dict[str, EfficiencyRatings] = {}


def _efficiency(spec: ModelSpec) -> BacktestModel:
    key = spec_hash(spec)
    if key not in _EFFICIENCY:
        try:
            _EFFICIENCY[key] = EfficiencyRatings(spec, EFFICIENCY_RULES)
        except UnsupportedSpecError as e:
            raise RefusedError(str(e)) from e
    return _EFFICIENCY[key]  # type: ignore[return-value]


TIER_MATCHUPS = tuple(f"{a} vs {b}" for i, a in enumerate(TIERS) for b in TIERS[i:])
UNMAPPED = "Unmapped"


def matchup_tier(row: Mapping[str, Any]) -> str:
    """ "Power 4 vs G5" and so on: each side's tier that season, the higher tier first. The
    backtest scores FBS-vs-FBS games only; a conference the map doesn't know (or a row written
    before results carried conferences) is "Unmapped"."""
    season = row["season"]
    try:
        tiers = sorted(
            (
                tier_of(season, int(row[f"{side}_source_id"]), row.get(f"{side}_group"), "fbs")
                for side in ("home", "away")
            ),
            key=TIERS.index,
        )
    except UnmappedConferenceError:
        return UNMAPPED
    return " vs ".join(tiers)


def _inner(spec: ModelSpec, name: str) -> BacktestModel:
    """The model under test, registered under the spec's `base`, looked up when the run starts."""
    inner = MODELS.get(spec.base)
    if inner is None:
        raise RefusedError(
            f"{name} wraps the spec's own model, and none is registered as {spec.base!r}"
        )
    return inner(spec)


def _last_season(spec: ModelSpec) -> BacktestModel:
    """The model under test, carried over from the season before (D-133)."""
    return LastSeason(_inner(spec, "last_season"))  # type: ignore[return-value]


def _home_field(spec: ModelSpec) -> BacktestModel:
    """The model under test's fitted home-field edge alone (04 § 9.6; TASK-033 amends D-133)."""
    return FittedHomeField(_inner(spec, "home_field"))  # type: ignore[return-value]


MODELS: dict[str, ModelFactory] = {
    "stub": MeanMargin,
    "power": _power,
    "efficiency": _efficiency,
    "home_field": _home_field,
    "last_season": _last_season,
    "closing_line": lambda spec: ClosingLine(),  # type: ignore[return-value]
    "sp": lambda spec: BenchmarkRating("sp"),  # type: ignore[return-value]
    "fpi": lambda spec: BenchmarkRating("fpi"),  # type: ignore[return-value]
}
