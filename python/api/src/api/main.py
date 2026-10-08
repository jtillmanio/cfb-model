"""FastAPI service: one endpoint per screen, all under /api/py (D-013).

Vercel loads `app` from here (`src.api.main:app`, a path relative to python/api/); locally
`pnpm dev` runs it with uvicorn on :8000. Sign-in and the JWT check arrive with the Phase 0
sign-in task.
"""

from __future__ import annotations

import os
from functools import cache

from fastapi import APIRouter, FastAPI
from pydantic import BaseModel
from sqlalchemy import Engine, text

from db.config import app_database_url, load_env
from db.session import make_engine

load_env()

app = FastAPI(
    title="CFB model API", docs_url=None, redoc_url=None, openapi_url="/api/py/openapi.json"
)
router = APIRouter(prefix="/api/py")


@cache
def engine() -> Engine:
    return make_engine(app_database_url())


class TeamOut(BaseModel):
    id: int
    school: str
    abbreviation: str | None
    conference: str | None
    color: str | None


class TeamsOut(BaseModel):
    season: int | None
    teams: list[TeamOut]


class HealthOut(BaseModel):
    commit: str
    db_reachable: bool
    migration_head: str | None


# One query (budget: ≤ 6, docs/02 › Non-functional requirements). FBS only (F-44). Conference
# is per season, so the list is the latest season any team has a row for.
TEAMS_SQL = text(
    """
    SELECT t.id, t.school, t.abbreviation, t.color, ts.conference, ts.season
    FROM team_seasons ts
    JOIN teams t ON t.id = ts.team_id
    WHERE t.sport_id = 'cfb'
      AND ts.division = 'fbs'
      AND ts.season = (SELECT max(season) FROM team_seasons)
    ORDER BY t.id
    """
)


@router.get("/teams")
def teams() -> TeamsOut:
    with engine().connect() as conn:
        rows = conn.execute(TEAMS_SQL).all()
    return TeamsOut(
        season=rows[0].season if rows else None,
        teams=[
            TeamOut(
                id=r.id,
                school=r.school,
                abbreviation=r.abbreviation,
                conference=r.conference,
                color=r.color,
            )
            for r in rows
        ],
    )


@router.get("/health")
def health() -> HealthOut:
    """The only route that stays outside the auth gate. No data."""
    commit = (
        os.environ.get("VERCEL_GIT_COMMIT_SHA") or os.environ.get("GIT_COMMIT_SHA") or "unknown"
    )
    try:
        with engine().connect() as conn:
            head = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
    except Exception:
        return HealthOut(commit=commit, db_reachable=False, migration_head=None)
    return HealthOut(commit=commit, db_reachable=True, migration_head=head)


app.include_router(router)
