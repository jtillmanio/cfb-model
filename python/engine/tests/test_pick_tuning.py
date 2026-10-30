"""Tuning the pick rules on earlier seasons (TASK-039; docs/04-model.md § 4, § 9.1, § 9.2; D-055).

AC-1: season Y's `market_shrinkage_k` is the lowest cover Brier on its tuning seasons, and its
thresholds the best ATS win % among candidates with 200+ graded picks there. AC-2: the model's
settings are tuned as before, both land in `run.json` `choices`, and grading and `engine rate`
read the pick rules from there.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any

import pytest
from lake_fixture import write_backtest_seasons

from engine.backtest import harness, metrics, pick_rules
from engine.backtest.stub import MeanMargin
from engine.core.spec import ModelSpec, fixed
from engine.ingest.lake import LocalLake
from engine.publish import models
from engine.transform import rebuild
from engine.transform.features import PointInTimeError

PICKS: dict[str, Any] = {
    "min_edge_pts": 3.0,
    "min_prob": 0.5,
    "tiers": {"A": 5.0, "B": 3.5, "C": 2.5},
}


def spec(picks: Mapping[str, Any], hyperparameters: Mapping[str, Any] | None = None) -> ModelSpec:
    return ModelSpec.model_validate(
        {
            "base": "power",
            "hyperparameters": hyperparameters or {"margin_cap": 28, "recency_half_life_weeks": 6},
            "picks": {**PICKS, **picks},
        }
    )


_ids = iter(range(10**6))


def row(season: int, edge: float, covered: bool) -> dict[str, Any]:
    """A pick'em game the model has home by `edge`; home covers by 10 or misses by 10."""
    return {
        "season": season,
        "season_type": "regular",
        "week": 1,
        "game_source_id": str(next(_ids)),
        "pred_margin": edge,
        "margin_sd": 16.0,
        "home_win_prob": 0.5,
        "spread_home": 0.0,
        "spread_home_open": None,
        "margin": 10 if covered else -10,
    }


def rows(season: int, edge: float, wins: int, losses: int) -> list[dict[str, Any]]:
    return [row(season, edge, True) for _ in range(wins)] + [
        row(season, edge, False) for _ in range(losses)
    ]


def evaluating(by_season: Mapping[int, Sequence[dict[str, Any]]]) -> pick_rules.Evaluate:
    def evaluate(choices: pick_rules.Choices, season: int) -> Sequence[dict[str, Any]]:
        return by_season[season]

    return evaluate


EDGES = {"min_edge_pts": {"tune": [1.0, 4.0]}}


def big_edges(picks: int) -> list[dict[str, Any]]:
    """`picks` games at edge 5 that win 60%, and 101 at edge 2 that win 45%: over every
    threshold the best ATS is edge 4's."""
    wins = round(picks * 0.6)
    return rows(2015, 5.0, wins, picks - wins) + rows(2015, 2.0, 45, 56)


def test_the_best_ats_threshold_with_199_picks_loses_to_the_next_best_with_200() -> None:
    tuned = pick_rules.tune(spec(EDGES), {}, (2015,), evaluating({2015: big_edges(199)}))

    assert tuned is not None
    assert tuned.choices == {"picks.min_edge_pts": 1.0}
    assert (tuned.picks, tuned.floor_met) == (300, True)


def test_the_best_ats_threshold_with_200_picks_is_chosen() -> None:
    tuned = pick_rules.tune(spec(EDGES), {}, (2015,), evaluating({2015: big_edges(200)}))

    assert tuned is not None
    assert tuned.choices == {"picks.min_edge_pts": 4.0}
    assert (tuned.picks, tuned.floor_met) == (200, True)


def test_with_no_candidate_at_200_picks_the_one_with_most_picks_is_chosen_and_flagged() -> None:
    few = rows(2015, 5.0, 60, 40) + rows(2015, 2.0, 10, 30)

    tuned = pick_rules.tune(spec(EDGES), {}, (2015,), evaluating({2015: few}))

    assert tuned is not None
    assert tuned.choices == {"picks.min_edge_pts": 1.0}
    assert (tuned.picks, tuned.floor_met) == (140, False)


