"""The contest import (TASK-070, D-038, D-113): a pasted contest page becomes rows matched to games,
names the page uses can be mapped to teams once, and confirming saves the week's contest lines as a
new snapshot.

The page is parsed by `engine.core.splash` (the light core, hard rule 5) in Eastern time until
`user_settings` arrives (M8.7). A team name resolves through `team_aliases` under the contest's
platform; a name with no alias falls back to an exact `teams.school` or `teams.mascot` match within
the contest's sports, saving nothing. A row is matched only when exactly one game on its date pairs
the two sides (either way round at a neutral site, with the line turned to the stored home side).

Every route but the reads here runs on the one connection `main.connection` gives the request, so a
write commits or rolls back whole. The statements run in turn: a POST isn't a screen's page call,
whose budget is one wave (docs/02 › Non-functional requirements)."""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Connection, text

from engine.core.contest_rules import ContestRules
from engine.core.splash import SplashParse, SplashRow, parse_splash

# The owner's zone and the parser's default, until user_settings (M8.7).
TIME_ZONE = ZoneInfo("America/New_York")
MAX_CANDIDATES = 8
MAX_TEXT = 200_000  # a full Splash page is about 15 KB

RowStatus = Literal["matched", "unmatched", "no_game", "ambiguous", "duplicate", "problem"]
ErrorCode = Literal["unparseable", "no_match", "unresolved"]


# Requests


class ImportIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=MAX_TEXT)
    period: int = Field(ge=1)  # the contest's week; the page prints none


class AliasMappingIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    alias: str = Field(min_length=1, max_length=200)  # the name exactly as the page writes it
    team_id: int


class AliasesIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mappings: list[AliasMappingIn] = Field(min_length=1, max_length=100)


# Responses


class ImportTeamOut(BaseModel):
    id: int
    sport_id: str
    school: str
    mascot: str | None
    abbreviation: str | None
    color: str | None


class ImportNameOut(BaseModel):
    """A name that resolves to no team, with the teams playing that day it most likely means."""

    name: str
    candidates: list[ImportTeamOut]


class ImportRowOut(BaseModel):
    index: int  # page order, from 0
    first_line: int  # the block's lines in the pasted text, from 1
    last_line: int
    away_name: str | None  # as written; None only for an unreadable block
    home_name: str | None
    status: RowStatus
    problem: Literal["no line", "lines disagree", "unreadable block"] | None
    matched_by: Literal["alias", "name"] | None  # "alias" when both sides came from aliases
    swapped: bool  # a neutral-site game the page lists the other way round from the stored one
    game_id: int | None
    sport_id: str | None
    away_team: ImportTeamOut | None  # the stored game's sides once matched; else as written
    home_team: ImportTeamOut | None
    spread_home: float | None  # on home_team's side; None for a problem row
    game_date: date | None
    kickoff_at: datetime | None  # the game's when matched, else the page's
    page_status: str | None  # the page's text, e.g. "Preview", "Final"
    unmatched: list[ImportNameOut]


class ImportCountsOut(BaseModel):
    rows: int
    matched: int
    unmatched: int  # not matched and not a problem: unmatched, no game, ambiguous, duplicate
    problem: int


class LineChangeOut(BaseModel):
    """A matched row whose line differs from the contest's current line (the re-paste diff)."""

    index: int
    game_id: int
    contest_line_id: int
    old_spread_home: float
    old_captured_at: datetime
    new_spread_home: float


class ImportPreviewOut(BaseModel):
    contest_id: int
    period: int
    lock_at: datetime | None
    rows: list[ImportRowOut]
    counts: ImportCountsOut
    changes: list[LineChangeOut]


class ImportRefusalOut(BaseModel):
    code: ErrorCode
    message: str
    rows: list[ImportRowOut]


class ImportRefusalBody(BaseModel):
    detail: ImportRefusalOut


class ContestLineOut(BaseModel):
    contest_line_id: int
    game_id: int
    spread_home: float


class ImportConfirmOut(BaseModel):
    contest_id: int
    period: int
    captured_at: datetime
    inserted: int
    lines: list[ContestLineOut]


class AliasOut(BaseModel):
    alias: str
    team_id: int
    created: bool


class AliasesOut(BaseModel):
    source: str
    created: int
    aliases: list[AliasOut]


class AliasConflictOut(BaseModel):
    code: Literal["alias_conflict", "unknown_team"]
    message: str
    aliases: list[str]


class AliasConflictBody(BaseModel):
    detail: AliasConflictOut


# The contest and its owner


@dataclass(frozen=True)
class ContestRef:
    id: int
    platform: str
    sports: tuple[str, ...]


def github_id(subject: str) -> int:
    """The token's `sub` is the GitHub user id (D-105); anything else gets the API's one 401."""
    if not subject.isdigit():
        raise HTTPException(401, "Not authenticated", headers={"WWW-Authenticate": "Bearer"})
    return int(subject)


def upsert_user(conn: Connection, subject: str) -> int:
    """The `users` row for the token's GitHub id, inserted on the first write (D-170)."""
    return conn.execute(
        text(
            "INSERT INTO users (github_id) VALUES (:g)"
            " ON CONFLICT (github_id) DO UPDATE SET github_id = EXCLUDED.github_id RETURNING id"
        ),
        {"g": github_id(subject)},
    ).scalar_one()


def find_contest(conn: Connection, contest_id: int, subject: str) -> ContestRef:
    """The caller's live contest, else 404 (another user's looks the same as none)."""
    row = conn.execute(
        text(
            "SELECT c.id, c.platform, c.rules FROM contests c JOIN users u ON u.id = c.user_id"
            " WHERE c.id = :c AND u.github_id = :g AND c.deleted_at IS NULL"
        ),
        {"c": contest_id, "g": github_id(subject)},
    ).one_or_none()
    if row is None:
        raise HTTPException(404, "No such contest")
    rules = ContestRules.model_validate(row.rules)
    return ContestRef(row.id, row.platform, rules.sports)


# Matching


@dataclass(frozen=True)
class Team:
    id: int
    sport_id: str
    school: str
    mascot: str | None
    abbreviation: str | None
    color: str | None

    def out(self) -> ImportTeamOut:
        return ImportTeamOut(**self.__dict__)


@dataclass(frozen=True)
class Game:
    id: int
    sport_id: str
    game_date: date
    kickoff_at: datetime | None
    neutral_site: bool
    home: Team
    away: Team


@dataclass(frozen=True)
class Names:
    """How the paste's names resolve: by alias (one team each), else by school or nickname."""

    aliases: dict[str, Team]
    by_name: dict[str, list[Team]]

    def resolve(self, name: str | None) -> tuple[list[Team], bool]:
        """The teams `name` may mean, and whether an alias said so."""
        if name is None:
            return [], False
        if name in self.aliases:
            return [self.aliases[name]], True
        return self.by_name.get(name, []), False


@dataclass(frozen=True)
class Matched:
    row: SplashRow
    out: ImportRowOut
    spread_home: Decimal | None  # on the stored game's home side


_WORD = re.compile(r"[a-z0-9]+")


def _words(value: str | None) -> list[str]:
    return _WORD.findall(value.lower()) if value else []


def candidates(name: str, teams: Iterable[Team]) -> list[ImportTeamOut]:
    """The teams `name` most likely means, best first: one point for each of its words that starts
    a word of a team's school or nickname or is its abbreviation. Teams scoring nothing are left
    out."""
    words = [w for w in _words(name) if len(w) >= 2]
    scored = []
    for team in teams:
        team_words = _words(team.school) + _words(team.mascot)
        abbreviation = (team.abbreviation or "").lower()
        score = sum(
            1 for w in words if w == abbreviation or any(t.startswith(w) for t in team_words)
        )
        if score:
            scored.append((-score, team.school, team.mascot or "", team.id, team))
    scored.sort(key=lambda s: s[:4])
    return [s[4].out() for s in scored[:MAX_CANDIDATES]]


def _pair(row: SplashRow, games: Sequence[Game], away: list[Team], home: list[Team]):
    """The games on the row's date pairing the sides: as written, else either way round at a
    neutral site (Splash's order there needn't be the stored one). Returns (games, flipped)."""
    on_day = [g for g in games if g.game_date == row.game_date]
    away_ids, home_ids = {t.id for t in away}, {t.id for t in home}
    straight = [g for g in on_day if g.away.id in away_ids and g.home.id in home_ids]
    if straight:
        return straight, False
    flipped = [
        g for g in on_day if g.neutral_site and g.home.id in away_ids and g.away.id in home_ids
    ]
    return flipped, True


