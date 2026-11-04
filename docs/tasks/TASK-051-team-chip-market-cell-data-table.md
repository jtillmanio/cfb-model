---
id: TASK-051
title: Build the team chip with logos, the market cell and the data table
status: In progress
depends_on: [TASK-050]
size: M
model: opus
autonomy: attended
ui: true
plan_status: approved
planned_at_commit: faea7a4
---

# TASK-051 — Build the team chip with logos, the market cell and the data table

## Goal

The design system gains the pieces every slate and table row is made of: a team chip that shows the team's logo (or its colour dot when there's none), a market cell with the opening line and a sparkline before the current line, and a data table in comfortable and compact densities, all reviewable on the same surface as TASK-050's components.

## Context

- Task list: `docs/08-tasklist.md` › M5 › M5.2 (second half; first half TASK-050). Team logos joined the MVP here (D-146).
- Design: `design/README.md` § Components (TeamChip: 20px max logo slot, model rank small and muted before the name with no "#", FCS tag, neutral marker "N", locked drops colour; LineMovementCell: opening line + sparkline muted before the current line, flat line when unchanged; DataTable: sortable, sticky header `top: 56px`, row hover `--accent`, focus ring, collapses to cards < 768), § Table density (comfortable header 40 / row 48; compact header 32 / row 36); `design/handoff/designs/Components.dc.html`, `Market Extras.dc.html`, `Foundations.dc.html`.
- Decisions: D-075 (team colours are accents only: the 20px logo dot and the 3px bar, never a background or under text; real logos drop into the same slot), D-146 (CFBD's `teams.logo_url` in D-075's slot, the colour dot when it's NULL, and the screen endpoints return `logo_url`; served without a third-party request), D-101/D-125 (Lighthouse gates on forbidden requests: a logo fetched from CFBD's or ESPN's CDN by the browser would fail it), D-084 (This Week's desktop slate is compact; comfortable everywhere else), D-064 (ratings in ink).
- **Plan gate decides:** how logos are served without a third-party request from the browser, and how the in-job Lighthouse build (no external network assumed) behaves. Options include Next's image optimizer (`next/image` with `remotePatterns`, so the browser asks `/_next/image` and the server fetches the CDN), a same-origin route that proxies and caches, or copying logos into the repo or R2 at publish time. Record the choice in `docs/decisions.md`.
- Data: `teams.logo_url` exists (`python/db/src/db/models.py`; 03 › Reference). The fixture's teams (`python/db/seeds/fixture/teams.json`) carry no `logo_url`, so fixture screens show dots; a component test supplies a URL.
- Sparkline points are line snapshots (`line_snapshots`, 03 › Games & market); the market cell takes the opener, the snapshot values and the current line as props. *From TASK-016 (PR #59):* the fixture has each game's opener and current line only, plus Texas vs Oklahoma's and BYU's in-between snapshots, so most fixture rows draw a two-point line.

## Acceptance criteria

- [ ] AC-1: Given a team with a `logo_url`, the team chip renders an image at most 20px whose `src` is same-origin (never the CDN host); given `logo_url` NULL and colour `#BB0000`, it renders a 20px dot in that colour and no image; the colour never appears as a background behind text (Vitest render tests).
- [ ] AC-2: The team chip renders the rank small and muted before the name with no `#`, an `FCS` tag for an FCS team, and an `N` marker for a neutral site, each from a prop.
- [ ] AC-3: Given opener −28, snapshots [−28, −27.5] and current −27.5 for OSU at home, the market cell renders `−28`, a sparkline with one point per snapshot, then `OSU −27.5`, the opener and sparkline in the muted token; given an unchanged line (opener −9, current −9) the sparkline is flat; given no line it renders `No line` with no opener and no sparkline.
- [ ] AC-4: The data table renders comfortable (header 40px, rows 48px) by default and compact (header 32px, rows 36px) when asked; its header is sticky; a sortable header is a `<button>` with `aria-sort` reflecting the order, toggled by click and by keyboard.
- [ ] AC-5: On the review surface from TASK-050, every state in AC-1 to AC-4 shows at 390 and 1440 in dark and light, and a fixture Lighthouse run of every route requests nothing from a host other than the app's own (the forbidden-request gate passes).

## Out of scope

- Returning `logo_url` from `/api/py/teams` and showing logos on the Teams page (M8.5); each screen endpoint adds `logo_url` when it's built (TASK-055 for `/slate`).
- The data table's collapse-to-cards behaviour for a specific screen (each screen's own task: This Week's cards are TASK-056).
- Game Detail's line-history step chart (M7.7).
- Fetching or storing logo files in the CFBD ingest, unless the plan gate picks that option.

## Files likely touched

- `web/components/team-chip.tsx`, `market-cell.tsx`, `sparkline.tsx`, `data-table.tsx` — new
- `web/components/team-chip.test.tsx`, `market-cell.test.tsx`, `data-table.test.tsx` — new
- `web/next.config.ts` — image settings, if the plan gate picks `next/image`
- `web/app/design-system/page.tsx` — the new states (if TASK-050 made it a page)
- `web/e2e/design-system.spec.ts` — the new states
- `scripts/perf/budget.json`, `docs/02-architecture.md` › Performance checks — if the specimen page's bytes move past its budget (with the written reason the section asks for)
- `docs/decisions.md` — how logos are served

## Verification

- Automated: the three Vitest files pass (AC-1 to AC-4); the e2e spec finds each state at 390 and 1440; the fixture Lighthouse run reports no forbidden request.
- Manual: on the review surface → expected: the chip, market cell and table match `Components.dc.html` and `Market Extras.dc.html`; in the browser's network panel, a logo request goes to the app's own origin.

## Follow-ups

_Work noticed during this task and deliberately left out. Each bullet ends `→ <path> § <section>` (where it was placed) or `→ not tracked: <reason>`. See `.claude/skills/track-follow-ups/classify.md`; the PR's Follow-ups section is copied from here._

- Open question for TASK-050's plan: this task's provisional plan assumes TASK-050 picks the specimen page `/design-system` and adds jsdom + Testing Library to `web/`; if it picks otherwise, TASK-051 re-plans → docs/tasks/TASK-050-shadcn-and-badge-components.md § Context (approved at plan)
- The market cell's past-season variant (`Market Extras.dc.html`: open and close only, two dots, dashed join, "Past season" title) isn't in this task's ACs; open question for TASK-056's plan whether a past week on This Week needs it → docs/tasks/TASK-056-this-week-slate.md § Context (approved at plan)
- CFBD also serves dark-theme logos (`logos-dark/…`), but staging stores only `logos[0]`; some logos may read poorly on the dark theme → not tracked: judged on this task's specimen page in dark mode; storing a dark logo would be a schema change, raised then if needed

## Plan

_Written by /plan-batch or /implement-task Phase 1. Approved by the user (plan_status: approved) before any code is written._

**Provisional: depends on TASK-050** (and TASK-049's `web/lib/format.ts`). Assumes TASK-050 picks the proposed specimen page `web/app/design-system/page.tsx` and adds jsdom + Testing Library to `web/` for its keyboard test; if it picks Vitest-only review, AC-5's surface is TASK-056 and steps 7–8 move there (re-plan).

**Logo choice (for the plan gate):** Next's image optimizer. `next.config.ts` gets `images: { remotePatterns: [new URL("https://cdn.collegefootballdata.com/logos/**")], qualities: [75], minimumCacheTTL: 2678400 }` (31 days; logos change about once a season). The chip renders `next/image` at 20×20, so the browser asks `/_next/image?url=…` on the app's origin and the Next server fetches CFBD's 500px PNG once per width and caches it. Ruled out: a proxy route (the same fetch, written by hand) and copying logos to the repo or R2 (an ingest change and storage for ~270 files, for no gain at this size). In the in-job Lighthouse build the fixture's teams have no `logo_url`, so screens request no logo; the specimen page's one sample logo goes through `/_next/image` like production (GitHub runners have network; if the fetch fails, the image is decorative, `alt=""` in a fixed 20×20 box, so nothing shifts and no gate reads it).

**Steps**
1. Tests first (below); see each fail.
2. `web/next.config.ts`: the `images` block above.
3. `web/components/team-chip.tsx` (server component): props `{ abbreviation, school?, logoUrl, color, rank?, fcs?, neutral?, locked?, full? }`. Logo slot 20×20: `next/image` when `logoUrl`, else a `rounded-full` dot with `style={{ backgroundColor: color }}` and no children (the only place the colour is used, D-075); no colour → `bg-muted` dot. Rank in `text-caption text-muted-foreground` before the name, no `#`; `FCS` tag and `N` marker from props; `locked` greys the slot (`grayscale`, dot `bg-locked`).
4. `web/lib/format.ts` + test: add `formatLineNumber(spreadHome)` → the favourite's number with true minus and no abbreviation (`−28`, `−9`, `PK`), the opener as `Market Extras.dc.html` draws it.
5. `web/components/sparkline.tsx`: 22×10 SVG `polyline`, one point per value, y scaled min→max, all equal → flat at y = 5; stroke `stroke-muted-foreground`, 1px. `web/components/market-cell.tsx`: `{ opener, snapshots, current, home, away }` → muted opener + sparkline, then `formatSpread(current, …)`; `current` null → `No line` only.
6. `web/components/data-table.tsx` (`"use client"`): generic columns `{ key, header, align?, sortValue?, cell }`, `density: "comfortable" | "compact"` (`h-10`/`h-12` vs `h-8`/`h-9` from the spacing scale); `thead` `sticky top-14` with the 1px border; sortable header = `<th aria-sort>` wrapping a `<button>` (click/Enter/Space: none → ascending → descending), sorted column gets the 2px ink rule + arrow; rows `hover:bg-accent`, `focus-visible:ring`.
7. `web/app/design-system/page.tsx`: sections for every AC-1–4 state (CFBD logo URL for Ohio State, `#BB0000` dot, rank/FCS/N/locked, the three market-cell cases, both densities with sortable columns), static props, no API call.
8. `scripts/perf/lib/perf.mjs`: `summariseLhr` also lists as forbidden any request whose origin differs from `lhr.requestedUrl`'s (Vercel extras still filtered); today the gate only catches `/api/py`, so AC-5's "nothing from another host" isn't checked without this.
9. Run the fixture Lighthouse locally on `/design-system`; if bytes pass its budget, raise it in `budget.json` and 02's table with the written reason.
10. Docs: new decision (ID from `next-id.ps1`) for the logo choice and the widened gate; `docs/02-architecture.md` › Performance checks › forbidden requests says "or any host other than the app's own".

**Files** (≤ 17): `web/next.config.ts`; `web/components/team-chip.tsx`, `sparkline.tsx`, `market-cell.tsx`, `data-table.tsx` + `team-chip.test.tsx`, `market-cell.test.tsx`, `data-table.test.tsx` (new); `web/lib/format.ts`, `format.test.ts` (not in "Files likely touched": the opener's number); `web/app/design-system/page.tsx`; `web/e2e/design-system.spec.ts`; `scripts/perf/lib/perf.mjs`, `web/lib/perf.test.ts` (not listed: the gate change); `scripts/perf/budget.json` (if needed); `docs/02-architecture.md`; `docs/decisions.md`.

**Test strategy**
- AC-1: `team-chip.test.tsx` › "renders a same-origin logo at most 20px" (`src` starts `/_next/image`, never contains `cdn.collegefootballdata.com` as host; width/height ≤ 20), "renders a 20px colour dot and no image without a logo", "puts the team colour only on an element with no text".
- AC-2: `team-chip.test.tsx` › "shows the rank muted before the name with no #", "shows FCS and N from props".
- AC-3: `market-cell.test.tsx` › "opener −28, two-point sparkline, OSU −27.5, opener and sparkline muted", "flat sparkline when unchanged", "No line without opener or sparkline"; `format.test.ts` › `formatLineNumber` cases.
- AC-4: `data-table.test.tsx` › "comfortable 40/48 by default", "compact 32/36", "sticky header", "sort button toggles aria-sort on click", "… on Enter and Space".
- AC-5: `e2e/design-system.spec.ts` › each new state visible at 390 and 1440, dark and light, and `page.on("request")` sees no host but the app's; `web/lib/perf.test.ts` › "flags a request to another origin as forbidden"; the PR's fixture Lighthouse run passes.

**Risks / open questions**
- AC-4 puts `aria-sort` on the button; ARIA allows it only on the column header, so the plan puts it on the `<th>` around the button and the test reads it there. Confirm at approval.
- `next/image` in jsdom: dev-mode `remotePatterns` checks may need the config passed to the test; fall back to asserting the rendered `src` only.
- Dark mode: CFBD also serves `logos-dark/…`; only `logos[0]` (light) is stored, so some dark logos may read poorly on the dark theme (follow-up).
- Vercel image optimization quota: ~270 teams × 2 widths, cached 31 days, well inside the free tier.

**Size check:** up to 17 files, one layer (web) plus the perf script; no schema. M, attended.

**Plan revisions after approval**
- 2026-11-04, Phase 0: plan stale only through TASK-050's expected changes (`/design-system`, jsdom + Testing Library, D-152); the owner confirmed carrying on, with `aria-sort` on the `<th>`.
- 2026-11-04, step 6 (owner approved): `DataTable` takes plain-data columns `{ key, header, align?, sortable? }` and rows `{ key, cells, sortValues? }` instead of `cell`/`sortValue` functions, which can't cross from a server component to the client table. Same files.
- Within the steps: `formatLineNumber` takes an optional `side`, so an opener that had the current favourite as the underdog reads `+1`; the sparkline follows the board's formula (most favoured at the top, stroke 1.25); the locked chip's dot is `bg-muted` as `Components.dc.html` draws it, not `bg-locked`.
- Step 9: run locally, `/design-system` measured 10,712 doc bytes against a 9,000 budget, but local doc bytes run ~15% above CI's (`/login` 9,071 locally vs 7,882 in CI), so the budget is set from the PR's fixture run (`report.mjs budget`, README › Set a route's budget).

## Review log

_Filled by /implement-task. One line per round._

## Blocked

_Only if status is Blocked: what failed, what was tried, best hypothesis, decision needed._

## Metrics

- Verify rounds:
- Review rounds:
- First-pass AC FAILs:
- Plan revisions after approval:
