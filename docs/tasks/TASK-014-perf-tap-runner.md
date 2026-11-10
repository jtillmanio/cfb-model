---
id: TASK-014
title: Time screen-to-screen taps in the lighthouse workflow
status: In progress
depends_on: [TASK-008, TASK-056]
size: M
model: opus
autonomy: attended
ui: false
plan_status: approved
planned_at_commit: f6cac60
---

# TASK-014 — Time screen-to-screen taps in the lighthouse workflow

## Goal

The Lighthouse PR comment also reports how long a tap from one screen to the next takes to paint (client navigation), not only cold page loads.

## Context

- *From TASK-008 (PR #29):* the owner's `ledger` project runs a tap → next-paint runner beside Lighthouse (`ledger/scripts/perf/measure.mjs`: puppeteer-core on the same throttling profile, click a link, wait for the `<h1>` to change and two frames, time it, and record any `/api/*` request the tap makes). TASK-008 measures cold loads only: neither `docs/02-architecture.md` › Performance checks nor D-101 plans a tap runner, and with one signed-in screen (`/teams`) there is no screen-to-screen tap to time.
- Plan it when a second signed-in screen ships (This Week, M5.6, is the first pair with `/teams`). It would add `puppeteer-core` to `scripts/perf/package.json`, a `tap` field to `scripts/perf/routes.mjs`, and a "Reported, never gated" row to the comment; 02 › Performance checks and D-101 would need the owner's approval to change.
- *Blocked on M5.6 (This Week),* now TASK-056, which is in `depends_on`.
- *From TASK-027 (PR #77):* Lighthouse now runs twice per PR (D-125): a gated `fixture` job that builds and serves the app on the seeded test DB inside the job, and a reported-only per-route `measure` job on the preview. Time taps on the fixture build (the `fixture` job in `.github/workflows/lighthouse.yml`), where the data holds still, and show them in the fixture comment; the preview run can add its own reported-only timings if wanted. The fixture job measures every route in one job, so a tap runner there needs no matrix.

## Acceptance criteria

_Approved by the owner 2026-11-10 (in the /next-task session): taps run on the mobile profile, This Week → Teams goes through the More sheet; a forbidden request during a tap fails the job; the preview run times no taps. At the plan gate the owner added a second number per tap, `loadedMs` (the page's data replaces the skeleton, which already draws the real `<h1>`), to AC-2 and AC-4._

- [ ] AC-1: `scripts/perf/routes.mjs` exports a tap list; each tap has an id, a `from` route, the link it clicks and a `to` route, starting with `this-week→teams` (on the mobile profile through the More sheet, since Teams isn't in the bottom tabs) and `teams→this-week`. A test in `web/lib/perf.test.ts` fails if a tap's `from` or `to` isn't a signed-in route in `ROUTES`.
- [ ] AC-2: In the `fixture` job, a puppeteer-core runner (pinned in `scripts/perf/package.json`) times each tap `RUNS` times on Lighthouse's mobile profile and throttling (Slow 4G, 4× CPU) with the signed-in session: it loads `from`, clicks, and stops the clock when the `<h1>` shows `to`'s heading and two frames have painted (`ms`), and again when the app shell is no longer `aria-busy` and two frames have painted (`loadedMs`). `metrics.json` gains `taps.<id>.loads[]`, each `{ ms, loadedMs, requests[] }` or `{ error }`. The shell sets `aria-busy="true"` only while it draws the loading state (unit test in `app-shell.test.tsx`).
- [ ] AC-3: A pure function in `scripts/perf/lib/perf.mjs` reduces a tap's loads to its first hit and median, leaving errors out; Vitest proves three loads give the right first and median, and a failed load is excluded and listed.
- [ ] AC-4: The fixture comment gains a "Taps, reported, never gated" table: one row per tap with first hit / median for heading and loaded, and the baseline's medians when one exists. Vitest proves the table renders and that a tap's timing never adds to `problems`.
- [ ] AC-5: A tap that never lands is listed under "Runs that didn't finish". A tap that requests `/api/py/*` or another host is a gate problem that fails the fixture run, named in the failure the way a page load's forbidden request is. Vitest proves both.
- [ ] AC-6: The preview run times no taps: `measure.mjs` without `PERF_MODE=fixture` writes no `taps`, and the preview comment has no taps table (Vitest for the comment).
- [ ] AC-7: `docs/02-architecture.md` › Performance checks describes the tap runner, and a new decision row records how it amends D-101 and D-125 (both approved by the owner).
- [ ] AC-8: The fixture comment on this task's PR shows both tap rows with numbers, not "–".

## Out of scope

- Gating on tap timings: timings are reported, never gated (02 › Performance checks).
- Timing taps on the preview run (owner, 2026-11-10).

## Files likely touched

- `scripts/perf/measure.mjs`, `scripts/perf/routes.mjs`, `scripts/perf/lib/perf.mjs`, `scripts/perf/package.json`
- `web/lib/perf.test.ts`
- `docs/02-architecture.md` › Performance checks

## Verification

- Automated: `pnpm --dir web exec vitest run lib/perf.test.ts components/shell/app-shell.test.tsx` (TASK-014 AC blocks); the lighthouse workflow's fixture job on this PR runs the tap runner for real.
- Manual: open the fixture comment on this task's PR: a "Taps, reported, never gated" table with `this-week→teams` and `teams→this-week`, each showing heading and loaded first hit / median in ms or s, not "–".

## Follow-ups

_Work noticed during this task and deliberately left out. Each bullet ends `→ <path> § <section>` (where it was placed) or `→ not tracked: <reason>`. See `.claude/skills/track-follow-ups/classify.md`; the PR's Follow-ups section is copied from here._

## Plan

Approved by the owner 2026-11-10 at f6cac60, with both numbers per tap (heading and loaded).

**Steps**
1. `scripts/perf/routes.mjs`: `TAPS`, each `{ id, from, to, heading, via?, link }` (`via` an untimed click, e.g. opening the More sheet). `perf.mjs` gets a pure `unknownTapRoutes(taps, routes)`.
2. `scripts/perf/lib/perf.mjs`: tap typedefs; `tapEmulation()` (Lighthouse's own `mobileSlow4G` throttling and mobile screen and user agent, as the CDP and puppeteer settings); `tapsFor(mode)` (none for the preview run); `aggregateTap()` (first, median of `ms` and `loadedMs`, errors); tap gate problems from `forbiddenPath` inside `checkRun`; `mergeMetrics` carries `taps`; `renderComment` draws the fixture-only "Taps, reported, never gated" table and lists taps that didn't finish.
3. `scripts/perf/taps.mjs` (new): puppeteer-core on `CHROME_PATH`, same emulation and throttling, signed in with the headers file Lighthouse gets. Per run: load `from`, click `via`, tap `link`; in-page clock from the tap to `<h1>` = `heading` + 2 frames (`ms`) and to the shell not `aria-busy` + 2 frames (`loadedMs`); records request URLs from tap to loaded (Vercel extras dropped); errors scrubbed of secrets.
4. `scripts/perf/measure.mjs`: runs the taps when `PERF_MODE=fixture`, writes `metrics.taps`.
5. `scripts/perf/report.mjs`: `load()` aggregates taps (current and baseline) and passes them to `checkRun` and `renderComment`.
6. `scripts/perf/package.json` and `package-lock.json`: pin `puppeteer-core` 25.16.0, the version Lighthouse already installs (the plan said 25.13.0, a stale local copy; the lockfile has 25.16.0).
7. `web/components/shell/app-shell.tsx`: `aria-busy` on the content column while `state` is `loading`; test in `app-shell.test.tsx`.
8. `.github/workflows/lighthouse.yml`: fixture job timeout 25 → 30 minutes.
9. Docs: a tap-runner paragraph in `docs/02-architecture.md` › Performance checks; a new D-### amending D-101 and D-125 (plus "Amended by" on both rows); README › Performance checks names the taps table.

**Files** (15, under the limit of 20): the 8 under `scripts/perf/` and `.github/workflows/`, `web/lib/perf.test.ts`, `app-shell.tsx` and its test, `docs/02-architecture.md`, `docs/decisions.md`, `README.md`, this task file. Not in "Files likely touched": `taps.mjs`, `report.mjs`, `package-lock.json`, `lighthouse.yml`, the two shell files, `decisions.md` and README.

**Test strategy** (`web/lib/perf.test.ts`, `describe("TASK-014 AC-n …")`)
- AC-1: the real `TAPS` pass `unknownTapRoutes`; a tap naming an unknown or signed-out route fails.
- AC-2: `tapEmulation` equals Lighthouse's `constants.js` mobile values; the shell's `aria-busy` (`app-shell.test.tsx`); the real timing is AC-8.
- AC-3: `aggregateTap` on three loads, and on loads with one error.
- AC-4: `renderComment` (fixture) has the taps table with heading and loaded cells and baseline medians; `checkRun` adds no problem for any timing.
- AC-5: a tap with only errors is listed under "Runs that didn't finish"; a tap request to `/api/py/x` or another host is in `problems`.
- AC-6: `tapsFor("preview")` is empty; the preview comment has no taps table even when given taps.
- AC-7: reviewed against the docs (spec-reviewer).
- AC-8: the PR's fixture comment (ready gate).

**Risks:** CDP throttling is close to Lighthouse's devtools method, not identical; shared-runner timings are noisy (reported only).

## Review log

_Filled by /implement-task. One line per round._

## Blocked

_Only if status is Blocked: what failed, what was tried, best hypothesis, decision needed._

## Metrics

- Verify rounds:
- Review rounds:
- First-pass AC FAILs:
- Plan revisions after approval:
