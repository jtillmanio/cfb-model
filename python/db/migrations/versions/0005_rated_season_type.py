"""A season type on the rated week, so postseason week 1 is a week of its own (TASK-047).

CFBD files every bowl and CFP game under postseason week 1, which `model_runs` and `team_ratings`
keyed by `(season, week)` alone would read as the season's regular week 1 (D-136). Both gain
`season_type` (`regular|postseason`, as on `games`): a live run must name it, a backtest run,
which spans seasons, may leave it NULL. Every existing week is a regular one, so live runs and
every rating are backfilled `regular`; `team_ratings` takes it as a default while the column is
added (a catalog-only change: its insert-only triggers don't fire), and the default is dropped so
no writer can leave it out. The ratings index gains it, so a view filtered by a week still reads
only that week.

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | Sequence[str] | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SEASON_TYPES = "season_type IN ('regular', 'postseason')"
LIVE_RUN_HAS_WEEK = (
    "run_type = 'backtest' OR (season IS NOT NULL AND week IS NOT NULL AND as_of IS NOT NULL)"
)
# The views that read the new columns, dependents first; `db migrate` re-applies them.
VIEWS = ("team_schedule_strength", "team_rankings", "latest_team_ratings")


def upgrade() -> None:
    op.add_column("model_runs", sa.Column("season_type", sa.Text(), nullable=True))
    op.execute("UPDATE model_runs SET season_type = 'regular' WHERE week IS NOT NULL")
    op.create_check_constraint(op.f("ck_model_runs_season_type"), "model_runs", SEASON_TYPES)
    op.drop_constraint(op.f("ck_model_runs_live_run_has_week"), "model_runs", type_="check")
    op.create_check_constraint(
        op.f("ck_model_runs_live_run_has_week"),
        "model_runs",
        "run_type = 'backtest'"
        " OR (season IS NOT NULL AND season_type IS NOT NULL AND week IS NOT NULL"
        " AND as_of IS NOT NULL)",
    )

    op.add_column(
        "team_ratings",
        sa.Column("season_type", sa.Text(), nullable=False, server_default="regular"),
    )
    op.alter_column("team_ratings", "season_type", server_default=None)
    op.create_check_constraint(op.f("ck_team_ratings_season_type"), "team_ratings", SEASON_TYPES)
    op.drop_index(op.f("ix_team_ratings_model_version_id_season_week"), table_name="team_ratings")
    op.create_index(
        op.f("ix_team_ratings_model_version_id_season_season_type_week"),
        "team_ratings",
        ["model_version_id", "season", "season_type", "week"],
    )


def downgrade() -> None:
    # Without the column a postseason week reads as regular week 1, and ratings can't be
    # deleted (hard rule 2): refuse rather than merge them.
    postseason = (
        op.get_bind()
        .execute(
            sa.text(
                "SELECT count(*) FROM model_runs WHERE season_type = 'postseason'"
                " OR id IN (SELECT model_run_id FROM team_ratings"
                " WHERE season_type = 'postseason')"
            )
        )
        .scalar_one()
    )
    if postseason:
        raise RuntimeError(
            f"{postseason} postseason runs would read as regular week 1 without season_type"
        )
    # The views read the columns; the checkout migrating down re-applies its own.
    for view in VIEWS:
        op.execute(f"DROP VIEW IF EXISTS {view}")
    op.drop_index(
        op.f("ix_team_ratings_model_version_id_season_season_type_week"),
        table_name="team_ratings",
    )
    op.create_index(
        op.f("ix_team_ratings_model_version_id_season_week"),
        "team_ratings",
        ["model_version_id", "season", "week"],
    )
    op.drop_constraint(op.f("ck_team_ratings_season_type"), "team_ratings", type_="check")
    op.drop_column("team_ratings", "season_type")

    op.drop_constraint(op.f("ck_model_runs_live_run_has_week"), "model_runs", type_="check")
    op.create_check_constraint(
        op.f("ck_model_runs_live_run_has_week"), "model_runs", LIVE_RUN_HAS_WEEK
    )
    op.drop_constraint(op.f("ck_model_runs_season_type"), "model_runs", type_="check")
    op.drop_column("model_runs", "season_type")
