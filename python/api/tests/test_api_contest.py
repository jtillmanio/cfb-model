"""The Contest page API (TASK-071, D-174): the week's slate ranked against the contest's lines,
your entries with the kickoff lock, results and standing.

The fixture CI loads before pytest (`pnpm db:seed`) holds the Splash work league: Week 6's ten
contest lines captured Thu 2026-10-08 9:10 PM ET, your entries OU +7 (9:14 PM) and BUF −3
(9:20 PM), weeks 1-5's lines, entries and the model's contest picks (contest_history.json), and
the standing 3rd of 14 entered after week 5. The page's clock is Thu 10:00 PM ET; the locked
game's is Fri 8:12 PM ET, after UNLV at Boise State's 8:00 PM kickoff.

The write routes run on one connection per request (`main.connection`); the tests hand them
`db_conn`, so their writes roll back with it (contest_entries refuses DELETE), and read the page
back on it with `contest.load`. GETs through the client read the seeded database as it is.
"""

from __future__ import annotations

import json
import threading
from collections.abc import Callable, Iterator
from datetime import datetime
from typing import Any

import model_rows as m  # pyright: ignore[reportMissingImports]  (on sys.path via conftest)
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Connection, event, text

from api import contest, wave
from engine.core import ModelSpec, NormalMargin, displayed_prob, market_gap

MakeToken = Callable[..., str]

CONTEST_NOW = "2026-10-08T22:00:00-04:00"  # Thu 10:00 PM ET, the Contest screen's time
LOCKED_NOW = "2026-10-09T20:12:00-04:00"  # Fri 8:12 PM ET, after UNLV at Boise State kicks off
OWNER = "4242"  # the fixture user's GitHub id (the token's sub)

CONTEST_SQL = (
    "SELECT c.id FROM contests c JOIN users u ON u.id = c.user_id"
    " WHERE u.github_id = 4242 AND c.name = 'Splash work league' AND c.deleted_at IS NULL"
)
SEEDED_V1 = (
    "SELECT id FROM model_versions WHERE sport_id = 'cfb' AND market = 'spread'"
    " AND name = 'power' AND version = 'v1.0' AND deleted_at IS NULL"
)

# Week 6's contest lines (home spread) and the market's Thu 9:02 PM pull.
CFB = {
    "2026-w6-unlv-bsu": -10.0,
    "2026-w6-pur-osu": -27.0,
    "2026-w6-miss-lsu": -3.0,
    "2026-w6-nd-stan": 17.5,
    "2026-w6-tex-ou": 7.0,
    "2026-w6-colo-byu": -5.5,
}
NFL = {  # contest, market
    "2026-w6-buf-nyj": (3.0, 4.5),
    "2026-w6-hou-jax": (1.0, 1.5),
    "2026-w6-kc-bal": (-2.5, -2.5),
    "2026-w6-nyg-phi": (-6.0, -7.0),
}
TOP_4 = ["2026-w6-tex-ou", "2026-w6-miss-lsu", "2026-w6-pur-osu", "2026-w6-colo-byu"]
NEXT_BEST = "2026-w6-nd-stan"
LOCKED = "2026-w6-unlv-bsu"


@pytest.fixture
def contest_id(db_conn: Connection) -> int:
    return db_conn.execute(text(CONTEST_SQL)).scalar_one()


@pytest.fixture
def games(db_conn: Connection) -> dict[str, int]:
    rows = db_conn.execute(
        text("SELECT source_id, id FROM games WHERE source = 'fixture' AND source_id = ANY(:ids)"),
        {"ids": [*CFB, *NFL]},
    )
    return {r.source_id: r.id for r in rows}


@pytest.fixture
def api(
    client: TestClient, db_conn: Connection, monkeypatch: pytest.MonkeyPatch
) -> Iterator[TestClient]:
    """The write routes on db_conn, each request in a savepoint (as TASK-070's tests)."""
    from api import main

    def per_request() -> Iterator[Connection]:
        savepoint = db_conn.begin_nested()
        try:
            yield db_conn
        except BaseException:
            savepoint.rollback()
            raise
        savepoint.commit()

    monkeypatch.setenv("FIXTURE_NOW", CONTEST_NOW)
    main.app.dependency_overrides[main.connection] = per_request
    try:
        yield client
    finally:
        main.app.dependency_overrides.pop(main.connection, None)


def _auth(make_token: MakeToken, sub: str = OWNER) -> dict[str, str]:
    return {"Authorization": f"Bearer {make_token(sub=sub)}"}


def _get(
    client: TestClient,
    make_token: MakeToken,
    monkeypatch: pytest.MonkeyPatch,
    contest_id: int,
    at: str = CONTEST_NOW,
    query: str = "",
) -> dict[str, Any]:
    monkeypatch.setenv("FIXTURE_NOW", at)
    response = client.get(f"/api/py/contests/{contest_id}{query}", headers=_auth(make_token))
    assert response.status_code == 200, response.text
    return response.json()


def _load(conn: Connection, contest_id: int, at: str = CONTEST_NOW) -> contest.ContestPageOut:
    return contest.load(conn, datetime.fromisoformat(at), contest_id, OWNER, 6)


def _by_source(body: dict[str, Any], games: dict[str, int]) -> dict[str, dict[str, Any]]:
    source = {v: k for k, v in games.items()}
    return {source[g["id"]]: g for g in body["games"]}


def _entries(conn: Connection, contest_id: int, game_id: int) -> list[Any]:
    return list(
        conn.execute(
            text(
                "SELECT e.id, e.side, e.contest_line_id, e.created_at, e.deleted_at,"
                " l.spread_home FROM contest_entries e"
                " JOIN contest_lines l ON l.id = e.contest_line_id"
                " WHERE e.contest_id = :c AND e.game_id = :g ORDER BY e.id"
            ),
            {"c": contest_id, "g": game_id},
        )
    )


def _post(api: TestClient, make_token: MakeToken, contest_id: int, game_id: int, side: str) -> Any:
    return api.post(
        f"/api/py/contests/{contest_id}/entries",
        json={"game_id": game_id, "side": side},
        headers=_auth(make_token),
    )


def _delete(api: TestClient, make_token: MakeToken, contest_id: int, game_id: int) -> Any:
    return api.delete(f"/api/py/contests/{contest_id}/entries/{game_id}", headers=_auth(make_token))


# AC-1


def test_week_6_ranks_by_cover_against_the_contest_line(
    client: TestClient,
    make_token: MakeToken,
    monkeypatch: pytest.MonkeyPatch,
    db_conn: Connection,
    contest_id: int,
    games: dict[str, int],
):
    body = _get(client, make_token, monkeypatch, contest_id, query="?period=6")
    assert body["period"] == 6
    assert body["shell"]["model"] is not None
    assert len(body["games"]) == 10
    rows = _by_source(body, games)
    order = [{v: k for k, v in games.items()}[g["id"]] for g in body["games"]]

    # Every CFB row's edge and cover are engine.core's on v1.0's prediction and the contest line.
    rules = ModelSpec.model_validate(
        db_conn.execute(
            text(f"SELECT spec FROM model_versions WHERE id = ({SEEDED_V1})")
        ).scalar_one()
    ).picks
    for source, line in CFB.items():
        pred, sd = db_conn.execute(
            text(
                "SELECT p.pred_margin, p.margin_sd FROM predictions p"
                f" WHERE p.game_id = :g AND p.model_version_id = ({SEEDED_V1})"
                " ORDER BY p.created_at DESC LIMIT 1"
            ),
            {"g": games[source]},
        ).one()
        edge = float(pred) + line
        side = "home" if edge >= 0 else "away"
        model = rows[source]["model"]
        assert rows[source]["no_model"] is False
        assert model["edge"] == pytest.approx(edge)
        assert model["side"] == side
        assert model["cover_prob"] == pytest.approx(
            displayed_prob(float(pred), line, side, rules, NormalMargin(float(sd)))
        )

    # Ranked by cover % (the model's, else the market-implied), highest first.
    covers = [
        g["model"]["cover_prob"] if g["model"] else g["market_gap"]["implied_prob"]
        for g in body["games"]
    ]
    assert covers == sorted(covers, reverse=True)
    assert [g["rank"] for g in body["games"]] == list(range(1, 11))
    assert order[:4] == TOP_4
    assert [g["top_n"] for g in body["games"]] == [True] * 4 + [False] * 6
    assert order[4] == NEXT_BEST
    assert [g["next_best"] for g in body["games"]] == [False] * 4 + [True] + [False] * 5


def test_the_page_defaults_to_the_newest_week_with_lines(
    client: TestClient, make_token: MakeToken, monkeypatch: pytest.MonkeyPatch, contest_id: int
):
    body = _get(client, make_token, monkeypatch, contest_id)
    assert body["period"] == 6
    assert body["periods"] == [1, 2, 3, 4, 5, 6]
    assert body["contest"]["name"] == "Splash work league"
    assert body["contest"]["rules"]["picks_per_period"] == 4


# AC-2


def test_nfl_rows_carry_the_gap_and_the_market_implied_share(
    client: TestClient,
    make_token: MakeToken,
    monkeypatch: pytest.MonkeyPatch,
    contest_id: int,
    games: dict[str, int],
):
    rows = _by_source(_get(client, make_token, monkeypatch, contest_id), games)
    expected = {
        "2026-w6-buf-nyj": (1.5, "away"),
        "2026-w6-hou-jax": (0.5, "away"),
        "2026-w6-kc-bal": (0.0, None),
        "2026-w6-nyg-phi": (1.0, "home"),
    }
    for source, (contest_line, market) in NFL.items():
        row = rows[source]
        assert row["no_model"] is True
        assert row["model"] is None
        assert row["top_n"] is False
        assert (row["market_gap"]["points"], row["market_gap"]["side"]) == expected[source]
        assert row["market_gap"]["implied_prob"] == pytest.approx(
            market_gap(contest_line, market).prob
        )
    assert rows["2026-w6-kc-bal"]["market_gap"]["implied_prob"] == 0.5
    assert round(rows["2026-w6-buf-nyj"]["market_gap"]["implied_prob"] * 100) == 54


def test_the_differs_flag_marks_8_of_10(
    client: TestClient,
    make_token: MakeToken,
    monkeypatch: pytest.MonkeyPatch,
    contest_id: int,
    games: dict[str, int],
):
    body = _get(client, make_token, monkeypatch, contest_id)
    for row in body["games"]:
        assert row["contest_spread_home"] is not None
        assert row["market_spread_home"] is not None
        assert row["differs"] is (row["contest_spread_home"] != row["market_spread_home"])
    rows = _by_source(body, games)
    assert {s for s, r in rows.items() if not r["differs"]} == {LOCKED, "2026-w6-kc-bal"}
    assert body["counts"]["differs"] == 8
    for source, (contest_line, market) in NFL.items():
        assert (rows[source]["contest_spread_home"], rows[source]["market_spread_home"]) == (
            contest_line,
            market,
        )
    for source, line in CFB.items():
        assert rows[source]["contest_spread_home"] == line


# AC-3


def test_an_entry_is_added_at_the_current_contest_line(
    api: TestClient,
    make_token: MakeToken,
    db_conn: Connection,
    contest_id: int,
    games: dict[str, int],
):
    nd = games["2026-w6-nd-stan"]
    response = _post(api, make_token, contest_id, nd, "away")
    assert response.status_code == 200, response.text
    (row,) = _entries(db_conn, contest_id, nd)
    assert (row.side, float(row.spread_home), row.deleted_at) == ("away", 17.5, None)
    assert row.created_at == datetime.fromisoformat(CONTEST_NOW)
    current = db_conn.execute(
        text(
            "SELECT contest_line_id FROM current_contest_lines"
            " WHERE contest_id = :c AND game_id = :g"
        ),
        {"c": contest_id, "g": nd},
    ).scalar_one()
    assert row.contest_line_id == current == response.json()["contest_line_id"]
    assert response.json()["line"] == 17.5


def test_the_same_side_again_changes_nothing(
    api: TestClient,
    make_token: MakeToken,
    db_conn: Connection,
    contest_id: int,
    games: dict[str, int],
):
    ou = games["2026-w6-tex-ou"]
    before = _entries(db_conn, contest_id, ou)
    response = _post(api, make_token, contest_id, ou, "home")
    assert response.status_code == 200
    assert _entries(db_conn, contest_id, ou) == before


def test_the_other_side_replaces_the_entry(
    api: TestClient,
    make_token: MakeToken,
    db_conn: Connection,
    contest_id: int,
    games: dict[str, int],
):
    ou = games["2026-w6-tex-ou"]
    (first,) = _entries(db_conn, contest_id, ou)
    assert first.side == "home"
    response = _post(api, make_token, contest_id, ou, "away")
    assert response.status_code == 200, response.text
    old, new = _entries(db_conn, contest_id, ou)
    assert old.id == first.id and old.deleted_at == datetime.fromisoformat(CONTEST_NOW)
    assert (new.side, new.deleted_at, float(new.spread_home)) == ("away", None, 7.0)
    assert [e.game_id for e in _load(db_conn, contest_id).entries].count(ou) == 1


def test_removing_soft_deletes(
    api: TestClient,
    make_token: MakeToken,
    db_conn: Connection,
    contest_id: int,
    games: dict[str, int],
):
    buf = games["2026-w6-buf-nyj"]
    response = _delete(api, make_token, contest_id, buf)
    assert response.status_code == 204, response.text
    (row,) = _entries(db_conn, contest_id, buf)
    assert row.deleted_at == datetime.fromisoformat(CONTEST_NOW)
    assert buf not in [e.game_id for e in _load(db_conn, contest_id).entries]
    assert _delete(api, make_token, contest_id, buf).status_code == 404


def test_a_fifth_pick_is_refused(
    api: TestClient,
    make_token: MakeToken,
    db_conn: Connection,
    contest_id: int,
    games: dict[str, int],
):
    for source, side in (("2026-w6-nd-stan", "away"), ("2026-w6-colo-byu", "home")):
        assert _post(api, make_token, contest_id, games[source], side).status_code == 200
    assert len(_load(db_conn, contest_id).entries) == 4
    osu = games["2026-w6-pur-osu"]
    response = _post(api, make_token, contest_id, osu, "home")
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "full"
    assert _entries(db_conn, contest_id, osu) == []
    # A change of side on one of the four is still allowed: it isn't a fifth pick.
    assert _post(api, make_token, contest_id, games["2026-w6-nd-stan"], "home").status_code == 200


def test_a_game_off_the_slate_is_404(
    api: TestClient, make_token: MakeToken, db_conn: Connection, contest_id: int
):
    other = db_conn.execute(
        text("SELECT id FROM games WHERE source = 'fixture' AND source_id = '2026-w6-iowa-wis'")
    ).scalar_one()
    response = _post(api, make_token, contest_id, other, "home")
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "not_on_slate"


# AC-4


def test_the_locked_game_is_marked_and_the_rest_stay_open(
    client: TestClient,
    make_token: MakeToken,
    monkeypatch: pytest.MonkeyPatch,
    contest_id: int,
    games: dict[str, int],
):
    body = _get(client, make_token, monkeypatch, contest_id, at=LOCKED_NOW)
    rows = _by_source(body, games)
    assert rows[LOCKED]["locked"] is True
    assert [s for s, r in rows.items() if r["locked"]] == [LOCKED]
    assert {v: k for k, v in games.items()}[body["games"][-1]["id"]] == LOCKED  # after the open
    assert rows[LOCKED]["top_n"] is False and rows[LOCKED]["next_best"] is False
    assert [r["rank"] for r in body["games"][:-1]] == list(range(1, 10))


def test_the_locked_game_refuses_every_write(
    api: TestClient,
    make_token: MakeToken,
    monkeypatch: pytest.MonkeyPatch,
    db_conn: Connection,
    contest_id: int,
    games: dict[str, int],
):
    bsu = games[LOCKED]
    # Free a slot first, then pick UNLV while the game is open.
    assert _delete(api, make_token, contest_id, games["2026-w6-buf-nyj"]).status_code == 204
    assert _post(api, make_token, contest_id, bsu, "away").status_code == 200
    before = _entries(db_conn, contest_id, bsu)

    monkeypatch.setenv("FIXTURE_NOW", LOCKED_NOW)
    for response in (
        _post(api, make_token, contest_id, bsu, "home"),  # a change
        _post(api, make_token, contest_id, bsu, "away"),  # the same pick again
        _delete(api, make_token, contest_id, bsu),
    ):
        assert response.status_code == 409, response.text
        assert response.json()["detail"]["code"] == "locked"
    assert _entries(db_conn, contest_id, bsu) == before

    # A new pick on it is refused too, and an open game still takes one.
    count = db_conn.execute(
        text("SELECT count(*) FROM contest_entries WHERE contest_id = :c"), {"c": contest_id}
    ).scalar_one()
    nd = games["2026-w6-nd-stan"]
    assert _post(api, make_token, contest_id, nd, "away").status_code == 200
    assert (
        db_conn.execute(
            text("SELECT count(*) FROM contest_entries WHERE contest_id = :c"), {"c": contest_id}
        ).scalar_one()
        == count + 1
    )


def test_a_new_pick_on_the_locked_game_is_refused(
    api: TestClient,
    make_token: MakeToken,
    monkeypatch: pytest.MonkeyPatch,
    db_conn: Connection,
    contest_id: int,
    games: dict[str, int],
):
    monkeypatch.setenv("FIXTURE_NOW", LOCKED_NOW)
    response = _post(api, make_token, contest_id, games[LOCKED], "home")
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "locked"
    assert _entries(db_conn, contest_id, games[LOCKED]) == []


# AC-5


def test_entries_results_and_standing(
    client: TestClient,
    make_token: MakeToken,
    monkeypatch: pytest.MonkeyPatch,
    contest_id: int,
    games: dict[str, int],
):
    body = _get(client, make_token, monkeypatch, contest_id)
    source = {v: k for k, v in games.items()}
    assert [
        (source[e["game_id"]], e["side"], e["line"], e["created_at"]) for e in body["entries"]
    ] == [
        ("2026-w6-tex-ou", "home", 7.0, "2026-10-09T01:14:00Z"),
        ("2026-w6-buf-nyj", "away", 3.0, "2026-10-09T01:20:00Z"),
    ]

    results = body["results"]
    season = results["season"]
    assert (season["you"]["wins"], season["you"]["losses"]) == (12, 8)
    assert (season["model"]["wins"], season["model"]["losses"]) == (11, 9)
    weeks = [
        (
            w["period"],
            w["you"]["wins"],
            w["you"]["losses"],
            w["model"]["wins"],
            w["model"]["losses"],
        )
        for w in results["weeks"]
    ]
    assert weeks == [
        (1, 3, 1, 2, 2),
        (2, 2, 2, 3, 1),
        (3, 3, 1, 2, 2),
        (4, 1, 3, 2, 2),
        (5, 3, 1, 2, 2),
    ]
    this_week = results["this_week"]
    assert this_week["you"]["points"] == this_week["model"]["points"] == 0
    assert this_week["you"]["pending"] == 2

    standing = body["standing"]
    assert (standing["position"], standing["field_size"], standing["points_behind_leader"]) == (
        3,
        14,
        1.0,
    )


def test_a_posted_standing_is_read_back(
    api: TestClient, make_token: MakeToken, db_conn: Connection, contest_id: int
):
    response = api.post(
        f"/api/py/contests/{contest_id}/standings",
        json={"period": 6, "position": 2, "field_size": 14, "points_behind_leader": 0.5},
        headers=_auth(make_token),
    )
    assert response.status_code == 200, response.text
    standing = _load(db_conn, contest_id).standing
    assert standing is not None
    assert (standing.period, standing.position, standing.field_size) == (6, 2, 14)
    assert standing.points_behind_leader == 0.5
    assert standing.id == response.json()["id"]
    assert standing.entered_at == datetime.fromisoformat(CONTEST_NOW)


def test_a_standing_outside_its_field_is_422(
    api: TestClient, make_token: MakeToken, contest_id: int
):
    response = api.post(
        f"/api/py/contests/{contest_id}/standings",
        json={"period": 6, "position": 15, "field_size": 14},
        headers=_auth(make_token),
    )
    assert response.status_code == 422


def test_points_behind_take_one_decimal(api: TestClient, make_token: MakeToken, contest_id: int):
    """contest_standings.points_behind_leader is numeric(5,1): 0.25 would be stored as 0.3."""
    response = api.post(
        f"/api/py/contests/{contest_id}/standings",
        json={"period": 6, "position": 2, "field_size": 14, "points_behind_leader": 0.25},
        headers=_auth(make_token),
    )
    assert response.status_code == 422


# AC-6


def test_the_page_runs_in_one_wave_within_budget(
    client: TestClient, make_token: MakeToken, monkeypatch: pytest.MonkeyPatch, contest_id: int
):
    """Every statement waits at a barrier for the others: run one after another, the first breaks
    the barrier and the request fails. A warm call first keeps first-connect queries out."""
    from api import main

    _get(client, make_token, monkeypatch, contest_id)
    statements: list[str] = []
    barrier = threading.Barrier(len(contest.QUERIES), timeout=5)
    lock = threading.Lock()

    def counted(conn, cursor, statement, parameters, context, executemany):
        with lock:
            statements.append(statement)
        barrier.wait()

    engine = main.engine()
    event.listen(engine, "before_cursor_execute", counted)
    try:
        _get(client, make_token, monkeypatch, contest_id)
    finally:
        event.remove(engine, "before_cursor_execute", counted)

    assert len(statements) == len(contest.QUERIES) == 6
    assert len(statements) <= wave.QUERY_BUDGET


def _plan(conn: Connection, contest_id: int, name: str) -> dict[str, Any]:
    sql, params = contest.queries(datetime.fromisoformat(CONTEST_NOW), contest_id, OWNER, None)[
        name
    ]
    return m.explain(conn, str(sql), params)


def _conds(nodes: list[dict[str, Any]]) -> list[str]:
    for node in nodes:
        assert node["Node Type"] != "Seq Scan", node
    return [n.get("Index Cond") or n.get("Recheck Cond") or "" for n in nodes]


def test_the_record_is_read_for_the_contest_alone(db_conn: Connection, contest_id: int):
    """contest_record and contest_results filter by contest below their grouping and windows
    (.claude/rules/database.md › Views & queries): the contest's entries, its lines and the picks
    on them, never every contest's."""
    plan = _plan(db_conn, contest_id, "record")
    entries = _conds(m.scans(plan, "contest_entries"))
    assert entries and all("contest_id" in c for c in entries), entries
    lines = _conds(m.scans(plan, "contest_lines"))
    assert lines and all("contest_id" in c or "contest_line_id" in c for c in lines), lines
    picks = _conds(m.scans(plan, "picks"))
    assert picks and all("contest_line_id" in c for c in picks), picks


def test_the_slate_is_read_for_the_weeks_games_alone(db_conn: Connection, contest_id: int):
    plan = _plan(db_conn, contest_id, "games")
    lines = _conds(m.scans(plan, "contest_lines"))
    assert lines and all("contest_id" in c for c in lines), lines
    predictions = _conds(m.scans(plan, "predictions"))
    assert predictions and all("game_id" in c for c in predictions), predictions
    ratings = _conds(m.scans(plan, "team_ratings"))
    assert ratings and all("week" in c for c in ratings), ratings


def test_the_entries_are_read_for_the_contest_alone(db_conn: Connection, contest_id: int):
    entries = _conds(m.scans(_plan(db_conn, contest_id, "entries"), "contest_entries"))
    assert entries and all("contest_id" in c for c in entries), entries


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        ("get", "/api/py/contests/{c}", None),
        ("post", "/api/py/contests/{c}/entries", {"game_id": 1, "side": "home"}),
        ("delete", "/api/py/contests/{c}/entries/1", None),
        ("post", "/api/py/contests/{c}/standings", {"period": 6, "position": 1, "field_size": 2}),
    ],
)
def test_every_contest_route_needs_a_token(
    client: TestClient, make_token: MakeToken, contest_id: int, method: str, path: str, body: Any
):
    url = path.format(c=contest_id)
    kwargs: dict[str, Any] = {} if body is None else {"json": body}
    assert client.request(method, url, **kwargs).status_code == 401
    bad = make_token(secret="not-the-api-secret-but-long-enough-to-sign-0002")
    headers = {"Authorization": f"Bearer {bad}"}
    assert client.request(method, url, headers=headers, **kwargs).status_code == 401


def test_another_users_contest_is_404(
    client: TestClient,
    api: TestClient,
    make_token: MakeToken,
    db_conn: Connection,
    contest_id: int,
    games: dict[str, int],
):
    headers = _auth(make_token, sub="99")
    assert client.get(f"/api/py/contests/{contest_id}", headers=headers).status_code == 404
    response = api.post(
        f"/api/py/contests/{contest_id}/entries",
        json={"game_id": games["2026-w6-nd-stan"], "side": "away"},
        headers=headers,
    )
    assert response.status_code == 404
    assert _entries(db_conn, contest_id, games["2026-w6-nd-stan"]) == []


def test_the_contest_routes_are_in_the_schema():
    from api.openapi import schema_json

    schema = json.loads(schema_json())
    assert "get" in schema["paths"]["/api/py/contests/{contest_id}"]
    assert "post" in schema["paths"]["/api/py/contests/{contest_id}/entries"]
    assert "delete" in schema["paths"]["/api/py/contests/{contest_id}/entries/{game_id}"]
    assert "post" in schema["paths"]["/api/py/contests/{contest_id}/standings"]
    for name in ("ContestPageOut", "ContestEntryOut", "ContestStandingOut", "ContestRefusalBody"):
        assert name in schema["components"]["schemas"]


# The task's manual check, through the test client.


def test_the_manual_check(
    api: TestClient,
    make_token: MakeToken,
    monkeypatch: pytest.MonkeyPatch,
    db_conn: Connection,
    contest_id: int,
    games: dict[str, int],
):
    assert len(_load(db_conn, contest_id).entries) == 2
    assert _post(api, make_token, contest_id, games["2026-w6-nd-stan"], "away").status_code == 200
    assert len(_load(db_conn, contest_id).entries) == 3
    monkeypatch.setenv("FIXTURE_NOW", LOCKED_NOW)
    assert _post(api, make_token, contest_id, games[LOCKED], "away").status_code == 409


# The Contest screen's own route (TASK-072, D-175): `GET /contest` serves the same page for the
# caller's first live contest until `user_settings` names a default (M8.7), or for `contest_id`.


def _add_contest(conn: Connection, name: str) -> int:
    """Another live contest of the owner's, after the Splash work league (rolled back)."""
    return conn.execute(
        text(
            "INSERT INTO contests (user_id, name, platform, season, rules)"
            " SELECT c.user_id, :name, c.platform, c.season, c.rules FROM contests c"
            " WHERE c.id = (" + CONTEST_SQL + ") RETURNING id"
        ),
        {"name": name},
    ).scalar_one()


