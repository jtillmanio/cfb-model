-- team_rankings: each FBS team's rank entering a week and how far it moved since the week
-- before (TASK-035, D-136, docs/03-data-model.md › Views).
--
-- Both weeks come from latest_team_ratings (each week's newest succeeded run of the version).
-- rank_change = previous_rank - rank, so a team that climbed is positive; both are NULL entering
-- week 1, or when the team had no FBS rank the week before. Never stored (hard rule 1).
CREATE OR REPLACE VIEW team_rankings AS
SELECT
    c.model_version_id,
    c.model_run_id,
    c.season,
    c.week,
    c.team_id,
    c.as_of,
    c.rating,
    c.off_rating,
    c.def_rating,
    c.st_rating,
    c.prior_weight,
    c.rank,
    p.rank AS previous_rank,
    p.rank - c.rank AS rank_change
FROM latest_team_ratings c
LEFT JOIN latest_team_ratings p
    ON p.model_version_id = c.model_version_id
    AND p.season = c.season
    AND p.week = c.week - 1
    AND p.team_id = c.team_id
WHERE c.fbs;
