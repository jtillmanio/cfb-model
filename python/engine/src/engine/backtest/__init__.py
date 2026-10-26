"""`engine backtest`: the walk-forward, rolling-origin harness (`harness`), the holdout lock
(`holdout`), and the models it can run.

`MODELS` maps a name to a factory that builds a model from a resolved `ModelSpec`. A run uses the
spec's `base` unless `--model` names another entry: Rung 1 registers `power` (TASK-033), the
baselines theirs (TASK-032), and `stub` is the harness's smoke-test model until then.
"""

from __future__ import annotations

from engine.backtest.harness import ModelFactory
from engine.backtest.stub import MeanMargin

MODELS: dict[str, ModelFactory] = {
    "stub": MeanMargin,
}
