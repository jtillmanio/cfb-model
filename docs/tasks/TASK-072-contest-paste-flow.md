---
id: TASK-072
title: Build the Contest paste flow
status: Draft
depends_on: [TASK-070, TASK-071, TASK-054]
size: M
model: opus
autonomy: attended
ui: true
plan_status: none
planned_at_commit:
---

# TASK-072 — Build the Contest paste flow

## Goal

On the Contest page you paste a Splash page, see the raw text beside the parsed rows, fix unmatched names with an inline team picker, and confirm the week's slate. A paste that can't be read or matches nothing gets its own state, and a re-paste shows which lines moved.

## Context

- Task list: `docs/08-tasklist.md` › M6 › M6.6. Depends on TASK-071 as well as the task list's M6.4 and M5.3: the page's one API call is TASK-071's contest page route, which tells the page whether the week has a slate, and carries the `shell` block.
- Screen: S-02 (`docs/05-ui-design-brief.md` › Screen inventory; › Screens › 7. Contest).
- Design: `design/handoff/designs/Contest Desktop.dc.html` (`pasteError` none / unparsed / nomatch, `repaste`) and `Contest Mobile.dc.html`; boards `Contest.dc.html` and `Pass C1 - Slate Contest Game.dc.html`: C2a "paste can't be parsed", C2b "paste matches no team", C2e "re-paste moved lines" (the RepasteDiff component); skeleton in `Loading States.dc.html`; light mode in `Pass D - Light Mode.dc.html` (D02).
- Reference screenshots: `design/handoff/screenshots/03-contest-desktop.png`, `04-contest-mobile.png`.
- Product: `docs/01-product.md` › Observable outcomes › F-03 AC-1.
- Architecture: `docs/02-architecture.md` › End-to-end journeys › 3, › Test-only sign-in and clock (Thu 2026-10-08 10:00 PM ET).
- Decisions: D-058 (IBM Plex Mono for raw paste text), D-069 (Contest in the sidebar and tab bar: `web/components/shell/sidebar.tsx` and `mobile-tabs.tsx` already link it), D-070, D-096 (designed error states, no fallback data), D-155 (types from `web/lib/api-types.ts`), D-157 (each page renders `<AppShell shell={data.shell}>`).
- **Writes:** the first pages that write. The browser never calls the API (hard rule 5, `.claude/rules/web.md`). Paste, map and confirm go through Server Actions that call TASK-070's routes with the signed JWT, so `web/lib/api.ts` gains a signed POST beside `signedGet`.
- **The empty hero needs an empty week.** The fixture already holds Week 6's contest lines (TASK-067), and an alias saved in one e2e run would make the next run's paste fully matched. The plan says which contest week e2e pastes into, and how each run starts from the seeded state (e2e runs after `pnpm db:seed`).
- **Lighthouse:** `/contest` is a new top-level screen, so its route and budget go in `scripts/perf/routes.mjs` and `budget.json` in this PR (`web/lib/perf.test.ts` fails otherwise).

## Acceptance criteria

- [ ] AC-1: Given a contest week with no confirmed slate, `/contest` shows the "Paste from Splash" hero. Pasting the fixture Week 6 text shows the raw text (IBM Plex Mono) beside the parsed rows, with "9 rows match · 1 unmatched". The unmatched row ("Hou Texans" @ "Jax") is highlighted, and Confirm is disabled.
- [ ] AC-2: Mapping "Hou Texans" to Houston Texans and "Jax" to Jacksonville Jaguars with the inline team picker enables Confirm. Confirm saves the slate, and the page then shows the confirmed week (TASK-073 draws its ranked slate). After a reload the slate is still there, and pasting the same text again matches all 10 rows.
- [ ] AC-3: Unparseable text shows C2a's state and a paste that matches no team shows C2b's, each with a way back to edit the paste. Neither writes anything (the API's row counts are unchanged).
- [ ] AC-4: Pasting again with a moved line shows the RepasteDiff (C2e) listing each moved row with its old and new line before Confirm.
- [ ] AC-5: `/contest` has a `loading.tsx` skeleton at the loaded size, with the pulse off under reduced motion, and shows the designed error state when the API fails (D-096). At 390, 768 and 1440 px there's no horizontal scroll and every tap target is at least 44 px. Colours, type and spacing come from tokens only (`web/components/tokens-only.test.ts` passes).
- [ ] AC-6: `/contest` is in `scripts/perf/routes.mjs` with a budget, and the fixture Lighthouse run is within it. `web/e2e/contest.spec.ts` runs journey 3 (paste → "9 rows match · 1 unmatched" → map → Confirm) at phone and desktop widths.

## Out of scope

- The ranked slate, the pick tray, results and standing, and the rules panel (TASK-073).
- Manual "add game" entry.
- Contest settings (M8.8).
- The mobile versions of the bad-paste, all-locked and re-paste states (not drawn: 05 › Screen inventory lists them as missing).

## Files likely touched

- `web/app/contest/page.tsx`, `loading.tsx`, `error.tsx`: new
- `web/app/contest/paste-flow.tsx`, `team-picker.tsx`, `repaste-diff.tsx`: new client components
- `web/app/contest/actions.ts`: new Server Actions for preview, map and confirm
- `web/lib/api.ts`: the signed POST and the contest calls
- `web/lib/contest.ts`, `web/lib/contest.test.ts`: new pure helpers (match counts, Confirm enabled) and their tests
- `web/app/contest/paste-flow.test.tsx`: new component states
- `web/e2e/contest.spec.ts`: new, journey 3
- `scripts/perf/routes.mjs`, `scripts/perf/budget.json`: the route and its budget

## Verification

- Automated: `pnpm --dir web exec vitest run lib/contest.test.ts app/contest`, `pnpm --dir web exec playwright test e2e/contest.spec.ts`, and `web/lib/perf.test.ts` pass.
- Manual (ui-verifier, at 390, 768 and 1440): paste the fixture text → expected: "9 rows match · 1 unmatched" and Confirm disabled; map both names → Confirm enabled; paste "hello" → C2a's state.

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
