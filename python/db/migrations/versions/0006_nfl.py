"""The NFL as a sport, and nflverse as a line source (TASK-069, D-039).

Splash slates mix CFB and NFL games, so the NFL schedule, scores and lines from nflverse go into
`games` and `line_snapshots` under `sport_id = 'nfl'`. 0001 seeded `cfb`; this seeds `nfl`, and
widens `line_snapshots.source`'s CHECK (D-115) to take `nflverse`.

The downgrade refuses while NFL rows exist: line snapshots can't be deleted (D-115), and the
sports row can't go while teams and games point at it.

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | Sequence[str] | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SOURCES = "source IN ('cfbd', 'oddsapi', 'manual', 'fixture', 'nflverse')"
SOURCES_BEFORE = "source IN ('cfbd', 'oddsapi', 'manual', 'fixture')"


def upgrade() -> None:
    op.execute("INSERT INTO sports (id, name) VALUES ('nfl', 'NFL')")
    op.drop_constraint(op.f("ck_line_snapshots_source"), "line_snapshots", type_="check")
    op.create_check_constraint(op.f("ck_line_snapshots_source"), "line_snapshots", SOURCES)


def downgrade() -> None:
    found = (
        op.get_bind()
        .execute(
            sa.text(
                "SELECT (SELECT count(*) FROM teams WHERE sport_id = 'nfl')"
                " + (SELECT count(*) FROM games WHERE sport_id = 'nfl')"
                " + (SELECT count(*) FROM line_snapshots WHERE source = 'nflverse')"
            )
        )
        .scalar_one()
    )
    if found:
        raise RuntimeError(
            f"{found} NFL teams, games or nflverse line snapshots exist; line snapshots can't be"
            " deleted, so the NFL can't be removed"
        )
    op.drop_constraint(op.f("ck_line_snapshots_source"), "line_snapshots", type_="check")
    op.create_check_constraint(op.f("ck_line_snapshots_source"), "line_snapshots", SOURCES_BEFORE)
    op.execute("DELETE FROM sports WHERE id = 'nfl'")
