-- current_contest_standing: your league standing now, per live contest (TASK-068,
-- docs/03-data-model.md › Your data). contest_standings is append-only, so the current standing is
-- the newest row by entered_at, then id; a newer row replaces it here, never in the table.
-- The lateral reads one contest's rows through (contest_id, entered_at DESC).
CREATE OR REPLACE VIEW current_contest_standing AS
SELECT
    c.id AS contest_id,
    c.user_id,
    s.id AS standing_id,
    s.period,
    s.position,
    s.field_size,
    s.points_behind_leader,
    s.note,
    s.entered_at
FROM contests c
CROSS JOIN LATERAL (
    SELECT *
    FROM contest_standings s
    WHERE s.contest_id = c.id
    ORDER BY s.entered_at DESC, s.id DESC
    LIMIT 1
) s
WHERE c.deleted_at IS NULL;
