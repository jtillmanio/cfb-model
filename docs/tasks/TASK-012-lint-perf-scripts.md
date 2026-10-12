---
id: TASK-012
title: Lint the scripts in scripts/perf
status: Draft
depends_on: []
size: S
model: sonnet
autonomy: attended
ui: false
plan_status: none
planned_at_commit:
---

# TASK-012 — Lint the scripts in scripts/perf

## Goal

`pnpm lint`, and so CI, also lints the Node scripts in `scripts/perf/`.

## Context

- *From #18 (TASK-007):* `scripts/perf/*.mjs` isn't linted: root `pnpm lint` runs `pnpm --dir web lint` (ESLint over `web/` only) and ruff on `python/`. `scripts/perf/` has its own `package.json` and lockfile.
- TASK-008 adds `measure.mjs` to the same folder.
- Keep `.claude/kit.json` › `verify` and the Commands table in `CLAUDE.md` in sync if the lint command changes.

## Acceptance criteria

_To be written when the task moves to Ready._

## Out of scope

- Fixing lint findings beyond what turning the linter on requires.

## Files likely touched

- `package.json` — the root `lint` script
- an ESLint config covering `scripts/perf/` — the plan decides where

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
