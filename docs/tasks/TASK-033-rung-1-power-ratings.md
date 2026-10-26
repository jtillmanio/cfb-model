---
id: TASK-033
title: Build Rung 1 least-squares power ratings, plus notebooks #2–3
status: Ready
depends_on: [TASK-031, TASK-032]
size: M
model: opus
autonomy: attended
ui: false
plan_status: none
planned_at_commit:
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
