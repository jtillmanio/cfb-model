"""A backtest run's § 9.4 metrics and go/no-go gates (TASK-031; docs/04-model.md § 9.3-9.5,
D-076, D-077, D-091).

Each results row is graded once (`grade_rows`): the model's margin is shrunk toward the market
by the season's `market_shrinkage_k`, the side it likes against the close gets the cover
probability the app would display, and `core.picks.pick()` applies the season's pick rules, both
at the close and at the opener. Probabilities use a normal margin with the row's `margin_sd`.

**Grading** (04 § 9.3). A push counts in a record (W-L-P), is left out of win %, and earns
nothing. At −110 a win is +1.0u and a loss −1.1u; a push is refunded, so it isn't risked, and
ROI is units won over the 1.1u risked on each win or loss.

**Gates** read pass, fail, or n/a when the run's data can't decide them (one season for the
consistency rule, no calibration bin of 100 picks yet). The bar of 52.4% is break-even at −110,
110/210.
"""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from statistics import NormalDist
from typing import Any, Literal

from engine.backtest.bootstrap import Interval, WeekKey, mean_difference
from engine.core.contest_rules import SPLASH_PRESET
from engine.core.picks import Pick, pick
from engine.core.probability import (
    NormalMargin,
    Side,
    blended_margin,
    break_even,
    cover_probability,
    win_probability,
)
from engine.core.spec import ModelSpec, fixed

__all__ = ["Metrics", "Result", "Side", "compute"]

Result = Literal["W", "L", "P"]
Status = Literal["pass", "fail", "n/a"]
Choices = Mapping[str, float]

PRICE = -110
BREAK_EVEN = break_even(PRICE)  # 110/210, "52.4%"
RISK = -PRICE / 100  # units risked to win 1.0
MAE_GAP = 0.5  # model MAE − closing MAE, at most (pts)
CALIBRATION_MIN_PICKS = 100
CALIBRATION_TOLERANCE = 3.0  # pts
SEASONS_BELOW_50 = 2  # at most, of the validation seasons
CONTEST_PICKS = SPLASH_PRESET.picks_per_period  # the contest backtest's top N (04 § 9.3)
CONTEST_GAP = 3.0  # pts: average predicted cover minus actual hit rate, at most
_EPS = 1e-9  # compare thresholds without float noise: 0.58 − 0.55 is 0.030000000000000027
_Z = NormalDist().inv_cdf(0.5 + 0.95 / 2)

# 04 § 5's all-game edge buckets feed the gate; § 9.4's pick buckets are display only (D-077).
EDGE_BUCKETS = ((0.0, "0–1.5"), (1.5, "1.5–3"), (3.0, "3–5"), (5.0, "5+"))
PICK_BUCKETS = ((2.5, "2.5–3.5"), (3.5, "3.5–5.0"), (5.0, "5.0–7.0"), (7.0, "7.0+"))
CALIBRATION_BINS = (0.50, 0.525, 0.55, 0.575, 0.60, 0.625, 0.65)  # the last is 65%+


@dataclass(frozen=True, slots=True)
class Gate:
    status: Status
    detail: str  # why, in words


@dataclass(frozen=True, slots=True)
class Record:
    wins: int
    losses: int
    pushes: int

    @classmethod
    def of(cls, results: Iterable[Result]) -> Record:
        listed = list(results)
        return cls(listed.count("W"), listed.count("L"), listed.count("P"))

    def __str__(self) -> str:
        return f"{self.wins}-{self.losses}-{self.pushes}"

    @property
    def graded(self) -> int:
        return self.wins + self.losses

    @property
    def win_pct(self) -> float | None:
        return self.wins / self.graded if self.graded else None

    @property
    def units(self) -> float:
        return self.wins - RISK * self.losses

    @property
    def risked(self) -> float:
        return RISK * self.graded

    @property
    def roi(self) -> float | None:
        return self.units / self.risked if self.graded else None

    @property
    def interval(self) -> tuple[float, float] | None:
        """Wilson's 95% score interval for the win %."""
        if not self.graded:
            return None
        n, p, z2 = self.graded, self.wins / self.graded, _Z * _Z
        center = (p + z2 / (2 * n)) / (1 + z2 / n)
        half = _Z / (1 + z2 / n) * math.sqrt(p * (1 - p) / n + z2 / (4 * n * n))
        return center - half, center + half


def grade(side: Side, margin: int, spread_home: float) -> Result:
    """Home covers when `margin + spread_home > 0`; exactly 0 is a push."""
    cover = margin + spread_home
    if cover == 0:
        return "P"
    return "W" if (cover > 0) == (side == "home") else "L"


# Margin accuracy against the closing line


@dataclass(frozen=True, slots=True)
class Accuracy:
    games: int
    mae: float
    closing_mae: float  # the closing line's own error: it predicts −spread_home
    rmse: float
    closing_rmse: float
    gap_interval: Interval | None  # week-level bootstrap of the gap (04 § 9.5)

    @property
    def gap(self) -> float:
        return self.mae - self.closing_mae

    @property
    def gate(self) -> Gate:
        detail = f"model MAE − closing MAE is {self.gap:+.2f} pts (target ≤ +{MAE_GAP})"
        return Gate("pass" if self.gap <= MAE_GAP + _EPS else "fail", detail)


def accuracy(
    games: Sequence[tuple[float, float, int]], weeks: Sequence[WeekKey] | None = None
) -> Accuracy:
    """`games` are (pred_margin, spread_home, margin); with each game's week, the gap also gets
    its bootstrap interval."""
    if not games:
        raise ValueError("no games to score")
    model = [p - m for p, _, m in games]
    closing = [-s - m for _, s, m in games]
    interval = None
    if weeks is not None:
        diffs = [abs(a) - abs(b) for a, b in zip(model, closing, strict=True)]
        interval = mean_difference(zip(weeks, diffs, strict=True))
    n = len(games)
    return Accuracy(
        n,
        math.fsum(map(abs, model)) / n,
        math.fsum(map(abs, closing)) / n,
        math.sqrt(math.fsum(e * e for e in model) / n),
        math.sqrt(math.fsum(e * e for e in closing) / n),
        interval,
    )


# Buckets and the edge trend


@dataclass(frozen=True, slots=True)
class Bucket:
    label: str
    record: Record


def buckets(
    points: Iterable[tuple[float, Result]],
    bounds: Sequence[tuple[float, str]],
    below: str | None = None,
) -> tuple[Bucket, ...]:
    """Records by edge size: each bucket from its bound up to the next. Edges under the first
    bound go in `below`, shown only when it has any."""
    grouped: dict[str, list[Result]] = defaultdict(list)
    for size, result in points:
        label = below
        for bound, name in bounds:
            if abs(size) >= bound:
                label = name
        if label is None:
            raise ValueError(f"edge {size} is below the first bucket")
        grouped[label].append(result)
    out = [Bucket(below, Record.of(grouped[below]))] if below and grouped[below] else []
    return (*out, *(Bucket(name, Record.of(grouped[name])) for _, name in bounds))


@dataclass(frozen=True, slots=True)
class EdgeTrend:
    games: int  # pushes left out
    intercept: float | None  # None: the fit doesn't exist (one outcome, or they separate)
    slope: float | None  # log-odds of covering per point of edge
    slope_low: float | None
    slope_high: float | None
    buckets: tuple[Bucket, ...]

    @property
    def gate(self) -> Gate:
        if self.slope is None or self.slope_low is None or self.slope_high is None:
            return Gate("n/a", "the outcomes don't vary enough to fit a slope")
        detail = (
            f"slope {self.slope:+.3f} per point of edge, 95% interval "
            f"{self.slope_low:+.3f} to {self.slope_high:+.3f} (target: above zero)"
        )
        return Gate("pass" if self.slope_low > 0 else "fail", detail)


def _sigmoid(z: float) -> float:
    if z >= 0:
        return 1 / (1 + math.exp(-z))
    e = math.exp(z)
    return e / (1 + e)


def logistic(xs: Sequence[float], ys: Sequence[int]) -> tuple[float, float, float] | None:
    """Fit `P(y = 1) = σ(a + b·x)` by Newton's method; (a, b, the standard error of b), or None
    when the maximum doesn't exist (a single outcome, one x, or perfect separation)."""
    if len(set(ys)) < 2 or len(set(xs)) < 2:
        return None
    a = b = 0.0
    for _ in range(100):
        ga = gb = haa = hab = hbb = 0.0
        for x, y in zip(xs, ys, strict=True):
            p = _sigmoid(a + b * x)
            w = p * (1 - p)
            ga += y - p
            gb += (y - p) * x
            haa += w
            hab += w * x
            hbb += w * x * x
        det = haa * hbb - hab * hab
        if det <= 0:
            return None
        da = (hbb * ga - hab * gb) / det
        db = (haa * gb - hab * ga) / det
        a += da
        b += db
        if max(abs(da), abs(db)) < 1e-10:
            return a, b, math.sqrt(haa / det)  # Wald: the inverse information's [b, b] entry
    return None


def edge_trend(points: Iterable[tuple[float, Result]]) -> EdgeTrend:
    """Every eligible game's edge size against whether its edge side covered (04 § 9.4)."""
    listed = list(points)
    graded = [(abs(e), r) for e, r in listed if r != "P"]
    fit = logistic([e for e, _ in graded], [r == "W" for e, r in graded])
    shown = buckets(listed, EDGE_BUCKETS)
    if fit is None:
        return EdgeTrend(len(graded), None, None, None, None, shown)
    a, b, se = fit
    return EdgeTrend(len(graded), a, b, b - _Z * se, b + _Z * se, shown)


# Calibration


@dataclass(frozen=True, slots=True)
class CalibrationBin:
    low: float
    high: float | None  # None: the top bin, 65%+
    count: int  # pushes left out
    mean_prob: float | None
    hit_rate: float | None

    @property
    def label(self) -> str:
        if self.high is None:
            return f"{self.low * 100:g}%+"
        return f"{self.low * 100:g}–{self.high * 100:g}%"

    @property
    def off(self) -> float | None:
        """Mean predicted minus actual, in points: above zero is overconfident."""
        if self.mean_prob is None or self.hit_rate is None:
            return None
        return (self.mean_prob - self.hit_rate) * 100


@dataclass(frozen=True, slots=True)
class Calibration:
    bins: tuple[CalibrationBin, ...]

    @property
    def gate(self) -> Gate:
        full = [b for b in self.bins if b.count >= CALIBRATION_MIN_PICKS]
        if not full:
            return Gate("n/a", f"no bin holds {CALIBRATION_MIN_PICKS} picks yet")
        off = [b for b in full if b.off is not None and abs(b.off) > CALIBRATION_TOLERANCE + _EPS]
        if off:
            shown = ", ".join(f"{b.label} {b.off:+.1f}" for b in off if b.off is not None)
            return Gate("fail", f"bins over ±{CALIBRATION_TOLERANCE:g} pts: {shown}")
        return Gate(
            "pass",
            f"{len(full)} bin(s) of {CALIBRATION_MIN_PICKS}+ picks, each within "
            f"±{CALIBRATION_TOLERANCE:g} pts",
        )


def calibration(points: Iterable[tuple[float, Result]]) -> Calibration:
    """The displayed cover probability of the side the model likes, against whether it
    covered, in 2.5-point bins from 50% up to 65%+ (04 § 9.4)."""
    grouped: dict[int, list[tuple[float, Result]]] = defaultdict(list)
    for prob, result in points:
        if prob < CALIBRATION_BINS[0] - _EPS:
            raise ValueError(f"cover probability {prob} is below 50%: not the edge side's")
        if result != "P":
            index = sum(prob >= low - _EPS for low in CALIBRATION_BINS) - 1
            grouped[max(index, 0)].append((prob, result))
    bins = []
    for i, low in enumerate(CALIBRATION_BINS):
        high = CALIBRATION_BINS[i + 1] if i + 1 < len(CALIBRATION_BINS) else None
        rows = grouped[i]
        n = len(rows)
        mean = math.fsum(p for p, _ in rows) / n if n else None
        hit = sum(r == "W" for _, r in rows) / n if n else None
        bins.append(CalibrationBin(low, high, n, mean, hit))
    return Calibration(tuple(bins))


# Consistency across seasons


@dataclass(frozen=True, slots=True)
class Consistency:
    seasons: tuple[tuple[int, Record], ...]
    below_50: int
    best_season: int | None
    without_best: Record | None

    @property
    def gate(self) -> Gate:
        if self.best_season is None or self.without_best is None:
            return Gate("n/a", "needs picks in at least two seasons")
        pct = self.without_best.win_pct
        rest = "n/a" if pct is None else f"{pct * 100:.1f}%"
        detail = (
            f"{self.below_50} of {len(self.seasons)} seasons below 50% (at most "
            f"{SEASONS_BELOW_50}); without {self.best_season}, ATS {rest} "
            f"(target > {BREAK_EVEN * 100:.1f}%)"
        )
        ok = self.below_50 <= SEASONS_BELOW_50 and pct is not None and pct > BREAK_EVEN
        return Gate("pass" if ok else "fail", detail)


def consistency(by_season: Mapping[int, Sequence[Result]]) -> Consistency:
    """D-077: no more than 2 seasons below 50%, and the pool still clears break-even with the
    best season removed."""
    seasons = [
        (s, Record.of(by_season[s])) for s in sorted(by_season) if Record.of(by_season[s]).graded
    ]
    below = sum(1 for _, r in seasons if r.win_pct is not None and r.win_pct < 0.5)
    if len(seasons) < 2:
        return Consistency(tuple(seasons), below, None, None)
    best = max(seasons, key=lambda sr: sr[1].win_pct or 0.0)[0]  # ties: the earliest
    rest = Record.of(r for s, rs in by_season.items() if s != best for r in rs)
    return Consistency(tuple(seasons), below, best, rest)


# Grading a run's rows


@dataclass(frozen=True, slots=True)
class Graded:
    """One eligible game, graded as the app would have shown it."""

    week: WeekKey
    game_source_id: str
    pred_margin: float
    margin_sd: float
    home_win_prob: float
    spread_home: float  # the close
    spread_home_open: float | None  # the opener of the books that quoted both ends
    spread_home_open_close: float | None  # and those books' close: CLV's other end
    margin: int
    edge: float  # on the blended margin, against the close
    side: Side  # the side the edge likes
    prob: float  # P(side covers): the displayed cover probability
    result: Result  # the side, graded against the close
    pick: Pick | None  # the pick rules' call at the close
    open_pick: Pick | None  # and at the opener
    open_result: Result | None  # the opener pick, graded against the opener

    @property
    def season(self) -> int:
        return self.week[0]

    @property
    def postseason(self) -> bool:
        return self.week[1] == "postseason"

    @property
    def clv(self) -> float | None:
        """Points the opener pick's line beat the same books' close by (04 § 9.3, D-132)."""
        opened, closed = self.spread_home_open, self.spread_home_open_close
        if self.open_pick is None or opened is None or closed is None:
            return None
        moved = opened - closed
        return moved if self.open_pick.side == "home" else -moved


def grade_rows(
    rows: Iterable[Mapping[str, Any]], spec: ModelSpec, choices: Mapping[int, Choices]
) -> list[Graded]:
    """Grade each row with its season's resolved pick rules."""
    resolved: dict[int, ModelSpec] = {}
    out = []
    for row in rows:
        season = row["season"]
        if season not in resolved:
            resolved[season] = spec.resolve(choices.get(season, {}))
        rules = resolved[season].picks
        k = fixed(rules.market_shrinkage_k, "picks.market_shrinkage_k")
        dist = NormalMargin(row["margin_sd"])
        close, opener = row["spread_home"], row.get("spread_home_open")
        cover = cover_probability(blended_margin(row["pred_margin"], close, k), close, dist)
        at_open = None if opener is None else pick(row["pred_margin"], opener, rules, dist)
        out.append(
            Graded(
                week=(season, row["season_type"], row["week"]),
                game_source_id=row["game_source_id"],
                pred_margin=row["pred_margin"],
                margin_sd=row["margin_sd"],
                home_win_prob=row["home_win_prob"],
                spread_home=close,
                spread_home_open=opener,
                spread_home_open_close=row.get("spread_home_open_close"),
                margin=row["margin"],
                edge=cover.edge,
                side=cover.side,
                prob=cover.prob,
                result=grade(cover.side, row["margin"], close),
                pick=pick(row["pred_margin"], close, rules, dist),
                open_pick=at_open,
                open_result=(
                    None
                    if at_open is None or opener is None
                    else grade(at_open.side, row["margin"], opener)
                ),
            )
        )
    return out


# The rest of § 9.4


@dataclass(frozen=True, slots=True)
class OpeningLine:
    games: int  # games with an opener
    picks: Record  # graded against the opener
    clv: float | None  # average, in points

    @property
    def warning(self) -> bool:
        """04 § 9.4: an average CLV at or below zero is a warning."""
        return self.clv is not None and self.clv <= 0


