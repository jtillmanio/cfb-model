---
id: TASK-010
title: Let the ui-verifier sign in to the local dev server
status: Draft
depends_on: []
size: S
model: sonnet
autonomy: attended
ui: false
plan_status: none
planned_at_commit:
---

# TASK-010 — Let the ui-verifier sign in to the local dev server

## Goal

The ui-verifier agent can open signed-in screens on the local dev server, so UI tasks get browser verification beyond `/login`. Production keeps GitHub as its only way in.

## Context

- Found during the kit 2.6 upgrade (`chore/kit-2.6`): GitHub sign-in shipped in TASK-001, but `ui.auth` in `.claude/kit.json` is still null, so the ui-verifier stops at `/login`. `.claude/project/ui-verifier.md` § Sign-in now tells it to report signed-in criteria as NOT RUN until this lands.
- Architecture: `docs/02-architecture.md` § Test-only sign-in and clock (the e2e mint lives in the Playwright fixtures, never in `web/` source); § Performance checks (the Lighthouse job mints with the preview `AUTH_SECRET`, `scripts/perf/mint-session.mjs`).
- Decisions: D-090 (e2e mints a session cookie), D-012 (each environment has its own `AUTH_SECRET`), D-101, D-102.
- The kit's `ui.auth` is `{ loginPath, envFile, secretVar, steps }`, and its steps type a secret into a sign-in form. A minted cookie doesn't fit that shape, so the plan must choose between a dev-only route or form that never ships to production, and a mint the agent runs before it opens the browser (via `.claude/project/ui-verifier.md`). Either way, a decision row records the choice.
- Open questions for the plan: which `.env.local` variables the mint may read (`AUTH_SECRET`, `AUTH_ALLOWED_GITHUB_ID`), and how a test proves the mechanism can't open production.

## Acceptance criteria

_To be written when the task moves to Ready._

## Out of scope

- Sign-in on Vercel previews (D-102).
- Any change to production sign-in.

## Files likely touched

- `.claude/kit.json` — `ui.auth`, or leave null if the mint runs outside it
- `.claude/project/ui-verifier.md` — § Sign-in
- `docs/decisions.md` — the new decision

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
