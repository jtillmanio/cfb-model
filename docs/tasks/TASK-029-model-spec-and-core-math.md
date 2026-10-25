---
id: TASK-029
title: Define ModelSpec v1, the model interfaces and the probability math in engine.core
status: Ready
depends_on: []
size: M
model: opus
autonomy: attended
ui: false
plan_status: none
planned_at_commit:
---

# TASK-029 — Define ModelSpec v1, the model interfaces and the probability math in engine.core

## Goal

Every model, the backtest and later the API describe a model the same way: a validated `ModelSpec` whose inputs come from one registry, and one shared piece of math that turns a predicted margin and a line into an edge, a cover probability, an expected value and a pick.

## Context

- Task list: `docs/08-tasklist.md` › M3 › M3.1.
- Model: `docs/04-model.md` § 1 (edge, Φ(edge/σ), break-even and EV at −110); § 4 From predictions to picks (`edge_pts = pred_margin + spread_home`, `model_prob = Φ(|edge_pts| / σ)`, min edge and min probability, A/B/C tiers, market shrinkage `final = k·model + (1−k)·market`); § 6 Every model is a spec (the YAML sketch: `base`, `inputs`, `hyperparameters`, `home_field`, `prior`, `distribution`, `picks`; each weight `fit` or a fixed number; the JSON Schema drives the Lab form later); § 6 Two kinds of numbers (spec holds settings, `model_runs.fitted_params` holds learned weights); § 6 Engineering contract (`RatingModel.fit`, `GamePredictor.predict` returning `pred_margin`, `margin_sd`, `home_win_prob`, `drivers`; pure functions of inputs + spec); § 10.6 One input registry (id, label, plain-English definition, unit, better direction, source, garbage-time handling, first season, noisy flag); § 10.2 (the v1 inputs: EPA/play and success rate, overall and rush/pass, offense and defense).
- Architecture: `docs/02-architecture.md` › Components › 1 `python/engine` (the light core is numpy, scipy, pydantic; the heavy `engine[train]` extra holds the rest) and › Ratings depth (one input registry in `engine.core`, light-core code so the API can serve it); › Testing strategy › Levels › Unit: engine.
- Decisions: D-004 (light core vs `engine[train]`), D-022 (shared code never imports a sport), D-049 (model ladder), D-050 (`ModelSpec` in `model_versions.spec`), D-053 (empirical margin distribution in v1, built in M4.3), D-055 (pick rules come from the spec, tuned later), D-113 (`engine/core/` started with `contest_rules.py`; frozen pydantic, unknown fields refused), D-117 (registry in `engine.core`).
- Rules: `.claude/rules/python.md` (`engine/core` never imports `engine/sports/*`; models are built from a `ModelSpec`, no hidden behaviour outside it).
- *From TASK-023 (PR #52):* `engine/core/` already exists, holding `contest_rules.py` (D-113); this task adds the rest of the light core beside it.
- **The light core today:** `python/engine/pyproject.toml` lists `pydantic`, `httpx`, `tzdata` and `cfb-db` as base dependencies; numpy and scipy aren't installed yet. The API doesn't depend on `cfb-engine` at all (`python/api/tests/test_bundle.py` asserts numpy and the engine stay out of its install), so adding them here doesn't change the API bundle.
- **Settled when this task was written (2026-10-25, owner accepted the recommendation):** Φ comes from the standard library (`statistics.NormalDist`), so scipy doesn't join now; it joins with the first code that needs it (likely M4.3's empirical distribution). numpy joins the light core in this task only if the interfaces or math use it (for example `Ratings` as arrays); otherwise TASK-033 adds it with the first fit.
- **Concept:** a spec is the model's recipe written as data. Two runs with the same spec and the same data must give the same numbers, which is what lets a model version mean something and lets the Lab (Phase 7) build a form from the spec's schema.
- **Decide at the plan gate:** the spec's shape for families this phase needs (`power` for Rung 1 and the Rung 0 baselines, with `efficiency` reserved for M4.1) and how a setting marks itself as tuned by the backtest (for example a list of candidate values) so M3.2 can read it; the cover-probability signature, so M4.3's empirical distribution can replace the normal without changing callers; the registry's first entries (the v1 inputs only; M18.1 adds the catalog); where `spec_schema_version` lives.

## Acceptance criteria

- [ ] AC-1: The probability functions return, for pred_margin 6.0 and spread_home −3.0 with σ 16.0: edge 3.0 (home side), cover probability Φ(3/16) to 4 decimal places, and EV at −110 equal to `p × 100/110 − (1 − p)`; EV is 0 to 6 decimal places at p = 110/210; a negative edge names the away side with the same probability as the mirrored positive edge.
- [ ] AC-2: Given a spec with pick rules min edge 2.5, min probability 0.55 and tiers A ≥ 5.0, B ≥ 3.5, C ≥ 2.5, the pick function returns tier A at edge 5.0, B at 3.6, C at 2.5, no pick at 2.4, and no pick at edge 3.0 when the probability is below 0.55; with market shrinkage k the blended margin is `k × pred_margin + (1 − k) × (−spread_home)`, and k = 1 leaves the edge unchanged.
- [ ] AC-3: `ModelSpec` refuses, with an error naming the field, a spec with an unknown field, an input id that isn't in the registry, or a weight that is neither `fit` nor a number; a valid spec round-trips through JSON to an equal object, and its JSON Schema lists exactly the registry's input ids as the allowed `stat` values.
- [ ] AC-4: The input registry has one entry per v1 input (§ 10.2), each with every § 10.6 field filled; ids are unique, and a test fails if an entry is added without a label or definition.
- [ ] AC-5: Importing `engine.core` in a fresh interpreter loads none of `duckdb`, `pyarrow`, `httpx`, `boto3`, `pandas` or any `engine.sports`, `engine.ingest` or `engine.transform` module (checked through `sys.modules` in a subprocess).
- [ ] AC-6: `RatingModel` and `GamePredictor` are typed protocols matching 04 § 6's contract, and a `Prediction` carries `pred_margin`, `margin_sd`, `home_win_prob` and `drivers` as `(label, points)` pairs; pyright passes with a test double implementing both.

## Out of scope

- Any rating model (Rung 1 is TASK-033, Rung 2 is M4.1) or the backtest harness (TASK-030).
- The empirical margin distribution and real `drivers` (M4.3); this task's cover probability uses the normal.
- Tuning the pick rules (M4.4): the rules here only apply whatever the spec says.
- The full metric catalog in the registry (M18.1), the conference-tier option `shrink_toward` (M4.1).
- Making the API depend on the engine, or any API route that reads the registry.

## Files likely touched

- `python/engine/src/engine/core/spec.py`: `ModelSpec` v1 and its JSON Schema (new).
- `python/engine/src/engine/core/inputs.py`: the input registry (new).
- `python/engine/src/engine/core/probability.py`: edge, cover probability, EV, market shrinkage (new).
- `python/engine/src/engine/core/picks.py`: pick and tier rules read from the spec (new).
- `python/engine/src/engine/core/interfaces.py`: `RatingModel`, `GamePredictor`, `Prediction`, `Ratings` (new).
- `python/engine/src/engine/core/__init__.py`: exports.
- `python/engine/pyproject.toml` and `python/uv.lock` (through `uv add`): numpy, only if this task's code uses it.
- `python/engine/tests/test_core_probability.py`, `test_model_spec.py`, `test_core_imports.py`: AC-1 to AC-6 (new).
- `docs/decisions.md`: the spec's shape and the light-core boundary as a D-### row.

## Verification

- Automated: the three new test files; `pnpm typecheck` (pyright) for AC-6.
- Manual: in `uv run python`, build the spec from 04 § 6's sketch (minus inputs the registry lacks), print its JSON Schema → `stat` is an enum of the registry ids, and `fit`/number weights validate.

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
