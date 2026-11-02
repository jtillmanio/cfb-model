---
id: TASK-050
title: Set up shadcn/ui and build the badge and chip components
status: Ready
depends_on: [TASK-049]
size: M
model: sonnet
autonomy: attended
ui: true
plan_status: none
planned_at_commit:
---

# TASK-050 — Set up shadcn/ui and build the badge and chip components

## Goal

The app has the design system's small components (edge pill, tier badge, result marker, filter chips) built on shadcn/ui and the design tokens, and the owner can review every drawn state of each on one page before any screen uses them.

## Context

- Task list: `docs/08-tasklist.md` › M5 › M5.2 (first half). M5.2 is split in two (`workflow.splitPolicy: split`, over 20 files as one task): this task sets up shadcn/ui and the specimen page and builds the badges and chips; TASK-051 adds the team chip with logos, the market cell with its sparkline and the data table densities. M5.2 is the design track's design-system PR and review gate; both halves are reviewed on the specimen page.
- Design: `design/README.md` § Components (Numbers & badges; Forms & controls: filter chips "selected = ink fill + check"), § Design tokens; `design/handoff/designs/Components.dc.html` (every state drawn: default, hover, focus, disabled/locked, loading), `Foundations.dc.html`, `Review Checks.dc.html` §02 (tier ramp). Tokens: `design/handoff/tokens/` via `web/app/tokens.css` and the `@theme` block in `web/app/globals.css` (hard rule 7).
- Architecture: `docs/02-architecture.md` › Components › 3 (`web/`: Tailwind + shadcn/ui).
- Decisions: D-061 (edge pill: filled `--edge` only when edge ≥ the pick threshold, plain muted text below), D-063 (tiers: one violet hue, three lightness steps, letter always printed, C with a 1px outline), D-055 and `design/README.md` § Number formats › Pick thresholds (thresholds are read from the active version's spec, never hard-coded: the pill takes the threshold as a prop), D-070 (no "Lock" verbs), D-085 (violet edge kept), D-101/D-125 (a new top-level page adds its Lighthouse route and budget in the same PR, measured on the fixture build).
- **Plan gate decides:** what the review surface is. Proposed: a signed-in specimen page (e.g. `/design-system`) rendering each component in every state against static sample props, with no API call; it is a top-level page, so `web/lib/perf.test.ts` requires its route and budget, and it should return 404 in production (e.g. on `VERCEL_ENV=production`) so the owner's app doesn't ship a design page. Alternative: Vitest-only state tests and no page, reviewed through TASK-056's screen instead.
- `.claude/rules/web.md`: tokens and shared components only; extend the system rather than adding a one-off style.
- *From TASK-051 (PR #125), open question for the plan:* TASK-051's approved plan assumes this task picks the specimen page `/design-system` and adds jsdom and Testing Library to `web/` (for its keyboard test); if this plan picks otherwise, TASK-051 re-plans.

## Acceptance criteria

- [ ] AC-1: Given an edge of 3.7 for OSU and a threshold prop of 2.5, the edge pill renders `+3.7 OSU` filled with the `--edge` token; given 0.6 for UTAH it renders `+0.6 UTAH` as plain muted text with no fill; given exactly 2.5 it is filled; given no line it renders `—` (Vitest render tests, one per state).
- [ ] AC-2: The tier badge renders the letters `A`, `B` and `C` with three distinct tier tokens, C with a 1px outline, and `—` for no pick; the result marker renders the glyph first (`✓`, `✗`, `P`) for covered, not covered and push, plus a pending state, each with a text label available to screen readers so colour is never the only signal.
- [ ] AC-3: Filter chips render selected (ink fill and a check icon) and unselected states, are real `<button>` elements with `aria-pressed` matching the state, and toggle with a click and with Enter or Space.
- [ ] AC-4: No component file under `web/components/` contains a hex, `rgb(`, `oklch(` literal or an arbitrary Tailwind size or colour value (`[#…]`, `[13px]`): a Vitest case scans them and fails on one (hard rule 7).
- [ ] AC-5: The review surface the plan gate chooses shows every state in AC-1 to AC-3 in dark and light themes at 390 and 1440 with no horizontal scroll at 390; if it is a page, its route and budget are in `scripts/perf/routes.mjs` and `budget.json` from a fixture run and `web/lib/perf.test.ts` passes.

## Out of scope

- Team chip, logos, market cell, sparkline and data table densities: TASK-051.
- Formatting numbers inside the components: they call `web/lib/format.ts` (TASK-049).
- Any screen using these components (shell TASK-054, This Week TASK-056).
- The ink-filled edge pill the design offered for colour blindness (D-085 kept violet).
- Components for later screens (probability bar, rank move beyond its text, lock countdown pill, toasts): each is built by the first screen that needs it.

## Files likely touched

- `web/components.json`, `web/package.json` (shadcn/ui and its dependencies: class-variance-authority, clsx, tailwind-merge, lucide-react), `pnpm-lock.yaml` (through pnpm only)
- `web/lib/utils.ts` — `cn()` helper
- `web/app/globals.css` — shadcn's theme variables mapped onto the tokens in `@theme`
- `web/components/edge-pill.tsx`, `tier-badge.tsx`, `result-marker.tsx`, `filter-chips.tsx` — new
- `web/components/badges.test.tsx`, `web/components/tokens-only.test.ts` — new
- `web/app/design-system/page.tsx` — new, if the plan gate picks a specimen page
- `web/e2e/design-system.spec.ts` — new, if a page
- `scripts/perf/routes.mjs`, `scripts/perf/budget.json`, `docs/02-architecture.md` › Performance checks budget table — if a page
- `docs/decisions.md` — the review-surface choice, if it's a page that production hides

## Verification

- Automated: `pnpm --dir web exec vitest run components` passes (AC-1 to AC-4); the e2e spec (if a page) loads it at 390 and 1440 and finds every state; `web/lib/perf.test.ts` passes.
- Manual: open the review surface in dark and light → expected: each state matches `Components.dc.html`; the owner signs off on the design system here (the M5.2 review gate).

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
