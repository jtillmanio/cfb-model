---
id: TASK-066
title: Carry the last game's date for the "season ended" line
status: Draft
depends_on: [TASK-062]
size: S
model: sonnet
autonomy: attended
ui: true
plan_status: none
planned_at_commit:
---

# TASK-066 — Carry the last game's date for the "season ended" line

## Goal

The off-season frame says when the season ended, as the design draws it: "The 2026 season ended with the title game on Mon Jan 18."

## Context

- Task list: `docs/08-tasklist.md` › M5 › M5.14.
- Design: `design/handoff/designs/App States Desktop.dc.html` (`frame="offseason"`).
- *From TASK-062 (feat/task-062-name-next-season-off-season):* the response carries only the next season; the design's last-game date needs a field (the newest game's date, Eastern) on `/slate` or the shell, and the frame's body to print it.
- Decisions: D-164.

## Acceptance criteria

- [ ] AC-1: Given the API at the off-season clock (Mon 2027-02-08 6:00 AM ET), `/slate` carries the date of the last game of the season that ended (expected: the fixture's newest game date).
- [ ] AC-2: At that clock the frame body reads "The 2026 season ended with the title game on <weekday> <month> <day>", and omits the clause when the field is null.

## Out of scope

- Any change to how a stored date is interpreted.

## Files likely touched

- `python/api/src/api/shell.py` or `slate.py`, `python/api/tests/`: the field
- `web/lib/api-types.ts`, `web/lib/slate.ts`, `web/app/(this-week)/slate-empty.tsx`: the copy

## Verification

- Automated: the API test at the off-season clock; `web/lib/slate.test.ts`
- Manual: `pnpm dev` at the off-season clock → expected: `20-offseason-empty-desktop.png`.

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
