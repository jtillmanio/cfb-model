---
id: TASK-075
title: Create the owner's contest in production
status: Draft
depends_on: [TASK-070]
size: S
model: sonnet
autonomy: attended
ui: false
plan_status: none
planned_at_commit:
---

# TASK-075 — Create the owner's contest in production

## Goal

The owner can create their Splash contest in the production database, so the contest import and the Contest page have a contest to work on.

## Context

- *From TASK-070 (PR #161):* production starts with no `users` row and no `contests` row. Nothing creates a contest: "Add contest" isn't designed and M8.8's Settings › Contests is read-only. Every import route 404s until one exists (the routes act only on the caller's own live contest, D-172). The fixture creates the test DB's contest (`engine/fixture.py` `_seed_contest`). The owner approved this as a new task at TASK-070's plan gate (2026-11-15).
- Data model: `docs/03-data-model.md` › Your data › `users`, `contests` (UQ `(user_id, name)` WHERE `deleted_at IS NULL`; `rules` a validated `ContestRules`).
- Decisions: D-170 (`users.github_id` is the token's `sub`; no migration seeds the real account), D-113 (`SPLASH_PRESET` in `engine/core/contest_rules.py`), D-089, D-015 (only workflows touch production; Claude never runs anything against it).
- The owner's GitHub id is the `sub` the API token carries. It must not be committed (D-170's reason: a personal id in git).
- Open question for the plan: does the command run from the owner's machine against production (as `engine ingest nflverse --target …` does for dev and test, but production is release-workflow only), or as a manual `workflow_dispatch` job with the id as an input? Either way Claude only builds it; the owner runs it.

## Acceptance criteria

- [ ] AC-1: `engine contest add --github-id <id> --name "Splash work league" --platform splash --season 2026 --target test` upserts the `users` row by `github_id` and inserts one live contest with `SPLASH_PRESET`'s rules. Run again, it inserts nothing and says the contest exists (test).
- [ ] AC-2: The rules stored validate as `ContestRules` and equal `SPLASH_PRESET` (test).
- [ ] AC-3: The command refuses a `--github-id` that isn't a positive integer, and no GitHub id appears in any committed file (test, plus a grep in review).
- [ ] AC-4: The way the owner runs it against production is written in the **Owner checklist** under Actions, with the exact command or workflow, and the plan's choice is recorded in a decision.

## Out of scope

- An "Add contest" screen or API route (not designed).
- Editing or deleting a contest (Settings › Contests is read-only, M8.8).
- More than one user.

## Files likely touched

- `python/engine/src/engine/cli.py` — the `contest add` command
- `python/engine/src/engine/contests.py` (or similar) — the upserts
- `python/engine/tests/test_contest_add.py` — AC-1 to AC-3
- `docs/owner-checklist.md` — the production step
- `docs/decisions.md` — how it reaches production

## Verification

- Automated: `uv --directory python run pytest engine/tests/test_contest_add.py`
- Manual: on the test DB, run the command twice → expected: one contest, the second run reports it exists.

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
