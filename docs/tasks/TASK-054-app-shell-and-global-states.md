---
id: TASK-054
title: Build the app shell and global states
status: In progress
depends_on: [TASK-050, TASK-053]
size: M
model: opus
autonomy: attended
ui: true
plan_status: approved
planned_at_commit: 1fbc8a5
---

# TASK-054 — Build the app shell and global states

## Goal

Every signed-in screen sits in the designed app shell: a desktop sidebar with the model's track-record card, a top bar, a tablet top-bar nav at 768 and a mobile tab bar with More, plus the global states (API unreachable with Retry, the waking-database note and the stale-lines banner), all fed by the page's one API call.

## Context

- Task list: `docs/08-tasklist.md` › M5 › M5.3 (UI half; the API half is TASK-053, which decides how shell data rides in each response).
- Screen: S-16 App shell and global states (`docs/05-ui-design-brief.md` › Screen inventory). Design: `design/handoff/designs/App States Desktop.dc.html` / `App States Mobile.dc.html` (`frame="apierror"`, mobile `frame="more"`, `frame="offseason"` for the card's "2026 final"), `This Week Tablet.dc.html`, `Pass B - New Screens.dc.html` B8a (More, mobile), `Pass C3 - Alerts Settings Shell.dc.html` C16a (stale banner, desktop), C16b (mobile), C16c (tablet 768), `Loading States.dc.html` (wake-up note). Shots: `01-this-week-desktop.png`, `27-more-mobile.png`, `28-this-week-tablet.png`, `20-offseason-empty-desktop.png`. Spec: `design/README.md` § Navigation (224px sidebar, nav items and lucide icons, track-record card, top bar, mobile tabs This Week · Picks · Contest · Rankings · More), § Feedback (wake note after 1.5 s; error says what failed and when it retries), § Breakpoints.
- Decisions: D-096 (no saved copies: "API unreachable" drops the design's saved-copy sentence; the stale banner means only "lines more than 24 h old", worded e.g. "Lines last updated Thu 9:02 PM ET · Refresh"), D-097 (copy: "If the server was idle, the database can take a few seconds to start"; 10 s server-side timeout in `web/lib/api.ts`), D-010 and hard rule 5 (one server-side API call per page; the browser never calls the API), D-088 (⌘K is M8.6), D-101/D-125 (Lighthouse route and budget for any new top-level page).
- Reuse `raceWakeNote` from `web/lib/login.ts` (from PR #15) for the 1.5 s wake note.
- **Plan gate decides:** how a page hands its response's `shell` block to the shell without a second call. A layout can't see the page's data, so options are a shell component each page renders around its content, or a per-request `cache()`d fetch shared by layout and page (one HTTP call). Also whether More is a route (then it needs a Lighthouse route and budget) or a sheet.
- Nav items for screens not built yet (Picks, Contest, Rankings, Performance, Lab) link to their paths and 404 until their milestones; the sport switcher shows college football only (NFL marked "Later"); the alerts bell is hidden until F-14 (Phase 5); the ⌘K box is drawn but inert until M8.6.
- The Teams page (`web/app/teams/`) is the only signed-in screen today; it moves into the shell here. `/` still redirects to `/teams` until TASK-056.

## Acceptance criteria

- [ ] AC-1: Signed in on the seeded test DB at 1440, `/teams` shows the 224px sidebar with the seven nav items in the design's order and icons, Teams marked active, and the track-record card showing the response's shell record (formatted by `web/lib/format.ts`, labelled "2026 live") linking to `/performance`; the top bar shows "2026 · Week 6" and "Updated Sat 9:00 AM ET" (the fixture's newest line snapshot; TASK-053's AC-1, approved 2026-11-04).
- [ ] AC-2: At 768 the sidebar is replaced by the top-bar navigation drawn in C16c; at 390 the bottom tab bar shows This Week, Picks, Contest, Rankings and More, every tab ≥ 44px tall, and More opens Teams, Performance, Lab and Settings (B8a); no width scrolls horizontally.
- [ ] AC-3: With the API stopped, `/teams` shows the "API unreachable" state with a Retry button and no saved-copy sentence; after the API restarts, Retry loads the data (e2e journey 8, 02 › Testing strategy).
- [ ] AC-4: With the API answering after a delay longer than 1.5 s (e2e's existing cold-API server, `web/e2e/cold-api.mjs`), the "Waking up the database…" note appears after 1.5 s and the page then loads without an error.
- [ ] AC-5: When the shell block's stale flag is true, a neutral banner reads "Lines last updated <time> ET · Refresh" at the top of the content (C16a desktop, C16b mobile); when false, no banner is drawn (component test with both flags; e2e on whichever the fixture state gives).
- [ ] AC-6: The shell's track-record card, nav and banners use tokens only (hard rule 7, TASK-050's scan passes), `/teams` still makes exactly one API call per request (a test counts the server-side fetches), and every new top-level page has its Lighthouse route and fixture budget (`web/lib/perf.test.ts` passes).

## Out of scope

- The screens behind the nav items (This Week TASK-056, Picks M7, Contest M6, Rankings M8, Performance M7, Lab M9/M14).
- The ⌘K palette (M8.6), the alerts bell and panel (F-14, Phase 5), Settings (M8.8), the week selector's season/week list (it shows the label only until a screen needs to step weeks; This Week's stepping is TASK-056's plan).
- Any API change: the shell block is TASK-053's.
- A saved copy of page data (D-096).

## Files likely touched

- `web/components/shell/app-shell.tsx`, `sidebar.tsx`, `top-bar.tsx`, `mobile-tabs.tsx`, `tablet-nav.tsx`, `track-record-card.tsx`, `stale-banner.tsx`, `api-unreachable.tsx`, `wake-note.tsx` — new
- `web/lib/shell.ts`, `web/lib/shell.test.ts` — new: shell props from the response, active nav item
- `web/lib/api.ts`, `web/lib/login.ts` — the shell block; `raceWakeNote` shared
- `web/app/teams/page.tsx`, `loading.tsx`, `error.tsx` (new) — inside the shell
- `web/app/more/page.tsx` — if More is a route
- `web/e2e/shell.spec.ts` — new: AC-1 to AC-5 at 390, 768 and 1440
- `scripts/perf/routes.mjs`, `scripts/perf/budget.json`, `docs/02-architecture.md` › Performance checks — new routes and the `teams` budget re-measured with the shell (with the written reason)

## Verification

- Automated: `web/e2e/shell.spec.ts` (phone and desktop projects, plus a 768 case), `web/lib/shell.test.ts`, `web/lib/perf.test.ts`, the fixture Lighthouse run.
- Manual: `pnpm dev`, signed in, resize through 390, 768 and 1440 → expected: the three layouts in `01`, `28` and `27`; stop the API → expected: "API unreachable" with Retry.

## Follow-ups

_Work noticed during this task and deliberately left out. Each bullet ends `→ <path> § <section>` (where it was placed) or `→ not tracked: <reason>`. See `.claude/skills/track-follow-ups/classify.md`; the PR's Follow-ups section is copied from here._

- Production builds hide server error messages, so `error.tsx` can't tell a down API from any other failure of the page's data (an expired token's 401, a 500). Every failure reads "Couldn't reach the server" → not tracked: the design draws one error state; a second one needs a design pass first

## Plan

_Written by /plan-batch or /implement-task Phase 1. Approved by the user (plan_status: approved) before any code is written._

Provisional: depends on TASK-053. It uses `ShellOut`'s field names, and AC-1's "Updated Sat 9:00 AM ET" is TASK-053's newest-pull time (its AC change, approved 2026-11-04; `stale` is false on the fixture).

**Decisions:**
- **Each page renders `<AppShell shell={data.shell}>` around its content; the layout doesn't.** A layout can't see which endpoint the page calls. It also persists across client navigation, so shell data rendered there would go stale. `loading.tsx` and `error.tsx` draw the same shell with no data.
- **More is a sheet using the HTML `popover` attribute**, not a route. It needs no client JS and no Lighthouse route.
- **The wake note is server-side via `raceWakeNote`**, as `/login/continue` does it.

Steps:
1. `web/lib/shell.ts`: `type Shell = components["schemas"]["ShellOut"]`; `NAV` (the 7 items, their hrefs and lucide icons, per design/README § Navigation; This Week → `/`); `MOBILE_TABS`, `MORE_ITEMS` (Teams, Performance, Lab, Settings); `SHELL_COPY`.
   `shellView(shell | null)` returns:
   - the week label ("2026 · Week 6", or just the season when there's no week);
   - "Updated <`formatKickoff`> ET";
   - the card: "Model · 2026 live" or "final", record, `formatWinRate(win_pct / 100)`, units, "CLV +0.9";
   - the Picks badge, and dashes when there's no data.
   Export `signed` from `web/lib/format.ts` for the card's CLV.
2. Components in `web/components/shell/`. None imports server-only code, so the client `error.tsx` can render them.
   - `app-shell.tsx`: `AppShell({ active, shell, state: ready|loading|error, path, children })`. Sidebar at xl (1280+), top bar plus tablet nav at md (768+), tabs below that. Also holds `StaleBanner` ("Lines last updated <time> ET · Refresh", which reloads `path`) and `WakeNote` (D-097 copy).
   - `sidebar.tsx`: logo, sport switcher (college football; NFL "Later"; inert), nav (`aria-current`, Picks badge), track-record card linking to `/performance`.
   - `top-bar.tsx`: week label, an inert "Search teams ⌘K", "Updated …", or "Can't reach the server" in the error state. Also the C16c nav row at md.
   - `mobile-tabs.tsx`: 5 tabs, each ≥ 44px; More opens a `popover` sheet (B8a).
   - `api-unreachable.tsx` (`"use client"`):
     - copy: "Couldn't reach the server · The API didn't answer after N tries." (the saved-copy sentence dropped, D-096);
     - Retry: `startTransition(() => retry())`, error.js's `retry` prop in Next 16.4, which re-fetches and re-renders the segment (revised after approval: it replaces `router.refresh()` + `reset()` and does both);
     - auto-retry: "Trying again in 15s", then 30 s, per the board;
     - Details: the request and the error digest.
3. `web/app/teams/page.tsx`: one `getTeams()` call, then `raceWakeNote(call)`. Ready → AppShell + content. Waking → a `Suspense` with the loading shell + `WakeNote` as fallback, whose child awaits the same call. `loading.tsx`: AppShell (`loading`) around the existing skeleton. `error.tsx` (new): AppShell (`error`) + `ApiUnreachable request="GET /api/py/teams"`. Edit `team-table.tsx` only if its header has to move into the content slot.
4. e2e: `web/e2e/switch-api.mjs` (new) proxies the e2e API. `POST /__e2e/down` / `up` switch it off and on (refused when down); `GET /__e2e/count` returns the number of proxied `/api/py/*` requests. `playwright.config.ts` starts it plus a third `next start` (port 3102) pointed at it, and `test-env.ts` names both URLs.
5. Perf: re-measure `teams` from the PR's fixture Lighthouse run (`node scripts/perf/report.mjs budget …`). Write `scripts/perf/budget.json` and the 02 › Performance checks table, with a dated note giving the reason. No new route.
6. `docs/decisions.md`: one D-### row (ID from `next-id.ps1`) for the three decisions above.

Files: `web/components/shell/{app-shell,sidebar,top-bar,mobile-tabs,api-unreachable}.tsx`, `app-shell.test.tsx` (new); `web/lib/shell.ts`, `shell.test.ts` (new); `web/lib/format.ts`; `web/app/teams/page.tsx`, `loading.tsx`, `error.tsx` (new), `team-table.tsx` (if needed); `web/e2e/shell.spec.ts`, `switch-api.mjs` (new), `test-env.ts`; `web/playwright.config.ts`; `scripts/perf/budget.json`; `docs/02-architecture.md`; `docs/decisions.md` (19–20 files).

Test strategy (`web/e2e/shell.spec.ts` unless noted):
- AC-1 (desktop): sidebar 224px wide; 7 nav names in order; Teams `aria-current="page"`; card text and `href="/performance"`; "2026 · Week 6"; the "Updated" text. `shell.test.ts` covers `shellView` on a fixture-shaped `Shell` and on null.
- AC-2: `setViewportSize(768)` → no sidebar, tablet nav visible. Phone project → 5 tabs, each with box height ≥ 44; More opens the 4 links. `scrollWidth <= clientWidth` at 390, 768 and 1440.
- AC-3 (desktop, serial, switch server): down → "Couldn't reach the server", a Retry button and no "saved copy" text; up → Retry → the Ohio State row.
- AC-4: cold preview `/teams` → "Waking up the database…" shows, then the table, with no error.
- AC-5: `app-shell.test.tsx` renders with `stale` true (banner text) and false (no banner). e2e: the fixture state (false) has no banner.
- AC-6: `tokens-only.test.ts` scans `web/components/shell/`. Switch server: the count rises by exactly 1 per `/teams` load. `perf.test.ts` passes (no new top-level page).

Risks / open questions:
- `reset()` alone re-renders without refetching; Next 16.4's `retry()` re-fetches, so Retry uses it.
- The switch server makes e2e start one more process; its tests run serially in the desktop project only.
- The page holds the stream up to 1.5 s for the race; `loading.tsx` shows the shell during that time.
- An off-season label beyond "2026" is TASK-057's (see TASK-053's follow-up).

Size check: 19–20 files, UI only (no schema) → passes at the 20-file limit. `autonomy: attended`.

## Review log

_Filled by /implement-task. One line per round._

## Blocked

_Only if status is Blocked: what failed, what was tried, best hypothesis, decision needed._

## Metrics

- Verify rounds:
- Review rounds:
- First-pass AC FAILs:
- Plan revisions after approval:
