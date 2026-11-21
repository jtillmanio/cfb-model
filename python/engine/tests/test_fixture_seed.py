"""`engine seed fixture` against a test DB seeded before the files changed (TASK-055): a model
version is reused, never changed, so a spec that moved since is refused by name, not kept."""

from __future__ import annotations

import copy

import pytest
from sqlalchemy import Connection, text

from engine import fixture
from engine.core.contest_rules import ContestRules


def test_a_reseed_with_the_same_spec_reuses_the_versions(db_conn: Connection):
    models = fixture._load("models.json")
    first = fixture._seed_versions(db_conn, models)
    assert fixture._seed_versions(db_conn, models) == first


def test_a_spec_that_changed_since_the_seed_is_refused(db_conn: Connection):
    models = copy.deepcopy(fixture._load("models.json"))
    fixture._seed_versions(db_conn, models)
    models["versions"][0]["spec"]["picks"]["min_edge_pts"] = 3.0

    with pytest.raises(fixture.FixtureDrift, match="v1.0 spec differs.*rebuild the test DB"):
        fixture._seed_versions(db_conn, models)


def test_a_reseed_adds_no_nfl_rows(db_conn: Connection):
    """TASK-069: the seeded NFL games and lines are found again, not added twice."""
    book_id = db_conn.execute(
        text("SELECT id FROM sportsbooks WHERE source = 'fixture' AND source_id = 'consensus'")
    ).scalar_one()
    count = text("SELECT count(*) FROM games WHERE sport_id = 'nfl' AND source = 'fixture'")
    before = db_conn.execute(count).scalar_one()

    assert fixture._seed_nfl(db_conn, fixture._load("nfl.json"), book_id) == (4, 0)
    assert db_conn.execute(count).scalar_one() == before == 4


def test_a_reseed_adds_no_contest_rows(db_conn: Connection):
    """TASK-067: the seeded user, contest, contest lines, entries and standing are found again,
    not added twice."""
    tables = ("users", "contests", "contest_lines", "contest_entries", "contest_standings")
    count = text(" + ".join(f"(SELECT count(*) FROM {t})" for t in tables))
    before = db_conn.execute(text(f"SELECT {count.text}")).scalar_one()

    new = fixture._seed_contest(
        db_conn, fixture._load("contest.json"), fixture._load("contest_history.json")
    )

    assert new == {"lines": 0, "entries": 0, "standings": 0}
    assert db_conn.execute(text(f"SELECT {count.text}")).scalar_one() == before


def test_a_reseed_adds_no_contest_games_or_model_picks(db_conn: Connection):
    """TASK-068: contest_history.json's week-2 games, their lines and predictions, and the
    model's contest picks are found again, not added twice."""
    picks, week = fixture._load("picks.json"), fixture._load("week6.json")
    history, contest = fixture._load("contest_history.json"), fixture._load("contest.json")
    team_ids = fixture._seed_teams(db_conn, fixture.load_teams())
    book_id = db_conn.execute(
        text("SELECT id FROM sportsbooks WHERE source = 'fixture' AND source_id = 'consensus'")
    ).scalar_one()
    version_id = fixture._seed_versions(db_conn, fixture._load("models.json"))[picks["version"]]
    count = text("SELECT count(*) FROM picks WHERE contest_line_id IS NOT NULL")
    before = db_conn.execute(count).scalar_one()

    assert fixture._seed_contest_games(
        db_conn, history, picks, week, team_ids, book_id, version_id
    ) == (0, 0)
    assert fixture._seed_contest_picks(
        db_conn, contest, history, week, picks["season"], version_id
    ) == 0
    assert db_conn.execute(count).scalar_one() == before == 25


# `engine seed paste-journey` (TASK-072, D-175): each e2e run of journey 3 starts from a fresh,
# empty contest whose platform has every fixture `splash` alias but the two the journey maps.

_ALIASES = text("SELECT alias, team_id FROM team_aliases WHERE source = :s ORDER BY alias")
_LIVE = text(
    "SELECT c.id, c.platform, c.season, c.rules FROM contests c JOIN users u ON u.id = c.user_id"
    " WHERE u.github_id = 4242 AND c.name = :n AND c.deleted_at IS NULL"
)


def test_a_reset_makes_an_empty_contest_with_the_splash_aliases_but_two(db_conn: Connection):
    contest_id = fixture.reset_paste_journey(db_conn, "phone")

    live = db_conn.execute(_LIVE, {"n": "Paste journey (phone)"}).one()
    assert (live.id, live.platform, live.season) == (contest_id, "splash-e2e-phone", 2026)
    seeded = fixture._load("contest.json")["contest"]["rules"]
    assert ContestRules.model_validate(live.rules) == ContestRules.model_validate(seeded)
    lines = text("SELECT count(*) FROM contest_lines WHERE contest_id = :c")
    assert db_conn.execute(lines, {"c": contest_id}).scalar_one() == 0

    splash = dict(db_conn.execute(_ALIASES, {"s": "splash"}).all())
    copied = dict(db_conn.execute(_ALIASES, {"s": "splash-e2e-phone"}).all())
    assert copied == {a: t for a, t in splash.items() if a not in ("Hou Texans", "Jax")}
    assert len(copied) == 18


def test_a_second_reset_replaces_the_contest_and_the_mapped_aliases(db_conn: Connection):
    first = fixture.reset_paste_journey(db_conn, "desktop")
    houston = (
        "SELECT id FROM teams WHERE sport_id = 'nfl' AND source = 'fixture' AND source_id = 'HOU'"
    )
    team = db_conn.execute(text(houston)).scalar_one()
    db_conn.execute(
        text("INSERT INTO team_aliases (team_id, source, alias) VALUES (:t, :s, 'Hou Texans')"),
        {"t": team, "s": "splash-e2e-desktop"},
    )

    second = fixture.reset_paste_journey(db_conn, "desktop")

    assert second != first
    assert db_conn.execute(_LIVE, {"n": "Paste journey (desktop)"}).one().id == second
    gone = text("SELECT deleted_at IS NOT NULL FROM contests WHERE id = :c")
    assert db_conn.execute(gone, {"c": first}).scalar_one()
    copied = dict(db_conn.execute(_ALIASES, {"s": "splash-e2e-desktop"}).all())
    assert "Hou Texans" not in copied and len(copied) == 18
    assert "Hou Texans" not in dict(db_conn.execute(_ALIASES, {"s": "splash"}).all())


@pytest.mark.parametrize("project", ["", "Phone", "phone desktop", "../x"])
def test_a_reset_refuses_a_project_name_that_isnt_a_plain_word(db_conn: Connection, project: str):
    with pytest.raises(ValueError, match="project"):
        fixture.reset_paste_journey(db_conn, project)


def test_the_paste_journey_refuses_under_live(monkeypatch: pytest.MonkeyPatch):
    """Like `seed fixture`, the reset never runs against a live database (refuse_if_live)."""
    from db.config import UnsafeDatabaseError

    monkeypatch.setenv("LIVE", "true")
    opened = []
    monkeypatch.setattr(fixture, "make_engine", lambda *a, **k: opened.append(a))
    with pytest.raises(UnsafeDatabaseError):
        fixture.paste_journey("phone")
    assert opened == []


# `engine seed pick-journey` (TASK-073): journey 4 taps picks and enters a standing, so it gets
# its own contest per Playwright project: the work league's rules and Week 6 lines, no entries.

_WORK_LINES = text(
    "SELECT l.game_id, l.spread_home, l.captured_at FROM contest_lines l"
    " JOIN contests c ON c.id = l.contest_id JOIN users u ON u.id = c.user_id"
    " WHERE u.github_id = 4242 AND c.name = :n AND c.deleted_at IS NULL AND l.period = :p"
    " ORDER BY l.game_id, l.captured_at"
)
_OWN_LINES = text(
    "SELECT game_id, spread_home, captured_at, period FROM contest_lines WHERE contest_id = :c"
    " ORDER BY game_id, captured_at"
)


def test_a_pick_reset_copies_the_work_leagues_week_6_lines_and_no_entries(db_conn: Connection):
    work = fixture._load("contest.json")["contest"]
    contest_id = fixture.reset_pick_journey(db_conn, "phone")

    live = db_conn.execute(_LIVE, {"n": "Pick journey (phone)"}).one()
    assert (live.id, live.season) == (contest_id, work["season"])
    assert ContestRules.model_validate(live.rules) == ContestRules.model_validate(work["rules"])

    seeded = db_conn.execute(_WORK_LINES, {"n": work["name"], "p": fixture.WEEK}).all()
    copied = db_conn.execute(_OWN_LINES, {"c": contest_id}).all()
    assert len(seeded) == 10
    assert [tuple(r)[:3] for r in copied] == [tuple(r) for r in seeded]
    assert {r.period for r in copied} == {fixture.WEEK}
    for table in ("contest_entries", "contest_standings"):
        count = text(f"SELECT count(*) FROM {table} WHERE contest_id = :c")
        assert db_conn.execute(count, {"c": contest_id}).scalar_one() == 0


def test_a_second_pick_reset_replaces_the_contest_and_leaves_the_work_league(db_conn: Connection):
    work = fixture._load("contest.json")["contest"]["name"]
    before = db_conn.execute(_LIVE, {"n": work}).one().id
    first = fixture.reset_pick_journey(db_conn, "desktop")
    entry = text(
        "INSERT INTO contest_entries (user_id, contest_id, game_id, contest_line_id, side)"
        " SELECT c.user_id, c.id, l.game_id, l.id, 'home' FROM contest_lines l"
        " JOIN contests c ON c.id = l.contest_id WHERE c.id = :c LIMIT 1"
    )
    db_conn.execute(entry, {"c": first})

    second = fixture.reset_pick_journey(db_conn, "desktop")

    assert second != first
    assert db_conn.execute(_LIVE, {"n": "Pick journey (desktop)"}).one().id == second
    gone = text("SELECT deleted_at IS NOT NULL FROM contests WHERE id = :c")
    assert db_conn.execute(gone, {"c": first}).scalar_one()
    count = text(
        "SELECT count(*) FROM contest_entries WHERE contest_id = :c AND deleted_at IS NULL"
    )
    assert db_conn.execute(count, {"c": second}).scalar_one() == 0
    # the default contest is untouched
    assert db_conn.execute(_LIVE, {"n": work}).one().id == before


@pytest.mark.parametrize("project", ["", "Phone", "phone desktop", "../x"])
def test_a_pick_reset_refuses_a_project_name_that_isnt_a_plain_word(
    db_conn: Connection, project: str
):
    with pytest.raises(ValueError, match="project"):
        fixture.reset_pick_journey(db_conn, project)


def test_the_pick_journey_refuses_under_live(monkeypatch: pytest.MonkeyPatch):
    from db.config import UnsafeDatabaseError

    monkeypatch.setenv("LIVE", "true")
    opened = []
    monkeypatch.setattr(fixture, "make_engine", lambda *a, **k: opened.append(a))
    with pytest.raises(UnsafeDatabaseError):
        fixture.pick_journey("phone")
    assert opened == []
