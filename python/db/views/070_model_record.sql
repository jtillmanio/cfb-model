-- model_record: the model's record through each week of a season (TASK-041, D-132,
-- docs/04-model.md § 9.3, docs/03-data-model.md › Views). There is no grading job: this reads
-- pick_outcomes, so a corrected score or a canceled game regrades on the next read.
--
-- Only current market picks count (is_current), so a pick superseded before kickoff counts once,
-- at the current pick's line. Backtest records are never here (D-071). Every row names the week it
-- runs through (season_type, week; the postseason after the regular season):
--   breakdown 'week':    that week's games alone
--   breakdown 'to_date': the season's start through that week (the newest week is the season)
--   breakdown 'tier':    to date, one row per tier (tier NULL: a side stored with no tier)
--   breakdown 'bucket':  to date, one row per edge_bucket (display only, D-077)
-- Pushes count in W-L-P and earn 0; win_pct (0-100) leaves pushes and voids out; roi_pct is units
-- ÷ risked, a push refunded (D-132); avg_clv is over every non-void pick with a closing line.
-- One plain GROUP BY over the four breakdowns, not GROUPING SETS: Postgres pushes a filter on a
-- grouping column below a plain GROUP BY only, so a read filtered by version and season reads
-- that version's picks alone, through the (model_version_id, game_id) index.
CREATE OR REPLACE VIEW model_record AS
SELECT
    w.model_version_id,
    w.season,
    k.breakdown,
    w.season_type,
    w.week,
    CASE WHEN k.breakdown = 'tier' THEN o.tier END AS tier,
    CASE WHEN k.breakdown = 'bucket' THEN o.edge_bucket END AS edge_bucket,
    count(*) AS picks,
    count(*) FILTER (WHERE o.result = 'won') AS wins,
    count(*) FILTER (WHERE o.result = 'lost') AS losses,
    count(*) FILTER (WHERE o.result = 'push') AS pushes,
    count(*) FILTER (WHERE o.result = 'void') AS voids,
    count(*) FILTER (WHERE o.result = 'pending') AS pending,
    100.0 * count(*) FILTER (WHERE o.result = 'won')
        / nullif(count(*) FILTER (WHERE o.result IN ('won', 'lost')), 0) AS win_pct,
    coalesce(sum(o.units), 0) AS units,
    100 * sum(o.units) / nullif(sum(o.risked), 0) AS roi_pct,
    avg(o.clv) FILTER (WHERE o.result <> 'void') AS avg_clv
FROM (
    -- The weeks a version has current picks in.
    SELECT DISTINCT model_version_id, season, season_type, week
    FROM pick_outcomes
    WHERE is_current AND line_source = 'market'
) w
CROSS JOIN (VALUES ('week'), ('to_date'), ('tier'), ('bucket')) k (breakdown)
JOIN pick_outcomes o
    ON o.model_version_id = w.model_version_id
    AND o.season = w.season
    AND o.is_current
    AND o.line_source = 'market'
    AND CASE k.breakdown
        WHEN 'week' THEN (o.season_type, o.week) = (w.season_type, w.week)
        ELSE (o.season_type = 'postseason', o.week) <= (w.season_type = 'postseason', w.week)
    END
GROUP BY
    w.model_version_id,
    w.season,
    k.breakdown,
    w.season_type,
    w.week,
    CASE WHEN k.breakdown = 'tier' THEN o.tier END,
    CASE WHEN k.breakdown = 'bucket' THEN o.edge_bucket END;
