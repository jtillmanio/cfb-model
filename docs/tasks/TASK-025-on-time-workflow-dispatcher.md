---
id: TASK-025
title: Start scheduled workflows on time with an external dispatcher
status: Ready
depends_on: []
size: M
model: opus
autonomy: attended
ui: false
plan_status: none
planned_at_commit:
---

# TASK-025 — Start scheduled workflows on time with an external dispatcher

## Goal

Scheduled jobs start within minutes of their ET time instead of hours late, and stay at the same ET time across daylight-saving changes. The first job it starts is the nightly backup at 03:30 ET; later jobs are added by adding a line to its schedule.

## Context

- **The problem:** GitHub's `schedule` trigger is best effort. GitHub's docs say runs "can be delayed during periods of high loads" and may be dropped. The backup's cron is `30 7 * * *` (07:30 UTC), but its scheduled runs started at 15:13 UTC (2026-10-13), 13:00 (2026-10-14) and 12:47 (2026-10-15): 5–8 hours late. `docs/02-architecture.md` assumes 10–30 minutes. At this lag, TASK-022's `results` job (Sun 06:00 ET) would miss the "predictions out by Sun 10 AM ET" target (D-092), and the backup no longer reliably runs before it.
- Architecture: `docs/02-architecture.md` › Components › 4 Jobs (ET times; the `scores` row's "10–30 min late" assumption); › Hosting & cost plan (Cloudflare is already in use for R2); › Non-functional requirements › Data freshness, Job budget.
- Decisions: D-001 (batch-first jobs in GitHub Actions), D-092 (freshness targets, ≤ 1,500 Actions minutes a month), D-108 (`workflow_dispatch` needs the workflow file on the default branch), D-109 (backup schedule).
- **Proposed approach** (confirm at the plan gate): a Cloudflare Worker with one Cron Trigger (e.g. every 15 or 30 minutes) that holds a table of `{workflow, ET weekday/time}` entries. On each tick it converts now to America/New_York and, for each entry due, calls GitHub's `POST /repos/{owner}/{repo}/actions/workflows/{file}/dispatches` on `main`. Doing the ET conversion in code removes the two-crons-per-slot daylight-saving workaround that TASK-022 would otherwise need. The schedule logic is a pure function (`due(now) → workflows`), unit tested with Vitest.
- **Alternatives to weigh at the plan gate:** a Vercel Cron calling an API route (the Hobby plan runs crons once a day and only "within the hour", and it would put a GitHub token in the app's environment); more GitHub crons at off-peak minutes (still best effort); a GitHub App instead of a fine-grained token (no expiry, more setup).
- **Decide at the plan gate:** the folder for the Worker (e.g. `infra/dispatcher/`) and how it joins the pnpm workspace, lint and typecheck; the tick interval; the token (proposed: a fine-grained personal access token with **Actions: Read and write** on this repository only, stored as a Worker secret); how a failed dispatch is made visible (Worker logs alone aren't watched; TASK-026 adds a GitHub-side fallback for the backup); Cloudflare's free-plan Cron Trigger limit.
- **Size:** about 11 files: one new package (Worker, schedule, tests, config), the workspace wiring and AC-5's doc edits. The owner kept it as one task (2026-10-16).
- **Owner prerequisites:** create the GitHub token and put it in the Worker's secrets; deploy the Worker (`wrangler deploy`). Claude never edits secrets and never deploys.

## Acceptance criteria

- [ ] AC-1: The schedule function is unit tested. Given the backup entry (daily 03:30 ET), it returns `backup.yml` for the ticks at 2026-10-17T07:30Z (EDT) and 2026-11-07T08:30Z (EST), and returns nothing for 2026-11-07T07:30Z and for the ticks either side of 03:30 ET.
- [ ] AC-2: Given a tick on which a workflow is due, the Worker sends one `POST …/actions/workflows/<file>/dispatches` with `{"ref": "main"}` and the token in the `Authorization` header. A non-2xx answer is logged with the status and body and doesn't stop the other due workflows. Unit tests use a stubbed `fetch`.
- [ ] AC-3: The Worker's code passes `pnpm lint`, `pnpm typecheck` and `pnpm test` (its tests run in the same `pnpm test` CI runs). No token or secret value is committed; the token's name appears only in the Worker's config and docs.
- [ ] AC-4: After the owner deploys the Worker, its next 03:30 ET tick starts a `backup` run whose event is `workflow_dispatch` and whose start time is within 5 minutes of 03:30 ET (checked with `gh run list --workflow backup.yml`).
- [ ] AC-5: `README.md` gains a Dispatcher section (what it starts and when, how to add a job, the token and its expiry, how to deploy, where its logs are). `docs/02-architecture.md` › Components › 4 Jobs says jobs are started by the dispatcher and corrects the 10–30-minute delay assumption, and the choice is recorded in `docs/decisions.md`.

## Out of scope

- Changing `backup.yml`'s own `schedule` or adding a fallback (TASK-026).
- Adding the `results`, `lines` or `scores` jobs to the table (TASK-022 adds its jobs when it lands; see its Context).
- A deploy workflow for the Worker (the owner deploys by hand; it rarely changes).
- Backup retention (TASK-024).

## Files likely touched

- `infra/dispatcher/src/index.ts`: the Worker's `scheduled` handler and the dispatch call (new; folder decided at the plan gate).
- `infra/dispatcher/src/schedule.ts`, `infra/dispatcher/src/schedule.test.ts`: the table, `due()`, and AC-1/AC-2 tests (new).
- `infra/dispatcher/wrangler.jsonc`, `infra/dispatcher/package.json`, `infra/dispatcher/tsconfig.json`: Worker config and tooling (new).
- `pnpm-workspace.yaml`, `package.json`: the new package in the workspace and in the root `lint`, `typecheck` and `test` scripts.
- `README.md`, `docs/02-architecture.md`, `docs/decisions.md`: AC-5.

## Verification

- Automated: the schedule and dispatch tests (AC-1, AC-2) inside `pnpm test`; CI green.
- Manual: the owner runs `wrangler dev --test-scheduled` and triggers the scheduled handler with a time when the backup is due → a `backup` run appears in Actions with event `workflow_dispatch` (owner-approved: it reads production). After deploy → AC-4.

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
