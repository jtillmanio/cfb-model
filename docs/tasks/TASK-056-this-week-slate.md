---
id: TASK-056
title: Build the This Week slate
status: Ready
depends_on: [TASK-051, TASK-054, TASK-055]
size: M
model: sonnet
autonomy: attended
ui: true
plan_status: none
planned_at_commit:
---

# TASK-056 — Build the This Week slate

## Goal

Signed in, the home page is This Week: the current week's games grouped by kickoff window, each reading Market → Model → Edge with cover %, tier, win % and the pick's status, as a compact table on desktop, priority columns at 768 and cards on a phone.

## Context

- Task list: `docs/08-tasklist.md` › M5 › M5.6. Features F-01, F-02, F-06, F-10 (`docs/01-product.md` › Observable outcomes).
- Screen: S-01 This Week (`docs/05-ui-design-brief.md` › Screen inventory). Design: `design/handoff/designs/This Week Desktop.dc.html`, `This Week Mobile.dc.html`, `This Week Tablet.dc.html`, board `This Week.dc.html`, `Pass C1 - Slate Contest Game.dc.html` C1a–e (Pass boards win, D-094). Shots: `01-this-week-desktop.png`, `02-this-week-mobile.png`, `28-this-week-tablet.png`. Spec: `design/README.md` § Screens › 1 (slate grid `24px 100px minmax(0,1fr) 388px 92px 32px 76px 160px 16px`; rows grouped by day/time window; row click → Game Detail; footer legend printed from the spec's thresholds), § Components (GameRow, GameCard, LineMovementCell, SpreadDisplay's second line for "moved since pick").
- Decisions: D-084 (This Week's desktop slate is compact), D-061/D-063 (edge pill, tiers), D-055 (thresholds from the spec, never constants), D-132/D-140 (CLV sign: "Picked at −2.5 → now −3.5 · CLV −1.0"), D-096 (error state without saved copies), D-097, D-101/D-125 (this route's Lighthouse budget is set on the fixture build; the fixture's full Week 6 slate from TASK-055 is the large case), D-047.
- The page takes over `/` (today `web/app/page.tsx` redirects to `/teams`); e2e journey 1 (02 › Testing strategy) expects This Week at `/` after sign-in.
- Hidden until their features ship (stub notes): the Spread / Total / Both control (F-11) and the star (F-14); the Best lines tab (M7.3); weather flags (F-08).
- Live games show their status and mono scores; the period and clock ("Q3 9:12") aren't stored yet (TASK-055's context), so the live row shows the live dot with "Live" until they are. The design's rule "never dot alone" still holds.
- *From TASK-016 (PR #59):* the fixture has each game's opener (Sun 6:00 AM ET) and current line (Thu 9:02 PM ET) only, plus Texas vs Oklahoma's four and BYU's three snapshots; if a sparkline AC cites `this-week-data.js`'s illustrative in-between points (e.g. LSU −2.5, −2.5, −3, −3.5), this task adds them. (The ACs below don't, so no fixture change is planned.)
- TASK-014 (M5.8, time screen-to-screen taps) waits on this task; its `depends_on` lists this task.
- `.claude/rules/web.md`: one API call per page, `loading.tsx` at the loaded size with the pulse off under reduced motion, e2e at phone and desktop widths.
- *From TASK-051 (PR #125), open question for the plan:* TASK-051 builds the market cell's current-season states only; `Market Extras.dc.html` also draws a past-season variant (opening and closing line only, two dots, dashed join, "Past season" title). Does a past week on This Week need it, and if so, does this task build it?
- *From TASK-051 (PR #133):* the shared pieces are `TeamChip`, `MarketCell` and `DataTable` (`web/components/`, D-154). `DataTable` takes plain-data columns and rows (cells already rendered, `sortValues` by column), so a server page passes them in directly. `TeamChip` has no loading state and no hover or focus state of its own: `Components.dc.html` › Team chip draws a loading skeleton (a 20px circle and a 72×14 bar) and, for a chip that links, an `--accent` fill with an underlined name and the focus ring. The slate's `loading.tsx` and any linked chip add them. `/slate` returns `logo_url` (Out of scope above), and the chip renders it from the app's `/logos/<id>.png` route.
- *From TASK-054 (PR #137):* the app shell is built (`web/components/shell/`, D-157). This Week draws `<AppShell active="this-week" path="/" shell={data.shell} state="ready">` around its content and its `loading.tsx` draws it with no data, as `web/app/teams/` does. The page catches its call's failure itself and draws `<AppShell state="error">` around `ApiUnreachable` on the server; `error.tsx` stays shell-less, because no client module may import the shell (`server-only-shell.test.ts`); the 1.5 s wake note comes from racing the page's one call with `raceWakeNote` (`web/app/teams/page.tsx`). The shell draws the stale banner from `shell.stale`, so This Week doesn't draw its own. The top bar's week box is a static label (`top-bar.tsx`): if this task steps weeks, the arrows and the season/week list go there.
- *From TASK-055 (feat/055-slate-endpoint):* `/slate` is built (`api/src/api/slate.py`, D-158; type it from `components["schemas"]["SlateOut"]`). Each game's `model.edge`, `model.side` and `model.cover_prob` are against the current line (Ole Miss @ LSU +4.9 now), and `pick` carries the line it was made at with its own `edge` and `cover_prob` (+3.9 at −2.5), `clv_so_far`, `clv` (null until the close), `result` and `units`; `rules` holds the thresholds and tiers. AC-2's "59%" for Purdue @ Ohio State isn't what the fixture gives: the pick's `model_prob` and `engine.core` both give Φ(3.7/13.8) = 0.6057, so the cell prints 61% from the response (the design's 59% is illustrative; numbers follow docs/04, CLAUDE.md › Which document wins). Live rows have no period or clock yet (`docs/03-data-model.md` › Proposed additions, M6.8).

## Acceptance criteria

- [ ] AC-1: Signed in on the seeded test DB at Sat 2026-10-10 2:15 PM ET, `/` shows the header "This Week · 2026 · Week 6 · 54 games · 9 picks" and rows grouped under day/time window headings ("FRI NIGHT", "SAT NOON", "SAT AFTERNOON", "SAT NIGHT", per the design's windows); each row links to `/games/<id>` for its game.
- [ ] AC-2: Purdue @ Ohio State reads, left to right, "OSU −27.5", "OSU −31.2", a filled "+3.7 OSU" pill, "59%", tier "B" and "OSU 99%"; Kansas State @ Utah shows "+0.6 UTAH" as plain muted text and no tier; the footer legend prints the thresholds from the response's pick rules, not constants (a test with different thresholds changes the legend and the pill).
- [ ] AC-3: Row states render as designed: UNLV @ Boise State "Final" with 24 / 31 and "✓ No pick · UNLV covered"; Purdue @ Ohio State live with the live dot, a text label and mono scores "PUR 3 · OSU 24"; Furman @ Clemson "No line" and "FCS · no lines yet"; Texas vs Oklahoma "N · Dallas"; Ole Miss @ LSU's second line "Picked at −2.5 → now −3.5 · CLV −1.0".
- [ ] AC-4: The Market cell shows the opener and sparkline muted before the current line (Purdue @ Ohio State "−28 ⟍ OSU −27.5"); Texas vs Oklahoma's sparkline has one point per snapshot in the response; a game with an unchanged line draws a flat line; Furman @ Clemson shows no opener.
- [ ] AC-5: At 1440 the table is compact (header 32px, rows 36px); at 768 it shows the design's priority columns and drops Win %; at 390 each game is a card showing Market, Model and Edge without expanding, with no horizontal scroll and every tap target ≥ 44px (e2e journey 7).
- [ ] AC-6: `/` has a `loading.tsx` drawn at the loaded size (header, window headings and rows as bars, pulse off under reduced motion) and an error state with no saved data; the route has its Lighthouse entry and a budget from the fixture run (`web/lib/perf.test.ts` passes, and `docs/02-architecture.md`'s table records the measured numbers).

## Out of scope

- The record strip, All / Picks only filters, and the empty states (lines not posted, off-season): TASK-057.
- Best lines (M7.3), totals and the Spread / Total / Both control (F-11), stars (F-14), weather (F-08), the alerts bell.
- Game Detail itself (M7.7); rows link to it and 404 until then.
- Stepping to another week from the top bar's week selector, unless the plan gate finds it small (the endpoint already takes a week).
- The live period and clock (needs a schema change; see Context).

## Files likely touched

- `web/app/page.tsx`, `web/app/loading.tsx`, `web/app/error.tsx` — This Week at `/`
- `web/app/this-week/slate-table.tsx`, `game-row.tsx`, `game-card.tsx`, `slate-legend.tsx` (or under `web/components/`) — new
- `web/lib/slate.ts`, `web/lib/slate.test.ts` — new: kickoff windows, row state from the response
- `web/lib/api.ts` — `getSlate()`
- `web/e2e/this-week.spec.ts` — new; `web/e2e/auth.spec.ts` — `/` now lands on This Week
- `scripts/perf/routes.mjs`, `scripts/perf/budget.json`, `docs/02-architecture.md` › Performance checks

## Verification

- Automated: `web/e2e/this-week.spec.ts` at 390 and 1440 (AC-1 to AC-5) plus a 768 case; `web/lib/slate.test.ts` (windows, row states, thresholds); `web/lib/perf.test.ts`; the fixture Lighthouse run.
- Manual: `pnpm dev`, signed in → expected: `/` looks like `01-this-week-desktop.png` at 1440, `28-this-week-tablet.png` at 768 and `02-this-week-mobile.png` at 390 (the numbers match on the fixture, except the live clock and the record strip).

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
