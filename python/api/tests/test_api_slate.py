"""This Week's endpoint (TASK-055): every game of a week with its market, the model's line, edge,
cover and win probability, the current pick and how it's doing, the week's counts and the
version's pick rules, plus the shell block.

The route tests read the fixture CI loads before pytest (`pnpm db:seed`, D-089) at a fixture time
(FIXTURE_NOW, honored with APP_ENV=test). Expected values come from the views and from
`engine.core` called directly on the fixture's rows, so the endpoint can't agree with itself
only. The `load` tests build rows under model_rows' throwaway sport inside db_conn's rolled-back
transaction."""

from __future__ import annotations

import json
import threading
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import model_rows as m  # pyright: ignore[reportMissingImports]  (on sys.path via conftest)
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Connection, event, text

from api import slate, wave
from engine.core import ModelSpec, NormalMargin, blended_margin, displayed_prob

MakeToken = Callable[..., str]

SLATE_NOW = "2026-10-10T14:15:00-04:00"  # Sat 2:15 PM ET, the slate's fixture time
THURSDAY_NOON = "2026-10-08T12:00:00-04:00"  # before Thursday's 9:02 PM ET pull
OFFSEASON_NOW = "2027-02-08T06:00:00-05:00"  # Mon 6:00 AM ET, no game still to come

SEEDED_V1 = (
    "SELECT id FROM model_versions WHERE sport_id = 'cfb' AND market = 'spread'"
    " AND name = 'power' AND version = 'v1.0' AND deleted_at IS NULL"
)


def _get(
    client: TestClient,
    make_token: MakeToken,
    monkeypatch: pytest.MonkeyPatch,
    at: str = SLATE_NOW,
    query: str = "",
) -> dict[str, Any]:
    monkeypatch.setenv("FIXTURE_NOW", at)
    response = client.get(
        f"/api/py/slate{query}", headers={"Authorization": f"Bearer {make_token()}"}
    )
    assert response.status_code == 200, response.text
    return response.json()


def _game(body: dict[str, Any], away: str, home: str) -> dict[str, Any]:
    (found,) = [
        g for g in body["games"]
        if (g["away"]["abbreviation"], g["home"]["abbreviation"]) == (away, home)
    ]  # fmt: skip
    return found


def _v1_rules(conn: Connection) -> Any:
    spec = conn.execute(text(f"SELECT spec FROM model_versions WHERE id = ({SEEDED_V1})"))
    return ModelSpec.model_validate(spec.scalar_one()).picks


def _game_id(conn: Connection, source_id: str) -> int:
    return conn.execute(
        text("SELECT id FROM games WHERE source = 'fixture' AND source_id = :s"), {"s": source_id}
    ).scalar_one()


# AC-1


def test_the_fixture_slate_at_the_slate_time(
    client: TestClient, make_token: MakeToken, monkeypatch: pytest.MonkeyPatch, db_conn: Connection
):
    body = _get(client, make_token, monkeypatch)

    assert (body["season"], body["season_type"], body["week"]) == (2026, "regular", 6)
    assert body["offseason"] is False
    assert body["counts"] == {"games": 54, "picks": 9}
    assert len(body["games"]) == 54
    assert sum(g["pick"] is not None for g in body["games"]) == 9

    rules = _v1_rules(db_conn)
    assert body["rules"] == {
        "min_edge_pts": rules.min_edge_pts,
        "min_prob": rules.min_prob,
        "tiers": {"A": rules.tiers.A, "B": rules.tiers.B, "C": rules.tiers.C},
    }
    assert body["rules"]["min_edge_pts"] == 2.5 and body["rules"]["tiers"]["B"] == 3.5

    # TASK-053's block, the same one /teams carries.
    teams = client.get("/api/py/teams", headers={"Authorization": f"Bearer {make_token()}"})
    assert body["shell"] == teams.json()["shell"]
    assert (body["shell"]["week"], body["shell"]["picks"]) == (6, 9)


def test_games_come_in_kickoff_order(
    client: TestClient, make_token: MakeToken, monkeypatch: pytest.MonkeyPatch
):
    kickoffs = [g["kickoff_at"] for g in _get(client, make_token, monkeypatch)["games"]]
    assert kickoffs == sorted(kickoffs)
    assert _get(client, make_token, monkeypatch)["games"][0]["away"]["abbreviation"] == "TULN"


# AC-2


def test_purdue_at_ohio_state(
    client: TestClient, make_token: MakeToken, monkeypatch: pytest.MonkeyPatch, db_conn: Connection
):
    game = _game(_get(client, make_token, monkeypatch), "PUR", "OSU")

    market = db_conn.execute(
        text(
            "SELECT opening_spread_home, current_spread_home FROM game_market WHERE game_id = :g"
        ),
        {"g": _game_id(db_conn, "2026-w6-pur-osu")},
    ).one()
    assert game["market"]["opening_spread_home"] == float(market.opening_spread_home) == -28
    assert game["market"]["current_spread_home"] == float(market.current_spread_home) == -27.5
    assert game["market"]["snapshots"] == [
        {"captured_at": "2026-10-04T10:00:00Z", "spread_home": -28.0},
        {"captured_at": "2026-10-09T01:02:00Z", "spread_home": -27.5},
    ]

    rules = _v1_rules(db_conn)
    model = game["model"]
    assert model["pred_margin"] == 31.2
    assert model["home_win_prob"] == 0.99  # Ohio State's
    k = float(rules.market_shrinkage_k)  # pyright: ignore[reportArgumentType]
    assert model["edge"] == pytest.approx(blended_margin(31.2, -27.5, k) - 27.5)
    assert model["edge"] == pytest.approx(3.7)
    assert model["side"] == "home"
    expected = displayed_prob(31.2, -27.5, "home", rules, NormalMargin(13.8))
    assert model["cover_prob"] == pytest.approx(expected)
    assert model["cover_prob"] == pytest.approx(0.6057, abs=1e-4)  # the pick's stored model_prob

    pick = game["pick"]
    assert (pick["side"], pick["tier"], pick["line"]) == ("home", "B", -27.5)
    assert pick["edge"] == pytest.approx(3.7)
    assert pick["cover_prob"] == pytest.approx(model["cover_prob"], abs=1e-4)


def test_kansas_state_at_utah_has_an_edge_but_no_pick(
    client: TestClient, make_token: MakeToken, monkeypatch: pytest.MonkeyPatch
):
    game = _game(_get(client, make_token, monkeypatch), "KSU", "UTAH")
    assert game["model"]["edge"] == pytest.approx(0.6)
    assert game["model"]["side"] == "home"
    assert game["pick"] is None


def test_the_line_history_holds_only_pulls_before_the_clock(
    client: TestClient, make_token: MakeToken, monkeypatch: pytest.MonkeyPatch
):
    """Texas vs Oklahoma's line moved Mon, Tue, Thu and Sat: at Thursday noon the Thursday and
    Saturday pulls haven't happened yet."""
    at_slate = _game(_get(client, make_token, monkeypatch), "TEX", "OU")
    at_thursday = _game(_get(client, make_token, monkeypatch, THURSDAY_NOON), "TEX", "OU")

    assert [s["spread_home"] for s in at_slate["market"]["snapshots"]] == [7, 6.5, 6.5, 6, 6.5]
    assert [s["spread_home"] for s in at_thursday["market"]["snapshots"]] == [7, 6.5, 6.5]


def test_the_market_and_picks_read_the_api_clock(
    client: TestClient, make_token: MakeToken, monkeypatch: pytest.MonkeyPatch
):
    """The database's clock is past every fixture kickoff, the API's isn't: at Thursday noon
    Ohio State's line is still Sunday's −28 (Thursday's −27.5 pull hasn't happened) and the pick
    made at it Thursday night doesn't exist yet; at the slate time Ole Miss @ LSU hasn't kicked
    off, so it has no close and its pick no CLV yet, while UNLV @ Boise State's close is there."""
    thursday = _get(client, make_token, monkeypatch, THURSDAY_NOON)
    osu = _game(thursday, "PUR", "OSU")
    assert osu["market"]["current_spread_home"] == -28
    assert osu["model"]["edge"] == pytest.approx(3.2)
    assert osu["pick"] is None

    body = _get(client, make_token, monkeypatch)
    miss = _game(body, "MISS", "LSU")
    assert miss["market"]["closing_spread_home"] is None
    assert miss["pick"]["clv"] is None
    assert miss["pick"]["clv_so_far"] == -1.0
    assert _game(body, "UNLV", "BSU")["market"]["closing_spread_home"] == -10


def test_an_edge_against_the_current_line_not_the_one_picked_at(
    client: TestClient, make_token: MakeToken, monkeypatch: pytest.MonkeyPatch
):
    """Ole Miss was picked at LSU −2.5 (edge 3.9); the line is now −3.5, so the game's edge is
    4.9 while the pick keeps its own (sample-data § 1's note)."""
    game = _game(_get(client, make_token, monkeypatch), "MISS", "LSU")
    assert game["model"]["edge"] == pytest.approx(-4.9)
    assert game["model"]["side"] == "away"
    assert game["pick"]["edge"] == pytest.approx(-3.9)


