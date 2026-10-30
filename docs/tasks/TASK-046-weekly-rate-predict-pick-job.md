---
id: TASK-046
title: Run the production weekly cycle: rate, predict and pick
status: Ready
depends_on: [TASK-043, TASK-044, TASK-045]
size: M
model: opus
autonomy: attended
ui: false
plan_status: none
planned_at_commit:
---

# TASK-046 — Run the production weekly cycle: rate, predict and pick

## Goal

Every Sunday morning in season, production gains new ratings, predictions and picks for the coming week from the promoted model with nobody running anything, and when lines move during the week the picks are re-evaluated. Paper trading of 2026 starts with this task's first scheduled run.

## Context

- Task list: `docs/08-tasklist.md` › M4 › M4.8 (split: TASK-044 stages canceled games and moves `engine rate` onto the harness's contexts; TASK-045 is the pick writer; this task runs both on production).
- Roadmap: `docs/06-roadmap.md` › Phase 3 — "Production weekly cycle live: rate → predict → pick (paper trading 2026)"; acceptance "weekly picks are generated automatically and graded by the views".
- Architecture: `docs/02-architecture.md` › Components › 4 Jobs (`rate-and-predict` Sun 9am; `lines` re-evaluates picks when lines move; the dispatcher's `SCHEDULE` lists only the jobs built); › Release & operations; › Non-functional requirements (D-092: predictions out by Sun 10 AM ET, each job ≤ 10 min).
- Model: `docs/04-model.md` § 4 (re-evaluate when the line moves); § 9.1 (2026 is live paper trading).
- Decisions: D-092, D-122 (the dispatcher starts jobs with `workflow_dispatch`), D-123 (how `results` and `lines` run: pull into R2, stage one season in a scratch lake, check, publish in one transaction), D-129 (the late-fallback cron and `skip-if-dispatched`), D-131 (the postseason is one week), D-134 (`engine rate --choices` resolves a season's tuned settings from a backtest's `run.json`), D-140, D-141, D-142, and TASK-043's go/no-go row (which version runs).
- Code today: `engine job results|lines --target dev|live` (`engine/jobs.py`, `.github/workflows/results.yml`, `lines.yml`); `engine rate --target dev|test` (`publish/models.py`), refused under `LIVE=true`, rates regular-season weeks only and needs `--choices` for a tuned spec; the dispatcher's `SCHEDULE` (`infra/dispatcher/src/index.ts`); README › Jobs and › Dispatcher › Add a job.
- *From TASK-022 (PR #62):* the `results` and `lines` jobs stage one season in a scratch lake, so they never refresh R2 `staging/` or the feature tables; `rate-and-predict` needs its own rebuild of history.
- **Decide at the plan gate:**
  - **Which version and settings:** the job rates with the target DB's `production` (cfb, spread) version, so how v1.0 and its status reach production (an `engine promote` the owner runs, or a step in the job), per TASK-043's call; and where the 2026 settings come from, since `run.json` `choices` hold only scored seasons (a backtest that scores 2026, tuned on 2015–2025 now the holdout is spent, with its `run.json` in R2 or in the repo).
  - **Postseason:** whether the job rates postseason week 1 (the bowls and CFP, D-131) in this task or a follow-up does.
  - **Branch run:** README's ready gate runs a changed workflow on the branch, and this one writes to production: whether that run targets production (stop and ask first) or the workflow gains an input that skips the publish.
  - **Lines:** whether `engine job lines` re-evaluates picks in the same transaction as its snapshot publish or after it.

## Acceptance criteria

- [ ] AC-1: Given a lake fixture and the test DB holding a `production` (cfb, spread) version, `engine job rate-and-predict --target dev` with the clock on a Sunday in season rebuilds every staged season from the raw lake in a scratch lake with zero CFBD calls (the call ledger is unchanged), and in one transaction inserts a `scheduled` model run, its ratings, a prediction for every staged game of the coming week that will be played (none for a canceled one), and TASK-045's picks for them (test).
- [ ] AC-2: With no `production` version, or one whose settings for the season can't be resolved, the job exits 2 and writes nothing; a failed data-quality check exits 1 before the database is opened; a second run in the same week inserts a new run and predictions but no pick whose side and tier are unchanged (tests).
- [ ] AC-3: `engine job lines`, after publishing new snapshots, re-evaluates the coming week's picks from the production version's newest `scheduled` run against the newest snapshots: a test where a line moves across the threshold gains a pick, one where nothing changes gains no row, and a game already kicked off gains none.
- [ ] AC-4: `.github/workflows/rate-and-predict.yml` runs the job under `LIVE=true` with `timeout-minutes: 10`, in the `lake-publish` concurrency group, with a fallback cron and `skip-if-dispatched` as `results.yml` has; the dispatcher's `SCHEDULE` gains `rate-and-predict.yml` on Sun at 09:00 ET with a Vitest case for that slot; the workflow's branch run (the ready gate, as the plan settles) passes in under 10 minutes.
- [ ] AC-5: README › Jobs gains the workflow's row (time, fallback cron, calls a run: 0) and what each step does, 02 › Components › 4 Jobs says `rate-and-predict` and the `lines` re-evaluation are built, and `docs/owner-checklist.md` lists each owner action the plan names (redeploy the dispatcher; promote v1.0 if that's an owner step), each with a check the owner can run (e.g. after the first Sunday 09:00 ET, `gh run list --workflow rate-and-predict.yml --event workflow_dispatch --limit 1` shows a run started within 5 minutes of it).

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
