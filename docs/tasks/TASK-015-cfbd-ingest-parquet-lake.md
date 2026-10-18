---
id: TASK-015
title: Build the CFBD ingest client with call-budget tracking and a raw Parquet writer
status: Ready
depends_on: []
size: M
model: opus
autonomy: attended
ui: false
plan_status: approved
planned_at_commit: 1bf71ef
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

- Season-level endpoints have no "already complete" rule here (step 3 always fetches them); TASK-021's resumable backfill needs one, e.g. a season's file is final when saved after its last game completed → docs/tasks/TASK-021-backfill-and-notebook-1.md § Context (open question for the plan)
- The scheduled jobs reach the R2 lake through `LAKE_URI=s3://<bucket>`, `R2_ACCOUNT_ID`, `R2_DATA_LAKE_ACCESS_KEY_ID` and `R2_DATA_LAKE_SECRET_ACCESS_KEY` in the step's `env:` (gate decision C), and the call ledger lives in R2 with the lake (D) → docs/tasks/TASK-022-scheduled-results-and-lines-jobs.md § Context
- 03 › Lake layout gains the raw file's shape (one row per record: `row`, `record` JSON text, `params`, `fetched_at`), the `season_type=postseason` level, and the ledger at the lake root → docs/03-data-model.md § Lake layout (approved at plan)
- Candidate decision: gate decisions A–G (Parquet shape, the `train` extra, R2 through boto3, the ledger, the D-098 files, partitions, the registry); amends D-098 → docs/decisions.md § D-112 (recorded with the approved plan)

## Plan

Approved 2026-10-16 (/plan-batch): every gate decision as recommended, including F's postseason level.

**Decisions at the gate** (recommended)
- A. **Parquet shape:** one row per top-level record: `row` (int32 position), `record` (the record as JSON text), `params` (the query sent, JSON text), `fetched_at` (timestamp UTC). A non-list response is one row; an empty list writes a zero-row file (the call still happened). Reading back = `json.loads(record)` in `row` order.
- B. **Libraries:** `pyarrow` (Parquet) and `boto3` (R2) in a new `train` extra of `cfb-engine` (D-004's heavy extra; DuckDB joins it in TASK-017). The workspace root depends on `cfb-engine[train]`; `moto[s3]` is dev-only. The light core and `python/api` gain nothing.
- C. **R2:** boto3 with `endpoint_url=https://<R2_ACCOUNT_ID>.r2.cloudflarestorage.com`, region `auto`, checksums `when_required` (as `backup.yml`), keys `R2_DATA_LAKE_ACCESS_KEY_ID` / `R2_DATA_LAKE_SECRET_ACCESS_KEY` (the names already in GitHub). No overwrite: `head_object` then `put_object` (one writer: TASK-022's shared concurrency group); conditional PUT is unverified on R2. Tests use moto's in-process `mock_aws`.
- D. **Ledger:** `cfbd_calls.json` at the lake root through the same lake object (file or R2 object); the one object the lake overwrites.
- E. **D-098's two JSON files** (2025 week 1 `/games`) stay untouched and unread. TASK-021's backfill fetches that week anyway.
- F. **Partitions:** `season=Y[/season_type=postseason][/week=NN]`. Regular season adds no level, so AC-2's path holds; postseason week 1 can't collide with regular week 1. `classification` stops being a flag and a partition: the registry fixes `fbs`. **Owner OK needed:** AC-2's pattern has no postseason level.
- G. **Registry** `ENDPOINTS` in `ingest/endpoints.py`: name → `path`, required params, fixed params, granularity (`season`, `week`, or both for `/games` and `/lines`). `/conferences` and `/venues` send no year but still file under `season=Y`. `/ppa/predicted` is `static`, taking `--param down=… --param distance=…`.

**Steps**
1. `lake.py`: `open_lake()` from `LAKE_URI` → `LocalLake(root)` or `S3Lake(bucket, client)`, with `write_new(key, data)` (raises `FileExistsError`), `read(key)`, `list(prefix)`, `read_text`/`write_text` (ledger only). Also `encode_raw`/`decode_raw` (A), `raw_key(...)` (F) and `latest_raw(lake, folder)` (newest `fetched_at`).
2. `cfbd.py`: `CallBudget(lake)` reads and writes the ledger through the lake. Unchanged: the count happens before the transport, the `BudgetExceededError`, and the `.../5000` warning at ≥ 80%.
3. `endpoints.py`: the registry plus `pull(lake, client, name, season, week, season_type, extra)`. If the saved file is final it prints `Using saved <key> (week complete); no API call.` and returns it. Otherwise it makes one counted call and calls `write_new`. A week-level file is final when some saved `/games` file covering that week (week- or season-level) is all `completed` and was fetched no later than it; `/games` itself is final when its latest file is all completed. Season-level files are never final (follow-up).
4. `games.py`: `ingest_games` = `pull("games", …)` → `decode_raw` → `map_games` → `publish_games_batch` (unchanged).
5. `cli.py`: `engine ingest <name> --season Y [--week N] [--season-type regular|postseason] [--param k=v]`, choices from the registry. `games` alone also publishes to dev (D-098). `--classification` is removed (G).
6. `uv add --package cfb-engine --optional train pyarrow boto3`, `uv add --dev "moto[s3]"`, root dependency `cfb-engine[train]`.
7. Record `/lines` 2025 week 1 with the new CLI (1 counted call, attended), trimmed to 3 games → `tests/fixtures/cfbd_lines_sample.json`.
8. `.env.example`: R2 lake variables; drop "s3:// isn't supported yet".

**Files** (12): `ingest/lake.py`, `ingest/cfbd.py`, `ingest/endpoints.py` (new), `ingest/games.py`, `cli.py`, `python/engine/pyproject.toml`, `python/pyproject.toml` (root dependency and dev group; not in Files likely touched), `python/uv.lock` (through uv), `tests/test_cfbd_client.py` (new), `tests/test_lake.py` (new), `tests/fixtures/cfbd_lines_sample.json` (new), `.env.example`. `docs/COMMANDS.md` is dropped to stay at 12; the CLI's `--help` lists the endpoints.

**Test strategy** (no test opens a socket: `httpx.MockTransport`, `mock_aws`, a fixed `FIXTURE_NOW` with `APP_ENV=test`)
- AC-1 `test_cfbd_client.py`: `test_the_4000th_call_is_counted_and_warns` (output has `4000/5000`), `test_a_spent_budget_raises_before_any_request` (transport saw 0 requests).
- AC-2 `test_lake.py`: `test_raw_round_trip[games]`, `test_raw_round_trip[lines]` (one file, path regex, records equal the fixture), `test_writing_an_existing_key_raises_and_keeps_the_file`.
- AC-3 `test_cfbd_client.py`: `test_a_completed_weeks_saved_file_is_used_without_a_call` (0 requests, ledger unchanged, `Using saved` printed), `test_a_file_saved_before_the_games_completed_is_fetched_again`.
- AC-4 `test_lake.py`: `test_s3_lake_round_trip_and_refuses_overwrite`.
- AC-5 `test_cfbd_client.py`: `test_registry_covers_every_endpoint_in_03` (the 18 names from 03's table), `test_ingest_games_publishes_what_it_read_back_from_parquet` (publish stubbed); the manual dev run in Verification.

**Risks / open questions**
- F changes AC-2's path for postseason files only.
- moto has to keep up with the locked boto3. pyarrow adds about 40 MB to the jobs' install; the API never installs it.
- `python/uv.lock` also changes in TASK-023: the second branch re-locks after the first merges.

**Size check:** 12 files (`uv.lock` included), one layer (etl), no schema or UI: passes at the limit.

## Review log

_Filled by /implement-task. One line per round._

## Blocked

_Only if status is Blocked: what failed, what was tried, best hypothesis, decision needed._

## Metrics

- Verify rounds:
- Review rounds:
- First-pass AC FAILs:
- Plan revisions after approval:
