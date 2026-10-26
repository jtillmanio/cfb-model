"""College football's rules for the power ratings (TASK-033; docs/04-model.md § 2 Rung 1, D-047).

- **FCS pool.** The lake holds only games with an FBS team, so an FCS team has one or two games a
  season: too few to rate on its own. Every FCS team is rated as one pooled team instead, which
  keeps those games from distorting FBS ratings while still counting what they say about the FBS
  side. A team with no classification is rated on its own.
- **Newcomers.** A team with no rating last season starts from the FCS pool's prior: every team
  that joined FBS since 2014 moved up from FCS.
- **Season of a date.** A season runs from late August to the January bowls, so a date from July
  on belongs to that year's season and an earlier one to the year before's.
"""

from __future__ import annotations

from datetime import datetime

from engine.models.power import Rules

FCS = "fcs"


def pool_of(classification: str | None) -> str | None:
    """The pool a team is rated in, or None for a team rated on its own."""
    if classification is None or classification == "fbs":
        return None
    return FCS


def season_of(as_of: datetime) -> int:
    return as_of.year if as_of.month >= 7 else as_of.year - 1


RULES = Rules(pool=pool_of, season=season_of, newcomer_pool=FCS)
