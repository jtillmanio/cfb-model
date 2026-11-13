---
id: TASK-067
title: Add users, contests, contest_lines, contest_entries and contest_standings
status: In progress
depends_on: [TASK-016, TASK-069]
size: M
model: opus
autonomy: attended
ui: false
plan_status: approved
planned_at_commit: cc43e8c
---

# TASK-067 — Add users, contests, contest_lines, contest_entries and contest_standings

## Goal

The database can hold your contests, each week's contest lines as snapshots, your entries at the exact line you got, your hand-entered league standing, and the model's contest picks. The test database has the seeded Splash work league to test against.

## Context

- Task list: `docs/08-tasklist.md` › M6 › M6.1. **Schema change: stop and ask** (CLAUDE.md). The plan gate is the ask.
- Data model: `docs/03-data-model.md` › Your data (`users`, `contests`, `ContestRules`, `contest_lines`, `contest_entries`), › Proposed additions from the design handoff (`contest_standings`), › Models & outputs › picks (the note on `contest_line_id`), › Conventions (soft delete; catalog vs per-user), › Views (`current_picks`, `pick_outcomes`, `model_record`).
- Architecture: `docs/02-architecture.md` › Testing strategy › Seed data (Contest and User rows).
- Decisions: D-029, D-033 (soft delete, re-adding allowed), D-034 (catalog vs per-user), D-038 (append-only contest snapshots), D-044, D-045 (Splash preset, push = 0), D-089 (every fixture `source` accepts `'fixture'`), D-105 (the JWT's `sub` is the GitHub user ID, so `users.github_id`), D-113 (`ContestRules` and `SPLASH_PRESET` in `engine/core/contest_rules.py`), D-140, D-142.
- Depends on TASK-069 for the NFL games: the Week 6 contest lines include 4 NFL games, and the BUF −3 entry is one of them.
- **Settle at the plan gate:**
  - **Who writes the `users` row.** The seed writes it in the test DB. In production, the API's first write either upserts it by `github_id` or a migration seeds the allowlisted user.
  - **The entry keys.** `contest_entries` refers to the game only through `contest_line_id`. Decide whether it carries `game_id` too (a composite FK like `picks`') so "one live entry per user, contest and game" can be a partial unique index.
  - **The model's top N for a "No model yet" game.** `contest-data.js`'s `rank` puts an NFL game with a gap side in the model's top 4, but a `picks` row needs a `prediction_id`, and NFL games have none. Either the schema stores those recommendations (and the plan says how), or the model's top N is CFB-only. TASK-068's model record depends on the answer.
- **Periods:** `contest_lines.period` is the contest's week (Splash's "Week 6"), not `games.week`; NFL week numbers differ (TASK-069).
- *From TASK-040 (PR #105):* add `picks.contest_line_id` (foreign key to `contest_lines`), make `picks.line_snapshot_id` nullable with an exactly-one CHECK, and let `picks.price` be NULL for a no-vig contest pick (D-140).
- *From TASK-041 (PR #107):* `current_picks` and `pick_outcomes` derive `line_source` 'market' from `line_snapshot_id` (a CASE with no ELSE), and `pick_outcomes` grades at `price`. When `line_snapshot_id` becomes nullable, set `line_source` 'contest' for a `contest_line_id` pick and keep contest picks out of the market grading (a NULL price gives NULL units). `model_record` already counts `line_source = 'market'` only (D-142).
- *From TASK-053 (PR #136):* the shell's week pick count (`api/shell.py`, `week_picks`) reads `current_picks` with `line_source = 'market'` only, a filter no test can prove until contest picks exist. Add a contest pick to a `python/api/tests/test_api_shell.py` case and check `picks` leaves it out.

## Acceptance criteria

- [ ] AC-1: Migration `0007` creates `users`, `contests`, `contest_lines`, `contest_entries` and `contest_standings`, per 03 › Your data and › Proposed additions with the plan's settled keys. It runs up → down → up on the test DB, and `pnpm db:check` passes (one head, models match).
- [ ] AC-2: `contest_lines` and `contest_standings` refuse UPDATE, DELETE and TRUNCATE (append-only). A `contest_entries` row can't be hard-deleted. After an entry is soft-deleted (`deleted_at` set), the same user, contest and game can take a new entry, and two live entries for one user, contest and game are refused (D-033).
- [ ] AC-3: `picks` gains `contest_line_id`. A pick with both or neither of `line_snapshot_id` and `contest_line_id` is refused. A contest pick with `price` NULL inserts. A contest pick whose contest line belongs to another game is refused, as a market pick on another game's snapshot already is.
- [ ] AC-4: `current_picks` and `pick_outcomes` give a contest pick `line_source` `contest`, and `pick_outcomes` gives it no market `units`. On the seeded DB, `model_record`'s v1.0 2026 `to_date` row through week 5 is still 31-24-1, +4.6u. A `test_api_shell.py` case with a contest pick for a week-6 game shows the shell's `picks` count leaves it out.
- [ ] AC-5: The seeded test DB has:
  - the allowlisted user;
  - "Splash work league" (platform `splash`, season 2026, `rules` equal to `SPLASH_PRESET`);
  - Week 6 contest lines for the 10 games in `contest-data.js`'s paste, captured Thu 2026-10-08 before 9:14 PM ET;
  - the entries OU +7 (Thu 9:14 PM ET) and BUF −3 (Thu 9:20 PM ET), each at its game's contest line;
  - weeks 1–5 entries on final games graded W1 3-1, W2 2-2, W3 3-1, W4 1-3, W5 3-1 (12-8);
  - a standing of 3rd of 14, 1 point behind the leader, after week 5.

  A test reads each back.

## Out of scope

- The contest views: current contest line, results and current standing (TASK-068).
- The model's weeks 1–5 contest picks that give "Model top 4 11-9" (TASK-068's fixture).
- Any API route or screen (TASK-070, TASK-071, TASK-072, TASK-073).
- `user_settings` (M8.7): time zone and default contest.
- Confidence-points contests and other platforms' parsers.

## Files likely touched

- `python/db/migrations/versions/0007_contests.py`: new
- `python/db/src/db/models.py`: the five tables and `picks.contest_line_id`
- `python/db/views/050_current_picks.sql`, `python/db/views/060_pick_outcomes.sql`: `line_source` `contest`, with no market grading for it
- `python/db/seeds/fixture/contest.json`: new, the contest, lines, entries and standing. `generate_contest.py`, if the weeks 1–5 entries are generated
- `python/engine/src/engine/fixture.py`: loads them
- `python/db/tests/test_contest_schema.py`: new, AC-1 to AC-3 and AC-5. `test_picks_schema.py`, `test_current_picks.py`, `test_pick_outcomes.py`, `test_model_record.py`: AC-3 and AC-4
- `python/api/tests/test_api_shell.py`: the contest-pick case
- `docs/03-data-model.md` › Your data, › Models & outputs › picks; `docs/02-architecture.md` › Seed data; `docs/decisions.md`

## Verification

- Automated: `uv --directory python run pytest db/tests api/tests/test_api_shell.py` passes on the reseeded test DB, and `pnpm db:check` passes.
- Manual: `pnpm db:migrate:test && pnpm db:seed`, then `SELECT` the contest's week-6 lines and entries → expected: 10 lines; OU +7 at 9:14 PM and BUF −3 at 9:20 PM ET.

## Follow-ups

_Work noticed during this task and deliberately left out. Each bullet ends `→ <path> § <section>` (where it was placed) or `→ not tracked: <reason>`. See `.claude/skills/track-follow-ups/classify.md`; the PR's Follow-ups section is copied from here._

- TASK-070's import is the production writer of `users`: upsert by `github_id` from the JWT's `sub` on the first write (no migration seeds the real account) → docs/tasks/TASK-070-contest-import-api.md § Context (approved at plan)
- TASK-068: the model's contest picks are CFB-only (a pick needs a prediction; the NFL gap side is computed on read and never counts in the model record); the weeks 1–5 contest slates are 5 final CFB games each with v1.0 predictions, for its "Model top 4 11-9" fixture; `current_picks` and `pick_outcomes` partition contest picks by contest → docs/tasks/TASK-068-contest-views.md § Context (approved at plan)
- `python/db/views/README.md`'s `current_picks` row still says "per game, version, market and line source"; since TASK-067 the partition also holds the contest. TASK-068 adds the contest views' rows to the same table

## Plan

_Written by /plan-batch or /implement-task Phase 1. Approved by the user (plan_status: approved) before any code is written._

Approved by the owner 2026-11-13.

### Settled at the plan gate

1. **Who writes `users`:** the fixture seed in the test DB (`github_id` 4242, the ID the API tests and e2e sign as). In production the contest API (TASK-070) upserts the row by the JWT's `sub` on its first write; no migration seeds the real account (it would put a personal ID in a migration). `github_id bigint NOT NULL UNIQUE`; `email` and `name` nullable, since the JWT carries only `sub`.
2. **Entry keys:** `contest_entries` carries `game_id` too. FK `(contest_line_id, contest_id, game_id)` → `contest_lines (id, contest_id, game_id)` (an entry can't sit on another contest's or game's line) and FK `(contest_id, user_id)` → `contests (id, user_id)` (the contest is the user's), both RESTRICT. Partial unique `(user_id, contest_id, game_id) WHERE deleted_at IS NULL`: one live entry per game, re-adding after a soft delete allowed (D-033).
3. **Model top N:** the model's stored contest picks are CFB-only (a `picks` row needs a `prediction_id`). The design's NFL "gap side" is computed on read and never stored as a model pick or counted in the model record. Week 6's top 4 are all CFB, so the design's numbers don't change.

### Steps

1. Migration `0007_contests.py`:
   - `users`: `id`, `github_id`, `email NULL`, `name NULL`, `created_at`.
   - `contests`: `id`, `user_id` (RESTRICT), `name`, `platform` (no CHECK, as `team_aliases.source`), `season`, `rules jsonb` (CHECK `jsonb_typeof = 'object'`; validated as `ContestRules` in code), `created_at`, `deleted_at`; UQ `(id, user_id)`; partial UQ `(user_id, name) WHERE deleted_at IS NULL`.
   - `contest_lines`: `id`, `contest_id`, `period` (the contest's week, not `games.week`), `game_id` (RESTRICT), `spread_home numeric(4,1) NOT NULL`, `captured_at NOT NULL`, `source` CHECK `paste|manual|fixture` (D-089), `created_at`; UQ `(contest_id, game_id, captured_at)` (also the newest-line index); UQ `(id, game_id)` and `(id, contest_id, game_id)` for the composite FKs; IDX `(contest_id, period)`.
   - `contest_entries`: `id`, `user_id`, `contest_id`, `game_id`, `contest_line_id`, `side` CHECK `home|away`, `confidence int NULL` (> 0), `created_at`, `deleted_at`; keys per settled item 2.
   - `contest_standings`: `id`, `contest_id`, `period`, `position` (> 0), `field_size` (> 0, CHECK `position <= field_size`), `points_behind_leader numeric(5,1) NULL` (≥ 0), `note NULL`, `entered_at`; IDX `(contest_id, entered_at DESC)`.
   - Triggers: `contest_lines` and `contest_standings` refuse UPDATE, DELETE and TRUNCATE; `contest_entries` refuses DELETE and TRUNCATE, and any UPDATE except setting `deleted_at` once (from NULL, nothing else changed), so the line you got never changes.
   - `picks`: add `contest_line_id NULL` with FK `(contest_line_id, game_id)` → `contest_lines (id, game_id)` RESTRICT; `line_snapshot_id` nullable; CHECK exactly one of the two; `price` nullable with CHECK `price IS NOT NULL OR contest_line_id IS NOT NULL`; UQ `(prediction_id, market, contest_line_id)`.
   - Downgrade refuses while any contest row or contest pick exists, then reverses.
2. `python/db/src/db/models.py`: the five tables and the `picks` changes, matching the migration so `pnpm db:check` passes.
3. Views: `050_current_picks.sql` and `060_pick_outcomes.sql` give `line_source` `contest` for a `contest_line_id` pick and partition the current pick by contest too (LEFT JOIN `contest_lines`); `contest_line_id` and `contest_id` are appended at the end of each column list (CREATE OR REPLACE can only add at the end, and `model_record` reads `pick_outcomes`). `pick_outcomes`: `units` and `risked` NULL for a contest pick, push and void included; `clv` unchanged (line picked at vs the market close).
4. Fixture:
   - `python/db/seeds/fixture/contest.json` (hand-written): the user (4242), "Splash work league" (`splash`, 2026, `SPLASH_PRESET`), the 10 Week 6 contest lines from `contest-data.js` (`spread_home` = −the away line: BSU −10, OSU −27, LSU −3, STAN +17.5, OU +7, BYU −5.5, NYJ +3, JAX +1, BAL −2.5, PHI −6) captured Thu 2026-10-08 9:10 PM ET, entries OU +7 (home, Thu 9:14 PM ET) and BUF −3 (away, Thu 9:20 PM ET), and the standing 3rd of 14, 1 behind, period 5.
   - `generate_contest.py` → `contest_history.json`: weeks 1–5 slates of 5 final CFB games each from `picks.json` (all with v1.0 predictions), lines on half points (no pushes) captured each week's Thursday before any kickoff, and 4 entries per week graded W1 3-1, W2 2-2, W3 3-1, W4 1-3, W5 3-1 (12-8); fixed seed, deterministic.
   - `python/engine/src/engine/fixture.py` loads both after the NFL games; a re-seed inserts nothing (user upserted by `github_id`, contest reused by user and name, lines and entries `ON CONFLICT DO NOTHING`, the standing inserted only when absent).
5. Tests (each written first and seen failing).
6. Docs: `docs/03-data-model.md` › Your data (the built tables and keys, `contest_standings` out of "Proposed additions"), › Models & outputs › picks, › Views (`line_source` `contest`); `docs/02-architecture.md` › Seed data (the contest rows); `docs/decisions.md` a new D-### for the keys and the three settled items.

### Files

- `python/db/migrations/versions/0007_contests.py` (new): the tables, triggers and `picks` changes
- `python/db/src/db/models.py`: the ORM mirror
- `python/db/views/050_current_picks.sql`, `python/db/views/060_pick_outcomes.sql`: `line_source` `contest`, no market units
- `python/db/seeds/fixture/contest.json` (new), `generate_contest.py` (new), `contest_history.json` (new, generated): the seed
- `python/engine/src/engine/fixture.py`: loads them
- `python/db/tests/test_contest_schema.py` (new); `test_picks_schema.py`, `test_current_picks.py`, `test_pick_outcomes.py`, `test_model_record.py`; `python/api/tests/test_api_shell.py`
- `docs/03-data-model.md`, `docs/02-architecture.md`, `docs/decisions.md`

17 files, within the project's 20-file limit; schema only, no UI. `contest_history.json` is the only file not in "Files likely touched" (the generator's output).

*Added while implementing (test files only, no change of approach):* `python/db/tests/model_rows.py` gains the shared `user`, `contest`, `contest_line` and `contest_pick` helpers the view and shell tests use, and `python/engine/tests/test_fixture_seed.py` gains the re-seed check for the contest rows, beside TASK-069's for the NFL rows. 19 files plus this one.

### Test strategy

- AC-1: `test_contest_schema.py::test_migration_0007_round_trips` (up → down → up in a scratch schema, as `test_nfl_schema.py`); `pnpm db:check` in verify.full.
- AC-2: `test_contest_schema.py`: `test_contest_lines_refuse_update_delete_truncate`, `test_contest_standings_refuse_update_delete_truncate`, `test_entries_cannot_be_hard_deleted`, `test_entry_update_only_soft_deletes`, `test_a_soft_deleted_entry_can_be_re_added`, `test_two_live_entries_for_one_game_are_refused`, plus the entry FK on another contest's line.
- AC-3: `test_picks_schema.py`: `test_a_pick_needs_exactly_one_line` (both, neither), `test_a_contest_pick_inserts_with_no_price`, `test_a_contest_pick_on_another_games_line_is_refused`.
- AC-4: `test_current_picks.py::test_a_contest_pick_has_line_source_contest`; `test_pick_outcomes.py::test_a_contest_pick_has_no_market_units` (won and push); `test_model_record.py::test_contest_picks_leave_the_record_alone` (31-24-1, +4.6u through week 5 with a contest pick inserted); `test_api_shell.py`: a contest pick on a week-6 game leaves the `picks` count unchanged.
- AC-5: `test_contest_schema.py`: `test_the_seed_has_the_user`, `…_the_splash_work_league` (rules == `SPLASH_PRESET`), `…_the_week_6_contest_lines` (10, before Thu 9:14 PM ET), `…_the_week_6_entries`, `…_the_weeks_1_to_5_entries_grade_12_8` (per week), `…_the_standing`.
- Manual: `pnpm db:migrate:test && pnpm db:seed`, then SELECT the week-6 lines and entries → 10 lines; OU +7 at 9:14 PM and BUF −3 at 9:20 PM ET.

### Risks

- `model_record` reads `pick_outcomes`: the new columns go at the end, or the view re-apply fails.
- `ON CONFLICT` on the partial unique index must repeat its `WHERE deleted_at IS NULL`.
- The entry trigger must allow the soft-delete UPDATE while refusing every other change.

## Review log

_Filled by /implement-task. One line per round._

## Blocked

_Only if status is Blocked: what failed, what was tried, best hypothesis, decision needed._

## Metrics

- Verify rounds:
- Review rounds:
- First-pass AC FAILs:
- Plan revisions after approval:
