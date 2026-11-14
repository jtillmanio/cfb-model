-- contest_record: your contest record and the model's top N's, per contest week and to date
-- (TASK-068, D-171, docs/03-data-model.md › Views). Never stored (hard rule 1).
--
-- One row per live contest, picker ('you', or 'model' per version with contest picks in it),
-- contest week (every period the contest has lines for) and breakdown: 'week' (that week alone)
-- or 'to_date' (the contest through it; the newest week is the season so far). A week with nothing
-- graded yet still has its rows, with 0 points (F-32's "this week so far").
--   wins, losses, pushes, voids, pending: contest_results' rows by result.
--   points: the sum of contest_results.points (the push rule applied there), 0 when none count.
-- Grouped by a plain GROUP BY on contest_id, so a read filtered by contest is applied below it.
CREATE OR REPLACE VIEW contest_record AS
SELECT
    k.contest_id,
    k.picker,
    k.model_version_id,
    k.period,
    b.breakdown,
    count(r.result) FILTER (WHERE r.result = 'won') AS wins,
    count(r.result) FILTER (WHERE r.result = 'lost') AS losses,
    count(r.result) FILTER (WHERE r.result = 'push') AS pushes,
    count(r.result) FILTER (WHERE r.result = 'void') AS voids,
    count(r.result) FILTER (WHERE r.result = 'pending') AS pending,
    coalesce(sum(r.points), 0.0) AS points
FROM (
    SELECT p.contest_id, p.period, who.picker, who.model_version_id
    FROM (
        SELECT DISTINCT l.contest_id, l.period
        FROM contest_lines l
        JOIN contests c ON c.id = l.contest_id
        WHERE c.deleted_at IS NULL
    ) p
    CROSS JOIN LATERAL (
        SELECT 'you' AS picker, NULL::bigint AS model_version_id
        UNION ALL
        SELECT DISTINCT 'model', cp.model_version_id
        FROM current_picks cp
        WHERE cp.contest_id = p.contest_id
    ) who
) k
CROSS JOIN (VALUES ('week'), ('to_date')) b (breakdown)
LEFT JOIN contest_results r
    ON r.contest_id = k.contest_id
    AND r.picker = k.picker
    AND r.model_version_id IS NOT DISTINCT FROM k.model_version_id
    AND (r.period = k.period OR (b.breakdown = 'to_date' AND r.period < k.period))
GROUP BY k.contest_id, k.picker, k.model_version_id, k.period, b.breakdown;
