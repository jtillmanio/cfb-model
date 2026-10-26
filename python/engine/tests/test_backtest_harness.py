"""The walk-forward harness (TASK-030, docs/04-model.md § 9.1-9.3): it predicts every eligible
game of the scored seasons once, in (season, week) order, tunes each season's settings on earlier
seasons only, fits each week on games finished before its `as_of`, refuses leaks and refused
inputs, and keeps the holdout seasons locked behind a flag and a reason.
"""

from __future__ import annotations

import io
import json
from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import timedelta
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from lake_fixture import (
    BACKTEST_SEASONS,
    FIXTURE,
    NO_LINE,
    POSTSEASON,
    backtest_game_id,
    engine,
    fixture_key,
    staged,
    write_backtest_seasons,
)

from engine import backtest
from engine.backtest import harness, holdout
from engine.backtest.stub import MeanMargin
from engine.core.interfaces import GameContext, GameHistory, Prediction, Ratings
from engine.core.spec import ModelSpec
from engine.ingest.lake import LocalLake
from engine.transform import feature_key, rebuild

PICKS = {"min_edge_pts": 3.0, "min_prob": 0.55, "tiers": {"A": 5.0, "B": 3.5, "C": 2.5}}
FIXED: dict[str, Any] = {
    "base": "power",
    "hyperparameters": {"margin_cap": 28, "recency_half_life_weeks": 6},
    "picks": PICKS,
}
TUNED: dict[str, Any] = {
    **FIXED,
    "hyperparameters": {"margin_cap": {"tune": [14, 28]}, "recency_half_life_weeks": 6},
}
UNLV_IDAHO_STATE = "401760371"  # FBS vs FCS
COLUMNS = ["season", "week", "game_source_id", "pred_margin", "margin_sd", "spread_home", "margin"]


@pytest.fixture
def backtest_lake(empty_lake: LocalLake) -> LocalLake:
    write_backtest_seasons(empty_lake)
    rebuild(empty_lake)
    return empty_lake


def spec_file(tmp_path: Path, spec: Mapping[str, Any]) -> str:
    path = tmp_path / "spec.json"
    path.write_text(json.dumps(spec), "utf-8")
    return str(path)


def written(lake: LocalLake) -> list[str]:
    return lake.walk("backtests")


def predictions(lake: LocalLake) -> list[dict[str, Any]]:
    """The one run's results rows, in file order."""
    (key,) = [k for k in written(lake) if k.endswith("/predictions.parquet")]
    return pq.read_table(io.BytesIO(lake.read(key))).to_pylist()


def eligible_ids(season: int) -> list[str]:
    """The fixture season's FBS-vs-FBS games with a closing line, worked out from the fixture."""
    ids = []
    for game in FIXTURE[fixture_key("games")]["records"]:
        week1 = str(game["id"])
        if week1 == UNLV_IDAHO_STATE:
            continue
        ids += [
            backtest_game_id(season, "regular", w, week1)
            for w in range(1, 9)
            if (w, week1) != NO_LINE
        ]
        if week1 in POSTSEASON:
            ids.append(backtest_game_id(season, "postseason", 1, week1))
    return ids


class Counting(MeanMargin):
    """The stub model, counting each game it's asked to predict."""

    calls: Counter[int] = Counter()

    def predict(self, game: GameContext, ratings: Ratings, as_of: Any) -> Prediction:
        Counting.calls[game.game_id] += 1
        return super().predict(game, ratings, as_of)


