---
id: TASK-026
title: Run the backup from the dispatcher with a GitHub-schedule fallback
status: Ready
depends_on: [TASK-024, TASK-025]
size: S
model: sonnet
autonomy: attended
ui: false
plan_status: none
planned_at_commit:
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

- [ ] AC-1: Given a `schedule` run when `backups/daily/<today's UTC date>.dump` already exists, the run's first steps find it and end green without dumping production. The summary says "Already backed up today by run <link or key>; skipped".
- [ ] AC-2: Given a `schedule` run when that object doesn't exist, the run takes the backup as before. A `workflow_dispatch` run always takes the backup, whatever exists (manual re-runs and the dispatcher still replace the day's dump).
- [ ] AC-3: Two owner-approved branch runs show both paths: one after a dump for the day exists (skips, AC-1) and, with the check pointed at a date that has no dump, one that proceeds (AC-2). Each run's summary says which path it took.
- [ ] AC-4: `backup.yml`'s header comment and `README.md` › Backups say the backup is started by the dispatcher at 03:30 ET, that the `schedule` entry is a fallback that skips when the day's dump exists, and the fallback's time.

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
