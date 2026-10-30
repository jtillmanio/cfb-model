---
id: TASK-044
title: Stage canceled and postponed games, and rate from the harness's staged contexts
status: Ready
depends_on: []
size: M
model: opus
autonomy: attended
ui: false
plan_status: none
planned_at_commit:
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

- [ ] AC-1: Given a lake fixture with a completed game, a future game and a game left uncompleted and unscored by a `/games` file saved 7+ days after its start, `engine transform --rebuild` stages them `final`, `scheduled` and `canceled` (or `postponed`, as the plan settles), and `engine publish --target test` writes the same three statuses to Postgres `games.status`; a second publish leaves them unchanged.
- [ ] AC-2: Given a fixture week holding one canceled game, `engine rate` inserts a prediction for every other staged game of the week and none for the canceled one (test against the test DB).
- [ ] AC-3: `engine rate` builds the week's games from the harness's staged contexts (`harness.load`), and `publish/models.py` no longer has `_kickoff`; a test shows a TBA game's kickoff in `engine rate` equals the one `features.KICKOFF` gives (the end of its Eastern `game_date`), and the existing `test_publish_models.py` cases pass unchanged.
- [ ] AC-4: On the local lake, `engine transform --rebuild` for 2014–2026 passes the data-quality checks with zero CFBD calls (`data/cfbd_calls.json` unchanged); the count of staged games per status and season is printed and recorded in the decision row, and App State–Liberty 2024 is staged as not played.
- [ ] AC-5: 03 › staging `games` lists the staged statuses and the rule that sets them, and a decision row (D-###) records the signal chosen.

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
