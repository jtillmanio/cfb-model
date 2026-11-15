-- current_contest_lines: each live contest's line per game now, beside the market's and the
-- model's (TASK-068, D-171, docs/03-data-model.md › Views). Never stored (hard rule 1).
--
-- One row per (contest, game): the newest contest_lines snapshot captured before the game's cutoff
-- (kickoff_at, or the end of game_date in Eastern time when the kickoff is TBA, as current_picks),
-- so a snapshot pasted after kickoff changes nothing. A soft-deleted contest has no rows.
--   market_spread_home: game_market's current spread (D-120, D-162).
--   model_*: the shown version's newest prediction for the game from a succeeded run before the
--           cutoff. The shown version is the shell's rule (api/shell.py SHOWN) for the game's
--           sport and season: production, else the newest candidate with a succeeded scheduled
--           run that season. model_spread_home is −pred_margin, the line the model would set.
--           NULL with no such version or prediction (an NFL game: no model yet, D-170).
-- Each lateral reads only the contest's or the game's own rows, so a read filtered by contest_id
-- reads that contest's lines through (contest_id, game_id, captured_at).
CREATE OR REPLACE VIEW current_contest_lines AS
SELECT
    c.id AS contest_id,
    c.user_id,
    l.period,
    l.game_id,
    l.id AS contest_line_id,
    l.spread_home,
    l.captured_at,
    l.source,
    gm.current_spread_home AS market_spread_home,
    gm.current_captured_at AS market_captured_at,
    m.model_version_id,
    m.prediction_id,
    m.pred_margin,
    -m.pred_margin AS model_spread_home
FROM contests c
CROSS JOIN LATERAL (
    SELECT DISTINCT ON (l.game_id) l.*
    FROM contest_lines l
    JOIN games g ON g.id = l.game_id
    WHERE l.contest_id = c.id
        AND l.captured_at < coalesce(
            g.kickoff_at, (g.game_date + 1)::timestamp AT TIME ZONE 'America/New_York'
        )
    ORDER BY l.game_id, l.captured_at DESC, l.id DESC
) l
JOIN games g ON g.id = l.game_id
JOIN game_market gm ON gm.game_id = l.game_id
LEFT JOIN LATERAL (
    SELECT p.model_version_id, p.id AS prediction_id, p.pred_margin
    FROM (
        SELECT v.id
        FROM model_versions v
        WHERE v.sport_id = g.sport_id
            AND v.market = 'spread'
            AND v.deleted_at IS NULL
            AND (
                v.status = 'production'
                OR (
                    v.status = 'candidate'
                    AND EXISTS (
                        SELECT 1
                        FROM model_runs r
                        WHERE r.model_version_id = v.id
                            AND r.run_type = 'scheduled'
                            AND r.status = 'succeeded'
                            AND r.season = g.season
                    )
                )
            )
        ORDER BY v.status = 'production' DESC, v.created_at DESC, v.id DESC
        LIMIT 1
    ) shown
    JOIN predictions p ON p.model_version_id = shown.id AND p.game_id = g.id
    JOIN model_runs r ON r.id = p.model_run_id AND r.status = 'succeeded'
    WHERE p.created_at < coalesce(
        g.kickoff_at, (g.game_date + 1)::timestamp AT TIME ZONE 'America/New_York'
    )
    ORDER BY p.created_at DESC, p.id DESC
    LIMIT 1
) m ON true
WHERE c.deleted_at IS NULL;
