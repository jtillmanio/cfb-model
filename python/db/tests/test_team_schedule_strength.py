"""`team_schedule_strength` (TASK-035; docs/04-model.md § 10.5): each team's SOS entering a week,
the mean of its opponents' ratings in the same run over this season's games finished by the
run's `as_of`, adjusted for site with the run's home field, and its rank among FBS teams.

The constructed rows use the throwaway sport in `model_rows` and roll back (db_conn)."""

from __future__ import annotations

from typing import Any

import model_rows as m
import pytest
from sqlalchemy import Connection, text
from test_team_rankings import assert_index_reads

HFA = 3.0
AS_OF = m.utc(2030, 9, 26, 16)  # entering week 4


def _schedule(conn: Connection, home_field: float | None = HFA) -> dict[str, int]:
    """Team a's weeks 1-3: home to b, away at c, neutral against d (FCS); its week-4 game with
    e kicked off three hours before `AS_OF`, so it hasn't finished, and its game with e last
    season is another season's. g hasn't played."""
    m.sport(conn)
    ids = {s: m.team(conn, s) for s in "abceg"}
    ids["d"] = m.team(conn, "d", "fcs")
    m.game(conn, ids["e"], ids["a"], m.utc(2029, 9, 15, 20), week=3, season=m.SEASON - 1)
    m.game(conn, ids["a"], ids["b"], m.utc(2030, 9, 5, 20), week=1)
    m.game(conn, ids["c"], ids["a"], m.utc(2030, 9, 12, 20), week=2)
    m.game(conn, ids["a"], ids["d"], m.utc(2030, 9, 19, 20), week=3, neutral=True)
    m.game(conn, ids["a"], ids["e"], m.utc(2030, 9, 26, 13), week=4)
    v = m.version(conn)
    r = m.run(conn, v, 4, AS_OF, home_field=home_field)
    ratings = {"a": 2.0, "b": 10.0, "c": 4.0, "d": -2.0, "e": 100.0, "g": 0.0}
    m.ratings(conn, r, v, 4, AS_OF, {ids[t]: rating for t, rating in ratings.items()})
    return ids | {"version": v}


def _sos(conn: Connection, ids: dict[str, int]) -> dict[str, dict[str, Any]]:
    rows = conn.execute(
        text(
            "SELECT * FROM team_schedule_strength"
            " WHERE model_version_id = :v AND season = :season AND week = 4"
        ),
        {"v": ids["version"], "season": m.SEASON},
    )
    names = {team_id: name for name, team_id in ids.items()}
    return {names[r.team_id]: dict(r._mapping) for r in rows}


def test_sos_adjusts_for_site(db_conn: Connection):
    """AC-3: b was at a's home (b − HFA), c hosted a (c + HFA), d was neutral (d)."""
    sos = _sos(db_conn, _schedule(db_conn))

    assert sos["a"]["games_played"] == 3
    assert sos["a"]["sos"] == pytest.approx(((10.0 - HFA) + (4.0 + HFA) + -2.0) / 3)
    assert sos["b"]["sos"] == pytest.approx(2.0 + HFA)
    assert sos["c"]["sos"] == pytest.approx(2.0 - HFA)
    assert sos["d"]["sos"] == pytest.approx(2.0)


def test_sos_rank(db_conn: Connection):
    """AC-3: rank 1 is the highest SOS; only FBS teams with a game played are ranked."""
    sos = _sos(db_conn, _schedule(db_conn))

    assert {t: (r["sos_rank"], r["games_played"]) for t, r in sos.items()} == {
        "b": (1, 1),
        "a": (2, 3),
        "c": (3, 1),
        "d": (None, 1),
        "e": (None, 0),
        "g": (None, 0),
    }
    assert sos["e"]["sos"] is None and sos["g"]["sos"] is None


def test_sos_needs_the_runs_home_field(db_conn: Connection):
    """With no learned home field, a game at a home site can't be adjusted: SOS is NULL rather
    than an average of the neutral games alone."""
    sos = _sos(db_conn, _schedule(db_conn, home_field=None))

    assert sos["a"]["sos"] is None and sos["b"]["sos"] is None
    assert sos["d"]["sos"] == pytest.approx(2.0)


def test_tba_game_finishes_four_hours_after_the_end_of_its_eastern_date(db_conn: Connection):
    """A TBA game on Fri 2030-09-27 kicks off at Sat 04:00Z for the cutoff, so it counts entering
    a week whose as_of is Sat 08:00Z, and not one at 07:00Z."""
    m.sport(db_conn)
    a, b = m.team(db_conn, "a"), m.team(db_conn, "b")
    m.game(db_conn, a, b, None, week=4, game_date="2030-09-27")
    v = m.version(db_conn)
    for week, hour in ((5, 7), (6, 8)):
        as_of = m.utc(2030, 9, 28, hour)
        r = m.run(db_conn, v, week, as_of)
        m.ratings(db_conn, r, v, week, as_of, {a: 1.0, b: 5.0})

    played = dict(
        db_conn.execute(
            text(
                "SELECT week, games_played FROM team_schedule_strength"
                " WHERE model_version_id = :v AND team_id = :a"
            ),
            {"v": v, "a": a},
        ).all()
    )

    assert played == {5: 0, 6: 1}


def test_single_team_read_uses_index(db_conn: Connection):
    """AC-4."""
    assert_index_reads(db_conn, "team_schedule_strength")
