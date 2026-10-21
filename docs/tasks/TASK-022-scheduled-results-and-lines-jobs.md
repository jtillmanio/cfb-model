---
id: TASK-022
title: Schedule the results and lines jobs
status: Ready
depends_on: [TASK-020, TASK-021, TASK-025]
size: M
model: opus
autonomy: attended
ui: false
plan_status: approved
planned_at_commit: 57badb4
---

# TASK-022 — Schedule the results and lines jobs

## Goal

With nobody running anything, Sunday and Monday mornings pick up the weekend's final scores and stats, and lines are snapshotted daily and on Thursday and Friday evenings. Everything is published to production, so the production Teams page lists the real 2026 FBS teams.

## Context

- Task list: `docs/08-tasklist.md` › M2 › M2.7, plus the production half of M2.6 ("backfill reaching prod"; see TASK-021).
- Architecture: `docs/02-architecture.md` › Components › 4 Jobs (`results` Sun 6am and Mon 6am ET: final scores, box scores, advanced stats, PBP for the week; `lines` daily plus Thu–Fri evenings: snapshot CFBD lines); › Environments & databases (`LIVE=true` on production, the unpooled URL for bulk publish); › Non-functional requirements (each run ≤ 10 min, ≤ 1,500 Actions minutes a month, lines refreshed at least daily, ≤ 40 CFBD calls a week in season).
- Data model: `docs/03-data-model.md` › Data sources (calls per week); `docs/02-architecture.md` › Components › 4 (`scores` needs CFBD's scoreboard endpoint, "confirm it's in tier 1 during Phase 1").
- Decisions: D-001 (batch-first), D-015 (`LIVE`, production URL only by explicit flag or workflow environment), D-016, D-027, D-092.
- Existing code: `.github/workflows/release.yml` and `backup.yml` (secrets through `env:`, `concurrency`, job summary), `python/db/src/db/config.py` (target URLs, `refuse_if_live`).
- **Stop and ask:** these workflows write to production. Running one on the branch (`gh workflow run <file> --ref <branch>`, a ready gate for changed workflows) needs the owner's go-ahead in the session.
- **Owner prerequisites:** Actions secrets `CFBD_API_KEY` and the R2 lake token as `R2_DATA_LAKE_ACCESS_KEY_ID` / `R2_DATA_LAKE_SECRET_ACCESS_KEY` (read/write on the lake bucket only, not `cfb-backups`) and the production database URL the publish uses; Claude never edits secrets.
- *From TASK-025 (drafted 2026-10-16):* GitHub's `schedule` started the backup 5–8 hours late (2026-10-13 to 10-15), which would miss the Sun 10 AM ET predictions target. TASK-025 proposes an external dispatcher that starts workflows by `workflow_dispatch` at ET times, with daylight saving handled in its code. The owner made this task depend on TASK-025 (2026-10-16): these jobs register with the dispatcher (a GitHub `schedule` fallback as in TASK-026), and the daylight-saving question below goes away.
- **Decide at the plan gate:** cron in UTC for ET times across daylight saving (two entries per slot, or a time check in the job); how the job gets the lake it transforms (incremental staging, or DuckDB reading R2 directly) so a run stays under 10 minutes; where the call ledger lives (TASK-015's decision); which production URL secret publishing uses, given the release workflow already holds `PRODUCTION_DATABASE_URL_UNPOOLED`.
- *From TASK-015 (PR #52):* the engine reaches the R2 lake through `LAKE_URI=s3://<bucket>`, `R2_ACCOUNT_ID`, `R2_DATA_LAKE_ACCESS_KEY_ID` and `R2_DATA_LAKE_SECRET_ACCESS_KEY`; pass them to the engine in the step's `env:`. The call ledger is `cfbd_calls.json` at the lake root, so it lives in R2 with the lake (D-112).
- *From TASK-025 (PR #52):* add this task's jobs as lines in `SCHEDULE` in `infra/dispatcher/src/index.ts`: ET times on quarter hours, none between 01:00 and 02:59 ET (those times repeat or vanish at a daylight-saving change). The dispatcher converts to ET itself, so no two-crons-per-slot workaround is needed.
- *From TASK-015 (PR #54), open question for the plan:* a week's raw file is reused forever once it's non-empty and saved after `/games` showed the week complete (D-114). A `results` run soon after the last game could save a week CFBD hasn't fully filled in (plays, drives, box scores). Should the job wait a settle time after the games complete before pulling, or should the engine gain a `--refetch` that appends a newer file through the budget?
- *From TASK-015 (PR #54):* `engine ingest` needs pyarrow and boto3, which the workspace root installs only through its `dev` group (D-114). Install the job's Python with `uv sync` or `uv run` as they default, never `--no-dev`.
- *From TASK-021 (PR #67):* D-121 counts an unscored game as done (canceled) once its `/games` file is saved 7+ days after its start, for the week and season final rules. A postponed game that CFBD leaves under its old week and start date would then make its week final, and a later pull of that week would never happen. The `results` job should list games treated as done while unscored and not completed, so one that is played later is caught (arrived after the plan was approved)
- *From TASK-025 (feat/task-025-on-time-workflow-dispatcher):* README › Dispatcher has a table of what the dispatcher starts and when (ET), mirroring `SCHEDULE`. Add a row there for each job added to `SCHEDULE`.

## Acceptance criteria

- [ ] AC-1: `.github/workflows/results.yml` is scheduled for Sunday and Monday at 6:00 AM ET and `lines.yml` daily plus Thursday and Friday evenings (UTC crons, with the daylight-saving handling written beside them). Both also have `workflow_dispatch` and share a `concurrency` group, so two runs never publish at once.
- [ ] AC-2: Each job runs ingest (the current week) → transform → data-quality checks → publish, with `LIVE=true`. A test on the job's Python entry point shows that, given staged data failing a check, publish is never called and the run exits non-zero.
- [ ] AC-3: An owner-approved branch run of each workflow finishes green in ≤ 10 minutes, and its job summary lists the CFBD calls spent, the month's total and the rows upserted per table.
- [ ] AC-4: After the first approved `results` run, production's `teams` has as many 2026 FBS teams as the staged 2026 data, and a second run inserts no new team or game rows.
- [ ] AC-5: `docs/03-data-model.md` › Data sources records whether CFBD's scoreboard endpoint answers on tier 1, from one counted call whose response is saved to the lake.

## Out of scope

- The `rate-and-predict` job (M4.8), the `scores` job (M6.8), NFL schedules from nflverse (M6), and watchlist alerts on the `lines` job (Phase 5).
- The Odds API.
- Re-planning job times beyond 02's table.

## Files likely touched

- `.github/workflows/results.yml`, `.github/workflows/lines.yml`: the two jobs (new).
- `python/engine/src/engine/jobs.py`: the ingest → transform → check → publish entry point (new).
- `python/engine/src/engine/cli.py`: `engine job results|lines`.
- `python/engine/tests/test_jobs.py`: AC-2 (new).
- `docs/03-data-model.md` › Data sources: AC-5.
- `README.md`: a Jobs section (schedule, secrets, how to run one by hand).
- `.env.example`: the "Lives elsewhere" block lists the new Actions secrets.

## Verification

- Automated: `test_jobs.py`; the ready gate "Changed workflow run on the branch" for both workflows (owner-approved).
- Manual: after the first scheduled `results` run on a Sunday, sign in on production → `/teams` lists the 2026 FBS teams; the Actions tab shows each run under 10 minutes.

## Follow-ups

_Work noticed during this task and deliberately left out. Each bullet ends `→ <path> § <section>` (where it was placed) or `→ not tracked: <reason>`. See `.claude/skills/track-follow-ups/classify.md`; the PR's Follow-ups section is copied from here._

- Add the repo variable `LAKE_URI` (`s3://<lake bucket>`). The production URL needs no new secret: the jobs reuse `PRODUCTION_DATABASE_URL_UNPOOLED` → docs/owner-checklist.md § Actions (approved at plan)
- Open question for TASK-026: should the backup's fallback reuse `.github/actions/skip-if-dispatched` (skip a `schedule` run when a dispatched run succeeded in the last 6 h), or keep its check on the day's dump? → docs/tasks/TASK-026-backup-dispatch-with-fallback.md § Context (approved at plan)
- The jobs stage one season in a scratch lake, so R2 `staging/` and the feature tables aren't refreshed by them. `rate-and-predict` needs its own rebuild of history → docs/08-tasklist.md § M4.8 (approved at plan)

## Plan

Provisional: depends on TASK-020 (`publish_lake`), TASK-021 (`sync_raw`, the R2 lake and its ledger, the season-level final rule) and TASK-025 (`SCHEDULE`).

**Gate decisions** (recommended)
- A. **Times (ET):** `results` Sun and Mon 06:00; `lines` daily 08:00, plus Thu and Fri 19:00 (the pick window). They're added to TASK-025's `SCHEDULE`, which converts to ET, so the dispatcher's `workflow_dispatch` is the primary start.
  - Each workflow also has a UTC `schedule` fallback: `0 12 * * 0,1` for results; `0 14 * * *` and `0 1 * * 5,6` for lines. A comment beside each says it fires 1–2 h after the ET slot (EST or EDT) and runs only if the dispatcher didn't.
  - The guard, `.github/actions/skip-if-dispatched`, skips a `schedule` run when a `workflow_dispatch` run of the same file succeeded in the last 6 h (`gh run list`, `actions: read`). TASK-026 reuses it.
- B. **Lake:** ingest writes the R2 lake (`LAKE_URI` s3, the shared ledger). The job then copies only `raw/cfbd/*/season=<current>/**` into a runner-local scratch lake (`sync_raw` with a season filter). It rebuilds, checks and publishes from that copy. R2 `staging/` is never touched, and a run reads one season, so it stays well under 10 min. Upserts never delete, so publishing one season is safe.
- C. **`LIVE`:** `rebuild` refuses under `LIVE=true` only when the lake already holds `staging/` files. An empty scratch lake overwrites nothing. This amends D-116; `test_rebuild_refuses_under_live` still holds.
- D. **Settle time** (TASK-015's open question; amends D-114): a week file is final only if it was also saved ≥ 24 h after the week's last kickoff in the `/games` file. Sunday's run is then never final, and Monday's settles the week. That keeps "never re-fetch completed weeks", with "completed" meaning settled, and needs no `--refetch`.
- E. **Pulls:**
  - `results` pulls the latest week whose `last_game_start` has passed: `games`, `games_teams`, `stats_game_advanced`, `plays`, `drives`, `lines` (post-kickoff, so TASK-020 makes them `closing` rows). That's 6 calls.
  - `lines` pulls the week containing now: `games` and `lines`, 2 calls.
  - Weeks come from the R2 `/calendar` file (pulled if it's missing). That's about 12 + 18 = 30 calls a week, within the 40 budget.
- F. **Production URL:** reuse the repo secret `PRODUCTION_DATABASE_URL_UNPOOLED` through `db.config.live_url(None)` (the release's, unpooled per D-016). No new secret. The repo variable `LAKE_URI` is an owner action.
- G. **Scoreboard:** the registry gains `scoreboard` (`/scoreboard`, season granularity, no params). One `engine ingest scoreboard --season 2026` call goes in 03 › Data sources with the result. A 401 or 403 response is recorded as "not in tier 1": there's no body to save, and the PR says so.

**Steps**
1. `endpoints.py`: D, plus the `scoreboard` entry (G).
2. `transform/__init__.py`: C.
3. `engine/jobs.py` (new): `run(kind, lake, *, target, client=None, now=None) -> Summary`, in order:
   1. pull (E);
   2. scratch `LocalLake(tempdir)` + `sync_raw`;
   3. `rebuild`;
   4. `quality.run`; when not ok, print the report and raise `JobFailed` (exit 1) before any DB connection;
   5. `publish_lake` in one transaction;
   6. `Summary`: the calls this run (the ledger difference), the month's total, and rows upserted per table.
4. `cli.py`: `engine job results|lines --target dev|live [--summary PATH]`. `live` needs `LIVE=true`, and `--summary` appends markdown (`$GITHUB_STEP_SUMMARY`).
5. `.github/workflows/results.yml` and `lines.yml`:
   - `workflow_dispatch` plus the fallback `schedule`, and `concurrency: {group: lake-publish, cancel-in-progress: false}`;
   - `permissions: {contents: read, actions: read}`, `timeout-minutes: 10`;
   - the guard, `setup-uv`, then `uv --directory python run engine job …` (the dev group, D-114; never `--no-dev`);
   - secrets only through `env:` (`CFBD_API_KEY`, `R2_DATA_LAKE_*`, `PRODUCTION_DATABASE_URL_UNPOOLED`), with `vars.R2_ACCOUNT_ID`, `vars.LAKE_URI` and `LIVE: "true"`.
6. `.github/actions/skip-if-dispatched/action.yml` (new).
7. `infra/dispatcher/src/index.ts`: four `SCHEDULE` lines, plus a case in `index.test.ts`.
8. Docs:
   - `03-data-model.md` › Data sources (the `/scoreboard` row and its tier result) and › Lake layout (D);
   - `README.md` › Jobs (schedule, secrets and variables, a run by hand: `gh workflow run results.yml`);
   - `.env.example` › Lives elsewhere;
   - `decisions.md`: one D-### for A–G.

**Files** (16): `results.yml`, `lines.yml`, `actions/skip-if-dispatched/action.yml` (all new), `engine/jobs.py` (new), `engine/cli.py`, `engine/tests/test_jobs.py` (new), `ingest/endpoints.py`, `tests/test_cfbd_client.py`, `transform/__init__.py`, `tests/test_transform.py`, `infra/dispatcher/src/index.ts`, `infra/dispatcher/src/index.test.ts`, `docs/03-data-model.md`, `README.md`, `.env.example`, `docs/decisions.md`.

**Test strategy**
- AC-1, read as text like `test_ci_config.py`: `test_workflows_dispatch_schedule_and_share_concurrency`, `test_fallback_crons_have_dst_comment`. In Vitest, "results fires Sun and Mon 06:00 ET; lines daily 08:00 and Thu/Fri 19:00 ET", in EDT and EST.
- AC-2 `test_failed_check_never_publishes` (fake client returns a final game with no score; `publish_lake` monkeypatched to fail if called; exit 1). Also `test_job_publishes_scratch_staging_under_live`.
- C `test_rebuild_into_empty_lake_allowed_under_live`.
- D `test_sunday_file_not_final_monday_file_final`. The finality tests in `test_cfbd_client.py` move their saved times past the settle time. The registry count goes from 18 to 19.
- AC-3, AC-4: owner-approved branch runs (`gh workflow run … --ref <branch>`, then `gh run watch --exit-status`). The PR shows the job summaries, the run times, and the production 2026 FBS team count against the staged count. A second run inserts 0 teams and 0 games.
- AC-5: the counted call, plus the 03 diff.

**Risks / open questions**
- **Stop and ask:** every branch run writes production; each one needs your go-ahead in the session.
- The repo variable `LAKE_URI` must exist before the first run (Owner checklist).
- A dispatcher outage leaves only the late fallback. A run that starts late still pulls the right week from the clock.

**Size check:** 16 files, ops + engine, no schema or UI: passes (limit 20).

## Review log

_Filled by /implement-task. One line per round._

## Blocked

_Only if status is Blocked: what failed, what was tried, best hypothesis, decision needed._

## Metrics

- Verify rounds:
- Review rounds:
- First-pass AC FAILs:
- Plan revisions after approval:
