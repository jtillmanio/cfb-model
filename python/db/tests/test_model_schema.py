"""Model registry and outputs (TASK-034): model_versions, model_runs, team_ratings, predictions.

The constraint tests write rows under a throwaway sport and roll back (db_conn). The seed tests
read the fixture that CI loads before pytest (`pnpm db:seed`, D-089). The round trip runs the
migrations in a scratch schema, so the seeded test DB is never dropped."""

import uuid
from collections.abc import Iterator

import pytest
from alembic import command
from psycopg import errors
from sqlalchemy import Connection, inspect, make_url, text
from sqlalchemy.exc import DBAPIError, IntegrityError

from db.migrate import alembic_config
from db.session import make_engine, sqlalchemy_url
from engine.core.spec import ModelSpec

SPORT = "pytest"  # a throwaway sport, so the fixture's production version never interferes

# design/sample-data.md § 4, entering week 6.
WEEK6_TOP10 = ["osu", "tex", "ore", "ou", "uga", "miss", "nd", "psu", "lsu", "utah"]
# Δ the seeded week-5 ratings give (the design's `traj`, rankings-data.js). § 4's own Δ column
# implies two teams at prior rank 9 and two at 5, so it can't be reproduced (TASK-034 › Plan).
WEEK6_DELTA = {
    "osu": 1, "tex": -1, "ore": 0, "ou": 3, "uga": 0,
    "miss": 2, "nd": -1, "psu": -4, "lsu": 0, "utah": 0,
}  # fmt: skip


# ─── Helpers ──────────────────────────────────────────────────────────────────────────────────


def _sport(conn: Connection) -> None:
    conn.execute(text("INSERT INTO sports (id, name) VALUES (:s, 'pytest')"), {"s": SPORT})


def _version(
    conn: Connection,
    version: str,
    *,
    status: str = "dev",
    market: str = "spread",
    deleted: bool = False,
) -> int:
    return conn.execute(
        text(
            "INSERT INTO model_versions (sport_id, market, name, version, spec,"
            " spec_schema_version, created_by, status, deleted_at)"
            " VALUES (:sport, :market, 'm', :version, '{}', 1, 'user', :status,"
            " CASE WHEN :deleted THEN now() END) RETURNING id"
        ),
        {
            "sport": SPORT,
            "market": market,
            "version": version,
            "status": status,
            "deleted": deleted,
        },
    ).scalar_one()


def _run(conn: Connection, version_id: int) -> int:
    return conn.execute(
        text(
            "INSERT INTO model_runs (model_version_id, run_type, season, week, as_of, status)"
            " VALUES (:v, 'scheduled', 2026, 6, '2026-10-04T04:00Z', 'succeeded') RETURNING id"
        ),
        {"v": version_id},
    ).scalar_one()


def _team(conn: Connection, source_id: str) -> int:
    return conn.execute(
        text(
            "INSERT INTO teams (sport_id, source, source_id, school)"
            " VALUES (:sport, 'pytest', :sid, :sid) RETURNING id"
        ),
        {"sport": SPORT, "sid": source_id},
    ).scalar_one()


def _game(conn: Connection) -> int:
    home, away = _team(conn, "home"), _team(conn, "away")
    return conn.execute(
        text(
            "INSERT INTO games (sport_id, source, source_id, season, week, season_type, game_date,"
            " neutral_site, conference_game, home_team_id, away_team_id, status)"
            " VALUES (:sport, 'pytest', 'g1', 2026, 6, 'regular', '2026-10-10', false, false,"
            " :home, :away, 'scheduled') RETURNING id"
        ),
        {"sport": SPORT, "home": home, "away": away},
    ).scalar_one()


def _rating(conn: Connection, run_id: int, version_id: int, team_id: int, rating: float) -> None:
    conn.execute(
        text(
            "INSERT INTO team_ratings (model_run_id, model_version_id, team_id, season, week,"
            " as_of, rating) VALUES (:r, :v, :t, 2026, 6, '2026-10-04T04:00Z', :rating)"
        ),
        {"r": run_id, "v": version_id, "t": team_id, "rating": rating},
    )


