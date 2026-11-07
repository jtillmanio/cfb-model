---
id: TASK-062
title: Name the next season in the off-season
status: Draft
depends_on: [TASK-057]
size: M
model: sonnet
autonomy: attended
ui: true
plan_status: none
planned_at_commit:
---

# TASK-062 — Name the next season in the off-season

## Goal

In the off-season the app names the coming season and its week 0 (the design's "2027 · Week 0 · off-season" and "Week 0 kicks off Sat Aug 28, 2027"), instead of naming the season that just ended.

## Context

- Design: `design/handoff/designs/App States Desktop.dc.html` and `App States Mobile.dc.html` (`frame="offseason"`); shots `20-offseason-empty-desktop.png`, `21-offseason-empty-mobile.png`.
- Decisions: D-156 (the shell block rides in each screen's one call), D-157, D-158 (`/slate`).
- *From TASK-057 (PR #141), open question for the plan:* TASK-053's open question stayed open. TASK-057 left the shell as it was: in the off-season `/slate` sends `season: null`, `shell.season` is the last season with games and the top bar, the caption and the empty frame's copy name that season ("2026 · off-season", "The 2026 season has ended"). The design names the next season ("2027 · Week 0") and adds "title game on Mon Jan 18". Decide: whether the shell block names the next season and its week 0 (from `seasons.weeks`); whether a season with no record yet shows the previous season's final record ("Model · 2025 final"); and whether the response carries the last game's date for the "season ended" line.
- TASK-057 reads an optional `next_kickoff_at` on `/slate` (`web/lib/slate.ts` `Slate`, `offseasonNote`): add the field to the API and the web type then, and the "Week 0 kicks off …" line appears with no web change.
- The web app never guesses the next season; any new name comes from the API.

## Acceptance criteria

- [ ] AC-1: Given the API at the off-season clock (Mon 2027-02-08 6:00 AM ET), `/slate` carries `next_kickoff_at`, the next season's first kickoff from `seasons.weeks` (expected: the fixture's value; null when the next season has no weeks yet).
- [ ] AC-2: At that clock This Week's frame shows "Week 0 kicks off <weekday> <month> <day>, <year>" from that field, and hides the line when the field is null.
- [ ] AC-3: The plan settles and records (a decisions-log row, if it needs one) whether the shell's season and week name the next season, and AC-4 follows that ruling.
- [ ] AC-4: The caption and top bar name the season the ruling picks (expected: "2027 · Week 0 · off-season" if the next season is named).

## Out of scope

- The stale-lines banner and the week selector (TASK-061).
- Any change to how a stored date or line is interpreted.

## Files likely touched

- `python/api/src/api/slate.py`, `python/api/tests/test_api_slate.py` — `next_kickoff_at` and the shell block
- `web/lib/api-types.ts` — regenerated
- `web/lib/slate.ts`, `web/app/(this-week)/slate-empty.tsx` — drop the optional type
- `docs/decisions.md` — the ruling, if it needs a row

## Verification

- Automated: the API test at the off-season clock; a component test of the frame with the field set and null.
- Manual: `pnpm dev` at the off-season clock → expected: `20-offseason-empty-desktop.png`.

## Follow-ups

_Work noticed during this task and deliberately left out._

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
