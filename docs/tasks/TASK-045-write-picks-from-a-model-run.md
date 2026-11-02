---
id: TASK-045
title: Write picks from a model run, and re-evaluate them when lines move
status: Review
depends_on: [TASK-042]
size: M
model: opus
autonomy: attended
ui: false
plan_status: approved
planned_at_commit: 1750be0
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
- *From TASK-043 (PR #110):* the hash changed again (`ridge_alpha` grid widened, D-144): TASK-042's run above no longer matches the spec; rate from `backtests/20261031T043227249121Z-50d9e5812819/run.json` (spec hash `50d9e5812819`) or a later run of it. v1 is `candidate`, not promoted, and the "uncalibrated" label shows while the validation calibration gate fails (55–57.5% shown, 46.5% covered on 142 games), so `picks.model_prob` is displayed under that label.
- **Decide at the plan gate:** which book a pick uses when the newest pull has no consensus quote; which prediction a re-evaluation reads (the version's newest succeeded run for the week); whether a pass row is written for a game that never had a pick (no: a pass only supersedes a pick); the entry point (`engine rate` writing picks in its own transaction, a separate `engine pick --target dev|test`, or both; refused under `LIVE=true` like `engine rate`); whether either CHECK above is proposed now (each is a schema change: stop and ask).

## Acceptance criteria

- [x] AC-1: Given a model run's predictions for a week in the test DB and each game's line snapshots, the writer inserts, for each game `core.picks.pick_game` (with `sports.cfb.teams.pickable` and the run's resolved pick rules) picks, one spread pick on the newest snapshot before the game's cutoff: `line` that row's `spread_home`, `price` its price or −110 when it has none, `edge_pts`, `model_prob` and `tier` as `pick_game` returns them; a game with an FCS team and an edge above every threshold gets no row (test).
- [x] AC-2: Run again with no new snapshot, the writer inserts nothing; given a newer snapshot, it inserts a new pick when the side or tier changes (and `current_picks` then shows the new line), nothing when side and tier stay (`current_picks` keeps the old line), and a pass row when the pick no longer qualifies (`current_picks` shows no pick for the game); each case is a test that reads `current_picks`.
- [x] AC-3: The writer writes no row for a game at or after its cutoff (kickoff, or the end of `game_date` in Eastern time when TBA): a test with one game kicked off a minute before the writer's clock and one still to play inserts a row for the second only, and nothing it writes has `created_at` at or after its game's cutoff.
- [x] AC-4: When the newest pull has no consensus quote, the writer uses the book the plan settles (recorded in a decision row), shown by a test with such a pull; a game with no snapshot before its cutoff gets no pick.
- [x] AC-5: The writer runs in one transaction with no UPDATE or DELETE on `picks` (the insert-only trigger stays untouched), is refused under `LIVE=true` from the CLI, and a failure partway inserts no pick (test).

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

- TASK-046 calls `publish.picks.write_picks` in its job's transaction; the writer reads the version's newest succeeded run of any non-backtest type, while TASK-046's AC-3 says "newest `scheduled` run", so its plan decides whether to filter (approved at plan) → docs/tasks/TASK-046-weekly-rate-predict-pick-job.md § Context
- Candidate decision: the book rule, the re-evaluation rule, `expected_value` on the displayed probability and the `engine pick` entry point, as one D-### row (approved at plan) → docs/decisions.md § D-148
- Schema review R2: the per-version lock serializes writers only under READ COMMITTED, and a `PicksRefused` or `PointInTimeError` raised partway leaves earlier inserts in the caller's transaction, so TASK-046's job keeps that isolation and rolls back on an error, never commits → docs/tasks/TASK-046-weekly-rate-predict-pick-job.md § Context
- Schema review R1: a run with no predictions returns 0 picks and 0 passes, which reads the same as "no line moved"; TASK-046's job summary should tell them apart → docs/tasks/TASK-046-weekly-rate-predict-pick-job.md § Context
- From TASK-041's note in Context: `pick_outcomes` grades spread picks only, so the first totals pick needs totals grading (combined points against `line`, CLV against `closing_total`) → docs/08-tasklist.md § M15 › M15.2
- From TASK-040's and TASK-041's notes in Context: the CHECKs on `picks` (`line` NULL only for moneyline; `price` ≤ −100 or ≥ +100) weren't proposed here (no schema change); they're schema changes to raise when another market is written → docs/08-tasklist.md § M15 › M15.2
- From TASK-041's note in Context: moneyline picks need `pick_outcomes` to grade the winner with units from `price` → docs/08-tasklist.md § Unscheduled (F-12)
- Schema review R2: the lock casts the bigint version id to `integer`, so a version id past 2^31 − 1 would fail the transaction (safely: nothing written) → not tracked: version ids are a few dozen and won't approach it

## Plan

Approved 2026-11-02 at `1750be0`.

**Decisions (the plan gate's):**
1. **Writer:** `publish/picks.py` `write_picks(conn, version_id, season, week, now)` reads the DB only: the version's newest succeeded run (`adhoc` or `scheduled`) for the week, by `finished_at` then `id`; pick rules from the stored spec resolved with the run's stored `choices`; the margin distribution from the run's `fitted_params` (`EmpiricalMargin.from_params`, else `NormalMargin(margin_sd)`); classification from `team_seasons.division`; `pick_game(…, teams.pickable)`. So the `lines` job re-evaluates without a refit.
2. **Line:** the newest pull with a spread quote, `captured_at` before the cutoff and ≤ `now`. Book: consensus when it quoted the spread; else DraftKings, then Bovada, then any other by `source_id` (2026 dev lines: no consensus in any pull, DraftKings in all 182, Bovada in 112, no prices). Price: the side's price, −110 when none.
3. **Rows:** a pick when the game has no current pick (`current_picks`) or the side or tier differs; a pass row only when a current pick stops qualifying, never for a game never picked. A pass row's numbers describe the side the blended edge favours; stake 0.
4. **Cutoff:** no row at or after the cutoff; `created_at` = the writer's `now` (its clock, not the DB's `now()`); the writer asserts each snapshot is before the cutoff and ≤ `now` (hard rule 4).
5. **`expected_value`** reads the displayed `model_prob` (04 § 4, 03 › picks), at the row's price.
6. **Entry point:** `engine pick --target dev|test --season --week [--name] [--version v1.0]`, one transaction (`publish_picks`), refused under `LIVE=true`; `engine rate` unchanged.
7. No CHECKs, no schema change.

**Steps:**
1. Tests first (`test_publish_picks.py`), confirmed failing (no module).
2. `publish/picks.py`: run lookup, game contexts, snapshot and book choice, current picks, decide, insert; `publish_picks(url, …)`.
3. `cli.py`: `engine pick`.
4. Docs: 02 › Components › 1, the D-### row, `model-guide.md`.

**Files:**
- `python/engine/src/engine/publish/picks.py` (new): the writer.
- `python/engine/src/engine/cli.py`: `engine pick` and its `LIVE` refusal.
- `python/engine/tests/test_publish_picks.py` (new): AC-1 to AC-5.
- `docs/02-architecture.md` › Components › 1: the writer under `publish`.
- `docs/decisions.md`: the D-### row.
- `docs/model-guide.md` (§ 2 commands, § 7, § 10 M4): not in "Files likely touched"; CLAUDE.md requires it when the pipeline changes.
- Dropped: `publish/models.py`, `test_publish_models.py` (`engine rate` unchanged).

**Test strategy** (`python/engine/tests/test_publish_picks.py`, test DB):
- AC-1: a pick on the newest snapshot with line, price (−110 and quoted), edge, prob, tier as `pick_game` gives; an FCS game with a large edge gets no row.
- AC-2: rerun without a new snapshot inserts nothing; a new line changing side or tier inserts a pick shown by `current_picks`; same side and tier inserts nothing (`current_picks` keeps the old line); no longer qualifying inserts a pass row (`current_picks` empty for the game).
- AC-3: a game kicked off a minute before the clock and one to come (and a TBA game past the end of its Eastern date): a row for the second only; every row's `created_at` before its cutoff.
- AC-4: a pull with no consensus uses DraftKings; a game with no snapshot before its cutoff gets no pick.
- AC-5: a statement listener sees no UPDATE or DELETE on `picks`; a failure on the second game leaves no row (`publish_picks` on a savepoint-backed engine); `engine pick` under `LIVE=true` exits 2 without connecting.

**Risks:** 2026 dev picks are DraftKings at −110 until consensus or prices appear; a run whose `choices` don't resolve every pick field is refused (exit 2).

**Revision 1** (2026-11-02, after schema review R1; the owner approved all four): the book tie-break ends on the snapshot id (two sources can quote one book in a pull); `write_picks` takes `pg_advisory_xact_lock(hashtext('engine.publish.picks'), version_id)` so two writers on a version serialize; a clock earlier than a pick already made for the week's games is refused, and only runs finished by the clock are read; a prediction with no `margin_sd` (under a normal margin) is refused. Spec review R1's fixes: D-148 says the run's `as_of` may equal a cutoff (the week's first kickoff), with a test of the `PointInTimeError` path. Tests: `test_a_pull_quoting_one_book_twice_takes_the_lowest_id`, `test_the_writer_holds_a_lock_on_the_version_until_it_commits`, `test_a_clock_before_a_pick_already_made_is_refused`, `test_a_run_finished_after_the_clock_is_not_picked_from`, `test_a_prediction_with_no_margin_sd_is_refused`, `test_a_run_as_of_after_a_games_cutoff_raises`.

## Review log

_Filled by /implement-task. One line per round._

- Verify R1 PASS (0cd3e70) → R2 PASS (75144ad, after the audit's test) → R3 PASS (39d5900, after the review fixes; pytest 785, Vitest 229, e2e 40)
- Audit R1 CHANGES (AC-2 PARTIAL: a tier-only comparison survived; the side-change case also changed the tier) → R2 PASS (side-only flip at −16.5 kills it)
- Spec R1 CHANGES (D-148 said the run's `as_of` must be before the cutoff; the code, correctly, allows equal) → R2 APPROVE
- Schema R1 APPROVE (six MINORs; four fixed as plan Revision 1 with the owner's approval, two to TASK-046's Context) → R2 APPROVE (MINORs placed as follow-ups)

## Blocked

_Only if status is Blocked: what failed, what was tried, best hypothesis, decision needed._

## Metrics

- Verify rounds: 3 (all PASS; the second after the audit's test, the third after the review fixes)
- Review rounds: 2 (spec), 2 (schema); audit 2
- First-pass AC FAILs: 0 (audit R1 found AC-2's test not discriminating, not the code; spec R1's CHANGES was D-148's wording)
- Plan revisions after approval: 1 (Revision 1: the schema review's hardening, approved by the owner)
