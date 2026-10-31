---
id: TASK-043
title: Run the holdout evaluation and the go/no-go for v1
status: Done
depends_on: [TASK-042]
size: M
model: opus
autonomy: attended
ui: false
plan_status: approved
planned_at_commit: 9cdf7be
---

# TASK-043 — Run the holdout evaluation and the go/no-go for v1

## Goal

The owner gets a written go/no-go for model v1: every gate on the validation seasons and the one-time holdout exam on 2024–2025, each pass or fail with its number, and a recorded call on whether v1 is promoted for 2026 paper trading and whether the app labels its cover probabilities "uncalibrated".

## Context

- Task list: `docs/08-tasklist.md` › M4 › M4.7 (split: TASK-042 fixes the displayed probability's calibration first; this task is the final validation run, the holdout and the go/no-go).
- Roadmap: `docs/06-roadmap.md` › Phase 3 — "Holdout evaluation on 2024–2025, then go/no-go"; acceptance "model v1 passes the go/no-go gates on validation seasons (or we understand why not and adjust)".
- Model: `docs/04-model.md` § 5 › Go / no-go to "production"; § 9.1 (› Holdout: at promotion, settings tuned on 2015–2023, the candidate runs **once** on 2024–2025; a failed holdout sends the candidate back and the next variant may not be tuned to fix it); § 9.4 (the gate table: MAE gap ≤ +0.5, ATS > 52.4% at the close, edge-trend slope's interval above zero, consistency, calibration; the holdout check ATS > 50% and MAE gap ≤ +0.5); § 9.5 (paired week bootstrap); § 9.6 › Phase 3 (beat Rung 1 on MAE **and** every § 9.4 gate); § 4 (the early-season skip "is read before the go/no-go (M4.7)").
- Decisions: D-076 (seasons), D-077 (gate definitions), D-132 (how gates read pass, fail or n/a), D-133 (`--compare baselines` refuses an efficiency spec), D-137 (Rung 2 against Rung 1 was −0.14, −0.30 to +0.01, "judged on all of v1 at M4.7"), D-138 (prior components), D-141 (v1's pick rules, k = 1).
- Code today: `engine backtest --spec … --seasons 2024-2025 --holdout --reason "…"` already tunes each holdout season on 2015–2023 only (`harness.tuning_seasons` skips holdout seasons) and adds one record under `backtests/holdout/` (`engine/backtest/holdout.py`); `engine compare RUN_A RUN_B [--weeks]` is the § 9.5 bootstrap.
- *From TASK-036 (PR #101):* `engine backtest --compare baselines` refuses an efficiency spec, since `home_field` and `last_season` wrap only a model that fits on games alone (D-133) and Rung 2 also reads `team_game_stats`; Rung 2 against Rung 1 is `engine compare RUN_A RUN_B` (D-137). If v1's go/no-go wants the Rung 0 rows too, the wrappers must hand the inner model its inputs.
- *From TASK-037 (PR #102):* under the fitted prior every 2016–2023 season picked `ridge_alpha` 2, the top of `efficiency-v1.json`'s grid {0.5, 1, 2}: widen it before the holdout run. The four preseason components beat the old last-season prior with linear decay (−0.13) but not yet last season alone with the fitted decay (−0.05, −0.12 to +0.01; D-138): recheck that on the final v1 before promotion.
- *From TASK-039 (PR #106):* at k = 1 the calibration gate fails, so the go/no-go needs a way to calibrate the displayed probability without moving the pick threshold (TASK-042). Also read the final v1 run's week-of-season breakdown before deciding: 04 § 4's "skip early-season games where the prior still dominates" isn't a rule yet.
- *From TASK-042 (PR #109), open question for the plan:* with the display shrinkage (`picks.display_shrinkage_k`, D-143) the picks are unchanged (499-407-9) and the cover Brier falls from 0.2611 to 0.2500, but the calibration gate still fails in one bin: 55–57.5% shown, 46.6% covered on 131 games (+9.1 points), 59 of them 2017's, the season that chose 0.25. A bin near 100–130 games has a standard error of about 4.4 points, so § 9.4's ±3 tolerance can fail on noise alone. Does the go/no-go read this as a fail, or does the owner revisit the gate's tolerance or minimum bin size (a § 9.4 change)? `efficiency-v1.json`'s hash changed, so the final run is a new one (the local lake's is `backtests/20261030T183302517984Z-cb1a4894a79d`).
- **Concept:** the holdout is the final exam: two seasons nothing was tuned on. With about 260 picks its ATS has a standard error near ±3 points, so it can catch a broken model but can't prove a good one; that's why its bar (> 50%) is looser than validation's (> 52.4%), and why it's opened once: every look turns it into another validation set.
- **Decide at the plan gate:** the widened α grid; how the prior recheck runs (a sibling spec with `components: [last_season]`, kept or deleted after); what the owner's call is when a validation gate fails (v1 is already known to miss the MAE gate: 13.15 against the close's 12.43 on TASK-036's run): promote anyway for paper trading with the failure recorded, keep v1 as `candidate` and paper-trade it, or send it back; this decides which version TASK-046's weekly job runs.

## Acceptance criteria

- [x] AC-1: `efficiency-v1.json`'s `ridge_alpha` grid reaches above 2, and the final validation run (`engine backtest --spec efficiency-v1.json --seasons 2016-2023 --report DIR`, with TASK-042's calibration) chooses an α below the grid's top in every season, or the decision row says why the edge stands; the run's five § 9.4 gates (pass/fail with the number), its week-of-season and conference-tier breakdowns and its run directory are recorded in 04 § 9.6 › Phase 3.
- [x] AC-2: On the final v1's games, `engine compare` gives Rung 2 against Rung 1 and the four-component prior against last season alone with the fitted decay, each as an MAE difference with its 95% week-bootstrap interval, recorded in 04 § 9.6 › Phase 3 (and 04 § 2 › Preseason priors if the components lose); 04 § 4's early-season line says whether a skip rule is wanted, citing the weeks 1–3 ATS and pick count it rests on.
- [x] AC-3: The holdout is opened exactly once in this task: one `engine backtest --seasons 2024-2025 --holdout --reason "<why>"` run of the final spec, so `backtests/holdout/` holds exactly one more record than before (count shown before and after), and its ATS against > 50% and MAE gap against ≤ +0.5 are recorded as pass or fail with the numbers.
- [x] AC-4: A go/no-go decision row (D-###) lists every § 9.4 gate and the holdout check as pass or fail with its number, records the owner's call (promote v1.0, paper-trade it as `candidate`, or send it back) with the date, and says whether the "uncalibrated" label shows (it shows while the calibration gate fails); 04 § 9.6 › Phase 3 says "Met" or "Not met" with the date and that decision's ID.
- [x] AC-5: If the holdout fails, no setting changes after it and no second holdout run happens in this task (§ 9.1); the decision row names what goes back for the next variant. `data/cfbd_calls.json` is unchanged by every run.

## Out of scope

- The calibration method itself (TASK-042).
- Setting `model_versions.status` in any database, and the weekly job that runs the promoted version (TASK-046).
- Writing backtest metrics or holdout records to `model_runs` (M14.1, M14.4); the Performance screen reads them (M7.4).
- Building an early-season skip rule, or making `--compare baselines` wrap Rung 2 (D-133): if the go/no-go wants either, it's a follow-up.
- Tuning anything to fix a failed holdout.

## Files likely touched

- `python/engine/specs/efficiency-v1.json`: the widened α grid.
- `python/engine/specs/efficiency-v1-last-season-prior.json`: the prior recheck's sibling spec, if the plan keeps one.
- `docs/04-model.md` § 2, § 4, § 9.6: the results and the verdict.
- `docs/decisions.md`: the go/no-go row.
- `docs/06-roadmap.md` › Phase 3: tick the holdout item when accepted.

## Verification

- Automated: `pnpm test` (the spec still validates; `test_efficiency_ratings.py`'s golden backtest reads `efficiency-v1.json`, so the widened grid regenerates `backtest_efficiency_golden.csv`: the fixture now picks α 8).
- Manual: the AC-1 and AC-2 runs on the local lake, then the single AC-3 holdout run → read every gate, comparison and the holdout result with the owner before the call in AC-4 is recorded; `engine backtest` refuses `--seasons 2024-2025` without `--holdout --reason`.

## Follow-ups

_Work noticed during this task and deliberately left out. Each bullet ends `→ <path> § <section>` (where it was placed) or `→ not tracked: <reason>`. See `.claude/skills/track-follow-ups/classify.md`; the PR's Follow-ups section is copied from here._

- TASK-046's weekly job needs the version and status the go/no-go settled: v1 stays `candidate` and is paper-traded through 2026, while its Goal and AC-1 assume a `production` version, an open question for its plan; and the spec's new hash and newest run (approved at plan) → docs/tasks/TASK-046-weekly-rate-predict-pick-job.md § Context
- TASK-045 writes `picks.model_prob`: the "uncalibrated" label shows while the calibration gate fails, and TASK-042's run no longer matches the spec's hash, so it rates from this task's run (approved at plan) → docs/tasks/TASK-045-write-picks-from-a-model-run.md § Context
- The calibration gate's ±3 points is tighter than a ~130-game bin's standard error (4.4 points): a noise-aware tolerance for later versions, not applied to v1 (owner, plan gate 2026-10-31) (approved at plan) → docs/decisions.md § D-144
- The widened α grid is +0.026 MAE (+0.010 to +0.044) against TASK-042's narrow-grid run; kept, since choosing the grid by validation MAE would tune on validation → not tracked: accepted as is by the owner (spec frozen with it, 2026-10-31; recorded in D-144)
- A tuned early-season skip setting, for a later variant to test → not tracked: owner said no rule for v1 (2026-10-31); recorded in 04 § 4 and D-144

## Plan

Approved 2026-10-31. Owner's plan-gate choices: α grid {1, 2, 3, 5, 8}; the sibling spec stays committed; the calibration gate is read as written (± 3 points, bins of ≥ 100); if gates fail, the intended call is to paper-trade v1 as `candidate` (recorded only after the results are read together).

**Steps:**

1. Test first: `test_model_spec.py` asserts the shipped `efficiency-v1.json` validates and its `ridge_alpha` grid reaches above 2 (fails on {0.5, 1, 2}). Widen it to {1, 2, 3, 5, 8}. `test_efficiency_ratings.py`'s golden backtest reads `efficiency-v1.json`: if the fixture now picks another α, regenerate the golden file in a commit that says why (D-132) and correct this file's Verification line.
2. Record the before state: `backtests/holdout/` record count (0) and the `data/cfbd_calls.json` SHA-256 (`2B2539…16993DB3B6`).
3. Final validation run: `engine backtest --spec efficiency-v1.json --seasons 2016-2023 --report DIR`. If a season still picks the grid's top (8), widen once more; if one is still at the top after that, the decision row says why the edge stands.
4. Comparisons on the same games: fresh `power-v1.json` 2016–2023 run (Rung 1), and `efficiency-v1-last-season-prior.json` (`components: [last_season]`, otherwise identical); `engine compare` each against the final run, pooled and `--weeks 1-3`. Fixed before the run: v1 switches to last season alone only if it is clearly better (its interval against the four components entirely below zero); otherwise the four stay.
5. Record in 04 § 9.6 › Phase 3: the five § 9.4 gates with their numbers, week-of-season and conference-tier breakdowns, the run directories, both comparisons; § 2 › Preseason priors if the components lose; § 4's early-season line with weeks 1–3 ATS and pick count. Read the results with the owner; the spec is frozen.
6. Holdout, once: `engine backtest --spec <final> --seasons 2024-2025 --holdout --reason "v1 promotion exam (TASK-043)" --report DIR`; show the record count (0 → 1) and the unchanged call-log hash. On a fail nothing changes after it (§ 9.1).
7. Read the holdout with the owner, then the go/no-go row (ID from `next-id.ps1`): every gate and the holdout check with its number, the owner's call and date, the "uncalibrated" label; 04 § 9.6 › Phase 3 "Met" / "Not met" with the date and the ID.

**Files:** `python/engine/specs/efficiency-v1.json` (α grid), `python/engine/specs/efficiency-v1-last-season-prior.json` (new, the recheck), `python/engine/tests/test_model_spec.py` (the grid test; not in Files likely touched), the efficiency golden file if it moves (not in Files likely touched), `docs/04-model.md`, `docs/decisions.md`, this task file; `docs/06-roadmap.md`'s holdout tick at close-out.

**Test strategy:** AC-1's grid: `test_model_spec.py::test_the_v1_spec_tunes_ridge_alpha_above_2`; the rest of AC-1 and AC-2–AC-5 are the manual runs, their numbers recorded in 04 and the decision row, with the holdout count and call-log hash shown before and after. `pnpm test` covers the specs still validating.

**Risks:** the golden backtest may move with the grid (step 1); the holdout's MAE check likely fails (2024–2025 closing-line MAE is lower on median lines), which § 9.1 reads as sending the candidate back for production, so the owner's call is recorded against it.

## Review log

Verify R1 PASS → R2 PASS (after the audit's test) | Audit R1 CHANGES (the sibling spec untested) → R2 PASS | Spec R1 CHANGES (AC-2: the prior recheck missing from 04 § 9.6 › Phase 3) → R2 APPROVE | Schema and UI reviewers not run (no schema, query or UI change)

## Blocked

_Only if status is Blocked: what failed, what was tried, best hypothesis, decision needed._

## Metrics

- Verify rounds: 2 (both PASS; the second after the audit's test)
- Review rounds: 2 (spec); audit 2
- First-pass AC FAILs: 1 (AC-2: spec R1 found the prior recheck recorded in § 2 and D-144 but not § 9.6 › Phase 3)
- Plan revisions after approval: 0
