---
id: TASK-015
title: Build the CFBD ingest client with call-budget tracking and a raw Parquet writer
status: Ready
depends_on: []
size: M
model: opus
autonomy: attended
ui: false
plan_status: none
planned_at_commit:
---

# TASK-015 — Build the CFBD ingest client with call-budget tracking and a raw Parquet writer

## Goal

Any CFBD endpoint the model needs can be pulled for a season or a week. Every call is counted against the month's budget before it's made, and the response is saved untouched as Parquet in the lake, on this machine or in R2.

## Context

- Task list: `docs/08-tasklist.md` › M2 › M2.1.
- Architecture: `docs/02-architecture.md` › Components › 1 (`ingest`: pulls by season/week, writes raw Parquet, tracks its own call budget); › Two kinds of storage, on purpose (raw is immutable and append-only); › Environments & databases (`LAKE_URI=./data` or `s3://…`); › Risks & mitigations (CFBD call budget); › Non-functional requirements (≤ 5,000 calls a month, warn at 80%).
- Data model: `docs/03-data-model.md` › Data sources › CFBD (the endpoint table and its granularity); › Lake layout (`raw/cfbd/{endpoint}/season=…/week=…/fetched_at=….parquet`).
- Decisions: D-025, D-026 (tier 1, ~500-call backfill), D-027 (append-only raw, never re-fetch completed weeks, every call through the budget tracker), D-098 (the skeleton's JSON raw files, "Parquet with the Phase 1 ingest"), D-004 (light core vs `engine[train]`), D-002.
- Existing code: `python/engine/src/engine/ingest/cfbd.py` (`CfbdClient`, `CallBudget`: a per-month JSON ledger), `ingest/lake.py` (JSON writer, local only, refuses `s3://`), `ingest/games.py` (the completed-week check), `cli.py` (`engine ingest games`). Local `data/raw/cfbd/games/` already holds JSON responses from D-098.
- **Decide at the plan gate:**
  - How a JSON response is stored "exactly as fetched" in Parquet (for example one row per top-level record holding the record as JSON text, plus the request params and `fetched_at`), so a transform reads back exactly what CFBD sent.
  - The Parquet library (pyarrow or duckdb) and where it goes. D-004 puts the heavy stack in an `engine[train]` extra; `python/api` doesn't depend on the engine today.
  - How R2 is reached (fsspec/s3fs, boto3, or DuckDB `httpfs`) and how that is tested with no network.
  - Where the call ledger lives when the lake is R2. The scheduled jobs (TASK-022) run on fresh runners, so a ledger on the runner's disk would reset every run and stop counting. *Direction agreed with the owner (2026-10-15):* the ledger lives at the lake root (`cfbd_calls.json` beside `raw/`, as it does locally today), so it is in R2 whenever the lake is. The jobs' shared `concurrency` group means there's only ever one writer.
  - What happens to the JSON files D-098 already wrote. The lake is append-only, so they stay. Either readers accept both formats, or a one-time step writes Parquet copies beside them. Nothing is deleted.
  - The endpoint registry: each endpoint in 03's table with its CFBD path, params and granularity (season or week). TASK-021 backfills from it, and TASK-017/TASK-018 record test fixtures with it.
- **Owner prerequisite (for the R2 check only):** a Cloudflare R2 bucket for the lake, separate from `cfb-backups` (D-109: R2 tokens are scoped by bucket, not folder), and a token with read/write on that bucket only. Roadmap Phase 0 › Accounts notes this bucket is missing. Claude never edits secrets.

## Acceptance criteria

- [ ] AC-1: Given a ledger at 3,999 of 5,000 calls for the current month (fixed clock), when the client makes one call, the ledger reads 4,000 and the output warns with `4000/5000`. Given a ledger at 5,000, the next call raises `BudgetExceededError` and the fake HTTP transport records zero requests.
- [ ] AC-2: Given a recorded CFBD response, when it's ingested into a local lake, exactly one Parquet file is written at `raw/cfbd/<endpoint>/season=<Y>[/week=<NN>]/fetched_at=<UTC>.parquet`, and reading it back returns records equal to the original JSON. The test covers at least `/games` and `/lines`. Writing to a path that exists raises, and the existing file is unchanged.
- [ ] AC-3: Given a week-level endpoint whose response for that week was already saved after every game in the week was completed (per the saved `/games` response), when that endpoint is requested again, no HTTP request is made, the ledger is unchanged, and the command says it used the saved file.
- [ ] AC-4: With `LAKE_URI=s3://<bucket>`, the writer writes and reads through R2's S3 API. A test against a fake S3 writes one file, reads it back unchanged, and refuses to overwrite it.
- [ ] AC-5: `engine ingest <endpoint> --season Y [--week N]` accepts every endpoint in 03 › Data sources' table. A registry test checks that each entry names its CFBD path, required params and granularity. `engine ingest games` still publishes to the dev DB as before (D-098), now reading the Parquet it wrote.

## Out of scope

- Staging and transforms (TASK-017, TASK-018), and publishing anything beyond what `ingest games` already publishes (TASK-020).
- Running the backfill or spending more than a handful of calls to record fixtures (TASK-021).
- Scheduled jobs (TASK-022).
- Creating the R2 bucket or its token (the owner).

## Files likely touched

- `python/engine/src/engine/ingest/cfbd.py`: ledger location, endpoint calls.
- `python/engine/src/engine/ingest/lake.py`: Parquet writer and reader, R2 support.
- `python/engine/src/engine/ingest/endpoints.py`: the endpoint registry (new).
- `python/engine/src/engine/ingest/games.py`, `python/engine/src/engine/cli.py`: generic `ingest <endpoint>`; `ingest games` on Parquet.
- `python/engine/pyproject.toml` (and `python/uv.lock` through `uv add`): Parquet and S3 dependencies.
- `python/engine/tests/test_cfbd_client.py`, `python/engine/tests/test_lake.py` (new); `python/engine/tests/fixtures/` recorded responses.
- `.env.example`, `docs/COMMANDS.md`: `LAKE_URI` for R2 and its credentials.

## Verification

- Automated: `test_cfbd_client.py` (AC-1, AC-3), `test_lake.py` (AC-2, AC-4), a registry test (AC-5); the existing `test_cfbd_games.py` and `test_publish_reference.py` still pass. No test opens a network connection.
- Manual: `pnpm ingest:games --season 2026 --week 6` against the dev DB → one call counted, one Parquet file under `data/raw/cfbd/games/…`, games upserted. With the owner's lake bucket set in `LAKE_URI`, `engine ingest calendar --season 2026` → the file appears in the bucket.

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
