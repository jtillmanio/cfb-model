---
id: TASK-065
title: Pull the next season's calendar in the off-season
status: Review
depends_on: [TASK-062]
size: S
model: sonnet
autonomy: attended
ui: false
plan_status: approved
planned_at_commit: 70e694b
---

# TASK-065 — Pull the next season's calendar in the off-season

## Goal

In the off-season the app already names the coming season and shows its kickoff line, because the jobs have pulled that season's calendar.

## Context

- Task list: `docs/08-tasklist.md` › M5 › M5.13.
- *From TASK-062 (feat/task-062-name-next-season-off-season):* D-164 names the next season from `seasons.weeks`, but the jobs pull a season's calendar only from July (`engine.jobs.current_season`, with its games), so before July `next_season` and `next_kickoff_at` are null and the app shows "2026 · off-season" with no kickoff line. Pull the next season's calendar (calendar only, no games) once the season ends. Mind the CFBD call budget (never re-fetch completed weeks).
- Decisions: D-164.

## Acceptance criteria

- [x] AC-1: Given the clock after the title game and before July, when the calendar job runs, then `seasons` holds a row for the next year with its weeks (expected: `/slate` carries `next_kickoff_at`, the opening Saturday).
- [x] AC-2: Given that row already exists, when the job runs again, then it makes no CFBD call (expected: zero calls).

## Out of scope

- Pulling the next season's games or lines.

## Files likely touched

- `python/engine/src/engine/jobs.py`: when the next calendar is due
- `python/engine/tests/`: AC-1, AC-2

## Verification

- Automated: `uv --directory python run pytest engine/tests` (the new job tests)
- Manual: none.

## Follow-ups

_Work noticed during this task and deliberately left out. Each bullet ends `→ <path> § <section>` (where it was placed) or `→ not tracked: <reason>`. See `.claude/skills/track-follow-ups/classify.md`; the PR's Follow-ups section is copied from here._

- Decision: the jobs pull the next season's calendar once the season ends, retry an empty one daily, and pull the season's calendar again in July; amends D-164 (approved at plan) → docs/decisions.md § D-167
- `docs/02-architecture.md` › Jobs gains the off-season calendar pull (approved at plan) → docs/02-architecture.md § 4. Jobs (GitHub Actions)
- `docs/03-data-model.md` call budget gains the off-season calendar calls (approved at plan) → docs/03-data-model.md § CollegeFootballData (CFBD): primary
- Schema review (minor): a July re-pull that comes back empty or shorter than the off-season copy would hide it from `backfill.season_types`, which reads only the newest calendar; reading the newest calendar with weeks would fix it, a backfill change for a case CFBD hasn't shown → docs/decisions.md § D-167 (Revisit if)

## Plan

_Approved by the owner in the session prompt (2026-11-12: "Accept the plan right away")._

**Steps**
1. `jobs.py`: after a job's week pulls, when the season has stored games and none is still to come (the `lines` rule, `due_weeks`) and `season + 1` has no usable calendar saved, pull `/calendar?year=season+1`: one counted call, calendar only, no games. A saved calendar with no weeks counts as missing once it is a day old, so a pull made before CFBD has the schedule is tried again daily instead of kept forever.
2. `jobs.py` `_pull_missing`: a season's calendar saved before the season became the job's season (`current_season(fetched_at) < season`, the off-season copy) is pulled once more, so the season works from an in-season calendar (`backfill.season_types` reads it to start the bowl pulls). One call a year.
3. `jobs.py` `run`: stage `season` and `season + 1` (`sync_raw(seasons=...)`), so the next season's calendar reaches `seasons` through the existing publish. The summary gains a "Next season's calendar" line.
4. Docs: the `jobs.py` docstring and README › Jobs (pull and stage steps).

**Files**
- `python/engine/src/engine/jobs.py`: steps 1–3
- `python/engine/tests/test_jobs.py`: the AC tests
- `README.md` › Jobs: what the jobs pull and stage (not in "Files likely touched")
- Close-out: `docs/decisions.md` (new decision, amends D-164), `docs/02-architecture.md` › Jobs, `docs/03-data-model.md` › call budget (approved at plan), `docs/08-tasklist.md` Done tick

**Test strategy**
- AC-1 `test_after_the_title_game_lines_pulls_the_next_calendar`: clock 2026-02-15, `engine job lines` with the real `publish_lake` into `db_conn`; `seasons` holds 2026 with the served weeks, the earliest starting on the opening Saturday, 2026-08-22T07:00:00Z (the value `/slate`'s `next_kickoff_at` reads; TASK-062's `test_the_offseason_slate_carries_the_next_kickoff`).
- AC-2 `test_a_stored_next_calendar_costs_no_call`: a second run at the same clock makes zero CFBD calls (the ledger and the request list).
- Also `test_an_empty_next_calendar_is_tried_again_a_day_later`, `test_the_season_pulls_its_calendar_again_in_july`, `test_no_next_calendar_while_a_game_is_to_come`.

**Risks**
- CFBD may return a partial calendar early (no postseason week); step 2's July re-pull covers the season's own use of it. A week CFBD drops between the two copies would linger in staging (newest pull per week); accepted.
- The session runs on Opus while the task says `sonnet`; the owner asked for the whole run in this session.

## Review log

_Filled by /implement-task. One line per round._

Verify R1 PASS (typecheck, lint, db:check, test, build; e2e 88 passed, 24 skipped) | Audit R1 PASS (4 discriminating, 2 guards) | Spec R1 APPROVE | Schema R1 APPROVE (2 minor: staging-scope wording fixed in 0c0ad1c; July re-pull caveat recorded in D-167)

## Blocked

_Only if status is Blocked: what failed, what was tried, best hypothesis, decision needed._

## Metrics

- Verify rounds: 1
- Review rounds: 1
- First-pass AC FAILs: 0
- Plan revisions after approval: 0 (the season-over test gained "the postseason has started" while implementing, after two existing tests showed games alone fire early; inside step 1, plus one extra guard test)
