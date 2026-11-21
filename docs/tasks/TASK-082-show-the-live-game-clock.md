---
id: TASK-082
title: Show the live game clock on This Week and the Contest slate
status: Draft
depends_on: [TASK-074]
size: M
model: sonnet
autonomy: attended
ui: true
plan_status: none
planned_at_commit:
---

# TASK-082 — Show the live game clock on This Week and the Contest slate

## Goal

A game in progress shows its score and the clock ("Live: OSU 24, PUR 3 · Q3 9:12") wherever the design draws a live row, so you can follow a pick while it's being played.

## Context

- Task list: `docs/08-tasklist.md` › M6 › M6.14.
- Data model: `docs/03-data-model.md` › Games & market: `games.period` and `games.clock` (migration `0009`), set by the `scores` job while a game is `in_progress` and NULL otherwise (D-178).
- Design: `design/sample-data.md` § 1 (the live row "Live: OSU 24, PUR 3 · Q3 9:12"); `design/handoff/designs/This Week Wireframe.dc.html`, `Contest Mobile.dc.html`, `Team Desktop.dc.html` and `Team Mobile.dc.html` draw live rows. The plan confirms which screens are in scope against the `Pass … .dc.html` boards.
- Decisions: D-158 (`/slate`), D-171/D-174 (the contest page's response), D-178 (the clock columns: `clock` is CFBD's string as given, e.g. `09:12`, so the API passes it through; overtime periods are 5 and up).
- *From TASK-074 (PR #171):* the clock columns are filled during game windows, but no API response carries them: `/slate`'s `status` is there (`api/slate.py`), `period` and `clock` aren't, and the contest page has neither. Showing them is this task.
- Product: `docs/01-product.md` › F-32 AC-2 (a live pick that's behind shows as live, never as lost, until final).

## Acceptance criteria

Each item names an observable result and an expected value or state.

- [ ] AC-1: `GET /api/py/slate` returns `period` and `clock` for each game: on the fixture's in-progress Ohio State–Purdue row `3` and `"09:12"`, and `null` on a final or scheduled game (API test).
- [ ] AC-2: The contest page's response carries the same two fields for each slate game (API test on a contest game in progress).
- [ ] AC-3: This Week's row for an in-progress game reads "Live: OSU 24, PUR 3 · Q3 9:12" (the design's copy), a final one "Final", and a period of 5 or more shows "OT" (Vitest on the formatter, and the This Week e2e on the fixture row).
- [ ] AC-4: The Contest slate shows the same live text on an in-progress game, and a pick on it that's behind shows as live, never as lost (F-32 AC-2; e2e on the fixture).
- [ ] AC-5: The generated API types (`web/` openapi types, D-155) include the new fields, and the `api-types` Vitest check passes.

## Out of scope

- Filling the clock (the `scores` job, TASK-074).
- Game Detail's live view (M7.7 builds Game Detail's live/final status band, from the same columns), play-by-play or a win-probability chart.
- Refreshing a page by itself while games are live (the page shows what the last load fetched).

## Files likely touched

- `python/api/src/api/slate.py`, `python/api/src/api/contest.py` — the fields
- `python/api/tests/test_api_slate.py`, `python/api/tests/test_api_contest.py`
- `python/db/seeds/fixture/…` — the fixture's live rows get their period and clock
- `web/` — the generated types, the live-text formatter, This Week's and the Contest slate's row
- `web/e2e/…` — the This Week and Contest journeys

## Verification

- Automated: the API tests and the Vitest and e2e cases named in the ACs.
- Manual: `pnpm dev` with the fixture clock on Saturday of week 6 → This Week shows "Live: OSU 24, PUR 3 · Q3 9:12" on the Ohio State–Purdue row.

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
