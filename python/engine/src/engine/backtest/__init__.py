"""`engine backtest`: the walk-forward, rolling-origin harness (`harness`), the holdout lock
(`holdout`), and the models it can run.

`MODELS` maps a name to a factory that builds a model from a resolved `ModelSpec`. A run uses the
spec's `base` unless `--model` names another entry: Rung 1 is `power` (`engine.models.power`,
with college football's rules, TASK-033), the Rung 0 baselines (`baselines`, TASK-032) are
registered below, and `stub` is the harness's smoke-test model.
"""

from __future__ import annotations

from engine.backtest.baselines import (
    BenchmarkRating,
    ClosingLine,
    FittedHomeField,
    LastSeason,
)
from engine.backtest.harness import BacktestModel, ModelFactory, RefusedError
from engine.backtest.stub import MeanMargin
from engine.core.spec import ModelSpec
from engine.models.power import PowerRatings, UnsupportedSpecError
from engine.sports.cfb.teams import RULES


def _power(spec: ModelSpec) -> BacktestModel:
    try:
        return PowerRatings(spec, RULES)  # type: ignore[return-value]
    except UnsupportedSpecError as e:
        raise RefusedError(str(e)) from e


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
    "home_field": _home_field,
    "last_season": _last_season,
    "closing_line": lambda spec: ClosingLine(),  # type: ignore[return-value]
    "sp": lambda spec: BenchmarkRating("sp"),  # type: ignore[return-value]
    "fpi": lambda spec: BenchmarkRating("fpi"),  # type: ignore[return-value]
}
