---
id: TASK-028
title: Stop a late fallback run of results and lines repeating the dispatched run
status: Done
depends_on: [TASK-022]
size: S
model: sonnet
autonomy: attended
ui: false
plan_status: approved
planned_at_commit: 74883d9
---

# TASK-028 — Stop a late fallback run of results and lines repeating the dispatched run

## Goal

A GitHub `schedule` fallback of `results.yml` or `lines.yml` that starts hours late does nothing when the dispatcher's run of the same job already succeeded, so a late fallback never repeats the job.

## Context

- *From TASK-026 (PR #84):* `.github/actions/skip-if-dispatched` (TASK-022) skips a `schedule` run only when a `workflow_dispatch` run of the same workflow succeeded in the last 6 hours. GitHub has started scheduled runs 5–8 hours late (D-122), so a late fallback can fall outside that window and run the job a second time. The upserts are harmless, but it spends a few CFBD calls (the call budget, D-027).
- TASK-026 settled the same question for the backup differently (D-128): its fallback asks R2 whether the day's dump exists, not whether a dispatched run succeeded recently. `results` and `lines` have no single artifact per day to ask about, so the choice here is open: widen the window, or check what the job produced.
- **Decide at the plan gate:** the window (or the output to check), and whether it differs per workflow (`lines.yml` runs five times a week; a window long enough to cover an 8-hour lag can swallow the next slot's own fallback).

## Acceptance criteria

Each item names an observable result and an expected value or state.

- [x] AC-1: Given a `schedule` run of `results.yml` or `lines.yml` that starts 8 hours after a successful dispatched run of the same workflow, when the guard runs, then the job's later steps are skipped and the summary says why (expected: skipped).
- [x] AC-2: Given a `schedule` run when no dispatched run of that workflow succeeded in the guard's window, when the guard runs, then the job runs as before (expected: runs).

## Out of scope

- The backup (TASK-026) and the dispatcher itself (TASK-025).

## Files likely touched

- `.github/actions/skip-if-dispatched/action.yml`: the window or the check.
- `.github/workflows/results.yml`, `.github/workflows/lines.yml`: only if the check changes.

## Verification

- Automated: tests of the guard's decision, where TASK-022 put them.
- Manual: run each changed workflow on the branch for both paths.

## Follow-ups

_Work noticed during this task and deliberately left out. Each bullet ends `→ <path> § <section>` (where it was placed) or `→ not tracked: <reason>`. See `.claude/skills/track-follow-ups/classify.md`; the PR's Follow-ups section is copied from here._

## Plan

Approved by the owner in the session on 2026-10-25, at 74883d9.

**Decision (the plan-gate question):** don't widen the window; anchor it to the slot. A `schedule` run knows which cron fired it (`github.event.schedule`). The guard takes that cron's latest UTC firing at or before now as the **slot** and skips when a `workflow_dispatch` run of the same file succeeded at or after **slot - 3 h**. Every dispatcher time is 1-2 h before its fallback cron (ET to UTC), so 3 h always reaches it, and a late start no longer moves the window. One rule for both workflows: the Fri 01:00 UTC `lines` fallback (for Thu 19:00 ET) looks back only to Thu 22:00 UTC, so it never counts that morning's 08:00 ET run. Rejected: a fixed 12 h window (lets the morning run cover for a failed evening run), and checking what landed in production (gives the guard production database access).

**Steps**
1. `python/engine/src/engine/fallback.py` (new, standard library only): `slot(cron, now)` is the latest UTC time at or before `now` matching the cron's minute and hour (a start more than 24 h late gives a later slot, so the job runs); `decide(event, cron, now, dispatched_at)` returns skip or run and one summary line; `main` calls `gh run list --event workflow_dispatch --status success --json createdAt` and writes `skip=` and the summary line.
2. `python/engine/src/engine/cli.py`: an `engine fallback --event --schedule --workflow --summary` subcommand.
3. `.github/actions/skip-if-dispatched/action.yml`: run `uv --directory python run engine fallback`. In `results.yml` and `lines.yml`, move `setup-uv` above the guard, running always (about 10 s with a warm cache when the guard skips).
4. Both workflows: a `fallback_cron` dispatch input, empty by default (the dispatcher sends none). When set, a dispatched run takes the fallback path as if that cron had fired, so both paths run on the branch (as D-128's `check_date`).
5. Docs: README › Jobs (the "6 hours" text), the workflows' header comments, and a decision amending D-123's guard (ID from `next-id.ps1`; "Amended by" on D-123).

**Files (9):** `python/engine/src/engine/fallback.py` (new), `python/engine/src/engine/cli.py`, `python/engine/tests/test_fallback.py` (new), `python/engine/tests/test_jobs.py` (`setup-uv` before the guard), `.github/actions/skip-if-dispatched/action.yml`, `.github/workflows/results.yml`, `.github/workflows/lines.yml`, `README.md`, `docs/decisions.md`. Not in "Files likely touched": the Python files, README and the decisions log.

**Test strategy** (`python/engine/tests/test_fallback.py`)
- AC-1: `results` cron `0 12 * * 0,1`, a dispatched success at Sun 10:00Z, the guard at 18:00Z (8 h later): skip, and the summary says why (fails on the old 6 h rule). Also `lines` at Fri 01:00 UTC.
- AC-2: no success since slot - 3 h: run; a success just before the window: run; Thursday morning's run seen by the Fri 01:00 fallback: run; a `workflow_dispatch` event: always run.
- Manual: run each workflow on the branch with `fallback_cron` set (skipped, since today's dispatched run counts) and without it (the real job runs and writes production, about 6 and 2 CFBD calls, as TASK-022's branch runs did).

**Risks:** a guard that can't reach `gh` fails the run, as it does today.

**Follow-ups:** none found at planning.

## Review log

Verify R1 PASS | Audit R1 CHANGES (job step gating untested) → R2 PASS | Spec R1 CHANGES (D-123 edited inline; CLI forwarding untested) → fixed, no re-run (docs and one added test) | UI n/a | Schema n/a

## Blocked

_Only if status is Blocked: what failed, what was tried, best hypothesis, decision needed._

## Metrics

- Verify rounds: 1 (plus a final run on the fixes)
- Review rounds: 1 (audit 2)
- First-pass AC FAILs: 0
- Plan revisions after approval: 0
