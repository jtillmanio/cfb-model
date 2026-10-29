---
id: TASK-040
title: Add the picks table
status: Done
depends_on: [TASK-034]
size: M
model: opus
autonomy: attended
ui: false
plan_status: approved
planned_at_commit: 4ad9060
---

# TASK-040 — Add the picks table

## Goal

The serving database can hold every pick the model makes, each locked to the exact line it was made at and never changed afterwards, and the test database is seeded with the fixture's 2026 picks: the 56 graded picks of weeks 1–5 and the 9 picks of week 6.

## Context

- Task list: `docs/08-tasklist.md` › M4 › M4.5. The stub sized it S; the fixture's weeks 1–5 games, lines and predictions make it M (one layer, data).
- **Schema change: stop and ask at the plan gate** (CLAUDE.md › Stop and ask before). The plan shows the full DDL for approval.
- Data model: `docs/03-data-model.md` › Models & outputs › `picks` (`prediction_id`, exactly one of `line_snapshot_id` / `contest_line_id`, `market`, `side`, `line`, `price` NULL for no-vig contest picks, `model_prob`, `edge_pts`, `expected_value`, `tier`, `stake_units`, `created_at`; "the current pick for a game is the latest one per (game, model version, market, line source)"; no `superseded_by`); › Conventions (model outputs stored immutably).
- Model: `docs/04-model.md` § 4 (EV; a pick is locked to the line it was made at and a new line creates a new pick that supersedes the old one; flat 1u stakes until Kelly, Later); § 9.3 (units at −110).
- Product: `docs/01-product.md` › F-02 outcome 3 (picks are immutable; a re-evaluation is stored as a new pick row), F-10 (CLV against the line picked at).
- Architecture: `docs/02-architecture.md` › Testing strategy › Seed data, row "Predictions and picks" (the 9 week-6 picks, Ole Miss picked at LSU −2.5 Sun 6:10 AM; 56 graded 2026 picks in weeks 1–5 adding up to 31-24-1, +4.6u, ROI +7.6%, avg CLV +0.9; tiers A 7-3, B 12-9-1, C 12-12; cumulative units W1 +1.8 · W2 +0.5 · W3 +2.9 · W4 +2.2 · W5 +4.6); › Generated rows (where the sample gives only totals, rows are generated deterministically with a fixed seed so the totals come out exact). The illustrative rows are in `design/handoff/designs/picks-data.js` (the 3 week-6 picks not on the slate: Tulane's Thursday win, Iowa State, Arizona State; every week-5 pick row; per-week CLV) and `design/sample-data.md` § 1, § 7.
- Decisions: D-135 (`forbid_model_output_changes()`, the insert-only triggers on UPDATE, DELETE and TRUNCATE; RESTRICT foreign keys; `double precision`), D-089 (fixture rows load into the test DB only), D-115 (`line_snapshots` and its `kind`), D-047 (no picks on FBS-vs-FCS games), D-132 (units at −110, a push refunded).
- Rules: hard rule 2 (picks are insert-only), hard rule 1 (no result, CLV or "current" column; those are M4.6's views), hard rule 6; `.claude/rules/database.md`.
- Pattern: `python/db/migrations/versions/0003_models.py` with `python/db/tests/test_model_schema.py`; the seed is `python/engine/src/engine/fixture.py` with JSON in `python/db/seeds/fixture/` (`week6.json`, `models.json`, whose weekly v1.0 runs entering weeks 1–6 already exist).
- **What the fixture lacks today:** only the 11 Week 6 slate games are seeded, with predictions for week 6 only. The 56 graded picks need weeks 1–5 games with final scores, opening and closing lines, and v1.0 predictions under the existing weekly runs; three of the 9 week-6 picks are on games M5.5 was to add (Tulane @ Memphis final 27-24, Iowa State @ Cincinnati, Arizona State @ Baylor).
- **Decide at the plan gate:**
  - `contest_line_id`: `contest_lines` doesn't exist until M6.1. Either the column waits for M6.1 (which then makes `line_snapshot_id` nullable and adds the exactly-one CHECK), or it's added now without its foreign key.
  - Which `line_snapshots` row a market pick points at when the line it was made at is a median across books (`game_market`), not one book's quote.
  - How a re-evaluation that drops a pick is stored, so the current pick can become "no pick" (a pass row with no side and tier, or something else); and whether a re-evaluation that keeps the same side and tier writes a new row at all (F-02's Ole Miss keeps "Picked at −2.5" after the line moved to −3.5). M4.6's views and M4.8's `lines` job both read this.
  - Whether `picks` carries `model_run_id` / `model_version_id` (with D-135's composite foreign key) for the views' reads, or reaches them only through `prediction_id`; CHECKs on `market`, `side`, `tier`, `model_prob` (0–1) and `stake_units` (> 0); whether a pick with no tier (edge above `min_edge_pts` but below tier C) can be stored.
  - The indexes M4.6's views read through (one game's picks; one version's picks in a season), so M4.6 needs no second schema change for its `EXPLAIN` checks.
  - Whether `edge_pts` and `model_prob` are stored on the margin after market shrinkage (what `core.picks.Pick` returns) or before it. The fixture's v1.0 spec tunes `market_shrinkage_k` over {0.5, 0.6, 0.7} while the design's edges are unshrunk (Ole Miss +3.9 at the pick would be about +2.3 at k = 0.6, below tier C), so the fixture's picks need either v1.0's chosen k fixed at 1 or edges stored as the design shows them.
  - The fixture: which file holds the weeks 1–5 games, lines, predictions and picks; that this task seeds the three week-6 games its picks need (and M5.5's note is updated to add the other 40); the seed and generator that make the totals exact.

## Acceptance criteria

- [x] AC-1: After `pnpm db:migrate:test`, `picks` exists with the columns in 03 › Models & outputs as amended at the plan gate, `pnpm db:check` reports one head with the models matching, and the migration runs up → down → up cleanly.
- [x] AC-2: A pick with both a line-snapshot and a contest line, or with neither, is refused, as are a `market`, `side` or `tier` outside their allowed values and a `model_prob` outside 0–1 (each a separate test; the allowed combination is the one the plan settles for `contest_line_id`).
- [x] AC-3: UPDATE, DELETE and TRUNCATE on `picks` each raise an error and leave the rows unchanged; deleting a prediction or line snapshot a pick references is refused; inserting a second pick for the same prediction at a new line snapshot succeeds.
- [x] AC-4: On the seeded test DB, v1.0 holds 9 week-6 picks, one per game the fixture's This Week picks name, none on Furman @ Clemson; Ole Miss @ LSU's is side away at the LSU −2.5 snapshot captured Sun 6:00 AM ET, created Sun 6:10 AM ET, tier B. For every seeded pick, `line` equals its snapshot's `spread_home`, `side` is the side its `edge_pts` favours, and `tier` is the one v1.0's tier cutoffs give `abs(edge_pts)`.
- [x] AC-5: On the seeded test DB, v1.0's weeks 1–5 picks are 56, every one on a final FBS-vs-FBS game with a closing line, and grading each in a test (the line it was picked at against the final margin, a push at 0, a win +1.0u and a loss −1.1u) gives 31-24-1, +4.6u, tiers A 7-3, B 12-9-1, C 12-12, cumulative units +1.8, +0.5, +2.9, +2.2, +4.6 by week, and an average CLV of +0.9 against the closing line (the sign as D-132 defines it).

## Out of scope

- The `current_picks`, `pick_outcomes` and `model_record` views (M4.6), and any grading stored in a column.
- Writing picks from the engine (`engine rate`, the weekly job, re-evaluation on line moves: M4.8) and tuning the pick rules (M4.4).
- `contest_lines`, contest entries and the model's contest top N (M6.1, M6.2).
- The other 40 Week 6 games behind "54 games" (M5.5).

## Files likely touched

- `python/db/migrations/versions/0004_picks.py`: the table, CHECKs, foreign keys, insert-only triggers (new).
- `python/db/src/db/models.py`: the SQLAlchemy model.
- `python/db/seeds/fixture/picks.json` (or the plan's file): weeks 1–5 games, lines, predictions and the 65 picks (new).
- `python/db/seeds/fixture/week6.json`: the three week-6 games the picks need, if they go there.
- `python/engine/src/engine/fixture.py`: seed the new rows.
- `python/db/tests/test_picks_schema.py`: AC-1 to AC-5 (new).
- `python/db/tests/test_model_schema.py`: if its fixture counts change.
- `docs/03-data-model.md` › Models & outputs: the amended `picks` columns and keys.
- `docs/02-architecture.md` › Seed data: where the picks fixture lives.
- `docs/08-tasklist.md` › M5.5: the three week-6 games this task seeds.
- `docs/decisions.md`: the schema choices as a D-### row.

## Verification

- Automated: `test_picks_schema.py`; `test_model_schema.py`; `pnpm db:check`; `pnpm test`.
- Manual: `pnpm db:migrate:test`, `pnpm db:seed`, then in `psql` → `SELECT count(*) FROM picks` is 65; `UPDATE picks SET tier = 'A'` fails.

## Follow-ups

_Work noticed during this task and deliberately left out. Each bullet ends `→ <path> § <section>` (where it was placed) or `→ not tracked: <reason>`. See `.claude/skills/track-follow-ups/classify.md`; the PR's Follow-ups section is copied from here._

- Add `contest_line_id` (with its FK), make `line_snapshot_id` nullable and add the exactly-one CHECK; `price` NULL then means a no-vig contest pick (approved at plan) → docs/08-tasklist.md § M6.1
- Pass rows (`side` NULL, `tier` NULL, `stake_units` 0) mean "no pick": `current_picks` and the record views must treat them so (approved at plan; M4.6 has a task file, so the note went to its Context rather than the task-list row) → docs/tasks/TASK-041-pick-views.md § Context
- The writer inserts a row only when the side or tier differs from the current pick (pass included), so Ole Miss keeps "Picked at −2.5"; `edge_pts` is on the blended margin (approved at plan) → docs/08-tasklist.md § M4.8
- From the schema review: nothing forces `line` to be NULL only for a moneyline pick; a CHECK would be a schema change, so M4.8's writer considers it → docs/08-tasklist.md § M4.8
- The conference and favorite/underdog splits in `picks-data.js` (`byConf`, `byFav`) are not constrained by this fixture (approved at plan) → docs/08-tasklist.md § M7.4
- The design's picked-at times for OSU and ND (Sun 6:10 AM) conflict with their opening lines, and Ole Miss's CLV sign in sample-data §1; recorded in the decision row, with the added Monday OU and Tuesday Iowa snapshots (approved at plan) → docs/decisions.md § D-140
- M5.5 now adds 40 Week 6 games, not 43 (approved at plan) → docs/08-tasklist.md § M5.5
- From the schema review: the weeks 1–5 final games give their teams a `team_schedule_strength` entering week 6, so the fixture's SOS ranks won't match sample-data § 4 → docs/08-tasklist.md § M8.1

## Plan

_Written by /plan-batch or /implement-task Phase 1. Approved by the user (plan_status: approved) before any code is written._

1. Migration `0004_picks` (DDL as approved at the plan gate): `picks` with CHECKs (market, side-for-market, tier, `model_prob` 0–1, pass-or-stake), composite FKs `(prediction_id, model_version_id, game_id)` → `predictions` and `(line_snapshot_id, game_id)` → `line_snapshots` (both RESTRICT), UQ `(prediction_id, market, line_snapshot_id)`, UQ `(id, model_version_id, game_id)` on `predictions` and `(id, game_id)` on `line_snapshots`, the two read indexes, `forbid_model_output_changes()` triggers. `contest_line_id` waits for M6.1.
2. `db/models.py`: the `Pick` model and the two new unique constraints, so `pnpm db:check` stays clean.
3. Fixture: `seeds/fixture/generate_picks.py` (fixed seed, hand-set tier mix per week) writes `picks.json`; 24 new FBS teams in `teams.json` with generated ratings (below Utah) in `models.json`; 2 added snapshots in `week6.json` (OU Mon 9:40 AM at 6.5, Iowa Tue 11:20 AM at −1.5). Weeks 1–5: 56 final FBS games, opening / Sun 6:00 AM snapshot / closing lines, v1.0 predictions under the weekly runs, picks created 6:10 AM; week 5 is the 15 design rows. Week 6: three games (Tulane, Iowa State, Arizona State) and the 9 picks; OSU and ND at the Thu 9:02 PM snapshots. Unshrunk edges.
4. `engine/fixture.py`: seed the new teams, games, lines, predictions and picks (idempotent; picks `ON CONFLICT DO NOTHING`).
5. Tests first, then code: `db/tests/test_picks_schema.py` (AC-1 to AC-5, generator-matches-JSON); update `test_model_schema.py` counts (FBS teams, week 6 games).
6. Docs: 03 › Models & outputs, 02 › Seed data, 08 (M5.5, M6.1, M4.6, M4.8, M7.4), a decisions row.
Risks: rankings / e2e tests may count teams; fix what the full suite flags.

## Review log

_Filled by /implement-task. One line per round._

- Verify R1 PASS | Audit R1 PASS | Spec R1 APPROVE (optional: 03's new unique keys, done) | Schema R1 APPROVE (6 MINOR: 4 fixed, 2 placed as follow-ups) | Verify R2 PASS (after the review fixes)

## Blocked

_Only if status is Blocked: what failed, what was tried, best hypothesis, decision needed._

## Metrics

- Verify rounds: 2 (both PASS; the second re-ran after the review fixes)
- Review rounds: 1
- First-pass AC FAILs: 0
- Plan revisions after approval: 0
