---
id: TASK-068
title: Add the current_contest_lines, contest_results and current-standing views
status: Ready
depends_on: [TASK-067, TASK-041]
size: M
model: opus
autonomy: attended
ui: false
plan_status: none
planned_at_commit:
---

# TASK-068 — Add the current_contest_lines, contest_results and current-standing views

## Goal

Each contest's current line per game, your graded entries, the model's graded top N, and your current league standing come from views. Results are graded against the contest's line with that contest's push rule, and nothing derived is stored.

## Context

- Task list: `docs/08-tasklist.md` › M6 › M6.2. Hard rule 1: results, records and the current contest line are views.
- Data model: `docs/03-data-model.md` › Views (`current_contest_lines`, `contest_results`; the `EXPLAIN` rule for single-item reads), › Your data (`ContestRules.push`: `zero|half|void`), › Proposed additions (`contest_standings`: "the current standing is the latest row per contest, read through a view").
- Product: `docs/01-product.md` › Observable outcomes › F-32 AC-3 ("this week so far" counts points), F-33 AC-1 and AC-3 (entries and the model's picks graded separately against the contest line).
- Decisions: D-029, D-045 (Splash push = 0), D-095 (a contest's games are all locked only after its last kickoff), D-120 and D-162 (`game_market`), D-142 (how `current_picks` and `pick_outcomes` pick the current row and grade it; follow the same cutoff rule).
- **The model's top N** is what TASK-067's plan settled: its contest `picks` rows, CFB-only or not. Rank them within each contest week by the displayed cover probability (`model_prob`, D-143), keep the contest's `picks_per_period`, and grade them like your entries. If the plan finds that "top N" can't be read from stored rows alone, it says so before adding anything stored.
- **Contest-entry CLV** (task list note): decide at the plan gate which close it's measured against: the contest's last snapshot before kickoff, or `game_market`'s close. Record the choice in a decision. The sign follows D-132 and D-140.
- **Fixture:** this task seeds the model's weeks 1–5 contest picks (and the contest lines and predictions they need) graded W1 2-2, W2 3-1, W3 2-2, W4 2-2, W5 2-2 (11-9) beside TASK-067's entries (12-8). Every fixture row has `source = 'fixture'` (D-089).
- *From TASK-067 (PR #159):* the plan gate settled the model's top N as **CFB-only**: a `picks` row needs a `prediction_id`, so the design's NFL "gap side" is computed on read and never stored or counted in the model record (D-170). The weeks 1–5 contest slates in `contest_history.json` are 5 final CFB games each, every one with a v1.0 prediction, so this task's "Model top 4 11-9" picks can be stored at those contest lines. `current_picks` and `pick_outcomes` already partition contest picks by contest (`contest_id` is their last column) and give them `units` and `risked` NULL.
- *From TASK-067 (PR #159):* `current_picks` and `pick_outcomes` read contest picks without checking their contest's `deleted_at` (`.claude/rules/database.md`: filter `deleted_at IS NULL` on every read). Decide whether a soft-deleted contest's picks drop out of them or only out of the contest views.
- *From TASK-067 (PR #159):* `contest_entries` has only the partial live index `uq_contest_entries_live (user_id, contest_id, game_id) WHERE deleted_at IS NULL`. If `contest_results` reads a contest's entries by contest alone, or reads soft-deleted ones, add the index it needs with an `EXPLAIN` test. `picks` has `ix_picks_contest_line_id` for reading a contest's picks through its lines.

## Acceptance criteria

- [ ] AC-1: `current_contest_lines` gives one row per contest and game. Its line is the newest `contest_lines` snapshot captured before the game's cutoff (kickoff, or the end of `game_date` in Eastern time when the kickoff is TBA, as `current_picks`), shown beside `game_market`'s current spread and the shown version's newest model line. A snapshot inserted after kickoff leaves the row unchanged (test). On the seeded DB, Texas vs Oklahoma reads the contest's TEX −7 beside the market's TEX −6.5.
- [ ] AC-2: `contest_results` grades each live (not soft-deleted) entry against the spread of the contest line it was made at. The result is `won`, `lost` or `push` on a final game, `pending` while the game is scheduled or in progress, and `void` when it's canceled or postponed. Points follow the contest's `push` rule: with `zero` a push scores 0; a test contest with `half` scores 0.5; with `void`, the push doesn't count.
- [ ] AC-3: The same grading runs on the model's top N per contest week, labelled apart from your entries. A soft-deleted entry is never graded.
- [ ] AC-4: On the seeded DB through week 5, your season record is 12-8 and the model's top 4 is 11-9. The week rows are W1 3-1 / 2-2, W2 2-2 / 3-1, W3 3-1 / 2-2, W4 1-3 / 2-2, W5 3-1 / 2-2. With Week 6's games not yet final, week 6 gives both 0 points, with your two entries pending.
- [ ] AC-5: The current-standing view returns the newest `contest_standings` row per contest: on the seeded DB, 3rd of 14, 1 point behind the leader. A newer row for the same contest replaces it in the view (test).
- [ ] AC-6: Each graded entry carries CLV against the close the plan chose, NULL until that close exists. Reading one contest's rows from each view shows no full-table scan of `contest_entries`, `contest_lines` or `picks` in `EXPLAIN` (test).

## Out of scope

- The contest page API and its ranking of the open slate (TASK-071): the views grade, they don't rank open games.
- Writing the model's contest picks in production (TASK-070's or TASK-071's plan decides who inserts them).
- Points for confidence contests (`scoring` other than `point_per_win`).
- Any screen.

## Files likely touched

- `python/db/views/080_current_contest_lines.sql`, `090_contest_results.sql`, `100_current_contest_standing.sql`: new (numbering follows `python/db/views/README.md`)
- `python/db/tests/test_contest_views.py`: new, AC-1 to AC-6
- `python/db/seeds/fixture/contest.json` (and its generator): the model's weeks 1–5 contest picks, lines and predictions
- `python/engine/src/engine/fixture.py`: loads them
- `python/db/tests/test_model_record.py`, `test_pick_outcomes.py`: only if the added rows move a seeded expectation (they shouldn't, since contest picks aren't market picks)
- `docs/03-data-model.md` › Views; `docs/decisions.md`

## Verification

- Automated: `uv --directory python run pytest db/tests/test_contest_views.py` passes, and so does the whole DB suite on the reseeded fixture.
- Manual: `pnpm db:seed`, then `SELECT` from `contest_results` for the Splash work league → expected: you 12-8, model 11-9 through week 5.

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
