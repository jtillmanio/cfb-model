---
id: TASK-035
title: Publish model runs, ratings and predictions, with the team_rankings and team_schedule_strength views
status: Ready
depends_on: [TASK-033, TASK-034]
size: M
model: opus
autonomy: attended
ui: false
plan_status: none
planned_at_commit:
---

# TASK-035 — Publish model runs, ratings and predictions, with the team_rankings and team_schedule_strength views

## Goal

Rung 1's ratings and predictions for any season and week land in Postgres as a new model run, and the database can answer "where does each team rank entering this week, how far did it move, and how hard has its schedule been" without storing any of those numbers.

## Context

- Task list: `docs/08-tasklist.md` › M3 › M3.7.
- Data model: `docs/03-data-model.md` › Models & outputs (`model_runs`, `team_ratings`, `predictions`; rank is a window-function view); › Views (`team_rankings`: rank and week-over-week change from `team_ratings`; `team_schedule_strength`: per team, season and week, SOS = the average rating entering that week of the opponents already played, adjusted for site, and its rank); › Views footer (re-applied after every migration; a test per view; single-item reads filter before aggregating, checked with `EXPLAIN`).
- Model: `docs/04-model.md` § 10.5 Schedule strength (SOS is an aggregate of stored ratings, so a view; F-17's SOS column and F-18's SOS rank read it; M18.4 adds remaining and full-season SOS).
- Architecture: `docs/02-architecture.md` › Components › 1 (`publish/` inserts versioned ratings and predictions); › Ratings depth (SOS of games played is a view); › Testing strategy › Levels › Integration: database.
- Roadmap: `docs/06-roadmap.md` › Phase 2 (`model_versions` / `model_runs` / `team_ratings` / `predictions` + publish); M3's demo at exit: Rung 1 ratings are published to the dev DB.
- Decisions: D-117 (SOS of games played is a view), D-120 (`engine publish --target dev|test`, one transaction on the direct URL, chunks of 1,000 rows), D-030 (games upserted by source key, so ratings join on stable `games.id` and `teams.id`).
- Rules: hard rules 1 and 2 (rank, Δ and SOS are views; re-runs insert new rows tied to a new `model_run`, never update); `.claude/rules/database.md`; the views README (`python/db/views/README.md`).
- Pattern: `python/engine/src/engine/publish/staging.py` (publish in one transaction, `--target dev|test`, LIVE refusal) and `python/db/views/010_game_market.sql` with `python/db/tests/test_game_market.py`.
- *Added 2026-10-20:* no task computed SOS before M3.7 was given it; the Rankings "SOS" column and the team page's "34th SOS rank" read this view.
- **Concept:** storing a rank would go stale the moment a new run lands; computing it in a view from the stored ratings means it's always the rank of the newest ratings.
- **Decide at the plan gate:** the command (`engine rate --season Y --week N --target dev|test`, or a flag on `engine publish`); which run a view reads when a version has several runs for one week (the newest succeeded run); the site adjustment in SOS (for example the opponent's rating plus the run's HFA when the opponent was at home, minus it when away, nothing on neutral sites); whether SOS rank orders FBS teams only; tie handling in ranks.
- *From TASK-033 (PR #94):* Rung 1 is `engine.backtest.MODELS["power"]`, i.e. `PowerRatings(spec, RULES)` (`engine/models/power.py`, CFB rules in `engine/sports/cfb/teams.py`), spec `python/engine/specs/power-v1.json`, whose tuned settings per season are in a backtest's `run.json` `choices` (D-134). `Ratings.params` holds `home_field`, `margin_sd`, `prior_weight`, `new_team` and `pool_fcs`, which is what `model_runs.fitted_params` stores. `Ratings.teams` lists every FCS team seen at the one FCS pool's rating, so `team_ratings` rows for FCS teams repeat that number: decide whether to publish them or the pool once.
- *From TASK-034 (PR #96):* the test DB's fixture holds `power` v1.0 (`production`), v1.1 and v1.2-dev for cfb/spread (D-135), with v1.0 ratings entering weeks 1–6 of 2026 and the 11 week-6 predictions. A test that publishes a production cfb/spread version must retire v1.0 inside its rolled-back transaction or use the `total` market, and must not reuse name `power` with those versions (the live-row unique index). `off_rating`/`def_rating` are set only for the § 4 top 10 entering week 6; if `team_rankings` ranks units, the filler teams have none.
- *From TASK-034 (PR #96):* `rating`, `pred_margin`, `pred_total` and `margin_sd` are `double precision` with no finiteness check, and the rows can never be fixed (insert-only), so the publish path should refuse NaN and ±Infinity before inserting.
- *From TASK-034 (PR #96):* `team_ratings` has no index leading with `team_id` (its PK leads with `model_run_id`, plus `(model_version_id, season, week)`). If the views' `EXPLAIN` tests show per-team reads (trajectory, team page) scanning, the index is this task's schema change to propose.
- *From TASK-034 (PR #96), open question for the plan:* the fixture sets a run's `as_of` to its calendar week's start (Sun 00:00 ET), while D-127 sets a feature week's `as_of` to its first kickoff and counts a game as finished 4 h after kickoff. Which `as_of` does a published run carry, and does it match the features it read?

## Acceptance criteria

- [ ] AC-1: Given the test DB with a season's games published, `engine rate --spec <power-v1 spec> --season Y --week N --target test` inserts one `model_runs` row (status `succeeded`, `fitted_params` holding the learned HFA) and one `team_ratings` row per team entering week N, plus one `predictions` row per week-N game, all tied to that run; running it again inserts a second run and a second set of rows and leaves the first set unchanged.
- [ ] AC-2: `team_rankings` for a model version, season and week reads only that version's newest succeeded run for the week, ranks teams by rating with rank 1 the highest, and its change equals the team's rank entering the previous week minus its rank entering this week (NULL when there's no previous week); on the seeded test DB, the week-6 order and changes match the seed's week-5 and week-6 ratings.
- [ ] AC-3: Given test rows where a team played three opponents in weeks 1–3 (one home, one away, one neutral) and ratings entering week 4, `team_schedule_strength` for that team entering week 4 equals the mean of the three opponents' week-4 ratings with the site adjustment agreed at the plan gate, and SOS rank 1 is the team with the highest SOS that week.
- [ ] AC-4: A read of either view filtered to one team, season and week uses an index (the `EXPLAIN` check from `test_game_market.py` finds no sequential scan on `team_ratings`), and both views are listed in `python/db/views/README.md` with their tests.
- [ ] AC-5: Under `LIVE=true`, `engine rate --target dev` refuses before writing anything, and a failed fit writes no `team_ratings` or `predictions` rows (the run is recorded `failed` with its error, or nothing is written, as the plan decides).

## Out of scope

- The Rankings and Team screens that read these views (M8), and the API endpoints (M5 onward).
- SOR, remaining and full-season SOS (M18.4).
- The scheduled `rate-and-predict` job (M4.8) and picks (M4.4–M4.6).
- Publishing backtest runs or their metrics.

## Files likely touched

- `python/engine/src/engine/publish/models.py`: insert a run, its ratings and predictions (new).
- `python/engine/src/engine/cli.py`: `engine rate`.
- `python/db/views/020_team_rankings.sql`, `030_team_schedule_strength.sql`: the views (new).
- `python/db/views/README.md`: list both views.
- `python/engine/tests/test_publish_models.py`: AC-1, AC-5 (new).
- `python/db/tests/test_team_rankings.py`, `test_team_schedule_strength.py`: AC-2 to AC-4 (new).
- `docs/03-data-model.md` › Views: the agreed SOS site adjustment and run choice.
- `docs/decisions.md`: the publish command and the views' rules as a D-### row.

## Verification

- Automated: the three new test files; `pnpm db:check`; `pnpm test`.
- Manual: on the dev DB, `uv --directory python run engine rate --spec <power-v1 spec> --season 2026 --week <current> --target dev` → `SELECT * FROM team_rankings WHERE season = 2026 AND week = <current> ORDER BY rank LIMIT 10` lists ten real teams with plausible ratings, and `team_schedule_strength` has a row for each (M3's demo at exit).

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
