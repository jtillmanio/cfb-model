"""The contest views (TASK-068, D-171): `current_contest_lines`, `contest_results`,
`contest_record` and `current_contest_standing`.

The constructed rows use the throwaway sport in `model_rows` and roll back (db_conn); the seeded
tests read the fixture CI loads before pytest (`pnpm db:seed`, D-089): the Splash work league,
your weeks 1-6 entries and the model's weeks 1-5 contest picks (generate_contest.py)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any

import model_rows as m
import pytest
from sqlalchemy import Connection, text

SEEDED_CONTEST = (
    "SELECT c.id FROM contests c JOIN users u ON u.id = c.user_id"
    " WHERE u.github_id = 4242 AND c.name = 'Splash work league' AND c.deleted_at IS NULL"
)
SEEDED_V1 = (
    "SELECT id FROM model_versions WHERE sport_id = 'cfb' AND market = 'spread'"
    " AND name = 'power' AND version = 'v1.0' AND deleted_at IS NULL"
)
# Each view and the tables a one-contest read of it must reach by index (AC-6).
READS = {
    "current_contest_lines": ("contest_lines",),
    "contest_results": ("contest_entries", "contest_lines", "picks"),
    "contest_record": ("contest_entries", "contest_lines", "picks"),
    "current_contest_standing": ("contest_standings",),
}
VIEWS = tuple(READS)
KICKOFF = m.utc(2030, 9, 7, 16)  # Sat noon ET
CAPTURED = m.utc(2030, 9, 4, 1)  # Wed 9 PM ET


# ─── Constructed rows ─────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class World:
    user_id: int
    contest_id: int
    version_id: int
    run_id: int
    book_id: int


def _contest(conn: Connection, user_id: int, push: str = "zero", per_period: int = 4) -> int:
    rules = {
        "period": "week", "sports": ["cfb", "nfl"], "slate": "curated",
        "picks_per_period": per_period, "picks_exact": True, "lock": "per_game_kickoff",
        "scoring": "point_per_win", "push": push,
    }  # fmt: skip
    return conn.execute(
        text(
            "INSERT INTO contests (user_id, name, platform, season, rules)"
            " VALUES (:u, :name, 'splash', :season, CAST(:rules AS jsonb)) RETURNING id"
        ),
        {"u": user_id, "name": f"push {push}", "season": m.SEASON, "rules": json.dumps(rules)},
    ).scalar_one()


def _world(conn: Connection, push: str = "zero", per_period: int = 4) -> World:
    m.sport(conn)
    user_id = m.user(conn)
    version_id = m.version(conn, f"contest-{push}")
    return World(
        user_id=user_id,
        contest_id=_contest(conn, user_id, push, per_period),
        version_id=version_id,
        run_id=m.run(conn, version_id, 1, m.utc(2030, 9, 1, 10)),
        book_id=m.book(conn),
    )


_teams = iter(range(10**6))


def _game(
    conn: Connection,
    *,
    status: str = "final",
    points: tuple[int, int] = (30, 20),
    kickoff: datetime | None = KICKOFF,
    game_date: str | None = None,
) -> int:
    n = next(_teams)
    home, away = m.team(conn, f"cv-home-{n}"), m.team(conn, f"cv-away-{n}")
    return m.game(
        conn, home, away, kickoff, week=1, status=status, points=points, game_date=game_date
    )


def _entry(
    conn: Connection, w: World, game_id: int, line_id: int, side: str, created_at: datetime
) -> int:
    return conn.execute(
        text(
            "INSERT INTO contest_entries (user_id, contest_id, game_id, contest_line_id, side,"
            " created_at) VALUES (:u, :c, :g, :l, :side, :at) RETURNING id"
        ),
        {"u": w.user_id, "c": w.contest_id, "g": game_id, "l": line_id, "side": side,
         "at": created_at},
    ).scalar_one()  # fmt: skip


def _entered(
    conn: Connection, w: World, spread: float, side: str, **game: Any
) -> tuple[int, int]:
    """A game, its contest line captured Wednesday and your entry on it a minute later."""
    game_id = _game(conn, **game)
    line_id = m.contest_line(conn, w.contest_id, game_id, spread, CAPTURED)
    return game_id, _entry(conn, w, game_id, line_id, side, CAPTURED.replace(minute=1))


def _model_pick(
    conn: Connection, w: World, game_id: int, spread: float, side: str, prob: float
) -> int:
    """The model's contest pick on a game, at a contest line captured Wednesday."""
    line_id = m.contest_line(conn, w.contest_id, game_id, spread, CAPTURED)
    prediction_id = m.prediction(conn, w.run_id, w.version_id, game_id)
    return m.contest_pick(conn, prediction_id, w.version_id, game_id, line_id,
                          CAPTURED.replace(minute=2), side=side, line=spread,
                          model_prob=prob)  # fmt: skip


