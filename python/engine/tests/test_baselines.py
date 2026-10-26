"""The Rung 0 baselines (TASK-032; docs/04-model.md § 2, § 9.2-9.3, D-133): home field only,
last season carried over, the closing line, and SP+/FPI, scored by the walk-forward harness on
the same games as any model.
"""

from __future__ import annotations

import io
import json
import statistics
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq
import pytest
from lake_fixture import (
    FIXTURE,
    benchmark_pulls,
    benchmark_rating,
    engine,
    fixture_key,
    staged,
    write,
    write_backtest_seasons,
    write_benchmarks,
)

from engine import backtest
from engine.backtest import baselines, harness
from engine.backtest.baselines import (
    HINDSIGHT,
    UNRATED,
    UNSEEN,
    BenchmarkRating,
    ClosingLine,
    FittedHomeField,
    HomeField,
    LastSeason,
)
from engine.backtest.stub import MeanMargin
from engine.core.interfaces import GameContext, GameResult
from engine.core.spec import ModelSpec
from engine.ingest.lake import LocalLake, raw_folder, raw_key
from engine.transform import rebuild
from engine.transform.features import PointInTimeError
from engine.transform.market import closing_lines

PICKS = {"min_edge_pts": 3.0, "min_prob": 0.55, "tiers": {"A": 5.0, "B": 3.5, "C": 2.5}}
# No recency decay, so the stub's ratings don't depend on the date they're fit at.
CAP: dict[str, Any] = {
    "base": "power",
    "hyperparameters": {"margin_cap": 28},
    "picks": PICKS,
}
SPEC = ModelSpec.model_validate(CAP)
KANSAS_FRESNO_STATE = "401756847"


def played(
    season: int, day: int, home: int, away: int, margin: int, *, neutral: bool = False
) -> GameResult:
    """A final game whose home team won by `margin`."""
    return GameResult(
        game_id=season * 1000 + day,
        season=season,
        season_type="regular",
        week=day,
        kickoff=datetime(season, 9, day, 18, tzinfo=UTC),
        home_team=home,
        away_team=away,
        neutral_site=neutral,
        home_points=30 + margin,
        away_points=30,
    )


def context(game_id: int, season: int, home: int, away: int, neutral: bool = False) -> GameContext:
    return GameContext(
        game_id=game_id,
        season=season,
        season_type="regular",
        week=1,
        kickoff=datetime(season, 10, 1, 18, tzinfo=UTC),
        home_team=home,
        away_team=away,
        neutral_site=neutral,
    )


def predicted(model: Any, games: list[GameResult], game: GameContext) -> float:
    as_of = datetime(game.season, 9, 30, tzinfo=UTC)
    return float(model.predict(game, model.fit(games, as_of), as_of).pred_margin)


def scored(lake: LocalLake, model: Any, seasons: list[int]) -> dict[str, dict[str, Any]]:
    """One baseline's results rows by game, from the harness."""
    run = harness.run(SPEC, lambda _: model, harness.load(lake), seasons, tune_from=2022)
    return {r["game_source_id"]: r for r in run.rows}


def written(lake: LocalLake) -> list[dict[str, Any]]:
    (key,) = [k for k in lake.walk("backtests") if k.endswith("/predictions.parquet")]
    return pq.read_table(io.BytesIO(lake.read(key))).to_pylist()


@pytest.fixture
def backtest_lake(empty_lake: LocalLake) -> LocalLake:
    write_backtest_seasons(empty_lake)
    write_benchmarks(empty_lake)
    rebuild(empty_lake)
    return empty_lake


# AC-1


def test_home_field_is_the_mean_home_margin_of_earlier_seasons() -> None:
    games = [
        played(2021, 1, 1, 2, 10),
        played(2021, 2, 3, 4, 4),
        played(2021, 3, 1, 3, 30, neutral=True),  # a neutral-site game says nothing about home
        played(2022, 1, 1, 2, 100),
    ]
    model = HomeField()
    assert predicted(model, games, context(1, 2022, 1, 2)) == pytest.approx(7.0)
    assert predicted(model, games, context(2, 2022, 1, 2, neutral=True)) == 0.0
    # 2022's own games count for 2023 and after, never for 2022.
    assert predicted(model, games, context(3, 2023, 1, 2)) == pytest.approx(38.0)
    # The first season has nothing earlier to fit on.
    assert predicted(model, games, context(4, 2021, 1, 2)) == 0.0


def test_home_field_ignores_a_change_to_the_scored_season() -> None:
    games = [played(2021, 1, 1, 2, 10), played(2022, 1, 1, 2, 50), played(2022, 2, 2, 3, -20)]
    changed = [games[0], played(2022, 1, 1, 2, -9), played(2022, 2, 2, 3, 40)]
    game = context(1, 2022, 1, 2)
    assert predicted(HomeField(), games, game) == predicted(HomeField(), changed, game) == 10.0


# AC-2


def test_last_season_rates_each_team_on_the_year_before_without_regressing() -> None:
    last = [played(2021, 1, 1, 2, 12), played(2021, 2, 2, 3, 6), played(2021, 3, 1, 3, 9)]
    games = [*last, played(2022, 1, 3, 1, 40), played(2022, 2, 2, 1, 40)]
    final = MeanMargin(SPEC).fit(last, datetime(2022, 1, 1, tzinfo=UTC))
    hfa = final.params["home_field"]
    model = LastSeason(MeanMargin(SPEC))

    seen = context(1, 2022, 1, 2)
    expected = final.teams[1] - final.teams[2] + hfa
    assert predicted(model, games, seen) == pytest.approx(expected)
    neutral = context(2, 2022, 1, 2, neutral=True)
    assert predicted(model, games, neutral) == pytest.approx(final.teams[1] - final.teams[2])
    # A team with no 2021 rating gets the stub's rating for a team it hasn't seen: 0.
    stranger = context(3, 2022, 1, 99)
    assert predicted(model, games, stranger) == pytest.approx(final.teams[1] + hfa)
    as_of = datetime(2022, 9, 30, tzinfo=UTC)
    assert model.note(stranger, model.fit(games, as_of)) == UNSEEN
    assert model.note(seen, model.fit(games, as_of)) is None

    # Changing 2022's games changes nothing about 2022's predictions.
    moved = [*last, played(2022, 1, 3, 1, -40), played(2022, 2, 2, 1, -40)]
    assert predicted(LastSeason(MeanMargin(SPEC)), moved, seen) == pytest.approx(expected)


def test_last_season_and_home_field_through_the_harness_ignore_the_scored_season(
    empty_lake: LocalLake, tmp_path: Path
) -> None:
    write_backtest_seasons(empty_lake)
    rebuild(empty_lake)
    models = {"last": lambda: LastSeason(MeanMargin(SPEC)), "home": HomeField}
    first = {name: scored(empty_lake, make(), [2022, 2023]) for name, make in models.items()}

    # The same lake with one 2023 game rescored 3-45.
    other = LocalLake(tmp_path / "rescored")
    write_backtest_seasons(other, rescore=(2023, "regular", 5, KANSAS_FRESNO_STATE))
    rebuild(other)
    for name, make in models.items():
        again = scored(other, make(), [2022, 2023])
        assert first[name].keys() == again.keys()
        for game, row in first[name].items():
            assert again[game]["pred_margin"] == row["pred_margin"], (name, game)
    # Season 2022 has no season before it: every team is unseen, so the line is just 0.
    first_season = [r for r in first["last"].values() if r["season"] == 2022]
    assert {r["pred_margin"] for r in first_season} == {0.0}
    assert {r["note"] for r in first_season} == {UNSEEN}


