-- current_picks: the model's pick on each game now (TASK-041, D-140, docs/03-data-model.md › Views).
--
-- The newest row per (game, model version, market, line source) by created_at, then id. A row is
-- written only when the side or tier changes, so the rows before it are superseded picks; a pass
-- row (no side) as the newest means no pick, and the game has no row here. line_source is
-- 'market' for a pick at a line snapshot (contest picks arrive with contest_lines, M6.1). Spread
-- only: nothing writes total or moneyline picks yet. The window partition holds game_id and
-- model_version_id, so a read filtered by either reads only those picks, through the
-- (game_id, model_version_id, created_at DESC) or (model_version_id, game_id) index.
CREATE OR REPLACE VIEW current_picks AS
SELECT
    p.id,
    p.prediction_id,
    p.model_version_id,
    p.game_id,
    p.line_snapshot_id,
    p.market,
    p.line_source,
    p.side,
    p.line,
    p.price,
    p.model_prob,
    p.edge_pts,
    p.expected_value,
    p.tier,
    p.stake_units,
    p.created_at
FROM (
    SELECT
        p.*,
        s.line_source,
        row_number() OVER (
            PARTITION BY p.game_id, p.model_version_id, p.market, s.line_source
            ORDER BY p.created_at DESC, p.id DESC
        ) AS newest
    FROM picks p
    CROSS JOIN LATERAL (
        SELECT CASE WHEN p.line_snapshot_id IS NOT NULL THEN 'market' END AS line_source
    ) s
    WHERE p.market = 'spread'
) p
WHERE p.newest = 1 AND p.side IS NOT NULL;
