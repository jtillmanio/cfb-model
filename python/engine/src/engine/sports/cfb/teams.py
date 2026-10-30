"""College football's rules for the rating models (TASK-033, TASK-036; docs/04-model.md § 2 Rung 1
and Rung 2, § 10.4, D-047).

- **FCS pool.** The lake holds only games with an FBS team, so an FCS team has one or two games a
  season: too few to rate on its own. Every FCS team is rated as one pooled team instead, which
  keeps those games from distorting FBS ratings while still counting what they say about the FBS
  side. A team with no classification is pooled too: in a lake of games with an FBS team, the
  unlabelled side is the lower-division one.
- **Newcomers.** A team with no rating last season starts from the FCS pool's prior: every team
  that joined FBS since 2014 moved up from FCS.
- **Season of a date.** A season runs from late August to the January bowls, so a date from July
  on belongs to that year's season and an earlier one to the year before's.
- **Tiers** (Rung 2's `shrink_toward: tier`, 04 § 10.4). Each team-season is Power 4, G5 or FCS,
  by its conference that season: a school that changed conference follows its new one from its
  first season there. The Pac-12 is a power conference through 2023, the last season before ten
  of its twelve members left; from 2024 it's G5. Notre Dame, an independent, is Power 4 every
  season. A FBS conference the map doesn't know is an error, not a guess.
"""

from __future__ import annotations

from datetime import datetime

from engine.core.interfaces import GameContext
from engine.models import efficiency, power

FCS = "fcs"

POWER_4 = "Power 4"
G5 = "G5"
FCS_TIER = "FCS"
TIERS = (POWER_4, G5, FCS_TIER)

_POWER = frozenset({"ACC", "Big 12", "Big Ten", "SEC"})
_G5 = frozenset(
    {
        "American Athletic",
        "Conference USA",
        "FBS Independents",
        "Mid-American",
        "Mountain West",
        "Sun Belt",
    }
)
PAC_12 = "Pac-12"
PAC_12_LAST_POWER = 2023
NOTRE_DAME = 87  # CFBD's team id


class UnmappedConferenceError(ValueError):
    """An FBS team-season whose conference the tier map doesn't know."""


def pool_of(classification: str | None) -> str | None:
    """The pool a team is rated in, or None for a team rated on its own."""
    return None if classification == "fbs" else FCS


def pickable(game: GameContext) -> bool:
    """Whether a game may be picked: both teams FBS. A game with an FCS (or unlabelled) team is
    rated but never picked (D-047)."""
    return pool_of(game.home_classification) is None and pool_of(game.away_classification) is None


def season_of(as_of: datetime) -> int:
    return as_of.year if as_of.month >= 7 else as_of.year - 1


def tier_of(season: int, team: int, conference: str | None, classification: str | None) -> str:
    """The team's tier that season: Power 4, G5 or FCS."""
    if pool_of(classification) is not None:
        return FCS_TIER
    if team == NOTRE_DAME or conference in _POWER:
        return POWER_4
    if conference == PAC_12:
        return POWER_4 if season <= PAC_12_LAST_POWER else G5
    if conference in _G5:
        return G5
    raise UnmappedConferenceError(
        f"team {team} in {season}: FBS conference {conference!r} has no tier "
        "(add it to engine.sports.cfb.teams)"
    )


RULES = power.Rules(pool=pool_of, season=season_of, newcomer_pool=FCS)
EFFICIENCY_RULES = efficiency.Rules(
    pool=pool_of, season=season_of, newcomer_pool=FCS, tier=tier_of, pool_tier=FCS_TIER
)
