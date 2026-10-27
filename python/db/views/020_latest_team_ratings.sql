-- latest_team_ratings: each team's rating entering a week from its version's newest succeeded
-- run, and its rank among that week's FBS teams (TASK-035, D-136, docs/03-data-model.md › Views).
--
-- A version can have several runs for one week (a re-run inserts new rows, hard rule 2); the
-- newest succeeded one by finished_at, then id, is the one read. fbs is the team's division
-- that season (false with no team_seasons row); rank is NULL for a team that isn't FBS, and ties
-- share a rank (RANK: 1, 2, 2, 4). The rank partition holds model_version_id, season and week,
-- so a read filtered by them reads only that week's rows, through the
-- (model_version_id, season, week) index.
CREATE OR REPLACE VIEW latest_team_ratings AS
SELECT
    t.model_version_id,
    t.model_run_id,
    t.season,
    t.week,
    t.team_id,
    t.as_of,
    t.rating,
    t.off_rating,
    t.def_rating,
    t.st_rating,
    t.prior_weight,
    coalesce(ts.division = 'fbs', false) AS fbs,
    CASE WHEN coalesce(ts.division = 'fbs', false) THEN
        rank() OVER (
            PARTITION BY t.model_version_id, t.season, t.week, coalesce(ts.division = 'fbs', false)
            ORDER BY t.rating DESC
        )
    END AS rank
FROM team_ratings t
LEFT JOIN team_seasons ts ON ts.team_id = t.team_id AND ts.season = t.season
WHERE t.model_run_id = (
    SELECT r.id
    FROM model_runs r
    WHERE r.model_version_id = t.model_version_id
        AND r.season = t.season
        AND r.week = t.week
        AND r.status = 'succeeded'
    ORDER BY r.finished_at DESC NULLS LAST, r.id DESC
    LIMIT 1
);
