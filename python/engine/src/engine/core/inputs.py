"""The input registry: every metric a `ModelSpec` can use, described once (docs/04-model.md
§ 10.6, D-117). The Lab's builder and weights view, the inputs explainer and every unit display
read labels and definitions from here, and a spec input must name an id in it.

It starts with the v1 inputs (§ 10.2): EPA/play and success rate, overall, rushing and passing.
M18.1 adds the rest of the catalog. Each id is one metric and split, so a split-only metric
(yards per carry) is just another id; offense and defense are rated from the same metric, so the
side isn't in the id. `feature` is the column stem in `team_week_features`: the offense column is
`off_<feature>` and the defense column `def_<feature>`.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
Id = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]*$")]


class InputDef(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: Id
    label: Text
    definition: Text  # plain English, shown beside the input in the Lab
    unit: Text
    better: Literal["higher", "lower"]  # for the offense; a defense is better allowing less
    source: Text
    feature: Id
    garbage_time: Literal["excluded", "included"]
    first_season: int = Field(ge=1869)  # first season the lake holds it
    noisy: bool  # labeled noisy in the UI (04 § 10.1)


# CFBD calls EPA "PPA" (predicted points added); its advanced stats come with garbage time
# filtered out, and TASK-018 pulls only that variant. The lake starts in 2014.
_ADVANCED = "CFBD advanced season stats by game (garbage time excluded)"

INPUTS: tuple[InputDef, ...] = (
    InputDef(
        id="epa_per_play",
        label="EPA/play",
        definition=(
            "Expected points added per play: how much each play changed the offense's "
            "expected points, averaged over every play."
        ),
        unit="points per play",
        better="higher",
        source=_ADVANCED,
        feature="ppa",
        garbage_time="excluded",
        first_season=2014,
        noisy=False,
    ),
    InputDef(
        id="rush_epa_per_play",
        label="Rush EPA/play",
        definition="Expected points added per rushing play.",
        unit="points per play",
        better="higher",
        source=_ADVANCED,
        feature="rush_ppa",
        garbage_time="excluded",
        first_season=2014,
        noisy=False,
    ),
    InputDef(
        id="pass_epa_per_play",
        label="Pass EPA/play",
        definition="Expected points added per passing play.",
        unit="points per play",
        better="higher",
        source=_ADVANCED,
        feature="pass_ppa",
        garbage_time="excluded",
        first_season=2014,
        noisy=False,
    ),
    InputDef(
        id="success_rate",
        label="Success rate",
        definition=(
            "Share of plays that kept the offense on schedule: at least half the yards to go "
            "on first down, 70% on second down, all of them on third or fourth down."
        ),
        unit="share of plays",
        better="higher",
        source=_ADVANCED,
        feature="success_rate",
        garbage_time="excluded",
        first_season=2014,
        noisy=False,
    ),
    InputDef(
        id="rush_success_rate",
        label="Rush success rate",
        definition="Success rate on rushing plays.",
        unit="share of plays",
        better="higher",
        source=_ADVANCED,
        feature="rush_success_rate",
        garbage_time="excluded",
        first_season=2014,
        noisy=False,
    ),
    InputDef(
        id="pass_success_rate",
        label="Pass success rate",
        definition="Success rate on passing plays.",
        unit="share of plays",
        better="higher",
        source=_ADVANCED,
        feature="pass_success_rate",
        garbage_time="excluded",
        first_season=2014,
        noisy=False,
    ),
)

INPUT_IDS: tuple[str, ...] = tuple(d.id for d in INPUTS)
