---
id: TASK-065
title: Pull the next season's calendar in the off-season
status: Draft
depends_on: [TASK-062]
size: S
model: sonnet
autonomy: attended
ui: false
plan_status: none
planned_at_commit:
---

# TASK-065 — Pull the next season's calendar in the off-season

## Goal

In the off-season the app already names the coming season and shows its kickoff line, because the jobs have pulled that season's calendar.

## Context

- Task list: `docs/08-tasklist.md` › M5 › M5.13.
- *From TASK-062 (feat/task-062-name-next-season-off-season):* D-164 names the next season from `seasons.weeks`, but the jobs pull a season's calendar only from July (`engine.jobs.current_season`, with its games), so before July `next_season` and `next_kickoff_at` are null and the app shows "2026 · off-season" with no kickoff line. Pull the next season's calendar (calendar only, no games) once the season ends. Mind the CFBD call budget (never re-fetch completed weeks).
- Decisions: D-164.

## Acceptance criteria

- [ ] AC-1: Given the clock after the title game and before July, when the calendar job runs, then `seasons` holds a row for the next year with its weeks (expected: `/slate` carries `next_kickoff_at`, the opening Saturday).
- [ ] AC-2: Given that row already exists, when the job runs again, then it makes no CFBD call (expected: zero calls).

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
