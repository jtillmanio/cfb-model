"""The engine's light core: sport- and platform-agnostic, numpy, scipy and pydantic only, so the
API can import it (D-004). It never imports `engine.sports` (D-022)."""

from engine.core.inputs import INPUT_IDS, INPUTS, InputDef
from engine.core.interfaces import (
    GameContext,
    GameHistory,
    GamePredictor,
    GameResult,
    Prediction,
    RatingModel,
    Ratings,
)
from engine.core.picks import Pick, pick
from engine.core.probability import (
    Cover,
    MarginDistribution,
    NormalMargin,
    blended_margin,
    break_even,
    cover_probability,
    edge,
    expected_value,
    win_probability,
)
from engine.core.spec import SPEC_SCHEMA_VERSION, ModelSpec, PickRules, UnresolvedSettingError

__all__ = [
    "INPUTS",
    "INPUT_IDS",
    "SPEC_SCHEMA_VERSION",
    "Cover",
    "GameContext",
    "GameHistory",
    "GamePredictor",
    "GameResult",
    "InputDef",
    "MarginDistribution",
    "ModelSpec",
    "NormalMargin",
    "Pick",
    "PickRules",
    "Prediction",
    "RatingModel",
    "Ratings",
    "UnresolvedSettingError",
    "blended_margin",
    "break_even",
    "cover_probability",
    "edge",
    "expected_value",
    "pick",
    "win_probability",
]
