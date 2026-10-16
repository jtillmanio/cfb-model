---
id: TASK-024
title: Keep backups in daily, weekly and monthly tiers that expire
status: Ready
depends_on: []
size: M
model: opus
autonomy: attended
ui: false
plan_status: none
planned_at_commit:
---

# TASK-024 — Keep backups in daily, weekly and monthly tiers that expire

## Goal

Backups stop piling up in R2 forever. Recent nights stay restorable day by day, and older weeks and months remain available at a coarser grain, so a problem noticed weeks late can still be rolled back to before it started.

## Context

- Architecture: `docs/02-architecture.md` › Release & operations › Backups (`backups/<UTC date>.dump` in its own bucket); › Hosting & cost plan (R2: 10 GB free); › Non-functional requirements › Backups (recovery point ≤ 24 h, recovery time ≤ 2 h).
- Decisions: D-019 (backup steps), D-109 (object key `backups/<UTC YYYY-MM-DD>.dump`, a same-day re-run replaces it; revisit "dumps outgrow R2's free tier (add pruning)"; this task amends D-109's key), D-092 (RPO/RTO).
- Existing code: `python/db/src/db/backup.py` `object_key()`, which the `dump` command writes to the job output `key`; `.github/workflows/backup.yml` › Upload to R2 (`aws s3 cp` with R2's checksum settings); `python/db/tests/test_backup.py`.
- Why tiers rather than a single "delete after N days" rule: if backups stopped silently, a single age rule would keep deleting until none were left, and a corruption noticed after N days would already be in every remaining dump. The long-lived tiers cap both risks.
- **Tiers** (owner confirmed the numbers 2026-10-16):

  | Prefix | Written when the run's UTC date is | Expires after |
  |---|---|---|
  | `backups/daily/` | every day | 14 days |
  | `backups/weekly/` | a Sunday (the run after Saturday's games) | 90 days |
  | `backups/monthly/` | the 1st of the month | 365 days |

- **Expiry is an R2 lifecycle rule per prefix, set by the owner** in Cloudflare › R2 › the backup bucket › Settings › Object lifecycle rules. The backup's token is Object Read & Write on the bucket and must not be able to change bucket settings, so the workflow never sets or reads the rules.
- **Decide at the plan gate:** how the weekly and monthly copies are made (a second upload, or a server-side `aws s3 cp s3://… s3://…` from the daily object); whether a missed Sunday or 1st is acceptable (proposed: yes; the daily tier still covers the gap, and the failed run is visible in Actions) or the tier is instead "the first good dump of the week/month" (needs a bucket listing); what happens to the flat `backups/<date>.dump` objects written before this task (proposed: left alone, and the owner deletes them by hand once `backups/daily/` has 14 days).
- **Stop and ask:** the backup reads production. Running it on the branch (`gh workflow run backup.yml --ref <branch>`) needs the owner's go-ahead in the session.

## Acceptance criteria

- [ ] AC-1: A tested Python function returns the object keys for a run's UTC date. Unit tests show: 2026-10-16 (a Friday) → `backups/daily/2026-10-16.dump` only; 2026-10-18 (a Sunday) → the daily key plus `backups/weekly/2026-10-18.dump`; 2026-12-01 (a Tuesday) → the daily key plus `backups/monthly/2026-12-01.dump`; 2026-11-01 (a Sunday and the 1st) → all three.
- [ ] AC-2: `backup.yml` writes every key from AC-1 only after the restore check passes, as today. If any write fails, the run fails, and its summary names each key that was and wasn't written.
- [ ] AC-3: An owner-approved branch run goes green, and the bucket shows the dump at the daily key for the run's UTC date (plus the weekly or monthly key when AC-1 says so). The job summary lists every key written.
- [ ] AC-4: `docs/runbooks/restore.md` › Steps › Find the newest dump points to `backups/daily/` first, and says when to reach into `weekly/` or `monthly/` (the damage is older than the daily window). `README.md` › Backups states the tiers and their expiry periods, and that the expiry rules live in the bucket's settings.
- [ ] AC-5: `docs/owner-checklist.md` › Actions has an item giving the exact lifecycle rule for each prefix (prefix, expiry days) from the plan, and `docs/decisions.md` records the key layout and tiers as a new decision that amends D-109.

## Out of scope

- Setting the lifecycle rules from code or the workflow (owner's dashboard setting; the backup token must not manage the bucket).
- Deleting the pre-task flat `backups/<date>.dump` objects (the owner's call).
- Fixing the late start of scheduled runs (TASK-025, TASK-026).
- Changing the schedule, the dump, the restore check or what's backed up.
- Backing up the data lake.

## Files likely touched

- `python/db/src/db/backup.py`: replace `object_key()` with a function that returns the keys for a date; the `dump` command's job outputs.
- `python/db/tests/test_backup.py`: AC-1.
- `.github/workflows/backup.yml`: Upload to R2 writes each key and lists them in the summary.
- `docs/runbooks/restore.md`: AC-4.
- `README.md` › Backups: AC-4.
- `docs/02-architecture.md` › Release & operations › Backups: the key layout and tiers.
- `docs/decisions.md`, `docs/owner-checklist.md`: AC-5.

## Verification

- Automated: `python/db/tests/test_backup.py` (AC-1); the ready gate "Changed workflow run on the branch" for `backup.yml` (owner-approved, AC-3).
- Manual: after the owner adds the lifecycle rules, Cloudflare › R2 › `cfb-backups` › Settings lists one rule per prefix with the agreed days. Fifteen days after the first `daily/` dump, `backups/daily/` holds no object older than 14 days.

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
