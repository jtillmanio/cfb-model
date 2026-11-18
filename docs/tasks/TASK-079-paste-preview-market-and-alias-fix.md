---
id: TASK-079
title: Show the market and the model in the paste preview, and let a saved alias be corrected
status: Draft
depends_on: [TASK-072]
size: M
model: opus
autonomy: attended
ui: true
plan_status: none
planned_at_commit:
---

# TASK-079 — Show the market and the model in the paste preview, and let a saved alias be corrected

## Goal

The Contest paste preview shows each row's market line beside the contest's, as the board draws it, and the re-paste diff says how each moved line changes the model's cover % and rank. A team picked for the wrong name can be corrected later.

## Context

- *From TASK-072 (feat/task-072-contest-paste-flow):* the board's parsed table has a Market column ("Market = consensus now", "differs · …") and the RepasteDiff (C2e) has cover %, rank and "for the model's side" columns, but `POST /contests/{id}/import/preview` (TASK-070, D-172) carries neither the market line nor the model's numbers, so TASK-072 left them out. The preview is a POST that isn't a screen's page call, so it isn't held to the one-wave budget (contest_import.py's docstring), but each extra read should still be one statement.
- *From TASK-072 (feat/task-072-contest-paste-flow):* team picks are saved as `team_aliases` at Confirm (D-175), and `POST /contests/{id}/aliases` refuses a name already mapped to another team (409). Nothing can change or remove an alias, so a wrong pick stays wrong for every later paste. Open question for the plan: a correction route on the API (an UPDATE of a reference row, or a new row that wins), or a Settings › Contests control (M8.8)?
- Screen: S-02 (`docs/05-ui-design-brief.md` › Screen inventory). Design: `design/handoff/designs/Contest Desktop.dc.html` (`parse`, `repaste`), `Pass C1 - Slate Contest Game.dc.html` C2e.
- Decisions: D-172, D-174, D-175.

## Acceptance criteria

Each item names an observable result and an expected value or state.

- [ ] AC-1: Pasting the fixture Week 6 text at Thu 2026-10-08 10:00 PM ET shows each matched row's market line beside its contest line, and "differs" with the gap on the rows whose lines differ (the fixture's lines give 8).
- [ ] AC-2: A re-paste that moves Texas vs Oklahoma from TEX −7 to TEX −6.5 shows the model's cover % and rank for that game before and after the move.
- [ ] AC-3: An alias saved for the wrong team can be changed to the right one, and the next paste matches the row to the right game.

## Out of scope

- The ranked slate (TASK-073).
- Manual "add game" entry.

## Files likely touched

- `python/api/src/api/contest_import.py`, `python/api/tests/test_api_contest_import.py`
- `web/lib/api-types.ts`, `web/lib/contest.ts`, `web/lib/contest.test.ts`
- `web/app/contest/paste-flow.tsx`, `repaste-diff.tsx`, `paste-flow.test.tsx`

## Verification

- Automated: `uv --directory python run pytest api/tests/test_api_contest_import.py`, `pnpm --dir web exec vitest run lib/contest.test.ts app/contest`
- Manual: paste the fixture text → expected: market lines beside the contest lines, 8 marked "differs".

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
