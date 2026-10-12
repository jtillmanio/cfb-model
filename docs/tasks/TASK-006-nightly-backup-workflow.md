---
id: TASK-006
title: Add the nightly backup workflow with restore verification
status: Ready
depends_on: []
size: M
model: opus
autonomy: attended
ui: false
plan_status: none
planned_at_commit:
---

# TASK-006 — Add the nightly backup workflow with restore verification

## Goal

Every night the production database is dumped, proven restorable, and stored in R2, and a written runbook gets the owner from "the database is gone" to a working app within two hours.

## Context

- Task list: `docs/08-tasklist.md` › M1 › M1.4.
- Architecture: `docs/02-architecture.md` › Release & operations › Backups (`pg_dump`, check exit code and size, restore into a Postgres container, re-apply views, run the view checks, compare row counts with production read-only, then upload to R2 `backups/`; only the backup workflow gets write access); › Environments & databases (`PG_MAJOR`, PGDG client on `PATH`); › Non-functional requirements › Backups (recovery point ≤ 24 h, recovery time ≤ 2 h, runbook written in this task); › What's reproducible and what isn't.
- Decisions: D-019 (backup steps), D-017 and D-099 (`PG_MAJOR = 18`, set once; the backup workflow reads the same value as CI), D-092 (RPO/RTO), D-002 (R2).
- Existing code: `.github/workflows/ci.yml` sets `PG_MAJOR` in its job `env` and starts Postgres in a step; `python/db/src/db/migrate.py` `apply_views()`; `python/db/views/` is empty today, so the view step must pass with zero views.
- **Interpretation to confirm at the plan gate:** the view tests in 02 assert fixture values, which a production restore can't match. Here "run view tests" means every `python/db/views/*.sql` applies to the restored database and each view answers a `SELECT` without error.
- **Decide at the plan gate:** where `PG_MAJOR` lives so CI and backup read one value (a repo variable or a file both workflows read); how row counts are taken so they match the dump's snapshot (e.g. `pg_export_snapshot` + `pg_dump --snapshot`); the object name (`backups/<UTC date>.dump`) and the schedule.
- **Owner prerequisites:**
  - A Cloudflare R2 bucket **of its own** for backups (e.g. `cfb-backups`), not a `backups/` folder in the lake bucket: R2 tokens can be limited to a bucket but not to a folder, so a lake-bucket token could also overwrite the append-only raw lake.
  - An R2 API token with Object Read & Write on that bucket only.
  - A read-only Postgres role (`backup_reader`) on production's `main` branch, so a bug in the workflow can't write to production.
  - Repository **secrets** `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `BACKUP_DATABASE_URL` (the read-only role's direct URL); **variables** `R2_ACCOUNT_ID`, `R2_BUCKET`.
  - Claude never edits secrets.
- **Stop and ask:** the backup reads production. Running it on the branch (`gh workflow run backup.yml --ref <branch>`) needs the owner's go-ahead in the session.
- *From #14 (Postgres from the ECR mirror):* if the restore runs in a container, pull it as `public.ecr.aws/docker/library/postgres:<PG_MAJOR>`, as `ci.yml` does; anonymous Docker Hub pulls from shared runners hit its rate limit.

## Acceptance criteria

- [ ] AC-1: Row-count comparison is a tested Python function: given per-table counts from production and from the restored database, it passes when they match and fails naming each table that differs, including a table present on one side only. Unit tests cover match, one mismatch and a missing table.
- [ ] AC-2: `.github/workflows/backup.yml` runs on a nightly `schedule` and `workflow_dispatch`, installs the PostgreSQL client for `PG_MAJOR` from PGDG, and reads `PG_MAJOR` from the same single source as `ci.yml` (no second literal `18` in either workflow).
- [ ] AC-3: The workflow runs in order: `pg_dump` (fails on a non-zero exit or an empty file) → restore into a `postgres:${PG_MAJOR}` container → apply views → query each view → compare row counts → upload to R2 `backups/`. Any failed step stops the run before the upload, so a bad dump is never stored.
- [ ] AC-4: R2 credentials and `BACKUP_DATABASE_URL` appear only in `backup.yml`, reach steps only through `env:`, and the workflow reads production only through `BACKUP_DATABASE_URL`; the workflow's `permissions` are `contents: read` or narrower.
- [ ] AC-5: An owner-approved run on the branch goes green, uploads one dump to R2 `backups/`, and its job summary lists each table's row count on both sides and the dump size.
- [ ] AC-6: `docs/runbooks/restore.md` gives numbered steps to restore the latest dump into a new Neon branch, point production at it, apply views, and check `/api/py/health`, with how to find the newest dump and the 2-hour recovery-time target.

## Out of scope

- Pruning or rotating old dumps (dumps are well under 100 MB; follow-up if R2 usage grows).
- Backing up the data lake (it's its own backup, 02 › Backups).
- Automated restore to production; the runbook is manual.
- The `release` workflow (TASK-005).

## Files likely touched

- `.github/workflows/backup.yml` — the workflow (new).
- `.github/workflows/ci.yml` — read `PG_MAJOR` from the shared source.
- `python/db/src/db/backup.py` — row counts and their comparison (new).
- `python/db/src/db/__main__.py` — a `rowcounts` / `compare` subcommand the workflow calls.
- `python/db/tests/test_backup.py` — AC-1 (new).
- `docs/runbooks/restore.md` — the restore runbook (new).

## Verification

- Automated: `python/db/tests/test_backup.py`; CI still green after the `PG_MAJOR` move; the branch run of `backup.yml` (AC-5), once the owner approves it.
- Manual: the owner follows `docs/runbooks/restore.md` once, restoring the newest dump into a scratch Neon branch → row counts match the job summary, and the time taken is recorded in the runbook.

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
