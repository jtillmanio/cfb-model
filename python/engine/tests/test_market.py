"""`closing_lines()` (TASK-021): each game's closing spread from the staged lake, by the rule the
`game_market` view uses (D-120), for notebook #1's benchmark and M3.4's baseline."""

from datetime import UTC, date, datetime, timedelta
from typing import Any

import pyarrow as pa
from lake_fixture import staged

from engine.ingest.lake import LocalLake
from engine.transform import rebuild
from engine.transform.market import closing_lines

KANSAS_FRESNO = "401756847"  # DraftKings -14, ESPN Bet -14.5, Bovada -14, pulled after kickoff
KICKOFF = datetime(2025, 9, 6, 19, 30, tzinfo=UTC)


def by_game(table: pa.Table) -> dict[str, dict[str, Any]]:
    return {row["game_source_id"]: row for row in table.to_pylist()}


def test_closing_lines_median_on_fixture(lake: LocalLake) -> None:
    rebuild(lake)

    closing = by_game(closing_lines(staged(lake, "games"), staged(lake, "lines")))

    kansas = closing[KANSAS_FRESNO]
    assert (kansas["spread_home"], kansas["source"]) == (-14.0, "median")  # the mean is -14.17
    assert kansas["closing_from"] == "cfbd_close"
    assert closing["401756846"]["spread_home"] == -3.0  # Kansas State-Iowa State


def game(kickoff_at: datetime | None = KICKOFF, game_date: date = date(2025, 9, 6)) -> pa.Table:
    return pa.table({"source_id": ["1"], "kickoff_at": [kickoff_at], "game_date": [game_date]})


def lines(*rows: tuple[str, datetime, float | None]) -> pa.Table:
    return pa.table(
        {
            "game_source_id": ["1"] * len(rows),
            "provider": [p for p, _, _ in rows],
            "fetched_at": [at for _, at, _ in rows],
            "spread_home": pa.array([s for _, _, s in rows], pa.float64()),
            "spread_home_open": pa.array([None] * len(rows), pa.float64()),
            "total": pa.array([None] * len(rows), pa.float64()),
            "total_open": pa.array([None] * len(rows), pa.float64()),
            "ml_home": pa.array([None] * len(rows), pa.int32()),
            "ml_away": pa.array([None] * len(rows), pa.int32()),
        }
    )


def test_consensus_wins_over_the_median() -> None:
    after = KICKOFF + timedelta(days=2)
    table = lines(("consensus", after, -3.5), ("Bovada", after, -3.0), ("DraftKings", after, -2.0))

    (row,) = closing_lines(game(), table).to_pylist()

    assert (row["spread_home"], row["source"]) == (-3.5, "consensus")


def test_without_a_close_the_last_snapshot_before_kickoff() -> None:
    table = lines(
        ("Bovada", KICKOFF - timedelta(days=3), -7.0),
        ("Bovada", KICKOFF - timedelta(hours=5), -6.0),
        ("DraftKings", KICKOFF - timedelta(hours=5), -5.0),
    )

    (row,) = closing_lines(game(), table, at=KICKOFF + timedelta(days=1)).to_pylist()

    assert (row["spread_home"], row["closing_from"]) == (-5.5, "last_snapshot")


def test_no_closing_line_before_the_cutoff() -> None:
    table = lines(("Bovada", KICKOFF - timedelta(hours=5), -6.0))
    tba = game(kickoff_at=None)  # cutoff: the end of 2025-09-06 Eastern, 04:00Z on the 7th

    assert closing_lines(tba, table, at=datetime(2025, 9, 7, 3, 59, tzinfo=UTC)).num_rows == 0
    assert closing_lines(tba, table, at=datetime(2025, 9, 7, 4, tzinfo=UTC)).num_rows == 1
