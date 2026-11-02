---
id: TASK-047
title: Rate, predict and pick the postseason (bowls and the CFP)
status: Draft
depends_on: [TASK-046]
size: M
model: opus
autonomy: attended
ui: false
plan_status: none
planned_at_commit:
---

# TASK-047 — Rate, predict and pick the postseason (bowls and the CFP)

## Goal

The weekly job rates, predicts and picks the bowls and the College Football Playoff as it does the regular season, so paper trading of 2026 covers the postseason. It needs to land before the first bowl, about 2026-12-13.

## Context

- Task list: `docs/08-tasklist.md` › M4 › M4.9.
- Roadmap: `docs/06-roadmap.md` › Timing context ("paper-trade the back half of 2026 plus bowls/CFP").
- Model: `docs/04-model.md` § 9.1; D-131 (postseason week 1 is one unit, every bowl and CFP game predicted from the ratings entering the first bowl), D-127 (its revisit: a CFP round may need its earlier rounds' results).
- Decisions: D-136 (`engine rate` is regular season only because `team_ratings` has no season type, so postseason week 1 would collide with regular week 1), D-149 (the weekly job stops, writing nothing, when the coming week is the postseason).
- *From TASK-046 (feat/046-weekly-rate-predict-pick-job):* `rate-and-predict` takes the week `lines` would pull and ends with exit 0 and "the postseason isn't rated yet" when it's postseason week 1. `model_runs` and `team_ratings` key a week by `(season, week)` with no season type, and the `latest_team_ratings`, `team_rankings` and `team_schedule_strength` views read them that way. Rating the postseason needs a season type there, or another way to keep postseason week 1 apart from regular week 1: a schema change, so stop and ask.
- *From TASK-046 (feat/046-weekly-rate-predict-pick-job), open question for the plan:* a game postponed to later in the season keeps its old week "not yet kicked off", so `lines` (and the weekly job, which shares its week rule, `jobs.due_weeks("lines", …)`) stays on that earlier week until the game is played. Decide whether the week rule changes (for example, the week of the earliest kickoff still to come) while touching it.
- **Decide at the plan gate:** the schema change for a postseason week; whether the CFP's later rounds are re-rated after earlier rounds finish (D-127) or all predicted entering the first bowl (D-131); what the views show for postseason ratings.

## Acceptance criteria

- [ ] AC-1: Given a lake fixture whose coming week is postseason week 1, `engine job rate-and-predict --target dev` inserts a `scheduled` run for the postseason week, its ratings, a prediction for every bowl and CFP game that will be played, and its picks, in one transaction, without colliding with the same season's regular week 1 run (test).
- [ ] AC-2: `latest_team_ratings` and `team_rankings` read a season's regular week 1 and postseason week 1 as different weeks (test).
- [ ] AC-3: `engine job lines` re-evaluates the postseason week's picks as it does a regular week's (test).

## Out of scope

- Season simulations and the CFP bracket odds (Phase 5).
- Re-tuning the settings for the postseason.

## Files likely touched

- `python/db/` models and a new migration: a season type on the rated week (schema change: stop and ask).
- `python/db/views/*.sql`: the ratings views.
- `python/engine/src/engine/publish/models.py`, `jobs.py`: rate the postseason week.
- `python/engine/tests/test_rate_and_predict.py`, `test_publish_models.py`.

## Verification

- Automated: the tests above.
- Manual: on the dev DB in December, `engine job rate-and-predict --target dev` → the summary names postseason week 1 and counts its bowl predictions and picks.

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
