---
id: TASK-046
title: Run the production weekly cycle: rate, predict and pick
status: In progress
depends_on: [TASK-043, TASK-044, TASK-045]
size: M
model: opus
autonomy: attended
ui: false
plan_status: approved
planned_at_commit: 5171d67
---

# TASK-046 — Run the production weekly cycle: rate, predict and pick

## Goal

Every Sunday morning in season, production gains new ratings, predictions and picks for the coming week from the model version it paper-trades (v1.0, `candidate`, D-144) with nobody running anything, and when lines move during the week the picks are re-evaluated. Paper trading of 2026 starts with this task's first scheduled run.

## Context

- Task list: `docs/08-tasklist.md` › M4 › M4.8 (split: TASK-044 stages canceled games and moves `engine rate` onto the harness's contexts; TASK-045 is the pick writer; this task runs both on production).
- Roadmap: `docs/06-roadmap.md` › Phase 3 — "Production weekly cycle live: rate → predict → pick (paper trading 2026)"; acceptance "weekly picks are generated automatically and graded by the views".
- Architecture: `docs/02-architecture.md` › Components › 4 Jobs (`rate-and-predict` Sun 9am; `lines` re-evaluates picks when lines move; the dispatcher's `SCHEDULE` lists only the jobs built); › Release & operations; › Non-functional requirements (D-092: predictions out by Sun 10 AM ET, each job ≤ 10 min).
- Model: `docs/04-model.md` § 4 (re-evaluate when the line moves); § 9.1 (2026 is live paper trading).
- Decisions: D-092, D-122 (the dispatcher starts jobs with `workflow_dispatch`), D-123 (how `results` and `lines` run: pull into R2, stage one season in a scratch lake, check, publish in one transaction), D-129 (the late-fallback cron and `skip-if-dispatched`), D-131 (the postseason is one week), D-134 (`engine rate --choices` resolves a season's tuned settings from a backtest's `run.json`), D-140, D-141, D-142, and TASK-043's go/no-go row (which version runs).
- Code today: `engine job results|lines --target dev|live` (`engine/jobs.py`, `.github/workflows/results.yml`, `lines.yml`); `engine rate --target dev|test` (`publish/models.py`), refused under `LIVE=true`, rates regular-season weeks only and needs `--choices` for a tuned spec; the dispatcher's `SCHEDULE` (`infra/dispatcher/src/index.ts`); README › Jobs and › Dispatcher › Add a job.
- *From TASK-022 (PR #62):* the `results` and `lines` jobs stage one season in a scratch lake, so they never refresh R2 `staging/` or the feature tables; `rate-and-predict` needs its own rebuild of history.
- *From TASK-043 (PR #110), open question for the plan:* the go/no-go (D-144) did **not** promote v1: it failed the holdout (ATS 47.3%, MAE gap +0.61), so it stays `candidate` and the owner's call is that this job paper-trades it through 2026, with the "uncalibrated" label shown. The Goal's "promoted model" and AC-1's `production` (cfb, spread) version assume a promotion that didn't happen: decide how the job selects the `candidate` version, and ask the owner whether AC-1's wording changes. The final spec is `efficiency-v1.json` at spec hash `50d9e5812819` (its α grid widened, so earlier runs' `run.json` no longer match it); the newest validation run is `backtests/20261031T043227249121Z-50d9e5812819`, and the holdout has been opened once (`backtests/holdout/`, one record).
- *From TASK-045 (PR #120), open question for the plan:* the pick writer is `engine.publish.picks.write_picks(conn, version_id, season, week, now)` (D-148), run in the caller's transaction; `engine pick --target dev|test` wraps it, refused under `LIVE=true`. It reads the version's newest succeeded run of either non-backtest type (`adhoc` or `scheduled`) that finished by `now`, while AC-3 says "newest `scheduled` run": decide whether the job filters to `scheduled`. It takes a transaction-scoped advisory lock on the version before its first read, so the weekly run and a `lines` re-evaluation serialize, but only under READ COMMITTED (the default `make_engine` gives): keep that isolation, or take the lock before any other read. A `PicksRefused` or `PointInTimeError` raised partway leaves earlier inserts in the caller's transaction, so the job must roll back, never catch it and commit. A run with no predictions returns 0 picks and 0 passes, the same as "no line moved": the job's summary should tell the two apart.
- **Decide at the plan gate:**
  - **Which version and settings:** the job rates with the target DB's `production` (cfb, spread) version, so how v1.0 and its status reach production (an `engine promote` the owner runs, or a step in the job), per TASK-043's call; and where the 2026 settings come from, since `run.json` `choices` hold only scored seasons (a backtest that scores 2026, tuned on 2015–2025 now the holdout is spent, with its `run.json` in R2 or in the repo).
  - **Postseason:** whether the job rates postseason week 1 (the bowls and CFP, D-131) in this task or a follow-up does.
  - **Branch run:** README's ready gate runs a changed workflow on the branch, and this one writes to production: whether that run targets production (stop and ask first) or the workflow gains an input that skips the publish.
  - **Lines:** whether `engine job lines` re-evaluates picks in the same transaction as its snapshot publish or after it.

## Acceptance criteria

- [ ] AC-1: Given a lake fixture and the test DB with the version the job names (created as `candidate` from its spec file when missing), `engine job rate-and-predict --target dev` with the clock on a Sunday in season rebuilds every staged season from the raw lake in a scratch lake with zero CFBD calls (the call ledger is unchanged), and in one transaction inserts a `scheduled` model run, its ratings, a prediction for every staged game of the coming week that will be played (none for a canceled one), and TASK-045's picks for them (test).
- [ ] AC-2: With a version of that name whose stored spec differs from the spec file, or settings for the season that can't be resolved, the job exits 2 and writes nothing; a failed data-quality check exits 1 before the database is opened; a second run in the same week inserts a new run and predictions but no pick whose side and tier are unchanged (tests).
- [ ] AC-3: `engine job lines`, after publishing new snapshots, re-evaluates the coming week's picks from each version's newest `scheduled` run in the season against the newest snapshots: a test where a line moves across the threshold gains a pick, one where nothing changes gains no row, and a game already kicked off gains none.
- [ ] AC-4: `.github/workflows/rate-and-predict.yml` runs the job under `LIVE=true` with `timeout-minutes: 10`, in the `lake-publish` concurrency group, with a fallback cron and `skip-if-dispatched` as `results.yml` has; the dispatcher's `SCHEDULE` gains `rate-and-predict.yml` on Sun at 09:00 ET with a Vitest case for that slot; the workflow's branch run (the ready gate, as the plan settles) passes in under 10 minutes.
- [ ] AC-5: README › Jobs gains the workflow's row (time, fallback cron, calls a run: 0) and what each step does, 02 › Components › 4 Jobs says `rate-and-predict` and the `lines` re-evaluation are built, and `docs/owner-checklist.md` lists each owner action the plan names (redeploy the dispatcher), each with a check the owner can run (e.g. after the first Sunday 09:00 ET, `gh run list --workflow rate-and-predict.yml --event workflow_dispatch --limit 1` shows a run started within 5 minutes of it).

## Out of scope

- The pick writer's rules (TASK-045) and the staged statuses (TASK-044).
- Season simulations, unit ratings, SOR and remaining SOS in the weekly job (Phase 5, M9 and M18).
- The `scores` job (M6.8), watchlist alerts from the `lines` job (M11) and weather snapshots (M10).
- Publishing backtest metrics to `model_runs` (M14.1) and the API or UI that shows picks (M5, M7).
- Running a release or the workflow on `main`: the owner does both.

## Files likely touched

- `python/engine/src/engine/jobs.py`: the `rate-and-predict` kind and the `lines` re-evaluation.
- `python/engine/src/engine/cli.py`: `engine job rate-and-predict`, and `engine promote` if the plan adds it.
- `python/engine/src/engine/publish/models.py`: rate under the job's live path and as a `scheduled` run.
- `python/engine/tests/test_jobs.py`: AC-1 to AC-3.
- `.github/workflows/rate-and-predict.yml` (new): AC-4.
- `infra/dispatcher/src/index.ts`, `infra/dispatcher/src/index.test.ts`: the Sunday 09:00 entry.
- `README.md` › Jobs, › Dispatcher: AC-5.
- `docs/02-architecture.md` › Components › 4 Jobs: AC-5.
- `docs/owner-checklist.md`: AC-5.
- `docs/decisions.md`: how the job runs, as a D-### row.

## Verification

- Automated: the tests above; `pnpm --dir infra/dispatcher exec vitest run`; `pnpm test`; the "Changed workflow run on the branch" ready gate.
- Manual: on the dev DB, `engine job rate-and-predict --target dev` → the summary lists the week, the run id and counts of predictions and picks, and `SELECT * FROM current_picks` shows the week's picks; then `engine job lines --target dev` with no line change → no new `picks` row.

## Follow-ups

_Work noticed during this task and deliberately left out. Each bullet ends `→ <path> § <section>` (where it was placed) or `→ not tracked: <reason>`. See `.claude/skills/track-follow-ups/classify.md`; the PR's Follow-ups section is copied from here._

- Rate, predict and pick the postseason (bowls and CFP, D-131's postseason week 1): `team_ratings` and `model_runs` have no season type, so it needs a schema change; it should land before the first bowl (about 2026-12-13) (approved at plan) → new Draft task + `docs/08-tasklist.md` § M4
- A game postponed to later in the season keeps its old week "not yet kicked off", so `lines` (and this job, which shares its week rule) stays on that week until it's played (approved at plan) → the new postseason task's Context

## Plan

Approved 2026-11-02, with the AC-1, AC-2, AC-3 and AC-5 wording changes above (the owner's yes at the plan gate: v1 stays `candidate`, D-144) and a `dry_run` branch run of the workflow against production at the ready gate.

**Measured first** (local lake, 2026-11-02): copying all 825 raw files into a scratch lake and rebuilding took 38 s, the checks under 1 s, `harness.load` 2 s, and fitting week 10 of 2026 with the holdout's settings 14 s (63 predictions, 250 teams, every one in 2026's staged `team_seasons`, so production's 2026-only `teams` covers them).

**Decisions**
1. **Version:** the workflow names it (`--spec engine/specs/efficiency-v1.json --choices <settings> --version v1.0`, name from the spec's base). The job finds the live version by (cfb, spread, name, version) or creates it as `candidate` from the spec file; one with another stored spec is refused (exit 2). No promote step. M23.1 (D-147) later rates every active version instead.
2. **2026 settings:** `engine backtest --spec engine/specs/efficiency-v1.json --seasons 2026`, run once; its `run.json` is committed as `python/engine/specs/efficiency-v1-2026.run.json`. The harness never tunes on holdout seasons, so 2026 tunes on 2015–2023: the settings the holdout examined.
3. **Postseason:** not in this task (schema change). A Sunday whose coming week is postseason, or with no week left, exits 0 and says so.
4. **Branch run:** a `dry_run` dispatch input (default `false`) runs every step against production and rolls the transaction back at the end. The dispatcher and the fallback cron run for real.
5. **Lines:** after the snapshot publish commits, a second transaction (READ COMMITTED; *schema review R1:* pinned on the jobs' engine, not left to the server's default, and `retired` versions skipped) re-evaluates, for each version with a succeeded `scheduled` run in the season, its newest such run's week at the job's clock; the writer skips games past their cutoff. A pick failure rolls back the picks only and exits 1; the snapshots stay. Picks read `scheduled` runs only (`write_picks(..., run_types=)`).

**Steps**
1. `engine/jobs.py`: `rate_and_predict(lake, url, *, spec, run, name, version, target, dry_run, summary)`: the coming week from R2's raw `/games` (`due_weeks("lines", ...)`), exit 0 when it isn't regular season; settings (`models.settings`, exit 2); sync every season's raw files to a scratch `LocalLake`, rebuild, check (exit 1 before the DB); `models.fit_week`; one transaction: find or create the version, a `scheduled` run with its ratings and predictions (`models.write`), then `write_picks(..., run_types=("scheduled",))`; roll back on any error, or at the end under `dry_run`. Zero CFBD calls: no client is built. `run("lines")` gains the re-evaluation after the publish. Summaries: week, version, run id and status, counts of ratings, predictions, picks and passes, and the predicted games still before their cutoff, so "no predictions" and "no line moved" read differently.
2. `publish/models.py`: `write(..., run_type="adhoc", status="dev")` (the run's type; a new version's status). `publish/picks.py`: `write_picks(..., run_types=RUN_TYPES)`; `PickSummary` gains `games` and `open`.
3. `cli.py`: `engine job rate-and-predict --target dev|live --spec FILE --choices RUN_JSON [--name] [--version] [--dry-run] [--summary]`; exit codes as the other jobs (1 check or fit failed, 2 refused).
4. Run the 2026 backtest and commit its `run.json`.
5. `.github/workflows/rate-and-predict.yml`: `workflow_dispatch` (`fallback_cron`, `dry_run`) and the fallback cron `0 15 * * 0`, `skip-if-dispatched`, `lake-publish`, `timeout-minutes: 10`, `LIVE=true`, R2 and `PRODUCTION_DATABASE_URL_UNPOOLED` only (no CFBD key). `infra/dispatcher`: `SCHEDULE` gains `rate-and-predict.yml` Sun 09:00, with a Vitest case for the slot in EDT and EST.
6. Docs: README › Jobs (row, steps, exits) and › Dispatcher (row); 02 › Components › 4 Jobs (built); `docs/model-guide.md` M4; D-149; Owner checklist (redeploy the dispatcher, with the `gh run list` check; production migrated to `main`'s head by a release before the first Sunday run).

**Files:** `python/engine/src/engine/jobs.py`, `cli.py`, `publish/models.py`, `publish/picks.py`; `python/engine/tests/test_jobs.py`, `python/engine/tests/test_rate_and_predict.py` (new; the DB-backed AC-1 to AC-3 tests); `python/engine/specs/efficiency-v1-2026.run.json` (new); `.github/workflows/rate-and-predict.yml` (new); `infra/dispatcher/src/index.ts`, `index.test.ts`; `README.md`; `docs/02-architecture.md`; `docs/model-guide.md`; `docs/owner-checklist.md`; `docs/decisions.md`; the new postseason task and `docs/08-tasklist.md`.

**Tests**
- AC-1: `test_rate_and_predict.py::test_weekly_run_writes_run_ratings_predictions_and_picks` (scheduled run, ratings, a prediction per week game but the canceled one, picks; call ledger unchanged; no CFBD client).
- AC-2: `test_settings_for_the_season_unresolved_exits_2`, `test_a_version_with_another_spec_exits_2`, `test_failed_check_exits_1_before_the_database`, `test_second_run_adds_a_run_but_no_unchanged_pick`.
- AC-3: `test_lines_gains_a_pick_when_the_line_crosses`, `test_lines_writes_nothing_when_nothing_changes`, `test_lines_writes_nothing_after_kickoff`; `test_jobs.py::test_lines_reevaluates_after_the_publish_commits`.
- AC-4: `test_jobs.py`'s workflow tests extended to `rate-and-predict.yml`; Vitest "fires rate-and-predict Sun 09:00 ET"; the dry branch run.
- AC-5: doc review.

**Risks:** production not yet migrated through 0004 and the pick views (the dry branch run shows it); the postponed-game week rule (follow-up).

## Review log

_Filled by /implement-task. One line per round._

## Blocked

_Only if status is Blocked: what failed, what was tried, best hypothesis, decision needed._

## Metrics

- Verify rounds:
- Review rounds:
- First-pass AC FAILs:
- Plan revisions after approval:
