---
id: TASK-081
title: Serve the clock, tier and pick threshold on the contest page, and show them on the slate
status: Draft
depends_on: [TASK-073]
size: M
model: sonnet
autonomy: attended
ui: true
plan_status: none
planned_at_commit:
---

# TASK-081 — Serve the clock, tier and pick threshold on the contest page, and show them on the slate

## Goal

The contest slate shows how long until each game locks, the model's tier on a pick, and "under 2.5" on an edge below the pick threshold, as the Contest board draws them.

## Context

- Task list: `docs/08-tasklist.md` › M6 › M6.13.
- Design: `design/handoff/designs/Contest Desktop.dc.html` (`now` thu / fri / sun: the "Locks in" column, the tier badge and the "under 2.5" caption), `Contest Mobile.dc.html`; shots `design/handoff/screenshots/03-contest-desktop.png`, `04-contest-mobile.png`.
- Decisions: D-055 (the active version's spec owns the pick threshold), D-063 (tier badge), D-176 (what TASK-073 left out and why), D-177.
- *From TASK-073 (PR #170):* the slate draws neither the "Locks in" countdown nor the tier badge nor the "under 2.5" caption, because `ContestPageOut` carries no clock (`ShellOut` has none), no tier on `ContestModelOut` and no pick threshold. A countdown computed from the browser's clock would be wrong under the fixture clock and for anyone whose clock is off, so the response has to carry the API's `now`. The page's Kickoff column shows the time until then.
- *From TASK-073 (PR #170), open question for the plan:* `GET /api/py/contest` takes about 1.4 s on the test DB and a second call at the same time waits for the first (three at once took 4 s each), so a save followed by the page's refresh feels slow and an e2e run needs long timeouts. Is that the wave's connections to Neon (NullPool opens one per query), the view plans (TASK-080), or the single worker? Measure before adding fields, and say in the plan whether the cost moves.

## Acceptance criteria

Each item names an observable result and an expected value or state.

- [ ] AC-1: With the API's clock at Thu 2026-10-08 10:00 PM ET, `GET /api/py/contest` returns `now` = `2026-10-09T02:00:00Z`, the shown version's pick threshold (the spec's `min_edge_pts`), and for each game with a model its `tier`, equal to `current_picks`'s tier for that game and null where the game is not a pick (a pytest).
- [ ] AC-2: At that clock the slate's Locks-in column reads "1d 21h" for Texas vs Oklahoma, and at Fri 2026-10-09 8:12 PM it reads "Locked" for UNLV @ Boise State (component test; e2e).
- [ ] AC-3: A model row whose edge clears the threshold shows its tier badge, and one below it reads "under <threshold>" with the number from the response, not a constant in the web code (component test).
- [ ] AC-4: The new fields add no query to the page's wave (the existing query-budget test passes unchanged).

## Out of scope

- Live game clocks and scores on contest rows (TASK-074 stores them).
- Changing how the response ranks games or what `top_n` means (D-171, D-174).

## Files likely touched

- `python/api/src/api/contest.py`, `python/api/tests/test_api_contest.py`: the clock, the threshold and the tier
- `web/lib/api-types.ts` (generated), `web/lib/contest.ts`, `web/lib/contest.test.ts`: the countdown text and the tier
- `web/app/contest/ranked-slate.tsx`, `web/app/contest/ranked-slate.test.tsx`: the column, the badge and the caption
- `web/e2e/contest.spec.ts`: the countdown at Thu 10:00 PM and "Locked" at Fri 8:12 PM

## Verification

- Automated: `uv --directory python run pytest api/tests/test_api_contest.py`, `pnpm --dir web exec vitest run lib/contest.test.ts app/contest` and `pnpm --dir web exec playwright test e2e/contest.spec.ts` pass.
- Manual: at Thu 10:00 PM, open /contest → expected: Texas vs Oklahoma reads "1d 21h" under Locks in, and a pick shows its tier letter.

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
