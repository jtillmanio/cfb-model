---
id: TASK-037
title: Add preseason priors with fitted decay blending
status: Review
depends_on: [TASK-036]
size: M
model: opus
autonomy: attended
ui: false
plan_status: approved
planned_at_commit: 10e933e
---

# TASK-037 — Add preseason priors with fitted decay blending

## Goal

Early-season ratings start from a preseason guess built from last season's rating, returning production, roster talent and recent recruiting, with the weights and the fade-out curve learned from earlier seasons. The backtest shows whether that beats starting from last season's rating alone, and each team's talent and returning production reach Postgres for the team pages.

## Context

- Task list: `docs/08-tasklist.md` › M4 › M4.2.
- Model: `docs/04-model.md` § 2 Preseason priors (`prior = a·last season regressed + b·returning production + c·talent + d·recruiting over the last 4 classes`, weights fit on history; `rating_week_N = w(N)·prior + (1 − w(N))·in_season`, `w(N)` decaying from about 1.0 in week 1 to about 0.1 by weeks 8–10, the curve fit in the backtest); § 9.2 (prior weights and the decay curve are learned weights, fit only on seasons before the one predicted; preseason inputs use the values published before that season); § 10.4 (the prior can carry the same tier term as the ridge fit); § 6 (`prior.components`, `weights: fit`, `decay: {type: fitted}`).
- Data: staged `talent`, `returning_production` (`percent_ppa` and its splits) and `recruiting` (`rank`, `points`; one class per season, so "the last 4 classes" reads four seasons' rows), built by `engine.transform.stats` (`docs/03-data-model.md` › Staging tables). Names that don't match a team leave `team_source_id` NULL and are listed in `unmatched_teams`. Postgres `team_seasons.talent` (`Numeric(7, 2)`) and `returning_ppa_pct` (`Numeric(5, 4)`) exist (03 › team_seasons) and are never written yet.
- Architecture: `docs/02-architecture.md` › Components › 1 (`publish` upserts reference data).
- Decisions: D-130 (the spec's `Prior` already has `components`, `weights` and `decay: fitted | linear`; Rung 1 refuses `fitted`), D-134 (Rung 1's regressed last-season prior, linear decay, and the newcomer starting from the FCS pool's prior), D-136 (`engine rate` fits as the backtest does), D-119 and D-121 (what was staged and when it was pulled), hard rules 3 and 4.
- Pattern: Rung 1's prior in `python/engine/src/engine/models/power.py`; `upsert_team_seasons` in `python/engine/src/engine/publish/reference.py`, called from `publish_lake` in `publish/staging.py`.
- **Concept:** regression to the mean. Teams that were extreme last year drift back toward average, partly because some of it was luck and partly from roster turnover. Returning production says how much of last year's team is still there, so it should change how far the prior regresses.
- **Concept:** a prior plus evidence gives an updated belief, and the prior matters less as evidence piles up. The decay curve `w(N)` is that "matters less", measured from history instead of guessed.
- **Point-in-time is an assumption here.** CFBD's preseason values carry no publication date, and the backfill fetched them after each season, so the lake can't prove when they were known. The plan sets an assumed publication time per source (a recruiting class is signed before its season; returning production is computed from last season's rosters; talent is the riskiest), records it in a decision, and the fit input asserts against it (hard rule 4).
- **Default for talent (owner, 2026-10-27):** season Y's prior reads season Y−1's talent, which is certainly known before Y; the four recruiting classes cover the incoming freshmen. A recruiting class for Y is signed in the winter before Y, and returning production is built from last season's stats, so both may be read for Y itself. As a leak check, the plan also runs once with same-season talent: if that's much better than Y−1's, the value likely carries in-season knowledge and stays out. The result goes in the decision row.
- **Decide at the plan gate:** the per-source publication assumption (starting from the talent default above); what the prior weights are fit to (for example next season's final rating, or the in-season rating at a fixed week) and on which seasons; the decay curve's shape and its fitted parameter; recruiting's aggregation over 4 classes; what a team missing a component gets (FCS, newcomers, unmatched names); whether the tier term enters the prior; and which publish step writes `team_seasons.talent` and `returning_ppa_pct`, and how CFBD's `percentPPA` maps to `Numeric(5, 4)`.
- *From TASK-018 (PR #62):* CFBD's talent, returning production and recruiting carry no publication date, and backfilled pulls are fetched after the season, so "published before the season" has to be assumed per source.
- *From TASK-020 (PR #62):* Postgres `team_seasons.talent` and `returning_ppa_pct` stay NULL until this task publishes them from staging.
- *From TASK-036 (PR #101):* Rung 2's prior is per stat and side, and under `shrink_toward: tier` (v1's setting) last season's rating regresses toward its tier's level, not zero (`engine/models/efficiency.py`, D-137); fitted priors should keep that anchor. Every 2016–2023 season picked `prior.regression` 0.1, the lower edge of the grid {0.1, 0.2}, as Rung 1 did: the fitted prior weights this task adds replace that setting.

## Acceptance criteria

- [x] AC-1: Given a fixture where each team's target rating for season Y is a known linear combination of last season's regressed rating, returning production, talent and 4-class recruiting, the prior fit recovers each weight within 0.01. The fit for season Y reads only seasons before Y: given a row from season Y or later, it raises.
- [x] AC-2: Each preseason source has an assumed publication time in `sports/cfb` code, recorded in the decision row. Given a preseason row whose assumed publication time is after its season's first `as_of`, the backtest raises `PointInTimeError`. The leakage test loosens the rule to prove the check runs on every preseason input.
- [x] AC-3: With `decay: {type: fitted}`, the blend weight `w(N)` for season Y lies in [0, 1] and never increases as N grows. It's fit only on seasons before Y: changing a game in season Y leaves Y's curve unchanged, and changing a game in Y−1 can change it.
- [x] AC-4: A team missing a component (no staged row, or a name that didn't match) gets the prior the plan defines from the components it has. `fitted_params` reports, per component, how many rated teams had it missing that season.
- [x] AC-5: On the local lake, `engine backtest --spec <efficiency-v1 spec with all four components, weights fit, decay fitted> --seasons 2016-2023 --report <dir>` is compared with the same spec using `components: [last_season]` and linear decay, by the paired bootstrap (§ 9.5) on the same games, pooled and for weeks 1–3. `efficiency-v1.json` keeps the four components only if they beat last season alone; both results are recorded in the decision row and 04 § 2 Preseason priors.
- [x] AC-6: After publishing the fixture lake to the test database, a team-season with staged talent and returning production has `team_seasons.talent` and `returning_ppa_pct` equal to the staged values at the columns' scale, and a team-season with no staged row keeps NULL. Re-publishing changes no row (upserted by `(team_id, season)`, hard rule 3).

## Out of scope

- Each unit's contribution in points, the drivers and the empirical distribution (M4.3, TASK-038).
- Pulling any new CFBD endpoint, or re-pulling a season to get pre-season values (call budget; CLAUDE.md › Domain conventions).
- Showing talent or returning production in the UI (M8.3).
- Changing Rung 1 (`power`): it keeps its last-season prior and linear decay.
- Tuning pick rules (M4.4) and any holdout run (M4.7).

## Files likely touched

- `python/engine/src/engine/models/priors.py` (new, or in `efficiency.py`): the fitted prior and the fitted decay.
- `python/engine/src/engine/models/efficiency.py`: blend the fitted prior; accept `decay: fitted` and `weights: fit`.
- `python/engine/src/engine/backtest/harness.py`: the preseason tables as a fit input, with the publication check.
- `python/engine/src/engine/sports/cfb/preseason.py` (new): each source's assumed publication time.
- `python/engine/specs/efficiency-v1.json`: the prior's components, weights and decay.
- `python/engine/src/engine/publish/reference.py`, `publish/staging.py`: write `talent` and `returning_ppa_pct`.
- `python/engine/tests/test_preseason_priors.py` (new): AC-1, AC-3, AC-4.
- `python/engine/tests/test_backtest_leakage.py`: AC-2.
- `python/engine/tests/test_publish_staging.py`: AC-6.
- `python/engine/tests/lake_fixture.py`: preseason rows for each backtest fixture season.
- `python/engine/tests/fixtures/backtest_efficiency_golden.csv`: regenerated if the fixture spec's prior changes.
- `docs/04-model.md` § 2 Preseason priors: how the prior is built and the AC-5 result.
- `docs/03-data-model.md` › team_seasons: which step writes `talent` and `returning_ppa_pct`.
- `docs/decisions.md`: the prior's design, the publication assumptions and the result as a D-### row.

## Verification

- Automated: `test_preseason_priors.py`, the leakage test, `test_publish_staging.py`; `pnpm test`.
- Manual: the AC-5 runs on the local lake → read the comparison with the owner, including weeks 1–3; look at the fitted weights and decay curve for 2023 and say whether they're plausible; publish the local lake to the dev database and spot-check three teams' talent and returning production against CFBD's site; confirm `data/cfbd_calls.json` is unchanged.

## Follow-ups

_Work noticed during this task and deliberately left out. Each bullet ends `→ <path> § <section>` (where it was placed) or `→ not tracked: <reason>`. See `.claude/skills/track-follow-ups/classify.md`; the PR's Follow-ups section is copied from here._

- Returning production could change how far last season's rating regresses (an interaction term) instead of only adding to it; test it as an M19.1 input (approved at plan; the plan named docs/06-roadmap.md, but the M19.1 item lives in the task list) → docs/08-tasklist.md § M19.1
- CFBD's returning production is offense-only, so defensive ratings get no roster-turnover signal (approved at plan) → not tracked: noted in docs/04-model.md § 2 Preseason priors
- Check the assumed publication dates against real pre-season pulls from 2027 on (approved at plan) → docs/owner-checklist.md § Actions
- Every 2016–2023 season picked `ridge_alpha` 2, the top of v1's grid, and the four components don't yet beat last season alone with the fitted decay; widen the grid and recheck before promotion → docs/08-tasklist.md § M4.7
- Under fitted decay the margin model is fit jointly with `k`, so TASK-038's empirical distribution should use the residuals at the chosen `k` → docs/tasks/TASK-038-points-drivers-empirical-margin.md § Context
- Candidate decision: the fitted prior, fitted decay, the publication assumptions and the AC-5 result → docs/decisions.md § D-138
- `efficiency-v1.json`'s spec hash changed, so an `efficiency` version already rated in a database with the old spec is refused by `engine rate` (D-136) → not tracked: recorded in D-138; no such version is in production

## Plan

_Written by /plan-batch or /implement-task Phase 1. Approved by the user (plan_status: approved) before any code is written._

Approved 2026-10-28.

**Decisions**
1. **Publication assumptions** (`engine/sports/cfb/preseason.py`): a recruiting class for season Y is known Feb 15 of Y; returning production for Y Jul 1 of Y; talent of season S Feb 1 of S+1, so season Y reads Y−1's talent (owner default). The backtest asserts every preseason value handed to season Y was known before Y's first `as_of`. The same-season-talent leak check is a one-off scratch run with that assumption loosened; its result goes in the decision row.
2. **Components:** returning production is `percent_ppa` clipped to [0, 1] (32 of 1,691 staged rows fall outside it, where last season's total PPA is near zero or negative); recruiting is the mean `points` of the classes Y−3..Y the team has.
3. **Prior:** per stat and side (12 regressions), `prior − anchor = a·(last season's final − anchor) + b·RP + c·talent + d·recruiting`, no intercept. The anchor is the team's tier level last season (D-137), so the tier term enters only through the anchor. Each component is centred on the mean of the team's anchor group that season (its tier under `tier`, all FBS under `zero`), so a team missing one counts as that group's average (AC-4).
4. **Target:** each team's pure in-season rating after its season's last game (the ridge solve with no prior blended in), fit on every target season before Y (04 § 9.2). A multi-component prior with `weights: fit` learns `a`, replacing `prior.regression`, which is then only the fallback for a season with no earlier season to fit on (2015). `components: [last_season]` keeps D-134/D-137's regression and linear decay unchanged, so v1 and its golden file don't move.
5. **Decay:** `w(N) = k/(k + N − 1)` (the prior is worth k weeks of games), so it lies in [0, 1] and never rises. `k` is fit jointly with the margin model on earlier seasons' games: each candidate on a log grid 0.1–10 gets its own OLS margin fit and the lowest squared error wins. Matchup rows store each game's prior and in-season gaps separately. With no earlier row that had a prior, `k` is `DEFAULT_PRIOR_WEEKS = 1.0` (the `DEFAULT_SD` precedent).
6. **Gaps:** newcomers and the FCS pool keep D-134's newcomer and pool priors (the pool gets `a`, no components). `fitted_params` adds `prior_missing_<component>` (rated teams lacking it that season), `decay_k`, the 12 last-season weights `prior_keep_<side>_<stat>`, and each other component's effect in points per unit `prior_points_<component>`.
7. **Postgres:** `publish_lake` writes `team_seasons.talent` (rounded to 2 dp) and `returning_ppa_pct` (raw `percent_ppa` fraction, rounded to 4 dp) from staging by (team, season). `upsert_team_seasons` sets only the columns a row carries, so the results job's `/games` publish never blanks them.

**Steps**
1. Tests first, failing: AC-1 and AC-3 on synthetic leagues, AC-4, the AC-2 leakage test parametrized by source, AC-6.
2. `sports/cfb/preseason.py` → the harness `preseason` fit input with the publication check → `models/priors.py` → `efficiency.py` blend and joint `k` fit → publish.
3. `engine compare A B --weeks 1-3` (`cli.py`, `compare.py`) for AC-5's weeks 1–3.
4. AC-5 on the local lake, 2016–2023: four components with fitted `k` against v1, pooled and weeks 1–3; also last season alone with fitted `k` (to separate the curve from the components) and the talent leak check. `efficiency-v1.json` changes only if the four components win.
5. Docs: 04 § 2 Preseason priors, 03 › team_seasons, a D-### row.

**Files:** `models/priors.py` (new), `models/efficiency.py`, `backtest/harness.py`, `sports/cfb/preseason.py` (new), `backtest/compare.py` and `cli.py` (not in Files likely touched: `--weeks`), `publish/reference.py`, `publish/staging.py`, `specs/efficiency-v1.json`, `tests/test_preseason_priors.py` (new), `tests/test_backtest_leakage.py`, `tests/test_publish_staging.py`, `tests/lake_fixture.py`, the efficiency golden CSV if the spec changes, `docs/04-model.md`, `docs/03-data-model.md`, `docs/decisions.md`.

**Test strategy:** AC-1 `test_preseason_priors.py` (weights recovered within 0.01; a row from Y or later raises); AC-2 `test_backtest_leakage.py` (each source's assumption loosened in turn raises `PointInTimeError`); AC-3 and AC-4 `test_preseason_priors.py`; AC-5 manual (the runs, recorded in the decision row and 04 § 2), `--weeks` in `test_backtest_compare.py`; AC-6 `test_publish_staging.py`.

**Risks:** 48 weights fit on one early season are noisy (2016's prior is fit on 2015 alone); joint `k` fitting adds runtime, offset by dropping the Z grid.

## Review log

_Filled by /implement-task. One line per round._

- Verify R1 PASS → R2 PASS (after the review fixes) | Audit R1 PASS → R2 PASS (the fix tests, against 2b53dc4) | Spec R1 CHANGES (talent 0 in the model; AC-1's test tolerance; follow-up paths) → R2 APPROVE | Schema R1 CHANGES (talent 0 publishes 0; percent_ppa overflow; `>` vs `>=`; rounding) → R2 APPROVE (two minors, done)
- Manual: AC-5 runs on the local lake (`backtests/20261028T053912664046Z-d21f7e229ea7`, v1 `…051600247091Z-d3f68cadbeae`, last season with fitted decay `…051600258121Z-f778b86ac22e`, same-season talent `…053912641371Z-d21f7e229ea7`), results in D-138; the 2023 fitted weights and curve read as plausible (D-138); the local lake published to the dev DB, and 2023's Ohio State 974.79 / 0.6440, Boise State 579.88 / 0.9210 and Navy NULL (CFBD sent 0) / 0.6110 match staging; `data/cfbd_calls.json` unchanged since 2026-10-20. Checking those values against CFBD's website is left to the owner.

## Blocked

_Only if status is Blocked: what failed, what was tried, best hypothesis, decision needed._

## Metrics

- Verify rounds: 2 (both PASS; the second after the review fixes)
- Review rounds: 2 (spec), 2 (schema); audit 2
- First-pass AC FAILs: 0 (spec R1's CHANGES were the talent-0 defect, a test's tolerance and follow-up paths, not an AC failure)
- Plan revisions after approval: 0
