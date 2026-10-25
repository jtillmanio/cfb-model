"""`ModelSpec` v1: a model's recipe written as data (docs/04-model.md § 6, D-050). It's stored in
`model_versions.spec`; what a fit learns goes in `model_runs.fitted_params`. Two runs with the
same spec on the same data give the same numbers, and the spec's JSON Schema drives the Lab's
model-builder form, so the form can't offer what the engine doesn't support.

- A weight is `"fit"` (learned) or a fixed number. A setting is a number, or `{"tune": [...]}`:
  candidates the backtest chooses between on earlier seasons (04 § 9.1). `tunables()` lists them
  by dotted path and `resolve()` fixes each to one; a model is built from a resolved spec.
- `base` is the rating family: `power` rates game margins only (Rung 1) and takes no inputs;
  `efficiency` (Rung 2, M4.1) rates the registry inputs it lists.
- `spec_schema_version` travels inside the spec, so a stored spec says which shape it has. A new
  optional field whose default reproduces the old behaviour keeps the version; changing what an
  existing field means bumps it.
- There's no `name`: a version's name lives on `model_versions`, and renaming a model mustn't
  change its spec.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from typing import Annotated, Any, Literal

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    Strict,
    ValidationInfo,
    WithJsonSchema,
    field_validator,
    model_validator,
)

from engine.core.inputs import INPUT_IDS

SPEC_SCHEMA_VERSION = 1

# Strict: "6" and true aren't numbers.
Number = Annotated[float, Strict(), Field(allow_inf_nan=False)]


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Tune(_Frozen):
    """Candidate values for a setting; the backtest picks one per scored season."""

    tune: tuple[Number, ...] = Field(min_length=2)

    @field_validator("tune")
    @classmethod
    def _distinct(cls, tune: tuple[float, ...]) -> tuple[float, ...]:
        if len(set(tune)) != len(tune):
            raise ValueError("a candidate is listed twice")
        return tune


Tunable = Number | Tune


class UnresolvedSettingError(ValueError):
    """A setting still holds its candidates where a single value is needed."""


def fixed(value: Tunable, path: str) -> float:
    """The setting's value, refusing one the backtest hasn't resolved yet."""
    if isinstance(value, Tune):
        raise UnresolvedSettingError(f"{path} is still tuned over {value.tune}; resolve the spec")
    return value


def _within(lo: float, hi: float | None = None, *, above: bool = False) -> AfterValidator:
    """Bound a setting and each of its candidates: `lo ≤ x ≤ hi`, or `lo < x` when `above`."""

    def check(value: Tunable) -> Tunable:
        for x in value.tune if isinstance(value, Tune) else (value,):
            if (x <= lo if above else x < lo) or (hi is not None and x > hi):
                bounds = f"> {lo}" if above else f"≥ {lo}"
                raise ValueError(f"{x} must be {bounds}" + (f" and ≤ {hi}" if hi else ""))
        return value

    return AfterValidator(check)


Positive = Annotated[Tunable, _within(0, above=True)]
NonNegative = Annotated[Tunable, _within(0)]
Share = Annotated[Tunable, _within(0, 1)]
CoverProb = Annotated[Tunable, _within(0.5, 1)]

Weight = Literal["fit"] | Number


def _registered(stat: str) -> str:
    if stat not in INPUT_IDS:
        raise ValueError(f"{stat!r} is not in the input registry")
    return stat


InputId = Annotated[
    str,
    Strict(),
    AfterValidator(_registered),
    WithJsonSchema({"type": "string", "enum": list(INPUT_IDS)}),
]


class Input(_Frozen):
    stat: InputId
    weight: Weight = "fit"


class Hyperparameters(_Frozen):
    ridge_alpha: NonNegative | None = None  # None: plain least squares
    recency_half_life_weeks: Positive | None = None  # None: every game counts the same
    margin_cap: Positive | None = None  # None: margins uncapped


class FittedDecay(_Frozen):
    type: Literal["fitted"]


class LinearDecay(_Frozen):
    type: Literal["linear"]
    zero_at_week: Positive


PriorComponent = Literal["last_season", "returning_production", "talent", "recruiting"]


class Prior(_Frozen):
    components: tuple[PriorComponent, ...] = Field(min_length=1)
    regression: Share  # how far last season's rating moves toward the mean: 0 keeps it
    weights: Weight = "fit"
    decay: Annotated[FittedDecay | LinearDecay, Field(discriminator="type")]

    @field_validator("components")
    @classmethod
    def _distinct(cls, components: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(components)) != len(components):
            raise ValueError("a component is listed twice")
        return components


class Tiers(_Frozen):
    A: Positive
    B: Positive
    C: Positive

    @model_validator(mode="after")
    def _descending(self) -> Tiers:
        tiers = [t for t in (self.A, self.B, self.C) if not isinstance(t, Tune)]
        if len(tiers) == 3 and tiers != sorted(tiers, reverse=True):
            raise ValueError(f"tiers must descend (A ≥ B ≥ C), got {tiers}")
        return self


class PickRules(_Frozen):
    min_edge_pts: NonNegative
    min_prob: CoverProb
    market_shrinkage_k: Share = 1.0  # 1: the model alone
    tiers: Tiers


class ModelSpec(_Frozen):
    spec_schema_version: Literal[1] = SPEC_SCHEMA_VERSION
    base: Literal["power", "efficiency"]
    inputs: tuple[Input, ...] = ()
    hyperparameters: Hyperparameters = Field(default_factory=Hyperparameters)
    home_field: Weight = "fit"
    prior: Prior | None = None
    distribution: Literal["normal", "empirical"] = "normal"
    picks: PickRules

    @field_validator("inputs")
    @classmethod
    def _inputs_fit_the_family(
        cls, inputs: tuple[Input, ...], info: ValidationInfo
    ) -> tuple[Input, ...]:
        base = info.data.get("base")
        if base == "power" and inputs:
            raise ValueError("a power model rates game margins only and takes no inputs")
        if base == "efficiency" and not inputs:
            raise ValueError("an efficiency model needs at least one input")
        stats = [i.stat for i in inputs]
        if len(set(stats)) != len(stats):
            raise ValueError("an input is listed twice")
        return inputs

    def tunables(self) -> dict[str, tuple[float, ...]]:
        """Every tuned setting's candidates, by dotted path (`picks.tiers.A`)."""
        return dict(_tunes(self.model_dump(), ""))

    @property
    def is_resolved(self) -> bool:
        return not self.tunables()

    def resolve(self, choices: Mapping[str, float]) -> ModelSpec:
        """A copy with each chosen setting fixed to one of its candidates."""
        tunables = self.tunables()
        data = self.model_dump()
        for path, value in choices.items():
            if path not in tunables:
                raise ValueError(f"{path} is not a tuned setting")
            if value not in tunables[path]:
                raise ValueError(f"{value} isn't one of {path}'s candidates {tunables[path]}")
            *parents, leaf = path.split(".")
            node = data
            for key in parents:
                node = node[key]
            node[leaf] = value
        return ModelSpec.model_validate(data)


def _tunes(node: Any, path: str) -> Iterator[tuple[str, tuple[float, ...]]]:
    if not isinstance(node, dict):
        return
    if node.keys() == {"tune"}:
        yield path, tuple(node["tune"])
        return
    for key, child in node.items():
        yield from _tunes(child, f"{path}.{key}" if path else key)
