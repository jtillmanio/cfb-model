"""`engine rate` (TASK-035): a model run, its ratings and its predictions, inserted for one week.

The backtest fixture's 2022-2023 seasons are published into the test DB through `db_conn`
(rolled back) as `PUBLISH`, a source no real publish uses, and rated under `NAME`, a model name
the fixture's `power` versions don't use (D-135's live-row unique index). The CLI tests only
refuse, so they commit nothing."""

from __future__ import annotations

import json
import math
from dataclasses import replace
from datetime import datetime, time, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from lake_fixture import (
    backtest_game,
    engine,
    staged,
    write_backtest_repull,
    write_backtest_seasons,
)
from sqlalchemy import Connection, text

from engine import backtest
from engine.backtest import harness
from engine.core.inputs import INPUT_IDS
from engine.core.interfaces import GameContext, Prediction, Ratings
from engine.core.spec import ModelSpec
from engine.ingest.lake import LocalLake
from engine.publish import models
from engine.publish.staging import publish_lake
from engine.transform import rebuild
from engine.transform.features import KICKOFF, PointInTimeError
from engine.transform.staging import connect

PUBLISH = "manual"
NAME = "pytest-power"
SEASON, WEEK = 2023, 5
CANCELED = "401756847"  # Kansas-Fresno State's week-1 id: its week-5 copy is canceled (TASK-044)
TBA = "401754516"  # its week-5 copy is re-pulled as TBA (TASK-044)
SPEC_FILE = Path(__file__).parents[1] / "specs" / "power-v1.json"
SPEC = ModelSpec.model_validate_json(SPEC_FILE.read_text("utf-8"))
# One candidate per tuned setting, as a backtest's run.json records them for a season.
CHOICES = {path: values[0] for path, values in SPEC.tunables().items()}


@pytest.fixture
def published(lake: LocalLake, db_conn: Connection) -> LocalLake:
    write_backtest_seasons(lake)
    rebuild(lake)
    publish_lake(lake, db_conn, PUBLISH)
    return lake


def _rate(lake: LocalLake, conn: Connection, **kwargs: Any) -> models.RunSummary:
    return models.rate(
        lake,
        conn,
        kwargs.pop("spec", SPEC),
        kwargs.pop("choices", CHOICES),
        season=SEASON,
        week=WEEK,
        name=NAME,
        version="v1.0",
        source=kwargs.pop("source", PUBLISH),
        **kwargs,
    )


def _run(conn: Connection, run_id: int) -> dict[str, Any]:
    return dict(
        conn.execute(text("SELECT * FROM model_runs WHERE id = :r"), {"r": run_id}).one()._mapping
    )


def _outputs(conn: Connection, run_id: int) -> tuple[list[Any], list[Any]]:
    ratings = conn.execute(
        text(
            "SELECT team_id, season, week, as_of, rating, prior_weight, created_at"
            " FROM team_ratings WHERE model_run_id = :r ORDER BY team_id"
        ),
        {"r": run_id},
    ).all()
    predictions = conn.execute(
        text(
            "SELECT id, game_id, pred_margin, home_win_prob, margin_sd, drivers"
            " FROM predictions WHERE model_run_id = :r ORDER BY game_id"
        ),
        {"r": run_id},
    ).all()
    return list(ratings), list(predictions)


def _week(history: harness.History) -> harness.Week:
    (week,) = [
        w
        for w in history.weeks
        if (w.season, w.season_type, w.week) == (SEASON, "regular", WEEK)
    ]
    return week


def _published_ids(conn: Connection, table: str, source_ids: set[str]) -> set[int]:
    return set(
        conn.execute(
            text(f"SELECT id FROM {table} WHERE source = :s AND source_id = ANY(:ids)"),
            {"s": PUBLISH, "ids": sorted(source_ids)},
        ).scalars()
    )


