---
id: TASK-044
title: Stage canceled and postponed games, and rate from the harness's staged contexts
status: Done
depends_on: []
size: M
model: opus
autonomy: attended
ui: false
plan_status: approved
planned_at_commit: 6ae9024
---

# TASK-044 — Stage canceled and postponed games, and rate from the harness's staged contexts

## Goal

A game that won't be played is marked canceled (or postponed) from the lake through to Postgres, so the weekly model run never gives it a permanent prediction or pick, and `engine rate` takes each game's kickoff from the same staged rows the backtest uses instead of its own copy of the rule.

## Context

- Task list: `docs/08-tasklist.md` › M4 › M4.8 (split: this task is M4.8's data prerequisites; TASK-045 writes picks; TASK-046 runs the weekly job).
- Data model: `docs/03-data-model.md` › staging `games` (`status` is `final`/`scheduled` today) and › Postgres `games.status` (`scheduled|in_progress|final|canceled|postponed`, already allowed: no schema change).
- Architecture: `docs/02-architecture.md` › Components › 1 (transform rebuilds from raw with zero API calls).
- Decisions: D-121 (a game is done when CFBD marks it completed, or when it's unscored and its `/games` file was saved 7+ days after its start: CFBD lists a canceled game, App State–Liberty 2024, as uncompleted forever), D-123 (the jobs' summary already lists such games through `jobs.canceled`), D-127 (`features.KICKOFF`: a TBA game kicks off at the end of its Eastern `game_date`), D-142 (the pick views grade `canceled`/`postponed` as `void`).
- Code today: `engine/transform/staging.py` stages `status` as `final` when CFBD's `completed`, else `scheduled`; `publish/staging.py` publishes it as is; `publish/models.py` `_week` drops `NOT_PLAYED = {canceled, postponed}`, which never matches, and re-reads staged `games` with `_kickoff`, a Python copy of `features.KICKOFF`.
- *From TASK-035 (PR #97):* the transform stages only `final` and `scheduled` (from CFBD's `completed`), so `engine rate`'s canceled/postponed filter never matches and a canceled game gets a permanent prediction: stage those statuses (or find CFBD's signal) before predictions go out weekly. `engine rate` also re-reads staged `games` and re-derives a TBA kickoff in Python (`publish/models.py` `_kickoff`, a copy of `features.KICKOFF`); have `harness.load` keep each week's staged contexts instead.
- **Decide at the plan gate:** the signal: D-121's unscored-and-7-days rule (which needs each `/games` file's `saved_at` in the transform), a field CFBD provides (check the raw files on the local lake, zero API calls), or both; whether `postponed` is distinguishable from `canceled` (a rescheduled game reappears under a new date with the same id); what a game in the 7-day window is (`scheduled`, so the weekly job may still predict it once; the views grade it `void` later); whether the data-quality checks gain a rule for the new statuses.

## Acceptance criteria

- [x] AC-1: Given a lake fixture with a completed game, a future game and a game left uncompleted and unscored by a `/games` file saved 7+ days after its start, `engine transform --rebuild` stages them `final`, `scheduled` and `canceled` (or `postponed`, as the plan settles), and `engine publish --target test` writes the same three statuses to Postgres `games.status`; a second publish leaves them unchanged.
- [x] AC-2: Given a fixture week holding one canceled game, `engine rate` inserts a prediction for every other staged game of the week and none for the canceled one (test against the test DB).
- [x] AC-3: `engine rate` builds the week's games from the harness's staged contexts (`harness.load`), and `publish/models.py` no longer has `_kickoff`; a test shows a TBA game's kickoff in `engine rate` equals the one `features.KICKOFF` gives (the end of its Eastern `game_date`), and the existing `test_publish_models.py` cases pass unchanged.
- [x] AC-4: On the local lake, `engine transform --rebuild` for 2014–2026 passes the data-quality checks with zero CFBD calls (`data/cfbd_calls.json` unchanged); the count of staged games per status and season is printed and recorded in the decision row, and App State–Liberty 2024 is staged as not played.
- [x] AC-5: 03 › staging `games` lists the staged statuses and the rule that sets them, and a decision row (D-###) records the signal chosen.

## Out of scope

- Writing picks (TASK-045) and the scheduled `rate-and-predict` job (TASK-046).
- Live `in_progress` status during game windows: the `scores` job (M6.8).
- Any change to the pick views' grading of `void` games (D-142 already handles it).
- Postseason weeks in `engine rate` (it rates regular-season weeks today; TASK-046 decides).

## Files likely touched

- `python/engine/src/engine/transform/staging.py`: the status rule.
- `python/engine/src/engine/transform/quality.py`: a check for the new statuses, if the plan adds one.
- `python/engine/src/engine/backtest/harness.py`: keep each week's staged contexts in `History`.
- `python/engine/src/engine/publish/models.py`: `_week` reads the harness's contexts; drop `_kickoff`.
- `python/engine/tests/test_transform.py`, `test_publish_staging.py`, `test_publish_models.py`, `lake_fixture.py`: AC-1 to AC-3.
- `docs/03-data-model.md` › staging `games`: the statuses.
- `docs/decisions.md`: the signal as a D-### row.

## Verification

- Automated: the tests above; `test_features.py` and `test_backtest_golden.py` unchanged (the harness's games and goldens don't move); `pnpm test`.
- Manual: `engine transform --rebuild` on the local lake → the status counts print and the quality checks pass; `engine publish --target dev` then `SELECT status, count(*) FROM games GROUP BY 1` on the dev DB shows the canceled games.

## Follow-ups

_Work noticed during this task and deliberately left out. Each bullet ends `→ <path> § <section>` (where it was placed) or `→ not tracked: <reason>`. See `.claude/skills/track-follow-ups/classify.md`; the PR's Follow-ups section is copied from here._

- Candidate decision: a game unscored and uncompleted 7+ days after its start is staged `canceled`, `postponed` is never staged, and `engine rate` predicts `harness.Week.contexts` (amends D-136's "stages only final and scheduled") → docs/decisions.md § D-145
- `engine ingest games` (`map_games`) wrote only final/scheduled, so re-ingesting a week flipped a canceled dev row back (schema review R1) → not tracked: done in this PR (plan revision 1)
- `map_games`'s `saved_at` defaults to None, which keeps the old final/scheduled behaviour for a caller that leaves it out (schema review R2, optional) → not tracked: its one production caller, `ingest/games.py`, passes it, and the sample-file tests rely on the default
- Line pulls after a canceled game's start still publish as its closing line in `game_market` → not tracked: the pick views grade the game `void` (D-142), so no record, ROI or CLV reads it
- The dev DB holds 104 `cfbd` games (all 2025 regular week 1, `final`) that staging doesn't have, likely from an early `ingest:games` run; upserts never delete them → not tracked: dev-only rows unrelated to this task, which no job or release reads

## Plan

Approved 2026-10-31 (attended).

**Decisions:** (1) Signal: D-121's rule alone. A game is `canceled` when its newest record isn't completed, both scores are NULL, and that record's `fetched_at` is `endpoints.SETTLE` (7 days) or more after its `startDate`. CFBD's records carry no status or notes field (App State–Liberty 2024: `completed` false, `notes` null). (2) `postponed` isn't staged: CFBD doesn't distinguish it, and a rescheduled game keeps its id with a new `startDate`, so the next pull stages it `scheduled` again. (3) Inside the 7-day window a game stays `scheduled`; the views grade it `void` once it turns `canceled`. (4) A notes-only `not_played` data-quality check lists each canceled game.

**Steps:**

1. `transform/staging.py` `games`: the status gains the `canceled` branch (raw `startDate`, `SETTLE` from `engine.ingest.endpoints`).
2. `transform/__init__.py` `rebuild`: print staged games per season and status (AC-4).
3. `transform/quality.py`: add the notes-only `not_played` check.
4. `backtest/harness.py`: `Week.contexts` (default `()`), each week's staged games with both teams whose status isn't in `NOT_PLAYED`, sorted by (kickoff, game id); `NOT_PLAYED` moves here.
5. `publish/models.py`: `_week` takes the week's `as_of` and `contexts` from the harness; drop `_kickoff`, the staged re-read and unused imports; update the module docstring.
6. Docs: 03 › staging `games` statuses and rule; a D-### row with the signal and the AC-4 counts.

**Files:** `engine/transform/staging.py`, `engine/transform/__init__.py`, `engine/transform/quality.py`, `engine/backtest/harness.py`, `engine/publish/models.py`, `tests/lake_fixture.py` (`write_backtest_repull`), `tests/test_transform.py`, `tests/test_publish_staging.py`, `tests/test_publish_models.py`, `docs/03-data-model.md`, `docs/decisions.md`, this task file.

**Test strategy:**

- AC-1: `test_transform.py::test_unscored_game_a_week_past_its_start_is_staged_canceled` (final, scheduled, canceled, and a 6-day pull left scheduled); `test_publish_staging.py::test_publish_writes_canceled_status_and_a_second_publish_keeps_it`.
- AC-2: `test_publish_models.py::test_a_canceled_game_from_the_lake_is_not_predicted` (a 2023 week-5 game unplayed, re-pulled 8 days after its start).
- AC-3: `test_publish_models.py::test_rate_takes_a_tba_kickoff_from_the_harness` (a TBA game's `fit_week` kickoff equals `features.KICKOFF`'s); existing `test_publish_models.py` cases unchanged; `test_features.py` and `test_backtest_golden.py` unchanged.
- AC-4: manual `engine transform --rebuild` on the local lake; `data/cfbd_calls.json` hash unchanged; counts into the decision row.
- AC-5: doc review (spec-reviewer).

**Risks:** a canceled game still counts toward its week's `as_of` (only ever earlier, never a leak; App State–Liberty isn't its week's first kickoff, so no backtest number moves). Line pulls after a canceled game's start still publish as its close; harmless, since it grades `void`.

**Revision 1** (2026-10-31, owner's OK after schema review R1): the dev-only `engine ingest games` (`map_games`) still wrote `final`/`scheduled` only, so re-ingesting a week turned a canceled dev row back to `scheduled`. `map_games(payload, saved_at)` now applies the same rule through `endpoints.done`, and `ingest/games.py` passes the saved file's time. Files added: `engine/sports/cfb/games.py`, `engine/ingest/games.py`, `tests/test_cfbd_games.py` (`test_unscored_game_a_week_past_its_start_is_canceled`), `tests/test_cfbd_client.py` (`test_ingest_games_publishes_a_game_unscored_a_week_on_as_canceled`); D-145 notes it.

## Review log

- Verify R1 PASS (verify.full) → R2 PASS after Revision 1 (752 pytest)
- Audit R1 PASS (6 tests, all discriminating) → R2 PASS (Revision 1's 2 tests)
- Spec R1 APPROVE → R2 APPROVE (Revision 1)
- Schema R1 APPROVE (2 MINOR: `map_games` still wrote only final/scheduled; the staging docstring) → Revision 1 → R2 APPROVE
- Manual: local-lake rebuild 6/6 checks, ledger hash unchanged, 2024 canceled 1 (401640992); `engine publish --target dev` → dev `games` canceled 1, final 10985, scheduled 378

## Blocked

_Only if status is Blocked: what failed, what was tried, best hypothesis, decision needed._

## Metrics

- Verify rounds: 2 (both PASS; the second after Revision 1)
- Review rounds: 2 (spec), 2 (schema); audit 2
- First-pass AC FAILs: 0 (schema R1's MINORs were a second status writer and a docstring, not an AC)
- Plan revisions after approval: 1 (the dev `ingest:games` status rule, owner's OK)