def _results(conn: Connection, contest_id: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        text(
            "SELECT * FROM contest_results WHERE contest_id = :c"
            " ORDER BY picker DESC, model_rank, entry_id"
        ),
        {"c": contest_id},
    )
    return [dict(r._mapping) for r in rows]


def _soft_delete(conn: Connection, table: str, row_id: int) -> None:
    conn.execute(text(f"UPDATE {table} SET deleted_at = now() WHERE id = :id"), {"id": row_id})


# ─── AC-1: current_contest_lines ──────────────────────────────────────────────────────────────


def test_texas_oklahoma_reads_the_contest_line_beside_the_market(db_conn: Connection):
    """AC-1: the seeded Week 6 Texas vs Oklahoma reads the contest's TEX −7 (OU +7) beside the
    market's TEX −6.5 and v1.0's TEX −1.3; one row per contest and game."""
    rows = db_conn.execute(
        text(
            "SELECT g.source_id, l.* FROM current_contest_lines l JOIN games g ON g.id = l.game_id"
            f" WHERE l.contest_id = ({SEEDED_CONTEST})"
        )
    ).all()
    ou = next(r for r in rows if r.source_id == "2026-w6-tex-ou")
    v1 = db_conn.execute(text(SEEDED_V1)).scalar_one()

    assert (ou.period, ou.spread_home, ou.market_spread_home) == (6, Decimal("7.0"), Decimal("6.5"))
    assert (ou.model_version_id, ou.model_spread_home) == (v1, pytest.approx(1.3))
    assert len(rows) == len({r.game_id for r in rows}) == 35  # weeks 1-5's 25 and week 6's 10
    buf = next(r for r in rows if r.source_id == "2026-w6-buf-nyj")
    assert buf.model_version_id is None and buf.model_spread_home is None  # NFL: no model


def test_the_newest_snapshot_before_kickoff_is_current(db_conn: Connection):
    """AC-1: the newest snapshot captured before kickoff is the line; one inserted after kickoff
    leaves the row unchanged."""
    w = _world(db_conn)
    game_id = _game(db_conn, status="scheduled")
    m.contest_line(db_conn, w.contest_id, game_id, -3.5, CAPTURED)
    newest = m.contest_line(db_conn, w.contest_id, game_id, -4.5, m.utc(2030, 9, 6, 1))

    def current() -> list[tuple[int, Decimal]]:
        return [
            (r.contest_line_id, r.spread_home)
            for r in db_conn.execute(
                text("SELECT * FROM current_contest_lines WHERE contest_id = :c"),
                {"c": w.contest_id},
            )
        ]

    assert current() == [(newest, Decimal("-4.5"))]
    m.contest_line(db_conn, w.contest_id, game_id, -6.5, m.utc(2030, 9, 7, 17))  # after kickoff
    assert current() == [(newest, Decimal("-4.5"))]


