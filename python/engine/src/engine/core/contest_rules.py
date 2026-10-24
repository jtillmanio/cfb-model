"""`ContestRules`: a pick'em contest's format as data, so no screen or job hard-codes one platform
(docs/03-data-model.md › Your data). Splash is the preset, not the design center (TASK-023, D-113).

The preset's push is `zero`, as 03 records it: D-045 scores a push 0 until Splash's rule is
confirmed.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

SportId = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]*$")]


class ContestRules(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    period: Literal["week", "day"]
    sports: tuple[SportId, ...] = Field(min_length=1)
    slate: Literal["all_games", "curated"]
    picks_per_period: int = Field(ge=1)
    picks_exact: bool = True  # False: at most picks_per_period
    lock: Literal["per_game_kickoff", "fixed_time"]
    scoring: Literal["point_per_win", "confidence"]
    push: Literal["zero", "half", "void"]


SPLASH_PRESET = ContestRules(
    period="week",
    sports=("cfb", "nfl"),
    slate="curated",
    picks_per_period=4,
    picks_exact=True,
    lock="per_game_kickoff",
    scoring="point_per_win",
    push="zero",
)
