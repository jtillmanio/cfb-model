"""The Rung 0 baselines (TASK-032; docs/04-model.md § 2, § 9.2-9.3, D-133): the simple
predictions every real model has to beat, scored by the same harness on the same games.

- `HomeField`: the home-field edge alone, fit on seasons before the one scored.
- `LastSeason(model)`: the wrapped model's final ratings from the season before, frozen for the
  whole season (no in-season updates, no regression toward the mean).
- `ClosingLine`: the market's closing spread, by `closing_lines()`'s rule (consensus, else the
  median), which each results row records in `spread_source`.
- `BenchmarkRating("sp" | "fpi")`: the rating published before the game's earliest possible
  kickoff, plus home field.
  When none was published before the game, the season-final rating stands in, and the row is
  noted as a hindsight benchmark (04 § 9.2): it never counts as a baseline beaten.

Baselines declare `baseline = True`, which lets them read the inputs the harness keeps from
models that fit (`harness.BASELINE_INPUTS`). They are not `ModelSpec`s (D-130): a run names the
baseline and the spec of the model it stands beside. A baseline's `fit` only keeps the games it
was given; every season-by-season number comes from earlier seasons, so a game of the season
being scored can't move its own baseline.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from engine.backtest.harness import Benchmark, BenchmarkInput, RefusedError
from engine.backtest.stub import DEFAULT_SD
from engine.core.interfaces import (
    GameContext,
    GameHistory,
    GameResult,
    Prediction,
    RatingModel,
    Ratings,
)
from engine.core.probability import NormalMargin, win_probability
from engine.transform.features import GAME_HOURS, PointInTimeError

HINDSIGHT = "hindsight benchmark"
UNSEEN = "unseen team"
UNRATED = "unrated team"

_FINISHED = timedelta(hours=GAME_HOURS)


@dataclass(frozen=True, slots=True)
class Played(Ratings):
    """What a baseline's `fit` returns: the games it was given."""

    games: GameHistory = ()


def _played(ratings: Ratings) -> Played:
    if not isinstance(ratings, Played):
        raise TypeError(f"a baseline needs the ratings its own fit returned, got {ratings!r}")
    return ratings


def _before(games: GameHistory, season: int) -> list[GameResult]:
    return [g for g in games if g.season < season]


def _sd(residuals: Sequence[float]) -> float:
    """The sample standard deviation, or `DEFAULT_SD` while there are fewer than two."""
    if len(residuals) < 2:
        return DEFAULT_SD
    mean = math.fsum(residuals) / len(residuals)
    sd = math.sqrt(math.fsum((r - mean) ** 2 for r in residuals) / (len(residuals) - 1))
    return sd or DEFAULT_SD


def _prediction(margin: float, sd: float, drivers: tuple[tuple[str, float], ...]) -> Prediction:
    return Prediction(margin, sd, win_probability(margin, NormalMargin(sd)), drivers)


def comparable(rows: Iterable[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    """The results rows that may count as a baseline beaten: not a hindsight benchmark, and not
    a game where a team had no rating (it would be rated 0, a bar that's easy to beat). A note
    can hold both, joined by "; "."""
    return [r for r in rows if not {HINDSIGHT, UNRATED} & set((r.get("note") or "").split("; "))]


class HomeField:
    """Predict the home-field edge, and 0 at a neutral site: the mean margin of the non-neutral
    games of every earlier season (an expanding window), so a season's games never move it."""

    reads = frozenset({"games"})
    baseline = True

    def __init__(self) -> None:
        self._memo: dict[tuple[int, datetime], tuple[float, float]] = {}

    def fit(self, games: GameHistory, as_of: datetime) -> Ratings:
        return Played(as_of, {}, {}, games)

    def edge(self, ratings: Ratings, season: int) -> tuple[float, float]:
        """The edge fit before `season` and the σ of margins around it."""
        played = _played(ratings)
        key = (season, played.as_of)
        if key not in self._memo:
            earlier = _before(played.games, season)
            home = [g.margin for g in earlier if not g.neutral_site]
            hfa = math.fsum(home) / len(home) if home else 0.0
            sd = _sd([g.margin - (0.0 if g.neutral_site else hfa) for g in earlier])
            self._memo[key] = (hfa, sd)
        return self._memo[key]

    def predict(self, game: GameContext, ratings: Ratings, as_of: datetime) -> Prediction:
        hfa, sd = self.edge(ratings, game.season)
        margin = 0.0 if game.neutral_site else hfa
        return _prediction(margin, sd, (("Home field", margin),))


class LastSeason:
    """A rating model's final ratings from the season before, carried into this one unchanged.

    The wrapped model is fit once for each season Y, on the games of seasons before Y, and
    predicts all of Y from that fit (and its home field, fit on the same games). A team it didn't
    rate gets the wrapped model's rating for an unseen team, and the row says so.
    """

    baseline = True

    def __init__(self, inner: RatingModel) -> None:
        self.inner = inner
        self.reads: frozenset[str] = getattr(inner, "reads", frozenset({"games"}))
        if getattr(inner, "baseline", False) or self.reads - {"games"}:
            raise RefusedError("last_season wraps a model that fits on games alone (D-133)")
        self._frozen: dict[int, Ratings] = {}

    def fit(self, games: GameHistory, as_of: datetime) -> Ratings:
        return Played(as_of, {}, {}, games)

    def _final(self, ratings: Ratings, season: int) -> Ratings:
        # Every game before `season` has finished by its first week, so the fit is the same
        # whichever week of the season asks first.
        if season not in self._frozen:
            played = _played(ratings)
            earlier = _before(played.games, season)
            end = max(g.kickoff for g in earlier) + _FINISHED if earlier else played.as_of
            if end > played.as_of:  # the point-in-time rule, 04 § 9.2
                raise PointInTimeError(
                    f"last_season's fit for {season} was given a game that hadn't finished by "
                    f"its as_of {played.as_of.isoformat()}"
                )
            self._frozen[season] = self.inner.fit(earlier, end)
        return self._frozen[season]

    def predict(self, game: GameContext, ratings: Ratings, as_of: datetime) -> Prediction:
        final = self._final(ratings, game.season)
        inner: Any = self.inner
        return inner.predict(game, final, final.as_of)  # type: ignore[no-any-return]

    def note(self, game: GameContext, ratings: Ratings) -> str | None:
        teams = self._final(ratings, game.season).teams
        return None if {game.home_team, game.away_team} <= teams.keys() else UNSEEN


class ClosingLine:
    """Predict the margin the closing line implies: `-spread_home`. The market's σ is measured
    on the closing lines of earlier seasons."""

    reads = frozenset({"games", "closing_lines"})
    baseline = True

    def __init__(self) -> None:
        self._spreads: Mapping[int, float] = {}
        self._memo: dict[tuple[int, datetime], float] = {}

    def use(self, inputs: Mapping[str, Any]) -> None:
        self._spreads = inputs["closing_lines"]

    def fit(self, games: GameHistory, as_of: datetime) -> Ratings:
        return Played(as_of, {}, {}, games)

    def _sd(self, ratings: Ratings, season: int) -> float:
        played = _played(ratings)
        key = (season, played.as_of)
        if key not in self._memo:
            earlier = _before(played.games, season)
            self._memo[key] = _sd(
                [g.margin + self._spreads[g.game_id] for g in earlier if g.game_id in self._spreads]
            )
        return self._memo[key]

    def predict(self, game: GameContext, ratings: Ratings, as_of: datetime) -> Prediction:
        if game.game_id not in self._spreads:
            raise RefusedError(f"game {game.game_id} has no closing line")
        margin = -self._spreads[game.game_id]
        return _prediction(margin, self._sd(ratings, game.season), (("Closing line", margin),))


def check_published(rating: Benchmark, game: GameContext, cutoff: datetime) -> None:
    """Assert a rating used as known before `game` was published before `cutoff` (04 § 9.2)."""
    if rating.known_at is None or rating.known_at >= cutoff:
        raise PointInTimeError(
            f"game {game.game_id}: the {rating.system} rating of team {rating.team} wasn't "
            f"published before {cutoff.isoformat()} (point-in-time rule, 04 § 9.2)"
        )


class BenchmarkRating:
    """SP+ or FPI as a predictor: `rating_home − rating_away`, plus home field for a game that
    isn't at a neutral site. Only a rating published before kickoff counts; with none, the
    season-final rating is used and the row is noted as a hindsight benchmark. The home-field
    edge and σ are `HomeField`'s, from earlier seasons."""

    baseline = True
    reads = frozenset({"games", "benchmark_ratings"})

    def __init__(self, system: str) -> None:
        self.system = system
        self._by_team: dict[tuple[int, int], list[Benchmark]] = {}
        self._earliest: Mapping[int, datetime] = {}
        self._home = HomeField()

    def use(self, inputs: Mapping[str, Any]) -> None:
        given: BenchmarkInput = inputs["benchmark_ratings"]
        self._earliest = given.earliest
        rows = [b for b in given.rows if b.system == self.system]
        if not rows:
            raise RefusedError(
                f"no {self.system} ratings are staged: run engine transform --rebuild after "
                f"pulling /ratings/{self.system}"
            )
        self._by_team = {}
        for row in sorted(rows, key=lambda b: b.fetched_at):
            self._by_team.setdefault((row.season, row.team), []).append(row)

    def fit(self, games: GameHistory, as_of: datetime) -> Ratings:
        return self._home.fit(games, as_of)

    def _rating(self, game: GameContext, team: int) -> tuple[float | None, bool]:
        """The team's rating for this game, and whether it's hindsight."""
        rows = self._by_team.get((game.season, team), [])
        # Known before the game means before its earliest possible kickoff: a TBA game's date
        # starts at Eastern midnight, though `game.kickoff` puts it at the end of the date.
        if game.game_id not in self._earliest:
            raise PointInTimeError(f"game {game.game_id} has no earliest kickoff to cut off at")
        cutoff = self._earliest[game.game_id]
        known = [r for r in rows if r.known_at is not None and r.known_at < cutoff]
        if known:
            newest = max(known, key=lambda r: r.known_at or r.fetched_at)
            check_published(newest, game, cutoff)
            return newest.rating, False
        final = [r for r in rows if r.known_at is None]
        return (final[-1].rating, True) if final else (None, False)

    def predict(self, game: GameContext, ratings: Ratings, as_of: datetime) -> Prediction:
        hfa, sd = self._home.edge(ratings, game.season)
        home = self._rating(game, game.home_team)[0] or 0.0
        away = self._rating(game, game.away_team)[0] or 0.0
        edge = 0.0 if game.neutral_site else hfa
        name = self.system
        drivers = (("Home field", edge), (f"Home {name}", home), (f"Away {name}", -away))
        return _prediction(home - away + edge, sd, drivers)

    def note(self, game: GameContext, ratings: Ratings) -> str | None:
        sides = [self._rating(game, t) for t in (game.home_team, game.away_team)]
        notes = []
        if any(hindsight for _, hindsight in sides):
            notes.append(HINDSIGHT)
        if any(rating is None for rating, _ in sides):
            notes.append(UNRATED)
        return "; ".join(notes) or None