def test_a_tba_kickoff_takes_lines_through_the_end_of_its_eastern_day(db_conn: Connection):
    """AC-1: with no kickoff time, the cutoff is the end of game_date in Eastern time."""
    w = _world(db_conn)
    game_id = _game(db_conn, status="scheduled", kickoff=None, game_date="2030-09-07")
    late = m.contest_line(db_conn, w.contest_id, game_id, -3.5, m.utc(2030, 9, 8, 3))  # 11 PM ET
    m.contest_line(db_conn, w.contest_id, game_id, -5.5, m.utc(2030, 9, 8, 5))  # 1 AM ET, next day

    row = db_conn.execute(
        text("SELECT * FROM current_contest_lines WHERE contest_id = :c"), {"c": w.contest_id}
    ).one()
    assert (row.contest_line_id, row.spread_home) == (late, Decimal("-3.5"))


# ─── AC-2: grading and the push rule ──────────────────────────────────────────────────────────


def test_entries_grade_won_lost_push_pending_void(db_conn: Connection):
    """AC-2: each entry is graded at its contest line: won, lost or push on a final game (home
    30-20), pending while scheduled or in progress, void when canceled or postponed."""
    w = _world(db_conn)
    cases = [
        (-7.5, "home", {}, "won", Decimal("1.0"), True),
        (-10.5, "home", {}, "lost", Decimal("0.0"), True),
        (-10.0, "away", {}, "push", Decimal("0.0"), True),
        (-3.5, "home", {"status": "scheduled"}, "pending", None, False),
        (-3.5, "away", {"status": "in_progress"}, "pending", None, False),
        (-3.5, "home", {"status": "canceled"}, "void", None, False),
        (-3.5, "away", {"status": "postponed"}, "void", None, False),
    ]
    entries = [_entered(db_conn, w, spread, side, **game)[1] for spread, side, game, *_ in cases]

    rows = _results(db_conn, w.contest_id)

    assert [(r["entry_id"], r["picker"], r["result"], r["points"], r["counted"]) for r in rows] == [
        (e, "you", result, points, counted)
        for e, (*_, result, points, counted) in zip(entries, cases, strict=True)
    ]


@pytest.mark.parametrize(
    ("push", "points", "counted", "record_points"),
    [("zero", Decimal("0.0"), True, Decimal("1.0")), ("half", Decimal("0.5"), True,
     Decimal("1.5")), ("void", None, False, Decimal("1.0"))],
)  # fmt: skip
def test_push_points_follow_the_contest_rule(
    db_conn: Connection, push: str, points: Decimal | None, counted: bool, record_points: Decimal
):
    """AC-2: a push scores 0 under `zero`, 0.5 under `half`, and doesn't count under `void`;
    the week's points add a win's 1 to it."""
    w = _world(db_conn, push)
    _, pushed = _entered(db_conn, w, -10.0, "home")  # home by 10 at −10
    _entered(db_conn, w, -7.5, "home")  # a win

    row = next(r for r in _results(db_conn, w.contest_id) if r["entry_id"] == pushed)
    record = db_conn.execute(
        text(
            "SELECT * FROM contest_record WHERE contest_id = :c AND picker = 'you'"
            " AND breakdown = 'week'"
        ),
        {"c": w.contest_id},
    ).one()

    assert (row["result"], row["points"], row["counted"]) == ("push", points, counted)
    assert (record.wins, record.losses, record.pushes, record.points) == (1, 0, 1, record_points)


# ─── AC-3: the model's top N, soft deletes ────────────────────────────────────────────────────


def test_the_model_top_n_is_graded_apart(db_conn: Connection):
    """AC-3: the model's current contest picks are ranked within the week by model_prob and the
    first picks_per_period (2 here) graded like your entries, labelled 'model' with its
    version; a superseded pick doesn't count, and your entry on the same game stays 'you'."""
    w = _world(db_conn, per_period=2)
    games = [_game(db_conn) for _ in range(3)]  # home 30-20 each
    low = _model_pick(db_conn, w, games[0], -3.5, "home", 0.55)  # would win, ranks 3rd
    top = _model_pick(db_conn, w, games[1], -7.5, "home", 0.65)  # wins
    _model_pick(db_conn, w, games[2], -11.5, "home", 0.70)  # superseded below
    moved = m.contest_line(db_conn, w.contest_id, games[2], -12.5, m.utc(2030, 9, 5, 1))
    prediction_id = db_conn.execute(
        text("SELECT id FROM predictions WHERE game_id = :g"), {"g": games[2]}
    ).scalar_one()
    second = m.contest_pick(db_conn, prediction_id, w.version_id, games[2], moved,
                            m.utc(2030, 9, 5, 1, 5), side="away", line=-12.5,
                            model_prob=0.60)  # fmt: skip
    yours = _entry(db_conn, w, games[1], db_conn.execute(
        text("SELECT id FROM contest_lines WHERE game_id = :g"), {"g": games[1]}
    ).scalar_one(), "away", CAPTURED.replace(minute=4))  # fmt: skip

    rows = _results(db_conn, w.contest_id)

    assert [
        (r["picker"], r["model_version_id"], r["model_rank"], r["pick_id"], r["entry_id"],
         r["side"], r["result"], r["points"])
        for r in rows
    ] == [
        ("you", None, None, None, yours, "away", "lost", Decimal("0.0")),
        ("model", w.version_id, 1, top, None, "home", "won", Decimal("1.0")),
        ("model", w.version_id, 2, second, None, "away", "won", Decimal("1.0")),
    ]  # fmt: skip
    assert low not in {r["pick_id"] for r in rows}


def test_the_model_top_n_is_fixed_at_the_weeks_first_kickoff(db_conn: Connection):
    """D-171: the model's top N is ranked from its picks made before the week's first kickoff.
    A pick written after it (here on a later game, at a moved line, liked more) can't bump a
    game already played out of the top N, so the record never changes with hindsight
    (hard rule 4)."""
    w = _world(db_conn, per_period=1)
    first = _game(db_conn)  # Sat noon ET, home 30-20
    later = _game(db_conn, kickoff=m.utc(2030, 9, 7, 23, 30))  # Sat 7:30 PM ET
    top = _model_pick(db_conn, w, first, -7.5, "home", 0.60)  # won
    _model_pick(db_conn, w, later, -7.5, "home", 0.55)
    moved = m.contest_line(db_conn, w.contest_id, later, -12.5, m.utc(2030, 9, 7, 17))
    prediction_id = db_conn.execute(
        text("SELECT id FROM predictions WHERE game_id = :g"), {"g": later}
    ).scalar_one()
    m.contest_pick(db_conn, prediction_id, w.version_id, later, moved, m.utc(2030, 9, 7, 17, 5),
                   side="away", line=-12.5, model_prob=0.70)  # fmt: skip

    rows = [r for r in _results(db_conn, w.contest_id) if r["picker"] == "model"]
    record = db_conn.execute(
        text(
            "SELECT wins, losses, points FROM contest_record WHERE contest_id = :c"
            " AND picker = 'model' AND breakdown = 'week'"
        ),
        {"c": w.contest_id},
    ).one()

    assert [(r["pick_id"], r["model_rank"], r["result"]) for r in rows] == [(top, 1, "won")]
    assert tuple(record) == (1, 0, Decimal("1.0"))


def test_a_pass_before_the_first_kickoff_leaves_the_top_n(db_conn: Connection):
    """D-171: when a game's newest contest pick before the first kickoff is a pass, the game has
    no model row and the next game by model_prob takes its place in the top N."""
    w = _world(db_conn, per_period=1)
    passed, other = _game(db_conn), _game(db_conn)
    _model_pick(db_conn, w, passed, -7.5, "home", 0.70)
    moved = m.contest_line(db_conn, w.contest_id, passed, -8.5, m.utc(2030, 9, 5, 1))
    prediction_id = db_conn.execute(
        text("SELECT id FROM predictions WHERE game_id = :g"), {"g": passed}
    ).scalar_one()
    m.contest_pick(db_conn, prediction_id, w.version_id, passed, moved, m.utc(2030, 9, 5, 1, 5),
                   side=None, line=-8.5, model_prob=0.65)  # fmt: skip
    kept = _model_pick(db_conn, w, other, -7.5, "home", 0.60)

    rows = [r for r in _results(db_conn, w.contest_id) if r["picker"] == "model"]

    assert [(r["pick_id"], r["model_rank"]) for r in rows] == [(kept, 1)]


