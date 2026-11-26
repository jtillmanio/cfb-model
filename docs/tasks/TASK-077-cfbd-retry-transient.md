---
id: TASK-077
title: Retry CFBD calls that time out or hit a transient server error
status: Draft
depends_on: []
size: M
model: sonnet
autonomy: attended
ui: false
plan_status: none
planned_at_commit:
---

# TASK-077 — Retry CFBD calls that time out or hit a transient server error

## Goal

A slow or briefly unavailable CFBD response no longer fails a scheduled job outright. The client retries a few times within the call budget. When it does give up, the run's summary says which call failed and why, so nobody has to read a traceback.

## Context

- **Incident (2026-11-14 to 11-16):** 4 of the last 8 `lines` runs failed with `httpcore.ReadTimeout: The read operation timed out`, raised from `CfbdClient.get` (`engine/ingest/cfbd.py`) during the per-week pull in `jobs.run` (`endpoints.pull`). The runs were 43871648160, 43716677745, 43629633109 and 43597527146. The client has a 30 s timeout and no retry, so a single slow response ends the run. The traceback doesn't name the endpoint or params, and the step summary has no line for it. The summary's table still prints with `0` new rows, which reads as if the publish ran.
- **Budget (D-027, D-112):** every call goes through `CallBudget.spend()` *before* it's sent, and the ledger is shared across runs. A retry is a call, and CFBD may count a request that timed out on our side, so each attempt must be spent. `BudgetExceededError` must still stop the run with exit 3, even mid-retry.
- **Runtime:** the job workflows have `timeout-minutes: 10` (D-123). The worst case for one call, attempts × timeout plus backoff, must stay well inside that, and the first call that exhausts its retries ends the run. A dead CFBD fails fast and doesn't retry every week's pull.
- **Pattern:** `test_cfbd_client.py` fakes CFBD with `httpx.MockTransport` and never opens a socket. The retry tests use it too, with the sleep injected so no test waits.
- Architecture: docs/02-architecture.md § Components › 4. Jobs
- Decisions: D-027, D-112, D-123
- *From TASK-076 (fix/076-jobs-run-production-commit):* the job workflows now run the commit production serves, not `main` (D-179). The retry reaches the `lines` job only after a release, so the Verification's manual check ("the next scheduled `lines` run") needs a release first. To try it on the task branch before that, dispatch `lines.yml` with `code_ref=<the task branch>`; that run writes production. Exit 4 now means production's schema is behind the code, so the give-up error must not reuse it.

## Acceptance criteria

- [ ] AC-1: Given a mock transport whose first response raises `httpx.ReadTimeout` (and, in a second case, `httpx.ConnectTimeout`) and whose second returns 200 with a JSON body, when `CfbdClient.get` is called, then it returns that body and the ledger's month count rises by 2.
- [ ] AC-2: Given a first response of 502, 503 or 504 then 200, `get` returns the 200 body after 2 counted calls. Given a 400, 401 or 404, `get` raises `httpx.HTTPStatusError` after exactly 1 counted call, with no retry.
- [ ] AC-3: Given every attempt times out, `get` raises after N attempts (N a module constant, at most 3), the ledger rises by N, and the injected sleep is called N − 1 times with waits whose total is at most a module constant (expected: the test asserts both constants, and N × the client timeout + total wait < 300 s).
- [ ] AC-4: Given the ledger is one call short of `MONTHLY_LIMIT` and the first attempt times out, when `get` retries, then it raises `BudgetExceededError` without sending a second request, and the ledger never exceeds the limit.
- [ ] AC-5: Given a `lines` job whose CFBD fake times out on every attempt, when `engine job lines` runs, then it exits 1, the step summary has one line naming the endpoint, its params, the number of attempts and the error type (e.g. `CFBD /lines season=2026 week=12: ReadTimeout after 3 attempts`), and the summary has no `| Table | Staged rows | New rows |` table (nothing was published).

## Out of scope

- Retrying the nflverse download. It already fails softly and publishes the rest (D-169).
- Retrying the database publish, or the job as a whole (a second workflow attempt).
- Raising the call budget or the job timeout.
- Pinning the jobs to production's commit (TASK-076).

## Files likely touched

- `python/engine/src/engine/ingest/cfbd.py` — the retry loop, attempts and backoff constants, injectable sleep, and an error that carries the endpoint, params and attempts
- `python/engine/src/engine/jobs.py` — record the CFBD failure on the `Summary`, and render it without the misleading table
- `python/engine/src/engine/cli.py` — catch the client's give-up error in `_job` (exit 1, summary written)
- `python/engine/tests/test_cfbd_client.py` — AC-1 to AC-4
- `python/engine/tests/test_jobs.py` — AC-5
- `README.md` — § Jobs › `### Read a failed run`: the new summary line and what to do
- `docs/decisions.md` — new row: which errors are retried, how many attempts, the backoff, and that each attempt is budgeted (amends D-112)

## Verification

- Automated: `test_cfbd_client.py` has retry tests that fail on today's client, which raises `ReadTimeout` on the first attempt. `test_jobs.py` has a lines-job timeout test asserting exit 1 and the summary line. No test sleeps or opens a socket.
- Manual: none needed beyond CI. The next scheduled `lines` run that meets a slow CFBD response should either succeed on a retry or fail with the new summary line.

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