def test_picks_are_pooled_over_the_tuning_seasons() -> None:
    by_season = {2015: big_edges(100), 2016: rows(2016, 5.0, 60, 40)}

    tuned = pick_rules.tune(spec(EDGES), {}, (2015, 2016), evaluating(by_season))

    assert tuned is not None
    assert tuned.choices == {"picks.min_edge_pts": 4.0}
    assert tuned.picks == 200


def test_equal_ats_goes_to_more_picks_then_grid_order() -> None:
    even = rows(2015, 5.0, 150, 150) + rows(2015, 2.0, 50, 50)
    tied = spec({"min_edge_pts": {"tune": [4.0, 1.0, 0.5]}})

    tuned = pick_rules.tune(tied, {}, (2015,), evaluating({2015: even}))

    assert tuned is not None
    assert tuned.choices == {"picks.min_edge_pts": 1.0}  # 0.5 picks the same 400: grid order


SHRINK = {"market_shrinkage_k": {"tune": [0.25, 0.5, 1.0]}}


@pytest.mark.parametrize(("hit", "k"), [(0.5, 0.25), (0.6, 0.5), (1.0, 1.0)])
def test_k_is_the_lowest_cover_brier_on_the_tuning_seasons(hit: float, k: float) -> None:
    # Edge 8 at σ 16: Φ(8k/16) is 0.55 at k 0.25, 0.6 at k 0.5 and 0.69 at k 1, so the Brier
    # score is lowest where the displayed probability is nearest the hit rate.
    games = rows(2015, 8.0, round(1000 * hit), 1000 - round(1000 * hit))

    tuned = pick_rules.tune(spec(SHRINK), {}, (2015,), evaluating({2015: games}))

    assert tuned is not None
    assert tuned.choices == {"picks.market_shrinkage_k": k}


def test_the_thresholds_are_chosen_on_the_blended_edge_at_the_chosen_k() -> None:
    # A coin flip at edge 8: k is 0.25, so the blended edge is 2.0 and only threshold 2 picks.
    games = rows(2015, 8.0, 150, 150)
    both = spec({**SHRINK, "min_edge_pts": {"tune": [3.0, 2.0]}})

    tuned = pick_rules.tune(both, {}, (2015,), evaluating({2015: games}))

    assert tuned is not None
    assert tuned.choices == {"picks.market_shrinkage_k": 0.25, "picks.min_edge_pts": 2.0}
    assert tuned.picks == 300


def test_a_spec_with_fixed_pick_rules_tunes_nothing() -> None:
    assert pick_rules.tune(spec({}), {}, (2015,), evaluating({2015: big_edges(200)})) is None


def test_tier_candidates_out_of_order_are_skipped() -> None:
    tiers = spec({"tiers": {"A": {"tune": [3.0, 6.0]}, "B": 4.0, "C": 2.5}})

    tuned = pick_rules.tune(tiers, {}, (2015,), evaluating({2015: big_edges(200)}))

    assert tuned is not None
    assert tuned.choices == {"picks.tiers.A": 6.0}  # A 3.0 is below B


def test_k_is_tuned_when_the_first_tier_candidate_is_out_of_order() -> None:
    both = spec({**SHRINK, "tiers": {"A": {"tune": [3.0, 6.0]}, "B": 4.0, "C": 2.5}})
    games = rows(2015, 8.0, 500, 500)

    tuned = pick_rules.tune(both, {}, (2015,), evaluating({2015: games}))

    assert tuned is not None
    assert tuned.choices == {"picks.market_shrinkage_k": 0.25, "picks.tiers.A": 6.0}


def test_pick_rules_with_no_valid_combination_are_refused(lake: LocalLake) -> None:
    bad = spec({"tiers": {"A": {"tune": [2.0, 3.0]}, "B": 4.0, "C": 2.5}}, MODEL_GRID)

    with pytest.raises(pick_rules.NoValidRulesError, match=r"picks\.tiers\.A"):
        pick_rules.tune(bad, {}, (2015,), evaluating({2015: big_edges(200)}))
    with pytest.raises(harness.RefusedError, match="valid set of pick rules"):
        harness.run(bad, MeanMargin, harness.load(lake), [2023], 2022)


# Through the harness, on the fixture lake.


@pytest.fixture
def lake(empty_lake: LocalLake) -> LocalLake:
    write_backtest_seasons(empty_lake, (2022, 2023))
    rebuild(empty_lake)
    return empty_lake


