"""`latest_team_ratings` and `team_rankings` (TASK-035): each FBS team's rank entering a week from
its version's newest succeeded run, and how far it moved since the week before.

The constructed rows use the throwaway sport in `model_rows` and roll back (db_conn); the seeded
test reads the fixture CI loads before pytest (`pnpm db:seed`, D-089)."""

from __future__ import annotations

import json
from datetime import timedelta
from typing import Any

import model_rows as m
from sqlalchemy import Connection, text

from db.config import repo_root

SEEDS = repo_root() / "python" / "db" / "seeds" / "fixture"


def _rankings(conn: Connection, version_id: int, week: int) -> dict[int, dict[str, Any]]:
    rows = conn.execute(
        text(
            "SELECT * FROM team_rankings"
            " WHERE model_version_id = :v AND season = :season AND week = :week"
        ),
        {"v": version_id, "season": m.SEASON, "week": week},
    )
    return {r.team_id: dict(r._mapping) for r in rows}


def test_newest_succeeded_run_is_ranked(db_conn: Connection):
    """AC-2: a newer failed run and an older succeeded run are both ignored."""
    m.sport(db_conn)
    a, b, c = m.team(db_conn, "a"), m.team(db_conn, "b"), m.team(db_conn, "c")
    v = m.version(db_conn)
    as_of = m.utc(2030, 9, 5, 16)
    old = m.run(db_conn, v, 1, as_of, finished_at=as_of + timedelta(hours=1))
    new = m.run(db_conn, v, 1, as_of, finished_at=as_of + timedelta(hours=2))
    failed = m.run(db_conn, v, 1, as_of, status="failed", finished_at=as_of + timedelta(hours=3))
    m.ratings(db_conn, old, v, 1, as_of, {a: 1.0, b: 2.0, c: 3.0})
    m.ratings(db_conn, new, v, 1, as_of, {a: 9.0, b: 5.0, c: 7.0})
    m.ratings(db_conn, failed, v, 1, as_of, {a: -9.0, b: 50.0, c: 0.0})

    ranks = _rankings(db_conn, v, 1)

    assert {t: (r["rank"], r["rating"], r["model_run_id"]) for t, r in ranks.items()} == {
        a: (1, 9.0, new),
        c: (2, 7.0, new),
        b: (3, 5.0, new),
    }
    assert all(r["previous_rank"] is None and r["rank_change"] is None for r in ranks.values())


def test_a_newer_backtest_run_of_the_week_doesnt_hide_its_ratings(db_conn: Connection):
    """A backtest run may carry a season and week (0003's CHECK) but writes no team_ratings, so
    only scheduled and ad-hoc runs are read."""
    m.sport(db_conn)
    a, b = m.team(db_conn, "a"), m.team(db_conn, "b")
    v = m.version(db_conn)
    as_of = m.utc(2030, 9, 5, 16)
    rated = m.run(db_conn, v, 1, as_of, finished_at=as_of + timedelta(hours=1))
    m.run(db_conn, v, 1, as_of, run_type="backtest", finished_at=as_of + timedelta(hours=2))
    m.ratings(db_conn, rated, v, 1, as_of, {a: 2.0, b: 1.0})

    ranks = _rankings(db_conn, v, 1)

    assert {t: (r["rank"], r["model_run_id"]) for t, r in ranks.items()} == {
        a: (1, rated),
        b: (2, rated),
    }


def test_change_is_last_weeks_rank_minus_this_weeks(db_conn: Connection):
    """AC-2: FBS teams only; ties share a rank; a team new to the ranks has no change."""
    m.sport(db_conn)
    a, b, c, d = (m.team(db_conn, s) for s in "abcd")
    fcs, unknown = m.team(db_conn, "fcs", "fcs"), m.team(db_conn, "unknown", None)
    v = m.version(db_conn)
    w1, w2 = m.utc(2030, 9, 5, 16), m.utc(2030, 9, 12, 16)
    r1, r2 = m.run(db_conn, v, 1, w1), m.run(db_conn, v, 2, w2)
    m.ratings(db_conn, r1, v, 1, w1, {a: 10.0, b: 8.0, c: 6.0, fcs: 50.0, unknown: 40.0})
    m.ratings(db_conn, r2, v, 2, w2, {a: 5.0, b: 9.0, c: 9.0, d: 1.0, fcs: 50.0})

    ranks = _rankings(db_conn, v, 2)

    assert set(ranks) == {a, b, c, d}
    assert {t: (r["rank"], r["previous_rank"], r["rank_change"]) for t, r in ranks.items()} == {
        b: (1, 2, 1),
        c: (1, 3, 2),
        a: (3, 1, -2),
        d: (4, None, None),
    }


