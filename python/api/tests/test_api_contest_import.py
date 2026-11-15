"""The contest import (TASK-070): paste a Splash page, see its rows matched to games, map the names
it couldn't match, and confirm the week's contest lines as a new snapshot (D-038, D-113).

The routes write through one connection per request (`main.connection`); every test here hands
them `db_conn`, so their writes roll back with it (contest_lines refuses DELETE). The fixture CI
loads before pytest (`pnpm db:seed`) holds the Splash work league, its Week 6 lines captured Thu
9:10 PM ET from this same paste, and the `splash` aliases for every Week 6 name but "Hou Texans"
and "Jax". The clock is Thu 2026-10-08 10:00 PM ET, the Contest screen's fixture time."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from datetime import date, datetime
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Connection, text

from api import contest_import
from db.config import repo_root
from engine.core.splash import parse_splash

MakeToken = Callable[..., str]

WEEK_6 = (repo_root() / "python" / "engine" / "tests" / "fixtures" / "splash_week6.txt").read_text(
    encoding="utf-8"
)
CONTEST_NOW = "2026-10-08T22:00:00-04:00"  # Thu 10:00 PM ET
LATER = "2026-10-09T18:00:00-04:00"  # Fri 6:00 PM ET, before every Week 6 kickoff

# Paste order, and each game's home line as the paste prints it.
GAMES = [
    ("2026-w6-unlv-bsu", -10), ("2026-w6-pur-osu", -27), ("2026-w6-miss-lsu", -3),
    ("2026-w6-nd-stan", 17.5), ("2026-w6-tex-ou", 7), ("2026-w6-colo-byu", -5.5),
    ("2026-w6-buf-nyj", 3), ("2026-w6-hou-jax", 1), ("2026-w6-kc-bal", -2.5),
    ("2026-w6-nyg-phi", -6),
]  # fmt: skip
HOU_JAX = 7  # the row "Hou Texans" @ "Jax"

CONTEST_SQL = (
    "SELECT c.id FROM contests c JOIN users u ON u.id = c.user_id"
    " WHERE u.github_id = 4242 AND c.name = 'Splash work league' AND c.deleted_at IS NULL"
)


@pytest.fixture
def api(
    client: TestClient, db_conn: Connection, monkeypatch: pytest.MonkeyPatch
) -> Iterator[TestClient]:
    from api import main

    monkeypatch.setenv("FIXTURE_NOW", CONTEST_NOW)
    main.app.dependency_overrides[main.connection] = lambda: db_conn
    try:
        yield client
    finally:
        main.app.dependency_overrides.pop(main.connection, None)


@pytest.fixture
def contest_id(db_conn: Connection) -> int:
    return db_conn.execute(text(CONTEST_SQL)).scalar_one()


@pytest.fixture
def game_ids(db_conn: Connection) -> dict[str, int]:
    rows = db_conn.execute(
        text("SELECT source_id, id FROM games WHERE source = 'fixture' AND source_id = ANY(:ids)"),
        {"ids": [g for g, _ in GAMES]},
    )
    return {r.source_id: r.id for r in rows}


@pytest.fixture
def nfl_team(db_conn: Connection) -> Callable[[str], int]:
    def find(code: str) -> int:
        return db_conn.execute(
            text("SELECT id FROM teams WHERE sport_id = 'nfl' AND source_id = :c"), {"c": code}
        ).scalar_one()

    return find


def headers(make_token: MakeToken, **claims: Any) -> dict[str, str]:
    return {"Authorization": f"Bearer {make_token(**claims)}"}


def post(
    api: TestClient, make_token: MakeToken, path: str, body: dict[str, Any], **claims: Any
) -> Any:
    return api.post(f"/api/py/contests/{path}", json=body, headers=headers(make_token, **claims))


def preview(api: TestClient, make_token: MakeToken, contest: int, paste: str = WEEK_6) -> Any:
    return post(api, make_token, f"{contest}/import/preview", {"text": paste, "period": 6})


def confirm(api: TestClient, make_token: MakeToken, contest: int, paste: str = WEEK_6) -> Any:
    return post(api, make_token, f"{contest}/import/confirm", {"text": paste, "period": 6})


def map_hou_jax(
    api: TestClient, make_token: MakeToken, contest: int, nfl_team: Callable[[str], int]
) -> Any:
    mappings = [
        {"alias": "Hou Texans", "team_id": nfl_team("HOU")},
        {"alias": "Jax", "team_id": nfl_team("JAX")},
    ]
    return post(api, make_token, f"{contest}/aliases", {"mappings": mappings})


def counts(conn: Connection) -> tuple[int, int]:
    return (
        conn.execute(text("SELECT count(*) FROM contest_lines")).scalar_one(),
        conn.execute(text("SELECT count(*) FROM team_aliases")).scalar_one(),
    )


def at(value: str) -> datetime:
    return datetime.fromisoformat(value)


def moved_byu(paste: str = WEEK_6) -> str:
    """The Week 6 paste with Colorado @ BYU moved from BYU -5.5 to BYU -4.5."""
    moved = paste.replace("Colorado\n3-2\n+5.5", "Colorado\n3-2\n+4.5")
    moved = moved.replace("BYU\n4-1\n-5.5", "BYU\n4-1\n-4.5")
    assert moved.count("4.5\n") >= 2 and moved != paste
    return moved


# AC-1


def test_preview_matches_nine_of_ten_and_writes_nothing(
    api: TestClient,
    make_token: MakeToken,
    db_conn: Connection,
    contest_id: int,
    game_ids: dict[str, int],
):
    before = counts(db_conn)

    response = preview(api, make_token, contest_id)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["counts"] == {"rows": 10, "matched": 9, "unmatched": 1, "problem": 0}
    rows = body["rows"]
    assert len(rows) == 10
    kickoffs = {
        r.id: r.kickoff_at
        for r in db_conn.execute(
            text("SELECT id, kickoff_at FROM games WHERE id = ANY(:ids)"),
            {"ids": list(game_ids.values())},
        )
    }
    for i, (row, (game, spread)) in enumerate(zip(rows, GAMES, strict=True)):
        assert row["index"] == i
        assert row["spread_home"] == spread
        if i == HOU_JAX:
            assert row["status"] == "unmatched"
            assert (row["away_name"], row["home_name"]) == ("Hou Texans", "Jax")
            assert row["game_id"] is None
            assert [n["name"] for n in row["unmatched"]] == ["Hou Texans", "Jax"]
            continue
        assert row["status"] == "matched", row
        assert row["matched_by"] == "alias"
        assert row["game_id"] == game_ids[game]
        assert at(row["kickoff_at"]) == kickoffs[game_ids[game]]
    assert body["changes"] == []  # the fixture's lines are this paste's
    assert counts(db_conn) == before


# AC-2


def test_mapping_saves_two_aliases_once_and_then_all_match(
    api: TestClient,
    make_token: MakeToken,
    db_conn: Connection,
    contest_id: int,
    game_ids: dict[str, int],
    nfl_team: Callable[[str], int],
):
    lines_before, aliases_before = counts(db_conn)

    first = map_hou_jax(api, make_token, contest_id, nfl_team)

    assert first.status_code == 200, first.text
    assert first.json()["created"] == 2
    saved = db_conn.execute(
        text(
            "SELECT alias, team_id FROM team_aliases WHERE source = 'splash'"
            " AND alias IN ('Hou Texans', 'Jax') ORDER BY alias"
        )
    ).all()
    assert [tuple(r) for r in saved] == [("Hou Texans", nfl_team("HOU")), ("Jax", nfl_team("JAX"))]
    assert counts(db_conn) == (lines_before, aliases_before + 2)

    again = map_hou_jax(api, make_token, contest_id, nfl_team)

    assert again.status_code == 200, again.text
    assert again.json()["created"] == 0
    assert counts(db_conn) == (lines_before, aliases_before + 2)

    body = preview(api, make_token, contest_id).json()
    assert body["counts"] == {"rows": 10, "matched": 10, "unmatched": 0, "problem": 0}
    assert body["rows"][HOU_JAX]["game_id"] == game_ids["2026-w6-hou-jax"]


def test_an_alias_mapped_to_another_team_is_409_and_writes_nothing(
    api: TestClient,
    make_token: MakeToken,
    db_conn: Connection,
    contest_id: int,
    nfl_team: Callable[[str], int],
):
    taken = post(
        api,
        make_token,
        f"{contest_id}/aliases",
        {"mappings": [{"alias": "Jax", "team_id": nfl_team("HOU")}]},
    )
    assert taken.status_code == 200, taken.text
    before = counts(db_conn)

    response = map_hou_jax(api, make_token, contest_id, nfl_team)

    assert response.status_code == 409, response.text
    assert response.json()["detail"]["aliases"] == ["Jax"]
    assert counts(db_conn) == before  # "Hou Texans" isn't saved either


def test_a_team_outside_the_contests_sports_is_refused(
    api: TestClient, make_token: MakeToken, db_conn: Connection, contest_id: int
):
    db_conn.execute(text("INSERT INTO sports (id, name) VALUES ('zz_test', 'Test sport')"))
    team = db_conn.execute(
        text(
            "INSERT INTO teams (sport_id, source, source_id, school)"
            " VALUES ('zz_test', 'fixture', 'zz-1', 'Elsewhere') RETURNING id"
        )
    ).scalar_one()
    before = counts(db_conn)

    response = post(
        api, make_token, f"{contest_id}/aliases", {"mappings": [{"alias": "Jax", "team_id": team}]}
    )

    assert response.status_code == 422, response.text
    assert counts(db_conn) == before


# AC-3


def test_confirm_inserts_one_line_per_row_at_the_api_clock(
    api: TestClient,
    make_token: MakeToken,
    db_conn: Connection,
    contest_id: int,
    game_ids: dict[str, int],
    nfl_team: Callable[[str], int],
):
    map_hou_jax(api, make_token, contest_id, nfl_team)
    lines_before, _ = counts(db_conn)

    response = confirm(api, make_token, contest_id)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["inserted"] == 10
    assert at(body["captured_at"]) == at(CONTEST_NOW)
    stored = db_conn.execute(
        text(
            "SELECT game_id, spread_home, period, source FROM contest_lines"
            " WHERE contest_id = :c AND captured_at = :t"
        ),
        {"c": contest_id, "t": at(CONTEST_NOW)},
    ).all()
    assert sorted((r.game_id, r.spread_home, r.period, r.source) for r in stored) == sorted(
        (game_ids[g], Decimal(str(s)), 6, "paste") for g, s in GAMES
    )
    assert counts(db_conn)[0] == lines_before + 10


def test_confirm_with_an_unmatched_row_is_422_and_writes_nothing(
    api: TestClient, make_token: MakeToken, db_conn: Connection, contest_id: int
):
    before = counts(db_conn)

    response = confirm(api, make_token, contest_id)

    assert response.status_code == 422, response.text
    detail = response.json()["detail"]
    assert detail["code"] == "unresolved"
    assert [(r["index"], r["away_name"], r["home_name"]) for r in detail["rows"]] == [
        (HOU_JAX, "Hou Texans", "Jax")
    ]
    assert counts(db_conn) == before


# AC-4


def test_repaste_lists_moved_lines_and_confirm_adds_a_new_snapshot(
    api: TestClient,
    make_token: MakeToken,
    db_conn: Connection,
    contest_id: int,
    game_ids: dict[str, int],
    nfl_team: Callable[[str], int],
    monkeypatch: pytest.MonkeyPatch,
):
    map_hou_jax(api, make_token, contest_id, nfl_team)
    earlier = db_conn.execute(
        text("SELECT id, game_id, spread_home, captured_at FROM contest_lines ORDER BY id")
    ).all()
    byu = game_ids["2026-w6-colo-byu"]

    body = preview(api, make_token, contest_id, moved_byu()).json()

    moves = [(c["game_id"], c["old_spread_home"], c["new_spread_home"]) for c in body["changes"]]
    assert moves == [(byu, -5.5, -4.5)]
    change = body["changes"][0]
    assert change["index"] == 5
    assert at(change["old_captured_at"]) == at("2026-10-09T01:10:00Z")  # the fixture's paste

    confirmed = confirm(api, make_token, contest_id, moved_byu())

    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["inserted"] == 10
    after = db_conn.execute(
        text("SELECT id, game_id, spread_home, captured_at FROM contest_lines ORDER BY id")
    ).all()
    assert after[: len(earlier)] == earlier  # every earlier snapshot as it was
    new = {r.game_id: r.spread_home for r in after[len(earlier) :]}
    assert new[byu] == Decimal("-4.5")

    monkeypatch.setenv("FIXTURE_NOW", LATER)
    assert preview(api, make_token, contest_id, moved_byu()).json()["changes"] == []
    back = preview(api, make_token, contest_id).json()["changes"]
    assert [(c["old_spread_home"], c["new_spread_home"]) for c in back] == [(-4.5, -5.5)]


# AC-5


def test_unparseable_text_is_422(
    api: TestClient, make_token: MakeToken, db_conn: Connection, contest_id: int
):
    before = counts(db_conn)

    for route in ("preview", "confirm"):
        response = post(
            api,
            make_token,
            f"{contest_id}/import/{route}",
            {"text": "Leaderboard\nYou 3rd of 14\nNo games here", "period": 6},
        )
        assert response.status_code == 422, response.text
        assert response.json()["detail"]["code"] == "unparseable"
    assert counts(db_conn) == before


NO_TEAM = """Pick against the spread
Picks lock:
Sun, Oct 11, 2026, 8:20 PM
Friday, Oct 9
Nowhere State
Elsewhere Tech
Preview
Fri 8:00pm

Nowhere State
3-2
+10

Elsewhere Tech
4-1
-10

Over 55.5

Under 55.5
"""


def test_no_team_matched_is_the_no_match_response(
    api: TestClient, make_token: MakeToken, db_conn: Connection, contest_id: int
):
    before = counts(db_conn)

    response = preview(api, make_token, contest_id, NO_TEAM)

    assert response.status_code == 422, response.text
    detail = response.json()["detail"]
    assert detail["code"] == "no_match"
    assert [(r["away_name"], r["home_name"], r["spread_home"]) for r in detail["rows"]] == [
        ("Nowhere State", "Elsewhere Tech", -10)
    ]
    assert counts(db_conn) == before


def test_a_problem_row_is_returned_and_blocks_confirm(
    api: TestClient,
    make_token: MakeToken,
    db_conn: Connection,
    contest_id: int,
    game_ids: dict[str, int],
    nfl_team: Callable[[str], int],
):
    map_hou_jax(api, make_token, contest_id, nfl_team)
    disagree = WEEK_6.replace("UNLV\n3-2\n+10", "UNLV\n3-2\n+9")
    no_line = disagree.replace("Purdue\n1-4\n+27\n", "Purdue\n1-4\n")
    assert no_line.count("\n") < disagree.count("\n") and disagree != WEEK_6
    before = counts(db_conn)

    body = preview(api, make_token, contest_id, no_line).json()

    assert body["counts"] == {"rows": 10, "matched": 8, "unmatched": 0, "problem": 2}
    unlv, purdue = body["rows"][0], body["rows"][1]
    assert (unlv["status"], unlv["problem"], unlv["spread_home"]) == (
        "problem", "lines disagree", None
    )  # fmt: skip
    assert (purdue["status"], purdue["problem"]) == ("problem", "no line")
    assert unlv["game_id"] == game_ids["2026-w6-unlv-bsu"]  # still placed, for the screen

    response = confirm(api, make_token, contest_id, no_line)

    assert response.status_code == 422, response.text
    detail = response.json()["detail"]
    assert detail["code"] == "unresolved"
    assert [(r["index"], r["problem"]) for r in detail["rows"]] == [
        (0, "lines disagree"), (1, "no line")
    ]  # fmt: skip
    assert counts(db_conn) == before


# The plan's decisions A and B, and the contest's owner


def test_a_name_without_an_alias_falls_back_to_school_or_nickname(
    api: TestClient,
    make_token: MakeToken,
    db_conn: Connection,
    contest_id: int,
    game_ids: dict[str, int],
):
    db_conn.execute(text("DELETE FROM team_aliases WHERE source = 'splash'"))
    before = counts(db_conn)

    body = preview(api, make_token, contest_id).json()

    assert body["counts"] == {"rows": 10, "matched": 9, "unmatched": 1, "problem": 0}
    for i, (row, (game, _)) in enumerate(zip(body["rows"], GAMES, strict=True)):
        if i != HOU_JAX:
            assert (row["game_id"], row["matched_by"]) == (game_ids[game], "name"), row
    assert counts(db_conn) == before  # the fallback saves nothing


def test_unmatched_names_come_with_the_days_likely_teams(
    api: TestClient, make_token: MakeToken, contest_id: int, nfl_team: Callable[[str], int]
):
    row = preview(api, make_token, contest_id).json()["rows"][HOU_JAX]

    hou, jax = row["unmatched"]
    assert hou["candidates"][0]["id"] == nfl_team("HOU")
    assert jax["candidates"][0]["id"] == nfl_team("JAX")
    for name in (hou, jax):
        assert 0 < len(name["candidates"]) <= contest_import.MAX_CANDIDATES


ROUTES = ("import/preview", "import/confirm", "aliases")


def test_every_import_route_is_401_without_a_token_before_any_connection(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
):
    """AC-6: the JWT guard refuses before the request's connection is opened."""
    from api import main

    def no_connection() -> None:
        raise AssertionError("opened a database connection before checking the token")

    monkeypatch.setattr(main, "engine", no_connection)
    for route in ROUTES:
        response = client.post(f"/api/py/contests/1/{route}", json={"text": "x", "period": 6})
        assert response.status_code == 401, (route, response.text)
        assert response.json() == {"detail": "Not authenticated"}


def test_another_users_contest_is_404(
    api: TestClient, make_token: MakeToken, db_conn: Connection, contest_id: int
):
    before = counts(db_conn)

    for route in ("import/preview", "import/confirm"):
        response = post(
            api, make_token, f"{contest_id}/{route}", {"text": WEEK_6, "period": 6}, sub="777"
        )
        assert response.status_code == 404, response.text
    assert preview(api, make_token, contest_id + 10_000).status_code == 404
    assert counts(db_conn) == before


def _team(team_id: int, school: str, sport: str = "cfb") -> contest_import.Team:
    return contest_import.Team(team_id, sport, school, None, None, None)


def _game(
    game_id: int, away: contest_import.Team, home: contest_import.Team, neutral: bool = False
) -> contest_import.Game:
    saturday = date(2026, 10, 10)
    return contest_import.Game(game_id, away.sport_id, saturday, None, neutral, home, away)


def _paste(*blocks: tuple[str, str, str, str]) -> str:
    """A Saturday page with one block per (away, home, away line, home line)."""
    lines = ["Picks lock:", "Sun, Oct 11, 2026, 8:20 PM", "Saturday, Oct 10"]
    for away, home, away_line, home_line in blocks:
        lines += [away, home, "Preview", "Sat 3:30pm", away, "4-1", away_line]
        lines += [home, "3-2", home_line, "Over 50.5", "Under 50.5"]
    return "\n".join(lines)