# AC-3


def test_row_states_come_back_as_data(
    client: TestClient, make_token: MakeToken, monkeypatch: pytest.MonkeyPatch
):
    body = _get(client, make_token, monkeypatch)

    unlv = _game(body, "UNLV", "BSU")
    assert unlv["status"] == "final"
    assert (unlv["away_points"], unlv["home_points"]) == (24, 31)
    assert unlv["cover"] == "away"  # BSU by 7 against −10

    for away, home, score in (("PUR", "OSU", (3, 24)), ("IOWA", "WIS", (10, 7))):
        live = _game(body, away, home)
        assert live["status"] == "in_progress"
        assert (live["away_points"], live["home_points"]) == score
        assert live["cover"] is None

    furman = _game(body, "FUR", "CLEM")
    assert furman["away"]["division"] == "fcs"
    assert furman["home"]["division"] == "fbs"
    assert furman["market"] == {
        "opening_spread_home": None,
        "current_spread_home": None,
        "closing_spread_home": None,
        "snapshots": [],
    }
    assert furman["model"]["pred_margin"] == 34.0
    assert (furman["model"]["edge"], furman["model"]["cover_prob"]) == (None, None)

    texas = _game(body, "TEX", "OU")
    assert texas["neutral_site"] is True
    assert texas["venue"] == {"name": "Cotton Bowl", "city": "Dallas", "state": "TX"}
    assert _game(body, "UK", "UGA")["venue"] is None


def test_each_team_carries_its_chip_and_its_rank_entering_the_week(
    client: TestClient, make_token: MakeToken, monkeypatch: pytest.MonkeyPatch, db_conn: Connection
):
    body = _get(client, make_token, monkeypatch)
    ranks = dict(
        db_conn.execute(
            text(
                f"SELECT team_id, rank FROM team_rankings WHERE model_version_id = ({SEEDED_V1})"
                " AND season = 2026 AND season_type = 'regular' AND week = 6"
            )
        ).all()
    )
    teams = [g[side] for g in body["games"] for side in ("away", "home")]
    assert len(teams) == 108
    for team in teams:
        assert set(team) == {
            "id", "school", "abbreviation", "color", "logo_url", "division", "rank",
        }  # fmt: skip
        assert team["rank"] == ranks.get(team["id"])
    osu = _game(body, "PUR", "OSU")["home"]
    assert (osu["school"], osu["color"], osu["rank"]) == ("Ohio State", "#BB0000", 1)
    assert _game(body, "FUR", "CLEM")["away"]["rank"] is None  # FCS: never ranked


# AC-4


def test_the_ole_miss_pick_keeps_its_line_and_reads_clv_so_far(
    client: TestClient, make_token: MakeToken, monkeypatch: pytest.MonkeyPatch, db_conn: Connection
):
    game = _game(_get(client, make_token, monkeypatch), "MISS", "LSU")
    outcome = db_conn.execute(
        text(
            "SELECT line, created_at, clv_so_far, current_spread_home FROM pick_outcomes"
            f" WHERE model_version_id = ({SEEDED_V1}) AND game_id = :g AND is_current"
        ),
        {"g": _game_id(db_conn, "2026-w6-miss-lsu")},
    ).one()

    pick = game["pick"]
    assert pick["line"] == float(outcome.line) == -2.5
    assert datetime.fromisoformat(pick["picked_at"]) == outcome.created_at
    assert pick["picked_at"] == "2026-10-04T10:10:00Z"
    assert game["market"]["current_spread_home"] == float(outcome.current_spread_home) == -3.5
    assert pick["clv_so_far"] == float(outcome.clv_so_far) == -1.0  # away at −2.5, now −3.5
    assert (pick["side"], pick["tier"], pick["result"], pick["units"]) == (
        "away", "B", "pending", None,
    )  # fmt: skip


def test_a_graded_week_6_pick(
    client: TestClient, make_token: MakeToken, monkeypatch: pytest.MonkeyPatch
):
    pick = _game(_get(client, make_token, monkeypatch), "TULN", "MEM")["pick"]
    assert (pick["result"], pick["units"]) == ("won", 1.0)
    assert pick["clv"] == pytest.approx(0.5)  # away at −4.0, closed −3.5: close − line


# AC-5


