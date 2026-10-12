---
id: TASK-006
title: Add the nightly backup workflow with restore verification
status: Review
depends_on: []
size: M
model: opus
autonomy: attended
ui: false
plan_status: approved
planned_at_commit: 6d4e50b
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

- [x] AC-1: Row-count comparison is a tested Python function: given per-table counts from production and from the restored database, it passes when they match and fails naming each table that differs, including a table present on one side only. Unit tests cover match, one mismatch and a missing table.
- [x] AC-2: `.github/workflows/backup.yml` runs on a nightly `schedule` and `workflow_dispatch`, installs the PostgreSQL client for `PG_MAJOR` from PGDG, and reads `PG_MAJOR` from the same single source as `ci.yml` (no second literal `18` in either workflow).
- [x] AC-3: The workflow runs in order: `pg_dump` (fails on a non-zero exit or an empty file) → restore into a `postgres:${PG_MAJOR}` container → apply views → query each view → compare row counts → upload to R2 `backups/`. Any failed step stops the run before the upload, so a bad dump is never stored.
- [x] AC-4: R2 credentials and `BACKUP_DATABASE_URL` appear in no workflow under `.github/workflows/` except `backup.yml`, reach steps only through `env:`, and the workflow reads production's database only through `BACKUP_DATABASE_URL`; the workflow's `permissions` are `contents: read` or narrower. _(Reworded by the owner 2026-10-12 at spec review R1: docs name the secrets, and Decision D reads production's `/api/py/health`.)_
- [x] AC-5: An owner-approved run on the branch goes green, uploads one dump to R2 `backups/`, and its job summary lists each table's row count on both sides and the dump size. _(Run 38303172843, 2026-10-12: green; uploaded `backups/2026-10-12.dump`, 2,446 bytes; production had 0 tables, so the counts table is empty and "Row counts match" is trivially true. A non-empty comparison comes with the first nightly run after the first real release.)_
- [x] AC-6: `docs/runbooks/restore.md` gives numbered steps to restore the latest dump into a new Neon branch, point production at it, apply views, and check `/api/py/health`, with how to find the newest dump and the 2-hour recovery-time target.

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

## Follow-ups

- Candidate decision: decisions A–E below (`PG_MAJOR` in the `start-postgres` action, snapshot-matched row counts, object name and schedule, views from production's commit, what "view tests" means); D-099 marked "Amended by D-109" → docs/decisions.md § D-109 (approved at plan)
- Tick Phase 0's `PG_MAJOR` and `backup` items (this task's own). The Accounts item says R2 isn't created, but the backup bucket `cfb-backups` and its secrets exist; its partial note says so, and its box stays unticked (the lake bucket for the Phase 1 raw writer isn't there yet; spec review R1) → docs/06-roadmap.md § Phase 0 (approved at plan)
- Architecture says the restore goes into "a Postgres service container"; it's a container started in a step by the `start-postgres` action. The same wording in § Environments & databases, § Testing strategy and § Walking skeleton, and § Release & operations' "Only the backup workflow gets write permissions" (it is `contents: read`; R2 is written with a bucket-scoped token) are fixed in the same edit (widened by the owner at spec review R1) → docs/02-architecture.md § Release & operations (approved at plan)
- Confirm the role in `BACKUP_DATABASE_URL` (`backup_reader`) is read-only and can read every table and sequence, now and future: `GRANT pg_read_all_data TO backup_reader` and nothing that writes (schema review R1: per-table grants miss new tables) → docs/owner-checklist.md § Actions (approved at plan)
- CLAUDE.md's Status line still listed the `backup` workflow and R2 as not built; the backup workflow is built and only the R2 lake bucket is missing → CLAUDE.md § Status (approved at close-out)
- `python/db/views/README.md` lists where views are re-applied; the backup's restore check also applies and queries them → not tracked: done in this PR (plan revision)
- Production is behind Vercel Authentication; the release workflow's smoke step calls health and `/api/py/teams` without the `x-vercel-protection-bypass` header, so the first real release would fail at smoke (found by this task's branch run R1) → docs/tasks/TASK-013-release-smoke-bypass.md (new, Draft)
- Branch run R2: `PRODUCTION_URL`'s health named `ad36d65` (the #26 merge, minutes old) although no real release has run, so `main` builds appear to reach the production URL without the release workflow (D-018); production's database also has no tables yet → docs/owner-checklist.md § Actions
- The 2 Alembic `path_separator` DeprecationWarnings in pytest predate this task → not tracked: unrelated to this task; harmless until an Alembic major removes the old option

## Plan

Approved 2026-10-12 (all of A–E as recommended; D = production's health commit).

**Decisions at the gate**
- A. `PG_MAJOR` is set once, in a composite action `.github/actions/start-postgres/action.yml`: it exports `PG_MAJOR` to `$GITHUB_ENV`, pulls `postgres:$PG_MAJOR` with CI's registry fallback loop, and starts the container. `ci.yml` and `backup.yml` both use it; neither has a literal major. Amends D-099.
- B. `python -m db backup dump` opens a `REPEATABLE READ READ ONLY` transaction, takes `pg_export_snapshot()`, runs `pg_dump -Fc --snapshot=<id>`, and counts every table in that same transaction, so production's counts match the dump exactly.
- C. Object `backups/<UTC YYYY-MM-DD>.dump` (a same-day re-run replaces it); cron `30 7 * * *` (03:30 ET).
- D. Views re-applied are those of the commit production serves (`commit` from `PRODUCTION_URL/api/py/health`), checked out into `target/` as the release does, so a merged-but-unreleased migration can't break the nightly backup. If health doesn't answer, the run fails loudly. Revised after branch run R1 (owner-approved): the call sends `x-vercel-protection-bypass` from `VERCEL_AUTOMATION_BYPASS_SECRET`, since production is behind Vercel Authentication.
- E. "View tests" = every view in the restored database answers a full `SELECT` without error; zero views passes.

**Steps**
0. Stub `backup.yml` (`workflow_dispatch` only, no-op) lands on `main` first in its own PR, so the branch's file can run with `gh workflow run backup.yml --ref <branch>` (as PR #23 did for release, D-108).
1. `python/db/src/db/backup.py`: pure `compare_counts` (names each differing or one-sided table), `check_dump` (non-zero exit or empty file), summary rendering; `count_rows(conn)` (base tables outside system schemas), `query_views(url)`; commands `dump` and `verify` (refuses a non-local restore URL; applies views, queries each, compares counts, writes the job summary with both sides' counts and the dump size). Non-zero exit on any failure.
2. `python/db/src/db/migrate.py`: `apply_views(url, views_dir=VIEWS_DIR)`. `__main__.py` registers `backup`.
3. `.github/workflows/backup.yml`: `schedule` + `workflow_dispatch`, `permissions: contents: read`, `concurrency: backup`, 15 min. One job: checkout → start Postgres (action; it exports `PG_MAJOR`, which the client step needs, so it runs first: noted at spec review R1) → PGDG client for `$PG_MAJOR` (its `bin` first on `PATH`) → `backup dump` → production's commit's views into `target/` → `pg_restore --no-owner --no-privileges --exit-on-error` → `backup verify` → `aws s3 cp` to R2. Secrets only through `env:`; a failed step stops before the upload.
4. `docs/runbooks/restore.md` (AC-6); README › Backups (secrets, run, read a failed run).

**Files**: `.github/workflows/backup.yml` (new), `.github/actions/start-postgres/action.yml` (new; not in Files likely touched), `.github/workflows/ci.yml`, `python/db/src/db/backup.py` (new), `python/db/src/db/__main__.py`, `python/db/src/db/migrate.py` (not in Files likely touched), `python/db/tests/test_backup.py` (new), `docs/runbooks/restore.md` (new), `README.md`. Nine files, two of them docs, no schema or UI: kept whole (approved). Plan revision at close-out (owner-approved): `python/db/views/README.md` names the backup's restore check among the places views are re-applied.

**Test strategy** (`python/db/tests/test_backup.py`)
- AC-1: match; one mismatch names the table and both counts; production-only and restored-only tables named; `count_rows` on the migrated test DB includes `alembic_version`.
- AC-2: `ci.yml` and `backup.yml` contain no `PG_MAJOR:` literal or `postgres:<n>` and both use the action; the action sets `PG_MAJOR`.
- AC-3: `check_dump` refuses a non-zero exit and an empty file; `verify` refuses a non-local URL; step order by review and the branch run.
- AC-4: R2 secrets and `BACKUP_DATABASE_URL` appear only in `backup.yml`, only on `NAME: ${{ secrets.X }}` env lines; permissions by review.
- AC-5: owner-approved branch run. AC-6: the runbook, by review.

## Review log

- Verify R1 PASS → R2 PASS (after the review fixes) | Audit R1 CHANGES (AC-3 order, AC-4 production-only UNPROVEN) → R2 PASS | Spec R1 CHANGES (roadmap follow-up overreach; health "unknown" commit; AC-4 SPEC GAP, reworded by the owner) → R2 APPROVE (conditional on AC-5's branch run) | Schema R1 CHANGES (MAJOR: runbook `--clean` restore into the damaged branch; 5 MINOR) → R2 APPROVE | UI n/a
- AC-5 branch run R1 FAIL: the dump from production worked, but `/api/py/health` answered with Vercel's login page (production is behind Vercel Authentication). The owner chose to send the `x-vercel-protection-bypass` header (plan revision) → R2 PASS (run 38303172843: every step green, one dump uploaded; production had 0 tables and served `ad36d65`, the newest `main` commit, though no real release has run).

## Blocked

_Only if status is Blocked: what failed, what was tried, best hypothesis, decision needed._

## Metrics

- Verify rounds: 2 (R1 PASS; R2 PASS after the review fixes)
- Review rounds: 2
- First-pass AC FAILs: 0 (AC-5 pending its branch run)
- Plan revisions after approval: 2 (the `views/README.md` line; the health call's bypass header after branch run R1. The start-postgres/client step order was a note, not a change)
