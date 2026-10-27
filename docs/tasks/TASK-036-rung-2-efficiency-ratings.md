---
id: TASK-036
title: Build Rung 2 ridge efficiency ratings and the margin model
status: Review
depends_on: [TASK-033, TASK-035]
size: M
model: opus
autonomy: attended
ui: false
plan_status: approved
planned_at_commit: 9151ead
---

# TASK-036 — Build Rung 2 ridge efficiency ratings and the margin model

## Goal

Every team gets an offense and a defense rating for each efficiency stat, adjusted for the opponents it has faced and shrunk toward an average when there's little data. A margin model turns those ratings into a predicted margin, so one backtest command scores Rung 2 on 2016–2023, compares it with Rung 1, and shows whether shrinking toward a team's conference tier beats shrinking toward the FBS average.

## Context

- Task list: `docs/08-tasklist.md` › M4 › M4.1. **The margin model moved here from M4.3** (owner, 2026-10-27): tuning on margin MAE and the tier test both need margins in points. M4.3 (TASK-038) keeps the points-per-unit split, the drivers and the empirical distribution.
- Model: `docs/04-model.md` § 2 Rung 2 (the per-stat equation `stat = μ + off_O − def_D + home_adj + ε`, ridge and its `alpha`, the stats to rate, and the margin model `pred_margin = β₀·HFA + β₁·(off_home − def_away) − β₂·(off_away − def_home) + …` fit by plain linear regression); § 9.2 (settings tuned to margin MAE, not ATS; the margin-model coefficients and σ are learned weights, fit only on seasons before the one predicted and refit once a season); § 10.2 (the v1 inputs: EPA/play and success rate, overall, rushing and passing); § 10.4 (shrinking toward a tier means unpenalized tier terms, estimated from non-conference games; the tier map is per season and lives in `sports/cfb` code; the Pac-12 counts as a power conference through 2023 and Notre Dame as Power 4); § 9.4 › Breakdowns (conference tier); § 9.6 Phase 3 row (Rung 2 must beat Rung 1, judged on all of v1 at M4.7).
- Architecture: `docs/02-architecture.md` › Components › 1 (`models/` built from a `ModelSpec`; `sports/` holds sport-specific code and shared code never imports a sport; numpy and scipy in the light core only once the API needs them).
- Data: staged `team_game_advanced` (`docs/03-data-model.md` › Staging tables; `off_`/`def_` + `ppa`, `success_rate`, `rush_ppa`, `rush_success_rate`, `pass_ppa`, `pass_success_rate`, one row per team and game, garbage time already excluded). Some team-games have no advanced row (D-121). Staged `team_seasons.conference` gives each team's conference per season.
- Decisions: D-049 (each rung ships only if it beats the one before), D-050, D-117, D-130 (`efficiency` needs at least one input and "M4.1 adds its settings"; a new optional spec field whose default keeps the old behaviour keeps the schema version), D-131 (the harness gives a model only `FIT_INPUTS`, which is `games` today), D-132 (breakdowns), D-134 (Rung 1's recency weighting, last-season prior, FCS pool and σ, to reuse or improve on), D-076, D-091.
- Pattern: `python/engine/src/engine/models/power.py`, `python/engine/specs/power-v1.json`, `python/engine/tests/test_power_ratings.py`.
- **Concept:** ridge regression adds a penalty that pulls each rating toward an anchor unless the games say otherwise. A team with 2 games is pulled hard and a team with 10 barely, and one knob (`ridge_alpha`) sets the strength, tuned in the backtest.
- **Concept:** "shrink toward the tier" adds one unpenalized term per tier (Power 4, G5, FCS). Ridge then pulls a team toward its tier's level instead of the FBS average, so a G5 team that beat two weak teams by 40 in September isn't treated as an average FBS team.
- **The harness gives only `games` today.** Rung 2 fits on per-game advanced stats, so the plan adds a fit input (a name in `FIT_INPUTS`) and the point-in-time assertion for it: each row's game finished by `as_of` (hard rule 4).
- **`GameContext` is sport-agnostic** and carries no conference. The plan decides how a team's tier reaches the model and the breakdown's per-game key.
- **Priors:** this task uses Rung 1's prior (`components: [last_season]`, linear decay). Fitted priors from talent, returning production and recruiting are M4.2 (TASK-037).
- **Decide at the plan gate:** which registry inputs v1 rates (the six § 10.2 ids, weights `fit`); the margin model's terms and how its β are fit out of sample (on earlier seasons' games, from ratings entering each game's week); whether HFA sits in each stat equation, in the margin model or both; how FCS teams enter the ridge fit (one pool as in Rung 1, or the FCS tier term); the spec's new fields (`shrink_toward: zero | tier`, with `zero` the default) and grids (`ridge_alpha`, recency half-life); the tier map's shape; a game's tier label for the breakdown; and the run time (Rung 1's comparison took about 2 minutes, and Rung 2 fits several stats per week per grid point).
- *From TASK-031 (M3 task files):* the backtest report's conference-tier breakdown (04 § 9.4 › Breakdowns) waits for this task's tier map; TASK-031's breakdowns group by any per-game column, so this task supplies a tier per game and adds the breakdown.
- *From TASK-031 (PR #91):* the hook is `engine.backtest.metrics.breakdown(name, games, key)`, added to the tuple in `metrics.compute` with a key that returns a game's tier.

## Acceptance criteria

- [x] AC-1: Given a noiseless fixture whose per-game stat values are generated from known offense and defense ratings and a home adjustment, a fit with `ridge_alpha` 0 recovers every rating within 0.01. With `ridge_alpha` > 0, a team with 2 games ends nearer its anchor, as a share of its alpha-0 distance, than an otherwise identical team with 8.
- [x] AC-2: `sports/cfb` maps each (season, conference) to Power 4, G5 or FCS: the Pac-12 is Power 4 in 2023 and its former members follow their new conference in 2024, and Notre Dame is Power 4 every season. On the local lake, every staged FBS team-season from 2014 to 2025 maps to a tier (the check prints 0 unmapped). Under `shrink_toward: tier`, a team with no games this season and no prior rates at its tier's fitted level; under `zero` it rates 0.
- [x] AC-3: The margin model's coefficients for season Y are fit only on games from seasons before Y, using ratings entering each game's week. On a noiseless fixture where margins are a known linear function of the rating matchups, they recover each coefficient within 0.01. A leakage test that feeds the fit a game from season Y, or an advanced-stat row whose game hadn't finished by `as_of`, fails with `PointInTimeError`.
- [x] AC-4: `engine backtest --spec <efficiency-v1 spec> --seasons 2016-2023 --report <dir>` (2014 warm-up, 2015 tuning) runs on the local lake, tuning each season on margin MAE over earlier seasons only. The report's Breakdowns include a conference-tier breakdown whose game counts add up to the run's eligible games. On the TASK-030 two-season fixture, the same spec's backtest matches a committed golden CSV, and a re-run gives a byte-identical `predictions.parquet`.
- [x] AC-5: On pooled 2016–2023 validation, the paired bootstrap (§ 9.5) compares `shrink_toward: tier` with `zero`, the spec being otherwise the same, and compares the chosen variant with Rung 1 (`engine/specs/power-v1.json`) on the same games. `efficiency-v1.json` keeps `tier` only if it beats `zero`; otherwise it uses `zero`. Both results, with their 95% intervals, are recorded in the decision row and 04 § 10.4.
- [x] AC-6: Against Rung 1, on the same games and with the same last-season prior: if the 95% interval of Rung 2's MAE minus Rung 1's lies entirely above zero (a clear loss), the task goes to Blocked with the report attached, and settings are never tuned on 2024–2025 to fix it. If the interval includes zero, the result is recorded and the task continues: § 9.6's Phase 3 bar is judged on all of v1 at M4.7 (owner, 2026-10-27).

## Out of scope

- Fitted preseason priors from talent, returning production and recruiting (M4.2, TASK-037).
- Each unit's contribution in points, the drivers waterfall, the empirical margin distribution, and grading with it (M4.3, TASK-038). This task's `drivers` may stay coarse.
- Writing `off_rating`, `def_rating` or `components` to `team_ratings` (M4.3).
- `shrink_toward: conference` (M19.1, 04 § 10.4) and any input beyond the six v1 ids (M18.1, M19.1).
- Tuning pick rules (M4.4) and any holdout run (M4.7).

## Files likely touched

- `python/engine/src/engine/models/efficiency.py` (new): Rung 2's ridge ratings and margin model as a `RatingModel` and `GamePredictor`.
- `python/engine/src/engine/models/__init__.py`: docstring lists `efficiency`.
- `python/engine/src/engine/backtest/__init__.py`: register `efficiency` in `MODELS`.
- `python/engine/src/engine/backtest/harness.py`: per-game advanced stats as a fit input with its point-in-time check; a team's tier per game for the breakdown.
- `python/engine/src/engine/backtest/metrics.py`: the conference-tier breakdown in `compute`.
- `python/engine/src/engine/core/spec.py`: `shrink_toward` and any efficiency settings.
- `python/engine/src/engine/core/interfaces.py`: if `Ratings` or `GameContext` needs per-unit ratings or a team group.
- `python/engine/src/engine/sports/cfb/tiers.py` (new, or `teams.py`): the per-season conference tier map.
- `python/engine/specs/efficiency-v1.json` (new).
- `python/engine/tests/test_efficiency_ratings.py` (new): AC-1, AC-3, the golden backtest.
- `python/engine/tests/test_conference_tiers.py` (new): AC-2.
- `python/engine/tests/test_backtest_leakage.py`: the advanced-stat input leak.
- `python/engine/tests/test_backtest_metrics.py`: the tier breakdown's counts.
- `python/engine/tests/test_model_spec.py`: `shrink_toward`.
- `python/engine/tests/fixtures/backtest_efficiency_golden.csv` (new).
- `python/engine/tests/lake_fixture.py`: if the two-season fixture needs conferences per season for the tier terms.
- `docs/04-model.md` § 2 Rung 2 and § 10.4: how Rung 2 is built and the tier result.
- `docs/03-data-model.md` › Lake layout › Backtests: if `predictions.parquet` gains a tier column.
- `docs/decisions.md`: Rung 2's design, the tier map and the results as a D-### row.

## Verification

- Automated: `test_efficiency_ratings.py`, `test_conference_tiers.py`, the new leakage and breakdown tests; `pnpm test`.
- Manual: the AC-4 command on the local lake, once with `tier` and once with `zero` → the AC-5 comparison read with the owner; spot-check one 2019 week's top 10 offenses and defenses against intuition; confirm the CFBD call ledger (`data/cfbd_calls.json`) is unchanged.

## Follow-ups

_Work noticed during this task and deliberately left out. Each bullet ends `→ <path> § <section>` (where it was placed) or `→ not tracked: <reason>`. See `.claude/skills/track-follow-ups/classify.md`; the PR's Follow-ups section is copied from here._

- The per-stat offense and defense ratings and the margin model's `b_off`/`b_def` coefficients live inside the efficiency fit; M4.3 exposes each unit in points and writes them to `team_ratings`; the six inputs overlap, so single coefficients are unstable (open question for its plan); σ is the residual RMSE until the empirical distribution → docs/tasks/TASK-038-points-drivers-empirical-margin.md § Context (approved at plan)
- Under `shrink_toward: tier` the prior regresses toward the team's tier level, not zero; fitted priors should keep that; every season picked `prior.regression` 0.1, the grid's lower edge → docs/tasks/TASK-037-preseason-priors.md § Context (approved at plan)
- `engine backtest --compare baselines` refuses an efficiency spec: `home_field` and `last_season` wrap only a model that fits on games alone (D-133); Rung 2 vs Rung 1 uses `engine compare` → docs/08-tasklist.md § M4.7
- Candidate decision: Rung 2's design, the tier map, the hash rule and the 2016–2023 results → docs/decisions.md § D-137
- Roadmap: Phase 3's "Rung 2" item stays open (the overall rating as the sum of unit contributions in points is TASK-038), and so does "Margin model … σ and empirical margin distribution" (the empirical distribution is TASK-038) → not tracked: both already covered by TASK-038's ACs
- The test audit's base run left a half-deleted scratch folder under this session's temp scratchpad (the guard blocked removing it) → not tracked: outside the repo, no effect on it; the owner can delete it

## Plan

_Approved by the owner 2026-10-27, with AC-4's golden run on the fixture generator extended to 2021–2023 (option a)._

**Model** (`engine/models/efficiency.py`, built from an `efficiency` spec and the sport's `Rules`, like Rung 1):

1. **Per-stat ridge, this season's games.** For each spec input, `stat = μ + off_O − def_D + h·s + tier_O − tier_D`, `s` = +1 home offense, −1 away offense, 0 neutral. `μ`, `h` and the tier terms (under `tier`) are unpenalized; team offense and defense are penalized by `ridge_alpha`. Rows are recency-weighted (half-life before `as_of`). One `lstsq` on the augmented system solves every stat at once (shared design matrix; an observation missing any spec stat is dropped). Ratings are then shifted so FBS teams average zero, per stat and side. FCS is one pooled unit (Rung 1, D-134); under `tier` it sits in the FCS tier.
2. **Prior.** Last season's final per-stat ratings, regressed by `prior.regression` toward 0 (`zero`) or toward their tier's level (`tier`), blended with Rung 1's linear decay. A team that hasn't played keeps its prior; a newcomer starts from the FCS pool's prior; with no prior, an unseen team rates at its anchor (0, or its tier's fitted level).
3. **Margin model.** `pred = HFA·(not neutral) + Σₖ b_offₖ·(offₖ,home − offₖ,away) + b_defₖ·(defₖ,home − defₖ,away)`: symmetric, no intercept, fit by OLS on the FBS-vs-FBS final games of every season before Y, from the ratings entering each game's week; refit once a season; σ = RMSE of its residuals. `home_field` fit or fixed sets HFA. It collapses to one points rating per team, `Rₜ = Σ b_off·off + b_def·def`, so `Ratings.teams` and `predict` keep Rung 1's shape; drivers stay coarse (M4.3). No earlier season → refused (exit 2). The fit asserts every training game's season is before Y (`PointInTimeError`).
4. **Run time.** Each model caches its weekly fits; the factory reuses one model per resolved spec and the model clears its caches when handed a new input.

**Plumbing:**

5. **Spec** (`core/spec.py`): top-level `shrink_toward: "zero" | "tier"`, default `zero`, schema version stays 1 (D-130). Rung 1 refuses `tier`. An efficiency input with a fixed nonzero weight is refused; weight 0 drops it.
6. **Tier map** (`sports/cfb/teams.py`): `tier(season, team, conference, classification)` → Power 4 (ACC, Big Ten, Big 12, SEC, Pac-12 through 2023, Notre Dame id 87), G5 (AAC, C-USA, MAC, Mountain West, Sun Belt, other FBS independents, Pac-12 from 2024), FCS (not FBS); an unknown FBS conference raises. `engine tiers --seasons 2014-2025` prints counts per tier and every unmapped team-season (exit 1 if any).
7. **Conferences** (`core/interfaces.py`, `backtest/harness.py`): `GameContext` gains keyword-only `home_group`/`away_group` (the team's league that season as the source labels it), filled from staged `team_seasons`; `predictions.parquet` gains both columns (03 › Lake layout › Backtests; the two golden CSVs and the report golden JSON regenerate for it). `metrics.compute` takes an optional tier function and adds a "Conference tier" breakdown (Power 4 vs Power 4, Power 4 vs G5, G5 vs G5); the CLI passes CFB's.
8. **Fit input `team_game_stats`** (`harness.py`, `publish/models.py`): staged `team_game_advanced` (garbage time excluded) joined to staged games, one row per team-game offense, handed over through `use()`. The model reads rows only through `finished_by(as_of)`, which selects by `SELECT_LAG` and raises `PointInTimeError` on any row whose game hadn't finished. `engine rate` hands it over too.
9. **`engine compare RUN_A RUN_B`** (`cli.py`, `backtest/compare.py`): the week bootstrap of A's absolute error minus B's on the games both scored, for AC-5 and AC-6.
10. **`engine/specs/efficiency-v1.json`**: the six § 10.2 inputs, weights `fit`, `shrink_toward` per AC-5; grid α {2, 5, 12}, half-life {8, 16, 32}, regression {0.2, 0.3}, Z {12, 16}; widened once if seasons keep picking an edge (as D-134).
11. **Docs**: 04 § 2 Rung 2 and § 10.4 (how it's built, the AC-5 result), 03 › Backtests (new columns), a D-### row (design, tier map, results).

**Files:** `models/efficiency.py` (new), `backtest/__init__.py`, `backtest/harness.py`, `backtest/metrics.py`, `backtest/compare.py`, `core/spec.py`, `core/interfaces.py`, `sports/cfb/teams.py` (tier map here, not a new `tiers.py`), `cli.py`, `publish/models.py`, `specs/efficiency-v1.json` (new); tests `test_efficiency_ratings.py` (new; AC-1, AC-3 incl. both leak tests, AC-4 golden and re-run), `test_conference_tiers.py` (new; AC-2), `test_backtest_metrics.py`, `test_model_spec.py`, `test_backtest_compare.py`, `fixtures/backtest_efficiency_golden.csv` (new); regenerated `fixtures/backtest_golden.csv`, `backtest_power_golden.csv`, `backtest_report_golden.json`; docs 03, 04, decisions. Not touched: `models/__init__.py` is folded in only if its docstring needs it; `test_backtest_leakage.py` (the stats leak test lives with AC-3). Size: 20 hand-edited files plus 3 regenerated fixtures; kept whole (owner, 2026-10-27).

*As built:* `models/power.py` also changed (Rung 1's refusal of `tier`, step 5) and `models/__init__.py`'s docstring (it named Rung 1 only); `backtest_report_golden.json` didn't change (its test computes metrics without the tier labeller). The grid was widened once (step 10): see D-137.

**Test strategy:**
- AC-1 → `test_efficiency_ratings.py::test_noiseless_ratings_are_recovered_at_alpha_zero`, `::test_ridge_pulls_a_two_game_team_harder_than_an_eight_game_team`
- AC-2 → `test_conference_tiers.py` (Pac-12 2023 vs 2024 members, Notre Dame every season, unknown conference raises, `engine tiers` on a fixture lake), `test_efficiency_ratings.py::test_an_unseen_team_rates_at_its_anchor` (tier vs zero); manual: `engine tiers --seasons 2014-2025` on the local lake prints 0 unmapped
- AC-3 → `test_efficiency_ratings.py::test_noiseless_margin_coefficients_are_recovered`, `::test_a_margin_fit_given_a_game_from_the_predicted_season_fails`, `::test_a_stat_row_whose_game_had_not_finished_fails`
- AC-4 → `test_efficiency_ratings.py::test_the_efficiency_backtest_matches_the_golden_file` (fixture 2021–2023, `efficiency-v1.json`, scoring 2023 tuned on 2022, run twice byte-identical), `test_backtest_metrics.py::test_tier_breakdown_counts_add_up_to_the_games`; manual: the local-lake run
- AC-5, AC-6 → manual: local-lake runs of `tier`, `zero` and `power-v1.json` on 2016–2023, then `engine compare`; recorded in the D-row and 04 § 10.4
- `test_model_spec.py`: `shrink_toward` default, values, Rung 1's refusal; `test_backtest_compare.py`: `engine compare` on two fixture runs

**Risks:** run time of the grid (cache per spec; grid cut if over ~15 minutes a run); collinear inputs make `b_off`/`b_def` individually unstable (predictions aren't); Rung 2 may not beat Rung 1 (AC-6 path).

## Review log

_Filled by /implement-task. One line per round._

- Verify R1 PASS (611 pytest, e2e 40) | Audit R1 NOT RUN (the base revert in this checkout was blocked by the guard; static review OK) → R2 run by Claude in a base worktree, not independent: every new test fails on main; 2 strengthened (`engine compare` missing-run test passed on main via argparse's exit 2; the margin-row test compared no row) → PASS
- Spec R1 APPROVE (3 advisories: `engine rate` with efficiency untested, every spec's hash changed, unmapped conference → traceback) | Schema R1 CHANGES (MAJOR: `rate` contexts had no conference; MAJOR: a final game with a NULL team id would crash `load()`; MINOR: `give_inputs` in rate untested) → fixed in 35707ae, each with a test failing on 3930b84 | Verify R2 PASS (614 pytest, e2e 40) | Schema R2 APPROVE | Spec R2 APPROVE (advisory: the exit-2 refusal untested → test added in e3a9b43, fails on 3930b84)
- Manual: `engine tiers --seasons 2014-2025` 1,566 FBS team-seasons, 0 unmapped; AC-4 local run 5,954 games, tier breakdown 2659 + 788 + 2507; AC-5 tier vs zero −0.19 (−0.28 to −0.11); AC-6 vs Rung 1 −0.14 (−0.30 to +0.01), continue; 2019 week 10 top 10s look right (Ohio State, Alabama, Clemson, Oklahoma, LSU…); CFBD ledger unchanged (md5 98e4a521…)

## Blocked

_Only if status is Blocked: what failed, what was tried, best hypothesis, decision needed._

## Metrics

- Verify rounds: 2 (both PASS; the second after the review fixes)
- Review rounds: 2 (spec), 2 (schema); audit 2 (R1 blocked, R2 by Claude in a worktree)
- First-pass AC FAILs: 0 (schema R1's CHANGES were `rate` and `load()` robustness, not an AC)
- Plan revisions after approval: 0 (`models/power.py` and `models/__init__.py` fell under steps 5 and 11; the grid widened once as step 10 allowed)
