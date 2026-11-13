"""The NFL schedule, scores and lines from nflverse (TASK-069, D-039): the pull into the raw lake,
the staged games and lines, the publish under `sport_id 'nfl'`, and the `lines` job's NFL step.

`fixtures/nflverse/games.csv` is a slice of the real `games.csv` recorded on 2026-11-13: two 2025
games (one a wild-card game), four 2026 week-6 games (final), four week-10 games (priced, still to
play) and two week-12 games (no line yet). nflverse is served by an httpx.MockTransport; the
conftest's autouse fixture serves the same file to any pull without its own client.
"""

from __future__ import annotations

import csv
import io
import json
from collections.abc import Sequence
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import httpx
import pyarrow.parquet as pq
import pytest
from lake_fixture import engine
from sqlalchemy import Connection, text

# The job tests' CFBD fake, scratch Postgres and lake (imported fixtures register here too).
from test_jobs import Published, fake_postgres, live, publish_into, r2, serve, unplayed

from engine import jobs
from engine.ingest import backfill, nflverse
from engine.ingest.lake import LocalLake, decode_raw
from engine.publish.nfl import publish_nfl
from engine.publish.staging import publish_lake
from engine.transform import rebuild, staging_key
from engine.transform.nfl import stage

__all__ = ["r2"]  # a fixture the job tests below use

RECORDED = (Path(__file__).parent / "fixtures" / "nflverse" / "games.csv").read_text("utf-8")
GAMES_2026 = [
    "2026_06_SEA_DEN",
    "2026_06_HOU_JAX",
    "2026_06_TEN_IND",
    "2026_06_BUF_LV",
    "2026_10_NE_DET",
    "2026_10_BUF_NYJ",
    "2026_10_LAC_BAL",
    "2026_12_GB_LA",
    "2026_12_PHI_DAL",
]
BEFORE = "2026-10-17T12:00:00Z"  # the Saturday before week 6's Sunday games
AFTER = "2026-10-19T12:00:00Z"  # the Monday morning after them
LATER = "2026-10-20T12:00:00Z"


def at(monkeypatch: pytest.MonkeyPatch, when: str) -> None:
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("FIXTURE_NOW", when)


def ts(when: str) -> datetime:
    return datetime.fromisoformat(when).astimezone(UTC)


def rows(text_: str) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(text_)))


def csv_with(changes: dict[str, dict[str, str]], extra: Sequence[dict[str, str]] = ()) -> str:
    """The recorded file with some games' values changed and rows added."""
    table = rows(RECORDED) + list(extra)
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=list(table[0]), lineterminator="\n")
    writer.writeheader()
    for row in table:
        writer.writerow({**row, **changes.get(row["game_id"], {})})
    return out.getvalue()


class Served:
    """An httpx client serving `body` (text, or a status code to fail with); counts requests."""

    def __init__(self, body: str | int) -> None:
        self.requests = 0

        def handler(request: httpx.Request) -> httpx.Response:
            assert str(request.url) == nflverse.URL
            self.requests += 1
            if isinstance(body, int):
                return httpx.Response(body, text="unavailable")
            return httpx.Response(200, text=body)

        self.client = httpx.Client(transport=httpx.MockTransport(handler))


def pull(lake: LocalLake, monkeypatch: pytest.MonkeyPatch, when: str, body: str = RECORDED) -> str:
    at(monkeypatch, when)
    key = nflverse.pull(lake, 2026, Served(body).client)
    assert key is not None
    return key


# ─── AC-1: the raw lake ────────────────────────────────────────────────────────────────────────


def test_a_pull_saves_the_seasons_rows_as_a_new_raw_file(
    empty_lake: LocalLake, monkeypatch: pytest.MonkeyPatch
) -> None:
    key = pull(empty_lake, monkeypatch, BEFORE)

    assert key == "raw/nflverse/games/season=2026/fetched_at=2026-10-17T120000Z.parquet"
    # Each 2026 row exactly as the file gives it; 2025's left out.
    assert decode_raw(empty_lake.read(key)) == [r for r in rows(RECORDED) if r["season"] == "2026"]
    params = pq.read_table(io.BytesIO(empty_lake.read(key))).column("params").to_pylist()
    assert {json.loads(p)["season"] for p in params} == {2026}


def test_a_second_pull_adds_a_second_file_and_keeps_the_first(
    empty_lake: LocalLake, monkeypatch: pytest.MonkeyPatch
) -> None:
    first = pull(empty_lake, monkeypatch, BEFORE)
    saved = empty_lake.read(first)
    moved = csv_with({"2026_10_LAC_BAL": {"spread_line": "5"}})
    second = pull(empty_lake, monkeypatch, AFTER, moved)

    assert empty_lake.walk("raw/nflverse") == [first, second]
    assert empty_lake.read(first) == saved


def test_rebuild_stages_every_2026_game_from_the_raw_files_alone(
    lake: LocalLake, monkeypatch: pytest.MonkeyPatch
) -> None:
    pull(lake, monkeypatch, BEFORE)
    pull(lake, monkeypatch, AFTER)

    def no_network(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("transform --rebuild made a network call")

    monkeypatch.setattr(httpx.Client, "send", no_network)
    counts = rebuild(lake)

    staged = pq.read_table(io.BytesIO(lake.read(staging_key("nfl_games")))).to_pylist()
    assert sorted(g["source_id"] for g in staged) == sorted(GAMES_2026)
    assert counts["nfl_games"] == len(GAMES_2026)
    assert counts["games"] > 0  # the CFB fixture is staged beside it


def test_a_finished_season_isnt_downloaded_again(
    empty_lake: LocalLake, monkeypatch: pytest.MonkeyPatch
) -> None:
    (wild_card,) = [r for r in rows(RECORDED) if r["game_id"] == "2025_19_BUF_JAX"]
    super_bowl = {**wild_card, "game_id": "2025_22_SEA_NE", "game_type": "SB", "week": "22"}
    served = Served(csv_with({}, [super_bowl]))
    at(monkeypatch, "2026-03-01T12:00:00Z")

    assert nflverse.pull(empty_lake, 2025, served.client) is not None
    assert nflverse.pull(empty_lake, 2025, served.client) is None
    assert served.requests == 1


def test_a_season_without_its_super_bowl_is_pulled_again(
    empty_lake: LocalLake, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Every 2025 game in the file is scored, but the bracket isn't done."""
    served = Served(RECORDED)
    at(monkeypatch, "2026-01-12T12:00:00Z")
    nflverse.pull(empty_lake, 2025, served.client)
    at(monkeypatch, "2026-01-13T12:00:00Z")
    nflverse.pull(empty_lake, 2025, served.client)
    assert served.requests == 2


def test_a_file_without_a_needed_column_is_refused(
    empty_lake: LocalLake, monkeypatch: pytest.MonkeyPatch
) -> None:
    renamed = RECORDED.replace("spread_line", "spread", 1)
    with pytest.raises(ValueError, match="lacks spread_line"):
        pull(empty_lake, monkeypatch, BEFORE, renamed)
    assert empty_lake.walk("raw/nflverse") == []


# ─── AC-2: games and teams ─────────────────────────────────────────────────────────────────────


def published(conn: Connection, lake: LocalLake) -> dict[str, int]:
    staged = stage(lake)
    return publish_nfl(conn, staged["nfl_games"], staged["nfl_lines"], staged["nfl_venues"])


GAME = text(
    "SELECT g.id, g.sport_id, g.season, g.week, g.season_type, g.game_date, g.kickoff_at,"
    " g.neutral_site, g.status, g.home_points, g.away_points, h.abbreviation AS home,"
    " a.abbreviation AS away, h.school AS home_school, h.sport_id AS team_sport, v.name AS venue"
    " FROM games g JOIN teams h ON h.id = g.home_team_id JOIN teams a ON a.id = g.away_team_id"
    " LEFT JOIN venues v ON v.id = g.venue_id"
    " WHERE g.source = 'nflverse' AND g.source_id = :id"
)


def game(conn: Connection, source_id: str) -> Any:
    return conn.execute(GAME, {"id": source_id}).one()


def cfb_rows(conn: Connection) -> list[Any]:
    return [
        *conn.execute(text("SELECT * FROM games WHERE sport_id = 'cfb' ORDER BY id")).all(),
        *conn.execute(text("SELECT * FROM teams WHERE sport_id = 'cfb' ORDER BY id")).all(),
    ]


def test_publishing_upserts_nfl_games_by_source_id(
    db_conn: Connection, empty_lake: LocalLake, monkeypatch: pytest.MonkeyPatch
) -> None:
    pull(empty_lake, monkeypatch, AFTER)
    cfb = cfb_rows(db_conn)

    new = published(db_conn, empty_lake)

    assert new["games"] == len(GAMES_2026)
    final = game(db_conn, "2026_06_TEN_IND")  # Sun 2026-10-18 1:00 PM EDT, TEN 26 at IND 20
    assert (final.sport_id, final.season, final.week, final.season_type) == (
        "nfl", 2026, 6, "regular",
    )  # fmt: skip
    assert final.game_date == date(2026, 10, 18)
    assert final.kickoff_at == datetime(2026, 10, 18, 17, 0, tzinfo=UTC)
    assert (final.status, final.home_points, final.away_points) == ("final", 20, 26)
    assert (final.home, final.away, final.home_school, final.team_sport) == (
        "IND", "TEN", "Indianapolis", "nfl",
    )  # fmt: skip
    assert final.venue == "Lucas Oil Stadium"
    london = game(db_conn, "2026_06_HOU_JAX")  # 9:30 AM EDT at Wembley
    assert london.kickoff_at == datetime(2026, 10, 18, 13, 30, tzinfo=UTC)
    assert london.neutral_site is True
    coming = game(db_conn, "2026_10_LAC_BAL")  # Mon 2026-11-16 8:15 PM EST
    assert (coming.status, coming.home_points, coming.away_points) == ("scheduled", None, None)
    assert (coming.game_date, coming.kickoff_at) == (
        date(2026, 11, 16), datetime(2026, 11, 17, 1, 15, tzinfo=UTC),
    )  # fmt: skip

    ids = dict(
        db_conn.execute(text("SELECT source_id, id FROM games WHERE source = 'nflverse'")).all()
    )
    again = published(db_conn, empty_lake)

    assert again == {t: 0 for t in again}
    assert ids == dict(
        db_conn.execute(text("SELECT source_id, id FROM games WHERE source = 'nflverse'")).all()
    )
    assert cfb_rows(db_conn) == cfb


def test_postseason_types_and_unknown_kickoffs(
    db_conn: Connection, empty_lake: LocalLake, monkeypatch: pytest.MonkeyPatch
) -> None:
    at(monkeypatch, "2026-01-12T12:00:00Z")
    nflverse.pull(empty_lake, 2025, Served(csv_with({"2025_06_PHI_NYG": {"gametime": ""}})).client)
    published(db_conn, empty_lake)

    wild_card = game(db_conn, "2025_19_BUF_JAX")
    assert (wild_card.season_type, wild_card.week) == ("postseason", 19)
    unknown = game(db_conn, "2025_06_PHI_NYG")
    assert (unknown.game_date, unknown.kickoff_at) == (date(2025, 10, 9), None)


def test_engine_publish_takes_the_nfl_rows_with_cfbs(
    db_conn: Connection, lake: LocalLake, monkeypatch: pytest.MonkeyPatch
) -> None:
    pull(lake, monkeypatch, BEFORE)
    rebuild(lake)

    new = publish_lake(lake, db_conn)

    assert new["games"] > 0  # the CFB fixture's
    assert new["nfl_games"] == len(GAMES_2026)
    assert new["nfl_line_snapshots"] == 7  # week 6 and week 10 priced; week 12 not yet
    assert game(db_conn, "2026_06_BUF_LV").sport_id == "nfl"


def test_a_malformed_row_is_left_out_and_never_fails_the_publish(
    db_conn: Connection, lake: LocalLake, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A row missing what a game needs is listed in skipped_raw, not published, so the CFB rows
    published in the same transaction never roll back over it (TASK-069 review)."""
    broken = {
        "2026_06_SEA_DEN": {"gameday": ""},
        "2026_06_TEN_IND": {"week": "six"},
        "2026_06_BUF_LV": {"spread_line": "n/a", "home_score": "x"},
    }
    pull(lake, monkeypatch, BEFORE, csv_with(broken))
    rebuild(lake)

    skipped = pq.read_table(io.BytesIO(lake.read(staging_key("skipped_raw")))).to_pylist()
    reasons = sorted(r["reason"] for r in skipped)
    assert len(reasons) == 2
    assert "nflverse game 2026_06_SEA_DEN lacks" in reasons[0]
    assert "nflverse game 2026_06_TEN_IND lacks" in reasons[1]

    new = publish_lake(lake, db_conn)

    assert new["games"] > 0
    assert new["nfl_games"] == len(GAMES_2026) - 2
    # An unreadable score is unknown, so the game isn't final; an unreadable spread isn't stored.
    assert game(db_conn, "2026_06_BUF_LV").status == "scheduled"
    spreads = [r.spread_home for r in db_conn.execute(LINES, {"id": "2026_06_BUF_LV"})]
    assert spreads == [None]  # the pull still quotes a total and moneylines


def test_ingest_target_is_nflverses_alone(empty_lake: LocalLake) -> None:
    assert engine("ingest", "games", "--season", "2026", "--target", "test") == 2


# ─── AC-3: lines ───────────────────────────────────────────────────────────────────────────────


LINES = text(
    "SELECT ls.kind, ls.captured_at, ls.spread_home, ls.total, ls.ml_home, ls.ml_away,"
    " b.source AS book_source, b.source_id AS book"
    " FROM line_snapshots ls JOIN games g ON g.id = ls.game_id"
    " JOIN sportsbooks b ON b.id = ls.book_id"
    " WHERE g.source = 'nflverse' AND g.source_id = :id AND ls.source = 'nflverse'"
    " ORDER BY ls.kind, ls.captured_at"
)


def test_spread_home_is_the_negative_of_nflverses_spread_line(
    db_conn: Connection, empty_lake: LocalLake, monkeypatch: pytest.MonkeyPatch
) -> None:
    pull(empty_lake, monkeypatch, BEFORE)
    published(db_conn, empty_lake)

    # Baltimore at home, spread_line 4.5: home favored by 4.5.
    (line,) = db_conn.execute(LINES, {"id": "2026_10_LAC_BAL"}).all()
    assert (line.kind, line.captured_at) == ("snapshot", ts(BEFORE))
    assert line.spread_home == Decimal("-4.5")
    assert (line.book_source, line.book) == ("nflverse", "nflverse")
    # Buffalo away, spread_line -8.5: the Jets get 8.5.
    (line,) = db_conn.execute(LINES, {"id": "2026_10_BUF_NYJ"}).all()
    assert line.spread_home == Decimal("8.5")


def test_the_first_pull_after_kickoff_is_the_closing_line(
    db_conn: Connection, empty_lake: LocalLake, monkeypatch: pytest.MonkeyPatch
) -> None:
    unplayed_ = {"home_score": "", "away_score": "", "spread_line": "6.5"}
    pull(empty_lake, monkeypatch, BEFORE, csv_with({"2026_06_TEN_IND": unplayed_}))
    pull(empty_lake, monkeypatch, AFTER, csv_with({"2026_06_TEN_IND": {"spread_line": "7"}}))
    pull(empty_lake, monkeypatch, LATER, csv_with({"2026_06_TEN_IND": {"spread_line": "7.5"}}))
    published(db_conn, empty_lake)

    lines = [tuple(r[:3]) for r in db_conn.execute(LINES, {"id": "2026_06_TEN_IND"})]
    assert lines == [("closing", None, Decimal("-7.0")), ("snapshot", ts(BEFORE), Decimal("-6.5"))]
    market = db_conn.execute(
        text(
            "SELECT opening_spread_home, current_spread_home, closing_spread_home, closing_from"
            " FROM game_market WHERE game_id = :id"
        ),
        {"id": game(db_conn, "2026_06_TEN_IND").id},
    ).one()
    assert tuple(market) == (Decimal("-6.5"), Decimal("-6.5"), Decimal("-7.0"), "cfbd_close")


# ─── AC-4: the lines job ───────────────────────────────────────────────────────────────────────


THURSDAY = "2025-08-21T23:00:00Z"  # 19:00 ET before the CFB fixture's week 1


def test_the_lines_job_pulls_and_publishes_the_nfl_season(
    r2: LocalLake, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, db_conn: Connection
) -> None:
    monkeypatch.setenv("FIXTURE_NOW", THURSDAY)
    serve(r2, monkeypatch, unplayed)
    publish_into(monkeypatch, db_conn)
    live(monkeypatch)
    summary = tmp_path / "summary.md"

    assert engine("job", "lines", "--target", "live", "--summary", str(summary)) == 0

    assert [k.rsplit("/", 1)[0] for k in r2.walk("raw/nflverse")] == [
        "raw/nflverse/games/season=2025"
    ]
    # The recorded file's two 2025 games, each priced before kickoff.
    assert "- NFL (nflverse): 2 games staged; new: 2 games, 2 line rows" in summary.read_text(
        "utf-8"
    )
    assert game(db_conn, "2025_19_BUF_JAX").sport_id == "nfl"


def test_a_failed_nflverse_download_still_publishes_and_exits_1(
    r2: LocalLake, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("FIXTURE_NOW", THURSDAY)
    requests = serve(r2, monkeypatch, unplayed)
    monkeypatch.setattr(nflverse, "_client", lambda: Served(503).client)
    published_ = Published()
    fake_postgres(monkeypatch, published_)
    live(monkeypatch)
    summary = tmp_path / "summary.md"

    assert engine("job", "lines", "--target", "live", "--summary", str(summary)) == 1

    assert requests == ["games week=None", "games week=1", "lines week=1"]
    assert published_.steps == ["begin", "publish", "commit", "begin", "reevaluate", "commit"]
    text_ = summary.read_text("utf-8")
    assert "**NFL (nflverse) download failed:** HTTPStatusError" in text_
    assert "503" in text_
    assert r2.walk("raw/nflverse") == []


def test_the_failure_is_raised_after_the_publish(
    r2: LocalLake, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FIXTURE_NOW", THURSDAY)
    serve(r2, monkeypatch, unplayed)
    monkeypatch.setattr(nflverse, "_client", lambda: Served(503).client)
    published_ = Published()
    fake_postgres(monkeypatch, published_)
    live(monkeypatch)
    summary = jobs.Summary("lines", 2025, "live")

    client = backfill.client_for(r2)  # the CFBD fake `serve` set up

    with pytest.raises(jobs.NflverseFailed):
        jobs.run("lines", r2, "postgresql://unused", target="live", client=client, summary=summary)
    assert "publish" in published_.steps
    assert summary.nfl_error is not None