MODEL_GRID = {"margin_cap": {"tune": [14, 28]}, "recency_half_life_weeks": 6}
TUNED_PICKS = {"market_shrinkage_k": {"tune": [0.5, 1.0]}, "min_edge_pts": {"tune": [1.0, 3.0]}}


def test_a_season_s_pick_rules_never_read_its_own_results(lake: LocalLake) -> None:
    tuned = spec(TUNED_PICKS, MODEL_GRID)
    history = harness.load(lake)
    before = harness.run(tuned, MeanMargin, history, [2023], 2022)

    flipped = []
    for week in history.weeks:
        games = week.games
        if week.season == 2023:
            games = tuple(
                replace(g, home_points=g.away_points, away_points=g.home_points) for g in games
            )
        flipped.append(replace(week, games=games))
    after = harness.run(tuned, MeanMargin, replace(history, weeks=tuple(flipped)), [2023], 2022)

    assert [r["margin"] for r in after.rows] == [-r["margin"] for r in before.rows]
    assert after.choices == before.choices
    assert after.pick_tuning == before.pick_tuning


def test_the_pick_tuner_sees_only_the_tuning_seasons(lake: LocalLake) -> None:
    def peeking(
        spec: ModelSpec,
        model: pick_rules.Choices,
        tuning: Sequence[int],
        evaluate: pick_rules.Evaluate,
    ) -> pick_rules.PickTuning | None:
        evaluate(model, 2023)  # the season being scored
        return pick_rules.tune(spec, model, tuning, evaluate)

    with pytest.raises(PointInTimeError, match="2023"):
        harness.run(
            spec(TUNED_PICKS, MODEL_GRID),
            MeanMargin,
            harness.load(lake),
            [2023],
            2022,
            pick_tuner=peeking,
        )


def test_pick_rules_never_change_the_model_settings(lake: LocalLake) -> None:
    history = harness.load(lake)
    built: list[ModelSpec] = []

    def counting(resolved: ModelSpec) -> MeanMargin:
        built.append(resolved)
        return MeanMargin(resolved)

    plain = harness.run(spec({}, MODEL_GRID), counting, history, [2023], 2022)
    fits = len(built)
    tuned = harness.run(spec(TUNED_PICKS, MODEL_GRID), counting, history, [2023], 2022)

    model = {p: v for p, v in tuned.choices[2023].items() if not p.startswith("picks.")}
    assert model == plain.choices[2023]
    assert tuned.rows == plain.rows
    # Each model setting is walked forward once per season, however many pick candidates.
    assert len(built) - fits == fits
    assert set(tuned.choices[2023]) - set(model) == {
        "picks.market_shrinkage_k",
        "picks.min_edge_pts",
    }


def test_run_json_carries_the_pick_rules_that_grading_and_engine_rate_use(
    lake: LocalLake,
) -> None:
    tuned = spec(TUNED_PICKS, MODEL_GRID)
    result = harness.run(tuned, MeanMargin, harness.load(lake), [2023], 2022)
    at = datetime(2026, 10, 30, tzinfo=UTC)
    folder = harness.write(
        lake, result, spec=tuned, model="stub", tune_from=2022, holdout=False, at=at
    )
    run = json.loads(lake.read(f"{folder}/run.json"))
    chosen = result.choices[2023]

    assert run["choices"]["2023"] == chosen
    assert run["pick_tuning"]["2023"] == {
        "picks": result.pick_tuning[2023].picks,
        "floor_met": result.pick_tuning[2023].floor_met,
    }
    rules = tuned.resolve(chosen).picks
    graded = metrics.grade_rows(result.rows, tuned, {2023: chosen})
    k = fixed(rules.market_shrinkage_k, "k")
    assert all(g.edge == pytest.approx(k * (g.pred_margin + g.spread_home)) for g in graded)
    assert tuned.resolve(models.settings(tuned, run, 2023)).picks == rules


def test_a_spec_with_fixed_pick_rules_writes_no_pick_tuning(lake: LocalLake) -> None:
    plain = spec({}, MODEL_GRID)
    result = harness.run(plain, MeanMargin, harness.load(lake), [2023], 2022)
    at = datetime(2026, 10, 30, tzinfo=UTC)
    folder = harness.write(
        lake, result, spec=plain, model="stub", tune_from=2022, holdout=False, at=at
    )

    assert result.pick_tuning == {}
    assert "pick_tuning" not in json.loads(lake.read(f"{folder}/run.json"))
