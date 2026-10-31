"""Data-quality checks on `staging/` (docs/03-data-model.md › Data quality checks, D-116).

`run(lake)` loads the staged tables and runs every check in `CHECKS`. A check returns failures
(each names the offending game's `source_id`) and notes (listed, never failing). Publishing
(TASK-020) calls `run` and refuses when `not report.ok`, so nothing partial reaches Postgres.
"""

from __future__ import annotations

import io
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from engine.ingest.lake import Lake
from engine.transform import TABLES, staging_key
from engine.transform.staging import connect

if TYPE_CHECKING:
    import duckdb

# The backtest seasons (docs/04-model.md § 9.1): each FBS-vs-FBS game in them needs a closing
# line, or a mark saying none exists.
BACKTEST_SEASONS = (2014, 2025)
# Team-games in the backtest seasons that CFBD has no advanced stats for, per the 2026-10-20
# backfill (D-121). More than this fails `advanced_stats`: a staging regression (e.g. names that
# stopped matching) or new CFBD gaps. Check which, then raise it.
KNOWN_MISSING_ADVANCED = 103


class StagingMissingError(RuntimeError):
    pass


@dataclass(frozen=True)
class Finding:
    failures: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Check:
    name: str
    description: str
    run: Callable[[duckdb.DuckDBPyConnection], Finding]


@dataclass
class Report:
    results: list[tuple[Check, Finding]] = field(default_factory=list)

    @property
    def failures(self) -> dict[str, list[str]]:
        return {c.name: f.failures for c, f in self.results if f.failures}

    @property
    def notes(self) -> dict[str, list[str]]:
        return {c.name: f.notes for c, f in self.results if f.notes}

    @property
    def ok(self) -> bool:
        return not self.failures

    def render(self) -> str:
        failed = len(self.failures)
        lines = [f"Data quality: {len(self.results) - failed} passed, {failed} failed."]
        for check, finding in self.results:
            status = "FAIL" if finding.failures else "PASS"
            lines.append(f"{status} {check.name}: {check.description}")
            lines += [f"  {item}" for item in finding.failures]
            if finding.notes:
                lines.append(f"  notes ({len(finding.notes)}):")
                lines += [f"    {item}" for item in finding.notes]
        return "\n".join(lines)


def _rows(con: duckdb.DuckDBPyConnection, sql: str) -> list[str]:
    return [row[0] for row in con.execute(sql).fetchall()]


def _game() -> str:
    """A game's label; concat() skips a NULL part, so the `source_id` always prints."""
    return (
        "concat(source_id, ' (', season, ' ', season_type, ' week ', week, ', ', "
        "away_source_id, ' at ', home_source_id, ')')"
    )


def final_has_score(con: duckdb.DuckDBPyConnection) -> Finding:
    return Finding(
        _rows(
            con,
            f"""SELECT {_game()} FROM games
            WHERE status = 'final' AND (home_points IS NULL OR away_points IS NULL)
            ORDER BY source_id""",
        )
    )


def no_duplicate_games(con: duckdb.DuckDBPyConnection) -> Finding:
    """Same two teams (either way round) on the same Eastern date."""
    return Finding(
        _rows(
            con,
            """SELECT concat(string_agg(source_id, ', ' ORDER BY source_id), ': teams ',
                least(home_source_id, away_source_id), ' and ',
                greatest(home_source_id, away_source_id), ' on ', game_date)
            FROM games
            GROUP BY least(home_source_id, away_source_id),
                greatest(home_source_id, away_source_id), game_date
            HAVING count(*) > 1
            ORDER BY 1""",
        )
    )


def closing_line(con: duckdb.DuckDBPyConnection) -> Finding:
    """A final FBS-vs-FBS game in a backtest season needs `closing_line_missing` set: false
    (a post-kickoff pull quotes a spread) or true (one covers it and quotes none, listed as a
    note). NULL means /lines was never pulled after kickoff for it, which fails. A game whose
    classification is unknown can't be scoped, so it's listed as a note."""
    first, last = BACKTEST_SEASONS
    finals = f"FROM games WHERE status = 'final' AND season BETWEEN {first} AND {last}"
    scope = f"{finals} AND home_classification = 'fbs' AND away_classification = 'fbs'"
    return Finding(
        failures=_rows(
            con,
            f"SELECT {_game()} {scope} AND closing_line_missing IS NULL ORDER BY source_id",
        ),
        notes=_rows(
            con,
            f"SELECT concat({_game()}, ': no closing line from any provider') {scope} "
            "AND closing_line_missing ORDER BY source_id",
        )
        + _rows(
            con,
            f"SELECT concat({_game()}, ': classification unknown, so not checked') {finals} "
            "AND (home_classification IS NULL OR away_classification IS NULL) "
            "ORDER BY source_id",
        ),
    )


