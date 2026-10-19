"""Market and reference tables: seasons, team_aliases, sportsbooks, line_snapshots.

line_snapshots is append-only (D-037), enforced by triggers on UPDATE, DELETE and TRUNCATE:
a live snapshot can't be fetched again (02 › What's reproducible), so a convention isn't enough.

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: str | Sequence[str] | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TSTZ = postgresql.TIMESTAMP(timezone=True)


def _created_at() -> sa.Column:
    return sa.Column("created_at", TSTZ, server_default=sa.text("now()"), nullable=False)


def upgrade() -> None:
    op.create_table(
        "seasons",
        sa.Column("sport_id", sa.Text(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("current_week", sa.Integer(), nullable=True),
        sa.Column("weeks", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("updated_at", TSTZ, server_default=sa.text("now()"), nullable=False),
        _created_at(),
        sa.CheckConstraint("jsonb_typeof(weeks) = 'array'", name=op.f("ck_seasons_weeks_is_array")),
        sa.CheckConstraint("end_date >= start_date", name=op.f("ck_seasons_end_after_start")),
        sa.ForeignKeyConstraint(
            ["sport_id"], ["sports.id"], name=op.f("fk_seasons_sport_id_sports")
        ),
        sa.PrimaryKeyConstraint("sport_id", "year", name=op.f("pk_seasons")),
    )

    op.create_table(
        "team_aliases",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("team_id", sa.BigInteger(), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("alias", sa.Text(), nullable=False),
        _created_at(),
        sa.ForeignKeyConstraint(
            ["team_id"], ["teams.id"], name=op.f("fk_team_aliases_team_id_teams")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_team_aliases")),
        sa.UniqueConstraint("source", "alias", name=op.f("uq_team_aliases_source_alias")),
    )
    op.create_index(op.f("ix_team_aliases_team_id"), "team_aliases", ["team_id"])

    op.create_table(
        "sportsbooks",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("source_id", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        _created_at(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sportsbooks")),
        sa.UniqueConstraint("source", "source_id", name=op.f("uq_sportsbooks_source_source_id")),
    )

    op.create_table(
        "line_snapshots",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("game_id", sa.BigInteger(), nullable=False),
        sa.Column("book_id", sa.BigInteger(), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("captured_at", TSTZ, nullable=True),
        sa.Column("spread_home", sa.Numeric(4, 1), nullable=True),
        sa.Column("total", sa.Numeric(4, 1), nullable=True),
        sa.Column("spread_home_price", sa.Integer(), nullable=True),
        sa.Column("spread_away_price", sa.Integer(), nullable=True),
        sa.Column("over_price", sa.Integer(), nullable=True),
        sa.Column("under_price", sa.Integer(), nullable=True),
        sa.Column("ml_home", sa.Integer(), nullable=True),
        sa.Column("ml_away", sa.Integer(), nullable=True),
        _created_at(),
        sa.CheckConstraint(
            "source IN ('cfbd', 'oddsapi', 'manual', 'fixture')",
            name=op.f("ck_line_snapshots_source"),
        ),
        sa.CheckConstraint(
            "kind IN ('opening', 'closing', 'snapshot')", name=op.f("ck_line_snapshots_kind")
        ),
        sa.CheckConstraint(
            "kind <> 'snapshot' OR captured_at IS NOT NULL",
            name=op.f("ck_line_snapshots_snapshot_has_captured_at"),
        ),
        sa.ForeignKeyConstraint(
            ["game_id"], ["games.id"], name=op.f("fk_line_snapshots_game_id_games")
        ),
        sa.ForeignKeyConstraint(
            ["book_id"], ["sportsbooks.id"], name=op.f("fk_line_snapshots_book_id_sportsbooks")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_line_snapshots")),
        sa.UniqueConstraint(
            "game_id",
            "book_id",
            "source",
            "kind",
            "captured_at",
            name=op.f("uq_line_snapshots_game_id_book_id_source_kind_captured_at"),
            postgresql_nulls_not_distinct=True,
        ),
    )
    op.create_index(
        op.f("ix_line_snapshots_game_id_captured_at"), "line_snapshots", ["game_id", "captured_at"]
    )

    op.execute(
        """
        CREATE FUNCTION forbid_line_snapshot_changes() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'line_snapshots is append-only: % is not allowed', TG_OP;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER line_snapshots_append_only
        BEFORE UPDATE OR DELETE ON line_snapshots
        FOR EACH ROW EXECUTE FUNCTION forbid_line_snapshot_changes()
        """
    )
    # TRUNCATE skips row triggers, so it gets its own statement-level one.
    op.execute(
        """
        CREATE TRIGGER line_snapshots_no_truncate
        BEFORE TRUNCATE ON line_snapshots
        FOR EACH STATEMENT EXECUTE FUNCTION forbid_line_snapshot_changes()
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER line_snapshots_no_truncate ON line_snapshots")
    op.execute("DROP TRIGGER line_snapshots_append_only ON line_snapshots")
    op.execute("DROP FUNCTION forbid_line_snapshot_changes()")
    op.drop_index(op.f("ix_line_snapshots_game_id_captured_at"), table_name="line_snapshots")
    op.drop_table("line_snapshots")
    op.drop_table("sportsbooks")
    op.drop_index(op.f("ix_team_aliases_team_id"), table_name="team_aliases")
    op.drop_table("team_aliases")
    op.drop_table("seasons")
