---
id: TASK-008
title: Run Lighthouse on every PR preview and set the first budgets
status: Review
depends_on: [TASK-007, TASK-002]
size: M
model: opus
autonomy: attended
ui: false
plan_status: approved
planned_at_commit: a553689
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
- *From #9 (kit 2.4 upgrade):* once this workflow runs on previews, add a Lighthouse gate to `workflow.readyGates` in `.claude/kit.json` (budget green on the PR's preview, checked by Claude, with the workflow run as its failure log).
- *From #18 (TASK-007):* notes for `measure.mjs`, from `ledger`: write Lighthouse's raw output outside the reports folder and delete it once read; rebuild the HTML from the scrubbed report; pass `--disable-full-page-screenshot`; key the npm cache on `scripts/perf/package-lock.json`; pass `AUTH_ALLOWED_GITHUB_ID` to `mint-session.mjs` through `env:`. That repository **variable** isn't in the owner prerequisites above and didn't exist on 2026-10-12 (`gh variable list`).
- *From #18 (TASK-007), open question for the plan:* a tap → next-paint runner (`ledger` measures screen-to-screen navigation, not only cold loads). Neither `docs/02-architecture.md` nor D-101 plans it: include it here, or make it its own task?

## Acceptance criteria

- [x] AC-1: `.github/workflows/lighthouse.yml` matches 02's shape: top-level `permissions: {}`, the `plan`, `measure` (matrix per route, `fail-fast: false`, concurrency `lighthouse-pr-<n>-<route>` with cancel-in-progress) and `report` jobs, with only `report` granted `pull-requests: write`; secrets reach scripts only through `env:`; header files go to a temp folder removed in an `if: always()` step; every request to the preview (Lighthouse `--extra-headers` and the session mint) carries `x-vercel-protection-bypass` from `VERCEL_AUTOMATION_BYPASS_SECRET`.
- [x] AC-2: On this PR's preview, the workflow runs on its own and measures `/login` signed out and `/teams` signed in, with neither ending on an unexpected URL; the PR has exactly one Lighthouse comment, and a re-run edits that comment instead of adding another.
- [x] AC-3: `scripts/perf/budget.json` holds, per route, `docBytes`, `jsBytes`, `requests` and `a11y` computed from this PR's preview run by 02's rule; the `perf-budget` table in `docs/02-architecture.md` matches it, with the measured numbers, Lighthouse version and Chrome version beside it.
- [x] AC-4: Vitest cases fail when `budget.json`'s keys differ from the route ids in `routes.mjs`, or when the `perf-budget` table in `docs/02-architecture.md` differs from `budget.json`.
- [x] AC-5: The run's uploaded artifacts are only scrubbed reports and `metrics.json` with 14-day retention, and the guard step passed; no artifact goes to LHCI temporary public storage.
- [x] AC-6: The README (or the setup doc the plan names) lists the workflow's secret and variable and what each is for.

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

## Follow-ups

- Tap → next-paint runner (ledger times screen-to-screen navigation, not only cold loads): not built here. Neither 02 nor D-101 plans it, and with one signed-in screen there is no screen-to-screen tap to time; plan it when a second signed-in screen ships → docs/tasks/TASK-014-perf-tap-runner.md (new, Draft) (approved at plan), with its stub in docs/08-tasklist.md § M1: Rails (M1.11)
- `gh workflow run lighthouse.yml -f url=…` can't run before merge: `workflow_dispatch` fires only once the file is on `main`. The branch's own `deployment_status` runs cover the ready gate → not tracked: listed in the PR's "How it was verified" as the check to run straight after merge
- `login`'s document bytes moved 1.3% between runs (4,005–4,058), over 02's "< 1%" check; `report.mjs budget` warns rather than refuses, and the 53 bytes sit well inside the 959-byte headroom → not tracked: recorded under the perf-budget table in docs/02-architecture.md and in the PR

## Plan

Approved 2026-10-13 at `a553689`.

**Steps**
1. Tests first, in `web/lib/perf.test.ts`:
   - AC-1: text checks on `.github/workflows/lighthouse.yml`, in the style of `python/db/tests/test_backup.py`: top-level `permissions: {}`; jobs `plan` → `measure` → `report`; the matrix with `fail-fast: false` and concurrency `lighthouse-<group>-<route>` with cancel-in-progress; `pull-requests: write` only in `report`; `secrets.` only as `VAR: ${{ secrets.X }}` env lines; an `if: always()` step that deletes the headers folder; 14-day uploads; no `lhci` or `temporary-public-storage`.
   - AC-4: `budget.json` keys equal the `ROUTES` ids; the `perf-budget` table in `docs/02-architecture.md` equals `budget.json`.
   - New helpers: `budgetFrom`, `chromeVersion`.
2. `scripts/perf/lib/perf.mjs`: `budgetFrom(metrics)` applies 02's rule (median + 20%, bytes rounded up to the next 1,000, requests rounded up, a11y = the measured median) and flags any route whose bytes move ≥ 1% between runs. `chromeVersion(lhr)` reads `environment.hostUserAgent`. `scripts/perf/report.mjs` gets `budget FILE`, which prints `budget.json` from a merged `metrics.json`.
3. `scripts/perf/measure.mjs` (new), following ledger minus the puppeteer tap runner: Lighthouse 3× on the matrix's one route, with ledger's flags plus `--disable-full-page-screenshot`. Raw output goes under `HEADERS_DIR` and is deleted once read. The JSON is scrubbed and the HTML rebuilt from the scrubbed result. `metrics.json` records the Lighthouse and Chrome versions.
4. `.github/workflows/lighthouse.yml` (new), in ledger's shape: `PREVIEW_AUTH_SECRET` reaches the scripts as `AUTH_SECRET`, and the `AUTH_ALLOWED_GITHUB_ID` variable and the bypass secret go through `env:`. The npm cache is keyed on `scripts/perf/package-lock.json`, with Node from `.nvmrc`.
5. Budgets in two pushes:
   - First push: `budget.json` with an empty entry per route (not gated, "No budget recorded"); the 02 table shows "–".
   - Second push: `report.mjs budget` on the run's `lighthouse-metrics` writes `budget.json`, the 02 table, and a "Measured" line (medians, Lighthouse and Chrome versions, run link).
6. `README.md` › Performance checks: triggers, secrets and variables, how to read a failed run, re-running by hand (AC-6).
7. `.claude/kit.json`: add the readyGate "Lighthouse within budget" (from #9's note in Context).
8. Close-out: tick `docs/06-roadmap.md` Phase 0's lighthouse line and the CLAUDE.md status line.

**Files:** `.github/workflows/lighthouse.yml` (new), `scripts/perf/measure.mjs` (new), `scripts/perf/budget.json` (new), `scripts/perf/lib/perf.mjs`*, `scripts/perf/report.mjs`*, `web/lib/perf.test.ts`, `docs/02-architecture.md`, `README.md`, `.claude/kit.json`*, plus bookkeeping in `docs/06-roadmap.md`* and `CLAUDE.md`* (* = not in "Files likely touched").

**Test strategy**

| AC | Proof |
|---|---|
| AC-1, AC-4 | Vitest |
| AC-2 | This PR's preview run; `report` re-run, then still exactly one comment |
| AC-3 | `budgetFrom` tests, plus the AC-4 table test |
| AC-5 | `gh api …/artifacts` (names and expiry), plus the guard step's log |
| AC-6 | Review |

**Risks**
- `workflow_dispatch` fires only once the file is on `main`, so the run with `-f url=…` is an after-merge check. The deployment-triggered run covers AC-2 and the ready gate.
- Size: 9 files, one over the split limit. Kept whole because the budgets must come from this workflow's own run on this PR.

## Review log

- Verify R1 PASS (one ESLint warning in the new test, fixed)
- Preview runs: 38359279590 on `f5503aa` (unbudgeted; set the budgets) and 38402578345 on `2c0b806` (gated against them): plan, measure (login), measure (teams) and report all green
- Audit R1 NOT RUN (rate limit) → R2: static OK on all 18 new cases. Dynamic NOT RUN: the permission classifier denied restoring `main`'s files in the working tree, and the tree was confirmed clean. Tests-first evidence from Phase 2: 17 of 18 new cases failed before the code existed (missing exports, workflow and budgets); the 18th, the versions-beside-the-table case, can only fail once `budget.json` has `measured`.
- Spec R1 CHANGES (Follow-ups bullet had no path; TASK-013 was a dropped ID; AC-2's comment half pending the PR) → fixed at close-out (TASK-014); follow-ups check APPROVE
- AC-2 on PR #29: run 38403658087 (`8f2a0c8`) posted one comment (6146476302, "✅ within budget"); re-running its `report` job edited that comment (updated 13:19:27Z → 13:20:03Z) and added none. The `96ae829` run was cancelled by the newer push, as its concurrency group intends

## Blocked

_Only if status is Blocked: what failed, what was tried, best hypothesis, decision needed._

## Metrics

- Verify rounds: 1
- Review rounds: 2 (spec R1 CHANGES on follow-ups only; R2 the close-out follow-ups check)
- First-pass AC FAILs: 0
- Plan revisions after approval: 0