def test_a_contest_missing_its_push_rule_scores_a_push_0(db_conn: Connection):
    """A contest whose rules lack `push` scores a push 0, the Splash default (D-045), and
    `counted` is never NULL."""
    w = _world(db_conn)
    db_conn.execute(
        text("UPDATE contests SET rules = rules - 'push' WHERE id = :c"), {"c": w.contest_id}
    )
    _, pushed = _entered(db_conn, w, -10.0, "home")
    _, pending = _entered(db_conn, w, -3.5, "home", status="scheduled")

    rows = {r["entry_id"]: r for r in _results(db_conn, w.contest_id)}

    assert (rows[pushed]["points"], rows[pushed]["counted"]) == (Decimal("0.0"), True)
    assert (rows[pending]["points"], rows[pending]["counted"]) == (None, False)


def test_a_soft_deleted_entry_is_never_graded(db_conn: Connection):
    """AC-3: a soft-deleted entry has no row; the entry made again in its place is graded."""
    w = _world(db_conn)
    game_id, first = _entered(db_conn, w, -7.5, "away")
    _soft_delete(db_conn, "contest_entries", first)
    line_id = db_conn.execute(
        text("SELECT id FROM contest_lines WHERE game_id = :g"), {"g": game_id}
    ).scalar_one()
    again = _entry(db_conn, w, game_id, line_id, "home", CAPTURED.replace(minute=5))

    rows = _results(db_conn, w.contest_id)

    assert [(r["entry_id"], r["result"]) for r in rows] == [(again, "won")]


def test_a_soft_deleted_contest_drops_out_of_every_view(db_conn: Connection):
    """A soft-deleted contest's lines, results, record and standing are gone, and so are the
    model's picks in it from current_picks and pick_outcomes (.claude/rules/database.md)."""
    w = _world(db_conn)
    _entered(db_conn, w, -7.5, "home")
    pick = _model_pick(db_conn, w, _game(db_conn), -7.5, "home", 0.6)
    db_conn.execute(
        text(
            "INSERT INTO contest_standings (contest_id, period, position, field_size)"
            " VALUES (:c, 1, 2, 10)"
        ),
        {"c": w.contest_id},
    )
    count = " + ".join(
        f"(SELECT count(*) FROM {v} WHERE contest_id = :c)"
        for v in (*VIEWS, "current_picks", "pick_outcomes")
    )
    before = db_conn.execute(text(f"SELECT {count}"), {"c": w.contest_id}).scalar_one()
    _soft_delete(db_conn, "contests", w.contest_id)

    assert before > 0
    assert db_conn.execute(text(f"SELECT {count}"), {"c": w.contest_id}).scalar_one() == 0
    for view in ("current_picks", "pick_outcomes"):
        key = "id" if view == "current_picks" else "pick_id"
        found = db_conn.execute(text(f"SELECT 1 FROM {view} WHERE {key} = :p"), {"p": pick}).all()
        assert found == [], view


# ─── AC-4: the seeded season ──────────────────────────────────────────────────────────────────


