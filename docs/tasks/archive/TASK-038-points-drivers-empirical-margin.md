---
id: TASK-038
title: Rate units in points, with drivers and the empirical margin distribution
status: Done
depends_on: [TASK-036, TASK-037]
size: M
model: opus
autonomy: attended
ui: false
plan_status: approved
planned_at_commit: b1d04a8
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

- [x] AC-1: For every prediction the efficiency model makes on the two-season backtest fixture, `drivers` holds a home-field entry and one entry per rated unit matchup, labeled from the input registry, and the points sum to `pred_margin` within 1e-9. At a neutral site the home-field entry is 0, and swapping home and away negates every entry.
- [x] AC-2: For every team the efficiency model rates entering every fixture week, its offense and defense contributions in points (special teams 0) sum to its overall rating within 1e-9. `components` holds one offense and one defense value per input-registry id the spec rates.
- [x] AC-3: Given earlier-season residuals with more mass at 3 and 7 than at their neighbours, `EmpiricalMargin` in `engine.core`: at a whole-number threshold, `prob_above`, `prob_below` and the push mass sum to 1 with push mass > 0; at a half-point threshold the push mass is 0; and the margin lands in (2.5, 3.5) more often than under `NormalMargin` with the same σ. It's fit only on seasons before the one predicted (a fit for season Y given a season-Y residual raises), and `test_core_imports.py` still passes.
- [x] AC-4: With `distribution: empirical`, `grade_rows` grades each row with that row's own distribution, not `NormalMargin(margin_sd)`. A test where the two give different cover probabilities shows the cover probability, calibration bin, pick and contest top N follow the empirical one. With `distribution: normal`, every existing golden file is unchanged.
- [x] AC-5: On the local lake, pooled 2016–2023, the report gives the Brier score on cover probability and the calibration bins for `empirical` against `normal`, the spec being otherwise the same, on the same games. `efficiency-v1.json` uses `empirical` only if its Brier score is no worse than `normal`'s. Otherwise it keeps `normal`, and the decision row says why (D-053 revisited). The result is recorded in 04 § 3.
- [x] AC-6: `engine rate --spec <efficiency spec> --season Y --week N --target test` on the fixture lake writes every `team_ratings` row with `off_rating` and `def_rating` in points, `rating` = `off_rating` + `def_rating` within 1e-9, `st_rating` NULL and `components` keyed by input-registry id; each `predictions` row's `drivers` sum to its `pred_margin` within 1e-9. A `power` spec's rows keep `off_rating`, `def_rating` and `components` NULL.

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

- The six inputs overlap heavily, so single per-input drivers may be large and offsetting (they still sum exactly); grouped units (one rushing, one passing) or a constrained margin fit would read more cleanly (approved at plan) → docs/08-tasklist.md § M19.1
- M7.6 (`/games/{id}`) evaluates the run's distribution with `EmpiricalMargin.from_params(fitted_params)`, falling back to `NormalMargin(margin_sd)` when it returns None (every v1 run, which keeps `normal`); drivers are labelled home/away for the UI to fill in, and there's no special-teams entry until M18.3 rates it (approved at plan) → docs/08-tasklist.md § M7.6
- Candidate decision: the empirical distribution, push handling, the drivers and the unit split (approved at plan) → docs/decisions.md § D-139
- Under an empirical distribution, when a key number makes the liked side the one the edge leans against, `core.picks.pick` still qualifies and tiers the pick on `abs(edge)`, so it can pick a side its own margin disagrees with (spec review R1); pick rules should pass such a game or measure the edge for the liked side. Moot while v1 is `normal` → docs/08-tasklist.md § M4.4

## Plan

Approved 2026-10-28 by the owner.

**Decisions.**

- **Units in points (AC-2):** offense = Σₖ b_offₖ·offₖ, defense = Σₖ b_defₖ·defₖ, from the blended per-stat vector the model already builds; the prior is per stat and side, so the split is exact in every week, prior-heavy ones included.
- **Drivers (AC-1):** home field, plus per input `"<registry label>: home offense vs away defense"` = b_off·off_home − b_def·def_away and `"<registry label>: away offense vs home defense"` = b_def·def_home − b_off·off_away. 13 entries for v1; they sum exactly with no remainder. No special-teams entry until M18.3.
- **Empirical distribution (AC-3):** a pmf on whole-number margins: Normal(pred, σ) density × a key-number weight per |margin| 0–50 (1 beyond), renormalized. Weights are fit (iterative proportional fitting) so the expected count at each whole margin matches the observed count on the margin model's own earlier-season games at the chosen k, shrunk toward 1 by 25 pseudo-games. Stored in `fitted_params` as `margin_weight_<n>`, evaluated in `engine.core` with the stdlib; the fit imports numpy lazily. No scipy.
- **Pushes:** `MarginDistribution` gains `prob_at` (push mass; `NormalMargin` returns exactly 0). The displayed cover probability is P(cover | no push), what ATS win % and calibration measure (pushes out); `Cover` gains `push`. Win probability likewise. Under `normal` every number is bit-identical.
- **Market win probability** in the report uses the row's own distribution.
- **`components`:** `{input_id: {"off": pts, "def": pts}}`.

**Steps.**

1. `core/probability.py`: `EmpiricalMargin` (pmf, `prob_above`/`prob_below`/`prob_at`, `from_params`/`params`, `fit` raising on a row of the predicted season or later), `prob_at` on the protocol and `NormalMargin`, `Cover.push`, conditional cover and win probabilities.
2. `core/interfaces.py`: `Ratings.units: {team: {stat: (off_pts, def_pts)}}`, empty by default.
3. `models/efficiency.py`: `fit` fills `units`; stand-ins (pools, newcomer, tier levels) get per-stat params; `predict` builds the drivers; under `empirical` the weights are fit once per season into the params and drive `home_win_prob`. `models/power.py` refuses `empirical`.
4. `backtest/harness.py`: a `margin_weights` list column, in the schema only for an empirical spec, so normal runs stay byte-identical.
5. `backtest/metrics.py`, `report.py`: `grade_rows` grades with `EmpiricalMargin(row σ, row weights)` under `empirical`; a Brier score on cover probability (pushes out) and its report row; the market's win probability on the row's distribution.
6. `backtest/compare.py`, `cli.py`: `engine compare A B` also prints each run's cover Brier and calibration bins on the shared games (AC-5).
7. `publish/models.py`: write `off_rating`, `def_rating`, `components`; NULL for power.
8. AC-5 on the local lake: 2016–2023 under `normal` and `empirical`; set `efficiency-v1.json` by the result; regenerate the efficiency golden if it changes.
9. Docs: 04 § 3 and § 10.2, 03 › Backtests and › Models & outputs, a D-### row.

**Files.** `core/probability.py`, `core/interfaces.py`, `models/efficiency.py`, `models/power.py`*, `backtest/harness.py`, `backtest/metrics.py`, `backtest/report.py`, `backtest/compare.py`*, `cli.py`*, `publish/models.py`, `specs/efficiency-v1.json`, `tests/fixtures/backtest_efficiency_golden.csv` (if v1 switches), `tests/test_core_probability.py`, `tests/test_efficiency_ratings.py`, `tests/test_backtest_metrics.py`, `tests/test_publish_models.py`, `tests/test_power_ratings.py`*, `docs/04-model.md`, `docs/03-data-model.md`, `docs/decisions.md`. (* not in Files likely touched.) No schema change; `pyproject.toml`/`uv.lock` untouched.

**Test strategy.**

- AC-1: `test_efficiency_ratings.py` — drivers sum to `pred_margin` on every fixture prediction, labels from the registry; at a neutral site home field is 0 and swapping home and away negates every entry.
- AC-2: `test_efficiency_ratings.py` — off + def = rating for every team entering every fixture week; `units` keys = the spec's inputs.
- AC-3: `test_core_probability.py` — synthetic residuals lumped at 3 and 7: above + below + push = 1 with push > 0 at a whole line, push 0 at a half line, more mass in (2.5, 3.5) than `NormalMargin` at the same σ; a season-Y row raises; `test_core_imports.py` passes.
- AC-4: `test_backtest_metrics.py` — a row where the two distributions disagree: probability, calibration bin, pick and contest top N follow the empirical one; existing goldens unchanged under `normal`.
- AC-5: manual on the local lake, read with the owner.
- AC-6: `test_publish_models.py` — efficiency rate on the test DB; power rows keep NULLs.

**Risks.** Overlapping inputs make single drivers large and offsetting (follow-up to M19.1). The empirical fit uses the margin model's in-sample fitted values: negligible bias at ~13 params on thousands of games, and the weights describe only the whole-number lattice. AC-5 runs take local-lake time.

**Revisions after approval.**

1. *The side the model likes* (owner, 2026-10-28): near a key number the edge's side can cover under 50% (home by 2.4 against −2.5 when home by 3 is common), which the calibration bins refuse. `cover_probability` keeps the edge's side unless the other side is likelier to cover; under a normal margin the edge's side is always at least 50%, so nothing changes there. Test: `test_core_probability.py::test_near_a_key_number_the_liked_side_is_the_one_more_likely_to_cover`.
2. *Where the cover Brier score shows* (owner confirmed at close-out, 2026-10-28): adding it to `Metrics` would change the report golden under `normal` (it serializes every field), against AC-4. It's `metrics.cover_brier(games)`, printed by `engine compare` with the calibration bins (step 6); the backtest report's facts name the run's cover curve instead.
3. Smaller: the key-number weights are one ratio per margin size against the plain normal's expected count, not iterative fitting (simpler to read, and `Σ observed = Σ expected` keeps it near calibrated); `backtest/baselines.py` passes `games` by keyword because `Ratings` gained a field; with home/away labels, swapping the teams moves each matchup to the other side's label (negated), which is how AC-1's swap is tested (owner confirmed this reading at close-out, 2026-10-28).

## Review log

_Filled by /implement-task. One line per round._

- Verify R1 PASS (full: typecheck, lint, db:check, test, build, e2e)
- Audit R1 PASS (every automated AC proven against main; two guard tests pass on main by design)
- Spec R1 CHANGES (a follow-up without its § section; ACs all PASS) | Schema R1 APPROVE (2 minors: non-finite units reached the jsonb cast; 03 didn't say higher off/def is better, both fixed)
- Verify R2 PASS (after the review fixes)
- Spec R2 APPROVE

## Blocked

_Only if status is Blocked: what failed, what was tried, best hypothesis, decision needed._

## Metrics

- Verify rounds: 2 (both PASS; the second after the review fixes)
- Review rounds: 2 (spec), 1 (schema); audit 1
- First-pass AC FAILs: 0 (spec R1's CHANGES was a follow-up destination, not an AC)
- Plan revisions after approval: 3 (the liked side, the owner's choice; the cover Brier in `engine compare`; small ones, see Plan)
