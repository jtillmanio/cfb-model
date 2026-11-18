"""The engine's light core: sport- and platform-agnostic, pydantic and the standard library only,
so the API can import it (D-004, D-158). It never imports `engine.sports` (D-022)."""

from engine.core.contest import NFL_MARGIN_SD, MarketGap, Ranked, RankRow, market_gap, rank
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
from engine.core.picks import Pick, displayed_prob, pick, pick_game
from engine.core.probability import (
    Cover,
    EmpiricalMargin,
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
    "NFL_MARGIN_SD",
    "INPUT_IDS",
    "SPEC_SCHEMA_VERSION",
    "Cover",
    "EmpiricalMargin",
    "GameContext",
    "GameHistory",
    "GamePredictor",
    "GameResult",
    "InputDef",
    "MarginDistribution",
    "MarketGap",
    "ModelSpec",
    "NormalMargin",
    "Pick",
    "PickRules",
    "Prediction",
    "RankRow",
    "Ranked",
    "RatingModel",
    "Ratings",
    "UnresolvedSettingError",
    "blended_margin",
    "break_even",
    "cover_probability",
    "displayed_prob",
    "edge",
    "expected_value",
    "market_gap",
    "pick",
    "pick_game",
    "rank",
    "win_probability",
]
