"""SQLAlchemy models. With the migrations, these are the schema's source of truth (docs/03)."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    ForeignKey,
    Identity,
    Index,
    MetaData,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

NAMING = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

GAME_STATUSES = ("scheduled", "in_progress", "final", "canceled", "postponed")
LINE_SOURCES = ("cfbd", "oddsapi", "manual", "fixture")
# A backfilled open or close has no capture time (D-031); a live pull is a timed snapshot.
LINE_KINDS = ("opening", "closing", "snapshot")


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING)


def _created_at() -> Mapped[datetime]:
    return mapped_column(TIMESTAMP(timezone=True), server_default=func.now())


class Sport(Base):
    __tablename__ = "sports"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text)


class Team(Base):
    __tablename__ = "teams"
    __table_args__ = (UniqueConstraint("sport_id", "source", "source_id"),)

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    sport_id: Mapped[str] = mapped_column(ForeignKey("sports.id"))
    source: Mapped[str] = mapped_column(Text)
    source_id: Mapped[str] = mapped_column(Text)
    school: Mapped[str] = mapped_column(Text)
    mascot: Mapped[str | None] = mapped_column(Text)
    abbreviation: Mapped[str | None] = mapped_column(Text)
    color: Mapped[str | None] = mapped_column(String(7))
    alt_color: Mapped[str | None] = mapped_column(String(7))
    logo_url: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = _created_at()


class TeamSeason(Base):
    """Conference is a per-season fact (realignment), not a team attribute."""

    __tablename__ = "team_seasons"

    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), primary_key=True)
    season: Mapped[int] = mapped_column(primary_key=True)
    conference: Mapped[str | None] = mapped_column(Text)
    division: Mapped[str | None] = mapped_column(Text)
    talent: Mapped[Decimal | None] = mapped_column(Numeric(7, 2))
    returning_ppa_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    created_at: Mapped[datetime] = _created_at()


class Venue(Base):
    __tablename__ = "venues"
    __table_args__ = (UniqueConstraint("source", "source_id"),)

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    source: Mapped[str] = mapped_column(Text)
    source_id: Mapped[str] = mapped_column(Text)
    name: Mapped[str] = mapped_column(Text)
    city: Mapped[str | None] = mapped_column(Text)
    state: Mapped[str | None] = mapped_column(Text)
    lat: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    lon: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    elevation_m: Mapped[Decimal | None] = mapped_column(Numeric(7, 1))
    dome: Mapped[bool | None]
    grass: Mapped[bool | None]
    timezone: Mapped[str | None] = mapped_column(Text)
    capacity: Mapped[int | None]
    created_at: Mapped[datetime] = _created_at()


class Game(Base):
    __tablename__ = "games"
    __table_args__ = (
        UniqueConstraint("sport_id", "source", "source_id"),
        Index(None, "sport_id", "season", "week"),
        CheckConstraint(f"status IN {GAME_STATUSES!r}", name="status"),
        CheckConstraint(
            "status <> 'final' OR (home_points IS NOT NULL AND away_points IS NOT NULL)",
            name="final_has_points",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    sport_id: Mapped[str] = mapped_column(ForeignKey("sports.id"))
    source: Mapped[str] = mapped_column(Text)
    source_id: Mapped[str] = mapped_column(Text)
    season: Mapped[int]
    week: Mapped[int]
    season_type: Mapped[str] = mapped_column(Text)
    game_date: Mapped[date] = mapped_column(Date)
    # NULL while the kickoff time is TBA; never defaulted to midnight.
    kickoff_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    neutral_site: Mapped[bool]
    conference_game: Mapped[bool]
    venue_id: Mapped[int | None] = mapped_column(ForeignKey("venues.id"))
    home_team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"))
    away_team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"))
    home_points: Mapped[int | None]
    away_points: Mapped[int | None]
    status: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )
    created_at: Mapped[datetime] = _created_at()


class Season(Base):
    """One row per sport and year. `weeks` is CFBD /calendar as
    [{"week", "season_type", "start", "end"}, ...] with UTC ISO times."""

    __tablename__ = "seasons"
    __table_args__ = (
        CheckConstraint("jsonb_typeof(weeks) = 'array'", name="weeks_is_array"),
        CheckConstraint("end_date >= start_date", name="end_after_start"),
    )

    sport_id: Mapped[str] = mapped_column(ForeignKey("sports.id"), primary_key=True)
    year: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(Text)
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    current_week: Mapped[int | None]
    weeks: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )
    created_at: Mapped[datetime] = _created_at()


class TeamAlias(Base):
    """Every spelling a source uses for a team (D-036). `source` is whose spelling it is."""

    __tablename__ = "team_aliases"
    __table_args__ = (UniqueConstraint("source", "alias"), Index(None, "team_id"))

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"))
    source: Mapped[str] = mapped_column(Text)
    alias: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = _created_at()


class Sportsbook(Base):
    """A provider as one line source names it, e.g. CFBD's `consensus`."""

    __tablename__ = "sportsbooks"
    __table_args__ = (UniqueConstraint("source", "source_id"),)

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    source: Mapped[str] = mapped_column(Text)
    source_id: Mapped[str] = mapped_column(Text)
    name: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = _created_at()


class LineSnapshot(Base):
    """Append-only price history (D-037): triggers refuse UPDATE, DELETE and TRUNCATE. The
    key makes re-publishing one raw file a no-op; NULLS NOT DISTINCT keeps an untimed open to
    one row."""

    __tablename__ = "line_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "game_id",
            "book_id",
            "source",
            "kind",
            "captured_at",
            postgresql_nulls_not_distinct=True,
        ),
        Index(None, "game_id", "captured_at"),
        CheckConstraint(f"source IN {LINE_SOURCES!r}", name="source"),
        CheckConstraint(f"kind IN {LINE_KINDS!r}", name="kind"),
        CheckConstraint(
            "kind <> 'snapshot' OR captured_at IS NOT NULL", name="snapshot_has_captured_at"
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id"))
    book_id: Mapped[int] = mapped_column(ForeignKey("sportsbooks.id"))
    source: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(Text)
    # NULL for a backfilled open or close: CFBD doesn't say when it was quoted (D-031).
    captured_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    spread_home: Mapped[Decimal | None] = mapped_column(Numeric(4, 1))
    total: Mapped[Decimal | None] = mapped_column(Numeric(4, 1))
    spread_home_price: Mapped[int | None]
    spread_away_price: Mapped[int | None]
    over_price: Mapped[int | None]
    under_price: Mapped[int | None]
    ml_home: Mapped[int | None]
    ml_away: Mapped[int | None]
    created_at: Mapped[datetime] = _created_at()
