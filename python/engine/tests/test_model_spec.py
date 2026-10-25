"""`ModelSpec` v1 (TASK-029, D-050): a model's settings as validated data, its inputs from the
registry, its tuned settings readable by the backtest (docs/04-model.md § 6)."""

from typing import Any

import pytest
from pydantic import ValidationError

from engine.core.inputs import INPUTS
from engine.core.spec import SPEC_SCHEMA_VERSION, ModelSpec

# 04 § 6's sketch in the v1 shape, minus `explosiveness` (not a v1 input).
SKETCH: dict[str, Any] = {
    "base": "efficiency",
    "inputs": [
        {"stat": "pass_epa_per_play", "weight": "fit"},
        {"stat": "rush_epa_per_play", "weight": "fit"},
        {"stat": "success_rate", "weight": 0.31},
    ],
    "hyperparameters": {
        "ridge_alpha": 150,
        "recency_half_life_weeks": {"tune": [4, 6, 8]},
        "margin_cap": 28,
    },
    "home_field": "fit",
    "prior": {
        "components": ["last_season", "returning_production", "talent", "recruiting"],
        "regression": 0.3,
        "weights": "fit",
        "decay": {"type": "fitted"},
    },
    "distribution": "normal",
    "picks": {
        "min_edge_pts": 3.0,
        "min_prob": 0.55,
        "market_shrinkage_k": 0.7,
        "tiers": {"A": 5.0, "B": 3.5, "C": 2.5},
    },
}

POWER: dict[str, Any] = {
    "base": "power",
    "hyperparameters": {"margin_cap": 28},
    "home_field": 2.5,
    "picks": SKETCH["picks"],
}


def error_fields(error: ValidationError) -> set[tuple[str | int, ...]]:
    return {tuple(e["loc"]) for e in error.errors()}


def refused(data: dict[str, Any]) -> set[tuple[str | int, ...]]:
    with pytest.raises(ValidationError) as caught:
        ModelSpec.model_validate(data)
    return error_fields(caught.value)


def with_input(**changes: Any) -> dict[str, Any]:
    return SKETCH | {"inputs": [SKETCH["inputs"][0] | changes]}


def test_the_sketch_validates_and_carries_the_schema_version() -> None:
    spec = ModelSpec.model_validate(SKETCH)

    assert spec.spec_schema_version == SPEC_SCHEMA_VERSION == 1
    assert [i.stat for i in spec.inputs] == [
        "pass_epa_per_play",
        "rush_epa_per_play",
        "success_rate",
    ]
    assert [i.weight for i in spec.inputs] == ["fit", "fit", 0.31]


def test_an_unknown_field_is_refused_by_name() -> None:
    assert refused(SKETCH | {"name": "efficiency-v1"}) == {("name",)}
    assert refused(SKETCH | {"picks": SKETCH["picks"] | {"kelly": 0.25}}) == {("picks", "kelly")}


def test_an_input_outside_the_registry_is_refused_by_name() -> None:
    assert refused(with_input(stat="explosiveness")) == {("inputs", 0, "stat")}


def test_a_weight_that_is_neither_fit_nor_a_number_is_refused_by_name() -> None:
    for weight in ("learned", "6", True, None):
        fields = refused(with_input(weight=weight))
        assert {f[:3] for f in fields} == {("inputs", 0, "weight")}, weight

    assert {f[:1] for f in refused(SKETCH | {"home_field": "guess"})} == {("home_field",)}


def test_a_fixed_number_or_fit_validates_as_a_weight() -> None:
    assert ModelSpec.model_validate(with_input(weight=0.0)).inputs[0].weight == 0.0
    assert ModelSpec.model_validate(with_input(weight=31)).inputs[0].weight == 31
    assert ModelSpec.model_validate(SKETCH | {"home_field": 2.0}).home_field == 2.0


def test_the_family_decides_whether_inputs_are_allowed() -> None:
    assert ModelSpec.model_validate(POWER).inputs == ()
    assert refused(POWER | {"inputs": SKETCH["inputs"]}) == {("inputs",)}
    assert refused(SKETCH | {"inputs": []}) == {("inputs",)}
    assert refused(SKETCH | {"inputs": [SKETCH["inputs"][0]] * 2}) == {("inputs",)}


def test_tiers_must_descend() -> None:
    tiers = {"A": 3.0, "B": 3.5, "C": 2.5}
    assert refused(SKETCH | {"picks": SKETCH["picks"] | {"tiers": tiers}}) == {("picks", "tiers")}


def test_a_probability_setting_outside_its_range_is_refused_by_name() -> None:
    picks = SKETCH["picks"] | {"min_prob": 0.4}
    assert refused(SKETCH | {"picks": picks}) == {("picks", "min_prob")}

    picks = SKETCH["picks"] | {"market_shrinkage_k": {"tune": [0.5, 1.2]}}
    assert refused(SKETCH | {"picks": picks}) == {("picks", "market_shrinkage_k")}


def test_a_valid_spec_round_trips_through_json() -> None:
    for data in (SKETCH, POWER):
        spec = ModelSpec.model_validate(data)
        assert ModelSpec.model_validate_json(spec.model_dump_json()) == spec


def test_the_json_schema_offers_exactly_the_registry_ids_as_stat() -> None:
    schema = ModelSpec.model_json_schema()
    stat = schema["$defs"]["Input"]["properties"]["stat"]

    assert sorted(stat["enum"]) == sorted(d.id for d in INPUTS)
    assert len(stat["enum"]) == len(INPUTS)


def test_tunables_lists_every_tuned_setting_by_path() -> None:
    picks = SKETCH["picks"] | {"tiers": {"A": {"tune": [4.5, 5.0]}, "B": 3.5, "C": 2.5}}
    spec = ModelSpec.model_validate(SKETCH | {"picks": picks})

    assert spec.tunables() == {
        "hyperparameters.recency_half_life_weeks": (4, 6, 8),
        "picks.tiers.A": (4.5, 5.0),
    }
    assert not spec.is_resolved


def test_resolve_fixes_each_tuned_setting_to_one_candidate() -> None:
    spec = ModelSpec.model_validate(SKETCH)
    resolved = spec.resolve({"hyperparameters.recency_half_life_weeks": 6})

    assert resolved.hyperparameters.recency_half_life_weeks == 6
    assert resolved.tunables() == {}
    assert resolved.is_resolved
    assert spec.hyperparameters.recency_half_life_weeks != 6  # the original is unchanged


def test_resolve_refuses_an_unknown_path_or_a_value_outside_the_candidates() -> None:
    spec = ModelSpec.model_validate(SKETCH)

    with pytest.raises(ValueError, match="hyperparameters.ridge_alpha"):
        spec.resolve({"hyperparameters.ridge_alpha": 100})
    with pytest.raises(ValueError, match="recency_half_life_weeks"):
        spec.resolve({"hyperparameters.recency_half_life_weeks": 5})


def test_a_tune_needs_at_least_two_candidates() -> None:
    hyper = SKETCH["hyperparameters"] | {"margin_cap": {"tune": [28]}}
    fields = refused(SKETCH | {"hyperparameters": hyper})
    assert {f[:2] for f in fields} == {("hyperparameters", "margin_cap")}
