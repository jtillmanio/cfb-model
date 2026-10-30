---
id: TASK-042
title: Calibrate the displayed cover probability without moving the pick threshold
status: In progress
depends_on: [TASK-039]
size: M
model: opus
autonomy: attended
ui: false
plan_status: approved
planned_at_commit: 967324f
---

# TASK-042 — Calibrate the displayed cover probability without moving the pick threshold

## Goal

The cover probability the app shows for a game matches how often such games actually cover, while the games v1 picks stay exactly the ones it picks today. The go/no-go (TASK-043) then judges a calibration gate that can pass at k = 1.

## Context

- Task list: `docs/08-tasklist.md` › M4 › M4.7 (split: this task is the calibration fix the go/no-go needs; TASK-043 runs the holdout and the go/no-go).
- Model: `docs/04-model.md` § 4 From predictions to picks (the edge, `model_prob = Φ(|edge|/σ)`; › Concept: why shrinkage is one dial with the threshold: k changes only the displayed probability on ATS; › Result (TASK-039): k tuned 0.1–0.3 gave cover Brier 0.2500 and one calibration bin off, k = 1 gave 0.2611 and six bins off, and v1 fixes k at 1); § 9.1 (season Y's settings are chosen on 2015 to Y−1 only); § 9.2 › Tuning targets (k on the cover Brier score of every eligible tuning-season game); § 9.4 › Calibration (the gate bins the **displayed** probability, after shrinkage: every bin with ≥ 100 picks within ±3 points; it also turns off the "uncalibrated" label).
- Decisions: D-141 (two-stage tuning; k on Brier, thresholds on ATS; v1 fixes k = 1; its Revisit if names "a display-only calibration (k for the probability, not the threshold)"), D-132 (each row graded once with its season's resolved pick rules; calibration on the side the model likes), D-139 (empirical vs normal margin; v1 keeps `normal`), D-137 (`spec.ADDED_DEFAULTS` keeps an older spec's hash while a new field holds its old-behaviour default).
- *From TASK-039 (PR #106):* market shrinkage was dropped on § 9.6's ATS bar, yet it was what made the displayed cover probability honest, so at k = 1 the calibration gate fails: the go/no-go needs a way to calibrate the displayed probability without moving the pick threshold (a display-only shrinkage, or M19.2's per-game σ).
- Code today: `core.picks.pick()` / `pick_game()` (`python/engine/src/engine/core/picks.py`) shrink the margin by `market_shrinkage_k` and qualify and tier on the result; `PickRules` (`core/spec.py`); `backtest/pick_rules.py` tunes k on `metrics.cover_brier` over `grade_rows`; `metrics.calibration` bins the displayed probability; `engine rate --choices` resolves tuned pick fields (`publish/models.py` `settings`).
- **Concept:** a probability is *calibrated* when the games it calls 60% cover about 60% of the time. Which games are picked depends only on the edge clearing the threshold, so the number shown next to a pick can be corrected on its own: v1's raw Φ(edge/σ) is overconfident at large edges, and shrinking it toward 50% (or fitting a map from edge to observed cover rate) fixes the display without touching ATS.
- **Decide at the plan gate:** the method: a display-only k (a second pick-rule field, tuned on cover Brier, applied to the probability but not to the threshold or tier), or a fitted recalibration from edge to cover rate (e.g. one logistic slope), each fit on tuning seasons only; its field name and grid; whether `min_prob` reads the raw or the displayed probability (v1 leaves it at 0.5, inactive); what `predictions` and `picks` store as `model_prob` (the displayed one, so the UI shows what the gate judged).

## Acceptance criteria

- [ ] AC-1: Given `efficiency-v1.json` with the display calibration on and the same spec with it off (k = 1 as today), every eligible 2016–2023 validation game gets the same pick (side and tier, or none) under both, so pooled W-L-P, ATS and ROI are equal; a test on the fixture lake compares the two runs' pick columns row by row and finds no difference.
- [ ] AC-2: The probability the calibration gate bins, the cover Brier score reads and `core.picks` returns as `model_prob` is the calibrated one; season Y's calibration is fit only on its tuning seasons (2015 to Y−1, never a holdout season), and a test that changes a season-Y row's result leaves season Y's fitted calibration unchanged.
- [ ] AC-3: Each season's fitted calibration is written to `run.json` `choices[Y]`, `engine rate --choices <that run.json>` resolves the same value for that season (round-trip test), and the report's "Pick rules by season" section lists it per season.
- [ ] AC-4: A spec without the new setting keeps its `spec_hash` and its results: `power-v1.json` and the backtest golden files are unchanged (`test_backtest_golden.py` passes with no golden edited).
- [ ] AC-5: On the local lake, pooled 2016–2023, the report gives cover Brier and the calibration gate (pass/fail, and each bin's predicted and actual rate with its count) for `efficiency-v1.json` with and without the display calibration on the same games; the result is recorded in 04 § 4 and in a decision row, whether or not the gate now passes.

## Out of scope

- The holdout run, the go/no-go and the promotion call (TASK-043); the ridge-α grid TASK-037 asked to widen is TASK-043's.
- A per-game σ (M19.2) and confidence levels from the calibrated probability (04 § 10.7, M19).
- Changing which games are picked: the thresholds, tiers, `market_shrinkage_k` on the edge, or the margin distribution.
- Writing picks to Postgres (TASK-045) and the "uncalibrated" label in the UI (M7).

## Files likely touched

- `python/engine/src/engine/core/picks.py`: apply the calibration to the returned probability only.
- `python/engine/src/engine/core/spec.py`: the new pick-rule field and its `ADDED_DEFAULTS` entry.
- `python/engine/src/engine/backtest/pick_rules.py`: fit it on tuning seasons (cover Brier).
- `python/engine/src/engine/backtest/metrics.py`: calibration and Brier read the displayed probability.
- `python/engine/src/engine/backtest/report.py`: the per-season value; the with/without comparison.
- `python/engine/src/engine/publish/models.py`: resolve it from `--choices`.
- `python/engine/specs/efficiency-v1.json`: turn it on.
- `python/engine/tests/test_core_picks.py`, `test_pick_tuning.py`, `test_publish_models.py`, `test_backtest_report.py`: AC-1 to AC-4.
- `docs/04-model.md` § 4, § 9.4: the method and the AC-5 result.
- `docs/decisions.md`: the method and result as a D-### row.

## Verification

- Automated: the tests above; `test_backtest_golden.py`; `test_core_imports.py` (the light core stays light); `pnpm test`.
- Manual: `engine backtest --spec python/engine/specs/efficiency-v1.json --seasons 2016-2023 --report DIR` with and without the calibration → the pick records match exactly and the calibration tables differ; read both with the owner. `data/cfbd_calls.json` is unchanged.

## Follow-ups

_Work noticed during this task and deliberately left out. Each bullet ends `→ <path> § <section>` (where it was placed) or `→ not tracked: <reason>`. See `.claude/skills/track-follow-ups/classify.md`; the PR's Follow-ups section is copied from here._

## Plan

_Written by /plan-batch or /implement-task Phase 1. Approved by the user (plan_status: approved) before any code is written._

Approved by the owner 2026-10-30.

**Decisions (plan gate):**
- Method: a display-only shrinkage `picks.display_shrinkage_k`, tuned per season on cover Brier over a grid (ties to the larger k, as D-141). Not a fitted logistic map: `choices[Y]` holds grid candidates only (`spec.resolve`), and a one-slope map through 50% is the same curve.
- Grid in `efficiency-v1.json`: {0.05, 0.1, 0.15, 0.2, 0.25, 0.3, 0.4, 0.5, 0.75, 1}.
- Displayed probability = Φ(k_d · k · edge / σ) for the pick's own side (k = market shrinkage; v1 k = 1). Default 1.0, with an `ADDED_DEFAULTS` entry so older specs keep their hash.
- `min_prob` reads the raw (blended-margin) probability, so the calibration never changes a pick.
- `Pick.prob` (so `picks.model_prob`, TASK-045) and `Graded.prob` (calibration, cover Brier, contest top-N) are the displayed probability. `predictions` stores no probability.

**Steps:**
1. `core/spec.py`: the field, bounded (0, 1]; `canonical()` drops a nested added default (`picks.display_shrinkage_k: 1.0`).
2. `core/picks.py`: pick, side, edge, tier and the `min_prob` cut stay on the blended margin; one helper gives the displayed probability for a side, used by `pick()` and `grade_rows`.
3. `backtest/pick_rules.py`: market k on Brier with the display shrink at 1 (D-141's choices unchanged), thresholds on ATS as today, then `display_shrinkage_k` on Brier, tuning seasons only, through the same guarded `evaluate`.
4. `backtest/metrics.py`: `grade_rows` sets `prob` to the displayed probability.
5. `backtest/report.py`: a "Display k" column in "Pick rules by season"; the section's note.
6. `specs/efficiency-v1.json`: turn it on.
7. AC-5: `engine backtest` 2016–2023 with and without, then `engine compare` (cover Brier, calibration gate and bins per run on the same games); record in 04 § 4 and § 9.4 and a D-### row amending D-141.

**Tests (written first):**
- AC-1 (`test_pick_tuning.py`): `efficiency-v1.json` on the fixture lake (2023, tuned on 2022), on vs off: identical rows, picks (side, tier) row by row, pooled W-L-P, units, ROI.
- AC-2: `test_core_picks.py` (`Pick.prob` = Φ(k_d·edge/σ); side, tier and the `min_prob` cut read the raw probability); `test_pick_tuning.py` (k_d is the lowest-Brier candidate; flipping 2023's results leaves 2023's k_d unchanged); `test_backtest_metrics.py` (`Graded.prob`, `cover_brier`, `calibration` read the displayed probability).
- AC-3: `test_pick_tuning.py` (`run.json` `choices` → `models.settings` resolves the same k_d) and `test_backtest_report.py` (the row shows it).
- AC-4: `test_model_spec.py` (`power-v1.json`'s hash unchanged with the field absent or 1.0); the golden tests pass with no golden edited.

**Files:** `core/spec.py`, `core/picks.py`, `backtest/pick_rules.py`, `backtest/metrics.py`, `backtest/report.py`, `specs/efficiency-v1.json`; tests `test_core_picks.py`, `test_pick_tuning.py`, `test_backtest_metrics.py` (not in Files likely touched), `test_backtest_report.py`, `test_model_spec.py` (not in Files likely touched); `docs/04-model.md`, `docs/decisions.md`. `publish/models.py` likely unchanged (`settings()` is generic).

**Risks:** per-season k_d may land at 0.25–0.3 and fail one bin, as TASK-039's did; AC-5 records the result either way. Calibrated probabilities sit near 50–55% for nearly every game, so a pick at edge 8+ shows about 53% against its ~55% hit rate; TASK-043 should know.

## Review log

_Filled by /implement-task. One line per round._

## Blocked

_Only if status is Blocked: what failed, what was tried, best hypothesis, decision needed._

## Metrics

- Verify rounds:
- Review rounds:
- First-pass AC FAILs:
- Plan revisions after approval:
