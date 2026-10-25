---
id: TASK-028
title: Stop a late fallback run of results and lines repeating the dispatched run
status: Draft
depends_on: [TASK-022]
size: S
model: sonnet
autonomy: attended
ui: false
plan_status: none
planned_at_commit:
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

- [ ] AC-1: Given a `schedule` run of `results.yml` or `lines.yml` that starts 8 hours after a successful dispatched run of the same workflow, when the guard runs, then the job's later steps are skipped and the summary says why (expected: skipped).
- [ ] AC-2: Given a `schedule` run when no dispatched run of that workflow succeeded in the guard's window, when the guard runs, then the job runs as before (expected: runs).

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
