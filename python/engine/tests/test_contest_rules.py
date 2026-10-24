"""`ContestRules` (TASK-023): a contest's format as a typed model, with Splash as the preset
(docs/03-data-model.md › Your data)."""

import pytest
from pydantic import ValidationError

from engine.core.contest_rules import SPLASH_PRESET, ContestRules

SPLASH = {
    "period": "week",
    "sports": ["cfb", "nfl"],
    "slate": "curated",
    "picks_per_period": 4,
    "picks_exact": True,
    "lock": "per_game_kickoff",
    "scoring": "point_per_win",
    "push": "zero",
}


def error_fields(error: ValidationError) -> set[tuple[str | int, ...]]:
    return {tuple(e["loc"]) for e in error.errors()}


def test_the_splash_preset_validates() -> None:
    rules = ContestRules.model_validate(SPLASH)

    assert rules == SPLASH_PRESET
    assert rules.sports == ("cfb", "nfl")
    assert (rules.picks_per_period, rules.picks_exact) == (4, True)


def test_zero_picks_names_picks_per_period() -> None:
    with pytest.raises(ValidationError) as caught:
        ContestRules.model_validate(SPLASH | {"picks_per_period": 0})

    assert error_fields(caught.value) == {("picks_per_period",)}


def test_an_unknown_scoring_names_scoring() -> None:
    with pytest.raises(ValidationError) as caught:
        ContestRules.model_validate(SPLASH | {"scoring": "most_points"})

    assert error_fields(caught.value) == {("scoring",)}


def test_an_unknown_field_or_an_empty_sport_list_is_refused() -> None:
    with pytest.raises(ValidationError) as caught:
        ContestRules.model_validate(SPLASH | {"tiebreak": "total"})
    assert error_fields(caught.value) == {("tiebreak",)}

    with pytest.raises(ValidationError) as caught:
        ContestRules.model_validate(SPLASH | {"sports": []})
    assert error_fields(caught.value) == {("sports",)}