def _prediction(conn: Connection, run_id: int, version_id: int, game_id: int) -> None:
    conn.execute(
        text(
            "INSERT INTO predictions (model_run_id, model_version_id, game_id, pred_margin,"
            " home_win_prob, margin_sd) VALUES (:r, :v, :g, 3.5, 0.6, 13.8)"
        ),
        {"r": run_id, "v": version_id, "g": game_id},
    )


# ─── AC-1: tables, keys, one head, round trip ─────────────────────────────────────────────────


def test_the_four_tables_exist(db_conn: Connection):
    insp = inspect(db_conn)
    columns = {
        t: {c["name"] for c in insp.get_columns(t)}
        for t in ("model_versions", "model_runs", "team_ratings", "predictions")
    }
    assert columns["model_versions"] == {
        "id", "sport_id", "market", "name", "version", "description", "spec",
        "spec_schema_version", "parent_version_id", "created_by", "code_sha", "status",
        "created_at", "deleted_at",
    }  # fmt: skip
    assert columns["model_runs"] == {
        "id", "model_version_id", "run_type", "season", "week", "as_of", "status",
        "requested_at", "started_at", "finished_at", "github_run_id", "fitted_params",
        "metrics", "error", "created_at",
    }  # fmt: skip
    assert columns["team_ratings"] == {
        "model_run_id", "model_version_id", "team_id", "season", "week", "as_of", "rating",
        "off_rating", "def_rating", "st_rating", "prior_weight", "components", "created_at",
    }  # fmt: skip
    assert columns["predictions"] == {
        "id", "model_run_id", "model_version_id", "game_id", "created_at", "pred_margin",
        "pred_total", "home_win_prob", "margin_sd", "drivers", "adjustments_applied",
    }  # fmt: skip

    assert insp.get_pk_constraint("team_ratings")["constrained_columns"] == [
        "model_run_id", "team_id", "season", "week",
    ]  # fmt: skip
    indexes = {i["name"]: i["column_names"] for i in insp.get_indexes("team_ratings")}
    assert ["model_version_id", "season", "week"] in indexes.values()


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


def _tables(url: str) -> set[str]:
    with make_engine(url).connect() as conn:
        schema = conn.execute(text("SELECT current_schema()")).scalar_one()
        assert schema.startswith("pytest_")  # never public
        return set(inspect(conn).get_table_names(schema=schema))


def test_the_migration_runs_up_down_up(scratch_url: str):
    cfg = alembic_config(scratch_url)
    new = {"model_versions", "model_runs", "team_ratings", "predictions"}

    command.upgrade(cfg, "head")
    assert new <= _tables(scratch_url)
    command.downgrade(cfg, "0002")
    remaining = _tables(scratch_url)
    assert not new & remaining
    assert "line_snapshots" in remaining
    command.upgrade(cfg, "head")
    assert new <= _tables(scratch_url)


# ─── AC-2: one production version per sport and market ────────────────────────────────────────


def test_one_production_version_per_sport_and_market(db_conn: Connection):
    _sport(db_conn)
    _version(db_conn, "v1", status="production")

    with pytest.raises(IntegrityError) as err, db_conn.begin_nested():
        _version(db_conn, "v2", status="production")
    assert isinstance(err.value.orig, errors.UniqueViolation)
    assert err.value.orig.diag.constraint_name == "uq_model_versions_production"

    _version(db_conn, "v3", status="production", market="total")
    for status in ("candidate", "candidate", "dev", "dev"):
        _version(db_conn, f"{status}-{uuid.uuid4().hex[:6]}", status=status)


def test_a_soft_deleted_production_version_does_not_block_a_new_one(db_conn: Connection):
    _sport(db_conn)
    _version(db_conn, "v1", status="production", deleted=True)
    _version(db_conn, "v2", status="production")
    count = db_conn.execute(
        text(
            "SELECT count(*) FROM model_versions"
            " WHERE sport_id = :s AND status = 'production' AND deleted_at IS NULL"
        ),
        {"s": SPORT},
    ).scalar_one()
    assert count == 1


