"""Publishing the staged lake to Postgres (TASK-020): idempotent upserts by (source, source_id),
append-only line snapshots, and a refusal on a failed data-quality check.

The publish tests write to the test DB through `db_conn` (rolled back); lines use
`source='cfbd'` there because `line_snapshots.source` is CHECKed. The CLI test only refuses, so it
commits nothing."""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

import pytest
from lake_fixture import FIXTURE, engine, staged, write
from sqlalchemy import Connection, text

from db.session import make_engine
from engine.ingest.lake import LocalLake
from engine.publish.lines import map_lines
from engine.publish.reference import insert_line_snapshots, upsert_games
from engine.publish.staging import DataQualityFailed, current_week, publish_lake
from engine.transform import rebuild

TABLES = ("teams", "venues", "games", "seasons", "sportsbooks", "line_snapshots")
GAMES_KEY = "raw/cfbd/games/season=2025/week=01/fetched_at=2025-09-02T120000Z.parquet"
BOTH_FBS = "401756847"  # Kansas-Fresno State, 2025-08-23T22:30Z
SOURCE = "pytest"  # reference rows the direct tests write; never 'cfbd' or 'fixture'


def _state(conn: Connection) -> dict[str, Any]:
    """Row counts of the six tables, plus the IDs of the rows a publish from 'cfbd' owns."""
    state: dict[str, Any] = {
        t: conn.execute(text(f"SELECT count(*) FROM {t}")).scalar_one() for t in TABLES
    }
    for t in ("teams", "venues", "games", "sportsbooks"):
        rows = conn.execute(text(f"SELECT source_id, id FROM {t} WHERE source = 'cfbd'"))
        state[f"{t}_ids"] = dict(rows.all())
    state["line_snapshot_ids"] = (
        conn.execute(text("SELECT id FROM line_snapshots WHERE source = 'cfbd' ORDER BY id"))
        .scalars()
        .all()
    )
    state["seasons_rows"] = conn.execute(
        text("SELECT year, source, start_date, end_date, weeks FROM seasons WHERE year = 2025")
    ).all()
    return state


def test_publish_twice_keeps_ids_and_counts(lake: LocalLake, db_conn: Connection) -> None:
    """AC-1."""
    rebuild(lake)
    before = _state(db_conn)

    first_new = publish_lake(lake, db_conn)
    first = _state(db_conn)
    second_new = publish_lake(lake, db_conn)
    second = _state(db_conn)

    assert second == first
    assert set(second_new.values()) == {0}

    lines = staged(lake, "lines").to_pylist()
    closing = sum(1 for r in lines if r["spread_home"] is not None or r["total"] is not None)
    opening = sum(
        1 for r in lines if r["spread_home_open"] is not None or r["total_open"] is not None
    )
    assert len(first["games_ids"]) == 5
    assert len(first["teams_ids"]) == 10
    assert len(first["venues_ids"]) == 5
    assert len(first["sportsbooks_ids"]) == len({r["provider"] for r in lines})
    # Every fixture pull came after kickoff: each priced row is one closing row, and each row
    # with an open is one opening row.
    assert len(first["line_snapshot_ids"]) == closing + opening
    assert first["line_snapshots"] - before["line_snapshots"] == closing + opening
    assert first_new["games"] == 5
    assert first_new["line_snapshots"] == closing + opening
    assert [r.year for r in first["seasons_rows"]] == [2025]


def test_publish_maps_staged_columns_by_meaning(lake: LocalLake, db_conn: Connection) -> None:
    """Classification is Postgres's division; CFBD's elevation is meters."""
    rebuild(lake)
    publish_lake(lake, db_conn)

    division = db_conn.execute(
        text(
            "SELECT ts.division FROM team_seasons ts JOIN teams t ON t.id = ts.team_id"
            " WHERE t.source = 'cfbd' AND t.source_id = '2305' AND ts.season = 2025"
        )
    ).scalar_one()
    assert division == "fbs"
    elevation = db_conn.execute(
        text("SELECT elevation_m FROM venues WHERE source = 'cfbd' AND source_id = '3833'")
    ).scalar_one()
    assert float(elevation) == 274.9


def _final_without_score(lake: LocalLake) -> None:
    games = FIXTURE[GAMES_KEY]["records"]
    good = next(g for g in games if str(g["id"]) == BOTH_FBS)
    bad = {**good, "id": 900000001, "homePoints": None, "startDate": "2025-08-30T19:00:00.000Z"}
    write(
        lake,
        "raw/cfbd/games/season=2025/week=01/fetched_at=2025-09-03T120000Z.parquet",
        [*games, bad],
        {"classification": "fbs", "seasonType": "regular", "week": 1, "year": 2025},
    )
    rebuild(lake)


def test_publish_lake_refuses_a_failed_check(lake: LocalLake, db_conn: Connection) -> None:
    """AC-2, in the caller's transaction: it raises before writing a row."""
    _final_without_score(lake)
    before = _state(db_conn)

    with pytest.raises(DataQualityFailed) as failed:
        publish_lake(lake, db_conn)

    assert "final_has_score" in failed.value.report.failures
    assert _state(db_conn) == before


def test_engine_publish_exits_1_on_a_failed_check(
    lake: LocalLake, test_db_url: str, capsys: pytest.CaptureFixture[str]
) -> None:
    """AC-2: `engine publish` exits non-zero and every table's row count is unchanged."""
    _final_without_score(lake)
    with make_engine(test_db_url).connect() as conn:
        before = _state(conn)
    capsys.readouterr()

    assert engine("publish", "--target", "test") == 1

    out = capsys.readouterr().out
    assert "FAIL final_has_score" in out
    assert "900000001" in out
    with make_engine(test_db_url).connect() as conn:
        assert _state(conn) == before


def _team(conn: Connection, source_id: str) -> int:
    return conn.execute(
        text(
            "INSERT INTO teams (sport_id, source, source_id, school)"
            " VALUES ('cfb', :s, :sid, :sid) RETURNING id"
        ),
        {"s": SOURCE, "sid": source_id},
    ).scalar_one()


def test_upsert_games_chunks_past_bind_limit(db_conn: Connection) -> None:
    """5,000 games x 16 columns is 80,000 binds, over Postgres's 65,535 in one statement."""
    home, away = _team(db_conn, "home"), _team(db_conn, "away")
    rows = [
        {
            "source_id": f"g{i}",
            "season": 2025,
            "week": 1,
            "season_type": "regular",
            "game_date": date(2025, 8, 30),
            "kickoff_at": None,
            "neutral_site": False,
            "conference_game": False,
            "venue_id": None,
            "home_team_id": home,
            "away_team_id": away,
            "home_points": None,
            "away_points": None,
            "status": "scheduled",
        }
        for i in range(5000)
    ]
    ids = upsert_games(db_conn, "cfb", SOURCE, rows)
    assert len(ids) == 5000
    assert upsert_games(db_conn, "cfb", SOURCE, rows) == ids


def test_insert_line_snapshots_twice_inserts_nothing(db_conn: Connection) -> None:
    home, away = _team(db_conn, "home"), _team(db_conn, "away")
    game = upsert_games(
        db_conn,
        "cfb",
        SOURCE,
        [
            {
                "source_id": "g1",
                "season": 2025,
                "week": 1,
                "season_type": "regular",
                "game_date": date(2025, 8, 30),
                "kickoff_at": None,
                "neutral_site": False,
                "conference_game": False,
                "venue_id": None,
                "home_team_id": home,
                "away_team_id": away,
                "home_points": None,
                "away_points": None,
                "status": "scheduled",
            }
        ],
    )["g1"]
    book = db_conn.execute(
        text(
            "INSERT INTO sportsbooks (source, source_id, name) VALUES (:s, 'b', 'B') RETURNING id"
        ),
        {"s": SOURCE},
    ).scalar_one()
    rows = [
        {"game_id": game, "book_id": book, "kind": kind, "captured_at": at, "spread_home": -3}
        for kind, at in (
            ("opening", None),
            ("closing", None),
            ("snapshot", datetime(2025, 8, 25, 12, tzinfo=UTC)),
            ("snapshot", datetime(2025, 8, 27, 12, tzinfo=UTC)),
        )
    ]
    assert insert_line_snapshots(db_conn, "manual", rows) == 4
    assert insert_line_snapshots(db_conn, "manual", rows) == 0
    count = db_conn.execute(
        text("SELECT count(*) FROM line_snapshots WHERE game_id = :g"), {"g": game}
    ).scalar_one()
    assert count == 4


# map_lines: which kind each staged pull becomes (rule A in the task's plan).

KICKOFF = datetime(2025, 8, 30, 19, tzinfo=UTC)


def _game(kickoff_at: datetime | None = KICKOFF) -> dict[str, Any]:
    return {"source_id": "g", "kickoff_at": kickoff_at, "game_date": date(2025, 8, 30)}


def _line(fetched_at: datetime, provider: str = "consensus", **prices: float | None) -> dict:
    values = {
        "spread_home": None,
        "spread_home_open": None,
        "total": None,
        "total_open": None,
        "ml_home": None,
        "ml_away": None,
    }
    return {
        "game_source_id": "g",
        "provider": provider,
        "fetched_at": fetched_at,
        **values,
        **prices,
    }


def _kinds(rows: list[dict]) -> list[tuple[str, datetime | None, float | None]]:
    return sorted(
        ((r["kind"], r["captured_at"], r["spread_home"]) for r in rows),
        key=lambda k: (k[0], k[1] or datetime.min.replace(tzinfo=UTC)),
    )


def test_pulls_before_kickoff_are_snapshots_and_after_one_closing() -> None:
    early = datetime(2025, 8, 25, 12, tzinfo=UTC)
    late = datetime(2025, 8, 29, 12, tzinfo=UTC)
    after = datetime(2025, 8, 31, 12, tzinfo=UTC)
    later = datetime(2025, 9, 2, 12, tzinfo=UTC)
    lines = [
        _line(early, spread_home=-3, spread_home_open=-2.5),
        _line(late, spread_home=-4, spread_home_open=-2.5),
        _line(after, spread_home=-4.5, spread_home_open=-2.5),
        _line(later, spread_home=-5, spread_home_open=-2),
    ]
    assert _kinds(map_lines(lines, [_game()])) == [
        ("closing", None, -4.5),
        ("opening", None, -2.5),
        ("snapshot", early, -3),
        ("snapshot", late, -4),
    ]


def test_an_unpriced_pull_is_skipped() -> None:
    assert map_lines([_line(datetime(2025, 8, 25, tzinfo=UTC))], [_game()]) == []


def test_tba_cutoff_is_the_end_of_the_eastern_date() -> None:
    # 23:30 ET on Aug 30 is before the cutoff; 00:30 ET on Aug 31 is after it.
    before = datetime(2025, 8, 31, 3, 30, tzinfo=UTC)
    after = datetime(2025, 8, 31, 4, 30, tzinfo=UTC)
    rows = map_lines(
        [_line(before, spread_home=-3), _line(after, spread_home=-4)], [_game(kickoff_at=None)]
    )
    assert _kinds(rows) == [("closing", None, -4), ("snapshot", before, -3)]


def test_opening_row_carries_the_open_and_closing_the_moneylines() -> None:
    after = datetime(2025, 8, 31, 12, tzinfo=UTC)
    rows = map_lines(
        [
            _line(
                after,
                spread_home=-4,
                spread_home_open=-3,
                total=50,
                total_open=52.5,
                ml_home=-180,
                ml_away=150,
            )
        ],
        [_game()],
    )
    by_kind = {r["kind"]: r for r in rows}
    assert (by_kind["opening"]["spread_home"], by_kind["opening"]["total"]) == (-3, 52.5)
    assert by_kind["opening"]["ml_home"] is None
    assert (by_kind["closing"]["total"], by_kind["closing"]["ml_home"]) == (50, -180)


# seasons.current_week: the regular week containing now, else NULL (gate E).

CALENDAR = [
    {
        "season_type": "regular",
        "week": 1,
        "start_at": datetime(2025, 8, 23, 7, tzinfo=UTC),
        "end_at": datetime(2025, 9, 2, 6, 59, tzinfo=UTC),
    },
    {
        "season_type": "regular",
        "week": 2,
        "start_at": datetime(2025, 9, 2, 7, tzinfo=UTC),
        "end_at": datetime(2025, 9, 8, 6, 59, tzinfo=UTC),
    },
    {
        "season_type": "postseason",
        "week": 1,
        "start_at": datetime(2025, 12, 13, 8, tzinfo=UTC),
        "end_at": datetime(2026, 1, 21, 7, 59, tzinfo=UTC),
    },
]


@pytest.mark.parametrize(
    ("now", "week"),
    [
        (datetime(2025, 9, 3, tzinfo=UTC), 2),
        (datetime(2025, 8, 23, 7, tzinfo=UTC), 1),
        (datetime(2025, 12, 20, tzinfo=UTC), None),
        (datetime(2026, 3, 1, tzinfo=UTC), None),
    ],
)
def test_current_week(now: datetime, week: int | None) -> None:
    assert current_week(CALENDAR, now) == week
