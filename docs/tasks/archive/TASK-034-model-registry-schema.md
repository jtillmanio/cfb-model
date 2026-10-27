---
id: TASK-034
title: Add model_versions, model_runs, team_ratings and predictions
status: Done
depends_on: [TASK-029]
size: M
model: opus
autonomy: attended
ui: false
plan_status: approved
planned_at_commit: 8a0c017
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
- *From TASK-029 (PR #87):* write the fixture's v1.0 spec in the v1 shape (D-130, `engine/core/spec.py`): `base: efficiency`, inputs from the registry (`pass_epa_per_play`, `rush_epa_per_play`, `success_rate`), no `name` (it's the `model_versions` column). `design/sample-data.md` § 8's prior fade (100% → 50% at week 4 → 10% at week 8) isn't linear, so the spec uses `prior.decay: {type: fitted}`; the learned weights it shows go in `fitted_params`.
- *From TASK-030 (PR #90), open question for the plan:* until `model_runs` exists, backtest runs live in the lake: `backtests/<run>/predictions.parquet` and `run.json`, and each holdout opening is a record under `backtests/holdout/` (time, spec hash, seasons, reason, model; 03 › Lake layout › Backtests, D-131). Does `model_runs` carry a run's holdout flag and reason now, so the Lab can count holdout openings from Postgres (04 § 6), or does that wait for the work that moves backtest runs there?

## Acceptance criteria

- [x] AC-1: After `pnpm db:migrate:test`, the four tables exist with the columns in 03 › Models & outputs plus `model_versions.market` and the `team_ratings` PK `(model_run_id, team_id, season, week)`, `pnpm db:check` reports one head with the models matching, and the migration runs up → down → up cleanly.
- [x] AC-2: Inserting a second `production` version for the same sport and market fails on the partial unique index; a `production` version for the same sport with the other market, or a second `candidate` or `dev` version, succeeds; a soft-deleted production version doesn't block a new one; a `market` other than `spread` or `total` is refused.
- [x] AC-3: UPDATE, DELETE and TRUNCATE on `team_ratings` and on `predictions` each raise an error and leave the rows unchanged; inserting a second run's rows for the same version, team, season and week succeeds.
- [x] AC-4: On the seeded test DB, the registry holds v1.0 (production), v1.1 (candidate, parent v1.0) and v1.2-dev (dev, parent v1.1); every version's `spec` validates as a `ModelSpec`; v1.0's backtest run carries the validation and holdout summaries from 02 › Seed data in `metrics` and its learned weights in `fitted_params`.
- [x] AC-5: On the seeded test DB, every seeded FBS team has a rating entering weeks 5 and 6 of 2026 under v1.0, ordered so that week 6 reproduces the `design/sample-data.md` § 4 order and its Δ from week 5, and each of the 11 seeded week-6 games has one v1.0 prediction; Texas vs Oklahoma's has `drivers` and `margin_sd` set.

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

- The fixture's v1.0 is `production` for cfb/spread, so TASK-035's tests must retire it or use another market when they insert a production version → docs/tasks/TASK-035-publish-ratings-and-ranking-views.md § Context (approved at plan)
- No holdout flag or reason on `model_runs` yet; M14.4 owns "holdout use recorded" → docs/08-tasklist.md § M14.4 (approved at plan)
- `docs/03-data-model.md` › Lake layout › Backtests says backtest runs move to `model_runs` "planned: TASK-034 and later"; reword it to say the move waits on M14.1 → docs/03-data-model.md § Lake layout (approved at plan)
- The fixture's `model_runs.metrics` (`validation`, `holdout`, `accuracy`, `pick_buckets`, `calibration`) is a placeholder shape; M14.1 writes the real one from `engine.backtest.metrics.Metrics` and must match it or update the fixture, since M7.4 reads it → docs/08-tasklist.md § M14.1 (approved at plan, revision 1)
- 02 › Seed data's "7 variants since the last promotion" isn't seeded: nothing defines a variant or records when a version was promoted → docs/08-tasklist.md § M14.4 (approved at plan, revision 1)
- Schema review: `rating`, `pred_margin`, `pred_total` and `margin_sd` accept NaN and ±Infinity, and insert-only rows can't be fixed; the publish path should refuse them → docs/tasks/TASK-035-publish-ratings-and-ranking-views.md § Context
- Schema review: no `team_ratings` index leads with `team_id`; per-team reads (trajectory, team page) go through `(model_version_id, season, week)` → docs/tasks/TASK-035-publish-ratings-and-ranking-views.md § Context
- Schema review: a run's `season`, `week`, `as_of` and `fitted_params` can still be updated after it has outputs (D-135 put no trigger on `model_runs`); a column-scoped trigger would close it → docs/08-tasklist.md § M14.2
- Schema review: the fixture's run `as_of` is the calendar week start, while D-127's feature `as_of` is the week's first kickoff; which one a published run carries is open → docs/tasks/TASK-035-publish-ratings-and-ranking-views.md § Context
- Spec review: AC-5's text promises § 4's Δ, which can't be reproduced; the test asserts the owner-approved Δ (Plan › Decisions made at the gate, 1). Proposed wording: "…week 6 reproduces the § 4 order, and its Δ from week 5 is the rank change between the seeded week-5 and week-6 ratings (the top 10's week 5 from `traj[4]` in rankings-data.js)" → not tracked: the ACs are the owner's; proposed in the PR for the owner to accept or leave
- Roadmap `docs/06-roadmap.md` › Phase 2's `model_versions` / … / `predictions` + publish item is only partly delivered (publish is TASK-035) and stays open → not tracked: already tracked in TASK-035 § Context (Roadmap)

## Plan

_Approved by the owner at the plan gate, 2026-10-27 (session reply "approve"), including the DDL, the two decisions and the two follow-ups below._

**DDL (migration `0003_models.py`; ids `bigint identity`; every table has `created_at`):**
- `model_versions`: `sport_id` FK, `market` text NOT NULL CHECK in (spread, total), `name`, `version` (stored as `v1.0`), `description` NULL, `spec` jsonb NOT NULL (object), `spec_schema_version` int, `parent_version_id` self-FK NULL, `created_by` CHECK (system, user), `code_sha` NULL, `status` CHECK (dev, candidate, production, retired), `deleted_at` NULL. UQ `(sport_id, market, name, version)` WHERE `deleted_at IS NULL`; UQ `(sport_id, market)` WHERE `status = 'production' AND deleted_at IS NULL`.
- `model_runs`: `model_version_id` FK RESTRICT, `run_type` CHECK (backtest, scheduled, adhoc), `season`/`week`/`as_of` NULL, `status` CHECK (queued, running, succeeded, failed) default queued, `requested_at` default now(), `started_at`/`finished_at` NULL, `github_run_id` bigint NULL, `fitted_params` jsonb NULL, `metrics` jsonb NULL, `error` NULL. CHECK `run_type = 'backtest' OR (season, week, as_of all NOT NULL)`; UQ `(id, model_version_id)`; IDX `(model_version_id)`.
- `team_ratings`: `model_run_id`, `model_version_id`, `team_id` FK, `season`, `week`, `as_of` NOT NULL, `rating` double NOT NULL, `off_rating`/`def_rating`/`st_rating` NULL, `prior_weight` NULL CHECK 0..1, `components` jsonb NULL. PK `(model_run_id, team_id, season, week)`; IDX `(model_version_id, season, week)`; composite FK `(model_run_id, model_version_id)` → `model_runs(id, model_version_id)` ON DELETE RESTRICT.
- `predictions`: `id` PK, `model_run_id`, `model_version_id` (same composite FK), `game_id` FK RESTRICT, `pred_margin` double NOT NULL, `pred_total` NULL, `home_win_prob` NOT NULL CHECK 0..1, `margin_sd` NULL CHECK > 0, `drivers` jsonb NULL, `adjustments_applied` jsonb NULL. UQ `(model_run_id, game_id)`; IDX `(game_id, model_version_id, created_at DESC)`.
- Insert-only: one function `forbid_model_output_changes()` (names the table through `TG_TABLE_NAME`); row triggers BEFORE UPDATE OR DELETE and a statement-level TRUNCATE trigger on `team_ratings` and `predictions` (the 0002 pattern). `model_runs.status` and `model_versions.status` are updated in place.

**Decisions made at the gate:**
1. AC-5's Δ: week-5 ratings for the top 10 come from the `traj` arrays in `design/handoff/designs/rankings-data.js` (entering week 5 = `traj[4]`, entering week 6 = `traj[5]`). Δ then matches `design/sample-data.md` § 4 for Ohio State, Texas, Oregon, Georgia and Penn State, and differs for Oklahoma (▲3, § 4 has ▲5), Ole Miss (▲2, not ▲3), Notre Dame (▼1, not ▼2), LSU (—, not ▼1) and Utah (—, not ▲2), because § 4's own Δ values imply two teams tied at prior rank 9 and two at rank 5. The week-6 order is exact. The AC text is unchanged (the owner's); the test asserts the Δ the seeded week-5 ratings give.
2. No holdout flag or reason on `model_runs` now; M14.4 owns "holdout use recorded".

**Steps (tests first, each shown failing before the change):**
1. `test_model_schema.py`: AC-1 (columns, PK, one head via `alembic check`; an up → down → up run in a scratch schema through `options=-csearch_path`, so the seeded test DB isn't dropped), AC-2 (production index, soft-deleted version, bad market), AC-3 (UPDATE, DELETE, TRUNCATE refused on both tables; a second run's rows for the same version, team, season and week insert), AC-4 and AC-5 against the seeded DB (version statuses and parents, `ModelSpec` validation of every spec, `metrics` and `fitted_params` of v1.0's backtest run, 28 FBS teams rated in weeks 5 and 6, the § 4 order and the Δ above, 11 predictions, Texas vs Oklahoma's `drivers` and `margin_sd`).
2. `0003_models.py` and the four models in `db/models.py`; `pnpm db:migrate:test`, `pnpm db:check`.
3. `python/db/seeds/fixture/models.json` and `engine/fixture.py` (idempotent: versions by `(sport, market, name, version)`, a run by version/type/season/week, outputs `ON CONFLICT DO NOTHING`). v1.0 `base: efficiency` with `pass_epa_per_play`, `rush_epa_per_play`, `success_rate` and `prior.decay: fitted`; § 8 weights in `fitted_params`, § 7 summaries in `metrics`; ratings for 28 FBS teams in weeks 5 and 6 (18 filler teams invented, all below Utah's 15.8), Ohio State's weeks 1–4; the 11 predictions from the § 1 model lines (`home_win_prob` and `pred_margin` verbatim, not recomputed from the ratings), drivers in the home − away sign so they sum to `pred_margin`.
4. Docs: `docs/03-data-model.md` › Models & outputs (the `market` column, the `team_ratings` PK, the composite FK, the `(model_run_id, game_id)` key), D-135 in `docs/decisions.md`.

**Files (6 plus tests/seed):** `0003_models.py`, `db/models.py`, `models.json`, `engine/fixture.py`, `test_model_schema.py`, `docs/03-data-model.md`, `docs/decisions.md`.

**Test strategy:** AC-1 → `test_the_four_tables_exist`, `test_migration_round_trip`; AC-2 → `test_one_production_version_per_sport_and_market`; AC-3 → `test_outputs_are_insert_only`, `test_a_second_run_inserts_its_own_ratings`; AC-4 → `test_seeded_registry`; AC-5 → `test_seeded_ratings_and_week6_order`, `test_seeded_predictions`.

**Revision 1 (2026-10-27, Opus review of the plan at the owner's request; DDL unchanged):**
- Ratings for all 28 FBS teams entering weeks 1–6 (one scheduled v1.0 run per week), the top 10 from the `traj` arrays, so every rated week is a complete table and the Rankings sparklines have data; the 18 filler teams stay below Utah every week.
- Times are explicit, never `now()`: a run's `as_of` is its week's start in the fixture calendar (`week6.json` › `season.weeks`); it finishes at `as_of` + 6 h (Sun 6:00 AM ET), which is also its outputs' `created_at`, so every prediction precedes kickoff and M4.5's "picked Sun 6:10 AM" follows its prediction. Version `created_at` from § 8 (2026-08-20, 2026-09-14, 2026-10-01).
- Backtest runs: v1.0 succeeded (§ 7 summaries, § 8 weights), v1.1 succeeded (MAE 12.8, ATS 54.4%), v1.2-dev running (§ 8 "backtest running").
- Name `power` for all three versions; `code_sha` NULL (no fake sha; the fixture is test-DB only).
- `off_rating`/`def_rating` from § 4 for the top 10 entering week 6; `st_rating` NULL (04 § 10.2: special teams isn't rated yet); filler teams have no unit ratings.
- `drivers` is a list of `{label, points}` (04 § 3), with home/away labels and home − away points summing to `pred_margin`.
- The `success_rate` weight is stored per share (31.0), the registry's unit; § 8's ×0.31 is per percentage point.
- Tuned settings stay `{"tune": [...]}` in the spec; the chosen values are in `fitted_params.choices`, as `run.json` records them.
- Two more follow-ups: the `metrics` shape for M14.1 and the uncounted "7 variants" for M14.4.

**Risks:** the fixture's `production` v1.0 for cfb/spread collides with any production version TASK-035's tests insert (follow-up below); fixture model rows have no `source` column, so the seed finds them by `(sport, market, name, version)`; the scratch-schema round trip must not touch `public`.

## Review log

- Plan: approved 2026-10-27; revision 1 (Opus review at the owner's request, DDL unchanged)
- Verify R1 PASS (typecheck, lint, db:check, pytest 531, vitest, build, e2e 40)
- Audit R1 PASS (AC-1 to AC-5 PROVEN; base run in a scratch schema, shared test DB untouched)
- Spec R1 APPROVE (AC-5 wording note) | Schema R1 APPROVE (5 minor findings, all placed as follow-ups)

## Blocked

_Only if status is Blocked: what failed, what was tried, best hypothesis, decision needed._

## Metrics

- Verify rounds: 1
- Review rounds: 1 (spec), 1 (schema); audit 1
- First-pass AC FAILs: 0
- Plan revisions after approval: 1 (the owner asked for an Opus review of the approved plan; seed details, DDL unchanged)
