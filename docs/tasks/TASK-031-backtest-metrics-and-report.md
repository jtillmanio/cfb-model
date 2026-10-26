---
id: TASK-031
title: Compute backtest metrics and write the markdown/HTML report
status: Ready
depends_on: [TASK-030]
size: M
model: opus
autonomy: attended
ui: false
plan_status: none
planned_at_commit:
---

# TASK-031 — Compute backtest metrics and write the markdown/HTML report

## Goal

Every backtest ends in a report that shows how accurate the model was against the closing line, whether its picks would have won, whether bigger edges win more often, whether its probabilities are honest, and whether a model really beats another or just got lucky.

## Context

- Task list: `docs/08-tasklist.md` › M3 › M3.3.
- Model: `docs/04-model.md` § 9.3 Lines, games and grading (closing line source per game; pushes in records but out of win %; units at −110, win +1.0u, loss −1.1u; ROI = units won ÷ units risked; CLV measured on opening-line picks against the close); § 9.4 Metrics and targets (every row: MAE gap vs closing, RMSE, ATS vs closing with a 95% interval, logistic edge trend with the § 5 buckets beside it, consistency per validation season, calibration in 2.5-point bins from 50% to 65%+ with the ±3-point rule for bins of ≥ 100 picks, avg CLV, ROI, win % by pick bucket, contest top 4, Brier score of `home_win_prob`, breakdowns); § 9.5 What "beats" means (week-level paired bootstrap, 10,000 resamples); § 5 Metrics we report.
- Architecture: `docs/02-architecture.md` › Testing strategy › Levels › Model / backtest (golden numbers that change only in a commit that says why); › Components › 1 (`backtest/`; heavy dependencies only in `engine[train]`).
- Decisions: D-076, D-077 (gate definitions: logistic slope interval above zero, ≤ 2 of 8 seasons below 50% and pooled ATS > 52.4% without the best season, calibration ±3 points on bins with ≥ 100 picks; the § 5 all-game buckets feed the gate, the pick buckets are display only), D-091 (week-level paired bootstrap), D-054 (flat 1 unit), D-046 (closing line is primary, opening also reported).
- Feature: F-37 Calibration charts (`docs/01-product.md` › Feature index): the calibration numbers computed here are what the Performance screen draws later.
- **Concept:** a calibration bin asks "of the games we called 57.5–60%, how many actually covered?". If the answer is 53%, the model is overconfident and its probabilities can't be taken at face value, however good its MAE looks.
- **Concept:** the bootstrap resamples whole weeks because games in one week share news and line moves; resampling single games would overstate how sure we are.
- **Decide at the plan gate:** the report's sections and file names (markdown and HTML from one source); which library fits the logistic regression and its interval (statsmodels in `engine[train]`, or a hand-rolled fit on numpy); the bootstrap's fixed seed; the breakdowns' bins (week of season, spread size, favorite/underdog).
- **Settled when this task was written (2026-10-25, owner accepted the recommendation):** the conference-tier breakdown waits for M4.1, which builds the per-season tier map in `sports/cfb` (04 § 10.4); a note on M4.1's stub carries it. Build the breakdowns as one function grouping by any per-game column, so M4.1 only supplies a tier per game.
- *From TASK-030 (PR #90):* the harness writes each run to the lake at `backtests/<run>/predictions.parquet`, one row per eligible game in (season, `as_of`, season type, week) order: `season`, `season_type`, `week`, `as_of`, `game_source_id`, `kickoff_at`, `home_source_id`, `away_source_id`, `neutral_site`, `pred_margin`, `margin_sd`, `home_win_prob`, `spread_home` (the close), `spread_source`, `closing_from`, `home_points`, `away_points`, `margin`; `run.json` beside it holds the spec, model, seasons and the settings chosen per season (03 › Lake layout › Backtests, D-131). It has no opening line, which CLV on opening-line picks needs (04 § 9.3): the plan decides whether this task joins it from staged `lines` (`spread_home_open`, same consensus-or-median rule) or the harness adds a column. Postseason rows have `season_type` = `postseason` for the separate report.

## Acceptance criteria

- [ ] AC-1: Given a results fixture of 5 graded picks (3 wins, 1 loss, 1 push), the report shows the record 3-1-1, win % 75.0, units +1.9 and ROI equal to units won ÷ units risked; given model and closing errors on the same games, it shows both MAEs and their difference, and RMSE.
- [ ] AC-2: Given a fixture where the edge side covers more often as the edge grows, the edge trend's logistic slope and its 95% interval are both above zero and the gate reads pass; given a fixture with no relationship, the interval includes zero and the gate reads fail; the § 5 buckets (0–1.5, 1.5–3, 3–5, 5+) are shown beside it.
- [ ] AC-3: Given picks with known displayed probabilities and outcomes, every calibration bin (2.5-point steps from 50% to 65%+) shows its pick count, mean predicted probability and actual hit rate, and the calibration gate fails exactly when a bin with ≥ 100 picks is more than 3 points off.
- [ ] AC-4: The consistency gate passes or fails per D-077 on fixtures built for each case (3 of 8 seasons below 50% fails; pooled ATS ≤ 52.4% after removing the best season fails).
- [ ] AC-5: Given two models scored on the same games where one is better by a constant amount every week, the paired week-level bootstrap (10,000 resamples, fixed seed) reports a 95% interval entirely below zero and "beats"; given identical models, the interval contains zero; the same seed gives identical intervals on repeat runs.
- [ ] AC-6: `engine backtest … --report <dir>` writes a markdown and an HTML report of every § 9.4 row the run's data supports, marking each gate pass or fail, and a golden test on the TASK-030 fixture compares the metrics against committed numbers.

## Out of scope

- The Performance and Lab screens that draw these numbers (M7), and storing metrics in `model_runs.metrics` (TASK-034 adds the column; publishing backtest runs comes later).
- Tuning pick rules (M4.4) and the go/no-go decision itself (M4.7).
- The conference-tier breakdown and the tier map it needs (M4.1, `docs/08-tasklist.md` › M4 › M4.1).
- Totals metrics (Phase 7).

## Files likely touched

- `python/engine/src/engine/backtest/metrics.py`: § 9.4 metrics and gates (new).
- `python/engine/src/engine/backtest/bootstrap.py`: the paired week-level bootstrap (new).
- `python/engine/src/engine/backtest/report.py`: markdown and HTML report (new).
- `python/engine/src/engine/cli.py`: `--report` on `engine backtest`.
- `python/engine/pyproject.toml` and `python/uv.lock` (through `uv add --optional train`): statsmodels, if the plan picks it.
- `python/engine/tests/test_backtest_metrics.py`, `test_bootstrap.py`, `test_backtest_report.py`: AC-1 to AC-6 (new).
- `docs/decisions.md`: report format and metric choices as a D-### row.

## Verification

- Automated: the three new test files; `pnpm test`.
- Manual: run the harness with the stub spec on 2016–2017 of the local lake with `--report` → open the HTML report; every row is labeled, pushes don't appear in win %, and each gate shows pass or fail.

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
