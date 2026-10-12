---
id: TASK-011
title: Add the test that forbids <Link> to /api/
status: Draft
depends_on: []
size: S
model: sonnet
autonomy: attended
ui: false
plan_status: none
planned_at_commit:
---

# TASK-011 — Add the test that forbids <Link> to /api/

## Goal

A test fails whenever web source renders a Next.js `<Link>` to anything under `/api/`, so the rule in `.claude/rules/web.md` is enforced, not only stated.

## Context

- *From #18 (TASK-007):* `.claude/rules/web.md` says "Never use `<Link>` to anything under `/api/`, because prefetch runs the handler. Use a plain `<a>`; a test enforces this", but no such test exists. `ledger` has one to borrow from: `no-prefetched-handlers.test.ts`.
- Rules: `.claude/rules/web.md`.
- Existing tests: Vitest files beside the code in `web/lib/*.test.ts`.

## Acceptance criteria

_To be written when the task moves to Ready._

## Out of scope

- Changing any existing link or route.

## Files likely touched

- `web/lib/no-prefetched-handlers.test.ts` (or wherever the plan puts it) — the new test

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
