"""`engine seed fixture` against a test DB seeded before the files changed (TASK-055): a model
version is reused, never changed, so a spec that moved since is refused by name, not kept."""

from __future__ import annotations

import copy

import pytest
from sqlalchemy import Connection, text

from engine import fixture


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
