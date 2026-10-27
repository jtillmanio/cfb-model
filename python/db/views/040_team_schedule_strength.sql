-- team_schedule_strength: each team's strength of schedule entering a week, and its rank among
-- FBS teams (TASK-035, D-136, docs/04-model.md § 10.5, docs/03-data-model.md › Views).
--
-- The games are the team's final games of the season that finished by the run's as_of: kickoff
-- (or, when TBA, the end of game_date in Eastern time) plus four hours, the rule the model's fit
-- uses (D-127). Each counts the opponent's rating in the same run, adjusted for site with the
-- run's learned home field (fitted_params.home_field): + HFA when the opponent was at home, - HFA
-- when the team was, nothing at a neutral site. sos is their mean; NULL with no game played, or
-- when an opponent has no rating in the run or the run has no home field to adjust a home game.
-- sos_rank 1 is the hardest schedule; only FBS teams with an SOS are ranked. Never stored
-- (hard rule 1).
CREATE OR REPLACE VIEW team_schedule_strength AS
SELECT
    s.model_version_id,
    s.model_run_id,
    s.season,
    s.week,
    s.team_id,
    s.as_of,
    s.games_played,
    s.sos,
    CASE WHEN s.fbs AND s.sos IS NOT NULL THEN
        rank() OVER (
            PARTITION BY s.model_version_id, s.season, s.week, s.fbs AND s.sos IS NOT NULL
            ORDER BY s.sos DESC
        )
    END AS sos_rank
FROM (
    SELECT
        t.model_version_id,
        t.model_run_id,
        t.season,
        t.week,
        t.team_id,
        t.as_of,
        t.fbs,
        count(p.opponent_id) AS games_played,
        CASE WHEN count(p.opponent_id) > 0 AND count(adjusted.rating) = count(p.opponent_id)
            THEN avg(adjusted.rating)
        END AS sos
    FROM latest_team_ratings t
    JOIN model_runs r ON r.id = t.model_run_id
    JOIN model_versions v ON v.id = t.model_version_id
    CROSS JOIN LATERAL (
        SELECT (r.fitted_params ->> 'home_field')::double precision AS points
    ) hfa
    LEFT JOIN (
        SELECT
            g.sport_id,
            g.season,
            side.team_id,
            side.opponent_id,
            side.site,
            coalesce(
                g.kickoff_at, (g.game_date + 1)::timestamp AT TIME ZONE 'America/New_York'
            ) AS kickoff
        FROM games g
        CROSS JOIN LATERAL (
            VALUES
                (g.home_team_id, g.away_team_id, CASE WHEN g.neutral_site THEN 'neutral' ELSE 'home' END),
                (g.away_team_id, g.home_team_id, CASE WHEN g.neutral_site THEN 'neutral' ELSE 'away' END)
        ) side (team_id, opponent_id, site)
        WHERE g.status = 'final'
    ) p
        ON p.sport_id = v.sport_id
        AND p.season = t.season
        AND p.team_id = t.team_id
        AND p.kickoff + interval '4 hours' <= t.as_of
    LEFT JOIN team_ratings o
        ON o.model_run_id = t.model_run_id
        AND o.team_id = p.opponent_id
        AND o.season = t.season
        AND o.week = t.week
    CROSS JOIN LATERAL (
        SELECT o.rating + CASE p.site
            WHEN 'neutral' THEN 0
            WHEN 'home' THEN -hfa.points
            ELSE hfa.points
        END AS rating
    ) adjusted
    GROUP BY
        t.model_version_id, t.model_run_id, t.season, t.week, t.team_id, t.as_of, t.fbs
) s;
