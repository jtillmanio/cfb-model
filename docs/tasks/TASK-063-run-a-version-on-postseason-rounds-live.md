---
id: TASK-063
title: Run a version on postseason rounds live and show each round's predictions
status: Draft
depends_on: [TASK-058]
size: M
model: opus
autonomy: attended
ui: false
plan_status: none
planned_at_commit:
---

# TASK-063 — Run a version on postseason rounds live and show each round's predictions

## Goal

The paper-traded model rates each College Football Playoff round after the rounds before it, and This Week shows those predictions. The owner wants this landed before the first 2026 bowl (owner, 2026-11-07), so it needs to be Ready and merged, and the release run, before the Sunday that first rates the postseason.

## Context

- Task list: `docs/08-tasklist.md` › M19 › M19.8.
- *From TASK-058 (feat/task-058-rate-each-cfp-round-live):* TASK-058 built the engine (`engine rate`, the weekly job, `lines` re-picks; D-161), but no live version uses it. `efficiency-v1.json` is `one_week`, and `postseason: rounds` changes the spec hash (it's left out of the hash only at the default, D-151), so three things stand in the way:
  - `models._version` refuses v1.0 with another spec, so a `rounds` spec needs its own version name or number.
  - `models.settings` refuses a `run.json` of another spec hash, so it needs its own, from a backtest of that spec that scored 2026 (as `efficiency-v1-2026.run.json` was, D-149).
  - `.github/workflows/rate-and-predict.yml` names the spec, the choices and the version.
- *From TASK-058 (feat/task-058-rate-each-cfp-round-live):* `/slate` reads one run for the week: `week_run` in `python/api/src/api/slate.py` matches `r.week` to the week from `games`, which is 1 for every postseason game. A `rounds` version's quarterfinals onward are predicted in runs with `week` 2–4, so they'd show no prediction or model line, and `RULES_SQL` reads its `fitted_params` from that one run too. Picks are unaffected: `PICKS_SQL` reads by game. `GAMES_SQL`'s `ranks` would keep showing round 1's ranks.
- *From TASK-058 (feat/task-058-rate-each-cfp-round-live), open question for the plan:* which version shows in the app? `shell.SHOWN` takes the newest live candidate with a scheduled run this season, so a new version would replace v1.0 on screen in December with a record of zero games. Options: keep v1.0 the shown one and run the new version beside it (the job rates one version today; many versions are M23.1, D-147), or switch and accept the short record. The owner decides at the plan gate.
- *From TASK-058 (feat/task-058-rate-each-cfp-round-live), open question for the plan:* does the version start at round 1 (the first postseason Sunday) or at the first round after it? `lines` re-picks every round of a `rounds` version's own runs, but a version's first run needs round 1's games rated if the bowls are to be picked by it.
- `.github/workflows/rate-and-predict.yml` is a workflow file: changing it runs the "Changed workflow run on the branch" ready gate, and the job writes to production, so the owner decides at the PR whether that run happens (a `dry_run` hand run does every step and rolls back).
- Decisions: D-161, D-151, D-150, D-149, D-144, D-156, D-158.

## Acceptance criteria

- [ ] AC-1: Given postseason games predicted in a round-1 run and a round-2 run of the shown version, `/slate` for postseason week 1 returns each game's `pred_margin` from the newest succeeded run that predicted it (expected: a bowl's from round 1's run, a quarterfinal's from round 2's), and each game's blended line is computed with that run's `fitted_params`.
- [ ] AC-2: A spec file with `postseason: rounds` and a `run.json` with its `spec_hash` and a 2026 entry exist under `python/engine/specs/`, and `engine job rate-and-predict --dry-run` with them exits 0 on the dev database.
- [ ] AC-3: `.github/workflows/rate-and-predict.yml` names the chosen spec, choices and version, and the shown version on `/slate` is the one the owner chose at the plan gate.
- [ ] AC-4: `/slate`'s query count for a postseason week stays within `QUERY_BUDGET` (`api/wave.py`).

## Out of scope

- Engine changes to how a round is chosen or fit (TASK-058).
- Opening the 2024–2025 holdout to score the 12-team rounds (D-151: the owner's call).
- Rating several versions in one job (M23.1).

## Files likely touched

- `python/api/src/api/slate.py`, `python/api/tests/` (the slate tests)
- `python/engine/specs/` (the new spec and `run.json`)
- `.github/workflows/rate-and-predict.yml`
- `docs/decisions.md`, `docs/model-guide.md`, `README.md` › Jobs

## Verification

- Automated: the `/slate` test named in the plan passes.
- Manual: `engine job rate-and-predict --dry-run` on the dev database with the new spec → expected: exit 0, "Week rated" naming the coming week.

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
