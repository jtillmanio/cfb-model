-- team_rankings: each FBS team's rank entering a week and how far it moved since the week
-- before (TASK-035, D-136, docs/03-data-model.md › Views).
--
-- Both weeks come from latest_team_ratings (each week's newest succeeded run of the version).
-- The week before is week - 1 of the same season type, except entering postseason week 1 (every
-- bowl and CFP game, TASK-047, D-150): there it is the last regular week the version has a
-- succeeded run of, so the bowl ranks show the moves of championship week and Army-Navy.
-- rank_change = previous_rank - rank, so a team that climbed is positive; both are NULL entering
-- regular week 1, or when the team had no FBS rank the week before. season_type is the last
-- column because CREATE OR REPLACE VIEW can only add columns at the end. Never stored (hard
-- rule 1).
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
    p.rank - c.rank AS rank_change,
    c.season_type
FROM latest_team_ratings c
CROSS JOIN LATERAL (
    SELECT
        CASE WHEN c.season_type = 'postseason' AND c.week = 1 THEN 'regular'
            ELSE c.season_type
        END AS season_type,
        CASE WHEN c.season_type = 'postseason' AND c.week = 1 THEN (
            SELECT max(r.week)
            FROM model_runs r
            WHERE r.model_version_id = c.model_version_id
                AND r.season = c.season
                AND r.season_type = 'regular'
                AND r.status = 'succeeded'
                AND r.run_type IN ('scheduled', 'adhoc')
        ) ELSE c.week - 1 END AS week
) before
-- Lateral, so the week before is a parameter of the lookup. The planner may still read it
-- through the version's season in the (model_version_id, season, season_type, week) index (CI's
-- does).
LEFT JOIN LATERAL (
    SELECT prev.rank
    FROM latest_team_ratings prev
    WHERE prev.model_version_id = c.model_version_id
        AND prev.season = c.season
        AND prev.season_type = before.season_type
        AND prev.week = before.week
        AND prev.team_id = c.team_id
) p ON true
WHERE c.fbs;
