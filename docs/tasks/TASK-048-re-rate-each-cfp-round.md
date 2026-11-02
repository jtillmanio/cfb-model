---
id: TASK-048
title: Re-rate each CFP round after the rounds before it
status: Draft
depends_on: [TASK-047]
size: M
model: opus
autonomy: attended
ui: false
plan_status: none
planned_at_commit:
---

# TASK-048 — Re-rate each CFP round after the rounds before it

## Goal

A College Football Playoff game is predicted from ratings that include the playoff rounds already played, not from the ratings entering the first bowl, but only if the backtest shows it predicts better. Target: before the 2027 postseason.

## Context

- Task list: `docs/08-tasklist.md` › M19 › M19.7.
- Model: `docs/04-model.md` § 9.2 ("The postseason is one week"); D-127 (its revisit: a CFP round may need its earlier rounds' results), D-131 (the harness scores postseason week 1 as one unit, `as_of` the first bowl's kickoff), D-150 (production rates it the same way, re-run each Sunday at that same `as_of`).
- *From TASK-047 (feat/047-rate-and-pick-the-postseason):* CFBD files every bowl and CFP round under postseason week 1, and the harness, `team_week_features`/`game_features` and the weekly job all treat it as one week with one `as_of`. A 12-team CFP's title game is then predicted from ratings about five weeks old that never saw the playoff. Splitting it (for example a sub-week per round, each with its own `as_of`, the first kickoff of that round) touches the feature tables' week key (D-127), the harness's week walk (D-131), how `model_runs`/`team_ratings` name a sub-week (D-150 keys a week by `(season_type, week)`: a schema change, so stop and ask), and the weekly job's coming-week rule (`jobs.due_weeks`). Validate it in the backtest (postseason games are reported on their own, 04 § 9.3) before it runs live, so live still scores what was validated.
- *From TASK-047 (feat/047-rate-and-pick-the-postseason):* the header comment of `.github/workflows/lines.yml` still describes the old coming-week rule ("the earliest week with a game not yet kicked off"); D-150 made it the week of the earliest kickoff still to come. It was left alone because editing a workflow file makes its branch run a ready gate, and `lines` writes to production. Fix it when this task (or any change before it) touches `lines.yml` or the coming-week rule.

## Acceptance criteria

To be written when the task is planned.

- [ ] AC-1:

## Out of scope

- CFP bracket odds and season simulations (Phase 5, M9).

## Files likely touched

- `python/engine/src/engine/transform/features.py`, `backtest/harness.py`, `publish/models.py`, `jobs.py`
- `python/db/` models and a migration if a sub-week needs its own key (schema change: stop and ask)

## Verification

- Automated: to be written with the ACs.
- Manual: a backtest of 2016–2023 with and without the split, postseason MAE compared.

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
