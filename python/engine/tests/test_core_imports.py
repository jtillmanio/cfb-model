"""The light core's boundary and the model contract (TASK-029, D-004, D-022): `engine.core` loads
without the training stack, ingest, transforms or any sport, and a model is anything that
satisfies `RatingModel` and `GamePredictor` (docs/04-model.md § 6 Engineering contract)."""

import json
import subprocess
import sys
from datetime import UTC, datetime

from engine.core.interfaces import (
    GameContext,
    GameHistory,
    GamePredictor,
    GameResult,
    Prediction,
    RatingModel,
    Ratings,
)
from engine.core.probability import NormalMargin, win_probability

HEAVY = ("duckdb", "pyarrow", "httpx", "boto3", "pandas")
ENGINE_PARTS = ("engine.sports", "engine.ingest", "engine.transform")

PROBE = """
import json, sys
from engine.core import INPUTS, ModelSpec, RatingModel, cover_probability, pick
print(json.dumps(sorted(sys.modules)))
"""


def test_importing_engine_core_loads_no_heavy_or_sport_module() -> None:
    out = subprocess.run(
        [sys.executable, "-c", PROBE], capture_output=True, text=True, check=True
    ).stdout
    loaded = set(json.loads(out))

    assert "engine.core" in loaded
    assert {m for m in loaded if m.split(".")[0] in HEAVY} == set()
    assert {m for m in loaded if m.startswith(ENGINE_PARTS)} == set()


AS_OF = datetime(2026, 10, 10, 16, tzinfo=UTC)


class MeanMarginModel:
    """A test double: each team's rating is its mean margin; home field is fixed."""

    def __init__(self, home_field: float, sd: float) -> None:
        self.home_field = home_field
        self.dist = NormalMargin(sd)

    def fit(self, games: GameHistory, as_of: datetime) -> Ratings:
        totals: dict[int, list[float]] = {}
        for g in games:
            if g.kickoff < as_of:
                totals.setdefault(g.home_team, []).append(g.margin)
                totals.setdefault(g.away_team, []).append(-g.margin)
        teams = {team: sum(m) / len(m) for team, m in totals.items()}
        params = {"home_field": self.home_field, "margin_sd": self.dist.sd}
        return Ratings(as_of=as_of, teams=teams, params=params)

    def predict(self, game: GameContext, ratings: Ratings, as_of: datetime) -> Prediction:
        hfa = 0.0 if game.neutral_site else ratings.params["home_field"]
        gap = ratings.teams[game.home_team] - ratings.teams[game.away_team]
        margin = gap + hfa
        return Prediction(
            pred_margin=margin,
            margin_sd=self.dist.sd,
            home_win_prob=win_probability(margin, self.dist),
            drivers=(("Rating gap", gap), ("Home field", hfa)),
        )


def game(game_id: int, home: int, away: int, home_points: int, away_points: int) -> GameResult:
    return GameResult(
        game_id=game_id,
        season=2026,
        season_type="regular",
        week=game_id,
        kickoff=datetime(2026, 9, game_id, 16, tzinfo=UTC),
        home_team=home,
        away_team=away,
        neutral_site=False,
        home_points=home_points,
        away_points=away_points,
    )


def test_a_test_double_satisfies_both_protocols() -> None:
    model = MeanMarginModel(home_field=2.5, sd=16.0)
    rater: RatingModel = model
    predictor: GamePredictor = model

    history = [game(1, 10, 20, 31, 17), game(2, 20, 30, 24, 21)]
    ratings = rater.fit(history, AS_OF)
    upcoming = GameContext(
        game_id=3,
        season=2026,
        season_type="regular",
        week=3,
        kickoff=AS_OF,
        home_team=30,
        away_team=10,
        neutral_site=False,
    )
    prediction = predictor.predict(upcoming, ratings, AS_OF)

    assert history[0].margin == 14
    assert ratings.teams == {10: 14.0, 20: -5.5, 30: -3.0}
    assert prediction.pred_margin == -17.0 + 2.5
    assert prediction.margin_sd == 16.0
    assert 0.0 < prediction.home_win_prob < 0.5
    assert prediction.drivers == (("Rating gap", -17.0), ("Home field", 2.5))
