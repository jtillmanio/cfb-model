"""`parse_splash()`: the text of a Splash contest page, as the owner copies it, becomes one row per
game block (TASK-023, D-113). Names are matched through an alias lookup and never guessed: a name
the lookup doesn't hold comes back unmatched, for the inline picker (D-036).

A block lists the away side first and the home side second; each side is a record line (`4-0`,
or `3-1-1` with a tie) with the team name on the line before it and the side's line after it.
A block ends at its `Under …` line. Kickoffs are read in `tz` (the page prints none; Eastern by
default), in the year of the `Picks lock:` line. No block is dropped: one whose sides can't be
read, or whose lines are missing or disagree, comes back with a `problem` and no spread.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, tzinfo
from decimal import Decimal
from typing import Literal
from zoneinfo import ZoneInfo

EASTERN = ZoneInfo("America/New_York")

Problem = Literal["no line", "lines disagree", "unreadable block"]

_MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
MONTHS = {m: i for i, m in enumerate(_MONTHS, 1)}

# Page chrome: the header above the slate, and the picks counter below it (`0`, `/4`, `Picks made`;
# its `0` falls in no block).
_CHROME = {"Pick against the spread", "Picks lock:", "PICKS", "PTS", "STATUS", "GAME DETAILS"}
_CHROME |= {"Picks made"}
_COUNTER = re.compile(r"^/\d+$")
_LOCK = re.compile(
    r"^[A-Z][a-z]{2}, ([A-Z][a-z]{2}) (\d{1,2}), (\d{4}), (\d{1,2}):(\d{2}) ([AP]M)$"
)  # Mon, Oct 5, 2026, 8:15 PM
_DAY = re.compile(r"^(?:Mon|Tues|Wednes|Thurs|Fri|Satur|Sun)day, ([A-Z][a-z]{2}) (\d{1,2})$")
_KICKOFF = re.compile(r"^(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun) (\d{1,2}):(\d{2})([ap]m)$")
_RECORD = re.compile(r"^\d+-\d+(?:-\d+)?$")
_RANK = re.compile(r"^#\d+ranked #\d+$")
_SCORE = re.compile(r"^(?:\d+|-)$")  # a final or live score, or the dash between the two
_SPREAD = re.compile(r"^[+-]\d+(?:\.\d+)?$")
_PICK_EM = {"PK", "EVEN", "Pick"}


@dataclass(frozen=True)
class SplashRow:
    away_name: str | None  # as written; None only for an unreadable block
    home_name: str | None
    away_team_id: int | None
    home_team_id: int | None
    spread_home: Decimal | None  # the home side's line; None when there's a problem
    game_date: date | None
    kickoff_at: datetime | None  # UTC; None once the game has started (no time printed)
    status: str | None  # the page's text, e.g. "Preview", "Final", "LIVE Q3 14:07"
    problem: Problem | None
    source_lines: tuple[int, int]  # first and last line of the block in the pasted text

    @property
    def matched(self) -> bool:
        return self.away_team_id is not None and self.home_team_id is not None

    @property
    def spread_away(self) -> Decimal | None:
        return None if self.spread_home is None else -self.spread_home


@dataclass(frozen=True)
class SplashParse:
    rows: list[SplashRow]
    lock_at: datetime | None  # UTC


@dataclass
class _Block:
    day: tuple[int, int] | None  # (month, day) from the day header above the block
    lines: list[tuple[int, str]] = field(default_factory=list)  # (line number, text), no blanks

    @property
    def is_game(self) -> bool:
        return any(_RECORD.match(t) or t.startswith("Over ") for _, t in self.lines)


@dataclass(frozen=True)
class _Side:
    name: str
    name_index: int
    line: Decimal | None


def _spread(text: str) -> Decimal | None:
    if text in _PICK_EM:
        return Decimal(0)
    return Decimal(text) if _SPREAD.match(text) else None


def _clock(hour: str, minute: str, half: str) -> time:
    return time(int(hour) % 12 + (12 if half.lower() == "pm" else 0), int(minute))


def _lock_at(lines: list[str], tz: tzinfo) -> datetime | None:
    for line in lines:
        if m := _LOCK.match(line):
            month, day, year, hour, minute, half = m.groups()
            local = date(int(year), MONTHS[month], int(day))
            return datetime.combine(local, _clock(hour, minute, half), tz).astimezone(UTC)
    return None


def _blocks(lines: list[str]) -> list[_Block]:
    blocks: list[_Block] = []
    day: tuple[int, int] | None = None
    block = _Block(day)
    totals_seen = False

    def close() -> None:
        nonlocal block, totals_seen
        if block.is_game:
            blocks.append(block)
        block, totals_seen = _Block(day), False

    for number, text in enumerate(lines, 1):
        if not text or text in _CHROME or _COUNTER.match(text) or _LOCK.match(text):
            continue
        if m := _DAY.match(text):
            close()
            day = (MONTHS[m[1]], int(m[2]))
            block = _Block(day)
            continue
        if totals_seen and not text.startswith("Under "):
            close()  # a block whose `Under` line is missing
        block.lines.append((number, text))
        if text.startswith("Under "):
            close()
        elif text.startswith("Over "):
            totals_seen = True
    close()
    return blocks


def _sides(texts: list[str]) -> list[_Side]:
    sides = []
    for i, text in enumerate(texts):
        if _RECORD.match(text) and i > 0:
            line = _spread(texts[i + 1]) if i + 1 < len(texts) else None
            sides.append(_Side(texts[i - 1], i - 1, line))
    return sides


def _row(block: _Block, lock: datetime | None, tz: tzinfo, aliases: Mapping[str, int]) -> SplashRow:
    texts = [t for _, t in block.lines]
    sides = _sides(texts)
    readable = len(sides) == 2
    header = texts[: sides[0].name_index] if sides else texts
    names = {s.name for s in sides}

    game_date = None
    if block.day and lock:
        month, day = block.day
        lock_local = lock.astimezone(tz)
        game_date = date(lock_local.year - (month > lock_local.month), month, day)
    kickoff_at = None
    clocks = [m for t in header if (m := _KICKOFF.match(t))]
    if game_date and clocks:
        kickoff_at = datetime.combine(game_date, _clock(*clocks[0].groups()), tz).astimezone(UTC)
    status = " ".join(
        t
        for t in header
        if not (_SCORE.match(t) or _RANK.match(t) or _KICKOFF.match(t) or t in names)
        and not t.startswith(("Over ", "Under "))
    )

    spread_home: Decimal | None = None
    problem: Problem | None = None
    if not readable:
        problem = "unreadable block"
    else:
        away, home = sides[0].line, sides[1].line
        if away is None or home is None:
            problem = "no line"
        elif away + home != 0:
            problem = "lines disagree"
        else:
            spread_home = home

    away_name = sides[0].name if readable else None
    home_name = sides[1].name if readable else None
    return SplashRow(
        away_name=away_name,
        home_name=home_name,
        away_team_id=aliases.get(away_name) if away_name else None,
        home_team_id=aliases.get(home_name) if home_name else None,
        spread_home=spread_home,
        game_date=game_date,
        kickoff_at=kickoff_at,
        status=status or None,
        problem=problem,
        source_lines=(block.lines[0][0], block.lines[-1][0]),
    )


def parse_splash(text: str, aliases: Mapping[str, int], *, tz: tzinfo = EASTERN) -> SplashParse:
    """One row per game block in `text`, in page order. `aliases` maps a team name exactly as
    Splash writes it to `teams.id`; the contest import builds it from `team_aliases` (D-036)."""
    lines = [line.strip() for line in text.splitlines()]
    lock = _lock_at(lines, tz)
    return SplashParse([_row(b, lock, tz, aliases) for b in _blocks(lines)], lock)
