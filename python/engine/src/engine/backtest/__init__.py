"""`engine backtest`: the walk-forward, rolling-origin harness (`harness`), the holdout lock
(`holdout`), and the models it can run.

`MODELS` maps a name to a factory that builds a model from a resolved `ModelSpec`. A run uses the
spec's `base` unless `--model` names another entry: Rung 1 registers `power` (TASK-033), the
Rung 0 baselines (`baselines`, TASK-032) are registered below, and `stub` is the harness's
smoke-test model.
"""

from __future__ import annotations

from engine.backtest.baselines import BenchmarkRating, ClosingLine, HomeField, LastSeason
from engine.backtest.harness import BacktestModel, ModelFactory, RefusedError
from engine.backtest.stub import MeanMargin
from engine.core.spec import ModelSpec


def _last_season(spec: ModelSpec) -> BacktestModel:
    """The model under test, carried over from the season before (D-133): it wraps whatever is
    registered under the spec's `base`, looked up when the run starts."""
    inner = MODELS.get(spec.base)
    if inner is None:
        raise RefusedError(
            f"last_season carries over the final ratings of the spec's own model, and none is "
            f"registered as {spec.base!r} yet (Rung 1's power model is TASK-033)"
        )
    return LastSeason(inner(spec))  # type: ignore[return-value]


MODELS: dict[str, ModelFactory] = {
    "stub": MeanMargin,
    "home_field": lambda spec: HomeField(),  # type: ignore[dict-item,return-value]
    "last_season": _last_season,
    "closing_line": lambda spec: ClosingLine(),  # type: ignore[return-value]
    "sp": lambda spec: BenchmarkRating("sp"),  # type: ignore[return-value]
    "fpi": lambda spec: BenchmarkRating("fpi"),  # type: ignore[return-value]
}
