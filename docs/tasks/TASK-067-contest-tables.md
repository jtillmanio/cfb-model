---
id: TASK-067
title: Add users, contests, contest_lines, contest_entries and contest_standings
status: Ready
depends_on: [TASK-016, TASK-069]
size: M
model: opus
autonomy: attended
ui: false
plan_status: none
planned_at_commit:
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
