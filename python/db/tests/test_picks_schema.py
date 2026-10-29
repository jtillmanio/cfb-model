"""The picks table (TASK-040): each pick locked to the line snapshot it was made at, insert-only.

The constraint tests write rows under the throwaway sport in `model_rows` and roll back (db_conn).
The seed tests read the fixture CI loads before pytest (`pnpm db:seed`, D-089). The round trip
runs the migrations in a scratch schema, so the seeded test DB is never dropped."""

from __future__ import annotations

import importlib.util
import json
import uuid
from collections import Counter
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import model_rows as m
import pytest
from alembic import command
from psycopg import errors
from sqlalchemy import Connection, Row, inspect, make_url, text
from sqlalchemy.exc import DBAPIError, IntegrityError

from db.config import repo_root
from db.migrate import alembic_config
from db.session import make_engine, sqlalchemy_url
from engine.core.spec import ModelSpec, fixed

SEEDS = repo_root() / "python" / "db" / "seeds" / "fixture"

# 03 › Models & outputs › picks, as amended at the plan gate: the version and game are carried
# for the composite foreign keys; `contest_line_id` waits for `contest_lines` (M6.1).
PICK_COLUMNS = {
    "id", "prediction_id", "model_version_id", "game_id", "line_snapshot_id", "market", "side",
    "line", "price", "model_prob", "edge_pts", "expected_value", "tier", "stake_units",
    "created_at",
}  # fmt: skip


# ─── Constructed rows ─────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Rows:
    version_id: int
    run_id: int
    game_id: int
    prediction_id: int
    book_id: int
    snapshot_id: int


def _snapshot(conn: Connection, game_id: int, book_id: int, hour: int, spread: float) -> int:
    return conn.execute(
        text(
            "INSERT INTO line_snapshots (game_id, book_id, source, kind, captured_at, spread_home)"
            " VALUES (:g, :b, 'manual', 'snapshot', :c, :s) RETURNING id"
        ),
        {"g": game_id, "b": book_id, "c": m.utc(2030, 9, 1, hour), "s": spread},
    ).scalar_one()


def _prediction(conn: Connection, run_id: int, version_id: int, game_id: int) -> int:
    return conn.execute(
        text(
            "INSERT INTO predictions (model_run_id, model_version_id, game_id, pred_margin,"
            " home_win_prob, margin_sd) VALUES (:r, :v, :g, 4.5, 0.63, 13.8) RETURNING id"
        ),
        {"r": run_id, "v": version_id, "g": game_id},
    ).scalar_one()


def _game(conn: Connection, tag: str) -> int:
    home, away = m.team(conn, f"home-{tag}"), m.team(conn, f"away-{tag}")
    return m.game(conn, home, away, m.utc(2030, 9, 7, 16), week=1, status="scheduled")


def _rows(conn: Connection) -> Rows:
    m.sport(conn)
    version_id = m.version(conn)
    run_id = m.run(conn, version_id, 1, m.utc(2030, 8, 30, 4))
    game_id = _game(conn, "a")
    book_id = conn.execute(
        text(
            "INSERT INTO sportsbooks (source, source_id, name)"
            " VALUES ('pytest', :sid, 'Pytest') RETURNING id"
        ),
        {"sid": uuid.uuid4().hex},
    ).scalar_one()
    return Rows(
        version_id=version_id,
        run_id=run_id,
        game_id=game_id,
        prediction_id=_prediction(conn, run_id, version_id, game_id),
        book_id=book_id,
        snapshot_id=_snapshot(conn, game_id, book_id, 10, -1.0),
    )


def _pick(conn: Connection, rows: Rows, **override: Any) -> int:
    """A valid tier-B home pick at −1 (model home by 4.5), with any column overridden."""
    values: dict[str, Any] = {
        "prediction_id": rows.prediction_id,
        "model_version_id": rows.version_id,
        "game_id": rows.game_id,
        "line_snapshot_id": rows.snapshot_id,
        "market": "spread",
        "side": "home",
        "line": -1.0,
        "price": -110,
        "model_prob": 0.6,
        "edge_pts": 3.5,
        "expected_value": 0.145,
        "tier": "B",
        "stake_units": 1.0,
        **override,
    }
    return conn.execute(
        text(
            f"INSERT INTO picks ({', '.join(values)})"
            f" VALUES ({', '.join(':' + c for c in values)}) RETURNING id"
        ),
        values,
    ).scalar_one()


def _refused(conn: Connection, rows: Rows, error: type, constraint: str | None, **override: Any):
    with pytest.raises(DBAPIError) as err, conn.begin_nested():
        _pick(conn, rows, **override)
    orig = err.value.orig
    assert isinstance(orig, error), override
    if constraint is not None:
        assert isinstance(orig, errors.Error)
        assert orig.diag.constraint_name == constraint, override


# ─── AC-1: the table, one head, round trip ────────────────────────────────────────────────────


def test_picks_has_the_amended_columns_keys_and_indexes(db_conn: Connection):
    insp = inspect(db_conn)
    assert {c["name"] for c in insp.get_columns("picks")} == PICK_COLUMNS
    nullable = {c["name"] for c in insp.get_columns("picks") if c["nullable"]}
    # A pass row (no pick) has no side and no tier; a moneyline pick has no line.
    assert nullable == {"side", "tier", "line"}

    fks = {
        fk["referred_table"]: (
            fk["constrained_columns"], fk["referred_columns"], fk.get("options")
        )
        for fk in insp.get_foreign_keys("picks")
    }
    assert fks == {
        "predictions": (
            ["prediction_id", "model_version_id", "game_id"],
            ["id", "model_version_id", "game_id"],
            {"ondelete": "RESTRICT"},
        ),
        "line_snapshots": (
            ["line_snapshot_id", "game_id"],
            ["id", "game_id"],
            {"ondelete": "RESTRICT"},
        ),
    }
    uniques = [u["column_names"] for u in insp.get_unique_constraints("picks")]
    assert uniques == [["prediction_id", "market", "line_snapshot_id"]]
    indexes = [i["column_names"] for i in insp.get_indexes("picks")]
    # One game's picks (the current pick per game) and one version's picks (its record).
    assert ["game_id", "model_version_id", "created_at"] in indexes
    assert ["model_version_id", "game_id"] in indexes


def test_one_head_and_the_models_match_the_migrated_db(test_db_url: str):
    # `pnpm db:check`: one Alembic head, and `alembic check` finds no drift.
    from db.migrate import check

    check(test_db_url)


@pytest.fixture
def scratch_url(test_db_url: str) -> Iterator[str]:
    """The test DB with search_path set to a new, empty schema, dropped afterwards."""
    schema = f"pytest_{uuid.uuid4().hex[:12]}"
    admin = make_engine(test_db_url)
    with admin.begin() as conn:
        conn.execute(text(f'CREATE SCHEMA "{schema}"'))
    url = make_url(sqlalchemy_url(test_db_url)).update_query_dict(
        {"options": f"-csearch_path={schema}"}
    )
    try:
        yield url.render_as_string(hide_password=False)
    finally:
        with admin.begin() as conn:
            conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))


def _schema(url: str) -> tuple[set[str], set[str | None]]:
    """The scratch schema's tables and its unique constraints on predictions and line_snapshots."""
    with make_engine(url).connect() as conn:
        schema = conn.execute(text("SELECT current_schema()")).scalar_one()
        assert schema.startswith("pytest_")  # never public
        insp = inspect(conn)
        uniques = {
            u["name"]
            for table in ("predictions", "line_snapshots")
            for u in insp.get_unique_constraints(table, schema=schema)
        }
        return set(insp.get_table_names(schema=schema)), uniques


def test_the_migration_runs_up_down_up(scratch_url: str):
    cfg = alembic_config(scratch_url)
    keys = {"uq_predictions_id_model_version_id_game_id", "uq_line_snapshots_id_game_id"}

    command.upgrade(cfg, "head")
    tables, uniques = _schema(scratch_url)
    assert "picks" in tables and keys <= uniques
    command.downgrade(cfg, "0003")
    tables, uniques = _schema(scratch_url)
    assert "picks" not in tables and not keys & uniques
    assert {"predictions", "line_snapshots"} <= tables
    command.upgrade(cfg, "head")
    tables, uniques = _schema(scratch_url)
    assert "picks" in tables and keys <= uniques


# ─── AC-2: what a pick may hold ───────────────────────────────────────────────────────────────