def match_rows(parse: SplashParse, names: Names, games: Sequence[Game]) -> list[Matched]:
    """Every parsed row, in page order, with its status. None is dropped."""
    teams_by_day: dict[date, dict[int, Team]] = defaultdict(dict)
    for g in games:
        teams_by_day[g.game_date] |= {g.home.id: g.home, g.away.id: g.away}
    seen: set[int] = set()
    matched: list[Matched] = []
    for index, row in enumerate(parse.rows):
        away, away_alias = names.resolve(row.away_name)
        home, home_alias = names.resolve(row.home_name)
        status: RowStatus
        game: Game | None = None
        flipped = False
        unmatched = [
            ImportNameOut(
                name=n,
                candidates=candidates(n, teams_by_day.get(row.game_date, {}).values())
                if row.game_date
                else [],
            )
            for n, ts in ((row.away_name, away), (row.home_name, home))
            if n is not None and not ts
        ]
        if row.away_name is None or unmatched:
            status = "unmatched"
        else:
            found, flipped = _pair(row, games, away, home)
            status = "matched" if len(found) == 1 else "ambiguous" if found else "no_game"
            if len(found) == 1:
                game = found[0]
                if game.id in seen:
                    status = "duplicate"
                seen.add(game.id)
        if row.problem is not None:
            status = "problem"

        spread = row.spread_home
        if game is None:
            away_team = away[0] if len(away) == 1 else None
            home_team = home[0] if len(home) == 1 else None
        else:  # the stored game's sides, and its home side's line
            away_team, home_team = game.away, game.home
            if flipped and spread is not None:
                spread = -spread
        out = ImportRowOut(
            index=index,
            first_line=row.source_lines[0],
            last_line=row.source_lines[1],
            away_name=row.away_name,
            home_name=row.home_name,
            status=status,
            problem=row.problem,
            matched_by=None if game is None else "alias" if away_alias and home_alias else "name",
            swapped=game is not None and flipped,
            game_id=None if game is None else game.id,
            sport_id=None if game is None else game.sport_id,
            away_team=None if away_team is None else away_team.out(),
            home_team=None if home_team is None else home_team.out(),
            spread_home=None if spread is None else float(spread),
            game_date=row.game_date,
            kickoff_at=row.kickoff_at if game is None else game.kickoff_at,
            page_status=row.status,
            unmatched=unmatched,
        )
        matched.append(Matched(row, out, spread))
    return matched


def counts(rows: Sequence[ImportRowOut]) -> ImportCountsOut:
    return ImportCountsOut(
        rows=len(rows),
        matched=sum(r.status == "matched" for r in rows),
        unmatched=sum(r.status not in ("matched", "problem") for r in rows),
        problem=sum(r.status == "problem" for r in rows),
    )


# Reads


_TEAM = "t.id, t.sport_id, t.school, t.mascot, t.abbreviation, t.color"

NAMES_SQL = text(
    f"""
    SELECT 'alias' AS via, a.alias AS name, {_TEAM}
    FROM team_aliases a JOIN teams t ON t.id = a.team_id
    WHERE a.source = :platform AND a.alias = ANY(:names) AND t.sport_id = ANY(:sports)
    UNION ALL
    SELECT 'name', t.school, {_TEAM} FROM teams t
    WHERE t.sport_id = ANY(:sports) AND t.school = ANY(:names)
    UNION ALL
    SELECT 'name', t.mascot, {_TEAM} FROM teams t
    WHERE t.sport_id = ANY(:sports) AND t.mascot = ANY(:names)
    """
)

GAMES_SQL = text(
    """
    SELECT g.id, g.sport_id, g.game_date, g.kickoff_at, g.neutral_site,
        h.id AS h_id, h.sport_id AS h_sport_id, h.school AS h_school, h.mascot AS h_mascot,
        h.abbreviation AS h_abbreviation, h.color AS h_color,
        a.id AS a_id, a.sport_id AS a_sport_id, a.school AS a_school, a.mascot AS a_mascot,
        a.abbreviation AS a_abbreviation, a.color AS a_color
    FROM games g
    JOIN teams h ON h.id = g.home_team_id
    JOIN teams a ON a.id = g.away_team_id
    WHERE g.sport_id = ANY(:sports) AND g.game_date = ANY(:dates)
    """
)