def test_a_requested_week(
    client: TestClient, make_token: MakeToken, monkeypatch: pytest.MonkeyPatch, db_conn: Connection
):
    body = _get(
        client, make_token, monkeypatch, query="?season=2026&season_type=regular&week=5"
    )
    week5 = set(
        db_conn.execute(
            text(
                "SELECT id FROM games WHERE sport_id = 'cfb' AND season = 2026"
                " AND season_type = 'regular' AND week = 5"
            )
        ).scalars()
    )
    assert (body["season"], body["season_type"], body["week"]) == (2026, "regular", 5)
    assert {g["id"] for g in body["games"]} == week5 and len(week5) == 15
    assert body["counts"] == {"games": 15, "picks": 15}
    assert body["shell"]["week"] == 6  # the shell still names the coming week


@pytest.mark.parametrize(
    "query", ["?week=5", "?season=2026&week=5", "?season=2026&season_type=bowl&week=5", "?week=0"]
)
def test_a_partial_or_bad_week_is_refused(
    client: TestClient, make_token: MakeToken, monkeypatch: pytest.MonkeyPatch, query: str
):
    monkeypatch.setenv("FIXTURE_NOW", SLATE_NOW)
    response = client.get(
        f"/api/py/slate{query}", headers={"Authorization": f"Bearer {make_token()}"}
    )
    assert response.status_code == 422


def test_the_offseason_answers_200_with_no_games(
    client: TestClient, make_token: MakeToken, monkeypatch: pytest.MonkeyPatch
):
    body = _get(client, make_token, monkeypatch, OFFSEASON_NOW)
    assert body["offseason"] is True
    assert (body["season"], body["season_type"], body["week"]) == (None, None, None)
    assert body["games"] == []
    assert body["counts"] == {"games": 0, "picks": 0}
    assert body["shell"]["week"] is None
    # The shell's version (2026's, the latest season) and its rules, as in season.
    assert body["shell"]["model"] == {"name": "power", "version": "v1.0"}
    assert body["rules"] is not None and body["rules"]["min_edge_pts"] == 2.5


NOW = m.utc(m.SEASON, 9, 1, 12)


def _shown_version(conn: Connection, spec: dict[str, Any]) -> int:
    return conn.execute(
        text(
            "INSERT INTO model_versions (sport_id, market, name, version, spec,"
            " spec_schema_version, created_by, status)"
            " VALUES (:sport, 'spread', 'slate', 'v1', CAST(:spec AS jsonb), 1, 'user',"
            " 'production') RETURNING id"
        ),
        {"sport": m.SPORT, "spec": json.dumps(spec)},
    ).scalar_one()


def _v1_spec(conn: Connection) -> dict[str, Any]:
    return conn.execute(
        text(f"SELECT spec FROM model_versions WHERE id = ({SEEDED_V1})")
    ).scalar_one()


def _week_without_lines(conn: Connection, spec: dict[str, Any]) -> tuple[int, int]:
    m.sport(conn)
    home, away = m.team(conn, "slate-home"), m.team(conn, "slate-away")
    game = m.game(conn, home, away, NOW + timedelta(days=5), week=2, status="scheduled")
    version = _shown_version(conn, spec)
    run = m.run(conn, version, 2, NOW - timedelta(days=1), run_type="scheduled", home_field=None)
    m.prediction(conn, run, version, game)
    return game, version


def test_a_week_without_lines_gives_the_model_line_and_no_edge(db_conn: Connection):
    game_id, _ = _week_without_lines(db_conn, _v1_spec(db_conn))

    got = slate.load(db_conn, NOW, m.SPORT)

    assert (got.season, got.week, got.counts.games) == (m.SEASON, 2, 1)
    (game,) = got.games
    assert game.id == game_id
    assert game.market.model_dump() == {
        "opening_spread_home": None,
        "current_spread_home": None,
        "closing_spread_home": None,
        "snapshots": [],
    }
    assert game.model is not None
    assert (game.model.pred_margin, game.model.home_win_prob) == (4.5, 0.63)
    assert (game.model.edge, game.model.side, game.model.cover_prob) == (None, None, None)
    assert game.pick is None


