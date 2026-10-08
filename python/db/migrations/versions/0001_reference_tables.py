"""Reference tables: sports, teams, team_seasons, venues, games.

Revision ID: 0001
Revises:
Create Date: 2026-10-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TSTZ = postgresql.TIMESTAMP(timezone=True)


def upgrade() -> None:
    op.create_table(
        "sports",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sports")),
    )
    op.execute("INSERT INTO sports (id, name) VALUES ('cfb', 'College football')")

    op.create_table(
        "teams",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("sport_id", sa.Text(), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("source_id", sa.Text(), nullable=False),
        sa.Column("school", sa.Text(), nullable=False),
        sa.Column("mascot", sa.Text(), nullable=True),
        sa.Column("abbreviation", sa.Text(), nullable=True),
        sa.Column("color", sa.String(length=7), nullable=True),
        sa.Column("alt_color", sa.String(length=7), nullable=True),
        sa.Column("logo_url", sa.Text(), nullable=True),
        sa.Column("created_at", TSTZ, server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["sport_id"], ["sports.id"], name=op.f("fk_teams_sport_id_sports")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_teams")),
        sa.UniqueConstraint(
            "sport_id", "source", "source_id", name=op.f("uq_teams_sport_id_source_source_id")
        ),
    )

    op.create_table(
        "team_seasons",
        sa.Column("team_id", sa.BigInteger(), nullable=False),
        sa.Column("season", sa.Integer(), nullable=False),
        sa.Column("conference", sa.Text(), nullable=True),
        sa.Column("division", sa.Text(), nullable=True),
        sa.Column("talent", sa.Numeric(7, 2), nullable=True),
        sa.Column("returning_ppa_pct", sa.Numeric(5, 4), nullable=True),
        sa.Column("created_at", TSTZ, server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["team_id"], ["teams.id"], name=op.f("fk_team_seasons_team_id_teams")
        ),
        sa.PrimaryKeyConstraint("team_id", "season", name=op.f("pk_team_seasons")),
    )

    op.create_table(
        "venues",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("source_id", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("city", sa.Text(), nullable=True),
        sa.Column("state", sa.Text(), nullable=True),
        sa.Column("lat", sa.Numeric(9, 6), nullable=True),
        sa.Column("lon", sa.Numeric(9, 6), nullable=True),
        sa.Column("elevation_m", sa.Numeric(7, 1), nullable=True),
        sa.Column("dome", sa.Boolean(), nullable=True),
        sa.Column("grass", sa.Boolean(), nullable=True),
        sa.Column("timezone", sa.Text(), nullable=True),
        sa.Column("capacity", sa.Integer(), nullable=True),
        sa.Column("created_at", TSTZ, server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_venues")),
        sa.UniqueConstraint("source", "source_id", name=op.f("uq_venues_source_source_id")),
    )

    op.create_table(
        "games",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("sport_id", sa.Text(), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("source_id", sa.Text(), nullable=False),
        sa.Column("season", sa.Integer(), nullable=False),
        sa.Column("week", sa.Integer(), nullable=False),
        sa.Column("season_type", sa.Text(), nullable=False),
        sa.Column("game_date", sa.Date(), nullable=False),
        sa.Column("kickoff_at", TSTZ, nullable=True),
        sa.Column("neutral_site", sa.Boolean(), nullable=False),
        sa.Column("conference_game", sa.Boolean(), nullable=False),
        sa.Column("venue_id", sa.BigInteger(), nullable=True),
        sa.Column("home_team_id", sa.BigInteger(), nullable=False),
        sa.Column("away_team_id", sa.BigInteger(), nullable=False),
        sa.Column("home_points", sa.Integer(), nullable=True),
        sa.Column("away_points", sa.Integer(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("updated_at", TSTZ, server_default=sa.text("now()"), nullable=False),
        sa.Column("created_at", TSTZ, server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "status IN ('scheduled', 'in_progress', 'final', 'canceled', 'postponed')",
            name=op.f("ck_games_status"),
        ),
        sa.CheckConstraint(
            "status <> 'final' OR (home_points IS NOT NULL AND away_points IS NOT NULL)",
            name=op.f("ck_games_final_has_points"),
        ),
        sa.ForeignKeyConstraint(["sport_id"], ["sports.id"], name=op.f("fk_games_sport_id_sports")),
        sa.ForeignKeyConstraint(["venue_id"], ["venues.id"], name=op.f("fk_games_venue_id_venues")),
        sa.ForeignKeyConstraint(
            ["home_team_id"], ["teams.id"], name=op.f("fk_games_home_team_id_teams")
        ),
        sa.ForeignKeyConstraint(
            ["away_team_id"], ["teams.id"], name=op.f("fk_games_away_team_id_teams")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_games")),
        sa.UniqueConstraint(
            "sport_id", "source", "source_id", name=op.f("uq_games_sport_id_source_source_id")
        ),
    )
    op.create_index(op.f("ix_games_sport_id_season_week"), "games", ["sport_id", "season", "week"])


def downgrade() -> None:
    op.drop_index(op.f("ix_games_sport_id_season_week"), table_name="games")
    op.drop_table("games")
    op.drop_table("venues")
    op.drop_table("team_seasons")
    op.drop_table("teams")
    op.drop_table("sports")