# Each game's newest contest line as of the API's clock, captured before the game's cutoff (the
# rule current_contest_lines follows, TASK-068), read on the contest's own lines.
CURRENT_LINES_SQL = text(
    """
    SELECT DISTINCT ON (l.game_id) l.id, l.game_id, l.spread_home, l.captured_at
    FROM contest_lines l
    JOIN games g ON g.id = l.game_id
    WHERE l.contest_id = :contest AND l.game_id = ANY(:games) AND l.captured_at <= :now
        AND l.captured_at < coalesce(
            g.kickoff_at, (g.game_date + 1)::timestamp AT TIME ZONE 'America/New_York'
        )
    ORDER BY l.game_id, l.captured_at DESC, l.id DESC
    """
)


def _team(row: Any, prefix: str = "") -> Team:
    return Team(
        id=getattr(row, f"{prefix}id"),
        sport_id=getattr(row, f"{prefix}sport_id"),
        school=getattr(row, f"{prefix}school"),
        mascot=getattr(row, f"{prefix}mascot"),
        abbreviation=getattr(row, f"{prefix}abbreviation"),
        color=getattr(row, f"{prefix}color"),
    )


def load_names(conn: Connection, contest: ContestRef, parse: SplashParse) -> Names:
    wanted = sorted({n for r in parse.rows for n in (r.away_name, r.home_name) if n})
    aliases: dict[str, Team] = {}
    by_name: dict[str, list[Team]] = defaultdict(list)
    for r in conn.execute(
        NAMES_SQL, {"platform": contest.platform, "names": wanted, "sports": list(contest.sports)}
    ):
        if r.via == "alias":
            aliases[r.name] = _team(r)
        elif all(t.id != r.id for t in by_name[r.name]):
            by_name[r.name].append(_team(r))
    return Names(aliases, dict(by_name))


def load_games(conn: Connection, contest: ContestRef, parse: SplashParse) -> list[Game]:
    dates = sorted({r.game_date for r in parse.rows if r.game_date})
    if not dates:
        return []
    return [
        Game(
            id=r.id,
            sport_id=r.sport_id,
            game_date=r.game_date,
            kickoff_at=r.kickoff_at,
            neutral_site=r.neutral_site,
            home=_team(r, "h_"),
            away=_team(r, "a_"),
        )
        for r in conn.execute(GAMES_SQL, {"sports": list(contest.sports), "dates": dates})
    ]


def _refuse(code: ErrorCode, message: str, rows: Sequence[ImportRowOut]) -> HTTPException:
    detail = ImportRefusalOut(code=code, message=message, rows=list(rows))
    return HTTPException(422, detail.model_dump(mode="json"))


def read_paste(
    conn: Connection, contest: ContestRef, body: ImportIn
) -> tuple[SplashParse, list[Matched]]:
    """Parse and match the paste; 422 when nothing in it is a game, or no name is a team."""
    parse = parse_splash(body.text, {}, tz=TIME_ZONE)
    if all(r.problem == "unreadable block" for r in parse.rows):  # also no rows at all
        raise _refuse("unparseable", "No game could be read from the pasted text.", [])
    names = load_names(conn, contest, parse)
    matched = match_rows(parse, names, load_games(conn, contest, parse))
    if not names.aliases and not names.by_name:
        rows = [m.out for m in matched]
        raise _refuse("no_match", "No team in the pasted text matched a team we know.", rows)
    return parse, matched


# Routes' work


def preview(
    conn: Connection, contest_id: int, subject: str, body: ImportIn, now: datetime
) -> ImportPreviewOut:
    contest = find_contest(conn, contest_id, subject)
    parse, matched = read_paste(conn, contest, body)
    rows = [m.out for m in matched]
    playing = {
        m.out.game_id: m
        for m in matched
        if m.out.status == "matched" and m.spread_home is not None  # a pick'em line is 0
    }
    changes = []
    if playing:
        current = conn.execute(
            CURRENT_LINES_SQL, {"contest": contest.id, "games": list(playing), "now": now}
        )
        for line in current:
            m = playing[line.game_id]
            if m.spread_home is not None and m.spread_home != line.spread_home:
                changes.append(
                    LineChangeOut(
                        index=m.out.index,
                        game_id=line.game_id,
                        contest_line_id=line.id,
                        old_spread_home=float(line.spread_home),
                        old_captured_at=line.captured_at,
                        new_spread_home=float(m.spread_home),
                    )
                )
    changes.sort(key=lambda c: c.index)
    return ImportPreviewOut(
        contest_id=contest.id,
        period=body.period,
        lock_at=parse.lock_at,
        rows=rows,
        counts=counts(rows),
        changes=changes,
    )


def confirm(
    conn: Connection, contest_id: int, subject: str, body: ImportIn, now: datetime
) -> ImportConfirmOut:
    upsert_user(conn, subject)
    contest = find_contest(conn, contest_id, subject)
    _, matched = read_paste(conn, contest, body)
    blocking = [m.out for m in matched if m.out.status != "matched" or m.spread_home is None]
    if blocking:
        message = "Every row must match one game and have a line before confirming."
        raise _refuse("unresolved", message, blocking)
    inserted = conn.execute(
        text(
            "INSERT INTO contest_lines (contest_id, period, game_id, spread_home, captured_at,"
            " source)"
            " SELECT :contest, :period, x.game_id, x.spread_home, :now, 'paste'"
            " FROM unnest(CAST(:games AS bigint[]), CAST(:spreads AS numeric[]))"
            " AS x(game_id, spread_home)"
            " RETURNING id, game_id, spread_home"
        ),
        {
            "contest": contest.id,
            "period": body.period,
            "now": now,
            "games": [m.out.game_id for m in matched],
            "spreads": [m.spread_home for m in matched],
        },
    ).all()
    return ImportConfirmOut(
        contest_id=contest.id,
        period=body.period,
        captured_at=now,
        inserted=len(inserted),
        lines=[
            ContestLineOut(
                contest_line_id=r.id, game_id=r.game_id, spread_home=float(r.spread_home)
            )
            for r in inserted
        ],
    )


def save_aliases(conn: Connection, contest_id: int, subject: str, body: AliasesIn) -> AliasesOut:
    """Each name as the contest's platform writes it, mapped to a team of the contest's sports.
    A mapping already stored is skipped; one naming another team refuses the whole request."""
    upsert_user(conn, subject)
    contest = find_contest(conn, contest_id, subject)
    wanted: dict[str, int] = {}
    for m in body.mappings:
        if wanted.setdefault(m.alias, m.team_id) != m.team_id:
            raise _alias_refusal(409, "alias_conflict", "A name is mapped to two teams.", [m.alias])
    teams = {
        r.id: r.sport_id
        for r in conn.execute(
            text("SELECT id, sport_id FROM teams WHERE id = ANY(:ids)"),
            {"ids": sorted(set(wanted.values()))},
        )
    }
    unknown = [a for a, t in wanted.items() if teams.get(t) not in contest.sports]
    if unknown:
        message = "A team isn't one of the contest's sports."
        raise _alias_refusal(422, "unknown_team", message, unknown)
    stored = {
        r.alias: r.team_id
        for r in conn.execute(
            text("SELECT alias, team_id FROM team_aliases WHERE source = :s AND alias = ANY(:a)"),
            {"s": contest.platform, "a": list(wanted)},
        )
    }
    taken = [a for a, t in wanted.items() if a in stored and stored[a] != t]
    if taken:
        raise _alias_refusal(409, "alias_conflict", "A name already means another team.", taken)
    new = [a for a in wanted if a not in stored]
    if new:
        conn.execute(
            text(
                "INSERT INTO team_aliases (team_id, source, alias) VALUES (:t, :s, :a)"
                " ON CONFLICT (source, alias) DO NOTHING"
            ),
            [{"t": wanted[a], "s": contest.platform, "a": a} for a in new],
        )
    return AliasesOut(
        source=contest.platform,
        created=len(new),
        aliases=[AliasOut(alias=a, team_id=t, created=a in new) for a, t in wanted.items()],
    )


def _alias_refusal(
    status: int, code: Literal["alias_conflict", "unknown_team"], message: str, aliases: list[str]
) -> HTTPException:
    detail = AliasConflictOut(code=code, message=message, aliases=aliases)
    return HTTPException(status, detail.model_dump(mode="json"))
