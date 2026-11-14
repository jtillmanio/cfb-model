---
id: TASK-068
title: Add the current_contest_lines, contest_results and current-standing views
status: Done
depends_on: [TASK-067, TASK-041]
size: M
model: opus
autonomy: attended
ui: false
plan_status: approved
planned_at_commit: f52eac6
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

- [x] AC-1: `current_contest_lines` gives one row per contest and game. Its line is the newest `contest_lines` snapshot captured before the game's cutoff (kickoff, or the end of `game_date` in Eastern time when the kickoff is TBA, as `current_picks`), shown beside `game_market`'s current spread and the shown version's newest model line. A snapshot inserted after kickoff leaves the row unchanged (test). On the seeded DB, Texas vs Oklahoma reads the contest's TEX −7 beside the market's TEX −6.5.
- [x] AC-2: `contest_results` grades each live (not soft-deleted) entry against the spread of the contest line it was made at. The result is `won`, `lost` or `push` on a final game, `pending` while the game is scheduled or in progress, and `void` when it's canceled or postponed. Points follow the contest's `push` rule: with `zero` a push scores 0; a test contest with `half` scores 0.5; with `void`, the push doesn't count.
- [x] AC-3: The same grading runs on the model's top N per contest week, labelled apart from your entries. A soft-deleted entry is never graded.
- [x] AC-4: On the seeded DB through week 5, your season record is 12-8 and the model's top 4 is 11-9. The week rows are W1 3-1 / 2-2, W2 2-2 / 3-1, W3 3-1 / 2-2, W4 1-3 / 2-2, W5 3-1 / 2-2. With Week 6's games not yet final, week 6 gives both 0 points, with your two entries pending.
- [x] AC-5: The current-standing view returns the newest `contest_standings` row per contest: on the seeded DB, 3rd of 14, 1 point behind the leader. A newer row for the same contest replaces it in the view (test).
- [x] AC-6: Each graded entry carries CLV against the close the plan chose, NULL until that close exists. Reading one contest's rows from each view shows no full-table scan of `contest_entries`, `contest_lines` or `picks` in `EXPLAIN` (test).

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

- TASK-071 reads `contest_results` and `contest_record` filtered to the shown model version (each version has its own model rows); whoever writes the model's contest picks in production writes every slate game's pick before the contest week's first kickoff (D-171: a later pick never enters the top N, so a job after a Thursday-night game would drop the week), with `expected_value` = 2p − 1 at even money and tier NULL unless that plan decides otherwise (approved at plan; reworded after spec review R2) → docs/tasks/TASK-071-contest-page-api.md § Context
- Decision D-171: contest CLV against `game_market`'s close; the model's top N fixed at the contest week's first kickoff, by `model_prob`, then kickoff, then game; push points; contest-pick storage conventions (approved at plan) → docs/decisions.md § D-171
- `current_contest_lines` repeats the shell's shown-version rule (`api/shell.py` `SHOWN`) in SQL; a change to one must follow in the other (spec review R1) → docs/tasks/TASK-071-contest-page-api.md § Context
- `contest_results`' first-kickoff lateral runs once per contest pick rather than once per (contest, week); fine at one contest's ~10 games a week, and the EXPLAIN test guards the one-contest read (schema review R2) → not tracked: accepted as is at today's volume
- The fixture loader takes a contest week as the CFB run week (true for weeks 1-5; a mismatch fails the seed with a KeyError, never seeds bad rows) (schema review R1) → not tracked: fixture only, fails loudly

## Plan

_Written by /plan-batch or /implement-task Phase 1. Approved by the user (plan_status: approved) before any code is written._

Approved 2026-11-14 (owner): add a week-2 fixture game rather than amend AC-4; contest CLV against `game_market`'s close; the `0008` index; the extra `contest_record` view; soft-deleted contests' picks out of `current_picks` and `pick_outcomes`.

**Why the fixture changes:** the fixture's week 2 has 5 final games and the model's side covers 2 of them at any contest line within 3 points of the close, so the model's W2 3-1 is unreachable; on today's slates the model's top 4 grades 10-10.

**Steps**
1. Migration `0008`: partial index `ix_contest_entries_contest_id_live` on `contest_entries (contest_id) WHERE deleted_at IS NULL` (`uq_contest_entries_live` leads with `user_id`, so a read by contest alone would scan); the same index in `models.py`.
2. `080_current_contest_lines.sql`: one row per (live contest, game): the newest `contest_lines` snapshot captured before the game's cutoff (kickoff, or the end of `game_date` ET when TBA), beside `game_market`'s current spread and the shown version's model line (the shell's rule, per the game's sport and season: production, else the newest candidate with a succeeded scheduled run that season; its newest prediction from a succeeded run before the cutoff; `model_spread_home = −pred_margin`). NFL games: no model line.
3. `090_contest_results.sql`: one row per graded item. `picker 'you'`: each live entry at its contest line. `picker 'model'`: `pick_outcomes`' current contest picks, ranked within (contest, version, period) by `model_prob` desc, then kickoff, then game id; rank ≤ `picks_per_period` kept. `result` won/lost/push/pending/void (as `pick_outcomes`); `points` 1 a win, 0 a loss, a push 0 (`zero`), 0.5 (`half`) or NULL (`void`: doesn't count); pending and void NULL. `clv` against `game_market`'s close (D-132's sign), NULL until it exists.
4. `100_contest_record.sql`: per contest, picker (and model version), period: W-L-P, pending, voids and points, `breakdown` `week` and `to_date`; periods come from the contest's lines, so a week with no graded rows still reads 0 points.
5. `110_current_contest_standing.sql`: the newest `contest_standings` row per live contest (by `entered_at`, then id).
6. `050_current_picks.sql`, `060_pick_outcomes.sql`: a soft-deleted contest's picks drop out.
7. Fixture: `generate_contest.py` adds two hand-set final week-2 CFB games between teams idle that week (lines, score, v1.0 prediction; revision 1 below) and redraws each week's slate with the seed until your result and the model's top-4 result both hold, with no tie at the 4th/5th cut; it writes the model's contest pick on every slate game (unshrunk cover probability, D-140's fixture convention; `edge_pts = pred_margin + line`; `expected_value = 2p − 1`; tier NULL; made 1 minute after the line's capture). `contest_history.json` regenerated; `fixture.py` loads its game, prediction and picks.
8. Docs: views README, `docs/03-data-model.md` › Views, D-171.

**Files**
- `python/db/migrations/versions/0008_contest_entries_by_contest.py` (new), `python/db/src/db/models.py`
- `python/db/views/080_current_contest_lines.sql`, `090_contest_results.sql`, `100_contest_record.sql` (not in Files likely touched: the record AC-4 reads), `110_current_contest_standing.sql` (new), `050_current_picks.sql`, `060_pick_outcomes.sql`, `README.md`
- `python/db/seeds/fixture/generate_contest.py`, `contest_history.json`, `python/engine/src/engine/fixture.py`
- `python/db/tests/test_contest_views.py` (new), `test_current_picks.py`, `python/engine/tests/test_fixture_seed.py` (if counts move)
- `docs/03-data-model.md`, `docs/decisions.md`, `docs/tasks/TASK-071-contest-page-api.md` (follow-up note)

**Test strategy** (`python/db/tests/test_contest_views.py`)
- AC-1: `test_texas_oklahoma_reads_the_contest_line_beside_the_market`, `test_a_snapshot_after_kickoff_leaves_the_line_unchanged`
- AC-2: `test_entries_grade_won_lost_push_pending_void`, `test_push_points_follow_the_contest_rule` (zero, half, void contests)
- AC-3: `test_the_model_top_n_is_graded_apart`, `test_a_soft_deleted_entry_is_never_graded`; `test_current_picks.py`: a soft-deleted contest's picks drop out
- AC-4: `test_the_seeded_season_is_12_8_against_11_9` (week rows and week 6 at 0 points, 2 pending)
- AC-5: `test_the_seeded_standing_is_3rd_of_14`, `test_a_newer_standing_replaces_it`
- AC-6: `test_clv_is_null_until_the_close_exists`, `test_one_contest_reads_without_a_full_scan` (each view, `model_rows.explain`)

**Revision 1 (Phase 2):** two week-2 games, not one. The model's natural week-2 wins include Arizona State at Wisconsin at 58.6%, and every week-2 loss sits at or above it, so a 3-1 top 4 needs a third win (Wake Forest at Clemson, 63.9%) and a weaker loss in 5th (Navy at SMU, 53.2%). The soft-deleted-contest test sits in `test_contest_views.py` (it checks all six views at once), and `test_model_record.py` scopes two queries to market picks and to its own contest, since the seeded contest picks now sit on week-5 games.

**Revision 2 (schema review R1, owner's choice 2026-11-14):** the model's top N is fixed at the contest week's first kickoff: each game's newest contest pick made before it, not `current_picks`, so a pick written after a game was played can't bump it out (hard rule 4). `contest_results` defaults a missing `push` to `zero` and `counted` is never NULL; `contest_record` finds a contest's model versions once. Tests: `test_the_model_top_n_is_fixed_at_the_weeks_first_kickoff`, `test_a_contest_missing_its_push_rule_scores_a_push_0`.

**Risks:** `current_contest_lines` repeats the shell's shown-version rule in SQL (per game's season rather than the coming week's); the two agree for a contest's own season. The weeks 2–5 slates and entries change (week 1's stays); your 12-8 still holds and TASK-067's test recomputes it.

## Review log

_Filled by /implement-task. One line per round._

Verify R1 PASS → R2 FAIL(1: the views README's test cell held two paths) → R3 PASS | Audit R1 PASS | Spec R1 CHANGES (RULE: 03 and the README didn't say a soft-deleted contest's picks drop out) → R2 CHANGES (follow-up wording only; fixed, rechecked by the close-out check) | Schema R1 CHANGES (MAJOR: hindsight top N; 2 MINOR) → R2 APPROVE (3 MINOR: a pass test and the 0008 docstring fixed, the per-pick lateral accepted)

## Blocked

_Only if status is Blocked: what failed, what was tried, best hypothesis, decision needed._

## Metrics

- Verify rounds: 3
- Review rounds: 2
- First-pass AC FAILs: 0
- Plan revisions after approval: 2