@dataclass(frozen=True, slots=True)
class Contest:
    weeks: int
    record: Record
    mean_prob: float | None  # the graded picks' average predicted cover
    gap: float | None  # mean_prob − hit rate, in points

    @property
    def warning(self) -> bool:
        """A larger gap is the winner's curse (04 § 4) and calls for more shrinkage."""
        return self.gap is not None and self.gap > CONTEST_GAP + _EPS


@dataclass(frozen=True, slots=True)
class WinProbability:
    games: int
    brier: float  # of home_win_prob
    market_brier: float  # of Φ(−spread_home / margin_sd): the line at the model's spread


@dataclass(frozen=True, slots=True)
class Group:
    label: str
    games: int
    mae: float
    closing_mae: float
    picks: Record


@dataclass(frozen=True, slots=True)
class Breakdown:
    name: str
    groups: tuple[Group, ...]


@dataclass(frozen=True, slots=True)
class Summary:
    """The reported (ungated) rows for a subset of games, e.g. the postseason on its own."""

    accuracy: Accuracy
    picks: Record
    win_probability: WinProbability


@dataclass(frozen=True, slots=True)
class Metrics:
    games: int
    seasons: tuple[int, ...]
    accuracy: Accuracy
    picks: Record  # qualifying picks against the close
    edge_trend: EdgeTrend
    consistency: Consistency
    calibration: Calibration
    opening: OpeningLine
    pick_buckets: tuple[Bucket, ...]
    contest: Contest
    win_probability: WinProbability
    breakdowns: tuple[Breakdown, ...]
    postseason: Summary | None
    holdout: bool

    @property
    def ats_gate(self) -> Gate:
        pct = self.picks.win_pct
        if pct is None:
            return Gate("n/a", "no graded picks")
        detail = f"{pct * 100:.1f}% on {self.picks} (target > {BREAK_EVEN * 100:.1f}%)"
        return Gate("pass" if pct > BREAK_EVEN else "fail", detail)

    @property
    def holdout_gate(self) -> Gate | None:
        """At promotion only (04 § 9.4): ATS over 50% and the MAE gap within +0.5."""
        if not self.holdout:
            return None
        pct = self.picks.win_pct
        if pct is None:
            return Gate("n/a", "no graded picks")
        ok = pct > 0.5 and self.accuracy.gate.status == "pass"
        detail = f"ATS {pct * 100:.1f}% (target > 50%), MAE gap {self.accuracy.gap:+.2f} pts"
        return Gate("pass" if ok else "fail", detail)

    @property
    def gates(self) -> tuple[tuple[str, Gate], ...]:
        named = (
            ("Margin MAE vs the closing line", self.accuracy.gate),
            ("ATS win % vs closing", self.ats_gate),
            ("Edge trend", self.edge_trend.gate),
            ("Consistency", self.consistency.gate),
            ("Calibration", self.calibration.gate),
        )
        holdout = self.holdout_gate
        return (*named, ("Holdout", holdout)) if holdout else named


def win_probability_score(games: Sequence[Graded]) -> WinProbability:
    def won(g: Graded) -> float:
        return 1.0 if g.margin > 0 else 0.0

    market = [win_probability(-g.spread_home, NormalMargin(g.margin_sd)) for g in games]
    return WinProbability(
        len(games),
        math.fsum((g.home_win_prob - won(g)) ** 2 for g in games) / len(games),
        math.fsum((p - won(g)) ** 2 for p, g in zip(market, games, strict=True)) / len(games),
    )


def contest(games: Sequence[Graded], picks: int = CONTEST_PICKS) -> Contest:
    """Each week's top `picks` by displayed cover probability against the close, pooled."""
    weeks: dict[WeekKey, list[Graded]] = defaultdict(list)
    for g in games:
        weeks[g.week].append(g)
    top = [
        g
        for week in sorted(weeks)
        for g in sorted(weeks[week], key=lambda g: (-g.prob, g.game_source_id))[:picks]
    ]
    record = Record.of(g.result for g in top)
    graded = [g for g in top if g.result != "P"]
    if not graded or record.win_pct is None:
        return Contest(len(weeks), record, None, None)
    mean = math.fsum(g.prob for g in graded) / len(graded)
    return Contest(len(weeks), record, mean, (mean - record.win_pct) * 100)


