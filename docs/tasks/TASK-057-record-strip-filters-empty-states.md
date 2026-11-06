---
id: TASK-057
title: Add the record strip, filters and empty states to This Week
status: Ready
depends_on: [TASK-056]
size: M
model: sonnet
autonomy: unattended
ui: true
plan_status: none
planned_at_commit:
---

# TASK-057 — Add the record strip, filters and empty states to This Week

## Goal

This Week shows how the model's picks are doing this week at a glance (won, live, to play, units), filters to picks only, and says clearly why it's empty when lines aren't posted yet or the season is over.

## Context

- Task list: `docs/08-tasklist.md` › M5 › M5.7. Feature F-32 (`docs/01-product.md` › Observable outcomes: "This week 1-0 · 2 live (IOWA covering, OSU not yet) · 6 to play · +1.0u", one segment per pick, clicking toggles Picks only; a live pick that's behind shows live, never lost).
- Screen: S-01 This Week. Design: `design/handoff/designs/This Week.dc.html` (header, LiveRecordStrip, filter chips; `showingTxt`: "Showing N of 54 games", "N games with a pick · of 54"), `Pass C1 - Slate Contest Game.dc.html` C1b (desktop, lines not posted yet) and C1d's mobile sibling ("lines not posted yet", mobile), `App States Desktop.dc.html` / `App States Mobile.dc.html` (`frame="offseason"`: "This Week 2027 · Week 0 · off-season", "No games this week", "Week 0 kicks off …"), `Loading States.dc.html`. Shots: `20-offseason-empty-desktop.png`, `21-offseason-empty-mobile.png`, `01-this-week-desktop.png`. Spec: `design/README.md` § Components (LiveRecordStrip; filter chips), § Feedback (empty: dashed frame, says which rule produced it and what's next).
- C1's note for lines not posted: "every row shows 'No line' in Market, the model line, '—' for edge, cover and tier, and a 'No line posted yet' note"; with no picks, "the record strip becomes a dashed 'No picks this week' note".
- Data: everything comes from TASK-055's `/slate` response (picks with `pick_outcomes`' `result`, `units`, live status and scores; the off-season marker; null market fields). Whether a live pick is "covering" is computed from the live score against the pick's line (a pure helper with tests); it's never stored.
- Decisions: D-142 (grading lives in the views), D-096 (no saved copies), D-070 (no "Lock" verbs).
- The stale-lines banner is the shell's (TASK-054), not this task's.
- The off-season state needs the API at the off-season clock (Mon 2027-02-08 6:00 AM ET). e2e already runs a second server pair for the cold API (`web/playwright.config.ts`, `COLD_PREVIEW_URL`); the plan picks between another pair at the off-season clock and a component-level test of the off-season render.
- Unattended: UI only, following TASK-056's components and e2e pattern; no API or schema change.
- *From TASK-053 (PR #135), open question for the plan:* in the off-season, TASK-053's shell block gives the last season with games, no week, and that season's record (its AC-4). The design differs in two places. Its off-season top bar reads "2027 · Week 0", which would come from the next season's `seasons.weeks` (App States `frame="offseason"`). Its pre-season card reads "Model · 2025 final" (`frame="team"`). Decide whether the shell block, and with it TASK-053's AC-4 rule, should name the next season and its week 0, and whether a season with no record yet should show the previous season's final record.
- *From TASK-056 (feat/056-this-week-slate):* This Week is built (`web/app/(this-week)/`): `SlateView` in `slate.tsx` draws the header, one section per window, the rows and the footer ("Showing N of M games" already compares `games.length` with `counts.games`, so a filter changes the first number only); `loading.tsx` draws the skeleton at the loaded size, so the strip and chips join it; `error.tsx` is shell-less (D-157). The page title row (`SlatePage`) takes a caption, not a strip: add the strip under it. Rows and cells carry `data-slot` / `data-cell` hooks for e2e. TeamChip prints a rank with no fixed-width slot, so a team name with no rank (an FCS opponent) sits a little left of its neighbour; the design gives the rank a 16px right-aligned slot. If you touch the chip, fix it there (not in this task's scope otherwise).

## Acceptance criteria

- [ ] AC-1: On the seeded test DB at Sat 2026-10-10 2:15 PM ET, the record strip under the header reads "This week 1-0 · 2 live (IOWA covering, OSU not yet) · 6 to play · +1.0u", with one segment per pick (9) in won, live and to-play states.
- [ ] AC-2: A live pick that's behind on the score renders as live ("not yet"), never as lost (a `web/lib` test with a live pick trailing its line, and the fixture's OSU pick).
- [ ] AC-3: Clicking the strip, or the "Picks only" chip, shows only the 9 games with a pick and the footer "9 games with a pick · of 54"; clicking again (or "All") shows all 54 with "Showing 54 of 54 games"; the chip's `aria-pressed` follows.
- [ ] AC-4: Given a `/slate` response whose games have no lines (a test fixture of the response), every row shows "No line" in Market, the model line, "—" for edge, cover and tier, and the "No line posted yet" note; the strip shows the dashed "No picks this week" note.
- [ ] AC-5: Given the off-season response, This Week shows the header "· off-season" and the dashed "No games this week" frame with no table; the "Week 0 kicks off …" line appears only when the response gives the next season's first kickoff.
- [ ] AC-6: The loading skeleton (`web/app/loading.tsx`) includes the record strip and filter chips at their loaded size, pulse off under reduced motion; the page's Lighthouse budget still passes on the fixture build, or is re-measured with the written reason `docs/02-architecture.md` › Performance checks asks for.

## Out of scope

- The stale-lines banner (TASK-054) and the API's off-season and no-lines responses (TASK-055).
- The other chips the design draws (FBS vs FBS, Starred, Conference, Window, Ranked) and the sort menu, unless the plan gate finds them small: Starred waits for F-14.
- Best lines' empty state (C1a, C1c, C1d; M7.3).
- Score refresh during game windows (the `scores` job, M6.8).
- Contest's record strip in points (M6.7).

## Files likely touched

- `web/app/this-week/record-strip.tsx`, `slate-filters.tsx`, `slate-empty.tsx` — new
- `web/app/page.tsx`, `web/app/loading.tsx` — strip, chips, empty states, skeleton
- `web/lib/slate.ts`, `web/lib/slate.test.ts` — strip segments, live covering, filter counts
- `web/e2e/this-week.spec.ts` — AC-1, AC-3, and AC-5 if served by a second server
- `web/playwright.config.ts`, `web/e2e/test-env.ts` — an off-season server pair, if the plan picks one
- `scripts/perf/budget.json`, `docs/02-architecture.md` › Performance checks — only if the budget moves

## Verification

- Automated: `web/lib/slate.test.ts` (segments, live never lost, filter counts, no-lines rows), `web/e2e/this-week.spec.ts` at 390 and 1440, the fixture Lighthouse run.
- Manual: `pnpm dev` on the test DB at the fixture clock → expected: the strip as in `01-this-week-desktop.png`; Picks only shows 9 rows; with the off-season clock → expected: `20-offseason-empty-desktop.png` and `21-offseason-empty-mobile.png`.

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
