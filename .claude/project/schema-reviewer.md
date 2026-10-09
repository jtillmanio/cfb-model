# schema-reviewer: cfb-model

Project section for `.claude/agents/schema-reviewer.md`. The kit never ships or overwrites this file.

Read `.claude/rules/database.md` first and check every change against it; it is the one home of the data rules, and the list below restates the ones a diff most often breaks.

## Project data rules

From the CLAUDE.md hard rules and `.claude/rules/database.md`. Once `python/db/` has them, its models and migrations win over the **Data model** doc.
- **Nothing derived is stored.** Results, records, ranks, CLV, current pick and current contest line are views in `python/db/views/*.sql`, never columns or tables.
- **Ratings, predictions and picks are insert-only**, each tied to a `model_run`. No UPDATE or DELETE paths and no `ON CONFLICT DO UPDATE` on them.
- **Reference rows** (teams, venues, games, …) are upserted by a UNIQUE `(source, source_id)`. Never truncate and reload, and never derive IDs from load order. Fixture rows use `source = 'fixture'`.
- **Unknown is NULL**, never `now()` or midnight (e.g. a TBA kickoff has `kickoff_at` NULL and `game_date` set). Flag any change to how a stored date or line is interpreted. It needs the user's approval.
- **Per-user data** lives in its own tables keyed by `user_id`, never as columns on catalog tables. User-created rows with history are soft-deleted (`deleted_at`), every read filters `deleted_at IS NULL`, and UNIQUE constraints allow re-adding.
- `sport_id` on sport-scoped tables (multi-sport later).
- **Point-in-time:** feature and backtest queries filter on source time `< as_of`; ratings at `(season, week=N)` mean "entering week N".
- **Views:** a single-item read filters before it aggregates, with an `EXPLAIN` test for no full scan. CTEs referenced twice are a smell. Each endpoint stays within its query budget.
- **Connections:** the app uses the pooled URL (`prepare_threshold=None`, `NullPool` in serverless). Migrations and bulk publishes use `DATABASE_URL_UNPOOLED`. Tests read only `TEST_DATABASE_URL` through the single guard, with no fallback.
- **Destructive CLI commands** (`--rebuild`, truncate, reload) check `LIVE` and refuse when it's true.

### Migration tool: Alembic
- Location `python/db/migrations/versions/`, file name `NNNN_<slug>.py` (`file_template = %(rev)s_%(slug)s` in `python/db/alembic.ini`). The revision ID is the zero-padded sequence (`0001`, `0002`, …), and `down_revision` points to the previous one.
- **One head, forward-only.** Never edit, rename or delete a migration on the base branch. A migration that drops or retypes a column needs a hand-written `downgrade()` and an up → down → up test that checks row values. Otherwise `downgrade()` may be a plain reverse.
- Models (`python/db/src/db/models.py`) and migrations must agree. `pnpm db:check` (`python -m db check`) checks one head and `alembic check`. Views (`python/db/views/*.sql`) are re-applied after every migration, so check that a column change doesn't break a view.
- Any new table or column, type change or dropped column needs the user's approval first. Flag it as BLOCKER if the task file doesn't record that approval.