def advanced_stats(con: duckdb.DuckDBPyConnection) -> Finding:
    """Each FBS side of a final game needs a `team_game_advanced` row. A missing one is a note
    when advanced stats fetched 7+ days after its kickoff cover its week: CFBD has none for it
    (D-121). Otherwise it fails when the game is in a backtest season, or when advanced stats
    fetched after its kickoff cover its week (CFBD may still fill it in); else the week hasn't
    been pulled since kickoff (the live season before its stats job), a note too (D-119)."""
    first, last = BACKTEST_SEASONS
    cte = f"""
    WITH g AS (
        SELECT *, coalesce(kickoff_at, timezone('America/New_York',
            CAST(game_date + 1 AS TIMESTAMP))) AS cutoff
        FROM games WHERE status = 'final'
    ),
    sides AS (
        SELECT *, home_source_id AS team FROM g WHERE home_classification = 'fbs'
        UNION ALL
        SELECT *, away_source_id AS team FROM g WHERE away_classification = 'fbs'
    ),
    missing AS (
        SELECT s.*, s.season BETWEEN {first} AND {last} OR EXISTS (
            SELECT 1 FROM team_game_advanced a
            WHERE a.season = s.season AND a.season_type = s.season_type AND a.week = s.week
              AND a.fetched_at > s.cutoff) AS required,
            EXISTS (
            SELECT 1 FROM team_game_advanced a
            WHERE a.season = s.season AND a.season_type = s.season_type AND a.week = s.week
              AND a.fetched_at >= s.cutoff + INTERVAL 7 DAY) AS settled
        FROM sides s
        WHERE NOT EXISTS (
            SELECT 1 FROM team_game_advanced a
            WHERE a.game_source_id = s.source_id AND a.team_source_id = s.team)
    )"""
    label = f"concat({_game()}, ': no advanced stats for team ', team"
    known = _rows(
        con,
        f"{cte} SELECT CAST(count(*) AS VARCHAR) FROM missing "
        f"WHERE settled AND season BETWEEN {first} AND {last}",
    )
    above = [
        f"{n} team-games in {first}-{last} CFBD has no advanced stats for, above the "
        f"{KNOWN_MISSING_ADVANCED} known (D-121): a staging regression or new CFBD gaps"
        for n in map(int, known)
        if n > KNOWN_MISSING_ADVANCED
    ]
    return Finding(
        failures=above
        + _rows(
            con, f"{cte} SELECT {label}) FROM missing WHERE required AND NOT settled ORDER BY 1"
        ),
        notes=_rows(
            con,
            f"{cte} SELECT {label}, CASE WHEN settled "
            "THEN ' (CFBD has none: a pull 7+ days after kickoff covers the week without it)' "
            "ELSE ' (none pulled since kickoff)' END) FROM missing "
            "WHERE settled OR NOT required ORDER BY 1",
        ),
    )


def not_played(con: duckdb.DuckDBPyConnection) -> Finding:
    """Each game staged `canceled` (D-121's rule, TASK-044), listed so a game CFBD left under
    its old week while postponed is seen; never a failure."""
    return Finding(
        notes=_rows(
            con,
            f"""SELECT concat({_game()}, ': ', status, ', started ', coalesce(
                CAST(kickoff_at AS VARCHAR), concat(game_date, ' (time TBA)')))
            FROM games WHERE status IN ('canceled', 'postponed') ORDER BY source_id""",
        )
    )


def raw_files(con: duckdb.DuckDBPyConnection) -> Finding:
    sql = "SELECT concat(key, ': ', reason) FROM skipped_raw ORDER BY key"
    return Finding(notes=_rows(con, sql))


CHECKS: list[Check] = [
    Check("final_has_score", "every final game has both scores", final_has_score),
    Check("no_duplicate_games", "no two games with the same teams on one date", no_duplicate_games),
    Check(
        "closing_line",
        f"every final FBS-vs-FBS game in {BACKTEST_SEASONS[0]}-{BACKTEST_SEASONS[1]} has a "
        "closing line or is marked as missing one",
        closing_line,
    ),
    Check(
        "advanced_stats",
        "every FBS team in a final game has advanced stats (in "
        f"{BACKTEST_SEASONS[0]}-{BACKTEST_SEASONS[1]}, or once a post-kickoff pull covers its "
        "week), unless a pull 7+ days after kickoff shows CFBD has none",
        advanced_stats,
    ),
    Check(
        "not_played",
        "games that won't be played (unscored and uncompleted 7+ days after their start, D-121)",
        not_played,
    ),
    Check("raw_files", "raw files skipped because their params don't match their key", raw_files),
]


def run(lake: Lake) -> Report:
    """Run every check on the staged tables in `lake`."""
    import pyarrow.parquet as pq

    present = set(lake.walk("staging"))
    missing = [staging_key(n) for n in TABLES if staging_key(n) not in present]
    if missing:
        raise StagingMissingError(
            f"{', '.join(missing)} not found: run `engine transform --rebuild` first."
        )
    con = connect()
    for name in TABLES:
        con.register(name, pq.read_table(io.BytesIO(lake.read(staging_key(name)))))
    return Report([(check, check.run(con)) for check in CHECKS])
