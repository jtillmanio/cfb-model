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


# TASK-047 AC-2: postseason week 1 is a week of its own (D-150).


def _ranked(
    conn: Connection, view: str, version_id: int, season_type: str, week: int
) -> dict[int, dict[str, Any]]:
    rows = conn.execute(
        text(
            f"SELECT * FROM {view} WHERE model_version_id = :v AND season = :season"
            " AND season_type = :season_type AND week = :week"
        ),
        {"v": version_id, "season": m.SEASON, "season_type": season_type, "week": week},
    )
    return {r.team_id: dict(r._mapping) for r in rows}


def test_regular_and_postseason_week_1_are_different_weeks(db_conn: Connection):
    """A season's regular week 1 and its postseason week 1 (every bowl and CFP game) are read
    from their own runs, each ranked on its own, however much newer the postseason run is."""
    m.sport(db_conn)
    a, b = m.team(db_conn, "a"), m.team(db_conn, "b")
    v = m.version(db_conn)
    w1, bowls = m.utc(2030, 8, 31, 16), m.utc(2030, 12, 14, 17)
    regular = m.run(db_conn, v, 1, w1)
    post = m.run(db_conn, v, 1, bowls, season_type="postseason", run_type="scheduled")
    m.ratings(db_conn, regular, v, 1, w1, {a: 1.0, b: 2.0})
    m.ratings(db_conn, post, v, 1, bowls, {a: 9.0, b: 5.0}, season_type="postseason")

    for view in ("latest_team_ratings", "team_rankings"):
        read = {
            t: (r["season_type"], r["rank"], r["rating"], r["model_run_id"], r["as_of"])
            for t, r in _ranked(db_conn, view, v, "regular", 1).items()
        }
        assert read == {
            b: ("regular", 1, 2.0, regular, w1),
            a: ("regular", 2, 1.0, regular, w1),
        }, view
        read = {
            t: (r["season_type"], r["rank"], r["rating"], r["model_run_id"], r["as_of"])
            for t, r in _ranked(db_conn, view, v, "postseason", 1).items()
        }
        assert read == {
            a: ("postseason", 1, 9.0, post, bowls),
            b: ("postseason", 2, 5.0, post, bowls),
        }, view
    regular_week = _ranked(db_conn, "team_rankings", v, "regular", 1)
    assert all(r["previous_rank"] is None for r in regular_week.values())


def test_postseason_change_is_from_the_last_rated_regular_week(db_conn: Connection):
    """Entering the bowls, the week before is the version's last succeeded regular week of the
    season (a failed run of a later week rated nothing), never regular week 0 or week 1."""
    m.sport(db_conn)
    a, b, c = (m.team(db_conn, s) for s in "abc")
    v = m.version(db_conn)
    w1, w14, w15, w16 = (m.utc(2030, *d, 16) for d in ((8, 31), (11, 30), (12, 7), (12, 14)))
    bowls = m.utc(2030, 12, 20, 17)
    for week, as_of, by_team in (
        (1, w1, {a: 3.0, b: 2.0, c: 1.0}),
        (14, w14, {a: 1.0, b: 2.0, c: 3.0}),
        (15, w15, {a: 3.0, b: 2.0, c: 1.0}),
    ):
        m.ratings(db_conn, m.run(db_conn, v, week, as_of), v, week, as_of, by_team)
    m.run(db_conn, v, 16, w16, status="failed")
    post = m.run(db_conn, v, 1, bowls, season_type="postseason")
    m.ratings(db_conn, post, v, 1, bowls, {a: 2.0, b: 3.0, c: 0.5}, season_type="postseason")

    ranks = _ranked(db_conn, "team_rankings", v, "postseason", 1)

    assert {t: (r["rank"], r["previous_rank"], r["rank_change"]) for t, r in ranks.items()} == {
        b: (1, 2, 1),
        a: (2, 1, -1),
        c: (3, 3, 0),
    }


def test_seeded_week_6_order_and_change(db_conn: Connection):
    """AC-2: v1.0's week-6 order and changes are the seed's week-5 and week-6 ratings ranked
    among its FBS teams."""
    teams = json.loads((SEEDS / "teams.json").read_text("utf-8"))
    ratings = json.loads((SEEDS / "models.json").read_text("utf-8"))["ratings"]
    filler = json.loads((SEEDS / "week6_filler.json").read_text("utf-8"))  # TASK-055
    fbs = {t["source_id"] for t in teams["teams"] + filler["teams"] if t["division"] == "fbs"}
    weeks = ratings["weeks"]
    seeded = ratings["teams"] | {r["team"]: r["by_week"] for r in filler["ratings"]}

    def expected(week: int) -> dict[str, int]:
        by_team = {t: r[weeks.index(week)] for t, r in seeded.items() if t in fbs}
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


def assert_index_reads(
    conn: Connection, view: str, season_type: str = "regular", week: int = 6
) -> None:
    """Every read of team_ratings for one team's week is an index lookup by its version or its run,
    and the week's own ratings are entered by week (AC-4). With sequential scans priced out, a
    view that ranked every rating first would still show a Seq Scan, an index scan with no
    condition, or no read by week. The week before may be read through the version's season
    (the planner's choice, D-136), never the version's whole history. A week is read as the app
    reads it, by season type too (D-150)."""
    version_id, team_id = conn.execute(
        text(
            "SELECT r.model_version_id, r.team_id FROM team_ratings r"
            " JOIN model_versions v ON v.id = r.model_version_id"
            " WHERE v.sport_id = 'cfb' AND v.name = 'power' AND v.version = 'v1.0'"
            " AND r.season = 2026 AND r.season_type = :st AND r.week = :week LIMIT 1"
        ),
        {"st": season_type, "week": week},
    ).one()
    plan = m.explain(
        conn,
        f"SELECT * FROM {view} WHERE model_version_id = :v"
        " AND team_id = :t AND season = 2026 AND season_type = :st AND week = :week",
        {"v": version_id, "t": team_id, "st": season_type, "week": week},
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


def seed_postseason_week(conn: Connection) -> None:
    """The seeded v1.0's week-6 ratings again, as a scheduled run entering 2026's bowls."""
    week6 = conn.execute(
        text(
            "SELECT r.id, r.model_version_id FROM model_runs r"
            " JOIN model_versions v ON v.id = r.model_version_id"
            " WHERE v.sport_id = 'cfb' AND v.name = 'power' AND v.version = 'v1.0'"
            " AND r.run_type = 'scheduled' AND r.season = 2026 AND r.week = 6"
        )
    ).one()
    bowls = m.utc(2026, 12, 19, 17)
    run_id = conn.execute(
        text(
            "INSERT INTO model_runs (model_version_id, run_type, season, season_type, week, as_of,"
            " status, started_at, finished_at)"
            " VALUES (:v, 'scheduled', 2026, 'postseason', 1, :as_of, 'succeeded', :as_of,"
            " :as_of) RETURNING id"
        ),
        {"v": week6.model_version_id, "as_of": bowls},
    ).scalar_one()
    conn.execute(
        text(
            "INSERT INTO team_ratings (model_run_id, model_version_id, team_id, season,"
            " season_type, week, as_of, rating)"
            " SELECT :run, model_version_id, team_id, 2026, 'postseason', 1, :as_of, rating"
            " FROM team_ratings WHERE model_run_id = :week6"
        ),
        {"run": run_id, "as_of": bowls, "week6": week6.id},
    )


def test_postseason_single_team_read_uses_index(db_conn: Connection):
    """TASK-047: entering the bowls, the week before is found through the version's runs, and
    the ratings are still read by index (D-150)."""
    seed_postseason_week(db_conn)
    assert_index_reads(db_conn, "team_rankings", "postseason", 1)


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
