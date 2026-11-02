"""`engine pick` (TASK-045): a model run's predictions turned into spread picks against the newest
line before each game's cutoff, and re-evaluated when the line moves (D-140, D-142, D-148).

Teams and games are inserted under the throwaway sport `pytest` and the version under `cfb` with
a name no real version uses; every test rolls back (db_conn). The rules are a power spec's with
`display_shrinkage_k` tuned, so the stored `model_prob` (the displayed probability) differs from
the probability the pick rules read."""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from lake_fixture import engine
from sqlalchemy import Connection, event, text

from engine.core.interfaces import GameContext
from engine.core.picks import pick_game
from engine.core.probability import NormalMargin, blended_margin, cover_probability, expected_value
from engine.core.spec import ModelSpec
from engine.publish import picks
from engine.sports.cfb.teams import pickable

SPORT = "pytest"
NAME = "pytest-picks"
VERSION = "v1.0"
SEASON, WEEK = 2030, 6
SD = 14.0
NOW = datetime(2030, 10, 8, 12, tzinfo=UTC)  # the writer's clock: a Tuesday noon
KICKOFF = datetime(2030, 10, 12, 19, 30, tzinfo=UTC)  # that Saturday

_BASE = json.loads((Path(__file__).parents[1] / "specs" / "power-v1.json").read_text("utf-8"))
SPEC = ModelSpec.model_validate(
    {
        **_BASE,
        "picks": {
            "min_edge_pts": 3.0,
            "min_prob": 0.5,
            "market_shrinkage_k": 1.0,
            "display_shrinkage_k": {"tune": [0.5, 1.0]},
            "tiers": {"A": 9.0, "B": 6.0, "C": 4.0},
        },
    }
)
# What `engine rate` stores in the run's fitted_params: every tuned setting the season chose.
CHOICES = {path: values[0] for path, values in SPEC.tunables().items()}
RULES = SPEC.resolve(CHOICES).picks


# Rows


def _team(conn: Connection, source_id: str, division: str | None = "fbs") -> int:
    team_id = conn.execute(
        text(
            "INSERT INTO teams (sport_id, source, source_id, school)"
            " VALUES (:sport, 'pytest', :sid, :sid) RETURNING id"
        ),
        {"sport": SPORT, "sid": source_id},
    ).scalar_one()
    if division is not None:
        conn.execute(
            text("INSERT INTO team_seasons (team_id, season, division) VALUES (:t, :s, :d)"),
            {"t": team_id, "s": SEASON, "d": division},
        )
    return team_id


def _version(conn: Connection) -> int:
    return conn.execute(
        text(
            "INSERT INTO model_versions (sport_id, market, name, version, spec,"
            " spec_schema_version, created_by, status)"
            " VALUES ('cfb', 'spread', :name, :version, CAST(:spec AS jsonb), 1, 'system', 'dev')"
            " RETURNING id"
        ),
        {"name": NAME, "version": VERSION, "spec": json.dumps(SPEC.model_dump(mode="json"))},
    ).scalar_one()


def _run(
    conn: Connection,
    version_id: int,
    *,
    finished_at: datetime = NOW - timedelta(days=2),
    choices: dict[str, float] | None = None,
    status: str = "succeeded",
) -> int:
    chosen = CHOICES if choices is None else choices
    params = {"home_field": 3.0, "margin_sd": SD, "choices": chosen}
    return conn.execute(
        text(
            "INSERT INTO model_runs (model_version_id, run_type, season, week, as_of, status,"
            " started_at, finished_at, fitted_params)"
            " VALUES (:v, 'adhoc', :season, :week, :as_of, :status, :started, :finished,"
            " CAST(:params AS jsonb)) RETURNING id"
        ),
        {
            "v": version_id,
            "season": SEASON,
            "week": WEEK,
            "as_of": NOW - timedelta(days=3),
            "status": status,
            "started": finished_at - timedelta(minutes=5),
            "finished": finished_at,
            "params": json.dumps(params),
        },
    ).scalar_one()


def _game(
    conn: Connection,
    home: int,
    away: int,
    kickoff_at: datetime | None = KICKOFF,
    *,
    game_date: date | None = None,
) -> int:
    return conn.execute(
        text(
            "INSERT INTO games (sport_id, source, source_id, season, week, season_type, game_date,"
            " kickoff_at, neutral_site, conference_game, home_team_id, away_team_id, status)"
            " VALUES (:sport, 'pytest', :sid, :season, :week, 'regular', :d, :k, false, false,"
            " :h, :a, 'scheduled') RETURNING id"
        ),
        {
            "sport": SPORT,
            "sid": f"{home}-{away}",
            "season": SEASON,
            "week": WEEK,
            "d": game_date or (kickoff_at.date() if kickoff_at else None),
            "k": kickoff_at,
            "h": home,
            "a": away,
        },
    ).scalar_one()


def _book(conn: Connection, source_id: str) -> int:
    return conn.execute(
        text(
            "INSERT INTO sportsbooks (source, source_id, name) VALUES ('pytest', :sid, :sid)"
            " ON CONFLICT (source, source_id) DO UPDATE SET name = excluded.name RETURNING id"
        ),
        {"sid": source_id},
    ).scalar_one()


def _line(
    conn: Connection,
    game_id: int,
    book: str,
    captured_at: datetime | None,
    spread_home: float | None,
    *,
    kind: str = "snapshot",
    home_price: int | None = None,
    away_price: int | None = None,
    total: float | None = None,
) -> int:
    return conn.execute(
        text(
            "INSERT INTO line_snapshots (game_id, book_id, source, kind, captured_at, spread_home,"
            " total, spread_home_price, spread_away_price)"
            " VALUES (:g, :b, 'manual', :kind, :c, :s, :t, :hp, :ap) RETURNING id"
        ),
        {
            "g": game_id,
            "b": _book(conn, book),
            "kind": kind,
            "c": captured_at,
            "s": spread_home,
            "t": total,
            "hp": home_price,
            "ap": away_price,
        },
    ).scalar_one()


def _prediction(conn: Connection, run_id: int, version_id: int, game_id: int, margin: float) -> int:
    return conn.execute(
        text(
            "INSERT INTO predictions (model_run_id, model_version_id, game_id, pred_margin,"
            " home_win_prob, margin_sd) VALUES (:r, :v, :g, :m, 0.6, :sd) RETURNING id"
        ),
        {"r": run_id, "v": version_id, "g": game_id, "m": margin, "sd": SD},
    ).scalar_one()


def _rows(conn: Connection, version_id: int) -> list[Any]:
    return list(
        conn.execute(
            text("SELECT * FROM picks WHERE model_version_id = :v ORDER BY created_at, id"),
            {"v": version_id},
        ).all()
    )


def _current(conn: Connection, version_id: int, game_id: int) -> Any:
    return conn.execute(
        text("SELECT * FROM current_picks WHERE model_version_id = :v AND game_id = :g"),
        {"v": version_id, "g": game_id},
    ).one_or_none()


class World:
    """A version, its run for the week, and FBS teams to make games of."""

    def __init__(self, conn: Connection) -> None:
        conn.execute(
            text("INSERT INTO sports (id, name) VALUES (:s, 'pytest') ON CONFLICT DO NOTHING"),
            {"s": SPORT},
        )
        self.conn = conn
        self.version = _version(conn)
        self.run = _run(conn, self.version)
        self._teams = 0

    def team(self, division: str | None = "fbs") -> int:
        self._teams += 1
        return _team(self.conn, f"t{self._teams}", division)

    def game(self, margin: float, kickoff_at: datetime | None = KICKOFF, **kwargs: Any) -> int:
        game_id = _game(self.conn, self.team(), self.team(), kickoff_at, **kwargs)
        self.predict(game_id, margin)
        return game_id

    def predict(self, game_id: int, margin: float) -> int:
        return _prediction(self.conn, self.run, self.version, game_id, margin)

    def write(self, now: datetime = NOW) -> picks.PickSummary:
        return picks.write_picks(self.conn, self.version, SEASON, WEEK, now)


@pytest.fixture
def world(db_conn: Connection) -> World:
    return World(db_conn)


def _context(game_id: int) -> GameContext:
    return GameContext(
        game_id=game_id,
        season=SEASON,
        season_type="regular",
        week=WEEK,
        kickoff=KICKOFF,
        home_team=1,
        away_team=2,
        neutral_site=False,
        home_classification="fbs",
        away_classification="fbs",
    )


# AC-1: one spread pick per picked game, on the newest snapshot before its cutoff


def test_a_pick_is_written_at_the_newest_snapshot_before_the_cutoff(world: World) -> None:
    home = world.game(10.0)
    _line(world.conn, home, "DraftKings", NOW - timedelta(days=2), -3.0)
    newest = _line(world.conn, home, "DraftKings", NOW - timedelta(hours=1), -2.5, home_price=-105)
    _line(world.conn, home, "DraftKings", NOW + timedelta(hours=1), -9.0)  # after the clock
    away = world.game(-12.0)
    away_line = _line(
        world.conn, away, "DraftKings", NOW - timedelta(hours=1), 3.0, home_price=-120
    )

    summary = world.write()

    assert (summary.run_id, summary.picks, summary.passes) == (world.run, 2, 0)
    rows = {r.game_id: r for r in _rows(world.conn, world.version)}
    expected = ((home, newest, 10.0, -2.5, -105), (away, away_line, -12.0, 3.0, -110))
    for game_id, snapshot, margin, line, price in expected:
        made = pick_game(_context(game_id), margin, line, RULES, NormalMargin(SD), pickable)
        assert made is not None
        row = rows[game_id]
        assert (row.line_snapshot_id, row.market, float(row.line), row.price) == (
            snapshot,
            "spread",
            line,
            price,
        )
        assert (row.side, row.tier, row.edge_pts) == (made.side, made.tier, made.edge)
        assert row.model_prob == pytest.approx(made.prob)
        assert row.expected_value == pytest.approx(expected_value(made.prob, price))
        assert (row.stake_units, row.created_at) == (1.0, NOW)
        assert row.prediction_id is not None
    assert (rows[home].side, rows[home].tier, rows[home].edge_pts) == ("home", "B", 7.5)
    assert (rows[away].side, rows[away].tier, rows[away].edge_pts) == ("away", "A", -9.0)
    # Stored is the displayed probability (display k 0.5), not the one the rules read.
    raw = cover_probability(blended_margin(10.0, -2.5, 1.0), -2.5, NormalMargin(SD)).prob
    assert rows[home].model_prob < raw - 0.05


@pytest.mark.parametrize("division", ["fcs", None])
def test_a_game_with_an_fcs_team_gets_no_pick(world: World, division: str | None) -> None:
    """D-047: an edge past every threshold, and no row (FCS, or a team with no division)."""
    game_id = _game(world.conn, world.team(), world.team(division))
    world.predict(game_id, 30.0)
    _line(world.conn, game_id, "DraftKings", NOW - timedelta(hours=1), -3.0)

    assert world.write().picks == 0
    assert _rows(world.conn, world.version) == []


# AC-2: re-evaluation when the line moves, read through current_picks


@pytest.fixture
def picked(world: World) -> int:
    """Home by 10 against −3: an edge of 7, home in tier B, written at NOW."""
    game_id = world.game(10.0)
    _line(world.conn, game_id, "DraftKings", NOW - timedelta(hours=1), -3.0)
    world.write()
    return game_id


LATER = NOW + timedelta(hours=6)


def test_a_rerun_with_no_new_snapshot_inserts_nothing(world: World, picked: int) -> None:
    summary = world.write(LATER)

    assert (summary.picks, summary.passes) == (0, 0)
    assert len(_rows(world.conn, world.version)) == 1
    assert float(_current(world.conn, world.version, picked).line) == -3.0