def test_a_pick_at_its_line_snapshot_is_stored(db_conn: Connection):
    rows = _rows(db_conn)
    pick_id = _pick(db_conn, rows)
    stored = db_conn.execute(
        text("SELECT line, tier, created_at FROM picks WHERE id = :p"), {"p": pick_id}
    ).one()
    assert (stored.line, stored.tier) == (Decimal("-1.0"), "B")
    assert stored.created_at is not None


def test_a_pick_without_a_line_snapshot_is_refused(db_conn: Connection):
    _refused(db_conn, _rows(db_conn), errors.NotNullViolation, None, line_snapshot_id=None)


def test_a_contest_line_is_not_a_column_until_m6_1(db_conn: Connection):
    """The plan's settlement: every pick is a market pick at a line snapshot until
    `contest_lines` exists; M6.1 adds `contest_line_id` and the exactly-one CHECK."""
    rows = _rows(db_conn)
    with pytest.raises(DBAPIError) as err, db_conn.begin_nested():
        _pick(db_conn, rows, contest_line_id=None)
    assert isinstance(err.value.orig, errors.UndefinedColumn)


def test_a_market_outside_its_values_is_refused(db_conn: Connection):
    rows = _rows(db_conn)
    for market in ("spreads", "", "parlay"):
        _refused(db_conn, rows, errors.CheckViolation, "ck_picks_market", market=market)


def test_a_side_outside_its_markets_values_is_refused(db_conn: Connection):
    rows = _rows(db_conn)
    for market, side in (("spread", "over"), ("spread", "left"), ("total", "home")):
        _refused(
            db_conn, rows, errors.CheckViolation, "ck_picks_side_for_market",
            market=market, side=side,
        )  # fmt: skip
    _pick(db_conn, rows, market="total", side="under", line=52.5)


def test_a_tier_outside_a_b_c_is_refused(db_conn: Connection):
    rows = _rows(db_conn)
    for tier in ("D", "a", ""):
        _refused(db_conn, rows, errors.CheckViolation, "ck_picks_tier", tier=tier)


def test_a_model_prob_outside_0_to_1_is_refused(db_conn: Connection):
    rows = _rows(db_conn)
    for prob in (-0.01, 1.01):
        _refused(db_conn, rows, errors.CheckViolation, "ck_picks_model_prob_share", model_prob=prob)


def test_a_pass_has_no_side_tier_or_stake(db_conn: Connection):
    """A re-evaluation that drops the pick is a pass row (side and tier NULL, 0 units); a side
    with no stake, or a pass that stakes, is refused."""
    rows = _rows(db_conn)
    _pick(db_conn, rows, side=None, tier=None, stake_units=0, edge_pts=1.2)
    for override in (
        {"side": None, "tier": None, "stake_units": 1.0},
        {"side": None, "tier": "C", "stake_units": 0},
        {"stake_units": 0},
        {"stake_units": -1.0},
    ):
        _refused(db_conn, rows, errors.CheckViolation, "ck_picks_pass_or_stake", **override)


# ─── AC-3: insert-only; references held ───────────────────────────────────────────────────────


def test_picks_cannot_be_updated_deleted_or_truncated(db_conn: Connection):
    rows = _rows(db_conn)
    pick_id = _pick(db_conn, rows)
    for sql in (
        "UPDATE picks SET tier = 'A' WHERE id = :p",
        "DELETE FROM picks WHERE id = :p",
        "TRUNCATE picks",
    ):
        with pytest.raises(DBAPIError) as err, db_conn.begin_nested():
            db_conn.execute(text(sql), {"p": pick_id})
        assert isinstance(err.value.orig, errors.RaiseException), sql
        assert "picks is insert-only" in str(err.value.orig), sql

    assert db_conn.execute(
        text("SELECT tier FROM picks WHERE id = :p"), {"p": pick_id}
    ).scalar_one() == "B"


def test_a_referenced_prediction_or_snapshot_cannot_be_deleted(db_conn: Connection):
    """Both tables' own triggers refuse a DELETE; with a trigger disabled (rolled back), the
    foreign key still RESTRICTs it."""
    rows = _rows(db_conn)
    _pick(db_conn, rows)
    for table, trigger, key in (
        ("predictions", "predictions_insert_only", rows.prediction_id),
        ("line_snapshots", "line_snapshots_append_only", rows.snapshot_id),
    ):
        sql = f"DELETE FROM {table} WHERE id = :k"
        with pytest.raises(DBAPIError) as err, db_conn.begin_nested():
            db_conn.execute(text(sql), {"k": key})
        assert isinstance(err.value.orig, errors.RaiseException), table

        with pytest.raises(IntegrityError) as err, db_conn.begin_nested():
            db_conn.execute(text(f"ALTER TABLE {table} DISABLE TRIGGER {trigger}"))
            db_conn.execute(text(sql), {"k": key})
        assert isinstance(err.value.orig, errors.RestrictViolation), table


def test_a_pick_must_be_on_its_predictions_game_and_version(db_conn: Connection):
    rows = _rows(db_conn)
    other_game = _game(db_conn, "b")
    other_snapshot = _snapshot(db_conn, other_game, rows.book_id, 10, -3.0)
    other_version = m.version(db_conn, "other")
    for override in (
        {"line_snapshot_id": other_snapshot},  # the snapshot is another game's
        {"game_id": other_game, "line_snapshot_id": other_snapshot},  # the prediction isn't
        {"model_version_id": other_version},
    ):
        _refused(db_conn, rows, errors.ForeignKeyViolation, None, **override)


def test_a_second_pick_for_the_prediction_at_a_new_snapshot_is_stored(db_conn: Connection):
    rows = _rows(db_conn)
    first = _pick(db_conn, rows)
    moved = _snapshot(db_conn, rows.game_id, rows.book_id, 14, -2.0)
    second = _pick(db_conn, rows, line_snapshot_id=moved, line=-2.0, edge_pts=2.5, tier="C")
    assert second != first
    # The same snapshot twice is the same pick: re-publishing inserts nothing.
    unique = "uq_picks_prediction_id_market_line_snapshot_id"
    _refused(db_conn, rows, errors.UniqueViolation, unique)
    count = db_conn.execute(
        text("SELECT count(*) FROM picks WHERE prediction_id = :p"), {"p": rows.prediction_id}
    ).scalar_one()
    assert count == 2


# ─── AC-4 and AC-5: the seeded picks ──────────────────────────────────────────────────────────

SEEDED = """
    SELECT p.*, g.source_id AS game, g.week, g.status, g.home_points, g.away_points,
           g.kickoff_at, pr.created_at AS predicted_at,
           s.kind AS snapshot_kind, s.captured_at AS snapshot_at, s.spread_home AS snapshot_spread,
           gm.closing_spread_home, hs.division AS home_division, aws.division AS away_division
    FROM picks p
    JOIN model_versions v ON v.id = p.model_version_id
    JOIN games g ON g.id = p.game_id
    JOIN predictions pr ON pr.id = p.prediction_id
    JOIN line_snapshots s ON s.id = p.line_snapshot_id
    JOIN game_market gm ON gm.game_id = g.id
    LEFT JOIN team_seasons hs ON hs.team_id = g.home_team_id AND hs.season = g.season
    LEFT JOIN team_seasons aws ON aws.team_id = g.away_team_id AND aws.season = g.season
    WHERE v.sport_id = 'cfb' AND v.market = 'spread' AND v.name = 'power'
      AND v.version = 'v1.0' AND v.deleted_at IS NULL AND g.season = 2026
"""

# design/handoff/designs/picks-data.js `current`: the 9 picks This Week names, side and tier.
WEEK6_PICKS = {
    "2026-w6-tex-ou": ("home", "A"),
    "2026-w6-miss-lsu": ("away", "B"),
    "2026-w6-pur-osu": ("home", "B"),
    "2026-w6-isu-cin": ("away", "B"),
    "2026-w6-colo-byu": ("home", "C"),
    "2026-w6-nd-stan": ("away", "C"),
    "2026-w6-asu-bay": ("away", "C"),
    "2026-w6-tuln-mem": ("away", "C"),
    "2026-w6-iowa-wis": ("away", "C"),
}


def _seeded(conn: Connection) -> list[Row[Any]]:
    return list(conn.execute(text(SEEDED)).all())


def _tier_cutoffs(conn: Connection) -> list[tuple[str, float]]:
    spec = conn.execute(
        text(
            "SELECT spec FROM model_versions WHERE sport_id = 'cfb' AND market = 'spread'"
            " AND name = 'power' AND version = 'v1.0' AND deleted_at IS NULL"
        )
    ).scalar_one()
    tiers = ModelSpec.model_validate(spec).picks.tiers
    return [(t, fixed(getattr(tiers, t), f"picks.tiers.{t}")) for t in ("A", "B", "C")]


def test_week_6_holds_the_nine_picks_this_week_names(db_conn: Connection):
    week6 = [r for r in _seeded(db_conn) if r.week == 6]
    assert Counter(r.game for r in week6) == dict.fromkeys(WEEK6_PICKS, 1)
    assert "2026-w6-fur-clem" not in {r.game for r in week6}
    assert {r.game: (r.side, r.tier) for r in week6} == WEEK6_PICKS

    miss = next(r for r in week6 if r.game == "2026-w6-miss-lsu")
    # Picked at LSU −2.5, the snapshot captured Sun 6:00 AM ET, created Sun 6:10 AM ET.
    assert (miss.snapshot_kind, miss.snapshot_spread) == ("snapshot", Decimal("-2.5"))
    assert miss.snapshot_at == datetime(2026, 10, 4, 10, 0, tzinfo=UTC)
    assert miss.created_at == datetime(2026, 10, 4, 10, 10, tzinfo=UTC)
    assert miss.line == Decimal("-2.5")


def test_every_seeded_pick_is_at_its_snapshot_on_its_edges_side_and_tier(db_conn: Connection):
    picks = _seeded(db_conn)
    assert len(picks) == 65
    cutoffs = _tier_cutoffs(db_conn)
    for r in picks:
        assert r.market == "spread" and r.price == -110 and r.stake_units == 1.0, r.game
        assert r.line == r.snapshot_spread, r.game
        assert r.side == ("home" if r.edge_pts > 0 else "away"), r.game
        size = abs(r.edge_pts)
        assert r.tier == next((t for t, at in cutoffs if size >= at), None), r.game
        # Point in time: the line and the prediction came before the pick, the pick before kickoff.
        assert r.snapshot_at is not None and r.snapshot_at <= r.created_at, r.game
        assert r.predicted_at <= r.created_at < r.kickoff_at, r.game


def _graded(r: Row[Any]) -> tuple[str, int, Decimal]:
    """(result, units in tenths, CLV): the line picked at against the final margin, a push at
    0, a win +1.0u and a loss −1.1u (−110); CLV against the closing line (D-132's sign)."""
    margin = r.home_points - r.away_points
    cover = margin + r.line if r.side == "home" else -(margin + r.line)
    result = "P" if cover == 0 else "W" if cover > 0 else "L"
    tenths = {"W": 10, "L": -11, "P": 0}[result]
    moved = r.line - r.closing_spread_home
    return result, tenths, moved if r.side == "home" else -moved


def test_weeks_1_to_5_grade_to_the_season_record(db_conn: Connection):
    picks = [r for r in _seeded(db_conn) if r.week <= 5]
    assert len(picks) == 56
    for r in picks:
        assert r.status == "final", r.game
        assert (r.home_division, r.away_division) == ("fbs", "fbs"), r.game
        assert r.closing_spread_home is not None, r.game

    graded = [(r, *_graded(r)) for r in picks]
    record = Counter(result for _, result, _, _ in graded)
    assert (record["W"], record["L"], record["P"]) == (31, 24, 1)
    assert sum(t for _, _, t, _ in graded) == 46  # +4.6u

    tiers = {
        tier: Counter(result for r, result, _, _ in graded if r.tier == tier) for tier in "ABC"
    }
    assert {t: (c["W"], c["L"], c["P"]) for t, c in tiers.items()} == {
        "A": (7, 3, 0),
        "B": (12, 9, 1),
        "C": (12, 12, 0),
    }

    cumulative, running = [], 0
    for week in range(1, 6):
        running += sum(t for r, _, t, _ in graded if r.week == week)
        cumulative.append(running)
    assert cumulative == [18, 5, 29, 22, 46]  # +1.8, +0.5, +2.9, +2.2, +4.6

    clv = sum(c for _, _, _, c in graded) / len(graded)
    assert round(clv, 1) == Decimal("0.9")


def test_picks_json_is_what_the_generator_writes():
    spec = importlib.util.spec_from_file_location("generate_picks", SEEDS / "generate_picks.py")
    assert spec is not None and spec.loader is not None
    generator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(generator)

    assert generator.build() == json.loads((SEEDS / "picks.json").read_text("utf-8"))
