---
id: TASK-026
title: Run the backup from the dispatcher with a GitHub-schedule fallback
status: Done
depends_on: [TASK-024, TASK-025]
size: M
model: sonnet
autonomy: attended
ui: false
plan_status: approved
planned_at_commit: d88ff01
---

# TASK-026 — Run the backup from the dispatcher with a GitHub-schedule fallback

## Goal

The nightly backup runs at 03:30 ET from the dispatcher. If the dispatcher ever stops, GitHub's own schedule still takes that day's backup, late but not missed, and a day never gets two backups' worth of work.

## Context

- Depends on TASK-024 (the `backups/daily/<UTC date>.dump` key, which the fallback checks for) and TASK-025 (the dispatcher, which starts `backup.yml` by `workflow_dispatch` at 03:30 ET).
- Why keep a fallback: a dispatcher that stops (expired token, Worker error, Cloudflare outage) starts no run, so nothing fails in Actions and nobody is told. The GitHub `schedule`, however late, catches that.
- Existing code: `.github/workflows/backup.yml` (`schedule: 30 7 * * *`, `workflow_dispatch`, `concurrency: backup`); Upload to R2 (R2 env and checksum settings to reuse for the check); README › Backups.
- Decisions: D-109 (schedule), D-092 (recovery point ≤ 24 h), and the decisions TASK-024 and TASK-025 record.
- **Decide at the plan gate:** the fallback's cron (proposed: a few hours after 03:30 ET, e.g. `0 12 * * *`; even 8 hours late it starts on the same UTC date as that night's dispatched run); how the check reads R2 (`aws s3api head-object` with the backup token, before the dump step so a skipped run costs under a minute).
- **Stop and ask:** the backup reads production. Running it on the branch needs the owner's go-ahead in the session.
- *From TASK-024 (PR #52):* the day's dump is `backups/daily/<UTC date>.dump`, the first key `object_keys(date)` returns in `python/db/src/db/backup.py`. The `dump` step's `date` output is the run's UTC date (it replaces the `key` output).
- *From TASK-022 (PR #62), open question for the plan:* TASK-022 adds `.github/actions/skip-if-dispatched`, which skips a `schedule` run when a `workflow_dispatch` run of the same workflow succeeded in the last 6 hours (`gh run list`, `actions: read`). Should the backup's fallback reuse it, or keep the check on the day's dump in R2?
- *From TASK-025 (PR #68):* the dispatcher is live in code: `SCHEDULE` in `infra/dispatcher/src/index.ts` starts `backup.yml` daily at 03:30 ET (D-122). Three places name the interim double run (the dispatched run plus `backup.yml`'s own `30 7 * * *`) and say "until TASK-026": README › Dispatcher (the paragraph under the table), README › Backups (the opening sentence) and D-122. Update all three to describe the fallback.

## Acceptance criteria

- [x] AC-1: Given a `schedule` run when `backups/daily/<today's UTC date>.dump` already exists, the run's first steps find it and end green without dumping production. The summary says "Already backed up today by run <link or key>; skipped".
- [x] AC-2: Given a `schedule` run when that object doesn't exist, the run takes the backup as before. A `workflow_dispatch` run always takes the backup, whatever exists (manual re-runs and the dispatcher still replace the day's dump).
- [x] AC-3: Two owner-approved branch runs show both paths: one after a dump for the day exists (skips, AC-1) and, with the check pointed at a date that has no dump, one that proceeds (AC-2). Each run's summary says which path it took.
- [x] AC-4: `backup.yml`'s header comment and `README.md` › Backups say the backup is started by the dispatcher at 03:30 ET, that the `schedule` entry is a fallback that skips when the day's dump exists, and the fallback's time.
- [x] AC-5: README › Dispatcher no longer mentions TASK-026 or a double backup run (the paragraph under the table, What it doesn't do, Logs and failures), and D-109 and D-122 each end "Amended by D-128", a new decisions-log row that records the fallback. (Added at the plan gate, owner-approved 2026-10-25.)

## Out of scope

- The dispatcher itself (TASK-025) and retention tiers (TASK-024).
- Alerts when both the dispatcher and the fallback miss a day (GitHub already emails on a failed scheduled run; a "no backup for 2 days" alert is separate).
- Fallbacks for TASK-022's jobs.

## Files likely touched

- `.github/workflows/backup.yml`: the fallback cron and the "already backed up today" check.
- `README.md` › Backups: AC-4.
- `docs/decisions.md`: amend D-109's schedule (or TASK-025's decision) with the fallback.

## Verification

- Automated: the ready gate "Changed workflow run on the branch" for `backup.yml`, both paths (AC-3).
- Manual: on the first day after merge, `gh run list --workflow backup.yml` shows a `workflow_dispatch` run near 03:30 ET that uploaded, and a `schedule` run later that day that skipped.

## Follow-ups

_Work noticed during this task and deliberately left out. Each bullet ends `→ <path> § <section>` (where it was placed) or `→ not tracked: <reason>`. See `.claude/skills/track-follow-ups/classify.md`; the PR's Follow-ups section is copied from here._

- `.github/actions/skip-if-dispatched` (TASK-022) skips a `schedule` run only when a dispatched run succeeded in the last 6 hours; GitHub has started scheduled runs 5–8 hours late, so a late fallback of `results.yml` or `lines.yml` runs the job a second time (harmless upserts, but a few CFBD calls). Widen the window or check what the job produced → docs/tasks/TASK-028-widen-skip-if-dispatched-window.md (new, Draft); stub in docs/08-tasklist.md § M2 (M2.9)

## Plan

Approved 2026-10-25 at `d88ff01`.

**Open question from TASK-022, settled:** the fallback checks R2 for `backups/daily/<UTC date>.dump`, not `.github/actions/skip-if-dispatched`. The guard's 6-hour window fails when GitHub starts the fallback 5–8 hours late (it would run a second full backup); the dump check asks whether today's backup exists, so a late start doesn't matter, and a hand-run backup counts too. The R2 token (Object Read & Write) can already `HeadObject`.

**Steps**
1. Tests first, in `python/db/tests/test_backup.py` (a TASK-026 section), each failing on the old code:
   - a `workflow_dispatch` run without `--date` outputs `skip=false` and makes no `aws` call (AC-2);
   - a `schedule` run whose daily dump exists (`head-object` exits 0) outputs `skip=true`, calls `aws s3api head-object` on `backups/daily/<date>.dump` with the R2 endpoint, and the summary says "Already backed up today (<date>) by `backups/daily/<date>.dump`; skipped." (AC-1);
   - a `schedule` run whose dump is missing (non-zero exit, `Not Found`/404) outputs `skip=false` and says it is taking the backup (AC-2);
   - any other R2 error outputs `skip=false` with a warning, so the fallback still backs up;
   - `--date` makes a `workflow_dispatch` run behave as the fallback (the AC-3 test hook);
   - workflow shape: a `fallback` job runs before `backup`, which has `needs: fallback` and `if: needs.fallback.outputs.skip != 'true'`; the `schedule` cron is `0 12 * * *`; the dispatch input `check_date` reaches the command; R2 secrets reach the check only through `env:`.
2. `python/db/src/db/backup.py`: `python -m db backup fallback --event E [--date D]`. A pure decision for the `head-object` result, then the command: writes `skip=` to `$GITHUB_OUTPUT` and one summary line. Date defaults to `run_date(now)`.
3. `.github/workflows/backup.yml`: a `fallback` job (checkout, setup-uv, the command with the R2 env and checksum settings) that always runs; the `backup` job `needs` it and is skipped on `skip == 'true'` (no `always()`, so the existing "nothing runs past a failure" test still holds). Cron `0 12 * * *` (08:00 EDT, 07:00 EST; 8 hours late it is still the dispatched run's UTC date). A `workflow_dispatch` input `check_date` (empty by default) tests the fallback path on a branch. Rewrite the header comment (AC-4).
4. `README.md`: › Backups opening sentence (AC-4); › Dispatcher: the paragraph under the table, What it doesn't do, Logs and failures (AC-5).
5. `docs/decisions.md`: D-128 (the fallback job, its cron, the R2 check, `check_date`, `skip-if-dispatched` rejected and why); append "Amended by D-128" to D-109 and D-122 (AC-5). Take the ID from `next-id.ps1` again before writing.
6. Close-out: create TASK-028 (Draft) for the follow-up above.

**Files:** `.github/workflows/backup.yml`, `python/db/src/db/backup.py`, `python/db/tests/test_backup.py`, `README.md`, `docs/decisions.md` (and this file; TASK-028 at close-out). Size raised S → M: Python plus CI, 5 files.

**Test strategy:** AC-1, AC-2: the pytest cases in step 1. AC-3: two owner-approved branch runs, which are also the "Changed workflow run on the branch" ready gate: `gh workflow run backup.yml --ref <branch> -f check_date=<today UTC>` after the day's dump exists (skips; never reads production), then `-f check_date=2000-01-01` (proceeds: a full backup that reads production and replaces today's dump). AC-4, AC-5: test-runner on the text, plus spec-reviewer.

**AC-2 reading:** a dispatch with `check_date` set runs the fallback's check (the test hook AC-3 needs); without it, a dispatch always backs up.

**Risks:** the check job adds about 20 s to every run (uv setup). A `head-object` error other than 404 proceeds with the backup, so a broken R2 token fails at the upload as it does today.

## Review log

Verify R1 PASS | Audit R1 PASS (11 new tests all fail on main) | Spec R1 APPROVE (AC-3 pending until the branch runs; nit taken: fallback time in the header) | Branch runs: run 40168170423 (`check_date=2026-10-24`, skipped) and run 40168212780 (`check_date=2000-01-01`, backed up)

## Blocked

_Only if status is Blocked: what failed, what was tried, best hypothesis, decision needed._

## Metrics

- Verify rounds: 1
- Review rounds: 1
- First-pass AC FAILs: 0
- Plan revisions after approval: 0
