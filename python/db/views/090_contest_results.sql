-- contest_results: your contest entries and the model's top N, each graded against the contest
-- line it was made at with the contest's push rule (TASK-068, D-171, docs/03-data-model.md › Views).
-- Never stored (hard rule 1): a corrected score regrades on the next read.
--
-- picker 'you': every live entry (deleted_at IS NULL) in a live contest, at its contest line.
-- picker 'model': the model's top N (D-170, D-171), fixed at the contest week's first kickoff
--   (the earliest cutoff among the week's contest lines' games): each game's newest contest pick
--   made before it (none when that is a pass), ranked within each contest, version and week by
--   the displayed cover probability (model_prob, D-143), then kickoff, then game; the first
--   picks_per_period are kept (model_rank 1…N). A pick written after the first kickoff never
--   changes the week's top N, so a game already played can't drop out of it with hindsight
--   (hard rule 4). A version's picks are its own rows: read one version (the shown one).
--   result: won | lost | push on a final game (home covers when margin + line > 0, a push at 0);
--           pending while it is scheduled or in progress; void when canceled or postponed.
--   points: a win 1, a loss 0, a push by the contest's rules.push: 'zero' 0, 'half' 0.5, 'void'
--           NULL (the push doesn't count); pending and void NULL. A contest with no push rule
--           scores 'zero' (D-045). counted (never NULL) says whether the row counts in the
--           record: a win, a loss, or a push the rule scores.
--   clv:    the contest line against game_market's closing line, in points for the side picked
--           (line − close for home, close − line for away, D-132), NULL until the close exists
--           (D-171: the market's close, not the contest's last snapshot).
-- Each branch reads one contest's rows when filtered by contest_id: entries through
-- ix_contest_entries_contest_id_live, picks through the contest's lines (ix_picks_contest_line_id).
-- A contest whose rules lack picks_per_period has no model rows (there is no default to assume).
CREATE OR REPLACE VIEW contest_results AS
SELECT
    x.picker,
    x.contest_id,
    x.user_id,
    x.model_version_id,
    x.model_rank,
    x.period,
    x.game_id,
    x.entry_id,
    x.pick_id,
    x.contest_line_id,
    x.side,
    x.line,
    x.created_at,
    g.season,
    g.season_type,
    g.week,
    g.kickoff_at,
    g.status AS game_status,
    g.home_points - g.away_points AS margin,
    r.result,
    CASE
        WHEN r.result = 'won' THEN 1.0
        WHEN r.result = 'lost' THEN 0.0
        WHEN r.result = 'push' AND x.push_rule = 'zero' THEN 0.0
        WHEN r.result = 'push' AND x.push_rule = 'half' THEN 0.5
    END AS points,
    coalesce(
        r.result IN ('won', 'lost') OR (r.result = 'push' AND x.push_rule IN ('zero', 'half')),
        false
    ) AS counted,
    gm.closing_spread_home,
    o.sign * (x.line - gm.closing_spread_home) AS clv
FROM (
    SELECT
        'you' AS picker,
        c.id AS contest_id,
        c.user_id,
        NULL::bigint AS model_version_id,
        NULL::bigint AS model_rank,
        l.period,
        e.game_id,
        e.id AS entry_id,
        NULL::bigint AS pick_id,
        e.contest_line_id,
        e.side,
        l.spread_home AS line,
        e.created_at,
        coalesce(c.rules ->> 'push', 'zero') AS push_rule
    FROM contests c
    JOIN contest_entries e ON e.contest_id = c.id AND e.deleted_at IS NULL
    JOIN contest_lines l ON l.id = e.contest_line_id
    WHERE c.deleted_at IS NULL
    UNION ALL
    SELECT
        'model',
        c.id,
        c.user_id,
        t.model_version_id,
        t.model_rank,
        t.period,
        t.game_id,
        NULL,
        t.id,
        t.contest_line_id,
        t.side,
        t.line,
        t.created_at,
        coalesce(c.rules ->> 'push', 'zero')
    FROM contests c
    JOIN (
        SELECT
            q.*,
            row_number() OVER (
                PARTITION BY q.contest_id, q.model_version_id, q.period
                ORDER BY q.model_prob DESC, q.kickoff_at NULLS LAST, q.game_id
            ) AS model_rank
        FROM (
            SELECT
                p.*,
                l.contest_id,
                l.period,
                g.kickoff_at,
                row_number() OVER (
                    PARTITION BY l.contest_id, p.model_version_id, l.period, p.game_id
                    ORDER BY p.created_at DESC, p.id DESC
                ) AS newest
            FROM picks p
            JOIN contest_lines l ON l.id = p.contest_line_id
            JOIN games g ON g.id = p.game_id
            CROSS JOIN LATERAL (
                SELECT min(coalesce(
                    wg.kickoff_at, (wg.game_date + 1)::timestamp AT TIME ZONE 'America/New_York'
                )) AS at
                FROM contest_lines wl
                JOIN games wg ON wg.id = wl.game_id
                WHERE wl.contest_id = l.contest_id AND wl.period = l.period
            ) first_kickoff
            WHERE p.market = 'spread' AND p.created_at < first_kickoff.at
        ) q
        WHERE q.newest = 1 AND q.side IS NOT NULL
    ) t ON t.contest_id = c.id AND t.model_rank <= (c.rules ->> 'picks_per_period')::int
    WHERE c.deleted_at IS NULL
) x
JOIN games g ON g.id = x.game_id
JOIN game_market gm ON gm.game_id = x.game_id
CROSS JOIN LATERAL (SELECT CASE x.side WHEN 'home' THEN 1 ELSE -1 END AS sign) o
CROSS JOIN LATERAL (
    SELECT CASE
        WHEN g.status IN ('canceled', 'postponed') THEN 'void'
        WHEN g.status <> 'final' THEN 'pending'
        WHEN o.sign * (g.home_points - g.away_points + x.line) > 0 THEN 'won'
        WHEN o.sign * (g.home_points - g.away_points + x.line) < 0 THEN 'lost'
        ELSE 'push'
    END AS result
) r;
