---
id: TASK-032
title: Add the backtest baselines: home field only, last season, closing line, SP+/FPI
status: Done
depends_on: [TASK-030]
size: S
model: sonnet
autonomy: unattended
ui: false
plan_status: approved
planned_at_commit: bd5e49c
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
- *From TASK-029 (PR #87):* Rung 0 baselines aren't `ModelSpec`s (D-130): a baseline is a name plus the wrapped model's spec, so the results and the report identify a baseline as, for example, `last_season` over the Rung 1 spec. The predictor contract is `GamePredictor` in `engine/core/interfaces.py`, returning a `Prediction`.
- *From TASK-030 (PR #90):* a baseline registers a factory in `engine.backtest.MODELS` under its name and runs with `engine backtest --model <name>`; the harness only gives a model the inputs in `harness.FIT_INPUTS` (`games` today) and refuses others by name, so the SP+/FPI baseline needs a `benchmark_ratings` input added there with its own published-before-the-game check (04 § 9.2) (D-131).

## Acceptance criteria

- [x] AC-1: The home-field baseline predicts `pred_margin = HFA` for every non-neutral game and 0 for neutral-site games, with HFA fit only on games before the season being scored (expanding window, 04 § 9.2); a test shows a later season's games don't change it.
- [x] AC-2: The last-season baseline, wrapping a stub rating model, predicts every game of season Y as `rating_home − rating_away + HFA × (not neutral_site)` from that model's unregressed final ratings for Y−1; its predictions don't change when a game of season Y is changed, and a team missing from Y−1 gets the stub's unseen-team rating.
- [x] AC-3: The closing-line baseline's predicted margin for each game equals `−spread_home` from `engine.transform.market.closing_lines()` on the same lake, and each row records whether the line came from `consensus` or the median.
- [x] AC-4: The SP+/FPI baselines use only `benchmark_ratings` rows whose `known_at` is before kickoff; when a game has none, the baseline is computed from the season-final row and every such result is labeled "hindsight benchmark", never counted as a baseline beaten.

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

- The `note` column in `predictions.parquet` needed describing (approved at plan) → docs/03-data-model.md § Lake layout › Backtests (done in this PR)
- The Benchmarks paragraph said a baseline reads `known_at` "before kickoff"; the code cuts off at the game's earliest possible kickoff (approved at close-out) → docs/03-data-model.md § Lake layout › Benchmarks (fixed in this PR)
- The baselines' design and the earliest-kickoff cutoff are a lasting decision (approved at plan; the row was extended after review R1/R2) → docs/decisions.md § D-133
- TASK-033's comparison must run the baselines through `baselines.comparable()` and report the hindsight, unrated and unseen-team games it leaves out or counts → docs/tasks/TASK-033-rung-1-power-ratings.md § Context
- `--model last_season` re-tunes the wrapped model on last season's own MAE, not on the settings Rung 1 chose, and the other baselines re-run the grid on a spec they ignore: TASK-033 decides how the comparison passes Rung 1's chosen settings → docs/tasks/TASK-033-rung-1-power-ratings.md § Context
- `harness.EARLIEST` repeats the `earliest` expression in the features SQL that sets each week's `as_of` → not tracked: a comment names both copies and a TBA test pins the harness's value; moving it into `features.py` is outside this task's files
- `ruff format` would reformat seven files already on `main` (`jobs.py`, `staging.py`, `backfill.py`, `report.py` and three tests) → not tracked: formatting isn't one of `verify.full`'s checks, and rewriting unrelated files isn't this task's diff

## Plan

_Approved 2026-10-26 (attended)._

**Design.** `GamePredictor.predict` sees only `(game, ratings, as_of)`, so baselines can't read lines or benchmarks today. A model with `baseline = True` may declare `closing_lines` and `benchmark_ratings` in `reads` (04 § 9.2 still refuses them for every other model); the harness hands it only the inputs it declared via `use(inputs)`. `History` gains the staged `benchmark_ratings` rows (optional, so older lakes still load). A model may provide `note(game, ratings) -> str | None`; results gain a nullable `note` column ("hindsight benchmark", "unseen team", "unrated team").

**Steps** (test first for each AC)
1. `HomeField`: mean non-neutral margin over seasons before `game.season`, frozen per season (AC-1).
2. `LastSeason(inner)`: the inner model's fit on games before season Y, frozen for Y, no regression; notes "unseen team" (AC-2).
3. `ClosingLine`: `-spread_home`; the row's `spread_source` records consensus vs median (AC-3).
4. `BenchmarkRating("sp"|"fpi")`: latest row with `known_at` < kickoff, else the season-final row, noted "hindsight benchmark"; plus HFA for non-neutral games (AC-4).
5. Register `home_field`, `last_season`, `closing_line`, `sp`, `fpi` in `MODELS`; `last_season` wraps `MODELS[spec.base]` and refuses cleanly until `power` exists (TASK-033).

**Files:** `backtest/baselines.py` (new), `backtest/harness.py` (inputs hook, `note` column, benchmark load), `backtest/__init__.py`, `tests/test_baselines.py` (new), `tests/lake_fixture.py`, `tests/test_backtest_golden.py` + golden CSV only if the `note` column changes it, `docs/decisions.md` (D-133), `docs/03-data-model.md` § Lake layout › Backtests (`note` column).

**Tests:** AC-1 `test_home_field_ignores_later_seasons` (+ neutral gives 0); AC-2 `test_last_season_frozen_and_unseen_team`; AC-3 `test_closing_line_matches_closing_lines`; AC-4 `test_benchmark_uses_known_at_else_hindsight`; `check_reads` still refuses `closing_lines` for a non-baseline.

**Risks:** HFA as the mean non-neutral margin runs a little high (FCS games included); Rung 1 fits it jointly. Manual check on 2024-2025 compares against `closing_lines()` directly rather than spending holdout looks.

**Follow-ups (approved at plan):** `docs/03-data-model.md` § Lake layout › Backtests: `note` column; D-133 in the decisions log.

## Review log

Verify R1 PASS → R2 PASS after the review fixes → R3 PASS on the branch head | Audit R1 PASS (4 of 4 ACs proven; 9 mutants run, the one survivor is equivalent) | Schema R1 CHANGES (TBA cutoff, no point-in-time assertion) → R2 APPROVE | Spec R1 CHANGES (no point-in-time assertion on the benchmark path) → R2 APPROVE

Manual check (closing-line baseline over the local lake, read straight from `closing_lines()`, so no holdout look was spent): per-season MAE 12.03 (2022, 765 consensus / 11 median), 12.11 (2023, 29 / 763), 12.07 (2024, all median), 11.81 (2025, all median). 2023 and 2024 match notebook #1. The change at the consensus seam (2023 → 2024, −0.04) is smaller than 2022 → 2023 (+0.08) and 2024 → 2025 (−0.26).

## Blocked

_Only if status is Blocked: what failed, what was tried, best hypothesis, decision needed._

## Metrics

- Verify rounds: 3 (all PASS; re-runs after the review fixes)
- Review rounds: 2 (spec), 2 (schema); audit 1
- First-pass AC FAILs: 0 (both R1 CHANGES were a rule-4 gap, not an AC)
- Plan revisions after approval: 1 (the benchmark cutoff became a game's earliest possible kickoff, with point-in-time assertions, after schema R1; made without asking first)
