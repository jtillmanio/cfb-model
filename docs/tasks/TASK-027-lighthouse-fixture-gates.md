---
id: TASK-027
title: Gate Lighthouse on an in-job build on the seeded fixture DB
status: Review
depends_on: [TASK-008]
size: M
model: opus
autonomy: attended
ui: false
plan_status: approved
planned_at_commit: c6d9ea8
---

# TASK-027 — Gate Lighthouse on an in-job build on the seeded fixture DB

## Goal

A PR fails the Lighthouse check only when its own code made a page heavier, never because the preview database's data changed. Each PR's preview is still measured on real data, and those numbers are shown on the PR but never fail it.

## Context

- Task list: `docs/08-tasklist.md` › M5 › M5.0. It must merge before M5.6 (This Week) sets the first data-heavy budget.
- Decisions: **D-125** (settles roadmap open question 5; amends D-101), D-101, D-106 (session minting), D-089 (fixture seed), D-012 (preview and production secrets differ).
- Architecture: `docs/02-architecture.md` › Performance checks (Lighthouse). The new "Where it measures" paragraph is the spec. The rest of that section (Triggers, Signing in, Workflow shape, Baseline, Routes, Budgets) still describes preview gating, and this task's PR rewrites it. Also update › Testing strategy's Performance row.
- Why: docs-only PR #73 failed when the preview database filled with the full FBS list and `/teams` grew from 5,861 to 12,444 doc bytes with no code change. PR #74 raised the budget to get past it. A slate swings from about 10 to about 60 games, so preview budgets loose enough to absorb the data would hide real regressions.
- The pattern to copy: CI's `verify` job (`.github/workflows/ci.yml`) starts Postgres with `./.github/actions/start-postgres`, migrates and seeds the test DB (`pnpm db:migrate:test`, `pnpm db:seed`), runs `pnpm build` with `API_URL` set (`next.config` bakes the `/api/py` rewrite in at build time), and `web/playwright.config.ts` serves `next start` plus uvicorn (`APP_ENV=test`) with the test-only values in `web/e2e/test-env.ts` (`TEST_AUTH_SECRET`, `TEST_GITHUB_ID`, `TEST_API_JWT_SECRET`, and `AUTH_TRUST_HOST=true` because `next start` runs as production off Vercel).
- The gated run signs in by minting a session with the test-only `AUTH_SECRET` (not a secret) through the existing `mint-session.mjs`. It needs no Vercel bypass header and no repository secret. The preview run keeps `PREVIEW_AUTH_SECRET` and `VERCEL_AUTOMATION_BYPASS_SECRET` exactly as now.
- Budgets are reset once from the first fixture run with `node scripts/perf/report.mjs budget <metrics.json>` (median + 20%). The fixture holds only a handful of teams (`python/db/seeds/fixture/teams.json`), so `/teams` gets a smaller budget than today's. A local `next start` won't compress or serve exactly as Vercel does, which is why the numbers are reset rather than carried over.
- Actions minutes: the current workflow runs one matrix job per route. Building the app once per route would multiply build time by the route count, which reaches about 10 routes in Phase 4. The 2,000 free minutes are shared with CI and the scheduled jobs (02 › Non-functional requirements › Job budget).
- `workflow.readyGates` in `.claude/kit.json` has a "Lighthouse within budget" gate that names the preview. It should name the gated run.
- **Questions for the plan:**
  - Should this be one workflow with two triggers (`pull_request` gated, `deployment_status` reported), or two workflow files? The baseline finder (`report.mjs baseline`) looks up runs of `lighthouse.yml` by head SHA, so it has to find the gated run.
  - Should the two runs share one PR comment or use two? They finish at different times, so one shared comment needs a safe way for each run to edit only its own part.
  - Should docs-only PRs skip measuring through `scripts/ci-scope.mjs`, as CI's build steps do? If so, the baseline has to skip runs that carry no metrics.
  - Which run's timings does the comment show?

## Acceptance criteria

- [x] AC-1: Given a PR, the gated Lighthouse run builds the app once, serves it with the API on a freshly migrated and seeded test DB inside the job, and measures every route in `scripts/perf/routes.mjs`: `/login` signed out, and `/teams` signed in with a session minted from the test-only `AUTH_SECRET`. It uses no Vercel URL and no repository secret. The run fails on exactly the problems D-101 lists (an `/api/py/*` request, bytes or requests over budget, CLS ≥ 0.1, accessibility below the recorded score, or a route that didn't measure or ended on an unexpected URL).
- [x] AC-2: Two gated runs on the same commit give each route's doc bytes and JS bytes within 1% of each other, and the same request count. `scripts/perf/budget.json` and the `perf-budget` table in `docs/02-architecture.md` are regenerated from a gated run by `report.mjs budget`, and the note beside the table records that run and the reason for the reset (D-125).
- [x] AC-3: Given a preview deployment of the PR, the preview run still measures every route and its numbers appear on the PR, labelled as reported only. A Vitest case in `web/lib/perf.test.ts` shows a preview-run result with a route over budget and a CLS of 0.2 producing no gate problem (the run exits 0). A second case shows the same metrics producing both problems in a gated run.
- [x] AC-4: The PR's Lighthouse comment(s) are edited in place on later runs, never added again. The gated run compares itself with the last merged PR's gated run, not a preview run. Vitest cases cover how the baseline run is chosen.
- [x] AC-5: With the current two routes, the gated run's whole workflow finishes in 15 minutes or less on this PR, as shown by the run's duration in `gh run view`.
- [x] AC-6: These docs describe the in-job gate, the preview's reported-only run and how to run each by hand: `docs/02-architecture.md` › Performance checks (Triggers, Signing in, Workflow shape, Baseline, Budgets; the "Not built yet" note removed) and its Testing strategy row; `README.md` › Performance checks (Run one by hand, Read a failed run, Set a route's budget, What it needs). The "Lighthouse within budget" gate in `.claude/kit.json` names the gated run.

## Out of scope

- Timing screen-to-screen taps (TASK-014).
- New routes or budgets for screens that don't exist yet. Each screen's PR adds its own, measured on the fixture build, and the table that holds its data adds the large instance to the fixture (D-089).
- Changing the fixture seed's data. `/teams` is measured on whatever the fixture holds today.
- Gating on timings: they stay reported only (D-101).
- Changing Vercel Deployment Protection, preview databases, or any repository secret or variable (owner settings; Claude never edits secrets).

## Files likely touched

- `.github/workflows/lighthouse.yml`: the gated in-job run on `pull_request`, plus the preview run as reported only (or a second workflow file, per the plan).
- `scripts/perf/report.mjs`: `plan`, `baseline` and `report` handle the gated and preview runs.
- `scripts/perf/lib/perf.mjs`: event and mode logic (`eventInputs`, `measurable`), report-only handling in the gate and comment, and baseline choice.
- `scripts/perf/measure.mjs`, `scripts/perf/mint-session.mjs`: an `http://127.0.0.1` target with no bypass header.
- `scripts/perf/budget.json`: reset from the first gated run.
- `web/lib/perf.test.ts`: AC-3 and AC-4 cases.
- `.github/actions/start-postgres/action.yml`: reused, probably unchanged.
- `docs/02-architecture.md`, `README.md`, `.claude/kit.json`: AC-6.

## Verification

- Automated: `web/lib/perf.test.ts` (preview mode never gates; gated mode does, with the same metrics; baseline picks the gated run; the budget table matches `budget.json`), run with `pnpm --dir web exec vitest run lib/perf.test.ts`.
- Manual: this PR's own gated run passes, and a second run on the same commit (`gh run rerun <id>`) lands within 1% on bytes → expected: both green, with the byte deltas reported in the PR body.
- Manual: this PR's preview run posts its reported numbers and passes, whatever they are.
- Manual: `gh run view <id>` for the gated run → expected: 15 minutes or less in total.

## Follow-ups

_Work noticed during this task and deliberately left out. Each bullet ends `→ <path> § <section>` (where it was placed) or `→ not tracked: <reason>`. See `.claude/skills/track-follow-ups/classify.md`; the PR's Follow-ups section is copied from here._

- TASK-014's tap runner should time taps on the fixture build, not the preview, now that gates run there (D-125) → docs/tasks/TASK-014-perf-tap-runner.md § Context (approved at plan)
- `download-artifact` puts a lone matching artifact straight into the download folder, which broke `merge` on the first fixture run (run 40015971648) → not tracked: done in this PR (plan revision; `metricsParts` and its test)
- The test auditor had to revert `scripts/perf/*.mjs` and `.github/workflows/lighthouse.yml` by hand: `testAudit.implementationExtensions` in `.claude/kit.json` lacks `.mjs` and workflows → not tracked: the owner asked for it as a separate chore PR once this one is approved

## Plan

_Approved 2026-10-23._

**Shape:** one workflow, `lighthouse.yml`, three triggers: `pull_request` → the gated **fixture** run; `deployment_status` → the **preview** run, reported only; `workflow_dispatch` → preview with a `url`, fixture on the chosen ref without one.

1. Tests first in `web/lib/perf.test.ts`, failing on the old code: plan modes (`pull_request` → fixture; dispatch without a URL → fixture); a preview run never gates (over budget + CLS 0.2 → no problems, exit 0) while the same metrics gate in a fixture run; a comment marker per mode; the baseline takes only runs of the same event; the new workflow shape; `paths-ignore` matches `scripts/lib/ci-scope.mjs`'s skip list.
2. `scripts/perf/lib/perf.mjs`: `measurable`/`eventInputs` return `{ mode, url }` (fixture URL `http://127.0.0.1:3100`); gate problems only in fixture mode (a preview lists forbidden requests and wrong landings as noticed, not gated, and compares nothing with a budget); `renderComment` and the marker per mode, so two comments per PR and no race between runs; `baselineRun` filters by `event`; the `/login` hint stops naming `PREVIEW_AUTH_SECRET`.
3. `scripts/perf/report.mjs`: `plan` outputs the mode; `baseline` walks merged PRs newest first (up to 10) to the first with a green run of the same event (docs-only PRs have no fixture run); `report` takes the PR from `pull_request` events and exits 0 in preview mode.
4. `.github/workflows/lighthouse.yml`: a single `fixture` job (start Postgres via the existing action, migrate and seed the test DB, `pnpm build` once, start uvicorn and `next start` in the background with `web/e2e/test-env.ts`'s test-only values as e2e does, mint with the test `AUTH_SECRET`, measure every route serially, guard, upload). The per-route `measure` matrix stays for previews. `pull_request` has `paths-ignore` for `docs/**`, `.claude/**`, `backups/**`, `*.md` (CI's scope skip list; a test keeps them in step).
5. Budgets: push, let the first fixture run go green, `report.mjs budget` on its metrics, re-run once for the < 1% check, commit `budget.json` and 02's table.
6. Docs: 02 › Performance checks (Triggers, Signing in, Workflow shape, Baseline, Budgets, Testing row; "Not built yet" removed), README › Performance checks, `.claude/kit.json`'s "Lighthouse within budget" gate (names the fixture run; docs-only PRs have none).

**Files:** `.github/workflows/lighthouse.yml`, `scripts/perf/lib/perf.mjs`, `scripts/perf/report.mjs`, `scripts/perf/budget.json`, `web/lib/perf.test.ts`, `docs/02-architecture.md`, `README.md`, `.claude/kit.json`, this task file; possibly comment-only edits to `scripts/perf/measure.mjs` and `scripts/perf/mint-session.mjs`.

**Test strategy:** AC-1 Vitest (modes, workflow shape) + this PR's green fixture run · AC-2 re-run on the same commit; the budget table test · AC-3 and AC-4 Vitest · AC-5 `gh run view` duration · AC-6 doc review and the table test.

**Risks:** a local `next start` gzips where Vercel serves brotli (expected; budgets are reset). The first fixture run has no baseline. The branch is stacked on PR #76; if #76 squash-merges first, merge `main` in.

## Review log

_Filled by /implement-task. One line per round._

Verify R1 PASS → (fixture run 40015971648 FAIL: lone artifact not merged; fixed) → R2 PASS | Audit R1 CHANGES (exit code and baseline walk untested; a test title) → R2 PASS | Spec R1 APPROVE

## Blocked

_Only if status is Blocked: what failed, what was tried, best hypothesis, decision needed._

## Metrics

- Verify rounds: 2
- Review rounds: 1
- First-pass AC FAILs: 0
- Plan revisions after approval: 2 (`metricsParts` after run 40015971648; `exitCode`/`findBaseline` extracted for the test audit)
