---
id: TASK-008
title: Run Lighthouse on every PR preview and set the first budgets
status: Ready
depends_on: [TASK-007, TASK-002]
size: M
model: opus
autonomy: attended
ui: false
plan_status: none
planned_at_commit:
---

# TASK-008 — Run Lighthouse on every PR preview and set the first budgets

## Goal

Every PR's preview is measured automatically: the PR gets one comment with the numbers, and it fails only when a page gets heavier, shifts, loses accessibility, or makes the browser call the API.

## Context

- Task list: `docs/08-tasklist.md` › M1 › M1.5 (second half; the logic is TASK-007).
- Architecture: `docs/02-architecture.md` › Performance checks (Lighthouse): Measurement profile (mobile, devtools throttling, performance + accessibility, three runs, median, `--no-sandbox`, `x-vercel-skip-toolbar: 1`), Triggers (`deployment_status` success on Preview, `workflow_dispatch` with `url` and `allow_production`), Signing in, Reports stay private (scrub, guard, 14-day artifacts, never LHCI public storage), Workflow shape (`permissions: {}`; `plan` → `measure` matrix with `fail-fast: false` and per-route concurrency → `report`, the only job with `pull-requests: write`), Budgets (never invented: median + 20% from the first preview run, bytes rounded up to the next 1,000, a11y is the measured score; record Lighthouse and Chrome versions), and the `perf-budget` table markers.
- Decisions: D-101, D-012.
- `docs/06-roadmap.md` › Phase 0: routes `/login` and `/teams` to start; repo secrets documented in the setup docs.
- Depends on TASK-002 so `/login`'s budget is measured on the finished screen, not the stub.
- **Owner prerequisites:**
  - Repository **secrets** `PREVIEW_AUTH_SECRET` (the same value as Vercel Preview's `AUTH_SECRET`, never production's) and `VERCEL_AUTOMATION_BYPASS_SECRET` (Vercel › Deployment Protection › Protection Bypass for Automation, as in `ledger`).
  - The repository **variable** `PRODUCTION_URL` (from TASK-005).
  - Claude never edits secrets.
- Previews have no GitHub sign-in (D-102), so the minted session is the only way this job gets past `/login`.
- `workflow.readyGates` includes "Changed workflow run on the branch": the PR's own preview triggers the workflow, and `gh workflow run lighthouse.yml --ref <branch> -f url=<preview>` re-runs it.

## Acceptance criteria

- [ ] AC-1: `.github/workflows/lighthouse.yml` matches 02's shape: top-level `permissions: {}`, the `plan`, `measure` (matrix per route, `fail-fast: false`, concurrency `lighthouse-pr-<n>-<route>` with cancel-in-progress) and `report` jobs, with only `report` granted `pull-requests: write`; secrets reach scripts only through `env:`; header files go to a temp folder removed in an `if: always()` step; every request to the preview (Lighthouse `--extra-headers` and the session mint) carries `x-vercel-protection-bypass` from `VERCEL_AUTOMATION_BYPASS_SECRET`.
- [ ] AC-2: On this PR's preview, the workflow runs on its own and measures `/login` signed out and `/teams` signed in, with neither ending on an unexpected URL; the PR has exactly one Lighthouse comment, and a re-run edits that comment instead of adding another.
- [ ] AC-3: `scripts/perf/budget.json` holds, per route, `docBytes`, `jsBytes`, `requests` and `a11y` computed from this PR's preview run by 02's rule; the `perf-budget` table in `docs/02-architecture.md` matches it, with the measured numbers, Lighthouse version and Chrome version beside it.
- [ ] AC-4: Vitest cases fail when `budget.json`'s keys differ from the route ids in `routes.mjs`, or when the `perf-budget` table in `docs/02-architecture.md` differs from `budget.json`.
- [ ] AC-5: The run's uploaded artifacts are only scrubbed reports and `metrics.json` with 14-day retention, and the guard step passed; no artifact goes to LHCI temporary public storage.
- [ ] AC-6: The README (or the setup doc the plan names) lists the workflow's secret and variable and what each is for.

## Out of scope

- Gate logic, the scrubber and session minting (TASK-007).
- Routes for screens that don't exist yet: each later screen adds its own route and budget in its PR.
- Deciding where byte gates measure data pages (roadmap › Open questions 5).
- Turning Vercel Deployment Protection on or off (an owner setting); this task only sends the bypass header.

## Files likely touched

- `.github/workflows/lighthouse.yml` — the workflow (new).
- `scripts/perf/measure.mjs` — runs Lighthouse three times per route and writes `metrics.json` (new).
- `scripts/perf/budget.json` — budgets from the first preview run (new).
- `docs/02-architecture.md` — the `perf-budget` table and the measured numbers.
- `web/lib/perf.test.ts` — AC-4.
- `README.md` — the secret and variable.

## Verification

- Automated: `web/lib/perf.test.ts` (AC-4); the workflow's run on this PR's preview (AC-2, AC-5); a `workflow_dispatch` run on the branch with the preview URL.
- Manual: open the PR comment → one comment, both routes listed with bytes, requests, CLS and accessibility against budget, and timings as first hit / median with "no baseline". Download an artifact → no cookie or secret in any file.

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
