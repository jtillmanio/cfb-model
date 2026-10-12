---
id: TASK-013
title: Send the Vercel bypass header from the release smoke test
status: Draft
depends_on: []
size: S
model: sonnet
autonomy: attended
ui: false
plan_status: none
planned_at_commit:
---

# TASK-013 — Send the Vercel bypass header from the release smoke test

## Goal

A real release's smoke step reaches production's `/api/py/health` and `/api/py/teams` past Vercel Authentication, so it checks the app rather than Vercel's login page.

## Context

- *From TASK-006 (PR #27):* production's domain (`PRODUCTION_URL`) is behind Vercel Authentication: an unsigned `GET /api/py/health` answers 302 to `vercel.com/sso-api`, and following it gives Vercel's login page with a 200. TASK-006's backup failed on that in its first branch run; it now sends `x-vercel-protection-bypass` from `VERCEL_AUTOMATION_BYPASS_SECRET` (D-109). The release workflow's smoke step (`python/db/src/db/release.py` `fetch_health`, called by `release smoke` in `.github/workflows/release.yml`) sends no header. A real release has never run (only the TASK-005 dry run, which skips smoke), so this hasn't failed yet.
- Without the header, health never parses, so smoke fails every attempt for ~5 minutes after promoting. And the unsigned `/api/py/teams` check (D-107, D-108) would see Vercel's 302 instead of the API's 401, so it couldn't prove the API guard anyway.
- `docs/02-architecture.md` § Auth already says automation calling production sends the `x-vercel-protection-bypass` header when protection covers it. The secret exists (repository secret, shared with the Lighthouse job, D-101).
- The bypass header gets past Vercel's protection only: the API's own JWT guard still answers 401 to an unsigned `/api/py/teams`, which is what smoke must keep asserting.

## Acceptance criteria

_To be written when the task moves to Ready._

## Out of scope

- Changing Vercel's Deployment Protection settings.
- The backup workflow's health call (done in TASK-006).

## Files likely touched

- `python/db/src/db/release.py` — `fetch_health` sends the header when the secret is set
- `.github/workflows/release.yml` — the smoke step's `env:`
- `python/db/tests/test_release.py`
- `README.md` › Releasing — the secret in "What it needs"

## Verification

- Automated: _to be written_
- Manual: _to be written_

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
