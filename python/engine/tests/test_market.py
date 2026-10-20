"""`closing_lines()` (TASK-021): each game's closing spread from the staged lake, by the rule the
`game_market` view uses (D-120), for notebook #1's benchmark and M3.4's baseline."""

from datetime import UTC, date, datetime, timedelta
from typing import Any

import pyarrow as pa
from lake_fixture import staged
from sqlalchemy import Connection, text

from engine.ingest.lake import LocalLake
from engine.publish.lines import map_lines, publish_lines
from engine.publish.reference import upsert_games
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


# closing_lines() against the game_market view itself, on the test DB (rolled back)


def _team(conn: Connection, source_id: str) -> int:
    return conn.execute(
        text(
            "INSERT INTO teams (sport_id, source, source_id, school)"
            " VALUES ('cfb', 'pytest', :sid, :sid) RETURNING id"
        ),
        {"sid": source_id},
    ).scalar_one()


def _pull(game: str, at: datetime, *books: tuple[str, float, float | None]) -> list[dict]:
    return [
        {
            "game_source_id": game,
            "provider": provider,
            "fetched_at": at,
            "spread_home": spread,
            "spread_home_open": None,
            "total": total,
            "total_open": None,
            "ml_home": None,
            "ml_away": None,
        }
        for provider, spread, total in books
    ]


def test_closing_lines_equal_game_market(db_conn: Connection) -> None:
    """The benchmark grades against the line the app shows: consensus, an even-count median,
    the last snapshot when there's no close, and a TBA kickoff's end-of-day cutoff."""
    home, away = _team(db_conn, "eq-home"), _team(db_conn, "eq-away")
    day = date(2025, 9, 6)
    games = {"eq-consensus": KICKOFF, "eq-median": KICKOFF, "eq-snapshot": KICKOFF, "eq-tba": None}
    before, after = KICKOFF - timedelta(hours=6), KICKOFF + timedelta(days=2)
    tba_before = datetime(2025, 9, 7, 3, 30, tzinfo=UTC)  # 23:30 Eastern on game day
    rows = [
        *_pull("eq-consensus", before, ("consensus", -3.0, 50.0), ("Bovada", -4.0, 51.0)),
        *_pull("eq-consensus", after, ("consensus", -3.5, 49.5), ("Bovada", -2.0, 48.0)),
        *_pull(
            "eq-median",
            after,
            ("A", -3.0, 40.0),
            ("B", -4.0, 41.0),
            ("C", -6.0, 44.0),
            ("D", -10.0, 51.0),  # mean -5.75 and 44.0, median -5.0 and 42.5
        ),
        *_pull("eq-snapshot", before - timedelta(days=1), ("A", -9.0, None)),
        *_pull("eq-snapshot", before, ("A", -6.0, 60.0), ("B", -5.0, 61.0)),
        *_pull("eq-tba", tba_before, ("A", 2.5, 55.0)),
        *_pull("eq-tba", tba_before + timedelta(days=1), ("A", 1.5, 54.0)),
    ]
    staged_games = [{"source_id": g, "kickoff_at": k, "game_date": day} for g, k in games.items()]
    ids = upsert_games(
        db_conn,
        "cfb",
        "pytest",
        [
            {
                **g,
                "season": 2025,
                "week": 2,
                "season_type": "regular",
                "neutral_site": False,
                "conference_game": False,
                "venue_id": None,
                "home_team_id": home,
                "away_team_id": away,
                "home_points": 21,
                "away_points": 14,
                "status": "final",
            }
            for g in staged_games
        ],
    )
    publish_lines(db_conn, "manual", map_lines(rows, staged_games), ids)

    expected = by_game(
        closing_lines(
            pa.Table.from_pylist(staged_games), pa.Table.from_pylist(rows), at=datetime.now(UTC)
        )
    )
    view = db_conn.execute(
        text(
            "SELECT g.source_id, m.closing_spread_home, m.closing_total, m.closing_source,"
            " m.closing_from FROM game_market m JOIN games g ON g.id = m.game_id"
            " WHERE g.id = ANY(:ids)"
        ),
        {"ids": list(ids.values())},
    ).all()

    actual = {
        sid: (float(spread), float(total), source, closing_from)
        for sid, spread, total, source, closing_from in view
    }
    assert actual == {
        g: (r["spread_home"], r["total"], r["source"], r["closing_from"])
        for g, r in expected.items()
    }
    assert actual["eq-consensus"] == (-3.5, 49.5, "consensus", "cfbd_close")
    assert actual["eq-median"] == (-5.0, 42.5, "median", "cfbd_close")
    assert actual["eq-snapshot"] == (-5.5, 60.5, "median", "last_snapshot")
    assert actual["eq-tba"] == (1.5, 54.0, "median", "cfbd_close")
