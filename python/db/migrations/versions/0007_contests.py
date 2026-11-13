"""Contests: users, contests, contest_lines, contest_entries and contest_standings, and contest
picks (TASK-067, D-170; applies D-033, D-034, D-038, D-140).

- `users`: one row per GitHub account (`github_id`, the JWT's `sub`, D-105). The fixture seeds the
  test DB's; in production the contest API upserts it on its first write (TASK-070).
- `contests`: yours, soft-deleted, `rules` a `ContestRules` object (D-113).
- `contest_lines`: append-only snapshots of a contest's slate (D-038). `period` is the contest's
  week, not `games.week` (NFL weeks differ).
- `contest_entries`: your picks, each at the exact contest line you got. The entry carries
  `game_id`, so a composite foreign key holds it to its contest's line for its game, and a
  partial unique index allows one live entry per user, contest and game; a soft-deleted one can
  be made again (D-033). Never hard-deleted; an UPDATE may only set `deleted_at`, once.
- `contest_standings`: your league standing as you enter it; append-only.
- `picks` gains `contest_line_id`: a pick is at a line snapshot (market) or a contest line, exactly
  one, and a contest pick has no price (no-vig, D-140).

The downgrade refuses while any user, contest or contest pick exists, then drops the three picks
views (they read `contest_line_id`); `db:migrate` re-applies them after the next upgrade.

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0007"
down_revision: str | Sequence[str] | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TSTZ = postgresql.TIMESTAMP(timezone=True)
APPEND_ONLY = ("contest_lines", "contest_standings")
PICK_VIEWS = ("model_record", "pick_outcomes", "current_picks")  # dependants first


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("github_id", sa.BigInteger(), nullable=False),
        sa.Column("email", sa.Text(), nullable=True),
        sa.Column("name", sa.Text(), nullable=True),
        sa.Column("created_at", TSTZ, server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("github_id", name=op.f("uq_users_github_id")),
    )

    op.create_table(
        "contests",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("platform", sa.Text(), nullable=False),
        sa.Column("season", sa.Integer(), nullable=False),
        sa.Column("rules", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", TSTZ, server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", TSTZ, nullable=True),
        sa.CheckConstraint(
            "jsonb_typeof(rules) = 'object'", name=op.f("ck_contests_rules_is_object")
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_contests_user_id_users"), ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_contests")),
        sa.UniqueConstraint("id", "user_id", name=op.f("uq_contests_id_user_id")),
    )
    op.create_index(
        "uq_contests_user_id_name",
        "contests",
        ["user_id", "name"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    op.create_table(
        "contest_lines",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("contest_id", sa.BigInteger(), nullable=False),
        sa.Column("period", sa.Integer(), nullable=False),
        sa.Column("game_id", sa.BigInteger(), nullable=False),
        sa.Column("spread_home", sa.Numeric(4, 1), nullable=False),
        sa.Column("captured_at", TSTZ, nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("created_at", TSTZ, server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "source IN ('paste', 'manual', 'fixture')", name=op.f("ck_contest_lines_source")
        ),
        sa.CheckConstraint("period > 0", name=op.f("ck_contest_lines_period_positive")),
        sa.ForeignKeyConstraint(
            ["contest_id"],
            ["contests.id"],
            name=op.f("fk_contest_lines_contest_id_contests"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["game_id"],
            ["games.id"],
            name=op.f("fk_contest_lines_game_id_games"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_contest_lines")),
        # One snapshot per contest, game and capture; also the newest-line-per-game index.
        sa.UniqueConstraint(
            "contest_id",
            "game_id",
            "captured_at",
            name=op.f("uq_contest_lines_contest_id_game_id_captured_at"),
        ),
        # The targets of the picks' and the entries' composite foreign keys.
        sa.UniqueConstraint("id", "game_id", name=op.f("uq_contest_lines_id_game_id")),
        sa.UniqueConstraint(
            "id", "contest_id", "game_id", name=op.f("uq_contest_lines_id_contest_id_game_id")
        ),
    )
    op.create_index(
        op.f("ix_contest_lines_contest_id_period"), "contest_lines", ["contest_id", "period"]
    )

    op.create_table(
        "contest_entries",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("contest_id", sa.BigInteger(), nullable=False),
        sa.Column("game_id", sa.BigInteger(), nullable=False),
        sa.Column("contest_line_id", sa.BigInteger(), nullable=False),
        sa.Column("side", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Integer(), nullable=True),
        sa.Column("created_at", TSTZ, server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", TSTZ, nullable=True),
        sa.CheckConstraint("side IN ('home', 'away')", name=op.f("ck_contest_entries_side")),
        sa.CheckConstraint("confidence > 0", name=op.f("ck_contest_entries_confidence_positive")),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_contest_entries_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["contest_id", "user_id"],
            ["contests.id", "contests.user_id"],
            name=op.f("fk_contest_entries_contest_id_contests"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["contest_line_id", "contest_id", "game_id"],
            ["contest_lines.id", "contest_lines.contest_id", "contest_lines.game_id"],
            name=op.f("fk_contest_entries_contest_line_id_contest_lines"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_contest_entries")),
    )
    # One live entry per user, contest and game; a soft-deleted one can be made again (D-033).
    op.create_index(
        "uq_contest_entries_live",
        "contest_entries",
        ["user_id", "contest_id", "game_id"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    op.create_table(
        "contest_standings",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("contest_id", sa.BigInteger(), nullable=False),
        sa.Column("period", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("field_size", sa.Integer(), nullable=False),
        sa.Column("points_behind_leader", sa.Numeric(5, 1), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("entered_at", TSTZ, server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("period > 0", name=op.f("ck_contest_standings_period_positive")),
        sa.CheckConstraint(
            "position > 0 AND position <= field_size",
            name=op.f("ck_contest_standings_position_in_field"),
        ),
        sa.CheckConstraint(
            "points_behind_leader >= 0",
            name=op.f("ck_contest_standings_points_behind_leader_not_negative"),
        ),
        sa.ForeignKeyConstraint(
            ["contest_id"],
            ["contests.id"],
            name=op.f("fk_contest_standings_contest_id_contests"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_contest_standings")),
    )
    # The current standing is the newest row per contest (TASK-068's view).
    op.create_index(
        "ix_contest_standings_contest_id_entered_at",
        "contest_standings",
        ["contest_id", sa.text("entered_at DESC")],
    )

    op.execute(
        """
        CREATE FUNCTION forbid_contest_snapshot_changes() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION '% is append-only: % is not allowed', TG_TABLE_NAME, TG_OP;
        END;
        $$
        """
    )
    for table in APPEND_ONLY:
        op.execute(
            f"""
            CREATE TRIGGER {table}_append_only
            BEFORE UPDATE OR DELETE ON {table}
            FOR EACH ROW EXECUTE FUNCTION forbid_contest_snapshot_changes()
            """
        )
        # TRUNCATE skips row triggers, so it gets its own statement-level one.
        op.execute(
            f"""
            CREATE TRIGGER {table}_no_truncate
            BEFORE TRUNCATE ON {table}
            FOR EACH STATEMENT EXECUTE FUNCTION forbid_contest_snapshot_changes()
            """
        )

    # An entry is soft-deleted, never hard-deleted, and the line you got never changes: the only
    # UPDATE allowed sets deleted_at from NULL and changes nothing else.
    op.execute(
        """
        CREATE FUNCTION guard_contest_entry_changes() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP <> 'UPDATE' THEN
                RAISE EXCEPTION 'contest_entries can''t be deleted: set deleted_at (% refused)',
                    TG_OP;
            END IF;
            IF OLD.deleted_at IS NOT NULL OR NEW.deleted_at IS NULL
                OR to_jsonb(NEW) - 'deleted_at' <> to_jsonb(OLD) - 'deleted_at' THEN
                RAISE EXCEPTION
                    'contest_entries: only setting deleted_at on a live entry is allowed';
            END IF;
            RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER contest_entries_soft_delete_only
        BEFORE UPDATE OR DELETE ON contest_entries
        FOR EACH ROW EXECUTE FUNCTION guard_contest_entry_changes()
        """
    )
    op.execute(
        """
        CREATE TRIGGER contest_entries_no_truncate
        BEFORE TRUNCATE ON contest_entries
        FOR EACH STATEMENT EXECUTE FUNCTION guard_contest_entry_changes()
        """
    )

    # Contest picks (D-140): at a contest line instead of a line snapshot, with no price.
    op.add_column("picks", sa.Column("contest_line_id", sa.BigInteger(), nullable=True))
    op.alter_column("picks", "line_snapshot_id", existing_type=sa.BigInteger(), nullable=True)
    op.alter_column("picks", "price", existing_type=sa.Integer(), nullable=True)
    op.create_foreign_key(
        op.f("fk_picks_contest_line_id_contest_lines"),
        "picks",
        "contest_lines",
        ["contest_line_id", "game_id"],
        ["id", "game_id"],
        ondelete="RESTRICT",
    )
    op.create_check_constraint(
        op.f("ck_picks_one_line"),
        "picks",
        "(line_snapshot_id IS NULL) <> (contest_line_id IS NULL)",
    )
    op.create_check_constraint(
        op.f("ck_picks_price_for_market"),
        "picks",
        "price IS NOT NULL OR contest_line_id IS NOT NULL",
    )
    op.create_unique_constraint(
        op.f("uq_picks_prediction_id_market_contest_line_id"),
        "picks",
        ["prediction_id", "market", "contest_line_id"],
    )
    # A contest's picks through its lines (TASK-068's contest reads); market picks have none.
    op.create_index(
        "ix_picks_contest_line_id",
        "picks",
        ["contest_line_id"],
        postgresql_where=sa.text("contest_line_id IS NOT NULL"),
    )


def downgrade() -> None:
    found = (
        op.get_bind()
        .execute(
            sa.text(
                "SELECT (SELECT count(*) FROM users) + (SELECT count(*) FROM contests)"
                " + (SELECT count(*) FROM picks WHERE contest_line_id IS NOT NULL)"
            )
        )
        .scalar_one()
    )
    if found:
        raise RuntimeError(
            f"{found} users, contests or contest picks exist; contest lines and picks can't be"
            " deleted, so the contest tables can't be removed"
        )
    for view in PICK_VIEWS:
        op.execute(f"DROP VIEW IF EXISTS {view}")

    op.drop_index("ix_picks_contest_line_id", table_name="picks")
    op.drop_constraint(
        op.f("uq_picks_prediction_id_market_contest_line_id"), "picks", type_="unique"
    )
    op.drop_constraint(op.f("ck_picks_price_for_market"), "picks", type_="check")
    op.drop_constraint(op.f("ck_picks_one_line"), "picks", type_="check")
    op.drop_constraint(op.f("fk_picks_contest_line_id_contest_lines"), "picks", type_="foreignkey")
    op.alter_column("picks", "price", existing_type=sa.Integer(), nullable=False)
    op.alter_column("picks", "line_snapshot_id", existing_type=sa.BigInteger(), nullable=False)
    op.drop_column("picks", "contest_line_id")

    op.drop_table("contest_standings")
    op.drop_table("contest_entries")
    op.drop_table("contest_lines")
    op.drop_table("contests")
    op.drop_table("users")
    op.execute("DROP FUNCTION guard_contest_entry_changes()")
    op.execute("DROP FUNCTION forbid_contest_snapshot_changes()")
