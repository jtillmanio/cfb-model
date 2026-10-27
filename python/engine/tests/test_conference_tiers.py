"""College football's conference tiers (TASK-036; docs/04-model.md § 10.4): Power 4, G5 or FCS
for each team-season, the Pac-12 a power conference through 2023, Notre Dame Power 4 every
season, and `engine tiers` checking a lake's staged team-seasons.
"""

from __future__ import annotations

import pytest
from lake_fixture import engine, write_backtest_seasons

from engine import backtest
from engine.ingest.lake import LocalLake
from engine.sports.cfb.teams import (
    FCS_TIER,
    G5,
    NOTRE_DAME,
    POWER_4,
    UnmappedConferenceError,
    tier_of,
)
from engine.transform import rebuild

OREGON, OREGON_STATE, BYU = 2483, 204, 252  # CFBD team ids


@pytest.mark.parametrize("conference", ["ACC", "Big 12", "Big Ten", "SEC"])
def test_the_power_conferences_are_power_4_every_season(conference: str) -> None:
    assert {tier_of(s, 1, conference, "fbs") for s in range(2014, 2027)} == {POWER_4}


@pytest.mark.parametrize(
    "conference",
    ["American Athletic", "Conference USA", "Mid-American", "Mountain West", "Sun Belt"],
)
def test_the_group_of_five_is_g5(conference: str) -> None:
    assert tier_of(2019, 1, conference, "fbs") == G5


def test_the_pac_12_is_power_4_through_2023_and_its_members_follow_their_new_conference() -> None:
    assert tier_of(2014, OREGON, "Pac-12", "fbs") == POWER_4
    assert tier_of(2023, OREGON, "Pac-12", "fbs") == POWER_4
    assert tier_of(2023, OREGON_STATE, "Pac-12", "fbs") == POWER_4
    # 2024: Oregon is in the Big Ten; Oregon State stays in a two-team Pac-12, now G5.
    assert tier_of(2024, OREGON, "Big Ten", "fbs") == POWER_4
    assert tier_of(2024, OREGON_STATE, "Pac-12", "fbs") == G5


def test_notre_dame_is_power_4_every_season_and_other_independents_are_g5() -> None:
    assert {tier_of(s, NOTRE_DAME, "FBS Independents", "fbs") for s in range(2014, 2027)} == {
        POWER_4
    }
    assert tier_of(2019, BYU, "FBS Independents", "fbs") == G5
    assert tier_of(2023, BYU, "Big 12", "fbs") == POWER_4


@pytest.mark.parametrize("classification", ["fcs", "ii", "iii", None])
def test_every_lower_division_team_is_fcs(classification: str | None) -> None:
    assert tier_of(2019, 1, "Big Sky", classification) == FCS_TIER


@pytest.mark.parametrize("conference", ["Big East", None])
def test_an_fbs_conference_without_a_tier_is_an_error(conference: str | None) -> None:
    with pytest.raises(UnmappedConferenceError, match="has no tier"):
        tier_of(2019, 1, conference, "fbs")


def test_a_results_row_is_labelled_by_its_matchup() -> None:
    row = {"season": 2023, "home_source_id": "2483", "away_source_id": "87"}
    assert backtest.matchup_tier(row | {"home_group": "Pac-12", "away_group": None}) == (
        "Power 4 vs Power 4"
    )
    assert backtest.matchup_tier(row | {"home_group": "Sun Belt", "away_group": None}) == (
        "Power 4 vs G5"
    )
    assert backtest.matchup_tier({**row, "away_source_id": "1"}) == backtest.UNMAPPED


def test_engine_tiers_maps_every_staged_fbs_team_season(
    empty_lake: LocalLake, capsys: pytest.CaptureFixture[str]
) -> None:
    write_backtest_seasons(empty_lake)
    rebuild(empty_lake)
    capsys.readouterr()

    assert engine("tiers", "--seasons", "2022-2023") == 0

    out = capsys.readouterr().out
    assert "18 FBS team-seasons 2022-2023:" in out  # the nine FBS fixture teams, two seasons
    assert f"{POWER_4}: 8" in out  # Iowa State, Kansas State, Kansas (Big 12), Stanford (ACC)
    assert f"{G5}: 10" in out  # UNLV, Fresno State, Hawai'i (MWC), WKU, Sam Houston (C-USA)
    assert "0 unmapped" in out


def test_engine_tiers_fails_on_an_unmapped_conference(
    empty_lake: LocalLake, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    write_backtest_seasons(empty_lake)
    rebuild(empty_lake)
    known = tier_of

    def without_cusa(season: int, team: int, conf: str | None, cls: str | None) -> str:
        if conf == "Conference USA":
            raise UnmappedConferenceError(f"team {team} in {season}: {conf!r} has no tier")
        return known(season, team, conf, cls)

    monkeypatch.setattr("engine.sports.cfb.teams.tier_of", without_cusa)
    capsys.readouterr()

    assert engine("tiers", "--seasons", "2023-2023") == 1

    out = capsys.readouterr().out
    assert "2 unmapped" in out
    assert "(Conference USA)" in out