def test_seeded_week_6_order_and_change(db_conn: Connection):
    """AC-2: v1.0's week-6 order and changes are the seed's week-5 and week-6 ratings ranked
    among its FBS teams."""
    teams = json.loads((SEEDS / "teams.json").read_text("utf-8"))
    ratings = json.loads((SEEDS / "models.json").read_text("utf-8"))["ratings"]
    fbs = {t["source_id"] for t in teams["teams"] if t["division"] == "fbs"}
    weeks = ratings["weeks"]

    def expected(week: int) -> dict[str, int]:
        by_team = {t: r[weeks.index(week)] for t, r in ratings["teams"].items() if t in fbs}
        return {t: 1 + sum(o > r for o in by_team.values()) for t, r in by_team.items()}

    week6, week5 = expected(6), expected(5)
    rows = db_conn.execute(
        text(
            "SELECT t.source_id, r.rank, r.previous_rank, r.rank_change"
            " FROM team_rankings r"
            " JOIN model_versions v ON v.id = r.model_version_id"
            " JOIN teams t ON t.id = r.team_id"
            " WHERE v.sport_id = 'cfb' AND v.market = 'spread' AND v.name = 'power'"
            " AND v.version = 'v1.0' AND r.season = 2026 AND r.week = 6"
        )
    ).all()

    assert {r.source_id: r.rank for r in rows} == week6
    assert {r.source_id: r.previous_rank for r in rows} == week5
    assert {r.source_id: r.rank_change for r in rows} == {t: week5[t] - week6[t] for t in week6}
    assert sorted(week6, key=week6.__getitem__)[:3] == ["osu", "tex", "ore"]


def assert_index_reads(conn: Connection, view: str) -> None:
    """Every read of team_ratings for one team's week is an index lookup by its version or its run,
    and the week's own ratings are entered by week (AC-4). With sequential scans priced out, a
    view that ranked every rating first would still show a Seq Scan, an index scan with no
    condition, or no read by week. The week before may be read through the version's season
    (the planner's choice, D-136), never the version's whole history."""
    version_id, team_id = conn.execute(
        text(
            "SELECT r.model_version_id, r.team_id FROM team_ratings r"
            " JOIN model_versions v ON v.id = r.model_version_id"
            " WHERE v.sport_id = 'cfb' AND v.name = 'power' AND v.version = 'v1.0'"
            " AND r.season = 2026 AND r.week = 6 LIMIT 1"
        )
    ).one()
    plan = m.explain(
        conn,
        f"SELECT * FROM {view} WHERE model_version_id = :v"
        " AND team_id = :t AND season = 2026 AND week = 6",
        {"v": version_id, "t": team_id},
    )

    scans = m.scans(plan, "team_ratings")
    assert scans
    conds = []
    for node in scans:
        assert node["Node Type"] != "Seq Scan", node
        cond = node.get("Index Cond") or node.get("Recheck Cond") or ""
        assert "model_version_id" in cond or "model_run_id" in cond, node
        assert "season" in cond or "model_run_id" in cond, node
        conds.append(cond)
    assert any("week" in cond for cond in conds), conds


def test_single_team_read_uses_index(db_conn: Connection):
    """AC-4."""
    assert_index_reads(db_conn, "team_rankings")


def test_views_readme_lists_every_view_with_its_test():
    """AC-4: python/db/views/README.md has a row per view file naming a test that exists."""
    views = repo_root() / "python" / "db" / "views"
    rows = {
        cells[1].strip("` "): cells[3].strip("` ")
        for line in (views / "README.md").read_text("utf-8").splitlines()
        if (cells := line.split("|")) and len(cells) == 5 and cells[1].strip().endswith(".sql`")
    }

    assert set(rows) == {p.name for p in views.glob("*.sql")}
    assert {
        "020_latest_team_ratings.sql",
        "030_team_rankings.sql",
        "040_team_schedule_strength.sql",
    } <= set(rows)
    for test in rows.values():
        assert (repo_root() / test).is_file(), test
