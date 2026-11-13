"""`model_record` (TASK-041): the current market picks' record through each week, alone, to date,
and to date by tier and by edge bucket (04 § 9.3: pushes count in W-L-P, not in win %; −110).

The seeded tests read the fixture CI loads before pytest (`pnpm db:seed`, D-089): v1.0's weeks 1–5
are 31-24-1, +4.6u (sample-data.md § 7), and week 6 has one final game (Tulane @ Memphis, a
win) and 8 pending. The constructed rows use the throwaway sport and roll back (db_conn)."""

from __future__ import annotations

from collections import Counter
from datetime import timedelta
from decimal import Decimal
from typing import Any

import model_rows as m
from sqlalchemy import Connection, text
from test_current_picks import SEEDED_V1

BUCKETS = ((7.0, "7.0+"), (5.0, "5.0-7.0"), (3.5, "3.5-5.0"), (2.5, "2.5-3.5"))


def _record(conn: Connection, version_id: int, season: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        text("SELECT * FROM model_record WHERE model_version_id = :v AND season = :s"),
        {"v": version_id, "s": season},
    )
    return [dict(r._mapping) for r in rows]


def _seeded(conn: Connection) -> list[dict[str, Any]]:
    return _record(conn, conn.execute(text(SEEDED_V1)).scalar_one(), 2026)


def _through(rows: list[dict[str, Any]], breakdown: str, week: int) -> list[dict[str, Any]]:
    return [
        r
        for r in rows
        if r["breakdown"] == breakdown and (r["season_type"], r["week"]) == ("regular", week)
    ]


def _wlp(row: dict[str, Any]) -> tuple[int, int, int]:
    return row["wins"], row["losses"], row["pushes"]


def test_seeded_season_record(db_conn: Connection):
    """AC-4: through week 5, 31-24-1, 56.4% (pushes out), +4.6u, ROI +7.6%, avg CLV +0.9."""
    (row,) = _through(_seeded(db_conn), "to_date", 5)

    assert (row["picks"], *_wlp(row), row["voids"], row["pending"]) == (56, 31, 24, 1, 0, 0)
    assert round(row["win_pct"], 1) == Decimal("56.4")
    assert row["units"] == Decimal("4.6")
    assert round(row["roi_pct"], 1) == Decimal("7.6")
    assert round(row["avg_clv"], 1) == Decimal("0.9")
    assert (row["tier"], row["edge_bucket"]) == (None, None)


def test_seeded_tiers(db_conn: Connection):
    """AC-4: through week 5, A 7-3, B 12-9-1, C 12-12 at −1.2u."""
    tiers = {r["tier"]: r for r in _through(_seeded(db_conn), "tier", 5)}

    assert {t: _wlp(r) for t, r in tiers.items()} == {
        "A": (7, 3, 0),
        "B": (12, 9, 1),
        "C": (12, 12, 0),
    }
    assert tiers["C"]["units"] == Decimal("-1.2")
    assert round(tiers["C"]["win_pct"], 1) == Decimal("50.0")


def test_seeded_weeks(db_conn: Connection):
    """AC-4: each week's units add up to +1.8, +0.5, +2.9, +2.2, +4.6, which the to-date rows
    read; week 6 alone is 1-0 with 8 pending and +1.0u."""
    rows = _seeded(db_conn)
    weeks = {r["week"]: r for r in rows if r["breakdown"] == "week"}
    to_date = {r["week"]: r for r in rows if r["breakdown"] == "to_date"}
    assert set(weeks) == set(to_date) == {1, 2, 3, 4, 5, 6}

    running, cumulative = Decimal(0), []
    for week in range(1, 6):
        running += weeks[week]["units"]
        cumulative.append(running)
    assert cumulative == [Decimal(u) for u in ("1.8", "0.5", "2.9", "2.2", "4.6")]
    assert [to_date[w]["units"] for w in range(1, 6)] == cumulative

    six = weeks[6]
    assert (*_wlp(six), six["pending"], six["units"]) == (1, 0, 0, 8, Decimal("1.0"))
    assert _wlp(to_date[6]) == (32, 24, 1)


def test_seeded_buckets_count_their_picks(db_conn: Connection):
    """AC-4: through week 5, each pick bucket counts exactly the weeks 1–5 picks whose
    abs(edge_pts) falls in it."""
    edges = db_conn.execute(
        text(
            "SELECT p.edge_pts FROM picks p JOIN games g ON g.id = p.game_id"
            f" WHERE p.model_version_id = ({SEEDED_V1}) AND g.season = 2026 AND g.week <= 5"
        )
    ).scalars()
    expected = Counter(next(b for at, b in BUCKETS if abs(e) >= at) for e in edges)
    assert sum(expected.values()) == 56

    buckets = {r["edge_bucket"]: r["picks"] for r in _through(_seeded(db_conn), "bucket", 5)}

    assert buckets == dict(expected)


