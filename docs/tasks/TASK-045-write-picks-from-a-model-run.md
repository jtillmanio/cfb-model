---
id: TASK-045
title: Write picks from a model run, and re-evaluate them when lines move
status: Ready
depends_on: [TASK-042]
size: M
model: opus
autonomy: attended
ui: false
plan_status: none
planned_at_commit:
---

# TASK-045 — Write picks from a model run, and re-evaluate them when lines move

## Goal

After a model run predicts a week, the engine turns its predictions into spread picks against the newest posted line, and when a line later moves enough to change a pick, it records the new pick, never touching one already made and never picking a game that has kicked off. The pick views then show and grade them with no other step.

## Context

- Task list: `docs/08-tasklist.md` › M4 › M4.8 (split: TASK-044 stages canceled games; this task is the pick writer; TASK-046 runs it from the weekly `rate-and-predict` and `lines` jobs).
- Model: `docs/04-model.md` § 4 From predictions to picks (edge, tiers, D-047; "Re-evaluate when the line moves. A pick is locked to the line it was made at, and a new line creates a new pick that supersedes the old one"); § 9.3 (−110 when a book quotes no price).
- Data model: `docs/03-data-model.md` › Models & outputs › `picks` (insert-only; `line_snapshot_id`, `line`, `price`, `edge_pts`, `model_prob`, `tier`, `side`, `market`).
- Architecture: `docs/02-architecture.md` › Components › 1 `publish` (inserts versioned picks); › 4 Jobs (`lines` re-evaluates picks when lines move).
- Decisions: D-140 (how picks are stored: one book's `line_snapshots` row, `line` its `spread_home`, `price` −110 when none; unique on `(prediction_id, market, line_snapshot_id)`), D-141 (the pick path is `core.picks.pick_game(game, …, pickable)`), D-142 (the current pick is the newest row before the game's cutoff; a pass as the newest row means no pick; rows after the cutoff are ignored), D-047 (no picks with an FCS team), hard rule 2 (insert-only), hard rule 4 (only data from before kickoff).
- Code today: no writer exists. `engine rate` (`publish/models.py`) inserts a run, ratings and predictions; `core.picks.pick_game` and `sports.cfb.teams.pickable` decide a pick; `fixture.py` `_seed_picks` and `python/db/tests/model_rows.py` `pick` insert pick rows for tests and the seed.
- *From TASK-040 (PR #105):* the writer inserts a pick row only when the side or tier differs from the current pick (a pass row when the pick drops), so a pick keeps the line it was made at (Ole Miss stays "Picked at −2.5"); `edge_pts` and `model_prob` are on the blended margin `core.picks.pick()` returns; a pick points at one book's `line_snapshots` row (consensus when it quoted the pull; a pull with no consensus quote needs a rule for which book) and `line` is that row's spread, `price` −110 when the row quotes none (D-140). Consider a CHECK that `line` is NULL only for moneyline (schema change: stop and ask).
- *From TASK-039 (PR #106):* the writer picks through `core.picks.pick_game(game, …, pickable)` with `engine.sports.cfb.teams.pickable`, never `pick()` directly, so no game with an FCS team is picked (D-047).
- *From TASK-041 (PR #107):* the pick views count only rows made before the game's cutoff (kickoff, or the end of `game_date` in Eastern time when TBA), so a pick written at or after kickoff is silently ignored: have the writer refuse one, with a test. The views grade spread picks only: add total (combined points against `line`, CLV against `closing_total`) and moneyline (the winner, units from `price`) grading to `pick_outcomes` when the writer first writes those markets. A CHECK that `price` is ≤ −100 or ≥ +100 would keep units sane (schema change: stop and ask) (D-142).
- *From TASK-042 (PR #109), open question for the plan:* `Pick.prob`, so `picks.model_prob`, is now the **displayed** probability: P(side covers) on the margin shrunk toward the line by `market_shrinkage_k × display_shrinkage_k` (D-143); `edge_pts`, the side and the tier stay on the margin blended by `market_shrinkage_k` alone, which TASK-040's note above says of both. Rows are insert-only, so this meaning is fixed by the first row written. At v1's display shrinkage (0.1–0.25) a pick at edge 8 shows 52–53%, about −110's break-even (52.4%), so `expected_value` from `model_prob` is near zero or negative on most picks while validation picks hit 55.1%: decide whether `expected_value` reads the displayed or the raw probability before writing rows. The `efficiency-v1.json` hash changed; rate from `backtests/20261030T183302517984Z-cb1a4894a79d/run.json` (D-143).
- *From TASK-043 (feat/043-holdout-and-go-no-go-v1):* the hash changed again (`ridge_alpha` grid widened, D-144): TASK-042's run above no longer matches the spec; rate from `backtests/20261031T043227249121Z-50d9e5812819/run.json` (spec hash `50d9e5812819`) or a later run of it. v1 is `candidate`, not promoted, and the "uncalibrated" label shows while the validation calibration gate fails (55–57.5% shown, 46.5% covered on 142 games), so `picks.model_prob` is displayed under that label.
- **Decide at the plan gate:** which book a pick uses when the newest pull has no consensus quote; which prediction a re-evaluation reads (the version's newest succeeded run for the week); whether a pass row is written for a game that never had a pick (no: a pass only supersedes a pick); the entry point (`engine rate` writing picks in its own transaction, a separate `engine pick --target dev|test`, or both; refused under `LIVE=true` like `engine rate`); whether either CHECK above is proposed now (each is a schema change: stop and ask).

## Acceptance criteria

- [ ] AC-1: Given a model run's predictions for a week in the test DB and each game's line snapshots, the writer inserts, for each game `core.picks.pick_game` (with `sports.cfb.teams.pickable` and the run's resolved pick rules) picks, one spread pick on the newest snapshot before the game's cutoff: `line` that row's `spread_home`, `price` its price or −110 when it has none, `edge_pts`, `model_prob` and `tier` as `pick_game` returns them; a game with an FCS team and an edge above every threshold gets no row (test).
- [ ] AC-2: Run again with no new snapshot, the writer inserts nothing; given a newer snapshot, it inserts a new pick when the side or tier changes (and `current_picks` then shows the new line), nothing when side and tier stay (`current_picks` keeps the old line), and a pass row when the pick no longer qualifies (`current_picks` shows no pick for the game); each case is a test that reads `current_picks`.
- [ ] AC-3: The writer writes no row for a game at or after its cutoff (kickoff, or the end of `game_date` in Eastern time when TBA): a test with one game kicked off a minute before the writer's clock and one still to play inserts a row for the second only, and nothing it writes has `created_at` at or after its game's cutoff.
- [ ] AC-4: When the newest pull has no consensus quote, the writer uses the book the plan settles (recorded in a decision row), shown by a test with such a pull; a game with no snapshot before its cutoff gets no pick.
- [ ] AC-5: The writer runs in one transaction with no UPDATE or DELETE on `picks` (the insert-only trigger stays untouched), is refused under `LIVE=true` from the CLI, and a failure partway inserts no pick (test).

## Out of scope

- The scheduled `rate-and-predict` and `lines` jobs that call the writer on production (TASK-046).
- Contest picks and `contest_line_id` (M6.1, M6.5); totals and moneyline picks and their grading.
- Any schema change, including the two CHECKs above, unless the owner approves one at the plan gate.
- Changing the pick views (D-142) or the pick rules (D-141); the display calibration is TASK-042's.

## Files likely touched

- `python/engine/src/engine/publish/picks.py` (new): the writer.
- `python/engine/src/engine/publish/models.py`: call the writer after a run's predictions, if the plan has `engine rate` write picks.
- `python/engine/src/engine/cli.py`: the entry point and its `LIVE` refusal.
- `python/engine/tests/test_publish_picks.py` (new): AC-1 to AC-5 against the test DB.
- `python/engine/tests/test_publish_models.py`: `engine rate` with picks, if it writes them.
- `docs/02-architecture.md` › Components › 1: the writer under `publish`.
- `docs/decisions.md`: the book rule and the re-evaluation rule as a D-### row.

## Verification

- Automated: the tests above; `python/db/tests/test_current_picks.py` and `test_pick_outcomes` cases unchanged; `pnpm test`.
- Manual: on the dev DB, `engine rate --target dev` for a 2026 week, then the writer → `SELECT * FROM current_picks` lists the week's picks, each pointing at a snapshot before its kickoff; publish a later `lines` pull and run the writer again → only games whose side or tier changed gain a row.

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
