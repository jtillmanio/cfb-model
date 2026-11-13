---
id: TASK-073
title: Build the ranked contest slate, pick tray and results
status: Ready
depends_on: [TASK-071, TASK-072]
size: M
model: sonnet
autonomy: unattended
ui: true
plan_status: none
planned_at_commit:
---

# TASK-073 — Build the ranked contest slate, pick tray and results

## Goal

The Contest page ranks the week's games against the contest's lines and marks the model's top 4. You add picks with one tap, see them in a tray with when each line was locked in, and follow results and your league standing against the model.

## Context

- Task list: `docs/08-tasklist.md` › M6 › M6.7.
- Screen: S-02 (`docs/05-ui-design-brief.md` › Screen inventory; › Screens › 7. Contest).
- Design: `design/handoff/designs/Contest Desktop.dc.html` (`now` thu / fri / sun) and `Contest Mobile.dc.html`; boards `Contest.dc.html` and `Pass C1 - Slate Contest Game.dc.html`: C2c and C2f "pick failed to save" (desktop, mobile), C2d "every game locked"; light mode in `Pass D - Light Mode.dc.html` (D02); data shape in `contest-data.js` (`rank`, `tray`).
- Reference screenshots: `design/handoff/screenshots/03-contest-desktop.png`, `04-contest-mobile.png`.
- Product: `docs/01-product.md` › Observable outcomes › F-03 AC-2 and AC-3, F-04 AC-1 to AC-3, F-32 AC-3, F-33 AC-1 and AC-2.
- Architecture: `docs/02-architecture.md` › End-to-end journeys › 4, › Test-only sign-in and clock (Thu 10:00 PM and Fri 8:12 PM ET).
- Decisions: D-068 (every number through `web/lib/format.ts`), D-070 (users "add" picks; no "Lock" verbs), D-095 (all locked only after the last kickoff), D-096, D-157.
- **Pattern to copy:** TASK-072's page, Server Actions and signed POST (`web/app/contest/`, `web/lib/api.ts`). This Week's slate, filters and record strip (`web/app/(this-week)/slate.tsx`, `slate-filters.tsx`, `record-strip.tsx`). Shared components `web/components/team-chip.tsx`, `market-cell.tsx`, `edge-pill.tsx`, `tier-badge.tsx`, `result-marker.tsx`, `filter-chips.tsx`, `data-table.tsx`.
- **Numbers come from the response.** The screen prints TASK-071's cover %, gap and market-implied %, and counts the ≠ rows from its flag. F-04 AC-3's "Line ≠ market 7" is sample data; the fixture's lines give 8.
- **Clipboard:** "Copy picks to enter on Splash" writes plain text. The format is drawn on the board.
- *From TASK-069 (PR #157):* NFL teams from nflverse publish with no color (only the 8 fixture NFL teams carry `contest-data.js`'s colors), so a real NFL chip needs a fallback color or nflverse's team file (D-169).

## Acceptance criteria

- [ ] AC-1: At Thu 2026-10-08 10:00 PM ET on the seeded DB, the slate lists the week's games in the response's order with the "MODEL'S TOP 4" cutoff under row 4 and, beside it, "Next best #5" with that row's line and cover %. NFL rows read "No model yet", the gap as "<n> pts off mkt → <team>" and "~<n>% mkt-implied", each from the response.
- [ ] AC-2: A row whose contest line differs from the market shows the market line under the contest line with a ≠ chip naming the difference and the side. The chip is blue (token) when the difference is better for the ranked side and orange (token) when it's worse. The "Line ≠ market" chip shows the count of flagged rows and filters to exactly those rows.
- [ ] AC-3: One tap on a side adds a pick, a second tap on the same side removes it, and a tap on the other side switches it. No control or copy says "Lock". The tray reads "Your picks 2 of 4", with "Locked in at OU +7 · Thu 9:14 PM" and "BUF −3 · Thu 9:20 PM". "Use the model's top 4" fills the open slots from the top 4. "Copy picks" puts the picks on the clipboard.
- [ ] AC-4: When a save fails, the tray keeps the picks it had and shows C2c's state (C2f on a phone). At Fri 2026-10-09 8:12 PM ET, UNLV @ Boise State is greyed with "Picks closed" and its side buttons are disabled. When the response marks every game locked, the page shows C2d's state (a component test).
- [ ] AC-5: Results & standing shows "You 12-8", "Model top 4 11-9", "3rd of 14" and the W1–W5 rows, with this week at "0 pts" for both at Thu 10:00 PM. Edit standing saves a new standing that is still there after a reload. The rules panel (desktop only) lists the contest's rules.
- [ ] AC-6: At 390, 768 and 1440 px there's no horizontal scroll and every tap target is at least 44 px, with the phone's tray as drawn in `Contest Mobile.dc.html`. Colours, type and spacing come from tokens only (`web/components/tokens-only.test.ts` passes), and the fixture Lighthouse run for `/contest` is within budget. `web/e2e/contest.spec.ts` runs journey 4 (pick OU +7 and BUF −3 → "2 of 4"; at Fri 8:12 PM UNLV @ Boise State shows "Picks closed" and the API refuses an entry) at phone and desktop widths.

## Out of scope

- The paste flow and its states (TASK-072).
- Best lines on Picks and This Week (M7.3).
- Contest settings and the rules form (M8.8), and confidence-points contests.
- Live game clocks on contest rows (TASK-074 stores them; showing them is follow-up work).

## Files likely touched

- `web/app/contest/page.tsx`: the confirmed-week layout
- `web/app/contest/ranked-slate.tsx`, `pick-tray.tsx`, `results-standing.tsx`, `rules-panel.tsx`: new
- `web/app/contest/actions.ts`: add, switch and remove entry; save standing
- `web/lib/contest.ts`, `web/lib/contest.test.ts`: tray logic (tap, re-tap, switch, fill from top 4), the ≠ count, copy text
- `web/app/contest/ranked-slate.test.tsx`, `pick-tray.test.tsx`: new component states
- `web/e2e/contest.spec.ts`: journey 4
- `scripts/perf/budget.json`: only if the slate's bytes need the budget raised (say why in the PR)

## Verification

- Automated: `pnpm --dir web exec vitest run lib/contest.test.ts app/contest` and `pnpm --dir web exec playwright test e2e/contest.spec.ts` pass.
- Manual (ui-verifier, at 390, 768 and 1440 against `03-contest-desktop.png` and `04-contest-mobile.png`): at Thu 10:00 PM, tap OU +7 → expected: the tray reads "Your picks … of 4" and shows the line it was locked in at; at Fri 8:12 PM → expected: UNLV @ Boise State reads "Picks closed".

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