def test_a_line_gives_the_edge_from_the_runs_pick_rules(db_conn: Connection):
    """The same week once a line is up: the edge and cover come from the spec resolved with
    the run, here a market shrinkage of 0.5 that the run's own choice fixes."""
    spec = _v1_spec(db_conn)
    spec["picks"]["market_shrinkage_k"] = {"tune": [0.5, 0.8]}
    game_id, version = _week_without_lines(db_conn, spec)
    db_conn.execute(
        text(
            "UPDATE model_runs SET fitted_params = CAST(:p AS jsonb)"
            " WHERE model_version_id = :v"
        ),
        {"v": version, "p": json.dumps({"choices": {"picks.market_shrinkage_k": 0.5}})},
    )
    m.line(db_conn, game_id, m.book(db_conn), NOW - timedelta(hours=1), -3.0)

    (game,) = slate.load(db_conn, NOW, m.SPORT).games

    assert game.model is not None
    assert game.model.edge == pytest.approx(blended_margin(4.5, -3.0, 0.5) - 3.0)  # 0.75
    rules = ModelSpec.model_validate(spec).resolve({"picks.market_shrinkage_k": 0.5}).picks
    assert game.model.cover_prob == pytest.approx(
        displayed_prob(4.5, -3.0, "home", rules, NormalMargin(13.8))
    )


def test_rules_the_run_never_resolved_leave_the_edge_out(db_conn: Connection):
    spec = _v1_spec(db_conn)
    spec["picks"]["market_shrinkage_k"] = {"tune": [0.5, 0.8]}
    game_id, _ = _week_without_lines(db_conn, spec)
    m.line(db_conn, game_id, m.book(db_conn), NOW - timedelta(hours=1), -3.0)

    got = slate.load(db_conn, NOW, m.SPORT)

    assert got.rules is None
    (game,) = got.games
    assert game.model is not None and game.model.pred_margin == 4.5
    assert (game.model.edge, game.model.cover_prob) == (None, None)


# AC-6


def test_slate_runs_its_queries_in_one_concurrent_wave(
    client: TestClient, make_token: MakeToken, monkeypatch: pytest.MonkeyPatch
):
    """Every statement waits at a barrier for the others: run one after another, the first
    breaks the barrier and the request fails. A warm call first keeps the driver's first-connect
    queries out of the count."""
    from api import main

    _get(client, make_token, monkeypatch)
    statements: list[str] = []
    barrier = threading.Barrier(len(slate.QUERIES), timeout=5)
    lock = threading.Lock()

    def counted(conn, cursor, statement, parameters, context, executemany):
        with lock:
            statements.append(statement)
        barrier.wait()

    engine = main.engine()
    event.listen(engine, "before_cursor_execute", counted)
    try:
        _get(client, make_token, monkeypatch)
    finally:
        event.remove(engine, "before_cursor_execute", counted)

    assert len(statements) == len(slate.QUERIES) == 5
    assert len(statements) <= wave.QUERY_BUDGET


def test_slate_rejects_a_missing_or_bad_token(client: TestClient, make_token: MakeToken):
    assert client.get("/api/py/slate").status_code == 401
    bad = make_token(secret="not-the-api-secret-but-long-enough-to-sign-0002")
    response = client.get("/api/py/slate", headers={"Authorization": f"Bearer {bad}"})
    assert response.status_code == 401


def test_the_slate_route_is_in_the_schema():
    from api.openapi import schema_json

    schema = json.loads(schema_json())
    assert "/api/py/slate" in schema["paths"]
    assert "SlateOut" in schema["components"]["schemas"]


def test_the_response_has_no_decimals(
    client: TestClient, make_token: MakeToken, monkeypatch: pytest.MonkeyPatch
):
    """Numeric columns reach JSON as numbers, never strings."""
    game = _game(_get(client, make_token, monkeypatch), "PUR", "OSU")
    assert isinstance(game["market"]["current_spread_home"], float)
    assert isinstance(game["pick"]["line"], float)
    assert datetime.fromisoformat(game["kickoff_at"]) == datetime(2026, 10, 10, 16, tzinfo=UTC)


# Views read for one week filter by it before ranking or windowing (.claude/rules/database.md ›
# Views & queries), so the slate's cost doesn't grow with the version's history.


def _plan(conn: Connection, name: str) -> dict[str, Any]:
    now = datetime.fromisoformat(SLATE_NOW)
    sql, params = slate.queries(now)[name]
    return m.explain(conn, str(sql), params)


def _conds(nodes: list[dict[str, Any]]) -> list[str]:
    for node in nodes:
        assert node["Node Type"] != "Seq Scan", node
    return [n.get("Index Cond") or n.get("Recheck Cond") or "" for n in nodes]


def test_the_ranks_are_read_for_the_week_alone(db_conn: Connection):
    conds = _conds(m.scans(_plan(db_conn, "games"), "team_ratings"))
    assert conds and all("week" in c for c in conds), conds


def test_the_picks_are_read_for_the_weeks_games_alone(db_conn: Connection):
    conds = _conds(m.scans(_plan(db_conn, "picks"), "picks"))
    assert conds and all("game_id" in c for c in conds), conds