def test_a_market_must_be_spread_or_total(db_conn: Connection):
    _sport(db_conn)
    for market in ("moneyline", ""):
        with pytest.raises(IntegrityError) as err, db_conn.begin_nested():
            _version(db_conn, "v1", market=market)
        assert isinstance(err.value.orig, errors.CheckViolation)
        assert err.value.orig.diag.constraint_name == "ck_model_versions_market"


# ─── AC-3: outputs are insert-only; a re-run inserts its own rows ─────────────────────────────


def test_outputs_cannot_be_updated_deleted_or_truncated(db_conn: Connection):
    _sport(db_conn)
    version_id = _version(db_conn, "v1")
    run_id = _run(db_conn, version_id)
    game_id = _game(db_conn)
    team_id = db_conn.execute(
        text("SELECT home_team_id FROM games WHERE id = :g"), {"g": game_id}
    ).scalar_one()
    _rating(db_conn, run_id, version_id, team_id, 12.5)
    _prediction(db_conn, run_id, version_id, game_id)

    for table, column in (("team_ratings", "rating"), ("predictions", "pred_margin")):
        for sql in (
            f"UPDATE {table} SET {column} = 0 WHERE model_run_id = :r",
            f"DELETE FROM {table} WHERE model_run_id = :r",
            # picks references predictions (TASK-040), so a plain TRUNCATE fails on the foreign
            # key before the trigger runs; CASCADE is the form that would otherwise get through.
            f"TRUNCATE {table} CASCADE",
        ):
            with pytest.raises(DBAPIError) as err, db_conn.begin_nested():
                db_conn.execute(text(sql), {"r": run_id})
            assert isinstance(err.value.orig, errors.RaiseException), sql
            assert f"{table} is insert-only" in str(err.value.orig), sql

    assert db_conn.execute(
        text("SELECT rating FROM team_ratings WHERE model_run_id = :r"), {"r": run_id}
    ).scalar_one() == pytest.approx(12.5)
    assert db_conn.execute(
        text("SELECT pred_margin FROM predictions WHERE model_run_id = :r"), {"r": run_id}
    ).scalar_one() == pytest.approx(3.5)


def test_a_second_run_inserts_its_own_ratings_and_predictions(db_conn: Connection):
    _sport(db_conn)
    version_id = _version(db_conn, "v1")
    game_id = _game(db_conn)
    team_id = db_conn.execute(
        text("SELECT home_team_id FROM games WHERE id = :g"), {"g": game_id}
    ).scalar_one()
    first, second = _run(db_conn, version_id), _run(db_conn, version_id)

    for run_id, rating in ((first, 12.5), (second, 13.0)):
        _rating(db_conn, run_id, version_id, team_id, rating)
        _prediction(db_conn, run_id, version_id, game_id)

    ratings = db_conn.execute(
        text(
            "SELECT rating FROM team_ratings WHERE model_version_id = :v AND team_id = :t"
            " AND season = 2026 AND week = 6 ORDER BY rating"
        ),
        {"v": version_id, "t": team_id},
    ).scalars()
    assert list(ratings) == [pytest.approx(12.5), pytest.approx(13.0)]
    predictions = db_conn.execute(
        text("SELECT count(*) FROM predictions WHERE game_id = :g"), {"g": game_id}
    ).scalar_one()
    assert predictions == 2


def test_an_output_names_its_runs_own_version(db_conn: Connection):
    _sport(db_conn)
    version_id, other = _version(db_conn, "v1"), _version(db_conn, "v2")
    run_id = _run(db_conn, version_id)
    game_id = _game(db_conn)
    with pytest.raises(IntegrityError) as err, db_conn.begin_nested():
        _prediction(db_conn, run_id, other, game_id)
    assert isinstance(err.value.orig, errors.ForeignKeyViolation)


def test_a_run_with_outputs_cannot_be_deleted(db_conn: Connection):
    _sport(db_conn)
    version_id = _version(db_conn, "v1")
    run_id = _run(db_conn, version_id)
    _prediction(db_conn, run_id, version_id, _game(db_conn))
    for sql, key in (
        ("DELETE FROM model_runs WHERE id = :k", run_id),
        ("DELETE FROM model_versions WHERE id = :k", version_id),
    ):
        with pytest.raises(IntegrityError) as err, db_conn.begin_nested():
            db_conn.execute(text(sql), {"k": key})
        assert isinstance(err.value.orig, errors.RestrictViolation), sql


# ─── AC-4: the seeded registry ────────────────────────────────────────────────────────────────


def _seeded_versions(conn: Connection) -> dict[str, dict]:
    rows = conn.execute(
        text(
            "SELECT v.version, v.status, v.market, p.version AS parent, v.spec"
            " FROM model_versions v LEFT JOIN model_versions p ON p.id = v.parent_version_id"
            " WHERE v.sport_id = 'cfb' AND v.name = 'power' AND v.deleted_at IS NULL"
        )
    ).mappings()
    return {r["version"]: dict(r) for r in rows}


def test_the_seeded_registry(db_conn: Connection):
    versions = _seeded_versions(db_conn)
    assert {v: (r["status"], r["parent"]) for v, r in versions.items()} == {
        "v1.0": ("production", None),
        "v1.1": ("candidate", "v1.0"),
        "v1.2-dev": ("dev", "v1.1"),
    }
    assert {r["market"] for r in versions.values()} == {"spread"}
    for row in versions.values():
        spec = ModelSpec.model_validate(row["spec"])
        assert spec.base == "efficiency"
    v1 = ModelSpec.model_validate(versions["v1.0"]["spec"])
    assert [i.stat for i in v1.inputs] == ["pass_epa_per_play", "rush_epa_per_play", "success_rate"]
    assert v1.prior is not None and v1.prior.decay.type == "fitted"


def test_v1_0s_backtest_carries_its_metrics_and_weights(db_conn: Connection):
    fitted, metrics = db_conn.execute(
        text(
            "SELECT r.fitted_params, r.metrics FROM model_runs r"
            " JOIN model_versions v ON v.id = r.model_version_id"
            " WHERE v.sport_id = 'cfb' AND v.name = 'power' AND v.version = 'v1.0'"
            " AND r.run_type = 'backtest' AND r.status = 'succeeded'"
        )
    ).one()
    # design/sample-data.md § 7 and 02 › Seed data.
    assert metrics["validation"] == {
        "seasons": [2016, 2023], "picks": 1184, "win_pct": 0.541, "roi": 0.033,
    }  # fmt: skip
    assert metrics["holdout"] == {
        "seasons": [2024, 2025], "picks": 263, "win_pct": 0.532, "roi": 0.016,
    }  # fmt: skip
    assert metrics["accuracy"] == {"mae": 12.9, "closing_mae": 12.6}
    assert [b["picks"] for b in metrics["pick_buckets"]] == [512, 431, 176, 65]
    assert len(metrics["calibration"]) == 6
    # § 8's learned weights.
    assert fitted["home_field"] == 2.3
    assert fitted["inputs"] == {
        "pass_epa_per_play": 31.0, "rush_epa_per_play": 24.0, "success_rate": 31.0,
    }  # fmt: skip
    assert fitted["margin_sd"] == 13.8
    assert fitted["choices"] == {
        "hyperparameters.ridge_alpha": 12.0,
        "hyperparameters.recency_half_life_weeks": 4.0,
        "picks.market_shrinkage_k": 0.6,
    }
    v1 = ModelSpec.model_validate(_seeded_versions(db_conn)["v1.0"]["spec"])
    assert v1.resolve(fitted["choices"]).is_resolved


# ─── AC-5: the seeded ratings and predictions ─────────────────────────────────────────────────

RANKS = """
    SELECT t.source_id, r.rating,
           rank() OVER (ORDER BY r.rating DESC) AS rk
    FROM team_ratings r
    JOIN model_runs mr ON mr.id = r.model_run_id
    JOIN model_versions v ON v.id = r.model_version_id
    JOIN teams t ON t.id = r.team_id
    WHERE v.sport_id = 'cfb' AND v.name = 'power' AND v.version = 'v1.0'
      AND mr.run_type = 'scheduled' AND r.season = 2026 AND r.week = :week
"""


def _ranks(conn: Connection, week: int) -> dict[str, int]:
    return {r.source_id: r.rk for r in conn.execute(text(RANKS), {"week": week})}


def test_every_fbs_team_is_rated_entering_weeks_5_and_6(db_conn: Connection):
    fbs = set(
        db_conn.execute(
            text(
                "SELECT t.source_id FROM teams t JOIN team_seasons s ON s.team_id = t.id"
                " WHERE t.source = 'fixture' AND s.season = 2026 AND s.division = 'fbs'"
            )
        ).scalars()
    )
    assert len(fbs) == 52  # 28 from the slate and rankings, 24 more for the picks (TASK-040)
    for week in (5, 6):
        assert set(_ranks(db_conn, week)) == fbs


def test_week_6_reproduces_the_rankings_order_and_delta(db_conn: Connection):
    week6, week5 = _ranks(db_conn, 6), _ranks(db_conn, 5)
    assert sorted(week6, key=week6.__getitem__)[:10] == WEEK6_TOP10
    assert len(set(week6.values())) == len(week6)  # no ties
    assert {t: week5[t] - week6[t] for t in WEEK6_TOP10} == WEEK6_DELTA


def test_ohio_states_trajectory_and_units(db_conn: Connection):
    rows = db_conn.execute(
        text(
            "SELECT r.week, r.rating, r.off_rating, r.def_rating, r.st_rating, r.as_of,"
            " mr.as_of AS run_as_of, mr.finished_at, r.created_at"
            " FROM team_ratings r JOIN model_runs mr ON mr.id = r.model_run_id"
            " JOIN teams t ON t.id = r.team_id"
            " WHERE t.source = 'fixture' AND t.source_id = 'osu' AND r.season = 2026"
            " ORDER BY r.week"
        )
    ).all()
    assert [r.week for r in rows] == [1, 2, 3, 4, 5, 6]
    assert [r.rating for r in rows] == pytest.approx([24.0, 24.9, 25.6, 26.1, 26.8, 27.4])
    week6 = rows[-1]
    assert (week6.off_rating, week6.def_rating, week6.st_rating) == (
        pytest.approx(14.1), pytest.approx(13.3), None,
    )  # fmt: skip
    for r in rows:
        assert r.as_of == r.run_as_of
        assert r.created_at == r.finished_at > r.as_of


def test_each_week_6_game_has_one_v1_prediction(db_conn: Connection):
    rows = db_conn.execute(
        text(
            "SELECT g.source_id, count(p.id) AS n, min(g.kickoff_at) AS kickoff,"
            " max(p.created_at) AS created_at"
            " FROM games g LEFT JOIN predictions p ON p.game_id = g.id"
            " AND p.model_version_id = (SELECT id FROM model_versions WHERE sport_id = 'cfb'"
            "   AND name = 'power' AND version = 'v1.0' AND deleted_at IS NULL)"
            " WHERE g.source = 'fixture' AND g.season = 2026 AND g.week = 6"
            " GROUP BY g.source_id"
        )
    ).all()
    assert len(rows) == 14  # the 11 slate games and the 3 picks.json adds (TASK-040)
    assert {r.source_id: r.n for r in rows} == {r.source_id: 1 for r in rows}
    for r in rows:
        assert r.created_at < r.kickoff  # made before the game


def test_texas_oklahomas_prediction(db_conn: Connection):
    pred = db_conn.execute(
        text(
            "SELECT p.pred_margin, p.home_win_prob, p.margin_sd, p.pred_total, p.drivers"
            " FROM predictions p JOIN games g ON g.id = p.game_id"
            " WHERE g.source = 'fixture' AND g.source_id = '2026-w6-tex-ou'"
        )
    ).one()
    # Oklahoma is the nominal home team at the Cotton Bowl; Texas by 1.3 is −1.3 home − away.
    assert pred.pred_margin == pytest.approx(-1.3)
    assert pred.home_win_prob == pytest.approx(0.46)
    assert pred.margin_sd == pytest.approx(13.8)
    assert pred.pred_total == pytest.approx(58.0)
    assert len(pred.drivers) == 7
    assert {"label", "points"} == set(pred.drivers[0])
    assert sum(d["points"] for d in pred.drivers) == pytest.approx(pred.pred_margin)
    assert pred.drivers[0] == {"label": "Away pass offense vs home pass defense", "points": -3.8}