def test_last_season_wraps_the_model_registered_under_the_specs_base(
    empty_lake: LocalLake, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_backtest_seasons(empty_lake)
    rebuild(empty_lake)
    spec = tmp_path / "spec.json"
    spec.write_text(json.dumps(CAP), "utf-8")
    argv = ["backtest", "--spec", str(spec), "--seasons", "2022-2023", "--model", "last_season"]

    monkeypatch.delitem(backtest.MODELS, "power")
    assert engine(*argv) == 2  # nothing to wrap

    monkeypatch.setitem(backtest.MODELS, "power", MeanMargin)
    assert engine(*argv) == 0
    rows = written(empty_lake)
    assert {r["note"] for r in rows if r["season"] == 2022} == {UNSEEN}
    assert {r["note"] for r in rows if r["season"] == 2023} == {None}


# TASK-033: home field only is the home-field edge the model under test fits (04 § 9.6).


def test_home_field_predicts_the_wrapped_models_fitted_edge_entering_each_week() -> None:
    games = [
        played(2021, 1, 1, 2, 10),
        played(2021, 2, 3, 4, 4),
        played(2022, 1, 1, 2, 30),
        played(2022, 2, 2, 3, -2),
    ]
    model = FittedHomeField(MeanMargin(SPEC))
    for day in (1, 2, 3):  # entering 2022 day 1, 2 and 3: the fit grows with the season
        as_of = datetime(2022, 9, day, 12, tzinfo=UTC)
        seen = [g for g in games if g.kickoff < as_of]
        fitted = MeanMargin(SPEC).fit(seen, as_of).params["home_field"]
        ratings = model.fit(seen, as_of)
        prediction = model.predict(context(1, 2022, 1, 2), ratings, as_of)
        assert prediction.pred_margin == fitted
        # σ: 2021's margins around that edge (10 and 4 at home).
        spread = statistics.stdev([10 - fitted, 4 - fitted])
        assert prediction.margin_sd == pytest.approx(spread)
        neutral = context(2, 2022, 1, 2, neutral=True)
        assert model.predict(neutral, ratings, as_of).pred_margin == 0.0
    # Unlike the mean-margin `HomeField`, this season's games move it.
    assert fitted != HomeField().predict(
        context(1, 2022, 1, 2), HomeField().fit(games, as_of), as_of
    ).pred_margin


def test_home_field_wraps_the_model_registered_under_the_specs_base(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from engine.models.power import PowerRatings

    built = backtest.MODELS["home_field"](SPEC)
    assert isinstance(built, FittedHomeField) and isinstance(built.inner, PowerRatings)
    monkeypatch.delitem(backtest.MODELS, "power")
    with pytest.raises(harness.RefusedError, match="home_field"):
        backtest.MODELS["home_field"](SPEC)
    with pytest.raises(harness.RefusedError, match="games alone"):
        FittedHomeField(HomeField())  # type: ignore[arg-type]


# AC-3


def test_closing_line_predicts_the_negative_closing_spread_and_names_its_source(
    empty_lake: LocalLake,
) -> None:
    # Kansas-Fresno State, 2022 week 1: a consensus book quoting -17 beside the other three.
    write_backtest_seasons(empty_lake, consensus=((2022, "regular", 1, KANSAS_FRESNO_STATE), -17.0))
    rebuild(empty_lake)
    rows = scored(empty_lake, ClosingLine(), [2022, 2023])

    lines = {
        r["game_source_id"]: r
        for r in closing_lines(staged(empty_lake, "games"), staged(empty_lake, "lines")).to_pylist()
    }
    assert len(rows) == 66 and rows.keys() <= lines.keys()
    for game, row in rows.items():
        assert row["pred_margin"] == -lines[game]["spread_home"]
        assert row["spread_source"] == lines[game]["source"]
    assert {r["spread_source"] for r in rows.values()} == {"consensus", "median"}
    consensus = [r["pred_margin"] for r in rows.values() if r["spread_source"] == "consensus"]
    assert consensus == [17.0]


# AC-4


def hfa_before(history: harness.History, season: int) -> float:
    margins = [r.margin for r in history.results if r.season < season and not r.neutral_site]
    return sum(margins) / len(margins) if margins else 0.0


@pytest.mark.parametrize("system", ["sp", "fpi"])
def test_benchmarks_use_only_ratings_known_before_kickoff(
    backtest_lake: LocalLake, system: str
) -> None:
    staged_rows = staged(backtest_lake, "benchmark_ratings").to_pylist()
    assert {r["known_at"] is None for r in staged_rows} == {True, False}
    assert all(r["team_source_id"] is not None for r in staged_rows)

    history = harness.load(backtest_lake)
    rows = scored(backtest_lake, BenchmarkRating(system), [2023])
    names = {t["source_id"]: t["school"] for t in staged(backtest_lake, "teams").to_pylist()}
    games = {g["source_id"]: g for g in staged(backtest_lake, "games").to_pylist()}
    mid_season, _ = benchmark_pulls(2023)
    hfa = hfa_before(history, 2023)

    known = hindsight = 0
    for game_id, row in rows.items():
        game = games[game_id]
        is_known = game["kickoff_at"] > mid_season
        home, away = (
            benchmark_rating(system, names[game[side]], final=not is_known)
            for side in ("home_source_id", "away_source_id")
        )
        expected = home - away + (0.0 if row["neutral_site"] else hfa)
        assert row["pred_margin"] == pytest.approx(expected), game_id
        assert row["note"] == (None if is_known else HINDSIGHT), game_id
        known += is_known
        hindsight += not is_known
    assert known and hindsight  # the fixture's mid-season pull falls inside the season


def test_a_hindsight_result_is_never_a_baseline_beaten(backtest_lake: LocalLake) -> None:
    rows = list(scored(backtest_lake, BenchmarkRating("sp"), [2023]).values())
    kept = baselines.comparable(rows)
    assert 0 < len(kept) < len(rows)
    assert all(r["note"] != HINDSIGHT for r in kept)
    hindsight = {r["game_source_id"] for r in rows if r["note"] == HINDSIGHT}
    assert hindsight.isdisjoint(r["game_source_id"] for r in kept)


def benchmark(known_at: datetime | None, rating: float, team: int = 1) -> harness.Benchmark:
    return harness.Benchmark(
        "sp", 2023, team, rating, known_at or datetime(2024, 2, 1, tzinfo=UTC), known_at
    )


def rate(rows: list[harness.Benchmark], game: GameContext, earliest: datetime) -> Any:
    """`BenchmarkRating("sp")`'s rating of the home team (team 1) of `game`."""
    model = BenchmarkRating("sp")
    model.use({"benchmark_ratings": harness.BenchmarkInput(tuple(rows), {game.game_id: earliest})})
    return model._rating(game, 1)  # pyright: ignore[reportPrivateUsage]


def test_a_rating_published_after_kickoff_is_never_known_before_it() -> None:
    game = context(1, 2023, 1, 2)  # 2023-10-01 18:00
    early = benchmark(datetime(2023, 9, 20, tzinfo=UTC), 5.0)
    late = benchmark(datetime(2023, 10, 20, tzinfo=UTC), 9.0)  # a mid-season pull, after the game
    final = benchmark(None, 12.0)
    assert rate([early, late, final], game, game.kickoff) == (5.0, False)
    assert rate([late, final], game, game.kickoff) == (12.0, True)  # the season-final row
    assert rate([late], game, game.kickoff) == (None, False)  # nothing known, nothing final


def test_a_rating_published_on_a_tba_games_date_is_not_known_before_it() -> None:
    # TBA: `kickoff` is the end of the Eastern date (the GameContext's), but the game may have
    # kicked off at the start of it, so a pull at noon that day is hindsight.
    game = context(1, 2023, 1, 2)
    start_of_date = game.kickoff - timedelta(hours=18)
    pulled = benchmark(game.kickoff - timedelta(hours=9), 7.0)
    final = benchmark(None, 12.0)
    assert rate([pulled, final], game, start_of_date) == (12.0, True)
    assert rate([pulled, final], game, game.kickoff) == (7.0, False)  # at the date's end it's known


def test_a_game_with_no_earliest_kickoff_is_refused_not_cut_off_late() -> None:
    game = context(1, 2023, 1, 2)
    model = BenchmarkRating("sp")
    model.use({"benchmark_ratings": harness.BenchmarkInput((benchmark(None, 1.0),), {})})
    with pytest.raises(PointInTimeError, match="game 1"):
        model._rating(game, 1)  # pyright: ignore[reportPrivateUsage]


def test_a_rating_not_published_before_the_cutoff_trips_the_point_in_time_check() -> None:
    game = context(1, 2023, 1, 2)
    for known_at in (None, game.kickoff, game.kickoff + timedelta(days=3)):
        with pytest.raises(PointInTimeError, match="game 1"):
            baselines.check_published(benchmark(known_at, 5.0), game, game.kickoff)
    baselines.check_published(benchmark(game.kickoff - timedelta(days=3), 5.0), game, game.kickoff)


def test_the_harness_gives_a_tba_game_the_start_of_its_date(backtest_lake: LocalLake) -> None:
    game = next(g for g in FIXTURE[fixture_key("games")]["records"] if str(g["id"]) == "401756846")
    tba = {**game, "id": 900199009, "week": 9, "season": 2022, "startTimeTBD": True}
    tba["startDate"] = "2022-10-25T04:00:00.000Z"  # CFBD's placeholder: Eastern midnight (EDT)
    params = {"classification": "fbs", "seasonType": "regular", "week": 9, "year": 2022}
    key = raw_key(raw_folder("games", 2022, 9), datetime(2022, 10, 27, 12, tzinfo=UTC))
    write(backtest_lake, key, [tba], params)
    rebuild(backtest_lake)

    history = harness.load(backtest_lake)

    assert history.earliest[900199009] == datetime(2022, 10, 25, 4, tzinfo=UTC)
    played = next(r for r in history.results if r.game_id == 900199009)
    assert played.kickoff == datetime(2022, 10, 26, 4, tzinfo=UTC)  # the end of its date
    regular = next(r for r in history.results if r.game_id != 900199009)
    assert history.earliest[regular.game_id] == regular.kickoff


def test_a_game_with_an_unrated_team_is_not_comparable() -> None:
    rows = [
        {"game_source_id": "a", "note": None},
        {"game_source_id": "b", "note": HINDSIGHT},
        {"game_source_id": "c", "note": UNRATED},
        {"game_source_id": "d", "note": f"{HINDSIGHT}; {UNRATED}"},
        {"game_source_id": "e", "note": UNSEEN},  # counted by the report, still a fair bar
    ]
    assert [r["game_source_id"] for r in baselines.comparable(rows)] == ["a", "e"]


def test_last_season_asserts_the_games_it_fits_on_had_finished() -> None:
    games = [played(2021, 1, 1, 2, 12)]  # 2021-09-01 18:00, finished 22:00
    model = LastSeason(MeanMargin(SPEC))
    too_soon = datetime(2021, 9, 1, 20, tzinfo=UTC)
    game = context(1, 2022, 1, 2)
    with pytest.raises(PointInTimeError, match="2022"):
        model.predict(game, model.fit(games, too_soon), too_soon)


def test_last_season_wraps_only_a_model_that_fits_on_games() -> None:
    with pytest.raises(harness.RefusedError, match="games alone"):
        LastSeason(ClosingLine())  # type: ignore[arg-type]


def test_a_benchmark_with_nothing_staged_is_refused(empty_lake: LocalLake) -> None:
    write_backtest_seasons(empty_lake)
    rebuild(empty_lake)
    with pytest.raises(harness.RefusedError, match="sp"):
        scored(empty_lake, BenchmarkRating("sp"), [2023])


# The inputs only a baseline may read


def reading(*names: str, baseline: bool) -> MeanMargin:
    """The stub model, claiming to read `names` besides the games."""
    attrs = {"reads": frozenset({"games", *names}), "baseline": baseline}
    return type("Reading", (MeanMargin,), attrs)(SPEC)


@pytest.mark.parametrize("name", ["closing_lines", "benchmark_ratings"])
def test_only_a_baseline_may_read_closing_lines_or_benchmarks(name: str) -> None:
    with pytest.raises(harness.RefusedError, match=name):
        harness.check_reads(reading(name, baseline=False))
    harness.check_reads(reading(name, baseline=True))


@pytest.mark.parametrize("name", ["lines", "hindsight_ratings", "weather"])
def test_no_baseline_reads_anything_else(name: str) -> None:
    with pytest.raises(harness.RefusedError, match=name):
        harness.check_reads(reading(name, baseline=True))


def test_the_baselines_are_registered_by_name() -> None:
    assert {"home_field", "last_season", "closing_line", "sp", "fpi"} <= backtest.MODELS.keys()