def test_rate_inserts_a_run_and_a_rerun_inserts_another(
    published: LocalLake, db_conn: Connection
) -> None:
    """AC-1."""
    history = harness.load(published)
    as_of = _week(history).as_of
    played = [g for g in history.results if g.kickoff + harness._FINISHED <= as_of]
    teams = {str(t) for g in played for t in (g.home_team, g.away_team)}
    week_games = {
        str(g.game_id)
        for g in history.results
        if (g.season, g.season_type, g.week) == (SEASON, "regular", WEEK)
    }
    assert teams and len(week_games) == 5

    first = _rate(published, db_conn)

    run = _run(db_conn, first.run_id)
    assert (run["status"], run["run_type"]) == ("succeeded", "adhoc")
    assert (run["season"], run["week"], run["as_of"]) == (SEASON, WEEK, as_of)
    assert run["error"] is None
    params = run["fitted_params"]
    assert isinstance(params["home_field"], float) and params["home_field"] != 0
    assert params["choices"] == CHOICES
    ratings, predictions = _outputs(db_conn, first.run_id)
    assert {r.team_id for r in ratings} == _published_ids(db_conn, "teams", teams)
    assert {(r.season, r.week, r.as_of) for r in ratings} == {(SEASON, WEEK, as_of)}
    assert {p.game_id for p in predictions} == _published_ids(db_conn, "games", week_games)
    for p in predictions:
        assert math.isclose(sum(d["points"] for d in p.drivers), p.pred_margin)
        assert p.margin_sd == params["margin_sd"]
    version = db_conn.execute(
        text("SELECT model_version_id FROM model_runs WHERE id = :r"), {"r": first.run_id}
    ).scalar_one()
    assert db_conn.execute(
        text("SELECT name, version, status, spec FROM model_versions WHERE id = :v"),
        {"v": version},
    ).one() == (NAME, "v1.0", "dev", SPEC.model_dump(mode="json"))
    assert (first.ratings, first.predictions) == (len(ratings), len(predictions))

    second = _rate(published, db_conn)

    assert second.run_id != first.run_id
    assert _run(db_conn, second.run_id)["model_version_id"] == version
    assert _outputs(db_conn, first.run_id) == (ratings, predictions)
    again, repredicted = _outputs(db_conn, second.run_id)
    assert [(r.team_id, r.rating) for r in again] == [(r.team_id, r.rating) for r in ratings]
    assert {p.game_id for p in repredicted} == {p.game_id for p in predictions}
    assert not {p.id for p in repredicted} & {p.id for p in predictions}


def test_rate_refuses_a_version_whose_spec_differs(
    published: LocalLake, db_conn: Connection
) -> None:
    _rate(published, db_conn)
    runs = db_conn.execute(text("SELECT count(*) FROM model_runs")).scalar_one()
    other = SPEC.model_copy(update={"home_field": 3.0})

    with pytest.raises(models.RateRefused, match="different spec"):
        _rate(published, db_conn, spec=other)

    assert db_conn.execute(text("SELECT count(*) FROM model_runs")).scalar_one() == runs


def test_rate_refuses_a_week_with_no_staged_games(
    published: LocalLake, db_conn: Connection
) -> None:
    with pytest.raises(models.RateRefused, match="week 30"):
        models.rate(
            published, db_conn, SPEC, CHOICES, season=SEASON, week=30, name=NAME, version="v1.0"
        )


def test_rate_refuses_teams_that_arent_published(
    published: LocalLake, db_conn: Connection
) -> None:
    runs = db_conn.execute(text("SELECT count(*) FROM model_runs")).scalar_one()

    with pytest.raises(models.RateRefused, match="engine publish"):
        _rate(published, db_conn, source="cfbd-not-published")

    assert db_conn.execute(text("SELECT count(*) FROM model_runs")).scalar_one() == runs


