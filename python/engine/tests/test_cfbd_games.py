"""Mapping a CFBD /games response to reference rows (no network, no database).

The sample's first row is the real 2025 week 1 Ohio State–Texas row from CFBD v2 (trimmed to the
fields we read). Rows 2–3 are built in the same shape for cases a completed week can't show:
a TBA kickoff, and a neutral-site game with no venue against an FCS team with no conference.
"""

import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest

from engine.sports.cfb.games import map_games

SAMPLE = json.loads(
    (Path(__file__).parent / "fixtures" / "cfbd_games_sample.json").read_text(encoding="utf-8")
)


def test_maps_every_game_and_dedupes_teams_and_venues():
    batch = map_games(SAMPLE)
    assert [g.source_id for g in batch.games] == ["401752677", "401752900", "401752901"]
    # Utah plays twice in the sample; each team appears once.
    assert {t.source_id for t in batch.teams} == {"194", "251", "254", "2534", "2700"}
    assert len(batch.teams) == 5
    assert {v.source_id for v in batch.venues} == {"3861", "3958"}


def test_final_game_keeps_score_kickoff_and_conference_by_season():
    batch = map_games(SAMPLE)
    osu = batch.games[0]
    assert osu.status == "final"
    assert (osu.home_points, osu.away_points) == (14, 7)
    assert osu.kickoff_at == datetime(2025, 8, 30, 16, 0, tzinfo=UTC)
    assert osu.game_date == date(2025, 8, 30)
    assert (osu.home_source_id, osu.away_source_id, osu.venue_source_id) == ("194", "251", "3861")
    seasons = {(s.team_source_id, s.season): s for s in batch.team_seasons}
    assert seasons[("194", 2025)].conference == "Big Ten"
    assert seasons[("194", 2025)].division == "fbs"


def test_tba_kickoff_is_null_and_game_date_is_the_eastern_calendar_date():
    tba = map_games(SAMPLE).games[1]
    assert tba.kickoff_at is None
    # 04:00Z on Aug 30 is midnight Eastern on Aug 30, not Aug 29.
    assert tba.game_date == date(2025, 8, 30)
    assert tba.status == "scheduled"
    assert (tba.home_points, tba.away_points) == (None, None)


def test_evening_kickoff_uses_the_eastern_date_not_the_utc_date():
    late = map_games(SAMPLE).games[2]
    # 00:00Z on Aug 31 is 8 PM Eastern on Aug 30.
    assert late.game_date == date(2025, 8, 30)
    assert late.neutral_site is True
    assert late.venue_source_id is None


def test_unknown_conference_and_division_stay_null():
    seasons = {s.team_source_id: s for s in map_games(SAMPLE).team_seasons}
    assert seasons["2700"].conference is None
    assert seasons["2700"].division == "fcs"


def test_completed_game_without_a_score_is_rejected():
    broken = [{**SAMPLE[0], "homePoints": None}]
    with pytest.raises(ValueError, match="401752677"):
        map_games(broken)


def test_unscored_game_a_week_past_its_start_is_canceled():
    """TASK-044 (D-121, D-145): the transform's status rule. Unscored and uncompleted on a file
    saved `SETTLE` (7 days) after its start is canceled; inside the window, or with no save time,
    it stays scheduled."""
    unplayed = {**SAMPLE[0], "completed": False, "homePoints": None, "awayPoints": None}
    start = datetime(2025, 8, 30, 16, tzinfo=UTC)

    def status(**kwargs: datetime) -> str:
        return map_games([unplayed], **kwargs).games[0].status

    assert status(saved_at=start + timedelta(days=7)) == "canceled"
    assert status(saved_at=start + timedelta(days=6, hours=23)) == "scheduled"
    assert status() == "scheduled"
    assert map_games(SAMPLE, saved_at=start + timedelta(days=30)).games[0].status == "final"
