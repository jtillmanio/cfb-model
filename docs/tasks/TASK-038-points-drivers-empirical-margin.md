---
id: TASK-038
title: Rate units in points, with drivers and the empirical margin distribution
status: Ready
depends_on: [TASK-036, TASK-037]
size: M
model: opus
autonomy: attended
ui: false
plan_status: none
planned_at_commit:
---

# TASK-038 — Rate units in points, with drivers and the empirical margin distribution

## Goal

Every prediction explains itself: its drivers (each unit matchup, plus home field) add up to the predicted margin, and each team's overall rating is its offense plus its defense in points. Cover probabilities come from how real margins have scattered around past predictions, so key numbers like 3 and 7 carry their weight, both in the backtest's grading and in what `engine rate` publishes.

## Context

- Task list: `docs/08-tasklist.md` › M4 › M4.3. **The margin model itself moved to M4.1** (TASK-036; owner, 2026-10-27). **Writing the unit ratings to `team_ratings` was added here** (owner, 2026-10-27), since this is where offense and defense are in points.
- Model: `docs/04-model.md` § 3 Simulating a single game (the empirical margin distribution over a plain bell curve; key numbers 3, 7, 10, 14); § 6 Engineering contract (`drivers` as `(label, points)` contributions; the light core turns ratings into a prediction for the API); § 10.2 (rate each metric, convert to points with the margin model, sum: overall = offense + defense + special teams, special teams 0 until M18.3); § 9.2 (σ and the empirical distribution are learned weights, fit on seasons before the one predicted and refit once a season); § 9.4 (calibration bins, Brier score on win probability).
- Product: `docs/01-product.md` › F-05 outcomes (the drivers waterfall lands on the model margin; the projected-margin panel splits outcomes three ways). The driver rows in `design/sample-data.md` § 2 show the shape: one row per unit matchup, special teams, home field (0 at a neutral site), positive for one side. Their numbers are sample data.
- Data: `team_ratings.off_rating`, `def_rating`, `st_rating` (NULL until special teams is rated) and `components` (unit ratings keyed by input-registry id) exist (`docs/03-data-model.md` › Models & outputs) and aren't written yet; `engine rate` (`publish/models.py`) writes `rating` and each prediction's `drivers`.
- Decisions: D-053 (v1 uses the empirical distribution), D-117 (the overall rating is the sum of its units in points), D-130 (cover probability goes through the `MarginDistribution` protocol, whose `prob_above` and `prob_below` leave room for push mass on whole-number lines; scipy likely joins the light core here), D-132 (grading uses `NormalMargin(margin_sd)` per row; its Revisit if names this task), D-135 (`drivers` entries are `{label, points}`, home − away, summing to `pred_margin`), D-136 (`engine rate`), hard rule 5.
- Pattern: `NormalMargin` in `python/engine/src/engine/core/probability.py`; `grade_rows` in `python/engine/src/engine/backtest/metrics.py`; `write` in `python/engine/src/engine/publish/models.py`.
- **Concept:** an empirical distribution counts how often real margins landed at each distance from the prediction, instead of assuming a bell curve. Margins pile up on 3 and 7 because scores come in 3s and 7s, so a line of −3 has a real chance of a push and −2.5 vs −3.5 differ by more than a bell curve says.
- **Runs after M4.2 (TASK-037; owner, 2026-10-27).** The empirical distribution is fit on the residuals of the model with its fitted priors, so AC-5 describes v1. The prior is built on the overall rating (last season's rating, talent, returning production, recruiting), so the plan decides how the blended prior splits into offense and defense per input, keeping AC-2's sum exact in every week, prior-heavy early weeks included.
- **Light core:** the API turns ratings into a prediction for hypothetical matchups, so the distribution must be evaluable from `engine.core` with what a model run stores (`fitted_params`, jsonb), never from the training stack (hard rule 5; `test_core_imports.py`).
- **Decide at the plan gate:** the distribution's representation (out-of-sample residuals from earlier seasons, binned on whole points, smoothed or not, scaled with σ or by spread size); how a push enters a cover probability and the picks; whether the market's win probability in the report uses the same distribution; how each input's offense and defense convert to points and what the drivers are (one per unit matchup, home field, and any intercept or remainder, so they sum exactly); the driver labels (the registry's labels; home and away rather than team names, which the UI fills in); and what `components` holds.
- *From TASK-031 (PR #91):* the backtest grades cover probabilities with `NormalMargin(margin_sd)` per row (`engine.backtest.metrics.grade_rows`); when the empirical distribution lands, the harness rows must carry what it needs and `grade_rows` must use it, or calibration and picks are graded on the wrong curve (D-132 › Revisit if).
- *From TASK-036 (PR #101), open question for the plan:* Rung 2's per-stat offense and defense ratings and the margin model's coefficients live inside the fit (`EfficiencyRatings.stat_ratings()`; `fitted_params` has `b_off_<stat>`, `b_def_<stat>`, `tier_<name>`; D-137); `Ratings.teams` holds only each team's total in points, `Σ b·rating`, and `drivers` are still Rung 1's three. This task exposes each unit in points and writes them to `team_ratings`. The six inputs overlap heavily, so single coefficients are unstable (entering 2019 week 10, rush and pass success rate had negative offense coefficients while overall success rate had +176); per-unit points and a drivers waterfall may need grouped inputs (e.g. one rushing and one passing unit) or a constrained fit to read sensibly. σ is the margin model's residual RMSE until the empirical distribution replaces it.
- *From TASK-037 (PR #102):* under `decay: {type: fitted}` (v1's setting now) the margin model is fit jointly with the decay's `k` (`EfficiencyRatings.fit_margin`, D-138): its residuals, the ones an empirical distribution is fit on, are those at the chosen `k` (`MarginModel.decay_k`), and `MatchupRow` now also carries the prior-only and in-season-only gaps. A unit's points come from its blended rating, so the prior's returning production, talent and recruiting reach `drivers` through the units, not as entries of their own.

## Acceptance criteria

- [ ] AC-1: For every prediction the efficiency model makes on the two-season backtest fixture, `drivers` holds a home-field entry and one entry per rated unit matchup, labeled from the input registry, and the points sum to `pred_margin` within 1e-9. At a neutral site the home-field entry is 0, and swapping home and away negates every entry.
- [ ] AC-2: For every team the efficiency model rates entering every fixture week, its offense and defense contributions in points (special teams 0) sum to its overall rating within 1e-9. `components` holds one offense and one defense value per input-registry id the spec rates.
- [ ] AC-3: Given earlier-season residuals with more mass at 3 and 7 than at their neighbours, `EmpiricalMargin` in `engine.core`: at a whole-number threshold, `prob_above`, `prob_below` and the push mass sum to 1 with push mass > 0; at a half-point threshold the push mass is 0; and the margin lands in (2.5, 3.5) more often than under `NormalMargin` with the same σ. It's fit only on seasons before the one predicted (a fit for season Y given a season-Y residual raises), and `test_core_imports.py` still passes.
- [ ] AC-4: With `distribution: empirical`, `grade_rows` grades each row with that row's own distribution, not `NormalMargin(margin_sd)`. A test where the two give different cover probabilities shows the cover probability, calibration bin, pick and contest top N follow the empirical one. With `distribution: normal`, every existing golden file is unchanged.
- [ ] AC-5: On the local lake, pooled 2016–2023, the report gives the Brier score on cover probability and the calibration bins for `empirical` against `normal`, the spec being otherwise the same, on the same games. `efficiency-v1.json` uses `empirical` only if its Brier score is no worse than `normal`'s. Otherwise it keeps `normal`, and the decision row says why (D-053 revisited). The result is recorded in 04 § 3.
- [ ] AC-6: `engine rate --spec <efficiency spec> --season Y --week N --target test` on the fixture lake writes every `team_ratings` row with `off_rating` and `def_rating` in points, `rating` = `off_rating` + `def_rating` within 1e-9, `st_rating` NULL and `components` keyed by input-registry id; each `predictions` row's `drivers` sum to its `pred_margin` within 1e-9. A `power` spec's rows keep `off_rating`, `def_rating` and `components` NULL.

## Out of scope

- The margin model and its coefficients (M4.1, TASK-036) and the fitted priors (M4.2, TASK-037).
- A game-specific σ from rating uncertainty (M19.2) and a drive-level simulator (Phase 7 research, D-053).
- Rating special teams (M18.3): `st_rating` stays NULL and its driver 0.
- Rendering the drivers waterfall or the distribution chart (M7, F-05).
- Tuning pick rules on the new probabilities (M4.4).

## Files likely touched

- `python/engine/src/engine/core/probability.py`: `EmpiricalMargin` behind `MarginDistribution`.
- `python/engine/src/engine/core/interfaces.py`: if `Ratings` carries each team's unit contributions.
- `python/engine/src/engine/models/efficiency.py`: units in points, drivers, the fitted distribution.
- `python/engine/src/engine/backtest/harness.py`: rows carry what the distribution needs.
- `python/engine/src/engine/backtest/metrics.py`: `grade_rows` and the win-probability score use each row's distribution.
- `python/engine/src/engine/backtest/report.py`: the empirical-vs-normal comparison, if it's a report section.
- `python/engine/src/engine/publish/models.py`: write `off_rating`, `def_rating` and `components`.
- `python/engine/pyproject.toml`, `python/uv.lock`: scipy, if the light core needs it (via `uv add`).
- `python/engine/specs/efficiency-v1.json`: `distribution`.
- `python/engine/tests/test_core_probability.py`: AC-3.
- `python/engine/tests/test_efficiency_ratings.py`: AC-1, AC-2.
- `python/engine/tests/test_backtest_metrics.py`: AC-4.
- `python/engine/tests/test_publish_models.py`: AC-6.
- `python/engine/tests/fixtures/backtest_efficiency_golden.csv`: regenerated if the rows gain columns.
- `docs/04-model.md` § 3 and § 10.2: how the distribution and the units are built, and the AC-5 result.
- `docs/03-data-model.md` › Lake layout › Backtests, › Models & outputs: new `predictions.parquet` columns; what `components` holds.
- `docs/decisions.md`: the distribution, the drivers and the unit split as a D-### row.

## Verification

- Automated: the tests above; `test_core_imports.py`; `pnpm test`.
- Manual: the AC-5 runs on the local lake → read the Brier and calibration comparison with the owner; `engine rate` one 2025 week to the dev database and check one game's drivers add up to its margin and one team's offense plus defense equals its rating; confirm `data/cfbd_calls.json` is unchanged.

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
