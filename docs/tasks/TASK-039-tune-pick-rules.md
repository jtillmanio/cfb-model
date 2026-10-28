---
id: TASK-039
title: Tune pick rules: thresholds, tiers and market shrinkage
status: Ready
depends_on: [TASK-038]
size: M
model: opus
autonomy: attended
ui: false
plan_status: none
planned_at_commit:
---

# TASK-039 — Tune pick rules: thresholds, tiers and market shrinkage

## Goal

The model's pick rules (minimum edge, minimum cover probability, tier cutoffs and how far to shrink toward the market) are chosen by the backtest on how picks did against closing lines, season by season with no peeking, instead of the guessed values in the spec. The report shows what each season chose and whether shrinking toward the market earned its place.

## Context

- Task list: `docs/08-tasklist.md` › M4 › M4.4.
- Model: `docs/04-model.md` § 4 From predictions to picks (edge, cover probability, tiers, re-evaluation; § 4 › When you pick: shrinking toward the market, `final = k·model + (1−k)·market`; the winner's curse in top-N picks); § 9.1 (rolling origin: season Y's settings, pick rules included, are chosen on 2015 to Y−1 only); § 9.2 › Tuning targets (model settings on margin MAE; **pick rules on ATS against closing lines over the tuning seasons, and only on choices backed by at least 200 picks**); § 9.3 (eligible games are FBS vs FBS; pushes out of win %); § 9.4 (calibration is on the displayed cover probability, after shrinkage; contest top 4); § 9.6 › Phase 3 (**market shrinkage stays only if validation ATS with it is at least as good as without it, k = 1**).
- Decisions: D-055 (pick thresholds, tiers, min probability and shrinkage are tuned, not guessed), D-047 (no picks on FBS-vs-FCS games), D-076 (rolling-origin seasons), D-132 (each row graded once with its season's resolved pick rules, the margin shrunk by `market_shrinkage_k` first), D-134 (a backtest's `run.json` `choices` carry each season's tuned settings, and `engine rate --choices` reads them), D-139 (the liked side; its Revisit if names this task).
- Code today: `core.picks.pick()` (`python/engine/src/engine/core/picks.py`) applies a spec's `picks` exactly; `PickRules` (`core/spec.py`) already accepts `{"tune": [...]}` for every field. The harness's `grid_tuner` (`backtest/harness.py`) chooses every tunable on pooled margin MAE, which pick rules don't move, so a tuned pick field today silently takes its first candidate. `efficiency-v1.json` and `power-v1.json` fix `min_edge_pts` 3.0, `min_prob` 0.55, `market_shrinkage_k` 1.0 and tiers A 5.0 · B 3.5 · C 2.5.
- **Concept:** pick rules don't change a prediction, only which games become picks, so they're tuned on a different target from the model's settings. Margin MAE is the steady measure for the model; ATS is noisy, so it's used only for the few pick knobs, and only where a choice rests on 200+ picks (about ±3.5 points of win % at that size). Shrinking toward the market (k < 1) trims the model's wildest disagreements, which are disproportionately its mistakes; the bar keeps it only if it doesn't cost ATS.
- **Decide at the plan gate:** the grids for each field; how tier cutoffs are tuned on ATS (tiers don't change which games are picked unless C rises above `min_edge_pts`; for example, chosen so each higher tier's tuning-season hit rate is at least the one below's) and whether a pick below tier C is allowed; the tie-break among choices with equal ATS; what a season gets when no candidate reaches 200 picks on its tuning seasons (2016 tunes on 2015 alone); whether the pick tuner is a second stage after `grid_tuner` (the model's settings first, then the pick rules on the rows they produce) and how both land in `run.json` `choices`; how D-047 reaches the live pick path, since `pick()` takes only a margin and a line today; whether 04 § 4's "skip early-season games where the prior still dominates" becomes a rule here (a tuned `max_prior_weight`, say) or waits for the week-of-season breakdown to show those picks underperform.
- *From TASK-038 (PR #103):* under `distribution: empirical`, when a key number makes the liked side the one the edge leans against (D-139), `core.picks.pick` still qualifies and tiers the pick on `abs(edge)`, so it can pick a side the model's own margin disagrees with: pass such a game or measure the edge for the liked side. Moot while v1 keeps `normal`.
- *From D-139 › Revisit if:* if market shrinkage is kept, it brings probabilities nearer the line, so TASK-038's AC-5 comparison (cover Brier and calibration, `empirical` against `normal`, pooled 2016–2023) is re-run with it (AC-5 below).
- M4.7 (holdout and go/no-go) runs on the rules this task settles; writing picks to Postgres is M4.5's table and M4.8's weekly job.

## Acceptance criteria

- [ ] AC-1: Given a spec whose `picks` fields are `{"tune": [...]}`, the backtest chooses validation season Y's pick rules from its tuning seasons only (2015 to Y−1, never a holdout season), by ATS win % against the closing line pooled over those seasons, among candidates with at least 200 picks there; a test on synthetic rows where the candidate with the best ATS has 199 picks shows the next-best candidate with ≥ 200 chosen instead, and a test that changes a season-Y row's result leaves season Y's choice unchanged.
- [ ] AC-2: The chosen pick rules for each scored season are written to `run.json` `choices` alongside the model's settings, grading uses them (D-132), and `engine rate --choices <that run.json>` resolves the same pick rules for that season; the model settings chosen on margin MAE are the same as a run with fixed pick rules (the pick tuner never changes them).
- [ ] AC-3: No pick is made on a game with an FCS team in the backtest or in the pick path `engine rate` and the weekly job will use (a test with an FBS-vs-FCS game and an edge above every threshold gets no pick), and under `distribution: empirical` a game whose liked side is the one the edge leans against gets no pick or a pick measured for the liked side, as the plan settles (a test builds that case; under `normal` every existing pick test and golden file is unchanged).
- [ ] AC-4: On the local lake, pooled 2016–2023, the report compares the tuned `market_shrinkage_k` against k = 1 (ATS win % with its 95% interval, picks, ROI, and the calibration gate) on the same games with the same model settings; `efficiency-v1.json` keeps a shrinkage grid only if validation ATS with it is at least k = 1's, otherwise k is fixed at 1, and the decision row says which and why. The result is recorded in 04 § 4.
- [ ] AC-5: If AC-4 keeps shrinkage, the empirical-against-normal comparison from TASK-038's AC-5 (cover Brier, calibration bins) is re-run with it on the same games and its result recorded in 04 § 3 (D-139 › Revisit if); `distribution` changes only if empirical's cover Brier is no worse. If AC-4 drops shrinkage, 04 § 3 says the comparison stands.
- [ ] AC-6: `efficiency-v1.json`'s `picks` holds the grids (or fixed values) AC-1 to AC-4 settled, the report lists each validation season's chosen pick rules and its tuning-season pick count, and the backtest golden files change only in a commit that says why.

## Out of scope

- The holdout run and the go/no-go for v1 (M4.7); the ridge grid TASK-037 asked to widen is M4.7's too.
- The `picks` table and the `current_picks`, `pick_outcomes` and `model_record` views (M4.5, M4.6), and writing picks from `engine rate` or the weekly job (M4.8).
- Contest top-N ranking against contest lines and the contest-vs-market gap (M6).
- Confidence levels from the calibrated cover probability (M19, 04 § 10.7) and Kelly staking (Later): stakes stay flat 1u.
- Changing the model's settings, inputs or margin distribution beyond AC-5's one comparison.

## Files likely touched

- `python/engine/src/engine/core/picks.py`: D-047 and the liked-side case in the pick path.
- `python/engine/src/engine/core/spec.py`: any new pick-rule field the plan adds.
- `python/engine/src/engine/backtest/harness.py`: the pick-rule tuner and its place after `grid_tuner`; `run.json` `choices`.
- `python/engine/src/engine/backtest/metrics.py`: candidate grading on tuning seasons, if it reuses `grade_rows`.
- `python/engine/src/engine/backtest/report.py`: chosen rules per season; the k against k = 1 comparison.
- `python/engine/src/engine/backtest/compare.py`: if AC-4 and AC-5 run through `engine compare`.
- `python/engine/src/engine/publish/models.py`: resolving tuned pick rules from `--choices`.
- `python/engine/specs/efficiency-v1.json`: the settled pick rules.
- `python/engine/tests/test_core_picks.py`: AC-3.
- `python/engine/tests/test_backtest_harness.py` (or a new `test_pick_tuning.py`): AC-1, AC-2.
- `python/engine/tests/test_backtest_report.py`, `fixtures/` goldens: AC-6.
- `python/engine/tests/test_publish_models.py`: AC-2's `--choices` round trip.
- `docs/04-model.md` § 3, § 4: the tuning rule and the AC-4 and AC-5 results.
- `docs/decisions.md`: the tuning method and the shrinkage verdict as a D-### row.

## Verification

- Automated: the tests above; `test_backtest_golden.py`; `test_core_imports.py`; `pnpm test`.
- Manual: the AC-4 runs on the local lake (`engine backtest --spec efficiency-v1.json --seasons 2016-2023 --report DIR`, once tuned and once with k = 1) → read the ATS, calibration and per-season chosen rules with the owner; confirm `data/cfbd_calls.json` is unchanged.

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
