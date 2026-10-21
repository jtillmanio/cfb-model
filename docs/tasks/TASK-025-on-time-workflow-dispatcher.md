---
id: TASK-025
title: Start scheduled workflows on time with an external dispatcher
status: Review
depends_on: []
size: M
model: opus
autonomy: attended
ui: false
plan_status: approved
planned_at_commit: 1bf71ef
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

- [x] AC-1: The schedule function is unit tested. Given the backup entry (daily 03:30 ET), it returns `backup.yml` for the ticks at 2026-10-17T07:30Z (EDT) and 2026-11-07T08:30Z (EST), and returns nothing for 2026-11-07T07:30Z and for the ticks either side of 03:30 ET.
- [x] AC-2: Given a tick on which a workflow is due, the Worker sends one `POST …/actions/workflows/<file>/dispatches` with `{"ref": "main"}` and the token in the `Authorization` header. A non-2xx answer is logged with the status and body and doesn't stop the other due workflows. Unit tests use a stubbed `fetch`.
- [x] AC-3: The Worker's code passes `pnpm lint`, `pnpm typecheck` and `pnpm test` (its tests run in the same `pnpm test` CI runs). No token or secret value is committed; the token's name appears only in the Worker's config and docs.
- [ ] AC-4: After the owner deploys the Worker, its next 03:30 ET tick starts a `backup` run whose event is `workflow_dispatch` and whose start time is within 5 minutes of 03:30 ET (checked with `gh run list --workflow backup.yml`).
- [x] AC-5: `README.md` gains a Dispatcher section (what it starts and when, how to add a job, the token and its expiry, how to deploy, where its logs are). `docs/02-architecture.md` › Components › 4 Jobs says jobs are started by the dispatcher and corrects the 10–30-minute delay assumption, and the choice is recorded in `docs/decisions.md`.

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

- Owner: create the fine-grained token (this repository only, Actions: Read and write), then from `infra/dispatcher/` run `pnpm dlx wrangler@4.149.0 login`, `deploy` and `secret put GITHUB_DISPATCH_TOKEN` (README › Dispatcher › Deploy), and check AC-4 after the next 03:30 ET (approved at plan) → docs/owner-checklist.md § Actions
- TASK-022 adds its jobs as lines in `SCHEDULE` in `infra/dispatcher/src/index.ts` (ET times on quarter hours, none between 01:00 and 02:59 ET), with no two-crons-per-slot DST workaround (approved at plan) → docs/tasks/TASK-022-scheduled-results-and-lines-jobs.md § Context
- TASK-022 also adds a row per new job to README › Dispatcher's table, which mirrors `SCHEDULE` → docs/tasks/TASK-022-scheduled-results-and-lines-jobs.md § Context
- TASK-026 rewrites the three "until TASK-026" mentions of the interim double backup run (README › Dispatcher, README › Backups, D-122) once the fallback lands → docs/tasks/TASK-026-backup-dispatch-with-fallback.md § Context
- `verify.fast` lints only `web/` and `scripts/` files; the Worker's `.ts` files are linted by `pnpm lint` (approved at plan) → not tracked: verify.full and CI cover it
- AC-3's "the token's name appears only in the Worker's config and docs" can't hold literally: the Worker's code reads the `GITHUB_DISPATCH_TOKEN` binding and the tests set it (spec-reviewer). The intent, no token value committed, is met and tested → not tracked: wording of this task's own AC, noted in the PR

## Plan

Approved 2026-10-16 (/plan-batch): every gate decision as recommended.

**Decisions at the gate** (recommended)
- A. **Tick:** a Cloudflare Worker with one Cron Trigger, `*/15 * * * *`.
  - Entries sit on quarter hours. `due(now)` floors `now` to its 15-minute slot in `America/New_York` and returns the entries for that weekday and `hh:mm`.
  - A tick that runs late but within its slot still fires; a missed slot isn't retried (TASK-026's fallback covers the backup).
  - That's 96 runs a day on the free plan, using 1 Cron Trigger.
- B. **Package:** `infra/dispatcher/` is a pnpm workspace package with its own `lint` (ESLint and typescript-eslint), `typecheck` (`tsc --noEmit` with `@cloudflare/workers-types`) and `test` (Vitest) scripts. The root scripts call them the way they call `web`'s. Wrangler isn't installed: the owner runs `pnpm dlx wrangler@<pinned> …`, which keeps workerd and its build scripts out of CI's install.
- C. **Token:** a fine-grained token for this repository only, with Actions: Read and write and nothing else, stored as the Worker secret `GITHUB_DISPATCH_TOKEN`. The repo (`jtillmanio/cfb-model`) and ref (`main`) are plain `vars` in `wrangler.jsonc`.
- D. **Failures:**
  - A non-2xx answer is logged with its status and body (`console.error`), and the remaining workflows are still sent.
  - The handler then throws, so the Cron event shows as failed in the Cloudflare dashboard.
  - `observability.enabled` keeps the logs (Workers Logs). Nothing GitHub-side until TASK-026.
- E. **No entries between 01:00 and 02:59 ET:** those times repeat or vanish when daylight saving changes. A test checks the table.

**Steps**
1. `infra/dispatcher/src/index.ts`:
   - `SCHEDULE = [{ workflow: "backup.yml", days: "daily", time: "03:30" }]`.
   - `due(now: Date): string[]`, using `Intl.DateTimeFormat` in `America/New_York`.
   - `dispatch(env, workflows, fetchFn = fetch)`: POST `https://api.github.com/repos/${repo}/actions/workflows/${file}/dispatches` with body `{"ref":"main"}`. Headers: `Authorization: Bearer …`, `Accept: application/vnd.github+json`, `X-GitHub-Api-Version: 2022-11-28`, and `User-Agent: cfb-dispatcher`, since GitHub refuses requests without a User-Agent.
   - `export default { scheduled(controller, env) }`, timed by `controller.scheduledTime`.
2. `src/index.test.ts` (the AC-1 and AC-2 tests below).
3. `wrangler.jsonc` (name, main, `compatibility_date`, `triggers.crons`, vars, observability), `package.json`, `tsconfig.json`, `eslint.config.mjs`.
4. `pnpm-workspace.yaml` adds `infra/dispatcher`; the root `package.json`'s `lint`, `typecheck` and `test` call the package; `pnpm install` updates `pnpm-lock.yaml`.
5. `README.md` › Dispatcher (AC-5's list).
6. `docs/02-architecture.md` › Components › 4 Jobs: jobs are started at their ET times by the dispatcher, and GitHub's schedule ran 5–8 h late, not 10–30 min.
7. `docs/decisions.md`: a new D-### recording A–E.

**Files** (12): in `infra/dispatcher/`: `src/index.ts`, `src/index.test.ts`, `wrangler.jsonc`, `package.json`, `tsconfig.json`, `eslint.config.mjs` (all new); then `pnpm-workspace.yaml`, `package.json`, `pnpm-lock.yaml` (through pnpm), `README.md`, `docs/02-architecture.md`, `docs/decisions.md`. Unlike Files likely touched, `schedule.ts` and its test fold into `index.ts` and `index.test.ts`, and `eslint.config.mjs` is added, to stay at 12.

**Test strategy** (Vitest, `infra/dispatcher/src/index.test.ts`)
- AC-1, `due`:
  - "fires at 03:30 ET in EDT and EST" (2026-10-17T07:30Z, 2026-11-07T08:30Z);
  - "not at 02:30 EST" (2026-11-07T07:30Z);
  - "not in the slots either side" (07:15Z and 07:45Z on 10-17; 08:15Z and 08:45Z on 11-07);
  - "no entry between 01:00 and 02:59 ET".
- AC-2, `dispatch`:
  - "one POST per due workflow, ref main, bearer token" (a stubbed `fetch` records the calls);
  - "a non-2xx is logged with status and body and the rest still go" (two entries, the first answers 422).
- AC-3: `pnpm lint`, `pnpm typecheck` and `pnpm test` cover the package in CI. "no token-shaped string in the package" scans `infra/dispatcher/` for `github_pat_` and `ghp_`.
- AC-4: after the owner deploys, `gh run list --workflow backup.yml --event workflow_dispatch --limit 1 --json createdAt` must show a start within 5 minutes of 03:30 ET.
- AC-5: by review.

**Risks / open questions**
- AC-4 waits on the owner (token, secret, deploy), so the PR may sit with AC-4 open until the first tick after the deploy.
- Until TASK-026 gates `backup.yml`'s `schedule`, the backup runs twice a day: dispatched at 03:30 ET, then GitHub's late cron. It's harmless, since a same-day run replaces the dump, but it costs about 5 extra Actions minutes a day. README says so.
- Cloudflare's free-plan Cron and Workers limits are checked again at deploy. The token's expiry and how to rotate it go in README.

**Size check:** 12 files, ops only, no schema or UI: passes at the limit.

**Plan revisions after approval** (owner-approved 2026-10-21; 16 files, under the 20-file limit)
1. `.claude/kit.json` gains a `testAudit.runners` entry for `infra/dispatcher/*.test.ts`, so the test auditor can run the Worker's tests. `CLAUDE.md` › Commands and `docs/COMMANDS.md` name the dispatcher in the Typecheck, Lint, Unit tests and Specific test files rows, keeping them in sync with the root scripts.
2. `.gitignore` ignores `.dev.vars*` (Wrangler's local secrets file, where README's local-tick check puts the token) and `.wrangler/` (`wrangler dev` state).
3. After review, at the owner's request (2026-10-21): README › Dispatcher explains what the dispatcher is for and how a tick works, adds a Names table (GitHub token `cfb-dispatcher`, workers.dev subdomain `jtillmanio`) and a first-time setup walkthrough covering pnpm's build-script prompt and Wrangler's access prompt; the Owner checklist item matches it.

## Review log

Verify R1 PASS | Audit R1 PASS (9 mutants, all killed) | Spec R1 APPROVE (AC-4 pending the owner's deploy) | Follow-ups check R1 APPROVE

## Blocked

_Only if status is Blocked: what failed, what was tried, best hypothesis, decision needed._

## Metrics

- Verify rounds: 1
- Review rounds: 1
- First-pass AC FAILs: 0
- Plan revisions after approval: 3