def test_the_screen_route_serves_the_first_live_contest(
    client: TestClient, make_token: MakeToken, monkeypatch: pytest.MonkeyPatch, contest_id: int
):
    monkeypatch.setenv("FIXTURE_NOW", CONTEST_NOW)
    response = client.get("/api/py/contest", headers=_auth(make_token))
    assert response.status_code == 200, response.text
    page = response.json()
    assert page["contest"]["id"] == contest_id
    assert page == _get(client, make_token, monkeypatch, contest_id)


def test_the_first_live_contest_is_the_default_and_an_id_picks_another(
    db_conn: Connection, contest_id: int
):
    later = _add_contest(db_conn, "A later league")
    now = datetime.fromisoformat(CONTEST_NOW)
    assert contest.load(db_conn, now, None, OWNER).contest.id == contest_id
    picked = contest.load(db_conn, now, later, OWNER)
    assert (picked.contest.id, picked.period) == (later, None)
    assert picked.games == [] and picked.periods == []

    # With the fixture's contest gone the next live one is the default: e2e's paste-journey
    # contests (D-175) may sit between it and `later` in a local test DB, so ask the table.
    db_conn.execute(text("UPDATE contests SET deleted_at = now() WHERE id = :c"), {"c": contest_id})
    first_live = db_conn.execute(
        text(
            "SELECT min(c.id) FROM contests c JOIN users u ON u.id = c.user_id"
            " WHERE u.github_id = 4242 AND c.deleted_at IS NULL"
        )
    ).scalar_one()
    assert first_live <= later
    assert contest.load(db_conn, now, None, OWNER).contest.id == first_live


def test_the_screen_route_is_404_with_no_contest(
    client: TestClient, make_token: MakeToken, monkeypatch: pytest.MonkeyPatch, contest_id: int
):
    monkeypatch.setenv("FIXTURE_NOW", CONTEST_NOW)
    headers = _auth(make_token, sub="99")
    assert client.get("/api/py/contest", headers=headers).status_code == 404
    url = f"/api/py/contest?contest_id={contest_id}"
    assert client.get(url, headers=headers).status_code == 404  # another user's
    assert client.get(url, headers=_auth(make_token)).status_code == 200


def test_the_page_names_the_contests_sports_and_scoring(
    client: TestClient, make_token: MakeToken, monkeypatch: pytest.MonkeyPatch, contest_id: int
):
    rules = _get(client, make_token, monkeypatch, contest_id)["contest"]["rules"]
    assert (rules["sports"], rules["scoring"]) == (["cfb", "nfl"], "point_per_win")


def test_the_screen_route_needs_the_token_and_is_in_the_schema(client: TestClient):
    from api.openapi import schema_json

    assert client.get("/api/py/contest").status_code == 401
    assert "get" in json.loads(schema_json())["paths"]["/api/py/contest"]


def test_the_default_contest_is_found_by_index(db_conn: Connection):
    """With no contest id, `mine` finds the caller by the github_id index and reads only their
    contests (.claude/rules/database.md › Views & queries; schema review R1). On a table this small
    the planner walks the primary key for `ORDER BY id LIMIT 1`, filtering on the user."""
    sql, params = contest.queries(datetime.fromisoformat(CONTEST_NOW), None, OWNER, None)["contest"]
    plan = m.explain(db_conn, str(sql), params)
    users = m.scans(plan, "users")
    assert users and all("github_id" in (n.get("Index Cond") or "") for n in users), users
    contests = m.scans(plan, "contests")
    assert contests and all(n["Node Type"] != "Seq Scan" for n in contests), contests
    conds = [(n.get("Index Cond") or "") + (n.get("Filter") or "") for n in contests]
    picked = [c for c in conds if "user_id" in c]
    assert picked, contests
