---
id: TASK-074
title: Refresh this week's scores during game windows (the scores job)
status: In progress
depends_on: [TASK-022, TASK-069]
size: M
model: opus
autonomy: attended
ui: false
plan_status: approved
planned_at_commit: 752c602
---

# TASK-074 — Refresh this week's scores during game windows (the scores job)

## Goal

During game windows the app's scores and game statuses refresh about every 30 minutes, for CFB games and the NFL games on a contest slate. The record strip and contest results then grade picks as games finish.

## Context

- Task list: `docs/08-tasklist.md` › M6 › M6.8. Sized M, not the task list's S: a new job, its workflow and dispatcher entries, and the live-clock columns don't fit in 4 files.
- Architecture: `docs/02-architecture.md` › Jobs (`scores`: about every 30 min Thu–Sat evenings and Sat all day; CFBD's scoreboard, about 25 calls a week; NFL contest games from nflverse; near-live only), › Components › 4 (the dispatcher starts every job).
- Data model: `docs/03-data-model.md` › Games & market (`games` upserted by source key), › Proposed additions from the 2026-11-01 features › **Live game clock (M6.8, from TASK-055)**: two nullable columns, e.g. `period` and `clock`, filled by the `scores` job from CFBD's `/scoreboard` and cleared when the game is final. **Schema change: stop and ask** at the plan gate.
- Product: `docs/01-product.md` › Observable outcomes › F-32 AC-2 (a live pick that's behind shows as live, never as lost, until final).
- Decisions: D-092 (Saturday scores ≤ 60 min old), D-114 and D-121 (call budget; never re-fetch completed weeks), D-122 (dispatcher, quarter-hour slots, never 01:00–02:59 ET), D-123 (`engine job results|lines` entry point, the summary, the `lake-publish` concurrency group, the `skip-if-dispatched` fallback; `/scoreboard` is already in the endpoint registry, `python/engine/src/engine/ingest/endpoints.py`).
- **NFL windows:** 02's windows (Thu–Sat) predate NFL contest games, which also play Sunday, Monday and Thursday nights. The plan sets the NFL slots. The NFL refresh is TASK-069's nflverse pull (no CFBD calls), run only while a contest has an NFL game that has kicked off and isn't final.
- **Grading stays in the views** (hard rule 1): this job writes `games` only. The `results` job stays the source of box scores, advanced stats and play-by-play.
- **Raw lake:** each scoreboard pull is a new raw file (append-only), so `transform --rebuild` reproduces what the job published.
- `/slate` and the screens showing the clock ("Q3 9:12") are out of scope. The clock columns are filled here, and showing them is a follow-up this task places.

## Acceptance criteria

- [ ] AC-1: `engine job scores --target dev|live` makes one CFBD `/scoreboard` call per run, saves the response as a new raw-lake file, and updates each matched CFB game's `status` and points by its source key. A game the scoreboard reports in progress becomes `in_progress` with its points, and a completed one becomes `final`. It never creates a game, and it never writes lines, ratings, predictions or picks (test on a recorded scoreboard).
- [ ] AC-2: `games` gains nullable `period` and `clock`, set from the scoreboard while a game is in progress and NULL once it's final. The migration runs up → down → up on the test DB, and `pnpm db:check` passes.
- [ ] AC-3: Running again on the same scoreboard changes no row. A game already `final` is never moved back to `in_progress` or `scheduled` by a later scoreboard (test).
- [ ] AC-4: When a contest has an NFL game that has kicked off and isn't final, the run also refreshes NFL scores through TASK-069's nflverse pull, with no CFBD call. With no such game, it skips the pull.
- [ ] AC-5: `.github/workflows/scores.yml` runs the job on `workflow_dispatch` in the `lake-publish` concurrency group, with `timeout-minutes` ≤ 10. The dispatcher's `SCHEDULE` starts it every 30 minutes across the plan's CFB and NFL windows. An `infra/dispatcher/src/index.test.ts` case shows `due()` fires at a window's slots and not outside them. The workflow runs green on the branch (ready gate).
- [ ] AC-6: The run summary reports this run's calls and the month's total, plus games updated by sport. Exceeding the call budget exits 3 without publishing, as the other jobs do.

## Out of scope

- Showing the live clock on This Week, Game Detail or Contest (follow-up: `/slate` and the screens).
- Box scores, advanced stats and play-by-play (the `results` job).
- Grading or storing results (views, TASK-068 and D-142).
- Push alerts when a game finishes (Phase 5).
- An NFL model.

## Files likely touched

- `python/engine/src/engine/jobs.py`: the `scores` job
- `python/engine/src/engine/cli.py`: `engine job scores`
- `python/engine/src/engine/publish/reference.py` (or a new `publish/scores.py`): the status, points and clock update
- `python/engine/tests/test_jobs.py` (or a new `test_scores_job.py`) and a recorded scoreboard under `python/engine/tests/fixtures/`
- `python/db/migrations/versions/0008_game_clock.py`: new. `python/db/src/db/models.py`
- `.github/workflows/scores.yml`: new
- `infra/dispatcher/src/index.ts`, `infra/dispatcher/src/index.test.ts`: the slots
- `docs/02-architecture.md` › Jobs, `docs/03-data-model.md` › Games & market (and remove the proposal), `docs/decisions.md`, `README.md` › Dispatcher

## Verification

- Automated: `uv --directory python run pytest engine/tests/test_jobs.py` and `pnpm --dir infra/dispatcher exec vitest run src/index.test.ts` pass, and `pnpm db:check` passes.
- Manual: `gh workflow run scores.yml --ref <branch>` then `gh run watch <id> --exit-status` → expected: green, and the summary shows 1 CFBD call and the games updated.

## Follow-ups

_Work noticed during this task and deliberately left out. Each bullet ends `→ <path> § <section>` (where it was placed) or `→ not tracked: <reason>`. See `.claude/skills/track-follow-ups/classify.md`; the PR's Follow-ups section is copied from here._

- Showing the live clock on `/slate`, This Week, Game Detail and Contest (approved at plan) → a new Draft task and its stub in `docs/08-tasklist.md` › M6
- Deploy the dispatcher's new slots only after the release that applies `0009` (approved at plan) → `docs/owner-checklist.md` § Actions
- Weekday CFB games (Tue/Wed in November) and NFL games on other days aren't in the windows; the next 08:00 `lines` run catches them (approved at plan) → recorded in the task's decision, not tracked

## Plan

_Written by /plan-batch or /implement-task Phase 1. Approved by the user (plan_status: approved) before any code is written._

Approved 2026-11-20 (schema change included).

**Schema:** migration `0009_game_clock` (0008 is taken): `games.period smallint NULL`, `games.clock text NULL` (CFBD's `"MM:SS"` as given), CHECK `status = 'in_progress' OR (period IS NULL AND clock IS NULL)`.

**Steps**
1. Migration and `models.Game` columns plus the CHECK; an up → down → up test with row values. The staged publish (`publish/staging.py`) sends `period`/`clock` NULL, so a `results`/`lines` publish that marks a game final clears its clock (staged games are never in progress).
2. `engine/scores.py`: one counted `/scoreboard` call (`endpoints.fetch`, new raw file). Each record matched by `(sport cfb, source cfbd, source_id)`, never inserted. In progress → `in_progress`, points, period, clock; completed → `final`, points, NULL clock; scheduled → nothing. A row already `final` is never touched; every write is `WHERE (status, points, period, clock) IS DISTINCT FROM` the new values, so a rerun changes no row. Unmatched records and completed records without points are listed in the summary.
3. NFL: when a non-deleted contest's `contest_lines` hold an NFL game kicked off in the last 12 h, not `final` or `canceled`, run TASK-069's path (`nflverse.pull` → `transform.nfl.stage` → `publish_nfl`), no CFBD call; otherwise skip. A failed download still commits the CFB updates, names the failure and exits 1 (as `lines`).
4. `engine job scores --target dev|live [--sport all|nfl] [--summary PATH]`: summary has calls this run, the month's total, games updated by sport; the budget exits 3 before anything is written, a refusal 2. `--sport nfl` makes no CFBD call.
5. `.github/workflows/scores.yml`: `workflow_dispatch` only (input `sport`), `lake-publish` concurrency, `timeout-minutes: 10`; no fallback cron (GitHub's schedule starts 5–8 h late, D-122, useless for a 30-minute job).
6. Dispatcher: a helper builds 30-minute slots. CFB+NFL: Thu and Fri 19:30–00:30, Sat 12:00–00:30 and Sun 03:00. NFL only (`inputs: {sport: "nfl"}`): Sun 13:30–00:30, Mon 20:30–00:30. About 49 CFBD calls a week (≈210 of 5,000 a month).
7. Docs: 02 › Jobs (windows, calls, no fallback), 03 › Games & market (the columns; the proposal removed), decision D-178 (incl. the rebuild limit below), README › Dispatcher.

**Files:** `python/engine/src/engine/scores.py` (new, instead of growing `jobs.py`), `cli.py`, `publish/staging.py`, `python/db/migrations/versions/0009_game_clock.py` (new), `python/db/src/db/models.py`, `python/engine/tests/test_scores_job.py` (new), `python/engine/tests/fixtures/cfbd_scoreboard_sample.json` (new), `python/db/tests/test_game_clock_schema.py` (new), `.github/workflows/scores.yml` (new), `infra/dispatcher/src/index.ts`, `index.test.ts`, `python/db/tests/test_ci_config.py` (if it lists workflows), docs 02, 03, decisions, README, `docs/08-tasklist.md`, owner checklist, the new task file.

**Test strategy:** AC-1/3/6 `test_scores_job.py` on the recorded scoreboard (written to CFBD's documented `ScoreboardGame` shape; R2 isn't readable locally) against the test DB; AC-4 with and without a live contest NFL game; AC-2 `test_game_clock_schema.py`; AC-5 `index.test.ts` slots in and out of windows plus the 01:00–02:59 rule.

**Accepted at the gate:**
- The raw scoreboard files are kept, but `transform --rebuild` doesn't read them: a rebuild reproduces final scores (from `/games` after `results`), not the transient in-progress status and clock. Recorded in D-178.
- AC-5's branch run can't pass before merge (the file isn't on `main`, production lacks `0009`): checked after merge and release with `gh workflow run scores.yml`; the dispatcher is deployed after that (Owner checklist).
- A Thu/Fri 19:00 `lines` publish during a live game sets it back to `scheduled` until the next scores run (≤ 30 min).

## Review log

_Filled by /implement-task. One line per round._

## Blocked

_Only if status is Blocked: what failed, what was tried, best hypothesis, decision needed._

## Metrics

- Verify rounds:
- Review rounds:
- First-pass AC FAILs:
- Plan revisions after approval:
