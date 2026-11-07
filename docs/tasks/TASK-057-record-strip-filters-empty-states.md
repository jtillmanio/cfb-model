---
id: TASK-057
title: Add the record strip, filters and empty states to This Week
status: Review
depends_on: [TASK-056]
size: M
model: sonnet
autonomy: unattended
ui: true
plan_status: approved
planned_at_commit: df380c9
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
- *From TASK-056 (PR #139):* This Week is built (`web/app/(this-week)/`): `SlateView` in `slate.tsx` draws the header, one section per window, the rows and the footer ("Showing N of M games" already compares `games.length` with `counts.games`, so a filter changes the first number only); `loading.tsx` draws the skeleton at the loaded size, so the strip and chips join it; `error.tsx` is shell-less (D-157). The page title row (`SlatePage`) takes a caption, not a strip: add the strip under it. Rows and cells carry `data-slot` / `data-cell` hooks for e2e. TeamChip prints a rank with no fixed-width slot, so a team name with no rank (an FCS opponent) sits a little left of its neighbour; the design gives the rank a 16px right-aligned slot. If you touch the chip, fix it there (not in this task's scope otherwise).

## Acceptance criteria

- [x] AC-1: On the seeded test DB at Sat 2026-10-10 2:15 PM ET, the record strip under the header reads "This week 1-0 · 2 live (IOWA covering, OSU not yet) · 6 to play · +1.0u", with one segment per pick (9) in won, live and to-play states.
- [x] AC-2: A live pick that's behind on the score renders as live ("not yet"), never as lost (a `web/lib` test with a live pick trailing its line, and the fixture's OSU pick).
- [x] AC-3: Clicking the strip, or the "Picks only" chip, shows only the 9 games with a pick and the footer "9 games with a pick · of 54"; clicking again (or "All") shows all 54 with "Showing 54 of 54 games"; the chip's `aria-pressed` follows.
- [x] AC-4: Given a `/slate` response whose games have no lines (a test fixture of the response), every row shows "No line" in Market, the model line, "—" for edge, cover and tier, and the "No line posted yet" note; the strip shows the dashed "No picks this week" note.
- [x] AC-5: Given the off-season response, This Week shows the header "· off-season" and the dashed "No games this week" frame with no table; the "Week 0 kicks off …" line appears only when the response gives the next season's first kickoff.
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

- The next season in the API: `/slate`'s `next_kickoff_at` (the next season's first kickoff, from `seasons.weeks`), the shell naming the next season and its week 0 off-season, and whether a season with no record yet shows the previous season's final record (TASK-053's open question) → docs/tasks/TASK-062-name-the-next-season-in-the-off-season.md (new, Draft), docs/08-tasklist.md § M5.11

## Plan

_Approved 2026-11-07 at the plan gate. The owner settled five points there:_

1. _AC-4's no-lines note follows the design's two titles: "No picks yet" when no game has a line (the board's `noLines`), "No picks this week" when lines exist and nothing clears the threshold. AC-4's wording says "No picks this week" for the first case; this ruling wins over it, and the owner rewords the AC._
2. _The "Week 0 kicks off …" line reads an optional `next_kickoff_at` the API doesn't send yet, proved with a test fixture, so it stays hidden until the follow-up task adds the field._
3. _TASK-053's open question: the shell stays as it is, so the caption and top bar say 2026, not the design's "2027 · Week 0"; the web app never guesses the next season. The off-season copy drops "title game on Mon Jan 18" because the response has no such date. Both differ from `20-offseason-empty-desktop.png` and `21-offseason-empty-mobile.png` on purpose._
4. _AC-5 is proved by a component test, not a third e2e server pair; `python/api/tests/test_api_slate.py` already covers the response at the off-season clock. The real page at that clock stays a manual check._
5. _The other chips (FBS vs FBS, Starred, Conference, Window, Ranked) stay out, as Out of scope allows._

**Steps**

1. `web/lib/slate.ts` + `web/lib/slate.test.ts` (pure, clock-free):
   - `liveCover(game)`, pulled out of `notesFor` so the row note and the strip share it: covering, on the number, or not yet, never lost (F-32).
   - `recordStrip(games)`: one segment per pick (won, lost, push, live, to play; void picks are left out, since those games are never played), covering picks first among the live ones; the record through `formatRecord`, the live note ("IOWA covering, OSU not yet"), the to-play count, units through `formatUnits`, and a label per segment for its title.
   - `showingText(filter, counts)`: "Showing 54 of 54 games", "9 games with a pick · of 54" ("1 game with a pick").
   - The no-picks note from the response (the two titles above; the threshold printed from `rules`, D-055) and the off-season copy, from `shell.season`.
2. `web/app/(this-week)/slate-filters.tsx` (new, thin client file): holds the All / Picks only state and renders the chips, the strip's button wrapper and the footer count. Rows stay server-rendered and CSS hides non-pick rows and windows with no pick, so 54 rows never become client props and the page keeps its one API call. The chips use `FilterChips` controlled: clicking Picks only again, or All, returns to all.
3. `web/app/(this-week)/record-strip.tsx` (new): one tree at the boards' sizes (40px at 1440 with the live note and the "Show picks" / "Showing picks · show all" call to action, 44 at 768 without either, 56 on a phone on two lines). A real `<button>` with `aria-pressed`, whose `aria-label` is the full sentence. Segments are tokens only. With no picks, the dashed note replaces it and it isn't a button.
4. `web/app/(this-week)/slate-empty.tsx` (new): the dashed "No games this week" frame with no table, chips or strip; its links go to `/rankings` and `/performance` (404 until those screens ship, as game rows do today).
5. `web/app/(this-week)/slate.tsx`: the strip and chips under the header, the header gap at 12px as the board has it, the branch on `offseason`, the caption "2026 · off-season" through `slateCaption`, the footer through `slate-filters.tsx`, and Tier printing "—" at 1440 on no-line rows only (TASK-056's AC-2 keeps lined rows with no tier blank).
6. `web/app/(this-week)/loading.tsx`: strip bars at the loaded heights; the chips stay real (Loading board).
7. `web/components/filter-chips.tsx`: `label` takes a node, so phones read "Picks" as the board draws it.
8. Lighthouse: `FilterChips` brings Radix Toggle onto `/`. If the fixture run breaks the 186,000 JS budget, re-measure and write the reason in `docs/02-architecture.md` › Performance checks.

**Files** (12 at most; no schema or API change): `web/app/(this-week)/record-strip.tsx`, `slate-filters.tsx`, `slate-empty.tsx` (new); `slate.tsx`, `loading.tsx`, `slate.test.tsx`; `web/lib/slate.ts`, `slate.test.ts`; `web/components/filter-chips.tsx`; `web/app/globals.css` (the filter's `display: none !important` rule, added during Phase 2; plan revision 1); `web/e2e/this-week.spec.ts`; `scripts/perf/budget.json` and `docs/02-architecture.md` only if the budget moves. Not in "Files likely touched": `filter-chips.tsx`, `slate.test.tsx` and the `(this-week)` route group, which replaces `web/app/this-week/`, `web/app/page.tsx` and `web/app/loading.tsx`. `web/playwright.config.ts` and `web/e2e/test-env.ts` don't change (point 4 above).

**Test strategy**

| AC | Proved by |
|---|---|
| AC-1 | `this-week.spec.ts` › the strip's text and 9 segments in their states, at 390 and 1440; `slate.test.ts` › `recordStrip` |
| AC-2 | `slate.test.ts` › a live pick trailing its line is live, never lost; `this-week.spec.ts` › the fixture's OSU pick reads "not yet" |
| AC-3 | `this-week.spec.ts` › the strip and the chip each toggle: 9 then 54 visible rows, both footers, `aria-pressed` on the chip |
| AC-4 | `slate.test.tsx` › a no-lines response: "No line", the model line, "—" for edge, cover and tier, the "No line posted yet" note, the dashed note; `slate.test.ts` › the two titles |
| AC-5 | `slate.test.tsx` › the off-season response: "· off-season", the dashed frame, no table, no chips, no strip; the "Week 0 kicks off …" line only with `next_kickoff_at` |
| AC-6 | `this-week.spec.ts` › the skeleton's strip is as tall as the loaded strip, the chips are present, the pulse stops under reduced motion; the fixture Lighthouse run |

**Risks / open questions**

- Tailwind's order can let `md:grid` beat the filter's `hidden` (TASK-056's `min-[1440px]:` problem), so the filter's rule uses `!important`.
- The fixture hasn't been run for this plan: the Iowa and OSU live scores come from `design/sample-data.md` until e2e runs.
- With no picks, the Picks only chip shows no rows and the footer "0 games with a pick · of 54"; the dashed note above says why.

## Review log

Verify R1 PASS | Audit R1 PASS | Spec R1 CHANGES (AC-5 off-season season from `shell.season`; reduced-motion check on the strip bars) → fixed in 276ef90 | UI: not run by ui-verifier (needs the e2e session signing); the Playwright spec checks the strip, filter and skeleton at 390 and 1440 (not independent)

## Blocked

_Only if status is Blocked: what failed, what was tried, best hypothesis, decision needed._

## Metrics

- Verify rounds: 1
- Review rounds: 1 (one fix commit)
- First-pass AC FAILs: 1 (AC-5, found by the spec review)
- Plan revisions after approval: 1 (`globals.css` added to Files)
