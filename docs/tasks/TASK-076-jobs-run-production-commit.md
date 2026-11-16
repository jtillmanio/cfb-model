---
id: TASK-076
title: Run the scheduled jobs on the commit production serves
status: Draft
depends_on: []
size: M
model: opus
autonomy: attended
ui: false
plan_status: none
planned_at_commit:
---

# TASK-076 — Run the scheduled jobs on the commit production serves

## Goal

A merged migration that hasn't been released yet no longer breaks the scheduled jobs. `results`, `lines` and `rate-and-predict` keep publishing on the code that matches production's schema. If a job ever does meet a schema older than its code, it stops before touching anything and says to run the release.

## Context

- **Incident (2026-11-13 to 11-16):** TASK-069 (#157) merged migration `0006_nfl`, which seeds `sports ('nfl')`, on 2026-11-13. The last release ran on 2026-11-04, so production stayed at `0005`. `results.yml` and `lines.yml` check out `main` with no `ref:`, so from #157 on they ran the NFL publish (`engine/publish/nfl.py` → `upsert_teams`) against production. Every run failed with `ForeignKeyViolation ... fk_teams_sport_id_sports: Key (sport_id)=(nfl) is not present in table "sports"`. Lines failed every run from 2026-11-13 20:49 UTC and Results every run from 2026-11-15. `0007` and `0008` (contests) were also unreleased. Example runs: Results 43853814223, Lines 43753683653.
- **The release's ordering rule is broken by the jobs:** docs/02-architecture.md § Release & operations says "schema goes first and code second, so old code briefly runs on the new schema, never the reverse." Release runs migrations before promoting, but the jobs skip that order by running `main`'s code as soon as it merges.
- **Existing pattern to reuse:** `backup.yml`'s "Find the commit production serves" step (D-109) reads `commit` from `PRODUCTION_URL/api/py/health` and checks out that SHA. It was built for the same reason: "main's views can need a migration production hasn't had yet, which would fail every nightly run until a release." `release.py`'s `pending_migrations` already computes which migrations production lacks.
- **Recommended approach (the plan decides):** check out production's commit in all three job workflows (a composite action shared with `backup.yml`). Also add an engine guard as a second line of defence. The guard fails only when production is *behind* the code's migration head. When production is ahead, which happens between a release's migrate and promote steps, it lets the run continue, because old code on a new schema is the supported direction.
- **Open questions for the plan:**
  1. The workflow YAML still comes from `main` (the dispatcher always dispatches `ref: main`, D-122), but the code would come from production's commit. A step command written on `main` (for example, a new `rate-and-predict` flag or spec path) could call a CLI that production's commit doesn't have. Options: run the command from a script inside the checked-out tree, or accept the coupling and document it.
  2. Does a branch dispatch need a way to test its own engine change (for example a `code_ref` input, empty by default), now that a dispatch runs production's code?
- Architecture: docs/02-architecture.md § Components › 4. Jobs, § Release & operations
- Decisions: D-027, D-108, D-109, D-122, D-123, D-129, D-149, D-169

## Acceptance criteria

- [ ] AC-1: Given production serves commit P (its `/api/py/health` `commit`) and `main` is ahead of P, when `results.yml`, `lines.yml` or `rate-and-predict.yml` runs (dispatched or fallback), then the engine code, specs and migrations it runs are P's, and the step summary names P (expected: summary line `Running production's commit <P>`, or wording the plan fixes, with the full SHA).
- [ ] AC-2: Given `/api/py/health` doesn't return a 40-hex `commit` (unreachable, an error status, or `unknown`), when any of the three workflows runs, then it fails before any CFBD call, lake write or database connection, and the summary names the URL and what it returned (expected: non-zero exit, `cfbd_calls.json` unchanged).
- [ ] AC-3: Given production's `alembic_version` is an ancestor of, and not equal to, the head of the migrations in the code being run, when `engine job results|lines|rate-and-predict --target live` starts, then it exits with a new distinct exit code before any CFBD call, lake write or production write, and the summary names production's revision, the code's head and "run the release workflow" (pytest against the test database, migrated to a revision below head).
- [ ] AC-4: Given production's revision equals the code's head, or is a revision the code's migrations don't contain (production ahead, during a release), when the same job starts, then the guard lets the run continue, and in the "ahead" case prints a one-line warning (pytest: both cases reach the pull step).
- [ ] AC-5: README › Jobs, docs/02-architecture.md § Components › 4. Jobs and § Release & operations, and a new decisions row say that the jobs run production's commit, that a change to a job reaches production only through a release, and what the new exit code means. Each job's `### Read a failed run` section lists the new failure.

## Out of scope

- Changing `release.yml`, or having it start the jobs after a promote.
- Making the dispatcher (`infra/dispatcher/`) dispatch a ref other than `main`.
- Running the release automatically when migrations are pending.
- Retrying CFBD timeouts (TASK-077).
- The planned `scores` and `external-ratings` jobs, which don't exist yet. The decisions row should state the rule so they follow it when they land.

## Files likely touched

- `.github/actions/production-commit/action.yml` — new composite action, the health lookup taken out of `backup.yml`
- `.github/workflows/backup.yml` — use the shared action
- `.github/workflows/results.yml` — check out production's commit
- `.github/workflows/lines.yml` — check out production's commit
- `.github/workflows/rate-and-predict.yml` — check out production's commit (it needs `PRODUCTION_URL` and the bypass secret too)
- `python/engine/src/engine/jobs.py` — the migration-head guard before the pull, shared by `run` and the rate-and-predict path
- `python/engine/src/engine/cli.py` — the new exit code in `_job` and `_rate_job`
- `python/db/src/db/release.py` — reuse or expose `pending_migrations` for the guard, if the plan chooses that
- `python/engine/tests/test_jobs.py` — guard cases for behind, equal and ahead
- `python/engine/tests/test_rate_and_predict.py` — the guard on the rate-and-predict path
- `README.md` — § Jobs, the job workflows' `### Read a failed run` sections, and § Backups if its step moves
- `docs/02-architecture.md` — § Components › 4. Jobs, § Release & operations
- `docs/decisions.md` — new row (amends D-123 and D-149, applies D-109)

## Verification

- Automated: `python/engine/tests/test_jobs.py` has a guard test that fails on today's code: with the test database migrated to a revision below head, `run("lines", ...)` exits with the new code, the CFBD fake gets no request and the ledger is unchanged. The equal and ahead cases pass through. There is an equivalent case in `test_rate_and_predict.py`.
- Manual: dispatch `lines.yml` on the task branch with `fallback_cron` empty → expected: the summary names the commit production serves, which is not the branch head, and the run succeeds. Then temporarily point `PRODUCTION_URL` at a path that returns 404 (or test it with a dry-run input the plan adds) → expected: it fails at the lookup with no CFBD call in the ledger.

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
