"""The contract every model meets, so backtests, production runs, the Lab and the API treat them
the same (docs/04-model.md § 6 Engineering contract, D-050). A model is a pure function of its
inputs and its `ModelSpec`.

Sport-agnostic (D-022): teams and games are the serving database's ids, and nothing here knows
what a conference or an FCS team is.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal, Protocol

TeamId = int


@dataclass(frozen=True, slots=True)
class GameContext:
    """A game to predict: what's known about it before kickoff."""

    game_id: int
    season: int
    season_type: Literal["regular", "postseason"]
    week: int
    kickoff: datetime
    home_team: TeamId
    away_team: TeamId
    neutral_site: bool
    # Each team's level that season, as the source labels it (CFB: "fbs", "fcs"); a model may
    # pool the levels it can't rate one team at a time. None when the source doesn't say.
    home_classification: str | None = field(default=None, kw_only=True)
    away_classification: str | None = field(default=None, kw_only=True)
    # Each team's league that season, as the source labels it (CFB: its conference); a model may
    # map it to the group it shrinks toward. None when the source doesn't say.
    home_group: str | None = field(default=None, kw_only=True)
    away_group: str | None = field(default=None, kw_only=True)


@dataclass(frozen=True, slots=True)
class GameResult(GameContext):
    """A finished game a model can fit on."""

    home_points: int
    away_points: int

    @property
    def margin(self) -> int:
        return self.home_points - self.away_points


GameHistory = Sequence[GameResult]


@dataclass(frozen=True, slots=True)
class Ratings:
    """A fit's output entering a week: each team's rating and the learned weights."""

    as_of: datetime
    teams: Mapping[TeamId, float]
    params: Mapping[str, float]  # e.g. home_field, margin_sd; stored as model_runs.fitted_params
    # Each team's units in points, by input-registry id: (offense, defense), summing to its
    # rating (04 § 10.2). Empty for a model that rates a team as one number.
    units: Mapping[TeamId, Mapping[str, tuple[float, float]]] = field(default_factory=dict)


Driver = tuple[str, float]  # ("Home pass offense vs away pass defense", 3.1)


@dataclass(frozen=True, slots=True)
class Prediction:
    pred_margin: float  # home − away
    margin_sd: float
    home_win_prob: float
    drivers: tuple[Driver, ...] = ()  # the "why this pick" contributions, in points


class RatingModel(Protocol):
    def fit(self, games: GameHistory, as_of: datetime) -> Ratings: ...


class GamePredictor(Protocol):
    def predict(self, game: GameContext, ratings: Ratings, as_of: datetime) -> Prediction:
        """Returns pred_margin, margin_sd, home_win_prob, drivers."""
        ...