def test_contest_picks_leave_the_record_alone(db_conn: Connection):
    """TASK-067 (AC-4): v1.0's contest picks on week-5 games (one per game, each on the side
    that covered) leave its record through week 5 at 31-24-1, +4.6u: it counts market picks
    only (D-142)."""
    games = db_conn.execute(
        text(
            "SELECT p.id AS prediction_id, p.game_id, g.kickoff_at,"
            " g.home_points - g.away_points AS margin, m.closing_spread_home AS close"
            " FROM predictions p JOIN games g ON g.id = p.game_id"
            " JOIN game_market m ON m.game_id = g.id"
            f" WHERE p.model_version_id = ({SEEDED_V1}) AND g.season = 2026 AND g.week = 5"
            " ORDER BY g.id LIMIT 3"
        )
    ).all()
    assert len(games) == 3
    version_id = db_conn.execute(text(SEEDED_V1)).scalar_one()
    contest_id = m.contest(db_conn, m.user(db_conn))
    for g in games:
        line = float(g.close) + 0.5 if float(g.close) % 1 == 0 else float(g.close)
        side = "home" if g.margin + line > 0 else "away"
        picked_at = g.kickoff_at - timedelta(days=2)
        contest_line = m.contest_line(db_conn, contest_id, g.game_id, line, picked_at, period=5)
        m.contest_pick(db_conn, g.prediction_id, version_id, g.game_id, contest_line,
                       picked_at + timedelta(minutes=5), side=side, line=line,
                       edge_pts=3.0 if side == "home" else -3.0)  # fmt: skip
    graded = db_conn.execute(
        text(
            "SELECT result FROM pick_outcomes WHERE model_version_id = :v AND is_current"
            " AND line_source = 'contest' AND game_id = ANY(:g)"
        ),
        {"v": version_id, "g": [g.game_id for g in games]},
    ).scalars()
    assert list(graded) == ["won"] * 3

    (row,) = _through(_seeded(db_conn), "to_date", 5)
    assert (row["picks"], *_wlp(row), row["units"]) == (56, 31, 24, 1, Decimal("4.6"))
    (week,) = _through(_seeded(db_conn), "week", 5)
    assert week["picks"] == 15


def test_a_superseded_pick_counts_once(db_conn: Connection):
    """AC-5: a pick replaced before kickoff counts once, graded at the current pick's line. Home
    by 4 wins the first pick (home −1) and loses the second (away at home −2), so the record is
    one loss, not a win and a loss."""
    m.sport(db_conn)
    home, away = m.team(db_conn, "home"), m.team(db_conn, "away")
    game_id = m.game(db_conn, home, away, m.utc(2030, 9, 7, 16), week=1, points=(24, 20))
    version_id = m.version(db_conn)
    run_id = m.run(db_conn, version_id, 1, m.utc(2030, 9, 1, 10))
    prediction_id = m.prediction(db_conn, run_id, version_id, game_id)
    book_id = m.book(db_conn)
    sunday = m.line(db_conn, game_id, book_id, m.utc(2030, 9, 1, 10), -1.0)
    thursday = m.line(db_conn, game_id, book_id, m.utc(2030, 9, 5, 1), -2.0)
    m.pick(db_conn, prediction_id, version_id, game_id, sunday, m.utc(2030, 9, 1, 10, 10),
           side="home", line=-1.0, edge_pts=3.5, tier="B")  # fmt: skip
    m.pick(db_conn, prediction_id, version_id, game_id, thursday, m.utc(2030, 9, 5, 1),
           side="away", line=-2.0, edge_pts=-2.6, tier="C")  # fmt: skip

    outcomes = db_conn.execute(
        text("SELECT result, is_current FROM pick_outcomes WHERE game_id = :g ORDER BY pick_id"),
        {"g": game_id},
    ).all()
    assert [tuple(o) for o in outcomes] == [("won", False), ("lost", True)]

    rows = _record(db_conn, version_id, m.SEASON)
    assert {r["breakdown"] for r in rows} == {"week", "to_date", "tier", "bucket"}
    for row in rows:
        assert (row["picks"], *_wlp(row), row["units"]) == (1, 0, 1, 0, Decimal("-1.1")), row
    assert {r["tier"] for r in rows if r["breakdown"] == "tier"} == {"C"}
    assert {r["edge_bucket"] for r in rows if r["breakdown"] == "bucket"} == {"2.5-3.5"}


def test_one_season_record_uses_an_index(db_conn: Connection):
    """AC-6: one version's season reads picks through an index, never a sequential scan, and
    the version is applied at that scan, before any window or aggregate (a filter left above
    the aggregate, as under GROUPING SETS, grades every version's picks first). Which index the
    planner picks is its choice: every seeded pick is v1.0's, so the version index is no more
    selective than another."""
    version_id = db_conn.execute(text(SEEDED_V1)).scalar_one()

    plan = m.explain(
        db_conn,
        "SELECT * FROM model_record WHERE model_version_id = :v AND season = 2026",
        {"v": version_id},
    )

    scans = m.scans(plan, "picks")
    assert scans
    for node in scans:
        assert node["Node Type"] != "Seq Scan", node
        applied = " ".join(node.get(k, "") for k in ("Index Cond", "Recheck Cond", "Filter"))
        assert "model_version_id" in applied, node
