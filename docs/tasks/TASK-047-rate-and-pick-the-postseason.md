---
id: TASK-047
title: Rate, predict and pick the postseason (bowls and the CFP)
status: In progress
depends_on: [TASK-046]
size: M
model: opus
autonomy: attended
ui: false
plan_status: approved
planned_at_commit: b580f8b
---

# TASK-047 — Rate, predict and pick the postseason (bowls and the CFP)

## Goal

The weekly job rates, predicts and picks the bowls and the College Football Playoff as it does the regular season, so paper trading of 2026 covers the postseason. It needs to land before the first bowl, about 2026-12-13.

## Context

- Task list: `docs/08-tasklist.md` › M4 › M4.9.
- Roadmap: `docs/06-roadmap.md` › Timing context ("paper-trade the back half of 2026 plus bowls/CFP").
- Model: `docs/04-model.md` § 9.1; D-131 (postseason week 1 is one unit, every bowl and CFP game predicted from the ratings entering the first bowl), D-127 (its revisit: a CFP round may need its earlier rounds' results).
- Decisions: D-136 (`engine rate` is regular season only because `team_ratings` has no season type, so postseason week 1 would collide with regular week 1), D-149 (the weekly job stops, writing nothing, when the coming week is the postseason).
- *From TASK-046 (PR #121):* `rate-and-predict` takes the week `lines` would pull and ends with exit 0 and "the postseason isn't rated yet" when it's postseason week 1. `model_runs` and `team_ratings` key a week by `(season, week)` with no season type, and the `latest_team_ratings`, `team_rankings` and `team_schedule_strength` views read them that way. Rating the postseason needs a season type there, or another way to keep postseason week 1 apart from regular week 1: a schema change, so stop and ask.
- *From TASK-046 (PR #121), open question for the plan:* a game postponed to later in the season keeps its old week "not yet kicked off", so `lines` (and the weekly job, which shares its week rule, `jobs.due_weeks("lines", …)`) stays on that earlier week until the game is played. Decide whether the week rule changes (for example, the week of the earliest kickoff still to come) while touching it.
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

- Re-rate each CFP round after the rounds before it (D-127's revisit), validated in the backtest before it runs live; for 2027 (approved at plan) → new Draft task and its task-list stub
- `docs/03-data-model.md` › model_runs, team_ratings and Views: the `season_type` column and the views' week key (approved at plan)
- `docs/04-model.md` § 9.2 › "The postseason is one week": production rates it the same way, re-run each Sunday at the same `as_of` (approved at plan)
- Check 2026's first bowl kickoff against the Sunday 09:00 ET run after Army–Navy; if a bowl kicks off first, dispatch `rate-and-predict` once by hand after Army–Navy (approved at plan) → Owner checklist § Actions

## Plan

Decided at the plan gate (2026-11-02): a `season_type` column (not a week-number encoding); the postseason is one unit as backtested (D-131), each CFP round re-rating waits for a 2027 task; `previous_rank` entering postseason week 1 is the version's last rated regular week; the coming week becomes the week of the earliest kickoff still to come.

**Steps**
1. Migration `0005`: `model_runs.season_type` (text, CHECK `regular|postseason`; `live_run_has_week` also requires it; live rows backfilled `regular`); `team_ratings.season_type` NOT NULL (added with default `regular` to backfill, then the default dropped); index `(model_version_id, season, season_type, week)` replaces `(model_version_id, season, week)`; downgrade drops them. SQLAlchemy models to match (`pnpm db:check` clean).
2. Views `020`/`030`/`040`: carry `season_type`, partition and join by it; `team_rankings.previous_rank` entering postseason week 1 is the version's last rated regular week of the season, otherwise same type week − 1.
3. `publish.models`: `fit_week`, `write`, `rate`, `publish` take `season_type` (default `regular`) and write it to the run and its ratings. `publish.picks`: `_run`/`write_picks`/`publish_picks` look up the run by `(season, season_type, week)`. CLI: `engine rate` and `engine pick` gain `--season-type` (default `regular`).
4. `jobs`: `due_weeks("lines")` = the week of the earliest kickoff still to come; `rate_and_predict` rates the postseason week (drops the stop); `reevaluate` re-picks the newest scheduled run's `(season_type, week)`; summaries name the season type.
5. `engine/fixture.py` and `db/tests/model_rows.py` write `season_type`.
6. Docs: a new decision amending D-136 and D-149; `docs/03-data-model.md`, `docs/04-model.md` § 9.2, `docs/model-guide.md`; the follow-up task and stub; Owner checklist item.

**Files**: `python/db/migrations/versions/0005_rated_season_type.py` (new), `python/db/src/db/models.py`, `python/db/views/020_latest_team_ratings.sql`, `030_team_rankings.sql`, `040_team_schedule_strength.sql`, `python/engine/src/engine/publish/models.py`, `publish/picks.py`, `jobs.py`, `cli.py`, `fixture.py` (not in "Files likely touched": seeds runs and ratings), `python/db/tests/model_rows.py` (not listed: test helper inserts), tests below, docs above.

**Test strategy**
- AC-1: `engine/tests/test_rate_and_predict.py::test_postseason_week_1_is_rated_beside_regular_week_1` (replaces `test_postseason_next_writes_nothing`).
- AC-2: `db/tests/test_team_rankings.py::test_regular_and_postseason_week_1_are_different_weeks` (and the postseason `previous_rank`); the EXPLAIN tests stay.
- AC-3: `engine/tests/test_rate_and_predict.py::test_lines_reevaluates_the_postseason_week`.
- Schema: `db/tests/test_model_schema.py` (backfill, a live run without a season type refused). Week rule: `engine/tests/test_jobs.py`.

**Risks**: the first bowl may kick off before the first Sunday run that sees the postseason as the coming week (Army–Navy holds it back): owner check above. Each Sunday re-rate re-inserts identical predictions for bowls already played (same `as_of`); no pick is written after a game's cutoff.

**Size**: about 20 files, at the limit; no UI.

## Review log

_Filled by /implement-task. One line per round._

## Blocked

_Only if status is Blocked: what failed, what was tried, best hypothesis, decision needed._

## Metrics

- Verify rounds:
- Review rounds:
- First-pass AC FAILs:
- Plan revisions after approval:
