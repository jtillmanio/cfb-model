# Views

Derived data lives here, never in columns (CLAUDE.md hard rule 1). Each `*.sql` file is
re-applied in name order after every migration (`db:migrate`, the preview build and the
`release` workflow), so write each one as `CREATE OR REPLACE VIEW …`, and give each one a test.

Empty until the first view lands in Phase 1.
