"""Model registry and outputs: model_versions, model_runs, team_ratings, predictions.

team_ratings and predictions are insert-only (hard rule 2), enforced by triggers on UPDATE, DELETE
and TRUNCATE like line_snapshots (D-115): a re-run inserts new rows under its own model_run.
Their composite foreign key to model_runs keeps an output's version equal to its run's, and
RESTRICT keeps any run or version with outputs from being deleted. Statuses of runs and versions
are their lifecycles, so those two tables are updated in place (D-135).

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003"
down_revision: str | Sequence[str] | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TSTZ = postgresql.TIMESTAMP(timezone=True)
JSONB = postgresql.JSONB(astext_type=sa.Text())
FLOAT = sa.Float(precision=53)
OUTPUT_TABLES = ("team_ratings", "predictions")


def _created_at() -> sa.Column:
    return sa.Column("created_at", TSTZ, server_default=sa.text("now()"), nullable=False)


def _run_fk(table: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        ["model_run_id", "model_version_id"],
        ["model_runs.id", "model_runs.model_version_id"],
        name=op.f(f"fk_{table}_model_run_id_model_runs"),
        ondelete="RESTRICT",
    )


def upgrade() -> None:
    op.create_table(
        "model_versions",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("sport_id", sa.Text(), nullable=False),
        sa.Column("market", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("version", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("spec", JSONB, nullable=False),
        sa.Column("spec_schema_version", sa.Integer(), nullable=False),
        sa.Column("parent_version_id", sa.BigInteger(), nullable=True),
        sa.Column("created_by", sa.Text(), nullable=False),
        sa.Column("code_sha", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False),
        _created_at(),
        sa.Column("deleted_at", TSTZ, nullable=True),
        sa.CheckConstraint("market IN ('spread', 'total')", name=op.f("ck_model_versions_market")),
        sa.CheckConstraint(
            "created_by IN ('system', 'user')", name=op.f("ck_model_versions_created_by")
        ),
        sa.CheckConstraint(
            "status IN ('dev', 'candidate', 'production', 'retired')",
            name=op.f("ck_model_versions_status"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(spec) = 'object'", name=op.f("ck_model_versions_spec_is_object")
        ),
        sa.ForeignKeyConstraint(
            ["sport_id"], ["sports.id"], name=op.f("fk_model_versions_sport_id_sports")
        ),
        sa.ForeignKeyConstraint(
            ["parent_version_id"],
            ["model_versions.id"],
            name=op.f("fk_model_versions_parent_version_id_model_versions"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_model_versions")),
    )
    # Soft-deleted lab models free their name and version for re-adding.
    op.create_index(
        "uq_model_versions_name_version",
        "model_versions",
        ["sport_id", "market", "name", "version"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "uq_model_versions_production",
        "model_versions",
        ["sport_id", "market"],
        unique=True,
        postgresql_where=sa.text("status = 'production' AND deleted_at IS NULL"),
    )

    op.create_table(
        "model_runs",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("model_version_id", sa.BigInteger(), nullable=False),
        sa.Column("run_type", sa.Text(), nullable=False),
        sa.Column("season", sa.Integer(), nullable=True),
        sa.Column("week", sa.Integer(), nullable=True),
        sa.Column("as_of", TSTZ, nullable=True),
        sa.Column("status", sa.Text(), server_default=sa.text("'queued'"), nullable=False),
        sa.Column("requested_at", TSTZ, server_default=sa.text("now()"), nullable=False),
        sa.Column("started_at", TSTZ, nullable=True),
        sa.Column("finished_at", TSTZ, nullable=True),
        sa.Column("github_run_id", sa.BigInteger(), nullable=True),
        sa.Column("fitted_params", JSONB, nullable=True),
        sa.Column("metrics", JSONB, nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        _created_at(),
        sa.CheckConstraint(
            "run_type IN ('backtest', 'scheduled', 'adhoc')", name=op.f("ck_model_runs_run_type")
        ),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'succeeded', 'failed')",
            name=op.f("ck_model_runs_status"),
        ),
        sa.CheckConstraint(
            "run_type = 'backtest'"
            " OR (season IS NOT NULL AND week IS NOT NULL AND as_of IS NOT NULL)",
            name=op.f("ck_model_runs_live_run_has_week"),
        ),
        sa.ForeignKeyConstraint(
            ["model_version_id"],
            ["model_versions.id"],
            name=op.f("fk_model_runs_model_version_id_model_versions"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_model_runs")),
        # The target of the outputs' composite foreign key.
        sa.UniqueConstraint(
            "id", "model_version_id", name=op.f("uq_model_runs_id_model_version_id")
        ),
    )
    op.create_index(op.f("ix_model_runs_model_version_id"), "model_runs", ["model_version_id"])

    op.create_table(
        "team_ratings",
        sa.Column("model_run_id", sa.BigInteger(), nullable=False),
        sa.Column("model_version_id", sa.BigInteger(), nullable=False),
        sa.Column("team_id", sa.BigInteger(), nullable=False),
        sa.Column("season", sa.Integer(), nullable=False),
        sa.Column("week", sa.Integer(), nullable=False),
        sa.Column("as_of", TSTZ, nullable=False),
        sa.Column("rating", FLOAT, nullable=False),
        sa.Column("off_rating", FLOAT, nullable=True),
        sa.Column("def_rating", FLOAT, nullable=True),
        sa.Column("st_rating", FLOAT, nullable=True),
        sa.Column("prior_weight", FLOAT, nullable=True),
        sa.Column("components", JSONB, nullable=True),
        _created_at(),
        sa.CheckConstraint(
            "prior_weight BETWEEN 0 AND 1", name=op.f("ck_team_ratings_prior_weight_share")
        ),
        _run_fk("team_ratings"),
        sa.ForeignKeyConstraint(
            ["team_id"], ["teams.id"], name=op.f("fk_team_ratings_team_id_teams")
        ),
        sa.PrimaryKeyConstraint(
            "model_run_id", "team_id", "season", "week", name=op.f("pk_team_ratings")
        ),
    )
    op.create_index(
        op.f("ix_team_ratings_model_version_id_season_week"),
        "team_ratings",
        ["model_version_id", "season", "week"],
    )

    op.create_table(
        "predictions",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("model_run_id", sa.BigInteger(), nullable=False),
        sa.Column("model_version_id", sa.BigInteger(), nullable=False),
        sa.Column("game_id", sa.BigInteger(), nullable=False),
        _created_at(),
        sa.Column("pred_margin", FLOAT, nullable=False),
        sa.Column("pred_total", FLOAT, nullable=True),
        sa.Column("home_win_prob", FLOAT, nullable=False),
        sa.Column("margin_sd", FLOAT, nullable=True),
        sa.Column("drivers", JSONB, nullable=True),
        sa.Column("adjustments_applied", JSONB, nullable=True),
        sa.CheckConstraint(
            "home_win_prob BETWEEN 0 AND 1", name=op.f("ck_predictions_home_win_prob_share")
        ),
        sa.CheckConstraint("margin_sd > 0", name=op.f("ck_predictions_margin_sd_positive")),
        _run_fk("predictions"),
        sa.ForeignKeyConstraint(
            ["game_id"],
            ["games.id"],
            name=op.f("fk_predictions_game_id_games"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_predictions")),
        # One prediction per game per run, so re-publishing a run inserts nothing.
        sa.UniqueConstraint(
            "model_run_id", "game_id", name=op.f("uq_predictions_model_run_id_game_id")
        ),
    )
    op.create_index(
        "ix_predictions_game_id_model_version_id_created_at",
        "predictions",
        ["game_id", "model_version_id", sa.text("created_at DESC")],
    )

    op.execute(
        """
        CREATE FUNCTION forbid_model_output_changes() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION '% is insert-only: % is not allowed', TG_TABLE_NAME, TG_OP;
        END;
        $$
        """
    )
    for table in OUTPUT_TABLES:
        op.execute(
            f"""
            CREATE TRIGGER {table}_insert_only
            BEFORE UPDATE OR DELETE ON {table}
            FOR EACH ROW EXECUTE FUNCTION forbid_model_output_changes()
            """
        )
        # TRUNCATE skips row triggers, so it gets its own statement-level one.
        op.execute(
            f"""
            CREATE TRIGGER {table}_no_truncate
            BEFORE TRUNCATE ON {table}
            FOR EACH STATEMENT EXECUTE FUNCTION forbid_model_output_changes()
            """
        )


def downgrade() -> None:
    for table in reversed(OUTPUT_TABLES):
        op.execute(f"DROP TRIGGER {table}_no_truncate ON {table}")
        op.execute(f"DROP TRIGGER {table}_insert_only ON {table}")
    op.execute("DROP FUNCTION forbid_model_output_changes()")
    op.drop_index("ix_predictions_game_id_model_version_id_created_at", table_name="predictions")
    op.drop_table("predictions")
    op.drop_index(op.f("ix_team_ratings_model_version_id_season_week"), table_name="team_ratings")
    op.drop_table("team_ratings")
    op.drop_index(op.f("ix_model_runs_model_version_id"), table_name="model_runs")
    op.drop_table("model_runs")
    op.drop_index("uq_model_versions_production", table_name="model_versions")
    op.drop_index("uq_model_versions_name_version", table_name="model_versions")
    op.drop_table("model_versions")
