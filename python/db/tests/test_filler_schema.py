"""The Week 6 filler games (TASK-055): week6_filler.json is what its generator writes, and the
seeded week holds the 54 games of "54 games · 9 picks" without moving anything the design fixes
(docs/02-architecture.md › Seed data)."""

from __future__ import annotations

import importlib.util
import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Connection, text

from db.config import repo_root

SEEDS = repo_root() / "python" / "db" / "seeds" / "fixture"
SLATE_NOW = datetime(2026, 10, 10, 18, 15, tzinfo=UTC)  # Sat 2:15 PM ET


def _file(name: str) -> dict[str, Any]:
    return json.loads((SEEDS / name).read_text("utf-8"))


def test_week6_filler_json_is_what_the_generator_writes():
    spec = importlib.util.spec_from_file_location("generate_filler", SEEDS / "generate_filler.py")
    assert spec is not None and spec.loader is not None
    generator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(generator)
    assert generator.build() == _file("week6_filler.json")


def test_the_filler_ratings_stay_below_utah_and_tie_no_team():
    ratings = _file("models.json")["ratings"]
    filler = {r["team"]: r["by_week"] for r in _file("week6_filler.json")["ratings"]}
    assert len(filler) == 62
    for i, _week in enumerate(ratings["weeks"]):
        assert all(r[i] < ratings["teams"]["utah"][i] for r in filler.values())
        # A filler rating ties no other team (the seed's own BYU and Iowa share 9.6 entering
        # week 4).
        new = [r[i] for r in filler.values()]
        assert len(set(new)) == len(new)
        assert not set(new) & {r[i] for r in ratings["teams"].values()}


def test_every_filler_game_is_still_to_play_at_the_slate_time():
    for g in _file("week6_filler.json")["games"]:
        assert g["status"] == "scheduled"
        assert (g["away_points"], g["home_points"]) == (None, None)
        assert datetime.fromisoformat(g["kickoff_at"]) > SLATE_NOW


def test_week_6_has_54_games_and_every_filler_edge_is_under_one(db_conn: Connection):
    rows = db_conn.execute(
        text(
            "SELECT g.source_id, p.pred_margin, m.current_spread_home"
            " FROM games g"
            " JOIN predictions p ON p.game_id = g.id"
            " JOIN model_versions v ON v.id = p.model_version_id"
            " JOIN game_market m ON m.game_id = g.id"
            " WHERE g.source = 'fixture' AND g.sport_id = 'cfb' AND g.season = 2026"
            " AND g.season_type = 'regular' AND g.week = 6 AND v.version = 'v1.0'"
            " AND m.current_spread_home IS NOT NULL"
        )
    ).all()
    assert len(rows) == 53  # every week-6 game but Furman @ Clemson has a current line
    total = db_conn.execute(
        text(
            "SELECT count(*) FROM games WHERE source = 'fixture' AND sport_id = 'cfb'"
            " AND season = 2026 AND season_type = 'regular' AND week = 6"
        )
    ).scalar_one()
    assert total == 54
    filler = {g["source_id"] for g in _file("week6_filler.json")["games"]}
    edges = {r.source_id: r.pred_margin + float(r.current_spread_home) for r in rows}
    assert set(edges) >= filler
    assert all(abs(edges[g]) < 1.0 for g in filler)
