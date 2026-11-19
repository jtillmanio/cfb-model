"""FastAPI service: one endpoint per screen, all under /api/py (D-013).

Vercel loads `app` from here (`src.api.main:app`, a path relative to python/api/); locally
`pnpm dev` runs it with uvicorn on :8000. Every route but health requires the JWT Next's server
code signs (auth.py, TASK-004): a route belongs on `router`, which carries the check, and only
health sits on `public`.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from functools import cache
from typing import Annotated, Any

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query, Response
from pydantic import BaseModel
from sqlalchemy import Connection, Engine, text

from db.config import app_database_url, load_env
from db.session import make_engine

from . import clock, contest, contest_import, shell, slate
from .auth import require_api_token
from .contest import (
    ContestEntryOut,
    ContestPageOut,
    ContestRefusalBody,
    ContestStandingOut,
    EntryIn,
    StandingIn,
)
from .contest_import import (
    AliasConflictBody,
    AliasesIn,
    AliasesOut,
    ImportConfirmOut,
    ImportIn,
    ImportPreviewOut,
    ImportRefusalBody,
)
from .shell import ShellOut
from .slate import SeasonType, SlateOut
from .wave import run_wave

load_env()

# FastAPI's own schema route can't take a dependency, so `router` serves it instead (below).
app = FastAPI(title="CFB model API", docs_url=None, redoc_url=None, openapi_url=None)
router = APIRouter(prefix="/api/py", dependencies=[Depends(require_api_token)])
public = APIRouter(prefix="/api/py")


@cache
def engine() -> Engine:
    return make_engine(app_database_url())


def connection() -> Iterator[Connection]:
    """One connection for a write route's whole request: committed when the route returns, rolled
    back when it raises (FastAPI throws the route's exception into this generator). Tests swap it
    for their rolled-back `db_conn`."""
    with engine().begin() as conn:
        yield conn


# scope="function" closes the connection, so commits, before the response is sent: the default
# ("request") would commit after it, and a failed commit would follow a 200 (schema review).
Conn = Annotated[Connection, Depends(connection, scope="function")]
Subject = Annotated[str, Depends(require_api_token)]  # the token's `sub`, checked once per request


class TeamOut(BaseModel):
    id: int
    school: str
    abbreviation: str | None
    conference: str | None
    color: str | None


class TeamsOut(BaseModel):
    season: int | None
    teams: list[TeamOut]
    shell: ShellOut


class HealthOut(BaseModel):
    commit: str
    db_reachable: bool
    migration_head: str | None


# The teams and the shell (shell.py): two queries in one wave (budget: ≤ 6, docs/02 ›
# Non-functional requirements). FBS only (F-44). Conference
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
    now = clock.now()
    found = run_wave(engine(), {"teams": (TEAMS_SQL, {}), "shell": shell.query(now, shell.SPORT)})
    rows = found["teams"]
    return TeamsOut(
        shell=shell.shell_from(found["shell"][0], now),
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


@router.get("/slate")
def get_slate(
    season: int | None = None,
    season_type: SeasonType | None = None,
    week: Annotated[int | None, Query(ge=1)] = None,
) -> SlateOut:
    """This Week (slate.py): the week asked for, all three of season, season type and week, or
    with none of them the coming week. Six queries in one wave (budget: ≤ 6)."""
    asked = (season, season_type, week)
    if any(v is None for v in asked) and any(v is not None for v in asked):
        raise HTTPException(422, "give season, season_type and week together, or none of them")
    chosen = None if season is None or season_type is None or week is None else (
        season, season_type, week
    )  # fmt: skip
    now = clock.now()
    found = run_wave(engine(), slate.queries(now, shell.SPORT, chosen))
    return slate.slate_from(found, now, chosen)


IMPORT_REFUSALS: dict[int | str, dict[str, Any]] = {
    404: {"description": "No such contest of yours"},
    422: {"model": ImportRefusalBody, "description": "Unparseable, no match, or unresolved rows"},
}


@router.post("/contests/{contest_id}/import/preview", responses=IMPORT_REFUSALS)
def preview_contest_import(
    contest_id: int, body: ImportIn, subject: Subject, conn: Conn
) -> ImportPreviewOut:
    """The pasted page's rows matched to games, with the re-paste diff. Writes nothing."""
    return contest_import.preview(conn, contest_id, subject, body, clock.now())


@router.post(
    "/contests/{contest_id}/import/confirm",
    responses={**IMPORT_REFUSALS, 409: {"description": "A snapshot already at this instant"}},
)
def confirm_contest_import(
    contest_id: int, body: ImportIn, subject: Subject, conn: Conn
) -> ImportConfirmOut:
    """Saves every row's line as a new contest_lines snapshot at the API's clock, or none."""
    return contest_import.confirm(conn, contest_id, subject, body, clock.now())


@router.post(
    "/contests/{contest_id}/aliases",
    responses={
        404: {"description": "No such contest of yours"},
        409: {"model": AliasConflictBody, "description": "A name already means another team"},
        422: {"model": AliasConflictBody, "description": "A team outside the contest's sports"},
    },
)
def save_contest_aliases(
    contest_id: int, body: AliasesIn, subject: Subject, conn: Conn
) -> AliasesOut:
    """Maps names the contest's platform writes to teams, once (team_aliases, D-036)."""
    return contest_import.save_aliases(conn, contest_id, subject, body)


@router.get("/contests/{contest_id}", responses={404: {"description": "No such contest of yours"}})
def get_contest(
    contest_id: int, subject: Subject, period: Annotated[int | None, Query(ge=1)] = None
) -> ContestPageOut:
    """The Contest page (contest.py): the week asked for, else the newest with lines. Six
    queries in one wave (budget: ≤ 6)."""
    now = clock.now()
    found = run_wave(engine(), contest.queries(now, contest_id, subject, period))
    return contest.page_from(found, now)


@router.get("/contest", responses={404: {"description": "No such contest of yours"}})
def get_contest_screen(
    subject: Subject,
    contest_id: Annotated[int | None, Query(ge=1)] = None,
    period: Annotated[int | None, Query(ge=1)] = None,
) -> ContestPageOut:
    """The Contest screen's call (TASK-072, D-175): `GET /contests/{id}`'s page for `contest_id`,
    else for your first live contest (the default until `user_settings`, M8.7)."""
    now = clock.now()
    found = run_wave(engine(), contest.queries(now, contest_id, subject, period))
    return contest.page_from(found, now)


ENTRY_REFUSALS: dict[int | str, dict[str, Any]] = {
    404: {"model": ContestRefusalBody, "description": "No such contest, game or entry of yours"},
    409: {"model": ContestRefusalBody, "description": "The game is locked, or the week is full"},
}


@router.post("/contests/{contest_id}/entries", responses=ENTRY_REFUSALS)
def add_contest_entry(
    contest_id: int, body: EntryIn, subject: Subject, conn: Conn
) -> ContestEntryOut:
    """Adds your pick at the game's current contest line, or switches its side."""
    return contest.add_entry(conn, contest_id, subject, body, clock.now())


@router.delete(
    "/contests/{contest_id}/entries/{game_id}", status_code=204, responses=ENTRY_REFUSALS
)
def remove_contest_entry(contest_id: int, game_id: int, subject: Subject, conn: Conn) -> Response:
    """Removes your pick on the game (a soft delete)."""
    contest.remove_entry(conn, contest_id, subject, game_id, clock.now())
    return Response(status_code=204)


@router.post(
    "/contests/{contest_id}/standings",
    responses={404: {"description": "No such contest of yours"}},
)
def add_contest_standing(
    contest_id: int, body: StandingIn, subject: Subject, conn: Conn
) -> ContestStandingOut:
    """Records your league standing as of now."""
    return contest.add_standing(conn, contest_id, subject, body, clock.now())


@router.get("/openapi.json", include_in_schema=False)
def openapi() -> dict[str, Any]:
    return app.openapi()


@public.get("/health")
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
app.include_router(public)
