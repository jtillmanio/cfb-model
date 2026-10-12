---
id: TASK-007
title: Build the Lighthouse gate logic, report and session minting with tests
status: Done
depends_on: [TASK-001]
size: M
model: opus
autonomy: attended
ui: false
plan_status: approved
planned_at_commit: 3bb29d7
---

# TASK-007 — Build the Lighthouse gate logic, report and session minting with tests

## Goal

The logic that decides whether a PR preview passes its performance and accessibility checks, writes the one PR comment, and keeps secrets out of reports exists as tested code, ready for the workflow in TASK-008 to run.

## Context

- Task list: `docs/08-tasklist.md` › M1 › M1.5, split in two: this task is the pure logic, the report script and session minting; TASK-008 adds the workflow, the measuring script and the first budgets.
- Architecture: `docs/02-architecture.md` › Performance checks (Lighthouse): Gates, Reported never gated, Signing in, Reports stay private, Workflow shape (`plan`, `report` subcommands), Baseline, Files (`scripts/perf/routes.mjs`, `mint-session.mjs`, `report.mjs`, `lib/perf.mjs`; a Vitest test with fixture Lighthouse results and no network).
- Decisions: D-101 (what is gated and what is reported; minting with the preview `AUTH_SECRET`; scrub and guard; 14-day artifacts), D-012 (preview and production `AUTH_SECRET`s differ).
- Pattern: the owner's `ledger` project (`scripts/perf/`, `test/perf.test.ts`), used as a pattern, not a template (02 › Performance checks).
- Depends on TASK-001 for the Auth.js session cookie's name and encoding, which `mint-session.mjs` must reproduce outside `web/` (the e2e helper in `web/e2e/` stays separate; production has no way in except GitHub).
- `scripts/perf/package.json` pins its own dependencies and stays out of `pnpm-workspace.yaml`; only the workflow installs it (`npm ci --prefix scripts/perf`). The test runs in the web Vitest suite so `pnpm test` covers it.

## Acceptance criteria

- [x] AC-1: For each gated number (document bytes plus the RSC payload, JS bytes, request count, CLS, accessibility score), a Vitest case passes a fixture result exactly at budget and fails one just over it (CLS fails at ≥ 0.1; accessibility fails below the recorded score), and the failure names the route and the number.
- [x] AC-2: A fixture page load that requests any `/api/py/*` URL (including a prefetch) fails, and the failure names the URL; Vercel extras (`vercel.live`, `_next-live`) are excluded from request counts. A route that never finished measuring, or that ended on `/login`, fails with a message saying so.
- [x] AC-3: `measurable` refuses the production URL unless `allow_production` is set, and refuses deployment states other than `success` (Vitest cases for each).
- [x] AC-4: The scrubber removes every given secret and the minted cookie from a fixture Lighthouse JSON and HTML report, and the guard fails on a file that still contains one, naming the file but never printing the value (Vitest asserts the message contains the file name and not the secret).
- [x] AC-5: The PR comment is one Markdown body with a fixed HTML-comment marker; it reports TTFB, FCP, LCP and TBT as first hit / median beside the baseline (or "no baseline"), and timings never cause a failure. Baseline choice picks the newest merged PR's newest green run (Vitest on fixture run lists).
- [x] AC-6: `scripts/perf/routes.mjs` lists `/login` (signed out) and `/teams` (signed in), and a Vitest case fails when a top-level page under `web/app/` has no route in the list.

## Out of scope

- `.github/workflows/lighthouse.yml`, `measure.mjs`, `budget.json` and the budget table in `docs/02-architecture.md` (TASK-008).
- Running Lighthouse or Chrome in tests: everything here runs on fixture results with no network.
- Deciding where byte gates measure data pages (roadmap › Open questions 5; decided before Phase 4).

## Files likely touched

- `scripts/perf/package.json` — pinned Lighthouse and helpers, outside the pnpm workspace (new; `package-lock.json` via npm).
- `scripts/perf/lib/perf.mjs` — gates, request filtering, scrubber, guard, baseline choice, comment (new).
- `scripts/perf/report.mjs` — `plan | guard DIR | merge DIR | baseline | report` (new).
- `scripts/perf/mint-session.mjs` — mints the Auth.js session cookie from `AUTH_SECRET`, masking it first (new).
- `scripts/perf/routes.mjs` — the one route list (new).
- `web/lib/perf.test.ts` — the Vitest suite on fixture results (new).
- `web/vitest.config.mts` or `web/tsconfig.json` — only if importing `../scripts/perf` needs it.

## Verification

- Automated: `web/lib/perf.test.ts` (AC-1 to AC-6) in `pnpm test`.
- Manual: run `node scripts/perf/report.mjs plan` with a fixture event file → prints the URL and route list as JSON, or the reason it won't measure. Run `mint-session.mjs` with a throwaway secret → its first output line is `::add-mask::`, and the cookie value never appears unmasked.

## Plan

Approved 2026-10-11.

**Steps**
1. `scripts/perf/package.json` (new, `"type": "module"`, Node 24): pins `lighthouse` (latest stable) and `@auth/core@0.41.3` (the version `next-auth@5.0.0-beta.32` installs); `package-lock.json` via `npm install`. Outside the pnpm workspace.
2. `scripts/perf/routes.mjs`: `ROUTES` = `login` (`/login`, signed out) and `teams` (`/teams`, signed in).
3. `scripts/perf/lib/perf.mjs`: pure functions, no imports, adapted from ledger: `summariseLhr` (document + RSC bytes, JS bytes, requests, CLS, a11y, TTFB/FCP/LCP/TBT, landed path; drops `vercel.live` / `_next-live`; collects `/api/py/*`), `aggregateRoute` (first hit + median), `gateProblems` (names route and number or URL; timings never checked), `measurable`, `scrubLhr`, `scrubText`, `guardMessage` (file names, never values), `baselinePr` / `baselineRun`, `renderComment`, `findComment`, `mergeMetrics`, `sessionCookieName(url)` and `mintSession({ url, secret, githubId, encode })` with `encode` injected so the lib has no dependencies. JSDoc types instead of `.d.mts` files.
4. `scripts/perf/mint-session.mjs`: `::add-mask::` for `AUTH_SECRET` and the bypass secret first, mints with `@auth/core/jwt`, masks the cookie value, writes `signed-in.json` / `signed-out.json` to `HEADERS_DIR`, logs statuses only. Reads the allowlisted ID from `AUTH_ALLOWED_GITHUB_ID` (TASK-008 adds the repo variable).
5. `scripts/perf/report.mjs`: `plan | guard DIR | merge DIR | baseline | report`, Node plus the GitHub REST API. A missing `budget.json` (TASK-008) means "no budget recorded", not a crash.
6. `web/lib/perf.test.ts`: fixtures, no network.

**Files:** the six above plus `package-lock.json` (generated) and `docs/decisions.md` (one row on session minting; not in "Files likely touched"). 8 files, no schema or UI: kept whole.

**Test strategy** (`web/lib/perf.test.ts`)
- AC-1: each gated number at budget passes, +1 fails, message names route and number; CLS 0.099 passes, 0.1 fails; a11y equal passes, one below fails.
- AC-2: an `/api/py/teams?_rsc=…` prefetch fails naming it; Vercel extras excluded from counts and bytes; errored-only runs say "not measured"; landing on `/login` says signed out.
- AC-3: production refused without `allow_production`, allowed with it; `failure`, `inactive`, `pending` skipped.
- AC-4: scrubbed fixture JSON and HTML hold no secret or cookie; the guard message holds the file name and not the secret.
- AC-5: the comment starts with the marker, shows first / median beside the baseline or "no baseline"; huge timings give zero problems; baseline choice on fixture PR and run lists.
- AC-6: route list entries; a scan of `web/app/` finds every top-level page, and the scanner is tested on a temp dir with an unlisted page.
- Minting: a cookie minted with `next-auth/jwt`'s `encode` decodes with the same salt to `sub = githubId`; the name is `__Secure-authjs.session-token` on https; `@auth/core` in `scripts/perf/package.json` matches the lockfile's for next-auth.

**Decisions in the plan:** `/` is exempt from the route test while it redirects to `/teams` (This Week takes it in Phase 4). `/api/auth/*` requests aren't gated (the spec forbids `/api/py/*`). `scripts/perf/*.mjs` isn't linted by `pnpm lint` (follow-up).

## Review log

Verify R1 PASS | Audit R1 CHANGES (AC-2: the only vercel.live fixture also matched the _next-live rule, NON-DISCRIMINATING) → R2 PASS | Spec R1 CHANGES (code read budget key `docRscBytes`, docs/02 and TASK-008 AC-3 say `docBytes`; guard didn't mask) → R2 APPROVE | Verify R2 (after review fixes) PASS

## Blocked

_Only if status is Blocked: what failed, what was tried, best hypothesis, decision needed._

## Metrics

- Verify rounds: 1 (plus one re-run after the review fixes, PASS)
- Review rounds: 2
- First-pass AC FAILs: 0
- Plan revisions after approval: 0 (`eventInputs` was added inside plan step 5 so `report.mjs plan` reads a fixture event file; spec review judged it in scope)
