---
paths:
  - "python/db/**"
  - "python/engine/src/engine/publish/**"
  - "python/api/**"
  - "**/*.sql"
---

# Database rules

**Schema changes need the user's approval first** (see CLAUDE.md).

## Connections
- The app uses Neon's **pooled** URL: psycopg `prepare_threshold=None`, SQLAlchemy `NullPool` in serverless.
- Migrations and bulk publish jobs use `DATABASE_URL_UNPOOLED`.
- Tests read **only** `TEST_DATABASE_URL` through the single guard function, which refuses when it's unset or matches `DATABASE_URL`. Never fall back.

## Migrations (Alembic)
- Forward-only, one head. Never edit, rename or delete a migration that's on `main`.
- A migration that drops or retypes a column gets a hand-written downgrade and an up → down → up test that checks row values.
- Keep the SQLAlchemy models and migrations in sync (`alembic check` must be clean).
- Re-apply `python/db/views/*.sql` after every migration.

## Modeling the data
- **Never store derived data.** Results, records, ranks, CLV and "current pick" are views. Model outputs (ratings, predictions, picks) are stored, immutably, and never UPDATEd or DELETEd.
- Reference rows (teams, venues, games) are **upserted by `(source, source_id)`**. Never truncate and reload, and never derive IDs from load order.
- **Unknown is NULL**, never `now()` or midnight (e.g. a TBA kickoff: `kickoff_at` NULL, `game_date` set).
- Soft delete (`deleted_at`) user-created rows that have history; filter `deleted_at IS NULL` on every read; design UNIQUE constraints for re-adding.
- Per-user data lives in its own tables keyed by `user_id`, never as columns on catalog tables.

## Views & queries
- A view read for one item filters by that item before aggregating. Add a test that checks `EXPLAIN` for a full scan; never assert wall-clock times.
- Watch CTEs referenced more than once: Postgres may re-run them. Structure each step to read only the step before.
- Each API endpoint has a query budget: run its queries concurrently, in one wave. Raising the budget needs a written reason.
