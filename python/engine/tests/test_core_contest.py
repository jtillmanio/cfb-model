"""Contest mode's ranking and the NFL rows' market-implied share (TASK-071, D-174, 04 § 4)."""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta

import pytest

from engine.core import NFL_MARGIN_SD, RankRow, market_gap, rank

T0 = datetime(2026, 10, 10, 16, tzinfo=UTC)


def _phi(x: float) -> float:
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


# market_gap: the design's NFL rows (contest-data.js), home lines.


@pytest.mark.parametrize(
    ("contest", "market", "points", "side", "shown"),
    [
        (3.0, 4.5, 1.5, "away", 54),  # BUF −3 at NYJ, market BUF −4.5: Bills +1.5
        (1.0, 1.5, 0.5, "away", 51),  # HOU −1 at JAX, market −1.5
        (-6.0, -7.0, 1.0, "home", 53),  # PHI −6, market −7: Eagles +1
    ],
)
def test_a_gap_favours_the_side_the_contest_line_gives_more(contest, market, points, side, shown):
    gap = market_gap(contest, market)
    assert gap.points == points
    assert gap.side == side
    assert gap.prob == pytest.approx(_phi(points / NFL_MARGIN_SD))
    assert round(gap.prob * 100) == shown


def test_no_gap_has_no_side_and_is_a_coin_flip():
    gap = market_gap(-2.5, -2.5)  # KC at BAL
    assert (gap.points, gap.side, gap.prob) == (0.0, None, 0.5)


# rank


def _row(key, prob, edge=None, *, model=True, locked=False, minutes=0) -> RankRow:
    return RankRow(key, prob, edge, model, locked, T0 + timedelta(minutes=minutes))


def test_open_games_rank_by_cover_then_edge():
    rows = [
        _row("a", 0.55, 2.0),
        _row("b", 0.60, 3.0),
        _row("c", 0.55, -4.0),  # the same cover, a bigger edge (away)
        _row("d", 0.70, 6.0),
    ]
    assert [r.key for r in rank(rows, 2)] == ["d", "b", "c", "a"]
    assert [r.rank for r in rank(rows, 2)] == [1, 2, 3, 4]


def test_a_no_model_row_ties_as_edge_0_then_by_kickoff():
    rows = [_row("nfl", 0.55, None, model=False), _row("cfb", 0.55, 0.5, minutes=60)]
    assert [r.key for r in rank(rows, 1)] == ["cfb", "nfl"]
    rows = [_row("late", 0.55, 1.0, minutes=60), _row("early", 0.55, 1.0)]
    assert [r.key for r in rank(rows, 1)] == ["early", "late"]


def test_the_top_n_takes_only_games_with_a_model_and_next_best_follows_the_nth():
    rows = [
        _row("c1", 0.66, 5.7),
        _row("n1", 0.64, None, model=False),
        _row("c2", 0.62, 4.4),
        _row("c3", 0.60, 3.6),
        _row("n2", 0.54, None, model=False),
        _row("c4", 0.52, 0.9),
    ]
    ranked = rank(rows, 3)
    assert [r.key for r in ranked if r.top_n] == ["c1", "c2", "c3"]
    assert [r.key for r in ranked if r.next_best] == ["n2"]


def test_no_next_best_when_the_top_n_takes_the_last_row():
    ranked = rank([_row("a", 0.6, 3.0), _row("b", 0.55, 2.0)], 2)
    assert [r.top_n for r in ranked] == [True, True]
    assert not any(r.next_best for r in ranked)


def test_a_locked_game_leaves_the_open_ranking_and_keeps_where_it_stood():
    rows = [
        _row("bsu", 0.70, 6.0, locked=True),
        _row("a", 0.60, 3.0),
        _row("b", 0.55, 2.0),
        _row("c", 0.52, 1.0),
    ]
    ranked = rank(rows, 2)
    assert [(r.key, r.rank, r.locked, r.top_n) for r in ranked] == [
        ("a", 1, False, True),
        ("b", 2, False, True),
        ("c", 3, False, False),
        ("bsu", 1, True, False),
    ]
    assert [r.key for r in ranked if r.next_best] == ["c"]


def test_once_every_game_is_locked_the_whole_slate_is_the_ranking():
    rows = [
        _row("a", 0.60, 3.0, locked=True),
        _row("b", 0.70, 6.0, locked=True),
        _row("c", 0.52, 1.0, locked=True),
    ]
    ranked = rank(rows, 2)
    assert [(r.key, r.rank, r.top_n) for r in ranked] == [
        ("b", 1, True),
        ("a", 2, True),
        ("c", 3, False),
    ]
    assert not any(r.next_best for r in ranked)
