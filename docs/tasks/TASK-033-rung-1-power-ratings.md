---
id: TASK-033
title: Build Rung 1 least-squares power ratings, plus notebooks #2–3
status: In progress
depends_on: [TASK-031, TASK-032]
size: M
model: opus
autonomy: attended
ui: false
plan_status: approved
planned_at_commit: 02abf9d
---

# TASK-033 — Build Rung 1 least-squares power ratings, plus notebooks #2–3

## Goal

Every team gets one rating per week, fit from game margins with a margin cap, recency weighting and last season's ratings as the prior, and one backtest command shows whether that beats the home-field and last-season baselines. Two notebooks walk through building the ratings by hand and turning them into probabilities.

## Context

- Task list: `docs/08-tasklist.md` › M3 › M3.5.
- Model: `docs/04-model.md` § 2 Rung 1 (`predicted_margin = rating_home − rating_away + HFA × (not neutral_site)`; least squares, one equation per game; margin cap about 28 or a log transform; recency weighting; FCS opponents pooled into a few tiers); § 2 Preseason priors (last season's final rating regressed toward the mean; `w(N)` fades with the week); § 9.1 (2014 warm-up, 2015 tuning, 2016–2023 validation); § 9.6 Phase 2 row (lower MAE than home-field only and last season's final ratings on pooled validation, per § 9.5; closing line and SP+/FPI reported alongside); § 8 Learning path (notebooks #2–3).
- Roadmap: `docs/06-roadmap.md` › Phase 2 acceptance ("one command runs a 2014–2023 backtest and produces a report comparing Rung 1 to the baselines. You can explain every number in it").
- Architecture: `docs/02-architecture.md` › Components › 1 (`models/`, built from a `ModelSpec`); › Repository layout (`python/notebooks/`).
- Decisions: D-049 (each rung ships only if it beats the previous one), D-076, D-091, D-047 (rate FCS teams, no picks on FBS-vs-FCS), D-121 (notebooks are marimo `.py` files with a `notebooks` dependency group, run from the local mirror with no API calls).
- Pattern: `python/notebooks/01-explore.py` for the notebooks.
- **Concept:** least squares is "solving lots of equations at once": 130 teams, about 800 games, one equation per game. No set of ratings fits every game, so it picks the ratings with the smallest total squared error, which adjusts for opponents for free.
- **Concept:** ratings have no natural zero (adding 5 to every team changes no prediction), so the fit needs a constraint, such as ratings averaging zero, to have one answer.
- **Decide at the plan gate:** the tuned settings and their grids (margin cap or log transform, recency half-life, prior regression and fade, ridge-style penalty if any); how FCS teams are pooled; the zero constraint; how `last_season` reuses TASK-032's wrapper with these ratings; what notebooks #2 and #3 show.
- *From TASK-030 (PR #90):* register the power model in `engine.backtest.MODELS` under `power` (the spec's `base`), replacing nothing: `stub` stays the harness's smoke test. The harness calls `fit(games, as_of)` every week with every final game before `as_of`, from all earlier seasons, FCS games included, so refitting learned weights once a season (04 § 9.2) is the model's job. `GameResult` carries no team classification, so pooling FCS teams into tiers (04 § 2, D-047) needs a field on it or a new harness input; the plan decides which (D-131).
- *From TASK-031 (PR #91):* the § 9.6 bar "lower MAE than both baselines on pooled validation" is `engine.backtest.bootstrap.compare(a_rows, b_rows)`: two runs' `predictions.parquet` rows, paired by game, week-level bootstrap (10,000 resamples, seed 20261007); `.beats` is true when the 95% interval of A's minus B's absolute error is entirely below zero (D-091, D-132). There's no CLI compare: call it from the notebook or the report step. `engine backtest … --report DIR` writes each run's own metrics and gates.
- *From TASK-032 (PR #92):* the baselines are in `engine.backtest.MODELS` (`home_field`, `last_season`, `closing_line`, `sp`, `fpi`; D-133) and their rows carry a `note`. The comparison must run them through `engine.backtest.baselines.comparable(rows)`, which drops `hindsight benchmark` and `unrated team` games, and report how many of each it dropped and how many `unseen team` games `last_season` kept.
- *From TASK-032 (PR #92), open question for the plan:* `--model last_season` wraps `MODELS[spec.base]` and the default tuner then picks the wrapped model's settings by last season's own MAE, not the settings Rung 1 chose; `home_field`, `closing_line`, `sp` and `fpi` ignore the spec and re-run the grid for nothing. How does `--compare baselines` hand Rung 1's chosen settings to `last_season` (the spec resolved with them)?

## Acceptance criteria

- [ ] AC-1: Given a noiseless fixture of 4 teams whose margins are generated from known ratings and HFA, a fit with no cap, recency or prior recovers each rating and HFA within 0.01, with ratings averaging zero.
- [ ] AC-2: Given the spec's margin cap c, a game won by more than c gives the same ratings as the same game won by exactly c; given half-life h, a game h weeks older than another has half its weight (checked on the fitted weights).
- [ ] AC-3: Entering week 1 of season Y, every team's rating equals its final Y−1 rating regressed by the spec's factor (a team new to the data gets its pool's prior), and the prior's weight falls as the season's games accumulate as the spec defines.
- [ ] AC-4: `engine backtest --spec <power-v1 spec> --seasons 2016-2023 --compare baselines --report <dir>` (2014 warm-up, 2015 tuning) writes one report with Rung 1, home field only, last season carried over (Rung 1's final ratings), the closing line and SP+/FPI on the same games, and the paired bootstrap result for Rung 1 against each of the first two.
- [ ] AC-5: On the local lake, Rung 1 beats both home field only and last season carried over on pooled 2016–2023 validation (§ 9.5: the 95% interval of the MAE difference is entirely below zero). If it doesn't, the task goes to Blocked with the report attached; settings are never tuned on 2024–2025 to fix it.
- [ ] AC-6: Notebooks `python/notebooks/02-ratings-by-hand.py` and `03-ratings-to-probabilities.py` run top to bottom from the local mirror with the CFBD ledger unchanged; #2 solves one week's ratings with the least-squares equations written out and matches the engine's ratings for that week within 0.01; #3 turns a rating gap into a margin, a cover probability and an EV with TASK-029's functions.

## Out of scope

- Publishing ratings or predictions to Postgres (TASK-035).
- Rung 2 efficiency ratings, fitted priors from talent, returning production and recruiting (M4.1, M4.2).
- Conference-tier shrinkage (M4.1, 04 § 10.4).
- Tuning pick rules (M4.4) or any holdout run (M4.7).

## Files likely touched

- `python/engine/src/engine/models/__init__.py` and `power.py`: Rung 1 as a `RatingModel` and `GamePredictor` (new).
- `python/engine/src/engine/sports/cfb/`: FCS pooling, if it's CFB-specific.
- `python/engine/src/engine/cli.py`: `--compare baselines` on `engine backtest`.
- `python/engine/specs/power-v1.json` (or where the plan puts specs): the Rung 1 spec (new).
- `python/engine/tests/test_power_ratings.py`: AC-1 to AC-3, and a golden backtest on the TASK-030 fixture (new).
- `python/notebooks/02-ratings-by-hand.py`, `03-ratings-to-probabilities.py`: AC-6 (new).
- `docs/04-model.md` § 9.6: Rung 1's pooled result beside the Phase 2 row (approved at plan).
- `docs/decisions.md`: Rung 1's settings and the comparison result as a D-### row.

## Verification

- Automated: `test_power_ratings.py`; `pnpm test`.
- Manual: the AC-4 command on the local lake → read the report together with the owner and explain each row (the Phase 2 acceptance); spot-check one 2019 week's top 10 against intuition; run both notebooks.

## Follow-ups

_Work noticed during this task and deliberately left out. Each bullet ends `→ <path> § <section>` (where it was placed) or `→ not tracked: <reason>`. See `.claude/skills/track-follow-ups/classify.md`; the PR's Follow-ups section is copied from here._

- 04 § 2 Rung 1 says FCS opponents pool into "a few tiers"; Rung 1 uses one pool, because the lake holds only games with an FBS team, so each FCS team has one or two games and nothing to tier them by (approved at plan) → docs/04-model.md § 2 Rung 1
- 04 § 9.6 Phase 2 row: record Rung 1's pooled 2016–2023 result beside the bar (approved at plan) → docs/04-model.md § 9.6

## Plan

_Approved 2026-10-26 in the session (home field: option A, Rung 1's fitted HFA)._

**Design (the plan-gate decisions)**
- **In-season fit:** weighted least squares on this season's games before `as_of`, one equation per game: unknowns are each FBS team's rating, one shared rating for every non-FBS team (the FCS pool), and HFA when `home_field` is `fit` (else fixed). Margins clipped to ±`margin_cap`; game weight `0.5 ** (age_weeks / recency_half_life_weeks)`, age measured from `as_of`. FBS ratings average zero (exact re-centring; predictions don't move). No ridge in Rung 1 (`ridge_alpha` refused if set; Rung 2 brings it). Solved with numpy `lstsq` (minimum norm, so an early week with unconnected groups still solves).
- **Prior:** `prior = (1 − regression) × last season's final rating`; a team with no rating last season gets the FCS pool's prior (every FBS newcomer since 2014 moved up from FCS); with no earlier season, 0. Blend: `rating = w·prior + (1 − w)·in_season`, `w = clamp((Z − N) / (Z − 1), 0, 1)`, N = 1 + this season's weeks with finished games, Z = `prior.decay.zero_at_week`; a team with no in-season game keeps its prior. HFA blends the same way from last season's final HFA. Only `components: [last_season]` and `decay: linear` are accepted. Last season's final rating is the model's own rating after its last game (memoised by season). The season a fit belongs to comes from `as_of` (July or later: that year), in `sports/cfb`.
- **FCS pooling:** `GameContext` gains optional keyword-only `home_classification` / `away_classification`, filled by the harness from staged games; `sports/cfb/teams.py` maps anything but `fbs` (missing included) to the pool. `Ratings.teams` lists every team id seen, FCS ones at the pool's rating; `params` holds `home_field`, `margin_sd`, `prior_weight`, `pool_fcs`, `new_team`.
- **σ:** RMSE of the model's own week-by-week predictions of last season's FBS-vs-FBS games (out of sample, once a season); 14.0 before there's one.
- **Spec** `python/engine/specs/power-v1.json`: margin_cap {28, 38, 50}, recency_half_life_weeks {8, 16, 32}, prior.regression {0.1, 0.2, 0.3}, prior.decay linear zero_at_week {9, 12, 16} (81 points; **revision 1**, approved in the session: the first real-lake run on the plan's grid {21, 28, 38} / {4, 8, 16} / {0.2, 0.35, 0.5} / {6, 9, 12} picked an edge of nearly every setting in nearly every season), home_field fit, picks fixed (min_edge 3, min_prob 0.55, k 1, tiers 5/3.5/2.5).
- **Home field baseline (option A, amends D-133):** `home_field` wraps the spec's model like `last_season` and predicts only its fitted HFA entering each week (0 at a neutral site), σ = spread of the margins around it in the games it was fit on before the season, matching § 9.6's "home by the fitted home-field value".
- **`--compare baselines`:** run Rung 1, then each baseline (`home_field`, `last_season`, `closing_line`, `sp`, `fpi`) with Rung 1's per-season choices via a new `harness.run(..., choices=)` (no re-tuning, TASK-032's open question); each run written to its own `backtests/` folder; rows through `baselines.comparable()`; one report = Rung 1's report plus a Comparison section (each model's games, MAE, Rung 1's MAE on the same games, difference and 95% interval, beats; dropped `hindsight benchmark` / `unrated team` counts and kept `unseen team` count). Refused with `--holdout` or `--model`.

**Steps**
1. numpy into the engine's `train` extra (`uv add`); the classification fields on `GameContext`, filled in `harness.load`.
2. `sports/cfb/teams.py`: `pool_of(classification)`, `season_of(as_of)`.
3. `models/power.py` (`PowerRatings`, `game_weights()`), `models/__init__.py`; register `power` in `backtest.MODELS`.
4. `harness.run(..., choices=)`; `home_field` wrapping the spec's model (`baselines.py`, `test_baselines.py`).
5. `backtest/compare.py`, the report's Comparison section, `engine backtest --compare baselines`.
6. `specs/power-v1.json`; the golden power CSV on the TASK-030 fixture.
7. AC-4 command on the local lake → AC-5 verdict (Blocked with the report if Rung 1 doesn't beat both).
8. Notebooks #2 and #3.
9. 04 § 2 / § 9.6, the decision row.

**Files**
- `python/engine/pyproject.toml`, `python/uv.lock`: numpy (lock via `uv`) — not in Files likely touched
- `python/engine/src/engine/core/interfaces.py`: classification fields — not in Files likely touched
- `python/engine/src/engine/backtest/harness.py`: fill them; `run(choices=)` — not in Files likely touched
- `python/engine/src/engine/backtest/__init__.py`: register `power`; `home_field` wraps the spec's model — not in Files likely touched
- `python/engine/src/engine/backtest/baselines.py`, `python/engine/tests/test_baselines.py`: fitted-HFA home field (option A) — not in Files likely touched
- `python/engine/src/engine/backtest/compare.py` (new), `backtest/report.py`: the comparison — not in Files likely touched
- `python/engine/src/engine/sports/cfb/teams.py` (new): FCS pool, season of a date
- `python/engine/src/engine/models/__init__.py`, `power.py` (new): Rung 1
- `python/engine/src/engine/cli.py`: `--compare baselines`
- `python/engine/specs/power-v1.json` (new)
- `python/engine/tests/test_power_ratings.py` (new), `tests/fixtures/backtest_power_golden.csv` (new), `tests/test_backtest_compare.py` (new)
- `python/notebooks/02-ratings-by-hand.py`, `03-ratings-to-probabilities.py` (new)
- `docs/04-model.md`, `docs/decisions.md`

**Test strategy**
- AC-1: `test_power_ratings.py::test_noiseless_fixture_recovers_ratings_and_home_field`
- AC-2: `test_margin_beyond_the_cap_fits_like_the_cap`, `test_a_game_one_half_life_older_has_half_the_weight`
- AC-3: `test_week_one_is_last_season_regressed`, `test_a_new_team_gets_the_pool_prior`, `test_the_prior_weight_falls_as_weeks_pass`
- AC-4: `test_backtest_compare.py::test_compare_baselines_writes_one_report` (fixture lake through the CLI); `test_power_ratings.py::test_power_backtest_matches_the_golden_file`
- AC-5: manual, the AC-4 command on the local lake; result in Review log, 04 § 9.6 and the decision
- AC-6: manual, both notebooks headless with the CFBD ledger hashed before and after; notebook #2 asserts its hand solve matches the engine within 0.01

**Risks:** the real run is ~10–20 min; the season-from-date rule is CFB-specific; early weeks can have unconnected groups (minimum-norm solve, small blend weight).

## Review log

_Filled by /implement-task. One line per round._

## Blocked

_Only if status is Blocked: what failed, what was tried, best hypothesis, decision needed._

## Metrics

- Verify rounds:
- Review rounds:
- First-pass AC FAILs:
- Plan revisions after approval:
