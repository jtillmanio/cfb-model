---
id: TASK-061
title: Step This Week through weeks and seasons and draw a past season's market cell
status: Draft
depends_on: [TASK-056]
size: M
model: sonnet
autonomy: attended
ui: true
plan_status: none
planned_at_commit:
---

# TASK-061 — Step This Week through weeks and seasons and draw a past season's market cell

## Goal

From the top bar's week selector, step This Week to the previous or next week and pick any season and week from the list, and read a past season's lines in the market cell the design draws for it (opening and closing line only).

## Context

- Task list: `docs/08-tasklist.md` › M5 › M5.10. Feature F-01 (`docs/01-product.md` › Observable outcomes). Screen: S-01 This Week and the shell's top bar (S-16).
- *From TASK-056 (PR #139):* `/slate` already takes a week (`api/src/api/slate.py`, `season`, `season_type`, `week` query parameters); TASK-056's page calls it with none, so it shows the coming week. The top bar's week box is a static label today (`web/components/shell/top-bar.tsx`): the arrows and the season/week list ("back to 2014", `design/README.md` › Navigation) go there. Out of TASK-056's scope.
- *From TASK-056 (PR #139), answers TASK-051's open question:* `Market Extras.dc.html` also draws a past-season variant of the market cell (opening and closing line only, two dots, a dashed join, a "Past season" title). TASK-051 built only the current-season states (`web/components/market-cell.tsx`); a past week needs the variant, so this task builds it. TASK-056 added the `stacked` layout beside the inline one: a past-season variant needs both layouts.
- Design: `design/handoff/designs/Market Extras.dc.html` (past-season line-movement cell), `This Week.dc.html` and the boards' week selector; `design/handoff/designs/App States Desktop.dc.html` for the selector's states.
- Decisions: D-150 (the coming week), D-096 (no saved copies).
- Open questions for the plan: the URL for a chosen week (`/?season=2026&week=5` against a path segment), how a week with no `line_snapshots` (a backfilled season) reaches the variant (`market.snapshots` empty and a closing line), and how the shell's "coming week" label reads when a past week is shown.

## Acceptance criteria

- [ ] AC-1: Signed in on the seeded test DB at Sat 2026-10-10 2:15 PM ET, pressing the left arrow in the top bar opens Week 5 (expected: the caption reads "2026 · Week 5 · …" with that week's game and pick counts from `/slate`, and the arrows and label show Week 5).
- [ ] AC-2: The season/week list opens from the label and lists the seasons and weeks that have games (expected: choosing 2026 · Week 3 shows Week 3's games and no other week's).
- [ ] AC-3: A past week's final games show their closing line in the market cell as the past-season variant (expected: opening and closing line, two dots joined by a dashed line, title "Past season"); a game with no line draws "No line".
- [ ] AC-4: At 390 the selector opens as the design's sheet and every target is ≥ 44px; at 768 and 1440 nothing scrolls sideways.
- [ ] AC-5: With the API stopped, a stepped week shows "API unreachable" with Retry and no saved copy (D-096).

## Out of scope

- The record strip, filters and empty states: TASK-057.
- Game Detail, and any change to `/slate`'s response.
- Time zone settings (M8.8): times stay Eastern.

## Files likely touched

- `web/components/shell/top-bar.tsx` — arrows and the season/week list
- `web/components/market-cell.tsx`, `web/components/market-cell.test.tsx` — the past-season variant
- `web/app/(this-week)/page.tsx`, `web/lib/api.ts`, `web/lib/slate.ts` — pass the week to `getSlate()`
- `web/e2e/this-week.spec.ts` — stepping and the variant

## Verification

- Automated: `web/e2e/this-week.spec.ts` (stepping, the list, the variant, the stopped API); `web/components/market-cell.test.tsx` (the variant).
- Manual: `pnpm dev`, signed in, press the left arrow → expected: Week 5 opens and its market cells show the past-season variant.

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
