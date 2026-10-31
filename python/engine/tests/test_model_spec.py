"""`ModelSpec` v1 (TASK-029, D-050): a model's settings as validated data, its inputs from the
registry, its tuned settings readable by the backtest (docs/04-model.md § 6)."""

from pathlib import Path
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


def test_shrink_toward_defaults_to_zero_and_takes_tier() -> None:
    """TASK-036 (04 § 10.4): a new optional field whose default keeps the old behaviour, so the
    schema version stays 1 (D-130)."""
    assert ModelSpec.model_validate(SKETCH).shrink_toward == "zero"
    assert ModelSpec.model_validate(SKETCH | {"shrink_toward": "tier"}).shrink_toward == "tier"
    assert refused(SKETCH | {"shrink_toward": "conference"}) == {("shrink_toward",)}  # M19.1
    assert ModelSpec.model_validate(SKETCH | {"shrink_toward": "tier"}).spec_schema_version == 1


def test_rung_1_refuses_to_shrink_toward_a_tier() -> None:
    from engine.models.power import PowerRatings, UnsupportedSpecError
    from engine.sports.cfb.teams import RULES

    with pytest.raises(UnsupportedSpecError, match="shrink_toward"):
        PowerRatings(ModelSpec.model_validate(POWER | {"shrink_toward": "tier"}), RULES)


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


def test_a_spec_at_shrink_toward_zero_keeps_its_hash() -> None:
    """D-137: a field added after v1 is left out of the hash at its default, so a backtest's
    `run.json` written before the field still matches its spec."""
    import hashlib
    import json

    from engine.backtest.harness import spec_hash

    spec = ModelSpec.model_validate(POWER)
    before = {k: v for k, v in spec.model_dump(mode="json").items() if k != "shrink_toward"}
    # The JSON as written before either added field (TASK-042's display_shrinkage_k too).
    before["picks"] = {k: v for k, v in before["picks"].items() if k != "display_shrinkage_k"}
    text = json.dumps(before, sort_keys=True, separators=(",", ":"))

    assert spec_hash(spec) == hashlib.sha256(text.encode("utf-8")).hexdigest()
    tier = ModelSpec.model_validate(SKETCH | {"shrink_toward": "tier"})
    assert spec_hash(tier) != spec_hash(ModelSpec.model_validate(SKETCH))


SPECS = Path(__file__).parents[1] / "specs"


def test_a_spec_without_the_display_shrinkage_keeps_its_hash() -> None:
    """TASK-042 AC-4: `picks.display_shrinkage_k` at its default (1, the model alone) is left out
    of the hash (D-137), so `power-v1.json` and every run.json written before keep matching."""
    import json

    from engine.backtest.harness import spec_hash

    power = json.loads((SPECS / "power-v1.json").read_text("utf-8"))
    at_one = power | {"picks": power["picks"] | {"display_shrinkage_k": 1.0}}
    shrunk = power | {"picks": power["picks"] | {"display_shrinkage_k": 0.5}}

    before = "064e84947bdf7b0595f91981e3301094ae57b7e075b3000d344e885555916415"
    assert spec_hash(ModelSpec.model_validate(power)) == before
    assert spec_hash(ModelSpec.model_validate(at_one)) == before
    assert spec_hash(ModelSpec.model_validate(shrunk)) != before
    assert ModelSpec.model_validate(power).picks.display_shrinkage_k == 1.0


def test_the_v1_spec_tunes_ridge_alpha_above_2() -> None:
    """TASK-043 AC-1: every 2016-2023 season picked `ridge_alpha` 2, the top of {0.5, 1, 2}
    (D-138), so v1's final grid reaches above it and an edge choice can be told from a real one."""
    import json

    v1 = ModelSpec.model_validate(json.loads((SPECS / "efficiency-v1.json").read_text("utf-8")))
    grid = v1.tunables()["hyperparameters.ridge_alpha"]

    assert max(grid) > 2
    assert 2 in grid and min(grid) < 2  # 2 stays an inner candidate


def test_the_last_season_prior_sibling_differs_from_v1_only_in_its_components() -> None:
    """TASK-043 AC-2: the prior recheck compares the four components with last season alone, so
    the sibling must stay v1 in every other setting or the comparison stops being like for like."""
    import json

    v1 = ModelSpec.model_validate(json.loads((SPECS / "efficiency-v1.json").read_text("utf-8")))
    path = SPECS / "efficiency-v1-last-season-prior.json"
    sibling = ModelSpec.model_validate(json.loads(path.read_text("utf-8")))

    assert sibling.prior is not None and sibling.prior.components == ("last_season",)
    assert v1.prior is not None and len(v1.prior.components) == 4
    prior = sibling.prior.model_copy(update={"components": v1.prior.components})
    assert sibling.model_copy(update={"prior": prior}) == v1