def breakdown(
    name: str, games: Sequence[Graded], key: Callable[[Graded], str], order: Sequence[str] = ()
) -> Breakdown:
    """Accuracy and picks by any per-game key; groups in `order`, then the rest by label.
    M4.1's conference tier is one more key (04 § 10.4)."""
    grouped: dict[str, list[Graded]] = defaultdict(list)
    for g in games:
        grouped[key(g)].append(g)
    labels = [o for o in order if o in grouped] + sorted(set(grouped) - set(order))
    groups = []
    for label in labels:
        rows = grouped[label]
        acc = accuracy([(g.pred_margin, g.spread_home, g.margin) for g in rows])
        record = Record.of(g.result for g in rows if g.pick is not None)
        groups.append(Group(label, len(rows), acc.mae, acc.closing_mae, record))
    return Breakdown(name, tuple(groups))


WEEK_GROUPS = ("Weeks 1–3", "Weeks 4–6", "Weeks 7–9", "Weeks 10–12", "Weeks 13+", "Postseason")
# By bound, not half-point: a median close can sit on a quarter point.
SPREAD_GROUPS = ("Up to 3", "Over 3 to 7", "Over 7 to 14", "Over 14 to 21", "Over 21")
SIDE_GROUPS = ("Likes the favorite", "Likes the underdog", "Pick'em")


def week_group(g: Graded) -> str:
    if g.postseason:
        return "Postseason"
    week = g.week[2]
    for last, label in zip((3, 6, 9, 12), WEEK_GROUPS, strict=False):
        if week <= last:
            return label
    return "Weeks 13+"


def spread_group(g: Graded) -> str:
    size = abs(g.spread_home)
    for top, label in zip((3, 7, 14, 21), SPREAD_GROUPS, strict=False):
        if size <= top:
            return label
    return "Over 21"


def side_group(g: Graded) -> str:
    if g.spread_home == 0:
        return "Pick'em"
    favorite: Side = "home" if g.spread_home < 0 else "away"
    return "Likes the favorite" if g.side == favorite else "Likes the underdog"


def summary(games: Sequence[Graded]) -> Summary:
    errors = [(g.pred_margin, g.spread_home, g.margin) for g in games]
    return Summary(
        accuracy(errors, [g.week for g in games]),
        Record.of(g.result for g in games if g.pick is not None),
        win_probability_score(games),
    )


def compute(
    rows: Iterable[Mapping[str, Any]],
    spec: ModelSpec,
    choices: Mapping[int, Choices],
    *,
    holdout: bool = False,
) -> Metrics:
    """Every § 9.4 row the run's rows support."""
    games = grade_rows(rows, spec, choices)
    if not games:
        raise ValueError("the run has no rows")
    picked = [g for g in games if g.pick is not None]
    by_season: dict[int, list[Result]] = defaultdict(list)
    for g in picked:
        by_season[g.season].append(g.result)
    opened = [g for g in games if g.spread_home_open is not None]
    at_open = [g for g in opened if g.open_pick is not None]
    clvs = [c for g in at_open if (c := g.clv) is not None]
    post = [g for g in games if g.postseason]
    return Metrics(
        games=len(games),
        seasons=tuple(sorted({g.season for g in games})),
        accuracy=summary(games).accuracy,
        picks=Record.of(g.result for g in picked),
        edge_trend=edge_trend((g.edge, g.result) for g in games),
        consistency=consistency(by_season),
        calibration=calibration((g.prob, g.result) for g in games),
        opening=OpeningLine(
            len(opened),
            Record.of(g.open_result for g in at_open if g.open_result is not None),
            math.fsum(clvs) / len(clvs) if clvs else None,
        ),
        pick_buckets=buckets(((g.edge, g.result) for g in picked), PICK_BUCKETS, below="Under 2.5"),
        contest=contest(games),
        win_probability=win_probability_score(games),
        breakdowns=(
            breakdown("Week of season", games, week_group, WEEK_GROUPS),
            breakdown("Spread size (closing, either side)", games, spread_group, SPREAD_GROUPS),
            breakdown(
                "Favorite or underdog (the side the model likes)", games, side_group, SIDE_GROUPS
            ),
        ),
        postseason=summary(post) if post else None,
        holdout=holdout,
    )
