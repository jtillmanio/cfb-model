---
id: TASK-014
title: Time screen-to-screen taps in the lighthouse workflow
status: Draft
depends_on: [TASK-008]
size: M
model: opus
autonomy: attended
ui: false
plan_status: none
planned_at_commit:
---

# TASK-014 — Time screen-to-screen taps in the lighthouse workflow

## Goal

The Lighthouse PR comment also reports how long a tap from one screen to the next takes to paint (client navigation), not only cold page loads.

## Context

- *From TASK-008 (PR #29):* the owner's `ledger` project runs a tap → next-paint runner beside Lighthouse (`ledger/scripts/perf/measure.mjs`: puppeteer-core on the same throttling profile, click a link, wait for the `<h1>` to change and two frames, time it, and record any `/api/*` request the tap makes). TASK-008 measures cold loads only: neither `docs/02-architecture.md` › Performance checks nor D-101 plans a tap runner, and with one signed-in screen (`/teams`) there is no screen-to-screen tap to time.
- Plan it when a second signed-in screen ships (This Week, M5.6, is the first pair with `/teams`). It would add `puppeteer-core` to `scripts/perf/package.json`, a `tap` field to `scripts/perf/routes.mjs`, and a "Reported, never gated" row to the comment; 02 › Performance checks and D-101 would need the owner's approval to change.
- *Blocked on M5.6 (This Week),* which has no task file yet. `depends_on` lists only TASK-008 because it takes task IDs; add M5.6's ID when `/new-task` creates it, and don't move this task to Ready before then.
- *From TASK-027 (PR #77):* Lighthouse now runs twice per PR (D-125): a gated `fixture` job that builds and serves the app on the seeded test DB inside the job, and a reported-only per-route `measure` job on the preview. Time taps on the fixture build (the `fixture` job in `.github/workflows/lighthouse.yml`), where the data holds still, and show them in the fixture comment; the preview run can add its own reported-only timings if wanted. The fixture job measures every route in one job, so a tap runner there needs no matrix.

## Acceptance criteria

_To be written when the task moves to Ready._

## Out of scope

- Gating on tap timings: timings are reported, never gated (02 › Performance checks).

## Files likely touched

- `scripts/perf/measure.mjs`, `scripts/perf/routes.mjs`, `scripts/perf/lib/perf.mjs`, `scripts/perf/package.json`
- `web/lib/perf.test.ts`
- `docs/02-architecture.md` › Performance checks

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
