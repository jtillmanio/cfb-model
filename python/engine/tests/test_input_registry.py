"""The input registry (TASK-029, D-117): every metric a spec can use, described once
(docs/04-model.md § 10.6), starting with the v1 inputs (§ 10.2)."""

import pytest
from pydantic import ValidationError

from engine.core.inputs import INPUTS, InputDef
from engine.transform.features import FEATURES

V1_INPUTS = {
    "epa_per_play",
    "rush_epa_per_play",
    "pass_epa_per_play",
    "success_rate",
    "rush_success_rate",
    "pass_success_rate",
}


def test_one_entry_per_v1_input_with_unique_ids() -> None:
    ids = [d.id for d in INPUTS]

    assert len(ids) == len(set(ids))
    assert set(ids) == V1_INPUTS


def test_every_entry_fills_every_field() -> None:
    for entry in INPUTS:
        for name, value in entry.model_dump().items():
            assert value is not None and value != "", (entry.id, name)
        assert entry.first_season >= 2014


def test_an_entry_without_a_label_or_definition_is_refused() -> None:
    entry = INPUTS[0].model_dump()

    for name in ("label", "definition"):
        with pytest.raises(ValidationError) as caught:
            InputDef.model_validate({k: v for k, v in entry.items() if k != name})
        assert {e["loc"] for e in caught.value.errors()} == {(name,)}

        with pytest.raises(ValidationError):
            InputDef.model_validate(entry | {name: "  "})


def test_every_entry_names_a_feature_column_for_offense_and_defense() -> None:
    for entry in INPUTS:
        assert f"off_{entry.feature}" in FEATURES, entry.id
        assert f"def_{entry.feature}" in FEATURES, entry.id
