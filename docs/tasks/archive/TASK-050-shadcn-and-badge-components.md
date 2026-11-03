---
id: TASK-050
title: Set up shadcn/ui and build the badge and chip components
status: Done
depends_on: [TASK-049]
size: M
model: sonnet
autonomy: attended
ui: true
plan_status: approved
planned_at_commit: ef00231
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

- [x] AC-1: Given an edge of 3.7 for OSU and a threshold prop of 2.5, the edge pill renders `+3.7 OSU` filled with the `--edge` token; given 0.6 for UTAH it renders `+0.6 UTAH` as plain muted text with no fill; given exactly 2.5 it is filled; given no line it renders `—` (Vitest render tests, one per state).
- [x] AC-2: The tier badge renders the letters `A`, `B` and `C` with three distinct tier tokens, C with a 1px outline, and `—` for no pick; the result marker renders the glyph first (`✓`, `✗`, `P`) for covered, not covered and push, plus a pending state, each with a text label available to screen readers so colour is never the only signal.
- [x] AC-3: Filter chips render selected (ink fill and a check icon) and unselected states, are real `<button>` elements with `aria-pressed` matching the state, and toggle with a click and with Enter or Space.
- [x] AC-4: No component file under `web/components/` contains a hex, `rgb(`, `oklch(` literal or an arbitrary Tailwind size or colour value (`[#…]`, `[13px]`): a Vitest case scans them and fails on one (hard rule 7).
- [x] AC-5: The review surface the plan gate chooses shows every state in AC-1 to AC-3 in dark and light themes at 390 and 1440 with no horizontal scroll at 390; if it is a page, its route and budget are in `scripts/perf/routes.mjs` and `budget.json` from a fixture run and `web/lib/perf.test.ts` passes.

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

- `Components.dc.html` also draws the result marker's compact "last 5 ATS" squares and straight-up W/L/P, and the edge pill's large (The Number) variant; none is in this task's ACs → not tracked: built by the first screen that needs it (this task's Out of scope rule)

## Plan

_Written by /plan-batch or /implement-task Phase 1. Approved by the user (plan_status: approved) before any code is written._

**Review surface (for the plan gate):** a signed-in specimen page `/design-system` (static props, no API call), as TASK-051's approved plan assumes. It shows every state twice, in a `.dark` panel and a `.light` panel (`tokens.css` scopes both themes by class, so no theme switch is needed), side by side at ≥ 1280 and stacked below. `page.tsx` calls `notFound()` when `process.env.VERCEL_ENV === "production"`; previews and the fixture build show it. Ruled out: Vitest-only review (the owner's M5.2 sign-off would wait for TASK-056).

**Steps**
1. Tests first (below); see each fail.
2. Deps through pnpm only: `pnpm --dir web add class-variance-authority clsx tailwind-merge lucide-react radix-ui` and `pnpm --dir web add -D jsdom @testing-library/react @testing-library/user-event`.
3. `web/components.json` hand-written (style `new-york`, `rsc: true`, `tailwind.css: app/globals.css`, `cssVariables: true`, `iconLibrary: lucide`, aliases `@/components`, `@/components/ui`, `@/lib/utils`). No `shadcn init`: it rewrites `globals.css`, whose `@theme` already maps the tokens under shadcn's names. Then `pnpm --dir web dlx shadcn@latest add badge toggle`; revert anything it writes outside `web/components/ui/`, and replace its arbitrary values (`ring-[3px]` and the like) with theme utilities so AC-4's scan passes.
4. `web/lib/utils.ts`: `cn()` = `clsx` + `extendTailwindMerge` taught the type scale (`text-caption|label|body|panel|section|title` as font sizes). Without it `cn("text-caption", "text-muted-foreground")` drops the size.
5. `web/components/edge-pill.tsx` (server): `{ edgePts: number | null, home, away, threshold, locked?, loading? }`; text from `formatEdge`; filled (`bg-edge text-edge-foreground`, h-6 px-2 rounded-full text-label font-semibold) when `Math.abs(edgePts) >= threshold`, else plain `text-muted-foreground`; null → `—`; locked → `text-locked` with lucide `Lock`; loading → a `bg-secondary` bar at pill size. Built on `ui/badge` variants via `cva`.
6. `web/components/tier-badge.tsx`: `{ tier: "A" | "B" | "C" | null, label?, loading? }`; 20px rounded-sm square, `bg-tier-a`/`b`/`c` with their foregrounds, C adds `border border-tier-c-foreground` (1px); null → `—`; `label` adds "Tier A".
7. `web/components/result-marker.tsx`: `{ result: "covered" | "not_covered" | "push" | "pending" }`; glyph `✓`/`✗`/`P` (`aria-hidden`) in `text-pos`/`text-neg`/`text-push`, then an `sr-only` label ("Covered", "Not covered", "Push", "Pending"); pending = 20px dashed `border-input` square.
8. `web/components/filter-chips.tsx` (`"use client"`): `{ options: { value, label }[], selected?, defaultSelected?, onChange? }`; each chip is `ui/toggle` (a `<button aria-pressed>`); selected = `bg-primary text-primary-foreground` + lucide `Check`; controlled or uncontrolled.
9. `web/app/design-system/page.tsx`: sections Edge pill / Tier badge / Result marker / Filter chips, every AC-1–3 state plus the board's locked and loading ones, `threshold={2.5}` passed as sample data (the real value comes from the spec, D-055); no horizontal scroll at 390.
10. Perf: `{ id: "design-system", path: "/design-system", signedIn: true }` in `scripts/perf/routes.mjs`. Push, let the PR's fixture Lighthouse run measure it (unbudgeted routes are listed, not gated), then `node scripts/perf/report.mjs budget <its metrics.json>` and keep only the new route's entry in `budget.json` and the 02 table (`login`/`teams` stay as they are), with the run cited beside the table.
11. Docs: one decision (ID from `next-id.ps1`): the specimen page, hidden in production, and shadcn added by hand-written `components.json` + `add` (no `init`) so the tokens stay the only theme.

**Files** (20): `web/package.json`, `pnpm-lock.yaml`, `web/components.json`, `web/lib/utils.ts`, `web/components/ui/badge.tsx`, `ui/toggle.tsx`, `edge-pill.tsx`, `tier-badge.tsx`, `result-marker.tsx`, `filter-chips.tsx`, `badges.test.tsx`, `tokens-only.test.ts` (new), `web/app/design-system/page.tsx`, `page.test.tsx` (new), `web/e2e/design-system.spec.ts`, `web/vitest.config.mts` (only if `.tsx` tests need a JSX setting), `scripts/perf/routes.mjs`, `scripts/perf/budget.json`, `docs/02-architecture.md` (perf table), `docs/decisions.md`.

**Test strategy** (`.tsx` tests start `// @vitest-environment jsdom` and `afterEach(cleanup)`)
- AC-1: `badges.test.tsx` › "edge 3.7 OSU at threshold 2.5 is filled `+3.7 OSU` (bg-edge)", "0.6 UTAH is muted text, no fill", "exactly 2.5 is filled", "no line renders —"; plus "cn keeps text-caption beside text-muted-foreground".
- AC-2: `badges.test.tsx` › "tier A/B/C use three tier tokens, C outlined, null → —"; "result marker puts the glyph first with a screen-reader label, pending dashed".
- AC-3: `badges.test.tsx` › "chips are buttons with aria-pressed matching selected (ink fill + check)", "click toggles", "Enter and Space toggle" (user-event).
- AC-4: `tokens-only.test.ts` › "flags each banned form in a sample" (hex, `rgb(`, `oklch(`, `[#…]`, `[13px]`; comments stripped first so `#125` in a comment passes) and "no file under web/components/ has one".
- AC-5: `e2e/design-system.spec.ts` (phone 390, desktop 1440) › every AC-1–3 state visible in the dark and the light panel; `scrollWidth <= clientWidth` at 390. `page.test.tsx` › "404s when VERCEL_ENV is production". `web/lib/perf.test.ts` passes with the new route and budget.

**Risks / open questions**
- Pill fill compares raw `|edge|` with the threshold, as the pick rule does, so 2.46 prints `+2.5` but stays muted. Confirm, or compare the rounded value.
- `shadcn add` may still touch `globals.css` or pull another dep; the step reverts it. The budget needs one pushed fixture run before it can be written (step 10).
- Lighthouse a11y on the specimen page must hold 100 (muted text and tier-c contrast in both themes); fix in the component, never by lowering the budget.
- Vitest 5 may need a JSX runtime setting for `.tsx`; that is the only reason `vitest.config.mts` changes.

**Size check:** 20 files (the project limit), web plus perf config, no schema. M, attended.

## Review log

_Filled by /implement-task. One line per round._

Verify R1 PASS | Audit R1 PASS | Spec R1 CHANGES (AC-5: the `design-system` budget waits on the PR's fixture Lighthouse run, plan step 10) | Budget set from the PR's fixture run (run 41591176278) | Spec R2 APPROVE | UI R1 PASS

## Blocked

_Only if status is Blocked: what failed, what was tried, best hypothesis, decision needed._

## Metrics

- Verify rounds: 1
- Review rounds: 2
- First-pass AC FAILs: 0 (AC-5 open only for the budget)
- Plan revisions after approval: 0 (`@testing-library/dom` added as the peer of `@testing-library/react`; not a plan change)