@pytest.mark.parametrize(
    ("spread", "side", "tier"),
    [(-0.5, "home", "A"), (-14.0, "away", "C"), (-16.5, "away", "B")],
    ids=["tier-changes", "side-and-tier-change", "side-changes"],
)
def test_a_new_line_that_changes_the_side_or_tier_inserts_a_pick(
    world: World, picked: int, spread: float, side: str, tier: str
) -> None:
    moved = _line(world.conn, picked, "DraftKings", LATER - timedelta(hours=1), spread)

    assert world.write(LATER).picks == 1

    current = _current(world.conn, world.version, picked)
    assert (current.line_snapshot_id, float(current.line)) == (moved, spread)
    assert (current.side, current.tier, current.created_at) == (side, tier, LATER)
    assert len(_rows(world.conn, world.version)) == 2


def test_a_new_line_with_the_same_side_and_tier_inserts_nothing(world: World, picked: int) -> None:
    _line(world.conn, picked, "DraftKings", LATER - timedelta(hours=1), -3.5)  # edge 6.5: B

    assert world.write(LATER).picks == 0

    assert float(_current(world.conn, world.version, picked).line) == -3.0
    assert len(_rows(world.conn, world.version)) == 1


def test_a_pick_that_no_longer_qualifies_gets_a_pass_row(world: World, picked: int) -> None:
    moved = _line(world.conn, picked, "DraftKings", LATER - timedelta(hours=1), -8.0)  # edge 2

    summary = world.write(LATER)

    assert (summary.picks, summary.passes) == (0, 1)
    assert _current(world.conn, world.version, picked) is None
    passed = _rows(world.conn, world.version)[-1]
    assert (passed.side, passed.tier, passed.stake_units) == (None, None, 0.0)
    assert (passed.line_snapshot_id, float(passed.line), passed.edge_pts) == (moved, -8.0, 2.0)
    assert 0.5 < passed.model_prob < 0.6  # the home side the edge favours, as displayed


def test_a_picked_game_past_its_cutoff_gets_no_pass_row(world: World, picked: int) -> None:
    _line(world.conn, picked, "DraftKings", KICKOFF - timedelta(hours=1), -8.0)  # edge 2

    assert world.write(KICKOFF).passes == 0

    assert len(_rows(world.conn, world.version)) == 1
    assert _current(world.conn, world.version, picked).side == "home"


def test_a_game_never_picked_gets_no_pass_row(world: World) -> None:
    game_id = world.game(10.0)
    _line(world.conn, game_id, "DraftKings", NOW - timedelta(hours=1), -8.0)

    assert world.write().passes == 0
    assert _rows(world.conn, world.version) == []


# AC-3: nothing at or after a game's cutoff


def test_no_pick_is_written_for_a_game_at_or_after_its_cutoff(world: World) -> None:
    started = world.game(10.0, NOW - timedelta(minutes=1))
    to_play = world.game(10.0, NOW + timedelta(hours=2))
    # TBA: the cutoff is the end of game_date in Eastern time (04:00 UTC the next day in October).
    tba_past = world.game(10.0, None, game_date=date(2030, 10, 7))
    tba_to_play = world.game(10.0, None, game_date=date(2030, 10, 8))
    for game_id in (started, to_play, tba_past, tba_to_play):
        _line(world.conn, game_id, "DraftKings", NOW - timedelta(hours=1), -3.0)

    world.write()

    assert {r.game_id for r in _rows(world.conn, world.version)} == {to_play, tba_to_play}
    late = world.conn.execute(
        text(
            "SELECT count(*) FROM picks p JOIN games g ON g.id = p.game_id"
            " WHERE p.model_version_id = :v AND p.created_at >= coalesce(g.kickoff_at,"
            " (g.game_date + 1)::timestamp AT TIME ZONE 'America/New_York')"
        ),
        {"v": world.version},
    ).scalar_one()
    assert late == 0


# AC-4: the book a pick uses when the pull has no consensus quote (D-148)


@pytest.mark.parametrize(
    ("quotes", "chosen"),
    [
        ({"consensus": -3.0, "DraftKings": -2.5, "Bovada": -3.5}, "consensus"),
        ({"Bovada": -2.5, "DraftKings": -3.0, "Caesars": -3.5}, "DraftKings"),
        ({"consensus": None, "DraftKings": -3.0, "Bovada": -2.5}, "DraftKings"),
        ({"Caesars": -3.5, "Bovada": -2.5}, "Bovada"),
        ({"William Hill": -3.5, "Caesars": -3.0}, "Caesars"),
    ],
    ids=["consensus", "draftkings", "consensus-no-spread", "bovada", "by-name"],
)
def test_the_pick_uses_the_book_the_rule_settles(
    world: World, quotes: dict[str, float | None], chosen: str
) -> None:
    game_id = world.game(10.0)
    at = NOW - timedelta(hours=1)
    ids = {
        book: _line(world.conn, game_id, book, at, spread, total=55.5)
        for book, spread in quotes.items()
    }
    _line(world.conn, game_id, "Bovada", at - timedelta(days=1), -1.0)  # an older pull

    world.write()

    (row,) = _rows(world.conn, world.version)
    assert (row.line_snapshot_id, float(row.line)) == (ids[chosen], quotes[chosen])


def test_a_game_with_no_snapshot_before_its_cutoff_gets_no_pick(world: World) -> None:
    world.game(10.0)  # no line at all
    untimed = world.game(10.0)
    _line(world.conn, untimed, "DraftKings", None, -3.0, kind="opening")
    _line(world.conn, untimed, "DraftKings", None, -3.0, kind="closing")

    assert world.write().picks == 0
    assert _rows(world.conn, world.version) == []


# AC-5: insert-only, one transaction, refused under LIVE


def test_the_writer_never_updates_or_deletes_picks(world: World, picked: int) -> None:
    seen: list[str] = []

    def record(conn: Any, cursor: Any, statement: str, *args: Any) -> None:
        seen.append(statement)

    _line(world.conn, picked, "DraftKings", LATER - timedelta(hours=2), -0.5)  # a new pick
    _line(world.conn, picked, "DraftKings", LATER - timedelta(minutes=30), -8.0)  # then a pass
    event.listen(world.conn, "before_cursor_execute", record)
    try:
        world.write(LATER - timedelta(hours=1))
        world.write(LATER)
    finally:
        event.remove(world.conn, "before_cursor_execute", record)

    writes = [s for s in seen if re.search(r"\b(UPDATE|DELETE|TRUNCATE)\b", s, re.IGNORECASE)]
    assert writes == []
    assert sum(re.search(r"INSERT INTO picks\b", s) is not None for s in seen) == 2
    triggers = world.conn.execute(
        text(
            "SELECT tgname FROM pg_trigger WHERE tgrelid = 'picks'::regclass AND NOT tgisinternal"
            " ORDER BY tgname"
        )
    ).scalars()
    assert list(triggers) == ["picks_insert_only", "picks_no_truncate"]


def _savepoint_engine(conn: Connection) -> Any:
    """publish_picks' engine, its transaction a savepoint on the rolled-back test connection."""

    class _Engine:
        @contextmanager
        def begin(self) -> Iterator[Connection]:
            with conn.begin_nested():
                yield conn

    return _Engine()


def test_a_failure_partway_inserts_no_pick(world: World, monkeypatch: pytest.MonkeyPatch) -> None:
    for _ in range(2):
        game_id = world.game(10.0)
        _line(world.conn, game_id, "DraftKings", NOW - timedelta(hours=1), -3.0)
    insert = picks._insert
    calls: list[int] = []

    def fail_second(conn: Connection, row: dict[str, Any]) -> None:
        calls.append(row["game_id"])
        if len(calls) == 2:
            raise RuntimeError("the database went away")
        insert(conn, row)

    monkeypatch.setattr(picks, "_insert", fail_second)
    monkeypatch.setattr(picks, "make_engine", lambda url: _savepoint_engine(world.conn))

    with pytest.raises(RuntimeError, match="went away"):
        picks.publish_picks(
            "postgresql://test", name=NAME, version=VERSION, season=SEASON, week=WEEK, now=NOW
        )

    assert len(calls) == 2  # the first game's pick was inserted before the failure
    assert _rows(world.conn, world.version) == []


def test_publish_picks_writes_through_one_transaction(
    world: World, picked: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    opened: list[str] = []

    def make_engine(url: str) -> Any:
        opened.append(url)
        return _savepoint_engine(world.conn)

    monkeypatch.setattr(picks, "make_engine", make_engine)
    _line(world.conn, picked, "DraftKings", LATER - timedelta(hours=1), -0.5)

    summary = picks.publish_picks(
        "postgresql://test", name=NAME, version=VERSION, season=SEASON, week=WEEK, now=LATER
    )

    assert opened == ["postgresql://test"]
    assert (summary.run_id, summary.picks) == (world.run, 1)
    assert _current(world.conn, world.version, picked).tier == "A"


def _refuse_postgres(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("engine pick opened a database")

    monkeypatch.setattr(picks, "make_engine", refuse)


@pytest.mark.parametrize("target", ["dev", "test"])
def test_pick_refuses_under_live(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], target: str
) -> None:
    monkeypatch.setenv("LIVE", "true")
    _refuse_postgres(monkeypatch)

    code = engine("pick", "--season", "2030", "--week", "6", "--target", target, "--name", NAME)

    assert code == 2
    assert "LIVE" in capsys.readouterr().err


def test_pick_cli_writes_on_the_target_at_the_engine_clock(
    world: World,
    picked: int,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    opened: list[str] = []

    def make_engine(url: str) -> Any:
        opened.append(url)
        return _savepoint_engine(world.conn)

    monkeypatch.setattr(picks, "make_engine", make_engine)
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("FIXTURE_NOW", LATER.isoformat())
    monkeypatch.setenv("TEST_DATABASE_URL", "postgresql://test-host/cfb_test")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("DATABASE_URL_UNPOOLED", raising=False)
    monkeypatch.delenv("LIVE", raising=False)
    _line(world.conn, picked, "DraftKings", LATER - timedelta(hours=1), -14.0)

    code = engine("pick", "--season", "2030", "--week", "6", "--target", "test", "--name", NAME)

    assert code == 0, capsys.readouterr().err
    assert opened == ["postgresql://test-host/cfb_test"]
    assert "1 picks, 0 passes" in capsys.readouterr().out
    current = _current(world.conn, world.version, picked)
    assert (current.side, current.created_at) == ("away", LATER)


# Refusals: nothing to pick from


def test_a_week_with_no_succeeded_run_is_refused(db_conn: Connection) -> None:
    version_id = _version(db_conn)
    _run(db_conn, version_id, status="failed")

    with pytest.raises(picks.PicksRefused, match="no succeeded run"):
        picks.write_picks(db_conn, version_id, SEASON, WEEK, NOW)


def test_a_run_whose_choices_leave_a_pick_rule_unresolved_is_refused(db_conn: Connection) -> None:
    version_id = _version(db_conn)
    choices = {p: v for p, v in CHOICES.items() if p != "picks.display_shrinkage_k"}
    _run(db_conn, version_id, choices=choices)

    with pytest.raises(picks.PicksRefused, match="picks.display_shrinkage_k"):
        picks.write_picks(db_conn, version_id, SEASON, WEEK, NOW)


def test_the_newest_succeeded_run_is_the_one_picked_from(world: World) -> None:
    game_id = _game(world.conn, world.team(), world.team())
    world.predict(game_id, 10.0)
    newer = _run(world.conn, world.version, finished_at=NOW - timedelta(days=1))
    newest_prediction = _prediction(world.conn, newer, world.version, game_id, -12.0)
    _run(world.conn, world.version, finished_at=NOW - timedelta(hours=2), status="failed")
    _line(world.conn, game_id, "DraftKings", NOW - timedelta(hours=1), -3.0)

    summary = world.write()

    assert summary.run_id == newer
    (row,) = _rows(world.conn, world.version)
    assert (row.prediction_id, row.side) == (newest_prediction, "away")
