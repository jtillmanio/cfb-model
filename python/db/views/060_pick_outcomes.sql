-- pick_outcomes: every pick graded against the line it was made at, with its CLV (TASK-041,
-- D-132, docs/04-model.md § 9.3, docs/03-data-model.md › Views). Never stored (hard rule 1).
--
-- One row per spread pick made before the game's cutoff, superseded ones too (passes have no side
-- to grade); is_current marks the row current_picks shows (ranked the same way, over the same
-- rows: see 050_current_picks.sql), the only one model_record counts. A row written after the
-- cutoff is left out (hard rule 4, D-142). The home side covers when margin + line > 0, a push
-- at 0.
--   result: won | lost | push on a final game; pending while it is scheduled or in progress;
--           void when it is canceled or postponed.
--   units:  priced at the pick's price for its stake (−110: a win +1.0u, a loss −1.1u); a push
--           and a void 0, pending NULL. risked is what a win or a loss put at risk (1.1u at −110),
--           0 for a push or a void (refunded), so ROI = units ÷ risked (D-132).
--   clv:    the line picked at against game_market's closing line, in points for the side picked:
--           line − close for a home pick, close − line for an away pick, so a home pick at −2.5
--           that closed −3.5 is +1.0 and an away pick there −1.0. NULL until the close exists
--           (game_market's cutoff, D-120). clv_so_far is the same against the current line.
--   edge_bucket: 04 § 9.4's pick buckets on abs(edge_pts), lower bound in, '<2.5' below the
--           lowest; display only (D-077).
-- The window partition holds game_id and model_version_id, so a read filtered by either is
-- applied at the picks scan, below the window, and game_market is read for those games alone.
CREATE OR REPLACE VIEW pick_outcomes AS
SELECT
    p.id AS pick_id,
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
    p.created_at,
    p.newest = 1 AS is_current,
    CASE
        WHEN abs(p.edge_pts) >= 7.0 THEN '7.0+'
        WHEN abs(p.edge_pts) >= 5.0 THEN '5.0-7.0'
        WHEN abs(p.edge_pts) >= 3.5 THEN '3.5-5.0'
        WHEN abs(p.edge_pts) >= 2.5 THEN '2.5-3.5'
        ELSE '<2.5'
    END AS edge_bucket,
    g.season,
    g.season_type,
    g.week,
    g.status AS game_status,
    g.home_points - g.away_points AS margin,
    r.result,
    CASE r.result
        WHEN 'won' THEN o.to_win
        WHEN 'lost' THEN -o.at_risk
        WHEN 'pending' THEN NULL
        ELSE 0
    END AS units,
    CASE r.result
        WHEN 'won' THEN o.at_risk
        WHEN 'lost' THEN o.at_risk
        WHEN 'pending' THEN NULL
        ELSE 0
    END AS risked,
    gm.closing_spread_home,
    gm.current_spread_home,
    o.sign * (p.line - gm.closing_spread_home) AS clv,
    o.sign * (p.line - gm.current_spread_home) AS clv_so_far
FROM (
    SELECT
        p.*,
        s.line_source,
        row_number() OVER (
            PARTITION BY p.game_id, p.model_version_id, p.market, s.line_source
            ORDER BY p.created_at DESC, p.id DESC
        ) AS newest
    FROM picks p
    JOIN games gk ON gk.id = p.game_id
    CROSS JOIN LATERAL (
        SELECT CASE WHEN p.line_snapshot_id IS NOT NULL THEN 'market' END AS line_source
    ) s
    WHERE p.market = 'spread'
        AND p.created_at < coalesce(
            gk.kickoff_at, (gk.game_date + 1)::timestamp AT TIME ZONE 'America/New_York'
        )
) p
JOIN games g ON g.id = p.game_id
JOIN game_market gm ON gm.game_id = p.game_id
CROSS JOIN LATERAL (
    SELECT
        CASE p.side WHEN 'home' THEN 1 ELSE -1 END AS sign,
        -- A price of −110 risks 1.1 to win 1; +150 risks 1 to win 1.5.
        p.stake_units::numeric * CASE WHEN p.price < 0 THEN 1 ELSE p.price / 100.0 END AS to_win,
        p.stake_units::numeric * CASE WHEN p.price < 0 THEN -p.price / 100.0 ELSE 1 END AS at_risk
) o
CROSS JOIN LATERAL (
    SELECT CASE
        WHEN g.status IN ('canceled', 'postponed') THEN 'void'
        WHEN g.status <> 'final' THEN 'pending'
        WHEN o.sign * (g.home_points - g.away_points + p.line) > 0 THEN 'won'
        WHEN o.sign * (g.home_points - g.away_points + p.line) < 0 THEN 'lost'
        ELSE 'push'
    END AS result
) r
WHERE p.side IS NOT NULL;
