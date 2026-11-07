---
id: TASK-061
title: Step This Week through weeks and seasons and draw a past season's market cell
status: Review
depends_on: [TASK-056]
size: M
model: sonnet
autonomy: attended
ui: true
plan_status: approved
planned_at_commit: 5a65e90
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

- [x] AC-1: Signed in on the seeded test DB at Sat 2026-10-10 2:15 PM ET, pressing the left arrow in the top bar opens Week 5 (expected: the caption reads "2026 · Week 5 · …" with that week's game and pick counts from `/slate`, and the arrows and label show Week 5).
- [x] AC-2: The season/week list opens from the label and lists the seasons and weeks that have games (expected: choosing 2026 · Week 3 shows Week 3's games and no other week's).
- [x] AC-3: A past week's final games show their closing line in the market cell as the past-season variant (expected: opening and closing line, two dots joined by a dashed line, title "Past season"); a game with no line draws "No line".
- [x] AC-4: At 390 the selector opens as the design's sheet and every target is ≥ 44px; at 768 and 1440 nothing scrolls sideways.
- [x] AC-5: With the API stopped, a stepped week shows "API unreachable" with Retry and no saved copy (D-096).

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

- Candidate decision (next free ID from `next-id.ps1`): the week URL scheme, `/slate`'s `weeks` list, and when the past-season market cell is drawn. The owner overrode this task's "any change to `/slate`'s response" out-of-scope line at the plan gate (2026-11-07) → `docs/decisions.md` § D-163 (approved at plan)
- The top bar's week selector on the other screens (it stays a static label there) → not tracked: each screen's own task decides (approved at plan)

## Plan

_Approved by the owner 2026-11-07 at `5a65e90`._

_Note: the plan's step 1 said the weeks query runs on the `(sport_id, season, week)` index; it is a grouped read of the sport's games (the index doesn't cover `season_type`), accepted because the table is small (schema review)._

**Owner's answers at the plan gate (2026-11-07):**
- The week list's data: add `weeks` to `/slate` (a sixth query in its wave), overriding the Out of scope line "any change to `/slate`'s response".
- AC-3's past-season variant: every final game in a week before the coming week draws open → close as the variant, even with a full snapshot history; the coming week's finals keep today's cell.

**Steps**
1. **API: `weeks` on `/slate`.** A sixth wave query `weeks` (`SELECT DISTINCT season, season_type, week FROM games WHERE sport_id = :sport`, on the `(sport_id, season, week)` index) and `SlateOut.weeks: [{season, season_type, week}]`, in season, regular before postseason, week order. The wave test's budget goes 5 → 6 (limit ≤ 6). Regenerate `web/lib/api-types.ts` (`pnpm api:types`).
2. **URL.** `/?season=2026&week=5`, plus `&type=postseason` for the postseason; the coming week stays at `/`. Bad or partial params fall back to the coming week. `getSlate(week?)` passes `season`, `season_type`, `week`. The error state's Retry and the stale banner's Refresh reload the stepped URL.
3. **Pure helpers (`web/lib/slate.ts`).** `parseWeekParams`, `weekHref` (the coming week → `/`), `weekNeighbours` (previous/next week with games, across seasons, e.g. 2026 Week 1 → 2025 Postseason), `weekLabel` ("2026 · Week 5", "2025 · Postseason"), `isPastWeek(slate)` (the shown week is before the shell's coming week; with no coming week, i.e. the off-season, every week is past). Weeks below 1 are left out of the list (the API refuses `week < 1`).
4. **Past-season market cell.** In a past week a final game's row carries open → close (close = `closing_spread_home`, else the current line) and `past`. `MarketCell past`: the opener, the two-dot dashed SVG (hollow open, filled close), then the close; title "Past season: opening and closing line only". Stacked: the close over the dots and "opened −3.5" (Market Extras › Mobile card). No line → "No line".
5. **Top bar selector.** An optional `weekNav` prop through `AppShell` to `TopBar`; only This Week passes it, so other screens keep the static label. The label names the shown week, not the coming one. Desktop: [‹][2026 · Week 5 ⌄][›] as drawn, the arrows links, disabled at the ends. Tablet: the "CFB · 2026 · Week 6 ⌄" box opens the list. Phone: the "2026 · Week 6 ⌄" label opens it.
6. **Season/week list** (`web/components/shell/week-picker.tsx`, a client island, a native popover like the More sheet), laid out after the Rankings time machine (Rankings Desktop / Mobile). ≥ 768: a season column and a four-column week grid; choosing a week navigates. 390: a bottom sheet with season chips, the week grid and a "Show 2026 · Week 3" button; every target ≥ 44px. The coming week carries the live dot; "This week" returns to `/`. Copy the boards don't draw (header "Week", "Season · back to {earliest}") is adapted from the Rankings picker.
7. e2e and unit tests; the decision row.

**Files**
- `python/api/src/api/slate.py`: the `weeks` query and field *(not in Files likely touched)*
- `python/api/tests/test_api_slate.py`: the weeks list, the budget of 6 *(not listed)*
- `web/lib/api-types.ts`: regenerated *(not listed)*
- `web/lib/api.ts`: `getSlate(week?)`
- `web/lib/slate.ts`, `web/lib/slate.test.ts`: the helpers and the past row
- `web/components/market-cell.tsx`, `web/components/market-cell.test.tsx`: the past variant
- `web/components/shell/week-picker.tsx` (new): the list *(not listed)*
- `web/components/shell/top-bar.tsx`: arrows and the label opening the list
- `web/components/shell/app-shell.tsx`, `web/components/shell/app-shell.test.tsx`: the `weekNav` prop *(not listed)*
- `web/app/(this-week)/page.tsx`, `web/app/(this-week)/slate.tsx`: read the params, pass the week, `past`
- `web/e2e/this-week.spec.ts`: stepping, the list, the variant, the widths, the stopped API
- `docs/decisions.md`: the decision row

**Test strategy**
- AC-1: e2e "the left arrow opens Week 5" (desktop): caption "2026 · Week 5 · 15 games · 15 picks", label "2026 · Week 5".
- AC-2: e2e "the list opens from the label and 2026 · Week 3 shows only Week 3's games"; pytest `test_the_weeks_with_games_are_listed`; vitest `weekNeighbours`, `parseWeekParams`.
- AC-3: `market-cell.test.tsx` (two dots, dashed join, title, the close, "No line", stacked); vitest `rowView` past vs coming week; e2e on Week 5's market cells.
- AC-4: e2e at 390 (the sheet opens, every target's box ≥ 44px) and at 768 and 1440 (`scrollWidth ≤ clientWidth`).
- AC-5: e2e in the switch-API block: a stepped week with the API stopped shows "API unreachable" with Retry and no games.

**Risks**
- A stored `week = 0` would be refused by the API (`ge=1`), so the list leaves it out.
- The phone sheet's pending-then-Show flow vs desktop's navigate-on-click lives in one client component.

## Review log

Verify R1 FAIL(1: `isPastWeek` on a null shell) → R2 PASS | Audit R1 CHANGES (e2e not discriminable on base; all passed on the branch; 2 assertions added) → PASS | Spec R1 CHANGES (follow-up destination) → fixed | Schema R1 APPROVE (3 minors: literal-order test and `season_type` guard added, index wording corrected) | UI R1 PASS (AC-1 to AC-4; AC-5 by e2e)

## Blocked

_Only if status is Blocked: what failed, what was tried, best hypothesis, decision needed._

## Metrics

- Verify rounds: 2
- Review rounds: 1
- First-pass AC FAILs: 0
- Plan revisions after approval: 0
