"""picks: the model's recommendations, each locked to the line snapshot it was made at.

Insert-only like the other model outputs (hard rule 2, D-135): the same trigger function refuses
UPDATE, DELETE and TRUNCATE. A re-evaluation at a new line is a new row; one that drops the pick
is a pass row (no side, no tier, 0 units), so the latest row per game, version and market is the
current pick. Two composite foreign keys keep a pick on its prediction's version and game and on a
snapshot of that same game; both RESTRICT. `contest_line_id` waits for `contest_lines` (M6.1).

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-29
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004"
down_revision: str | Sequence[str] | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TSTZ = postgresql.TIMESTAMP(timezone=True)
FLOAT = sa.Float(precision=53)


def upgrade() -> None:
    # The targets of the picks' composite foreign keys.
    op.create_unique_constraint(
        op.f("uq_predictions_id_model_version_id_game_id"),
        "predictions",
        ["id", "model_version_id", "game_id"],
    )
    op.create_unique_constraint(
        op.f("uq_line_snapshots_id_game_id"), "line_snapshots", ["id", "game_id"]
    )

    op.create_table(
        "picks",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("prediction_id", sa.BigInteger(), nullable=False),
        sa.Column("model_version_id", sa.BigInteger(), nullable=False),
        sa.Column("game_id", sa.BigInteger(), nullable=False),
        sa.Column("line_snapshot_id", sa.BigInteger(), nullable=False),
        sa.Column("market", sa.Text(), nullable=False),
        sa.Column("side", sa.Text(), nullable=True),
        sa.Column("line", sa.Numeric(4, 1), nullable=True),
        sa.Column("price", sa.Integer(), nullable=False),
        sa.Column("model_prob", FLOAT, nullable=False),
        sa.Column("edge_pts", FLOAT, nullable=False),
        sa.Column("expected_value", FLOAT, nullable=False),
        sa.Column("tier", sa.Text(), nullable=True),
        sa.Column("stake_units", FLOAT, nullable=False),
        sa.Column("created_at", TSTZ, server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "market IN ('spread', 'total', 'moneyline')", name=op.f("ck_picks_market")
        ),
        sa.CheckConstraint(
            "side IS NULL"
            " OR (market IN ('spread', 'moneyline') AND side IN ('home', 'away'))"
            " OR (market = 'total' AND side IN ('over', 'under'))",
            name=op.f("ck_picks_side_for_market"),
        ),
        sa.CheckConstraint("tier IN ('A', 'B', 'C')", name=op.f("ck_picks_tier")),
        sa.CheckConstraint("model_prob BETWEEN 0 AND 1", name=op.f("ck_picks_model_prob_share")),
        sa.CheckConstraint(
            "(side IS NULL AND tier IS NULL AND stake_units = 0)"
            " OR (side IS NOT NULL AND stake_units > 0)",
            name=op.f("ck_picks_pass_or_stake"),
        ),
        sa.ForeignKeyConstraint(
            ["prediction_id", "model_version_id", "game_id"],
            ["predictions.id", "predictions.model_version_id", "predictions.game_id"],
            name=op.f("fk_picks_prediction_id_predictions"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["line_snapshot_id", "game_id"],
            ["line_snapshots.id", "line_snapshots.game_id"],
            name=op.f("fk_picks_line_snapshot_id_line_snapshots"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_picks")),
        # One pick per prediction, market and snapshot, so re-publishing inserts nothing.
        sa.UniqueConstraint(
            "prediction_id",
            "market",
            "line_snapshot_id",
            name=op.f("uq_picks_prediction_id_market_line_snapshot_id"),
        ),
    )
    # One game's picks, newest first (current_picks, M4.6); one version's picks (model_record).
    op.create_index(
        "ix_picks_game_id_model_version_id_created_at",
        "picks",
        ["game_id", "model_version_id", sa.text("created_at DESC")],
    )
    op.create_index(
        op.f("ix_picks_model_version_id_game_id"), "picks", ["model_version_id", "game_id"]
    )

    op.execute(
        """
        CREATE TRIGGER picks_insert_only
        BEFORE UPDATE OR DELETE ON picks
        FOR EACH ROW EXECUTE FUNCTION forbid_model_output_changes()
        """
    )
    # TRUNCATE skips row triggers, so it gets its own statement-level one.
    op.execute(
        """
        CREATE TRIGGER picks_no_truncate
        BEFORE TRUNCATE ON picks
        FOR EACH STATEMENT EXECUTE FUNCTION forbid_model_output_changes()
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER picks_no_truncate ON picks")
    op.execute("DROP TRIGGER picks_insert_only ON picks")
    op.drop_index(op.f("ix_picks_model_version_id_game_id"), table_name="picks")
    op.drop_index("ix_picks_game_id_model_version_id_created_at", table_name="picks")
    op.drop_table("picks")
    op.drop_constraint(op.f("uq_line_snapshots_id_game_id"), "line_snapshots", type_="unique")
    op.drop_constraint(
        op.f("uq_predictions_id_model_version_id_game_id"), "predictions", type_="unique"
    )
