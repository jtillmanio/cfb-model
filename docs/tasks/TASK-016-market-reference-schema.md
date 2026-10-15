---
id: TASK-016
title: Add seasons, team_aliases, sportsbooks and line_snapshots
status: Ready
depends_on: []
size: M
model: opus
autonomy: attended
ui: false
plan_status: none
planned_at_commit:
---

# TASK-016 — Add seasons, team_aliases, sportsbooks and line_snapshots

## Goal

The serving database can hold each season's calendar, every name a source uses for a team, the sportsbooks, and the full history of lines for each game. The test fixture gets the Week 6 lines that the screens and views will cite.

## Context

- Task list: `docs/08-tasklist.md` › M2 › M2.2.
- **Schema change: stop and ask.** The plan names every table, column, type, constraint and index, and waits for the owner's approval (CLAUDE.md › Stop and ask). The schema-reviewer agent reviews the migration.
- Data model: `docs/03-data-model.md` › Reference (`seasons`, `team_aliases`); › Games & market (`sportsbooks`, `line_snapshots`: append-only price history, IDX `(game_id, captured_at)`); › Conventions (upsert by `(source, source_id)`, unknown is NULL, UTC `timestamptz`); › Proposed additions › Fixture rows (every `source` accepts `'fixture'`).
- Architecture: `docs/02-architecture.md` › Testing strategy › Seed data (the "Season and clock" and "Line snapshots" rows); › Release & operations (CI migration checks).
- Decisions: D-030, D-031, D-032, D-036 (names match through `team_aliases`), D-037 (append-only snapshots; closing = last before kickoff), D-089 (fixture in the test DB only).
- Existing code: `python/db/src/db/models.py`, `python/db/migrations/versions/0001_reference_tables.py` (naming convention, CHECK style), `python/engine/src/engine/fixture.py` and `python/db/seeds/fixture/teams.json` (the fixture has teams only; no games yet).
- **Direction agreed with the owner (2026-10-15, at task drafting).** The plan still sets out the exact schema for approval:
  - Backfilled lines: a `kind` column (`opening|closing|snapshot`) replaces 03's `is_opening`. CFBD's historical open and close rows are `opening`/`closing` with `captured_at` NULL (unknown, D-031). Live pulls are `snapshot` with `captured_at` = the raw file's `fetched_at`. The idempotency key is `(game_id, book_id, source, kind, captured_at)` with `NULLS NOT DISTINCT` (Postgres 15+; `PG_MAJOR` is 18). 03 › Games & market is updated to match in the same PR.
  - Fixture scope: the recommended scope in the last bullet below.
- **Decide at the plan gate:**
  - **Backfilled lines have no capture time.** For past games CFBD `/lines` gives each provider's opening and closing spread, not when either was quoted. Decide how they're stored so `game_market` (TASK-020) reads them as opening and closing, and F-06 can draw a past game as two dots, open and close. Options include a `kind` column (`opening|closing|snapshot`) or `captured_at` NULL with flags. D-031 rules out inventing a time.
  - The key that makes re-publishing the same raw file a no-op (for example `(game_id, book_id, source, captured_at)`, with `captured_at` = the raw file's `fetched_at` for live pulls), since the table is append-only and TASK-020 must be idempotent.
  - Allowed `source` values (`cfbd|oddsapi|manual|fixture` for lines; `cfbd|splash|manual|fixture|…` for aliases) and whether they're CHECK constraints.
  - The shape of `seasons.weeks jsonb` (from CFBD `/calendar`).
  - Whether "append-only" on `line_snapshots` is enforced (a trigger or a test, like hard rule 2) or a convention.
  - **Fixture scope.** The tasklist rule is that only the schema task owning a table extends the fixture (D-089). Line snapshots need games, and the fixture has none: the skeleton built `games` but seeded only teams. Recommended: seed the 2026 season row (current week 6), the `consensus` book, the 11 Week 6 games in `design/sample-data.md` §1 with their opening and current lines, Texas vs Oklahoma's four snapshots and BYU's Wednesday move. Leave the filler games (to 54), Ohio State's weeks 1–7 lines (§6) and the NFL games to the screen tasks that cite them, and record each with its task as a follow-up.

## Acceptance criteria

- [ ] AC-1: Migration `0002` creates `seasons`, `team_aliases`, `sportsbooks` and `line_snapshots`; on a database at `0001`, `pnpm db:migrate:test` applies it, and `pnpm db:check` passes (one head, `alembic check` clean).
- [ ] AC-2: Given the alias `('splash', 'Ohio St')` for one team, inserting `('splash', 'Ohio St')` for any team fails with a unique violation, and `('cfbd', 'Ohio St')` succeeds.
- [ ] AC-3: Inserting a line snapshot for a game or book that doesn't exist fails on its foreign key. Re-inserting a snapshot with the same idempotency key (as decided at the plan gate) through `ON CONFLICT DO NOTHING` leaves the row count unchanged.
- [ ] AC-4: On the seeded test DB, `seasons` holds `('cfb', 2026)` with `current_week = 6`. Texas @ Oklahoma (home Oklahoma, Texas favored) has snapshots whose `spread_home`, ordered by capture time, is `+7, +6.5, +6, +6.5`. Furman @ Clemson has no snapshots.
- [ ] AC-5: Every fixture row in the new tables has `source = 'fixture'`, and `pnpm db:seed` still refuses any target except `TEST_DATABASE_URL` (the existing guard test passes).

## Out of scope

- The `game_market` view and publishing CFBD lines (TASK-020).
- Publishing CFBD's alternate team names into `team_aliases` (TASK-020 or later); saving Splash aliases at confirm (M6).
- Contest tables (`contests`, `contest_lines`, …; M6.1), model tables (M3.6), `picks` (M4.5).
- Fixture rows beyond the scope agreed at the plan gate.

## Files likely touched

- `python/db/src/db/models.py`: four models.
- `python/db/migrations/versions/0002_market_reference.py`: the migration (new).
- `python/db/seeds/fixture/`: season, sportsbooks, Week 6 games and lines (new JSON files).
- `python/engine/src/engine/fixture.py`: load the new fixture files.
- `python/engine/src/engine/publish/reference.py`: upserts for the new reference rows, if the fixture loader reuses them.
- `python/db/tests/test_market_schema.py`: AC-2, AC-3, AC-4 (new).

## Verification

- Automated: `python/db/tests/test_market_schema.py`; CI's migration checks (one head, `alembic check`, merged-migration check).
- Manual: `pnpm db:migrate` on the dev DB → `\d line_snapshots` shows the agreed columns, keys and indexes; `pnpm db:migrate:test && pnpm db:seed` → AC-4's rows are visible.

## Follow-ups

_Work noticed during this task and deliberately left out. Each bullet ends `→ <path> § <section>` (where it was placed) or `→ not tracked: <reason>`. See `.claude/skills/track-follow-ups/classify.md`; the PR's Follow-ups section is copied from here._

## Plan

_Written by /plan-batch or /implement-task Phase 1. Approved by the user (plan_status: approved) before any code is written._

## Review log

_Filled by /implement-task. One line per round._

## Blocked

_Only if status is Blocked: what failed, what was tried, best hypothesis, decision needed._

## Metrics

- Verify rounds:
- Review rounds:
- First-pass AC FAILs:
- Plan revisions after approval:
