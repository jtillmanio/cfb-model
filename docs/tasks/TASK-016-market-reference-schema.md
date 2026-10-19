---
id: TASK-016
title: Add seasons, team_aliases, sportsbooks and line_snapshots
status: In progress
depends_on: []
size: M
model: opus
autonomy: attended
ui: false
plan_status: approved
planned_at_commit: 1bf71ef
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

- Fixture: the other 43 Week 6 games that make "54 games" (Tulane @ Memphis final 27-24, Iowa State @ Cincinnati, Arizona State @ Baylor, and filler with edges under 1.0; 02 › Seed data) → docs/08-tasklist.md § M5.5
- Fixture: Ohio State's weeks 1–7 lines (sample-data §6) → docs/08-tasklist.md § M8.3
- Fixture: the 5 NFL games (§3) and the `nfl` sports row → docs/08-tasklist.md § M6.3
- Fixture: `splash` aliases for every Week 6 paste name except "Hou Texans" and "Jax", so the import shows "9 rows match · 1 unmatched" → docs/08-tasklist.md § M6.4
- `seasons.current_week` is stored, as 03 and AC-4 have it, though it follows from `weeks` and the clock; who keeps it current (the `/calendar` publish, or a view) → docs/tasks/TASK-020-publish-lake-and-game-market.md § Context (open question for the plan)

## Plan

Approved 2026-10-16 (/plan-batch): the schema below as written, including the `source` columns on `seasons` and `sportsbooks` and the append-only trigger (the schema change is approved).

**Schema** (migration `0002_market_reference`; the naming convention and CHECK style follow 0001; every table gets `created_at`)
- `seasons`: `sport_id text FK sports`, `year int`, `source text NOT NULL`, `start_date date NOT NULL`, `end_date date NOT NULL`, `current_week int NULL`, `weeks jsonb NOT NULL`, `updated_at` · PK `(sport_id, year)` · CHECK `jsonb_typeof(weeks) = 'array'`, CHECK `end_date >= start_date`. `weeks` is CFBD `/calendar` as `[{"week": 6, "season_type": "regular", "start": "<UTC ISO>", "end": "<UTC ISO>"}, …]`.
- `team_aliases`: `id bigint identity PK`, `team_id bigint FK teams NOT NULL`, `source text NOT NULL` (whose spelling: `cfbd`, `splash`, `manual`, `fixture`, …; no CHECK, since each new platform adds one), `alias text NOT NULL` · UQ `(source, alias)` · IDX `(team_id)`.
- `sportsbooks`: `id bigint identity PK`, `source text NOT NULL`, `source_id text NOT NULL` (the provider as that source writes it, e.g. CFBD's `consensus`, `DraftKings`), `name text NOT NULL` · UQ `(source, source_id)`. It replaces 03's `key` (hard rule 3; AC-5 needs a `source`). Matching books across sources waits for a second line source.
- `line_snapshots`: `id bigint identity PK`, `game_id FK games NOT NULL`, `book_id FK sportsbooks NOT NULL`, `source text NOT NULL` CHECK IN (`cfbd`, `oddsapi`, `manual`, `fixture`), `kind text NOT NULL` CHECK IN (`opening`, `closing`, `snapshot`), `captured_at timestamptz NULL` with CHECK `kind <> 'snapshot' OR captured_at IS NOT NULL`. Prices: `spread_home numeric(4,1)`, `total numeric(4,1)`, and `int` for `spread_home_price`, `spread_away_price`, `over_price`, `under_price`, `ml_home`, `ml_away` (all NULL when not quoted). UQ `(game_id, book_id, source, kind, captured_at)` NULLS NOT DISTINCT · IDX `(game_id, captured_at)`.
- **Append-only, enforced:** trigger `line_snapshots_append_only` (BEFORE UPDATE OR DELETE, raises) via function `forbid_line_snapshot_changes()`; the downgrade drops both. A live snapshot can't be regenerated (02 › What's reproducible), so a convention isn't enough.
- CFBD's historical open and close are `opening`/`closing` rows with `captured_at` NULL (D-031). A live pull writes its current spread as a `snapshot` at the raw file's `fetched_at`, and its `spreadOpen` as one `opening` row, which the NULLS NOT DISTINCT key keeps to one.

**Fixture** (test DB only, D-089): `seeds/fixture/week6.json` holds:
- The 2026 season: `current_week` 6, weeks 1–15 regular plus postseason 1 in 7-day steps; week 6 is Sun 10-04 to Sat 10-10 ET.
- The book `consensus`, and the venue Cotton Bowl (Texas @ Oklahoma is neutral, so the home team is Oklahoma).
- The 11 games of sample-data §1, with their statuses and scores. UNLV 24 BSU 31 is final; PUR 3 OSU 24 and IOWA 10 WIS 7 are in progress; the rest are scheduled. Kickoffs are converted from ET to UTC.
- Lines for every game but Furman @ Clemson:
  - an `opening` row at the "Opened" number;
  - `snapshot` rows at Sun 10-04 06:00 ET (the opener) and Thu 10-08 21:02 ET (the current number);
  - Texas @ Oklahoma instead: Sun +7, Tue 12:00 +6.5, Thu 21:02 +6, Sat 09:00 +6.5;
  - BYU instead: Sun −7, Wed 19:04 −6, Thu −6.
- `teams.json` gains UNLV, Boise State, Iowa, Wisconsin, Furman (`fcs`), Clemson, Michigan, Northwestern, Colorado and BYU, with colors from `*-data.js` where given and NULL otherwise.

**Steps**
1. `models.py`: `Season`, `TeamAlias`, `Sportsbook`, `LineSnapshot` (UQ with `postgresql_nulls_not_distinct=True`).
2. `0002_market_reference.py`: tables, constraints and indexes, plus the trigger SQL; checked against autogenerate.
3. `publish/reference.py`: `upsert_season`, `upsert_sportsbooks` (by `(source, source_id)` → ids), and `insert_line_snapshots` (`ON CONFLICT DO NOTHING` on the key, returns the inserted count). TASK-020 reuses them.
4. `fixture.py`: after the teams, load `week6.json` (venue, games through the existing upserts, then the season, books and lines). A re-seed changes nothing.
5. 03 › Reference and Games & market get the approved shapes; `decisions.md` gets a new D-### (kind, key, the sportsbooks source, the trigger).

**Files** (9): `python/db/src/db/models.py`, `python/db/migrations/versions/0002_market_reference.py` (new), `python/engine/src/engine/publish/reference.py`, `python/engine/src/engine/fixture.py`, `python/db/seeds/fixture/teams.json`, `python/db/seeds/fixture/week6.json` (new), `python/db/tests/test_market_schema.py` (new), `docs/03-data-model.md`, `docs/decisions.md` (the last two aren't in Files likely touched).

**Test strategy** (`python/db/tests/test_market_schema.py`; AC-4 and AC-5 read the seeded test DB, which CI seeds before pytest)
- AC-1: CI's `pnpm db:migrate:test` and `pnpm db:check` steps, plus the manual run on a local test DB at `0001`. Automated: `test_the_four_tables_exist`.
- AC-2: `test_an_alias_is_unique_per_source` (savepoints; the second `splash` insert raises `UniqueViolation`; `cfbd` succeeds).
- AC-3: `test_a_snapshot_needs_its_game_and_book` (both FK violations), `test_republishing_snapshots_is_a_no_op` (includes an `opening` row with NULL `captured_at`), `test_snapshots_cannot_be_updated_or_deleted`.
- AC-4: `test_the_seeded_season_and_texas_oklahoma_lines` (`kind = 'snapshot'` ordered by `captured_at` gives `[7, 6.5, 6, 6.5]`; Furman @ Clemson has 0 rows).
- AC-5: `test_every_row_in_the_new_tables_is_fixture`; the existing seed-guard test still passes.

**Risks / open questions**
- `alembic check` must see NULLS NOT DISTINCT (SQLAlchemy reflects it on PG 15+). If it still reports a diff, declare the key as a unique `Index` with the same option.
- AC-4's "snapshots ordered by capture time" is read as the `kind = 'snapshot'` rows. Texas @ Oklahoma also has its `opening` row (+7, no time).
- UQ `(source, alias)` spans sports. Splash names CFB teams by school ("Houston") and NFL teams by nickname ("Texans"), so neither copy collides.
- The fixture's snapshot times are invented (fixture only). D-031 still governs real rows.

**Size check:** 9 files, one layer (data), schema without UI: passes.

**Revisions after approval** (agreed with the owner, 2026-10-19, during implementation)
1. A statement-level `BEFORE TRUNCATE` trigger, `line_snapshots_no_truncate`, on the same function: TRUNCATE skips row triggers, so the approved trigger alone left the history open to a wipe. `test_snapshots_cannot_be_updated_deleted_or_truncated` covers it.
2. `python/api/tests/test_api_health.py` (a 10th file): it asserted `migration_head == "0001"`, which 0002 breaks. It now compares with `db.migrate.heads()[0]`, so later migrations don't break it again. `web/e2e/auth.spec.ts` (an 11th file) had the same hard-coded `"0001"`, found by verify R1; it gets the same fix, reading the newest revision from `python/db/migrations/versions/`.

## Review log

_Filled by /implement-task. One line per round._

## Blocked

_Only if status is Blocked: what failed, what was tried, best hypothesis, decision needed._

## Metrics

- Verify rounds:
- Review rounds:
- First-pass AC FAILs:
- Plan revisions after approval:
