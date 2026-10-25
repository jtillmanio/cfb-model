---
id: TASK-034
title: Add model_versions, model_runs, team_ratings and predictions
status: Ready
depends_on: [TASK-029]
size: M
model: opus
autonomy: attended
ui: false
plan_status: none
planned_at_commit:
---

# TASK-034 — Add model_versions, model_runs, team_ratings and predictions

## Goal

The serving database can hold model versions, the runs that executed them, and the ratings and predictions each run produced, with ratings and predictions that can never be changed once written, and the test database is seeded with the fixture's model registry, ratings and predictions.

## Context

- Task list: `docs/08-tasklist.md` › M3 › M3.6.
- **Schema change: stop and ask at the plan gate** (CLAUDE.md › Stop and ask before). The plan shows the full DDL for approval.
- Data model: `docs/03-data-model.md` › Models & outputs (`model_versions`, `model_runs`, `team_ratings`, `predictions`; one `production` version per sport per market by partial unique index; `fitted_params` and `metrics` jsonb; rank is a view, not a column); › Conventions (soft delete on lab models; never store derived data; model outputs are stored immutably).
- Architecture: `docs/02-architecture.md` › Testing strategy › Seed data (Model registry: v1.0 production with spec and fitted params per `design/sample-data.md` § 8, v1.1 candidate, v1.2-dev, 7 variants since the last promotion, backtest metrics in `model_runs.metrics`; Ratings entering weeks 5 and 6, so Δ computes; Predictions for every week-6 game, with Texas vs Oklahoma's drivers and σ); › Levels › Integration: database (one head, `alembic check`, insert-only test).
- Decisions: D-050 (`spec` in `model_versions`, learned weights in `model_runs.fitted_params`), D-089 (fixture rows load into the test DB only; extended only by the task that owns the table), D-115 (the `line_snapshots` triggers are the insert-only pattern), D-117 (unit ratings go in `team_ratings.components` and `st_rating`).
- Rules: hard rule 2 (ratings and predictions are insert-only: no UPDATE or DELETE); hard rule 1 (no rank or record columns); hard rule 6 (never edit a migration already on `main`); `.claude/rules/database.md`.
- Pattern: `python/db/migrations/versions/0002_market_reference.py` (append-only triggers on UPDATE, DELETE and a statement-level TRUNCATE trigger) and `python/db/tests/test_market_schema.py`; the seed is `python/engine/src/engine/fixture.py` with JSON in `python/db/seeds/fixture/`.
- Depends on TASK-029 so the fixture's v1.0 spec validates as a `ModelSpec`.
- **Settled when this task was written (2026-10-25, owner accepted the recommendations; the plan still shows the full DDL for approval, and 03 is amended to match):**
  - **`market` on `model_versions`:** 03 asks for one production version "per sport per market" but has no `market` column. Add `market text NOT NULL` with a CHECK of `spread` or `total` (no default; every version says which), and the partial unique index is `(sport_id, market) WHERE status = 'production' AND deleted_at IS NULL`. Adding it now costs one column; adding it once totals exist (Phase 7) would mean rebuilding the index on a table with live rows.
  - **`team_ratings` key:** 03's PK `(model_version_id, team_id, season, week)` allows one row per version and week, which blocks the new rows a re-run inserts (CLAUDE.md › Domain conventions). The PK is `(model_run_id, team_id, season, week)`, with an index on `(model_version_id, season, week)` for the views' reads.
  - **Statuses change in place:** `model_runs.status` (queued → running → succeeded/failed) and `model_versions.status` (dev → candidate → production → retired) are a run's and a version's lifecycle, so they're updated. Only `team_ratings` and `predictions` get the insert-only triggers (hard rule 2), and their foreign keys to `model_runs` and `model_versions` are `ON DELETE RESTRICT`, so no run or version with outputs can be deleted.
  - **Fixture predictions:** the fixture has 11 Week 6 games today. This task seeds a v1.0 prediction for each of them; M5.5 seeds the other 43 games behind "54 games" and their predictions with them (a note on M5.5's stub says so).
- *From TASK-029 (feat/029-model-spec-and-core-math):* write the fixture's v1.0 spec in the v1 shape (D-130, `engine/core/spec.py`): `base: efficiency`, inputs from the registry (`pass_epa_per_play`, `rush_epa_per_play`, `success_rate`), no `name` (it's the `model_versions` column). `design/sample-data.md` § 8's prior fade (100% → 50% at week 4 → 10% at week 8) isn't linear, so the spec uses `prior.decay: {type: fitted}`; the learned weights it shows go in `fitted_params`.

## Acceptance criteria

- [ ] AC-1: After `pnpm db:migrate:test`, the four tables exist with the columns in 03 › Models & outputs plus `model_versions.market` and the `team_ratings` PK `(model_run_id, team_id, season, week)`, `pnpm db:check` reports one head with the models matching, and the migration runs up → down → up cleanly.
- [ ] AC-2: Inserting a second `production` version for the same sport and market fails on the partial unique index; a `production` version for the same sport with the other market, or a second `candidate` or `dev` version, succeeds; a soft-deleted production version doesn't block a new one; a `market` other than `spread` or `total` is refused.
- [ ] AC-3: UPDATE, DELETE and TRUNCATE on `team_ratings` and on `predictions` each raise an error and leave the rows unchanged; inserting a second run's rows for the same version, team, season and week succeeds.
- [ ] AC-4: On the seeded test DB, the registry holds v1.0 (production), v1.1 (candidate, parent v1.0) and v1.2-dev (dev, parent v1.1); every version's `spec` validates as a `ModelSpec`; v1.0's backtest run carries the validation and holdout summaries from 02 › Seed data in `metrics` and its learned weights in `fitted_params`.
- [ ] AC-5: On the seeded test DB, every seeded FBS team has a rating entering weeks 5 and 6 of 2026 under v1.0, ordered so that week 6 reproduces the `design/sample-data.md` § 4 order and its Δ from week 5, and each of the 11 seeded week-6 games has one v1.0 prediction; Texas vs Oklahoma's has `drivers` and `margin_sd` set.

## Out of scope

- Publishing real ratings or predictions from the engine, and the `team_rankings` / `team_schedule_strength` views (TASK-035).
- `picks` and `season_simulations` (M4.5, M9).
- Unit ratings in `components` and `st_rating` beyond what the fixture sets (M18).
- Any API route reading these tables (M5 onward).

## Files likely touched

- `python/db/migrations/versions/0003_models.py`: the four tables, the partial unique index, the insert-only triggers (new).
- `python/db/src/db/models.py`: SQLAlchemy models.
- `python/db/seeds/fixture/models.json`: versions, runs, ratings and predictions (new).
- `python/engine/src/engine/fixture.py`: seed the new rows.
- `python/db/tests/test_model_schema.py`: AC-1 to AC-5 (new).
- `docs/03-data-model.md` › Models & outputs: the amended columns and keys.
- `docs/decisions.md`: the schema choices as a D-### row.

## Verification

- Automated: `test_model_schema.py`; `pnpm db:check`; `pnpm test`.
- Manual: `pnpm db:migrate:test`, `pnpm db:seed`, then in `psql` → `SELECT name, version, status FROM model_versions` shows three rows; `UPDATE team_ratings SET rating = 0` fails.

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
