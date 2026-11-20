---
id: TASK-080
title: Filter the contest views' contest_lines joins by contest
status: Draft
depends_on: []
size: S
model: opus
autonomy: attended
ui: false
plan_status: none
planned_at_commit:
---

# TASK-080 — Filter the contest views' contest_lines joins by contest

## Goal

Reading one contest's results or record reads only that contest's contest lines, whatever the table's size, so the "no full scan" checks hold on any test database.

## Context

- *From TASK-072 (PR #169), schema review R1:* `contest_results` joins `contest_lines l ON l.id = e.contest_line_id` (python/db/views/090_contest_results.sql:77, and :114 for the model's picks) and `contest_record` does the same (100_contest_record.sql:39), on the line id alone; the contest filter reaches only entries and contests. Once `contest_lines` holds more than the fixture's rows, the planner (with sequential scans priced out) switches to a merge join over a full `pk_contest_lines` scan with no condition. On a local test DB that e2e journey 3 has written to (its confirms add lines, which can't be deleted, D-038), `db/tests/test_contest_views.py::test_one_contest_reads_without_a_full_scan[contest_results|contest_record]` and `api/tests/test_api_contest.py::test_the_record_is_read_for_the_contest_alone` fail, on base code too. CI is unaffected: it runs pytest before e2e on a fresh database.
- The likely fix is adding `AND l.contest_id = e.contest_id` (and the pick's contest) to those joins; `contest_lines` has `UNIQUE (id, contest_id, game_id)`. Views are re-applied after every migration (`.claude/rules/database.md`); changing one is a database change, so the plan says so and asks.
- *From TASK-073 (feat/073-contest-ranked-slate-tray-results):* e2e journey 4 adds to the same pile: `engine seed pick-journey` copies the work league's ten Week 6 lines into a new contest on every seed (about twenty per Playwright project per run), and lines can't be deleted. A local test DB that several e2e runs have written to has about 900 `contest_lines` rows, and the three tests above fail on it on base code too. The planner then reads `contest_lines` through `pk_contest_lines` with a Filter, and one subplan reads every row. The schema review of TASK-073 also names the picks join (`FROM picks p JOIN contest_lines l ON l.id = p.contest_line_id`, in 090 and 100) as one the contest filter doesn't reach: a join on `l.contest_id = e.contest_id` fixes the entries side, but `picks` has no contest column, so drive that branch from `contest_lines` (a lateral into `picks` that Postgres can't flatten, such as `OFFSET 0`) so the plan starts from the contest whatever the table sizes.
- Decisions: D-171, D-174, D-175.

## Acceptance criteria

Each item names an observable result and an expected value or state.

- [ ] AC-1: With 100 more `contest_lines` rows for another contest in the test transaction, `EXPLAIN SELECT * FROM contest_results WHERE contest_id = <the fixture contest>` (sequential scans priced out) reads `contest_lines` only by index with a condition (a test); the same for `contest_record`.
- [ ] AC-2: `contest_results` and `contest_record` return the same rows for the fixture contest as before the change (the existing view tests pass unchanged).

## Out of scope

- Any other view, or a change to what the views compute.

## Files likely touched

- `python/db/views/090_contest_results.sql`, `python/db/views/100_contest_record.sql`
- `python/db/tests/test_contest_views.py`

## Verification

- Automated: `uv --directory python run pytest db/tests/test_contest_views.py api/tests/test_api_contest.py`
- Manual: none.

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