def test_the_seeded_season_is_12_8_against_11_9(db_conn: Connection):
    """AC-4: through week 5 you're 12-8 and the model's top 4 11-9, week by week as
    contest-data.js; week 6, not yet final, gives both 0 points with your two entries pending."""
    v1 = db_conn.execute(text(SEEDED_V1)).scalar_one()
    rows = db_conn.execute(
        text(
            "SELECT * FROM contest_record"
            f" WHERE contest_id = ({SEEDED_CONTEST}) AND model_version_id IS NOT DISTINCT FROM"
            " CASE WHEN picker = 'model' THEN CAST(:v AS bigint) END"
        ),
        {"v": v1},
    ).all()
    record = {(r.picker, r.breakdown, r.period): r for r in rows}

    def wl(picker: str, breakdown: str, period: int) -> tuple[int, int, int, int, Decimal]:
        r = record[(picker, breakdown, period)]
        return r.wins, r.losses, r.pushes, r.pending, r.points

    you = {1: (3, 1), 2: (2, 2), 3: (3, 1), 4: (1, 3), 5: (3, 1)}
    model = {1: (2, 2), 2: (3, 1), 3: (2, 2), 4: (2, 2), 5: (2, 2)}
    for week in range(1, 6):
        assert wl("you", "week", week) == (*you[week], 0, 0, Decimal(you[week][0])), week
        assert wl("model", "week", week) == (*model[week], 0, 0, Decimal(model[week][0])), week
    assert wl("you", "to_date", 5) == (12, 8, 0, 0, Decimal(12))
    assert wl("model", "to_date", 5) == (11, 9, 0, 0, Decimal(11))
    assert wl("you", "week", 6) == (0, 0, 0, 2, Decimal(0))
    assert wl("model", "week", 6) == (0, 0, 0, 0, Decimal(0))
    assert len(rows) == 2 * 2 * 6  # two pickers, two breakdowns, six weeks

    week6 = db_conn.execute(
        text(
            "SELECT g.source_id, r.result, r.points FROM contest_results r"
            f" JOIN games g ON g.id = r.game_id WHERE r.contest_id = ({SEEDED_CONTEST})"
            " AND r.period = 6 ORDER BY r.created_at"
        )
    ).all()
    assert [tuple(r) for r in week6] == [
        ("2026-w6-tex-ou", "pending", None),
        ("2026-w6-buf-nyj", "pending", None),
    ]


def test_the_seeded_model_top_4_are_v1_contest_picks(db_conn: Connection):
    """AC-3 and AC-4: each week's 4 graded model rows are v1.0's 4 likeliest contest picks of
    the week's 5, ranked by model_prob, every one a CFB game (D-170)."""
    rows = db_conn.execute(
        text(
            "SELECT r.period, r.model_rank, r.model_version_id, g.sport_id, p.model_prob"
            " FROM contest_results r JOIN games g ON g.id = r.game_id"
            " JOIN picks p ON p.id = r.pick_id"
            f" WHERE r.contest_id = ({SEEDED_CONTEST}) AND r.picker = 'model'"
            " ORDER BY r.period, r.model_rank"
        )
    ).all()
    v1 = db_conn.execute(text(SEEDED_V1)).scalar_one()

    assert [(r.period, r.model_rank) for r in rows] == [
        (w, n) for w in range(1, 6) for n in range(1, 5)
    ]
    assert {(r.model_version_id, r.sport_id) for r in rows} == {(v1, "cfb")}
    for week in range(1, 6):
        probs = [r.model_prob for r in rows if r.period == week]
        assert probs == sorted(probs, reverse=True), week
        dropped = db_conn.execute(
            text(
                "SELECT max(p.model_prob) FROM picks p JOIN contest_lines l"
                " ON l.id = p.contest_line_id"
                f" WHERE l.contest_id = ({SEEDED_CONTEST}) AND l.period = :w"
                " AND p.id NOT IN (SELECT pick_id FROM contest_results WHERE pick_id IS NOT NULL)"
            ),
            {"w": week},
        ).scalar_one()
        assert dropped < probs[-1], week


# ─── AC-5: the current standing ───────────────────────────────────────────────────────────────


def test_the_seeded_standing_is_3rd_of_14(db_conn: Connection):
    """AC-5: the Splash work league stands 3rd of 14, 1 point behind the leader."""
    row = db_conn.execute(
        text(f"SELECT * FROM current_contest_standing WHERE contest_id = ({SEEDED_CONTEST})")
    ).one()
    assert (row.period, row.position, row.field_size, row.points_behind_leader) == (
        5, 3, 14, Decimal("1.0"),
    )  # fmt: skip


def test_a_newer_standing_replaces_it(db_conn: Connection):
    """AC-5: a row entered later for the same contest is the current standing."""
    contest_id = db_conn.execute(text(SEEDED_CONTEST)).scalar_one()
    newer = db_conn.execute(
        text(
            "INSERT INTO contest_standings (contest_id, period, position, field_size,"
            " points_behind_leader, entered_at)"
            " VALUES (:c, 6, 2, 14, 0.5, '2026-10-12T13:00:00Z') RETURNING id"
        ),
        {"c": contest_id},
    ).scalar_one()

    rows = db_conn.execute(
        text("SELECT * FROM current_contest_standing WHERE contest_id = :c"), {"c": contest_id}
    ).all()
    assert [(r.standing_id, r.period, r.position, r.points_behind_leader) for r in rows] == [
        (newer, 6, 2, Decimal("0.5"))
    ]


# ─── AC-6: CLV and the one-contest read ───────────────────────────────────────────────────────


def test_clv_is_against_the_market_close_and_null_until_it_exists(db_conn: Connection):
    """AC-6 (D-171): an entry's CLV is its contest line against game_market's close for its side
    (line − close for home, close − line for away, D-132); before the cutoff there's no close."""
    w = _world(db_conn)
    played = m.utc(2025, 9, 6, 16)  # kicked off: game_market has its close
    games = {}
    for side, spread in (("home", -3.5), ("away", 6.5)):
        game_id, _ = _entered(db_conn, w, spread, side, kickoff=played)
        m.line(db_conn, game_id, w.book_id, m.utc(2025, 9, 5, 12), spread - 1.0)
        games[side] = game_id
    coming, _ = _entered(db_conn, w, -3.5, "home", kickoff=m.utc(2099, 9, 5, 16),
                         status="scheduled")  # fmt: skip
    m.line(db_conn, coming, w.book_id, m.utc(2030, 9, 5, 12), -4.5)

    clv = {r["game_id"]: r["clv"] for r in _results(db_conn, w.contest_id)}

    assert clv[games["home"]] == Decimal("1.0")  # −3.5 against a −4.5 close
    assert clv[games["away"]] == Decimal("-1.0")  # +6.5 against a +5.5 close
    assert clv[coming] is None


def test_the_seeded_ou_entry_beat_the_close(db_conn: Connection):
    """AC-6: your OU +7 against the market's +6.5 close is +0.5."""
    clv = db_conn.execute(
        text(
            "SELECT r.clv FROM contest_results r JOIN games g ON g.id = r.game_id"
            f" WHERE r.contest_id = ({SEEDED_CONTEST}) AND r.picker = 'you'"
            " AND g.source_id = '2026-w6-tex-ou'"
        )
    ).scalar_one()
    assert clv == Decimal("0.5")


@pytest.mark.parametrize("view", VIEWS)
def test_one_contest_reads_without_a_full_scan(db_conn: Connection, view: str):
    """AC-6: reading one contest's rows reads contest_entries, contest_lines, picks (and
    contest_standings) by index with a condition. With sequential scans priced out, a view that
    read every contest first would still show a Seq Scan, or an index scan with no condition."""
    contest_id = db_conn.execute(text(SEEDED_CONTEST)).scalar_one()
    plan = m.explain(db_conn, f"SELECT * FROM {view} WHERE contest_id = :c", {"c": contest_id})

    for relation in ("contest_entries", "contest_lines", "picks", "contest_standings"):
        scans = m.scans(plan, relation)
        assert bool(scans) == (relation in READS[view]), (view, relation)
        for node in scans:
            assert node["Node Type"] != "Seq Scan", (view, relation)
            cond = node.get("Index Cond") or node.get("Recheck Cond") or ""
            assert cond, (view, relation, node["Node Type"])
