"""A live game's period and clock on `games` (TASK-074, D-178).

The `scores` job fills them from CFBD's `/scoreboard` while a game is in progress; every other
write clears them, and a CHECK keeps them NULL unless `status = 'in_progress'`. `clock` is CFBD's
string as given (e.g. "09:12"): the API documents no format.

The downgrade drops the CHECK and both columns; the rest of each row is untouched.

Revision ID: 0009
Revises: 0008
Create Date: 2026-11-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: str | Sequence[str] | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("games", sa.Column("period", sa.SmallInteger(), nullable=True))
    op.add_column("games", sa.Column("clock", sa.Text(), nullable=True))
    op.create_check_constraint(
        op.f("ck_games_clock_only_in_progress"),
        "games",
        "status = 'in_progress' OR (period IS NULL AND clock IS NULL)",
    )


def downgrade() -> None:
    op.drop_constraint(op.f("ck_games_clock_only_in_progress"), "games", type_="check")
    op.drop_column("games", "clock")
    op.drop_column("games", "period")
