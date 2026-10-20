-- game_market: each game's opening, current and closing line (TASK-020, docs/03-data-model.md › Views).
--
-- Each line is one group of line_snapshots rows with the same kind and captured_at (one pull
-- across books). Its spread and total come from the `consensus` book when it quoted that price,
-- else the median across the group's books; *_source says which, for the spread.
--   opening: the untimed `opening` rows, else the earliest snapshot.
--   current: the newest snapshot, else the `closing` rows, else the opening.
--   closing: NULL until the cutoff has passed. Then the untimed `closing` rows (CFBD's close),
--            else the last snapshot before the cutoff; closing_from says which.
-- The cutoff is kickoff_at, or the end of game_date in Eastern time when the kickoff is TBA.
-- Each lateral reads only the game's own rows, through the (game_id, captured_at) index.
CREATE OR REPLACE VIEW game_market AS
SELECT
    g.id AS game_id,
    o.spread_home AS opening_spread_home,
    o.total AS opening_total,
    o.source AS opening_source,
    o.captured_at AS opening_captured_at,
    c.spread_home AS current_spread_home,
    c.total AS current_total,
    c.source AS current_source,
    c.captured_at AS current_captured_at,
    cl.spread_home AS closing_spread_home,
    cl.total AS closing_total,
    cl.source AS closing_source,
    cl.captured_at AS closing_captured_at,
    cl.closing_from
FROM games g
CROSS JOIN LATERAL (
    SELECT coalesce(
        g.kickoff_at, (g.game_date + 1)::timestamp AT TIME ZONE 'America/New_York'
    ) AS at
) cutoff
LEFT JOIN LATERAL (
    SELECT
        ls.captured_at,
        coalesce(
            min(ls.spread_home) FILTER (WHERE b.source_id = 'consensus'),
            (percentile_cont(0.5) WITHIN GROUP (ORDER BY ls.spread_home))::numeric
        ) AS spread_home,
        coalesce(
            min(ls.total) FILTER (WHERE b.source_id = 'consensus'),
            (percentile_cont(0.5) WITHIN GROUP (ORDER BY ls.total))::numeric
        ) AS total,
        CASE
            WHEN count(ls.spread_home) FILTER (WHERE b.source_id = 'consensus') > 0 THEN 'consensus'
            WHEN count(ls.spread_home) > 0 THEN 'median'
        END AS source
    FROM line_snapshots ls
    JOIN sportsbooks b ON b.id = ls.book_id
    WHERE ls.game_id = g.id AND ls.kind IN ('opening', 'snapshot')
    GROUP BY ls.kind, ls.captured_at
    ORDER BY ls.kind = 'opening' DESC, ls.captured_at
    LIMIT 1
) o ON true
LEFT JOIN LATERAL (
    SELECT
        ls.captured_at,
        coalesce(
            min(ls.spread_home) FILTER (WHERE b.source_id = 'consensus'),
            (percentile_cont(0.5) WITHIN GROUP (ORDER BY ls.spread_home))::numeric
        ) AS spread_home,
        coalesce(
            min(ls.total) FILTER (WHERE b.source_id = 'consensus'),
            (percentile_cont(0.5) WITHIN GROUP (ORDER BY ls.total))::numeric
        ) AS total,
        CASE
            WHEN count(ls.spread_home) FILTER (WHERE b.source_id = 'consensus') > 0 THEN 'consensus'
            WHEN count(ls.spread_home) > 0 THEN 'median'
        END AS source
    FROM line_snapshots ls
    JOIN sportsbooks b ON b.id = ls.book_id
    WHERE ls.game_id = g.id
    GROUP BY ls.kind, ls.captured_at
    ORDER BY
        CASE ls.kind WHEN 'snapshot' THEN 0 WHEN 'closing' THEN 1 ELSE 2 END,
        ls.captured_at DESC
    LIMIT 1
) c ON true
LEFT JOIN LATERAL (
    SELECT
        ls.captured_at,
        coalesce(
            min(ls.spread_home) FILTER (WHERE b.source_id = 'consensus'),
            (percentile_cont(0.5) WITHIN GROUP (ORDER BY ls.spread_home))::numeric
        ) AS spread_home,
        coalesce(
            min(ls.total) FILTER (WHERE b.source_id = 'consensus'),
            (percentile_cont(0.5) WITHIN GROUP (ORDER BY ls.total))::numeric
        ) AS total,
        CASE
            WHEN count(ls.spread_home) FILTER (WHERE b.source_id = 'consensus') > 0 THEN 'consensus'
            WHEN count(ls.spread_home) > 0 THEN 'median'
        END AS source,
        CASE ls.kind WHEN 'closing' THEN 'cfbd_close' ELSE 'last_snapshot' END AS closing_from
    FROM line_snapshots ls
    JOIN sportsbooks b ON b.id = ls.book_id
    WHERE ls.game_id = g.id
        AND now() >= cutoff.at
        AND (ls.kind = 'closing' OR (ls.kind = 'snapshot' AND ls.captured_at < cutoff.at))
    GROUP BY ls.kind, ls.captured_at
    ORDER BY ls.kind = 'closing' DESC, ls.captured_at DESC
    LIMIT 1
) cl ON true;
