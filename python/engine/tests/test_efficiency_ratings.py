"""Rung 2's ridge efficiency ratings and margin model (TASK-036; docs/04-model.md § 2 Rung 2,
§ 9.2, § 10.4): recovering known ratings, ridge shrinkage, the tier anchor, the margin model's
coefficients and its out-of-sample rule, the advanced-stat input's point-in-time check, and a
golden backtest of `engine/specs/efficiency-v1.json` on the TASK-030 fixture generator.
"""

from __future__ import annotations

import io
import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pyarrow.parquet as pq
import pytest
from lake_fixture import engine, write_backtest_seasons, write_preseason

from engine import backtest
from engine.backtest import harness, metrics
from engine.backtest.harness import TeamGameStat, TeamGameStats
from engine.core.interfaces import GameResult
from engine.core.spec import ModelSpec
from engine.ingest.lake import LocalLake
from engine.models.efficiency import EfficiencyRatings, MatchupRow, NoEarlierSeasonError
from engine.models.power import UnsupportedSpecError
from engine.sports.cfb.teams import EFFICIENCY_RULES, G5, POWER_4
from engine.transform import rebuild
from engine.transform.features import PointInTimeError

PICKS = {"min_edge_pts": 3.0, "min_prob": 0.55, "tiers": {"A": 5.0, "B": 3.5, "C": 2.5}}
STATS = ("epa_per_play", "success_rate")
FEATURES = ("ppa", "success_rate")
SPEC_FILE = Path(__file__).parents[1] / "specs" / "efficiency-v1.json"
GOLDEN = Path(__file__).parent / "fixtures" / "backtest_efficiency_golden.csv"
CONFERENCE = {POWER_4: "SEC", G5: "Sun Belt"}


def model(**spec: Any) -> EfficiencyRatings:
    data = {"base": "efficiency", "inputs": [{"stat": s} for s in STATS], "picks": PICKS, **spec}
    return EfficiencyRatings(ModelSpec.model_validate(data), EFFICIENCY_RULES)


def kickoff(season: int, week: int) -> datetime:
    """A "week" here is a day, so a long round robin stays inside its season."""
    return datetime(season, 9, 2, 19, tzinfo=UTC) + timedelta(days=week - 1)


class League:
    """Games and their per-game stats, generated from known ratings: each offense's value is
    `μ + off_O − def_D + h·s` exactly, so a fit at alpha 0 must give the ratings back."""

    MU = np.array([0.05, 0.42])
    HOME = np.array([0.03, 0.02])

    def __init__(self, ratings: dict[int, tuple[np.ndarray, np.ndarray]], tiers: dict[int, str]):
        self.ratings = ratings  # team -> (offense per stat, defense per stat)
        self.tiers = tiers
        self.games: list[GameResult] = []
        self.rows: dict[int, list[TeamGameStat]] = {}

    def value(self, offense: int, defense: int, site: int) -> np.ndarray:
        return self.MU + self.ratings[offense][0] - self.ratings[defense][1] + self.HOME * site

    def play(self, season: int, week: int, home: int, away: int, *, margin: int = 7) -> None:
        game_id = season * 100_000 + week * 1_000 + len(self.games)
        at = kickoff(season, week)
        self.games.append(
            GameResult(
                game_id=game_id,
                season=season,
                season_type="regular",
                week=week,
                kickoff=at,
                home_team=home,
                away_team=away,
                neutral_site=False,
                home_classification="fbs",
                away_classification="fbs",
                home_group=CONFERENCE[self.tiers[home]],
                away_group=CONFERENCE[self.tiers[away]],
                home_points=30 + margin,
                away_points=30,
            )
        )
        for offense, defense, site in ((home, away, 1), (away, home, -1)):
            values = self.value(offense, defense, site)
            self.rows.setdefault(season, []).append(
                TeamGameStat(
                    game_id,
                    season,
                    at,
                    offense,
                    defense,
                    site,
                    dict(zip(FEATURES, map(float, values), strict=True)),
                )
            )

    def stats(self) -> TeamGameStats:
        return TeamGameStats(
            {s: tuple(sorted(r, key=lambda x: x.kickoff)) for s, r in self.rows.items()}
        )

    def after(self) -> datetime:
        return max(g.kickoff for g in self.games) + timedelta(hours=5)


def fitted(m: EfficiencyRatings, league: League) -> EfficiencyRatings:
    m.use({"team_game_stats": league.stats()})
    return m


def known(seed: int, teams: range) -> dict[int, tuple[np.ndarray, np.ndarray]]:
    """Ratings averaging zero over the teams, per stat and side."""
    rng = np.random.default_rng(seed)
    off = rng.normal(0, [0.1, 0.04], (len(teams), 2))
    dfn = rng.normal(0, [0.1, 0.04], (len(teams), 2))
    off, dfn = off - off.mean(axis=0), dfn - dfn.mean(axis=0)
    return {t: (off[i], dfn[i]) for i, t in enumerate(teams)}


def round_robin(league: League, season: int, teams: list[int], first_week: int = 1) -> int:
    """Every pairing home and away, one game per team per week; returns the next free week."""
    week = first_week
    for i, home in enumerate(teams):
        for away in teams[i + 1 :]:
            league.play(season, week, home, away)
            league.play(season, week + 1, away, home)
            week += 2
    return week


# AC-1


def test_noiseless_ratings_are_recovered_at_alpha_zero() -> None:
    teams = range(1, 7)
    league = League(known(1, teams), dict.fromkeys(teams, POWER_4))
    round_robin(league, 2023, list(teams))

    ratings = fitted(model(), league).stat_ratings(league.games, league.after())

    for team in teams:
        off, dfn = league.ratings[team]
        for i, stat in enumerate(STATS):
            assert ratings[team][stat][0] == pytest.approx(off[i], abs=0.01), (team, stat)
            assert ratings[team][stat][1] == pytest.approx(dfn[i], abs=0.01), (team, stat)


def test_ridge_pulls_a_two_game_team_harder_than_an_eight_game_team() -> None:
    core = list(range(1, 9))
    ratings = known(2, range(1, 9))
    strong = (np.array([0.25, 0.08]), np.array([0.2, 0.06]))
    ratings |= {101: strong, 102: strong}  # identical teams: 101 plays 2 games, 102 plays 8
    league = League(ratings, dict.fromkeys([*core, 101, 102], POWER_4))
    week = round_robin(league, 2023, core)
    for i, opponent in enumerate(core):
        league.play(2023, week + i, 102, opponent)
        if i < 2:
            league.play(2023, week + i, opponent, 101)
    plain = fitted(model(), league).stat_ratings(league.games, league.after())
    ridge = fitted(model(hyperparameters={"ridge_alpha": 5}), league).stat_ratings(
        league.games, league.after()
    )

    for stat in STATS:
        for side in (0, 1):
            # Both recover the truth unpenalized; each keeps a share of it under ridge.
            assert plain[101][stat][side] == pytest.approx(plain[102][stat][side], abs=0.01)
            share = {t: ridge[t][stat][side] / plain[t][stat][side] for t in (101, 102)}
            assert 0 < share[101] < share[102] < 1, (stat, side, share)


# AC-2 (the tier anchor; the map itself is test_conference_tiers.py)


def tiered_league() -> League:
    """Four Power 4 teams better than four G5 teams on every stat, playing each other across
    tiers in 2022 and 2023, plus a G5 team (300) that never plays in 2023."""
    p4, g5 = [1, 2, 3, 4], [11, 12, 13, 14]
    ratings = {t: (np.array([0.15, 0.05]), np.array([0.1, 0.04])) for t in p4}
    ratings |= {t: (np.array([-0.15, -0.05]), np.array([-0.1, -0.04])) for t in [*g5, 300]}
    for t, bump in zip([*p4, *g5], np.linspace(-0.02, 0.02, 8), strict=True):
        ratings[t] = (ratings[t][0] + bump, ratings[t][1] - bump)
    tiers = dict.fromkeys(p4, POWER_4) | dict.fromkeys([*g5, 300], G5)
    league = League(ratings, tiers)
    for season in (2022, 2023):
        week = round_robin(league, season, p4)
        week = round_robin(league, season, g5, week)
        for i, (a, b) in enumerate(zip(p4, g5, strict=True)):
            league.play(season, week + i, a, b, margin=21)
            league.play(season, week + 4 + i, b, a, margin=-14)
    league.play(2022, 30, 300, 11, margin=-3)  # 300 played last season only
    return league


@pytest.mark.parametrize("shrink", ["zero", "tier"])
def test_an_unseen_team_rates_at_its_anchor(shrink: str) -> None:
    league = tiered_league()
    league.games = [g for g in league.games if 300 not in (g.home_team, g.away_team)]
    league.rows = {
        s: [r for r in rows if 300 not in (r.team, r.opponent)] for s, rows in league.rows.items()
    }
    m = fitted(model(shrink_toward=shrink, hyperparameters={"ridge_alpha": 2}), league)
    as_of = league.after()

    ratings = m.fit(league.games, as_of)
    unseen = m.rating(ratings, 2023, 300, "fbs", CONFERENCE[G5])
    per_stat = m.stat_ratings(league.games, as_of)

    if shrink == "tier":
        assert unseen == ratings.params[f"tier_{G5}"]
        assert ratings.params[f"tier_{G5}"] < ratings.params[f"tier_{POWER_4}"]
        assert (
            per_stat[f"tier:{G5}"]["epa_per_play"][0]
            < 0
            < per_stat[f"tier:{POWER_4}"]["epa_per_play"][0]
        )
    else:
        assert unseen == 0.0
        assert not any(isinstance(k, str) and k.startswith("tier:") for k in per_stat)


def test_under_tier_the_prior_regresses_toward_the_tiers_level() -> None:
    league = tiered_league()
    prior = {"components": ["last_season"], "regression": 0.5}
    prior |= {"decay": {"type": "linear", "zero_at_week": 4}}
    week_one = datetime(2023, 8, 26, tzinfo=UTC)
    last = [g for g in league.games if g.season == 2022]
    m = fitted(model(shrink_toward="tier", prior=prior), league)
    final = m.stat_ratings(last, max(g.kickoff for g in last) + timedelta(hours=5))
    entering = m.stat_ratings(last, week_one)

    # 300 played once in 2022: halfway from its final rating to the G5 level.
    for stat in STATS:
        for side in (0, 1):
            level = final[f"tier:{G5}"][stat][side]
            expected = level + 0.5 * (final[300][stat][side] - level)
            assert entering[300][stat][side] == pytest.approx(expected)


# AC-3


def test_noiseless_margin_coefficients_are_recovered() -> None:
    m = model()
    rng = np.random.default_rng(3)
    truth = np.array([30.0, 12.0, 25.0, 9.0])  # b_off per stat, then b_def
    hfa = 2.5
    rows = []
    for i in range(200):
        gaps = rng.normal(0, [0.15, 0.05, 0.15, 0.05])
        home = float(i % 4 != 0)
        rows.append(MatchupRow(i, 2021 + i % 2, home, gaps, hfa * home + float(truth @ gaps)))

    margin = m.fit_margin(rows, 2023)

    assert margin.home_field == pytest.approx(hfa, abs=0.01)
    assert margin.coefficients == pytest.approx(truth, abs=0.01)
    assert margin.sd == pytest.approx(0.0, abs=1e-6)


def test_the_margin_model_is_fit_on_earlier_seasons_from_ratings_entering_each_week() -> None:
    league = tiered_league()
    m = fitted(model(hyperparameters={"ridge_alpha": 2}), league)
    early_2023 = kickoff(2023, 3) - timedelta(hours=1)
    seen = [g for g in league.games if g.kickoff + timedelta(hours=4) <= early_2023]

    ratings = m.fit(seen, early_2023)

    last = [g for g in league.games if g.season == 2022]
    rows = m.matchup_rows({2022: last}, 2022)
    assert len(rows) == len(last)  # every 2022 game, and none of 2023's
    # The 2023 fit's coefficients are exactly those fit on these 2022 rows.
    margin = m.fit_margin(rows, 2023)
    assert ratings.params["home_field"] == pytest.approx(margin.home_field)
    assert ratings.params["margin_sd"] == pytest.approx(margin.sd)
    for i, stat in enumerate(STATS):
        assert ratings.params[f"b_off_{stat}"] == pytest.approx(margin.coefficients[i])
        assert ratings.params[f"b_def_{stat}"] == pytest.approx(margin.coefficients[2 + i])
    # Each row's gaps are the ratings entering its week (a team not yet rated is at 0).
    rated = 0
    for row in rows:
        game = next(g for g in last if g.game_id == row.game_id)
        entering = m.stat_ratings([g for g in last if g.week < game.week], game.kickoff)
        unseen = dict.fromkeys(STATS, (0.0, 0.0))
        home = entering.get(game.home_team, unseen)
        away = entering.get(game.away_team, unseen)
        rated += game.home_team in entering and game.away_team in entering
        for i, stat in enumerate(STATS):
            assert row.gaps[i] == pytest.approx(home[stat][0] - away[stat][0], abs=1e-12)
            assert row.gaps[2 + i] == pytest.approx(home[stat][1] - away[stat][1], abs=1e-12)
    assert rated > len(rows) / 2


def test_a_margin_fit_given_a_game_from_the_predicted_season_fails() -> None:
    rows = [MatchupRow(1, 2022, 1.0, np.zeros(4), 3.0), MatchupRow(2, 2023, 1.0, np.zeros(4), 7.0)]
    with pytest.raises(PointInTimeError, match="earlier seasons only"):
        model().fit_margin(rows, 2023)


def test_the_first_season_has_no_margin_model() -> None:
    league = tiered_league()
    first = [g for g in league.games if g.season == 2022]
    m = fitted(model(), league)
    with pytest.raises(NoEarlierSeasonError):
        m.fit(first, max(g.kickoff for g in first) + timedelta(hours=5))


def test_a_stat_row_whose_game_had_not_finished_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    league = tiered_league()
    m = fitted(model(), league)
    as_of = kickoff(2023, 3) + timedelta(hours=1)  # week 3's games kicked off an hour ago
    games = [g for g in league.games if g.kickoff + timedelta(hours=4) <= as_of]
    m.fit(games, as_of)  # the harness's selection leaves week 3's rows out

    monkeypatch.setattr(harness, "SELECT_LAG", timedelta(0))  # a selection that lets them in
    m = fitted(model(), league)
    with pytest.raises(PointInTimeError, match="hadn't finished"):
        m.fit(games, as_of)


# The spec.


@pytest.mark.parametrize(
    ("spec", "message"),
    [
        ({"base": "power"}, "efficiency spec"),
        ({"inputs": [{"stat": "epa_per_play", "weight": 2.0}]}, "fits every input"),
        ({"inputs": [{"stat": "epa_per_play", "weight": 0.0}]}, "nothing to rate"),
        (
            {"prior": {"components": ["talent"], "regression": 0.2, "decay": {"type": "fitted"}}},
            "last season",
        ),
    ],
)
def test_what_rung_2_doesnt_do_is_refused(spec: dict[str, Any], message: str) -> None:
    base = {"base": "efficiency", "inputs": [{"stat": "epa_per_play"}], "picks": PICKS}
    if spec.get("base") == "power":
        base = {"base": "power", "picks": PICKS}
        spec = {}
    with pytest.raises(UnsupportedSpecError, match=message):
        EfficiencyRatings(ModelSpec.model_validate({**base, **spec}), EFFICIENCY_RULES)


def test_an_input_weighted_zero_is_left_out() -> None:
    m = model(inputs=[{"stat": "epa_per_play"}, {"stat": "success_rate", "weight": 0.0}])
    assert m.stats == ("epa_per_play",)


# AC-4: the golden backtest of efficiency-v1.json on the fixture generator, 2021-2023.


def render(data: bytes) -> str:
    """The results as CSV text, numbers rounded to 8 decimals: LAPACK's last bits differ between
    Windows and Linux (CI), and a rating that should be exactly zero mustn't flip sign."""
    table = pq.read_table(io.BytesIO(data))
    lines = [",".join(table.column_names)]
    for row in table.to_pylist():
        cells = []
        for value in row.values():
            if isinstance(value, float):
                cells.append(f"{round(value, 8) + 0.0:.10g}")
            else:
                cells.append("" if value is None else str(value))
        lines.append(",".join(cells))
    return "\n".join(lines) + "\n"


@pytest.fixture
def three_season_lake(empty_lake: LocalLake) -> LocalLake:
    # 2021 gives the margin model a season before 2022, the tuning season (option a, plan gate).
    write_backtest_seasons(empty_lake, seasons=(2021, 2022, 2023))
    # The preseason values the v1 prior reads (TASK-037): recruiting from 2018, talent 2020-2022.
    write_preseason(empty_lake, tuple(range(2018, 2024)))
    rebuild(empty_lake)
    return empty_lake


def test_the_efficiency_backtest_matches_the_golden_file(three_season_lake: LocalLake) -> None:
    argv = ["backtest", "--spec", str(SPEC_FILE), "--seasons", "2023", "--tune-from", "2022"]

    assert engine(*argv) == 0
    assert engine(*argv) == 0

    keys = [k for k in three_season_lake.walk("backtests") if k.endswith("/predictions.parquet")]
    first, second = (three_season_lake.read(k) for k in keys)
    assert first == second
    text = render(first)
    if os.environ.get("UPDATE_GOLDEN") == "1":
        GOLDEN.write_text(text, "utf-8", newline="\n")
    assert text == GOLDEN.read_text("utf-8")

    run = json.loads(three_season_lake.read(keys[0].replace("predictions.parquet", "run.json")))
    rows = pq.read_table(io.BytesIO(first)).to_pylist()
    scored = metrics.compute(
        rows,
        ModelSpec.model_validate(run["spec"]),
        {int(s): c for s, c in run["choices"].items()},
        tier=(backtest.matchup_tier, backtest.TIER_MATCHUPS),
    )
    (tiers,) = [b for b in scored.breakdowns if b.name == metrics.TIER_BREAKDOWN]
    assert sum(g.games for g in tiers.groups) == scored.games == len(rows)
    assert {g.label for g in tiers.groups} == {
        "Power 4 vs Power 4",
        "Power 4 vs G5",
        "G5 vs G5",
    }


def test_an_efficiency_backtest_with_no_earlier_season_is_refused(
    empty_lake: LocalLake, tmp_path: Path
) -> None:
    write_backtest_seasons(empty_lake)  # 2022-2023: tuning on 2022 has no season before it
    rebuild(empty_lake)
    argv = ["backtest", "--spec", str(SPEC_FILE), "--seasons", "2023", "--tune-from", "2022"]
    assert engine(*argv) == 2
    assert not list(empty_lake.walk("backtests"))


# engine rate (D-136) fits Rung 2 as the backtest does.


def test_engine_rate_fits_an_efficiency_week_with_stats_and_conferences(
    three_season_lake: LocalLake,
) -> None:
    from engine.publish.models import fit_week

    spec = ModelSpec.model_validate(
        {
            "base": "efficiency",
            "inputs": [{"stat": s} for s in STATS],
            "hyperparameters": {"ridge_alpha": 2},
            "shrink_toward": "tier",
            "picks": PICKS,
        }
    )

    # Entering 2023 week 1 no team has played and there's no prior: every team rates at its
    # tier, which needs each team's conference, and the margin model needs 2021-2022's stats.
    fitted = fit_week(three_season_lake, spec, {}, season=2023, week=1)

    assert fitted.error is None
    assert fitted.outputs is not None
    ratings, predicted = fitted.outputs
    assert {g.home_group for g, _ in predicted} >= {"Big 12", "Conference USA"}
    hfa = ratings.params["home_field"]
    for game, p in predicted:
        expected = (0.0 if game.neutral_site else hfa) + p.drivers[1][1] + p.drivers[2][1]
        assert p.pred_margin == pytest.approx(expected)


def test_a_final_game_missing_a_team_gives_no_stat_rows(empty_lake: LocalLake) -> None:
    """A staged final game with one team id unknown is in neither `results` nor the stats."""
    import copy

    from lake_fixture import FIXTURE, fixture_key, write_fixture

    fixture = copy.deepcopy(FIXTURE)
    (game,) = [g for g in fixture[fixture_key("games")]["records"] if g["id"] == 401757218]
    game["awayId"] = None  # Western Kentucky-Sam Houston: Sam Houston's id unknown
    write_fixture(empty_lake, fixture)
    rebuild(empty_lake)

    history = harness.load(empty_lake)

    rows = [r for rs in history.stats.by_season.values() for r in rs]
    assert rows and all(r.game_id != 401757218 for r in rows)
    assert {r.game_id for r in rows} <= {g.game_id for g in history.results}


def test_a_tier_backtest_with_an_unmapped_conference_is_refused(
    empty_lake: LocalLake, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    import copy

    import lake_fixture

    fixture = copy.deepcopy(lake_fixture.FIXTURE)
    games = fixture[lake_fixture.fixture_key("games")]["records"]
    for g in games:
        if g["homeTeam"] == "Western Kentucky":
            g["homeConference"] = "Big East"  # an FBS conference the tier map doesn't know
    monkeypatch.setattr(lake_fixture, "FIXTURE", fixture)
    write_backtest_seasons(empty_lake, seasons=(2021, 2022, 2023))
    rebuild(empty_lake)
    capsys.readouterr()

    argv = ["backtest", "--spec", str(SPEC_FILE), "--seasons", "2023", "--tune-from", "2022"]
    assert engine(*argv) == 2

    assert "'Big East' has no tier" in capsys.readouterr().err
    assert not list(empty_lake.walk("backtests"))