class _Broken:
    """A power model whose fit fails, or whose ratings or predictions aren't finite."""

    reads = frozenset({"games"})

    def __init__(self, inner: Any, how: str) -> None:
        self.inner, self.how = inner, how

    def fit(self, games: Any, as_of: datetime) -> Ratings:
        if self.how == "raise":
            raise ArithmeticError("the solve diverged")
        ratings = self.inner.fit(games, as_of)
        if self.how == "nan_rating":
            team = next(iter(ratings.teams))
            return Ratings(ratings.as_of, {**ratings.teams, team: math.nan}, ratings.params)
        if self.how == "nan_unit":  # TASK-038: a unit `components` (jsonb) can't hold
            team = next(iter(ratings.teams))
            units = {team: {"epa_per_play": (math.nan, 0.0)}}
            return Ratings(ratings.as_of, ratings.teams, ratings.params, units)
        if self.how == "prior_weight_above_one":  # finite, but prior_weight's CHECK refuses it
            return Ratings(ratings.as_of, ratings.teams, {**ratings.params, "prior_weight": 1.5})
        return ratings

    def predict(self, game: GameContext, ratings: Ratings, as_of: datetime) -> Prediction:
        p = self.inner.predict(game, ratings, as_of)
        if self.how == "inf_margin":
            return Prediction(math.inf, p.margin_sd, p.home_win_prob, p.drivers)
        if self.how == "zero_sd":  # finite, but margin_sd's CHECK refuses it
            return Prediction(p.pred_margin, 0.0, p.home_win_prob, p.drivers)
        if self.how == "prob_above_one":
            return Prediction(p.pred_margin, p.margin_sd, 1.5, p.drivers)
        return p


@pytest.mark.parametrize(
    ("how", "error"),
    [
        ("raise", "the solve diverged"),
        ("nan_rating", "rating"),
        ("nan_unit", "epa_per_play"),
        ("inf_margin", "pred_margin"),
        ("zero_sd", "margin_sd"),
        ("prob_above_one", "home_win_prob"),
        ("prior_weight_above_one", "prior_weight"),
    ],
)
def test_failed_fit_records_a_failed_run_without_outputs(
    published: LocalLake,
    db_conn: Connection,
    monkeypatch: pytest.MonkeyPatch,
    how: str,
    error: str,
) -> None:
    """AC-5: the run is recorded `failed` with its error; no ratings or predictions."""
    power = backtest.MODELS["power"]
    monkeypatch.setitem(backtest.MODELS, "power", lambda spec: _Broken(power(spec), how))

    summary = _rate(published, db_conn)

    run = _run(db_conn, summary.run_id)
    assert run["status"] == "failed"
    assert error in run["error"]
    assert run["finished_at"] is not None
    assert _outputs(db_conn, summary.run_id) == ([], [])
    assert (summary.status, summary.ratings, summary.predictions) == ("failed", 0, 0)


def test_a_point_in_time_violation_raises_and_writes_nothing(
    published: LocalLake, db_conn: Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Hard rule 4: a fit given a game that hadn't finished by `as_of` fails the check; it isn't
    recorded as an ordinary failed fit."""
    runs = db_conn.execute(text("SELECT count(*) FROM model_runs")).scalar_one()
    monkeypatch.setattr(harness, "fit_games", lambda history, as_of: history.results)

    with pytest.raises(PointInTimeError, match="point-in-time"):
        _rate(published, db_conn)

    assert db_conn.execute(text("SELECT count(*) FROM model_runs")).scalar_one() == runs


def test_canceled_and_postponed_games_are_not_predicted(
    published: LocalLake, db_conn: Connection
) -> None:
    """A prediction is permanent, so a game that won't be played gets none."""
    import pyarrow as pa
    import pyarrow.parquet as pq

    path = published.root / "staging" / "games.parquet"
    games = pq.read_table(path).to_pylist()
    week = [g for g in games if (g["season"], g["season_type"], g["week"]) == (2023, "regular", 5)]
    off = {week[0]["source_id"]: "canceled", week[1]["source_id"]: "postponed"}
    for g in games:
        g["status"] = off.get(g["source_id"], g["status"])
    pq.write_table(pa.Table.from_pylist(games, pq.read_schema(path)), path)

    summary = _rate(published, db_conn)

    predicted = db_conn.execute(
        text(
            "SELECT g.source_id FROM predictions p JOIN games g ON g.id = p.game_id"
            " WHERE p.model_run_id = :r"
        ),
        {"r": summary.run_id},
    ).scalars()
    assert set(predicted) == {g["source_id"] for g in week} - set(off)


def _predicted(conn: Connection, run_id: int) -> set[str]:
    return set(
        conn.execute(
            text(
                "SELECT g.source_id FROM predictions p JOIN games g ON g.id = p.game_id"
                " WHERE p.model_run_id = :r"
            ),
            {"r": run_id},
        ).scalars()
    )


def test_a_canceled_game_from_the_lake_is_not_predicted(
    lake: LocalLake, db_conn: Connection
) -> None:
    """TASK-044 AC-2: a week-5 game CFBD still lists as uncompleted and unscored by a /games pull
    8 days after its start is staged canceled (D-121) and gets no prediction; every other game
    of the week gets one."""
    write_backtest_seasons(lake)
    game = backtest_game(SEASON, "regular", WEEK, CANCELED)
    start = datetime.fromisoformat(game["startDate"])
    unplayed = {**game, "completed": False, "homePoints": None, "awayPoints": None}
    write_backtest_repull(lake, SEASON, "regular", WEEK, [unplayed], start + timedelta(days=8))
    rebuild(lake)
    publish_lake(lake, db_conn, PUBLISH)
    week = [
        g
        for g in staged(lake, "games").to_pylist()
        if (g["season"], g["season_type"], g["week"]) == (SEASON, "regular", WEEK)
    ]
    canceled = {g["source_id"] for g in week if g["status"] == "canceled"}
    assert canceled == {str(game["id"])} and len(week) == 5

    summary = _rate(lake, db_conn)

    assert _predicted(db_conn, summary.run_id) == {g["source_id"] for g in week} - canceled


def test_rate_takes_the_weeks_games_from_the_harness(
    published: LocalLake, db_conn: Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    """TASK-044 AC-3: `engine rate` predicts the week's staged contexts as `harness.load` keeps
    them, not its own read of staged games."""
    load = harness.load
    dropped: list[int] = []

    def fewer(lake: LocalLake) -> harness.History:
        history = load(lake)
        weeks = []
        for w in history.weeks:
            if (w.season, w.season_type, w.week) == (SEASON, "regular", WEEK):
                dropped.append(w.contexts[0].game_id)
                w = replace(w, contexts=w.contexts[1:])
            weeks.append(w)
        return replace(history, weeks=tuple(weeks))

    monkeypatch.setattr(harness, "load", fewer)
    week = {str(g.game_id) for g in load(published).results if (g.season, g.week) == (SEASON, WEEK)}

    summary = _rate(published, db_conn)

    assert len(week) == 5 and len(dropped) == 1
    assert _predicted(db_conn, summary.run_id) == week - {str(dropped[0])}


def test_rate_takes_a_tba_kickoff_from_the_harness(lake: LocalLake) -> None:
    """TASK-044 AC-3: a TBA game's kickoff in `engine rate` is `features.KICKOFF`'s, the end of
    its Eastern `game_date`, and `publish/models.py` keeps no copy of the rule."""
    write_backtest_seasons(lake)
    game = backtest_game(SEASON, "regular", WEEK, TBA)
    start = datetime.fromisoformat(game["startDate"])
    tba = {**game, "startTimeTBD": True}
    write_backtest_repull(lake, SEASON, "regular", WEEK, [tba], start + timedelta(days=2))
    rebuild(lake)
    con = connect()
    con.register("games", staged(lake, "games"))
    (expected,) = (
        con.execute(f"SELECT {KICKOFF} AS k FROM games WHERE source_id = ?", [str(game["id"])])
        .arrow()
        .read_all()
        .column("k")
        .to_pylist()
    )

    fitted = models.fit_week(lake, SPEC, CHOICES, season=SEASON, week=WEEK)

    assert fitted.outputs is not None
    kickoffs = {g.game_id: g.kickoff for g, _ in fitted.outputs[1]}
    date = start.astimezone(ZoneInfo("America/New_York")).date()
    end_of_date = datetime.combine(date + timedelta(days=1), time(), ZoneInfo("America/New_York"))
    assert kickoffs[game["id"]] == expected == end_of_date
    assert not hasattr(models, "_kickoff")


def test_rate_refuses_a_version_whose_stored_spec_is_invalid(
    published: LocalLake, db_conn: Connection
) -> None:
    db_conn.execute(
        text(
            "INSERT INTO model_versions (sport_id, market, name, version, spec,"
            " spec_schema_version, created_by, status)"
            " VALUES ('cfb', 'spread', :n, 'v1.0', '{\"base\": \"nope\"}', 1, 'user', 'dev')"
        ),
        {"n": NAME},
    )

    with pytest.raises(models.RateRefused, match="isn't a valid ModelSpec"):
        _rate(published, db_conn)


def _run_json(**overrides: Any) -> dict[str, Any]:
    return {"spec_hash": harness.spec_hash(SPEC), "choices": {str(SEASON): CHOICES}} | overrides


def test_settings_come_from_the_backtest_run_for_the_season() -> None:
    assert models.settings(SPEC, _run_json(), SEASON) == CHOICES


def test_settings_of_a_resolved_spec_need_no_run() -> None:
    assert models.settings(SPEC.resolve(CHOICES), None, SEASON) == {}


@pytest.mark.parametrize(
    ("run", "match"),
    [
        (None, "--choices"),
        (_run_json(spec_hash="0" * 64), "different spec"),
        (_run_json(choices={"2022": CHOICES}), "2023"),
        ([CHOICES], "isn't a backtest run"),
        (_run_json(choices=[CHOICES]), "isn't a backtest run"),
        (_run_json(choices={str(SEASON): [1.0]}), "isn't a backtest run"),
        (_run_json(choices={str(SEASON): {path: "high" for path in CHOICES}}), "isn't a number"),
    ],
)
def test_settings_refuse(run: Any, match: str) -> None:
    with pytest.raises(models.RateRefused, match=match):
        models.settings(SPEC, run, SEASON)


def _refuse_postgres(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("engine rate opened a database")

    monkeypatch.setattr(models, "make_engine", refuse)


@pytest.mark.parametrize("target", ["dev", "test"])
def test_rate_refuses_under_live(
    lake: LocalLake,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    target: str,
) -> None:
    """AC-5: LIVE=true refuses before anything is opened or written."""
    monkeypatch.setenv("LIVE", "true")
    _refuse_postgres(monkeypatch)

    code = engine(
        "rate", "--spec", str(SPEC_FILE), "--season", "2023", "--week", "5", "--target", target
    )

    assert code == 2
    assert "LIVE" in capsys.readouterr().err


def test_rate_cli_refuses_a_tuned_spec_without_choices(
    lake: LocalLake, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _refuse_postgres(monkeypatch)

    code = engine(
        "rate", "--spec", str(SPEC_FILE), "--season", "2023", "--week", "5", "--target", "test"
    )

    assert code == 2
    assert "--choices" in capsys.readouterr().err


def test_rate_cli_refuses_without_the_dev_url(
    lake: LocalLake,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    run_file = tmp_path / "run.json"
    run_file.write_text(json.dumps(_run_json()), "utf-8")
    monkeypatch.delenv("DATABASE_URL_UNPOOLED", raising=False)
    _refuse_postgres(monkeypatch)

    code = engine(
        "rate",
        *("--spec", str(SPEC_FILE), "--choices", str(run_file)),
        *("--season", "2023", "--week", "5", "--target", "dev"),
    )

    assert code == 2
    assert "DATABASE_URL_UNPOOLED" in capsys.readouterr().err


def test_rate_cli_publishes_through_one_transaction(
    lake: LocalLake,
    db_conn: Connection,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The command reads the backtest run's settings and publishes on the target's direct URL;
    here the target's transaction is the rolled-back test connection."""
    write_backtest_seasons(lake)
    rebuild(lake)
    publish_lake(lake, db_conn, PUBLISH)
    run_file = tmp_path / "run.json"
    run_file.write_text(json.dumps(_run_json()), "utf-8")
    opened: list[str] = []

    class _Engine:
        def begin(self) -> Any:
            from contextlib import nullcontext

            return nullcontext(db_conn)

    def make_engine(url: str) -> Any:
        opened.append(url)
        return _Engine()

    steps: list[str] = []
    fit_week = models.fit_week

    def fit_first(*args: Any, **kwargs: Any) -> models.FittedWeek:
        assert not opened, "the transaction opened before the fit"
        steps.append("fit")
        return fit_week(*args, **kwargs)

    monkeypatch.setattr(models, "fit_week", fit_first)
    monkeypatch.setattr(models, "make_engine", make_engine)
    monkeypatch.setattr(models, "SOURCE", PUBLISH)
    monkeypatch.setenv("TEST_DATABASE_URL", "postgresql://test-host/cfb_test")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("DATABASE_URL_UNPOOLED", raising=False)

    code = engine(
        "rate",
        *("--spec", str(SPEC_FILE), "--choices", str(run_file)),
        *("--season", "2023", "--week", "5", "--target", "test", "--name", NAME),
    )

    assert code == 0, capsys.readouterr().err
    assert steps == ["fit"]
    assert opened == ["postgresql://test-host/cfb_test"]
    out = capsys.readouterr().out
    assert "succeeded" in out
    assert db_conn.execute(
        text(
            "SELECT count(*) FROM model_runs r JOIN model_versions v ON v.id = r.model_version_id"
            " WHERE v.name = :n AND r.status = 'succeeded'"
        ),
        {"n": NAME},
    ).scalar_one() == 1


# TASK-038 AC-6: an efficiency run writes each team's units in points; a power run doesn't.

EFFICIENCY = ModelSpec.model_validate(
    {
        "base": "efficiency",
        "inputs": [{"stat": s} for s in INPUT_IDS],
        "hyperparameters": {"ridge_alpha": 2, "recency_half_life_weeks": 16},
        "shrink_toward": "tier",
        "prior": {"components": ["last_season"], "regression": 0.1, "decay": {"type": "fitted"}},
        "distribution": "empirical",
        "picks": {"min_edge_pts": 3.0, "min_prob": 0.55, "tiers": {"A": 5.0, "B": 3.5, "C": 2.5}},
    }
)


def _units(conn: Connection, run_id: int) -> list[Any]:
    return list(
        conn.execute(
            text(
                "SELECT rating, off_rating, def_rating, st_rating, components"
                " FROM team_ratings WHERE model_run_id = :r ORDER BY team_id"
            ),
            {"r": run_id},
        ).all()
    )


def test_an_efficiency_run_writes_offense_and_defense_in_points(
    published: LocalLake, db_conn: Connection
) -> None:
    summary = models.rate(
        published,
        db_conn,
        EFFICIENCY,
        {},
        season=SEASON,
        week=WEEK,
        name="pytest-efficiency",
        version="v1.0",
        source=PUBLISH,
    )

    assert summary.status == "succeeded", summary.error
    rows = _units(db_conn, summary.run_id)
    assert len(rows) == summary.ratings > 0
    for r in rows:
        assert r.st_rating is None
        assert r.off_rating + r.def_rating == pytest.approx(r.rating, abs=1e-9)
        assert set(r.components) == set(INPUT_IDS)  # jsonb keeps no key order
        assert all(set(unit) == {"off", "def"} for unit in r.components.values())
        assert math.fsum(u["off"] for u in r.components.values()) == pytest.approx(
            r.off_rating, abs=1e-9
        )
        assert math.fsum(u["def"] for u in r.components.values()) == pytest.approx(
            r.def_rating, abs=1e-9
        )
    _, predictions = _outputs(db_conn, summary.run_id)
    assert len(predictions) == summary.predictions > 0
    for p in predictions:
        assert len(p.drivers) == 1 + 2 * len(INPUT_IDS)
        assert math.fsum(d["points"] for d in p.drivers) == pytest.approx(p.pred_margin, abs=1e-9)
    assert "margin_weight_3" in _run(db_conn, summary.run_id)["fitted_params"]


def test_a_power_run_leaves_the_units_null(published: LocalLake, db_conn: Connection) -> None:
    summary = _rate(published, db_conn)

    rows = _units(db_conn, summary.run_id)
    assert rows
    assert {(r.off_rating, r.def_rating, r.st_rating, r.components) for r in rows} == {
        (None, None, None, None)
    }
