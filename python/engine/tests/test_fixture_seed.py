"""`engine seed fixture` against a test DB seeded before the files changed (TASK-055): a model
version is reused, never changed, so a spec that moved since is refused by name, not kept."""

from __future__ import annotations

import copy

import pytest
from sqlalchemy import Connection

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
