"""`parse_splash()` (TASK-023): text copied from a Splash contest page becomes one row per game,
matched through an alias lookup or left unmatched (docs/03-data-model.md › Contest lines, D-038).

The two real copies are read from `design/` in place; the Week 6 paste is written out from
`design/handoff/designs/contest-data.js` as `fixtures/splash_week6.txt`."""

import re
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

from engine.contests.splash import SplashRow, parse_splash

DESIGN = Path(__file__).parents[3] / "design"
OCT_6 = DESIGN / "sample-splash-10062026.txt"
OCT_15 = DESIGN / "sample-splash-10152026.txt"
WEEK_6 = Path(__file__).parent / "fixtures" / "splash_week6.txt"

WEEK_6_NAMES = [
    "UNLV", "Boise State", "Purdue", "Ohio State", "Ole Miss", "LSU", "Notre Dame", "Stanford",
    "Texas", "Oklahoma", "Colorado", "BYU", "Bills", "Jets", "Chiefs", "Ravens", "Giants", "Eagles",
]  # fmt: skip
WEEK_6_ALIASES = {name: team_id for team_id, name in enumerate(WEEK_6_NAMES, start=1)}

# What a team name must never be: a rank line, a record (ties too), a score, the score dash, a
# status or game clock, a total, or the picks counter.
NOT_A_NAME = re.compile(
    r"#\d+ranked|^\d+-\d+(-\d+)?$|^\d+$|^-$|^(Final|LIVE|Preview)$|^Q\d|^(Over|Under) |^/\d+$"
    r"|^Picks made$"
)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def over_lines(text: str) -> int:
    return sum(1 for line in text.splitlines() if line.startswith("Over "))


def by_teams(rows: list[SplashRow]) -> dict[tuple[str | None, str | None], SplashRow]:
    return {(r.away_name, r.home_name): r for r in rows}


def test_the_oct_6_copy_gives_one_row_per_over_line() -> None:
    text = read(OCT_6)

    rows = parse_splash(text, {}).rows

    assert len(rows) == over_lines(text) == 72
    for row in rows:
        assert row.problem is None, row
        assert row.spread_home is not None and row.spread_away == -row.spread_home
        for name in (row.away_name, row.home_name):
            assert name and not NOT_A_NAME.search(name), row
    games = by_teams(rows)
    assert len(games) == 72
    assert games["Notre Dame", "North Carolina"].spread_home == Decimal("21.5")  # ND -21.5
    assert games["Steelers", "Browns"].spread_home == Decimal("2.5")
    assert games["Cardinals", "Giants"].status == "LIVE Q3 14:07"


def test_week6_paste_matches_nine_and_flags_hou_jax() -> None:
    rows = parse_splash(read(WEEK_6), WEEK_6_ALIASES).rows

    assert len(rows) == 10
    assert sum(r.matched for r in rows) == 9
    [unmatched] = [r for r in rows if not r.matched]
    assert (unmatched.away_name, unmatched.home_name) == ("Hou Texans", "Jax")
    assert (unmatched.away_team_id, unmatched.home_team_id) == (None, None)
    assert unmatched.spread_home == Decimal("1")
    games = by_teams(rows)
    texas = games["Texas", "Oklahoma"]
    assert (texas.away_team_id, texas.home_team_id) == (
        WEEK_6_ALIASES["Texas"],
        WEEK_6_ALIASES["Oklahoma"],
    )
    assert texas.spread_home == Decimal("7")
    assert games["UNLV", "Boise State"].spread_home == Decimal("-10")


def test_disagreeing_and_missing_lines_are_flagged_not_dropped() -> None:
    text = read(WEEK_6)
    text = text.replace("Boise State\n4-1\n-10\n", "Boise State\n4-1\n-9.5\n")
    text = text.replace("Purdue\n1-4\n+27\n", "Purdue\n1-4\n")
    text = text.replace("Ohio State\n5-0\n-27\n", "Ohio State\n5-0\n")

    rows = parse_splash(text, WEEK_6_ALIASES).rows

    assert len(rows) == 10
    games = by_teams(rows)
    boise = games["UNLV", "Boise State"]
    assert (boise.problem, boise.spread_home) == ("lines disagree", None)
    ohio_state = games["Purdue", "Ohio State"]
    assert (ohio_state.problem, ohio_state.spread_home) == ("no line", None)
    others = [r for r in rows if r not in (boise, ohio_state)]
    assert all(r.problem is None and r.spread_home is not None for r in others)


def test_a_block_without_two_sides_is_kept_as_unreadable() -> None:
    text = read(WEEK_6).replace("UNLV\n3-2\n+10\n\n", "")

    rows = parse_splash(text, WEEK_6_ALIASES).rows

    assert len(rows) == 10
    first = rows[0]
    assert (first.problem, first.away_name, first.home_name) == ("unreadable block", None, None)
    assert first.spread_home is None and not first.matched
    assert all(r.problem is None for r in rows[1:])


def test_the_oct_15_copy_gives_73_rows_without_the_counter_or_ties_in_names() -> None:
    text = read(OCT_15)

    rows = parse_splash(text, {}).rows

    assert len(rows) == over_lines(text) == 73
    assert len({(r.away_name, r.home_name, r.game_date) for r in rows}) == 73
    for row in rows:
        assert row.problem is None, row
        for name in (row.away_name, row.home_name):
            assert name and not NOT_A_NAME.search(name), row
    last = by_teams(rows)["Commanders", "49ers"]  # the Commanders are 1-3-1
    assert last.spread_home == Decimal("-7.5")
    assert last.kickoff_at == datetime(2026, 10, 20, 0, 15, tzinfo=UTC)  # Mon 8:15pm EDT


def test_kickoffs_are_eastern_time_in_utc() -> None:
    week_6 = parse_splash(read(WEEK_6), WEEK_6_ALIASES)
    boise = by_teams(week_6.rows)["UNLV", "Boise State"]
    assert boise.game_date == date(2026, 10, 9)
    assert boise.kickoff_at == datetime(2026, 10, 10, 0, 0, tzinfo=UTC)  # Fri 8:00pm EDT
    assert week_6.lock_at == datetime(2026, 10, 12, 0, 20, tzinfo=UTC)  # Sun, Oct 11, 8:20 PM

    final = by_teams(parse_splash(read(OCT_6), {}).rows)["Western Kentucky", "New Mexico State"]
    assert (final.status, final.game_date, final.kickoff_at) == ("Final", date(2026, 10, 1), None)


def test_a_december_game_on_a_january_lock_is_the_year_before() -> None:
    text = read(WEEK_6).replace("Sun, Oct 11, 2026, 8:20 PM", "Mon, Jan 4, 2027, 8:00 PM")
    text = text.replace("Friday, Oct 9", "Thursday, Dec 31")
    text = text.replace("Saturday, Oct 10", "Friday, Jan 1")

    games = by_teams(parse_splash(text, {}).rows)

    assert games["UNLV", "Boise State"].game_date == date(2026, 12, 31)
    assert games["Purdue", "Ohio State"].game_date == date(2027, 1, 1)