def test_backtest_predicts_every_eligible_game_once_in_week_order(
    backtest_lake: LocalLake, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    Counting.calls = Counter()
    monkeypatch.setitem(backtest.MODELS, "counting", Counting)
    spec = spec_file(tmp_path, FIXED)

    assert engine("backtest", "--spec", spec, "--seasons", "2022-2023", "--model", "counting") == 0

    rows = predictions(backtest_lake)
    expected = eligible_ids(2022) + eligible_ids(2023)
    assert sorted(r["game_source_id"] for r in rows) == sorted(expected)
    assert len(rows) == len(expected) == 66
    assert Counting.calls == Counter({int(g): 1 for g in expected})
    # The FBS-vs-FCS game and the game with no line are staged, and get no row.
    staged_ids = {g["source_id"] for g in staged(backtest_lake, "games").to_pylist()}
    left_out = {
        backtest_game_id(season, "regular", week, game)
        for season in BACKTEST_SEASONS
        for week, game in [NO_LINE, (1, UNLV_IDAHO_STATE)]
    }
    assert left_out <= staged_ids
    assert left_out.isdisjoint(r["game_source_id"] for r in rows)

    # (season, week) order, postseason after the regular season.
    order = [(r["season"], r["season_type"] == "postseason", r["week"]) for r in rows]
    assert order == sorted(order)
    assert [r["as_of"] for r in rows] == sorted(r["as_of"] for r in rows)

    games = {g["source_id"]: g for g in staged(backtest_lake, "games").to_pylist()}
    for row in rows:
        assert set(COLUMNS) <= row.keys()
        game = games[row["game_source_id"]]
        assert row["margin"] == game["home_points"] - game["away_points"]
        assert row["margin_sd"] > 0
    # Kansas-Fresno State's lines quote -14, -14.5 and -14: the median of the closing rows.
    kansas_id = backtest_game_id(2022, "regular", 1, "401756847")
    (kansas,) = [r for r in rows if r["game_source_id"] == kansas_id]
    assert kansas["spread_home"] == -14.0


def test_a_game_that_is_not_final_gets_no_row(
    empty_lake: LocalLake, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Kansas-Fresno State, 2023 week 8: never completed, though its line is there.
    unplayed = (2023, "regular", 8, "401756847")
    write_backtest_seasons(empty_lake, unplayed=unplayed)
    rebuild(empty_lake)
    game = backtest_game_id(*unplayed)
    staged_game = by_source_id(staged(empty_lake, "games"))[game]
    assert staged_game["status"] == "scheduled"
    assert game in {r["game_source_id"] for r in staged(empty_lake, "lines").to_pylist()}

    spec = spec_file(tmp_path, FIXED)
    assert engine("backtest", "--spec", spec, "--seasons", "2022-2023", "--model", "stub") == 0

    rows = predictions(empty_lake)
    assert game not in {r["game_source_id"] for r in rows}
    assert len(rows) == 65


def test_scoring_a_holdout_season_never_tunes_on_one(empty_lake: LocalLake) -> None:
    write_backtest_seasons(empty_lake, (2022, 2023, 2024, 2025))
    rebuild(empty_lake)
    shown: list[tuple[int, ...]] = []

    def recording_tuner(
        spec: ModelSpec, tuning: Sequence[int], evaluate: harness.Evaluate
    ) -> Mapping[str, float]:
        shown.append(tuple(tuning))
        return harness.grid_tuner(spec, tuning, evaluate)

    spec = ModelSpec.model_validate(TUNED)
    harness.run(spec, MeanMargin, harness.load(empty_lake), [2024, 2025], 2022, recording_tuner)

    # 2025 is tuned on 2022-2023 like 2024, not on 2024 (04 § 9.1).
    assert shown == [(2022, 2023), (2022, 2023)]


def by_source_id(table: pa.Table) -> dict[str, dict[str, Any]]:
    return {r["source_id"]: r for r in table.to_pylist()}


def test_scoring_a_season_tunes_on_earlier_seasons_and_fits_on_finished_games(
    empty_lake: LocalLake,
) -> None:
    seasons = (2015, 2016, 2017, 2018)
    write_backtest_seasons(empty_lake, seasons)
    rebuild(empty_lake)
    history = harness.load(empty_lake)
    games = staged(empty_lake, "games").to_pylist()

    shown: list[tuple[int, ...]] = []

    def recording_tuner(
        spec: ModelSpec, tuning: Sequence[int], evaluate: harness.Evaluate
    ) -> Mapping[str, float]:
        shown.append(tuple(tuning))
        return harness.grid_tuner(spec, tuning, evaluate)

    fits: list[tuple[Any, frozenset[int]]] = []

    class Recording(MeanMargin):
        def fit(self, games: GameHistory, as_of: Any) -> Ratings:
            fits.append((as_of, frozenset(g.game_id for g in games)))
            return super().fit(games, as_of)

    run = harness.run(
        ModelSpec.model_validate(TUNED),
        Recording,
        history,
        seasons=[2016, 2017, 2018],
        tune_from=2015,
        tuner=recording_tuner,
    )

    assert shown == [(2015,), (2015, 2016), (2015, 2016, 2017)]
    assert set(run.choices) == {2016, 2017, 2018}
    assert fits
    for as_of, given in fits:
        finished = {
            int(g["source_id"])
            for g in games
            if g["status"] == "final" and g["kickoff_at"] + timedelta(hours=4) <= as_of
        }
        assert given == finished, as_of
    # The fit entering a postseason sees that whole regular season, and earlier seasons.
    post_as_of = max(a for a, _ in fits if a.year == 2018)
    (post,) = {g for a, g in fits if a == post_as_of}
    assert int(backtest_game_id(2018, "regular", 8, "401756847")) in post
    assert int(backtest_game_id(2015, "regular", 1, "401756847")) in post
    assert int(backtest_game_id(2018, "postseason", 1, "401756847")) not in post


def test_a_spec_with_tuned_settings_needs_an_earlier_tuning_season(
    backtest_lake: LocalLake, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    argv = ["backtest", "--spec", spec_file(tmp_path, TUNED), "--model", "stub"]
    assert engine(*argv, "--seasons", "2022-2023", "--tune-from", "2022") == 2
    assert "2022" in capsys.readouterr().err
    assert written(backtest_lake) == []
    # The default first tuning season, 2015, isn't in the lake.
    assert engine(*argv, "--seasons", "2023") == 2
    assert "2015" in capsys.readouterr().err
    assert written(backtest_lake) == []


def test_a_feature_row_that_reads_a_later_game_stops_the_run(
    backtest_lake: LocalLake, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    key = feature_key("game_features")
    table = pq.read_table(io.BytesIO(backtest_lake.read(key)))
    rows = table.to_pylist()
    target = backtest_game_id(2023, "regular", 5, "401756847")
    for row in rows:
        if row["game_source_id"] == target:
            row["home_last_game_kickoff"] = row["as_of"]  # a game that hadn't finished
    buffer = io.BytesIO()
    pq.write_table(pa.Table.from_pylist(rows, table.schema), buffer)
    backtest_lake.replace(key, buffer.getvalue())

    spec = spec_file(tmp_path, FIXED)
    assert engine("backtest", "--spec", spec, "--seasons", "2022-2023", "--model", "stub") == 1
    out = capsys.readouterr()
    assert "2023 regular week 5" in out.out + out.err
    assert written(backtest_lake) == []


def test_fitting_on_a_game_that_had_not_finished_stops_the_run(
    backtest_lake: LocalLake,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Loosen the harness's selection so each week's fit also gets the next week's games.
    monkeypatch.setattr(harness, "SELECT_LAG", timedelta(days=-8))
    spec = spec_file(tmp_path, FIXED)
    assert engine("backtest", "--spec", spec, "--seasons", "2022-2023", "--model", "stub") == 1
    out = capsys.readouterr()
    assert "2022 regular week 1" in out.out + out.err
    assert written(backtest_lake) == []


@pytest.mark.parametrize("asked", ["hindsight_ratings", "lines", "line_snapshots", "closing_lines"])
def test_a_model_that_asks_for_a_refused_input_stops_the_run(
    asked: str,
    backtest_lake: LocalLake,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Asking(MeanMargin):
        reads = frozenset({"games", asked})

    monkeypatch.setitem(backtest.MODELS, "asking", Asking)
    spec = spec_file(tmp_path, FIXED)
    assert engine("backtest", "--spec", spec, "--seasons", "2022-2023", "--model", "asking") == 2
    assert asked in capsys.readouterr().err
    assert written(backtest_lake) == []


def test_a_spec_base_with_no_model_yet_is_refused(
    backtest_lake: LocalLake, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert engine("backtest", "--spec", spec_file(tmp_path, FIXED), "--seasons", "2022") == 2
    assert "power" in capsys.readouterr().err


@pytest.fixture
def holdout_lake(empty_lake: LocalLake) -> LocalLake:
    write_backtest_seasons(empty_lake, (2023, 2024, 2025))
    rebuild(empty_lake)
    return empty_lake


@pytest.mark.parametrize("seasons", ["2023-2024", "2025"])
@pytest.mark.parametrize(
    "flags", [[], ["--holdout"], ["--reason", "a look"], ["--holdout", "--reason", " "]]
)
def test_holdout_seasons_need_the_flag_and_a_reason(
    seasons: str,
    flags: list[str],
    holdout_lake: LocalLake,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    spec = spec_file(tmp_path, FIXED)
    assert engine("backtest", "--spec", spec, "--seasons", seasons, "--model", "stub", *flags) == 2
    assert "holdout" in capsys.readouterr().err
    assert written(holdout_lake) == []
    assert holdout.count(holdout_lake) == 0


def test_a_flagged_holdout_run_completes_and_is_recorded(
    holdout_lake: LocalLake, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    spec = spec_file(tmp_path, FIXED)
    argv = ["backtest", "--spec", spec, "--seasons", "2024-2025", "--model", "stub"]
    reason = "Promotion check for v1.1"

    assert engine(*argv, "--holdout", "--reason", reason) == 0
    assert {r["season"] for r in predictions(holdout_lake)} == {2024, 2025}
    assert holdout.count(holdout_lake) == 1
    (record,) = holdout.records(holdout_lake)
    assert record["reason"] == reason
    assert record["seasons"] == [2024, 2025]
    assert record["spec_hash"] == harness.spec_hash(ModelSpec.model_validate(FIXED))
    assert record["at"]
    assert "Holdout runs so far: 1" in capsys.readouterr().out

    assert engine(*argv, "--holdout", "--reason", "Second look") == 0
    assert holdout.count(holdout_lake) == 2


def test_the_holdout_flag_without_a_holdout_season_is_refused(
    holdout_lake: LocalLake, tmp_path: Path
) -> None:
    spec = spec_file(tmp_path, FIXED)
    argv = ["backtest", "--spec", spec, "--seasons", "2023", "--model", "stub"]
    assert engine(*argv, "--holdout", "--reason", "nothing locked here") == 2
    assert holdout.count(holdout_lake) == 0
