---
id: TASK-051
title: Build the team chip with logos, the market cell and the data table
status: Ready
depends_on: [TASK-050]
size: M
model: opus
autonomy: attended
ui: true
plan_status: none
planned_at_commit:
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
