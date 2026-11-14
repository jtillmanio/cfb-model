"""Index a contest's live entries by contest (TASK-068, D-171).

`contest_results` reads one contest's entries; `uq_contest_entries_live` leads with `user_id`, so
a read by contest alone would scan the table. The partial index matches the view's
`deleted_at IS NULL` filter.

The downgrade also drops TASK-068's contest views (they read the 0007 tables and current_picks,
which 0007's downgrade drops); `db:migrate` re-applies them after the next upgrade.

Revision ID: 0008
Revises: 0007
Create Date: 2026-11-14
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: str | Sequence[str] | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CONTEST_VIEWS = (  # dependants first
    "current_contest_standing",
    "contest_record",
    "contest_results",
    "current_contest_lines",
)


def upgrade() -> None:
    op.create_index(
        "ix_contest_entries_contest_id_live",
        "contest_entries",
        ["contest_id"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )


def downgrade() -> None:
    for view in CONTEST_VIEWS:
        op.execute(f"DROP VIEW IF EXISTS {view}")
    op.drop_index("ix_contest_entries_contest_id_live", table_name="contest_entries")