def test_matching_turns_a_neutral_site_game_round_and_flags_ambiguity_and_repeats():
    texas, ou, buf_cfb, buf_nfl, kent, miami_oh, miami_fl = (
        _team(1, "Texas"), _team(2, "Oklahoma"), _team(3, "Buffalo"),
        _team(4, "Buffalo", "nfl"), _team(5, "Kent State"), _team(6, "Miami"), _team(7, "Miami"),
    )  # fmt: skip
    games = [
        _game(10, ou, texas, neutral=True),  # stored as Oklahoma @ Texas
        _game(11, kent, buf_cfb),
        _game(12, ou, miami_oh),
        _game(13, ou, miami_fl),
    ]
    names = contest_import.Names(
        aliases={},
        by_name={
            "Texas": [texas], "Oklahoma": [ou], "Kent State": [kent],
            "Buffalo": [buf_cfb, buf_nfl], "Miami": [miami_oh, miami_fl],
        },
    )  # fmt: skip
    parse = parse_splash(
        _paste(
            ("Texas", "Oklahoma", "-7", "+7"),  # written the other way round
            ("Kent State", "Buffalo", "+3", "-3"),  # "Buffalo" is two teams; one game pairs
            ("Oklahoma", "Miami", "+1", "-1"),  # two games pair
            ("Kent State", "Buffalo", "+3", "-3"),  # the same game again
        ),
        {},
    )

    rows = [m.out for m in contest_import.match_rows(parse, names, games)]

    assert [(r.status, r.game_id) for r in rows] == [
        ("matched", 10), ("matched", 11), ("ambiguous", None), ("duplicate", 11)
    ]  # fmt: skip
    assert rows[0].spread_home == -7  # Texas -7, and Texas is the stored home side
    assert rows[0].home_team is not None and rows[0].home_team.id == texas.id
    assert rows[0].swapped and not rows[1].swapped
    assert rows[1].spread_home == -3 and rows[1].matched_by == "name"


def test_a_write_upserts_the_user_by_github_id(db_conn: Connection):
    def users(github_id: int) -> int:
        return db_conn.execute(
            text("SELECT count(*) FROM users WHERE github_id = :g"), {"g": github_id}
        ).scalar_one()

    assert users(31337) == 0
    first = contest_import.upsert_user(db_conn, "31337")
    assert users(31337) == 1
    assert contest_import.upsert_user(db_conn, "31337") == first
    assert users(31337) == 1
    fixture_user = db_conn.execute(text("SELECT id FROM users WHERE github_id = 4242")).scalar_one()
    assert contest_import.upsert_user(db_conn, "4242") == fixture_user
