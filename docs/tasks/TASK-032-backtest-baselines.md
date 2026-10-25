---
id: TASK-032
title: Add the backtest baselines: home field only, last season, closing line, SP+/FPI
status: Ready
depends_on: [TASK-030]
size: S
model: sonnet
autonomy: unattended
ui: false
plan_status: none
planned_at_commit:
---

# TASK-032 — Add the backtest baselines: home field only, last season, closing line, SP+/FPI

## Goal

The backtest can score the simple predictions every real model has to beat (home field only, last season's ratings carried over, the closing line, and SP+/FPI) on exactly the same games as the model.

## Context

- Task list: `docs/08-tasklist.md` › M3 › M3.4.
- Model: `docs/04-model.md` § 2 Rung 0: Baselines (home-field only, last season's final ratings carried over, closing line, SP+/FPI spreads); § 9.2 (SP+, FPI and Elo count only if published before the game, otherwise "hindsight benchmark"); § 9.3 (closing line: `consensus`, else the median across providers; each game records which); § 9.6 Phase 2 row (Rung 1 must beat home-field only, with the fitted home-field value, and last season's final ratings; closing line and SP+/FPI are reported alongside).
- Data model: `docs/03-data-model.md` › Lake layout › Staged tables (`benchmark_ratings`: `system`, `season`, `team_source_id`, `rating`, `season_final`, `known_at`).
- Decisions: D-056, D-119 (benchmark staging), D-121 (`engine.transform.market.closing_lines()`).
- Pattern to copy: the stub model in TASK-030's tests and the `GamePredictor` protocol from TASK-029 (`python/engine/src/engine/core/interfaces.py`).
- *From TASK-018 (PR #62):* staged `benchmark_ratings` rows carry `season_final` and `known_at` (NULL when season-final); use only rows with `known_at` before kickoff. Backfilled SP+/FPI are season-final, so hindsight only. A weekly `/ratings/elo?week=` pull would give pre-game Elo, but the registry pulls Elo per season.
- *From TASK-021 (PR #62):* the closing-line baseline reuses `engine.transform.market.closing_lines()`, so it matches notebook #1's recorded benchmark.
- *From TASK-021 (PR #67):* CFBD's `consensus` line stops in late 2023 (29 of 792 games in 2023, none in 2024–2025), so later closing lines are medians across books; check that the closing-line baselines don't shift at that seam (notebook #1's per-season MAE: 12.11 in 2023, 12.07 in 2024).
- **Last season carried over (settled when this task was written, 2026-10-25):** 04 § 2 says this baseline "shows how much in-season info adds", and § 9.6 makes it the bar Rung 1 must beat. So it is the model under test's own final ratings from season Y−1, frozen for all of season Y: no in-season updates and no regression toward the mean (regressing is part of the prior that Rung 1 adds), plus the home-field value fit on seasons before Y. This task builds it as a wrapper around any `RatingModel`, tested here with a stub; TASK-033 runs it with Rung 1, and a later rung's comparison can wrap that rung the same way. A team with no Y−1 rating gets the wrapped model's rating for an unseen team, and the report counts those games.

## Acceptance criteria

- [ ] AC-1: The home-field baseline predicts `pred_margin = HFA` for every non-neutral game and 0 for neutral-site games, with HFA fit only on games before the season being scored (expanding window, 04 § 9.2); a test shows a later season's games don't change it.
- [ ] AC-2: The last-season baseline, wrapping a stub rating model, predicts every game of season Y as `rating_home − rating_away + HFA × (not neutral_site)` from that model's unregressed final ratings for Y−1; its predictions don't change when a game of season Y is changed, and a team missing from Y−1 gets the stub's unseen-team rating.
- [ ] AC-3: The closing-line baseline's predicted margin for each game equals `−spread_home` from `engine.transform.market.closing_lines()` on the same lake, and each row records whether the line came from `consensus` or the median.
- [ ] AC-4: The SP+/FPI baselines use only `benchmark_ratings` rows whose `known_at` is before kickoff; when a game has none, the baseline is computed from the season-final row and every such result is labeled "hindsight benchmark", never counted as a baseline beaten.

## Out of scope

- The Rung 1 model and the comparison report (TASK-033), metrics (TASK-031).
- Weekly Elo pulls or any new CFBD endpoint.
- Using benchmarks as model inputs (M19, § 10.7).

## Files likely touched

- `python/engine/src/engine/backtest/baselines.py`: the four baselines (new).
- `python/engine/tests/test_baselines.py`: AC-1 to AC-4 (new).
- `python/engine/tests/lake_fixture.py`: `benchmark_ratings` rows with and without `known_at`.

## Verification

- Automated: `test_baselines.py`; `pnpm test`.
- Manual: run the closing-line baseline over 2022–2025 of the local lake → its per-season MAE matches notebook #1's table for those seasons, and the 2023→2024 change at the `consensus` seam is no larger than other season-to-season changes.

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
