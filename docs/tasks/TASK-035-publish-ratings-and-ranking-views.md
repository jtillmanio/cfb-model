---
id: TASK-035
title: Publish model runs, ratings and predictions, with the team_rankings and team_schedule_strength views
status: In progress
depends_on: [TASK-033, TASK-034]
size: M
model: opus
autonomy: attended
ui: false
plan_status: approved
planned_at_commit: a076c8c
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

- D-136: the rate command, `as_of`, run choice, FCS rule, SOS formula and failed-run rule; its revisit names postseason ratings, which need a `season_type` on `team_ratings` (approved at plan)
- `docs/03-data-model.md` › Views: rows for `latest_team_ratings`, `team_rankings` and `team_schedule_strength` with the agreed rules (approved at plan)

## Plan

_Approved by the owner 2026-10-27._

**Plan-gate decisions**
1. **Command:** `engine rate --spec FILE --season Y --week N --target dev|test [--choices RUN.json] [--name NAME] [--version V]` (name defaults to the spec's `base`, version to `v1.0`). A spec with tuned settings needs `--choices`, a backtest's `run.json`, and uses `choices[Y]`; refused when the run's `spec_hash` differs or Y isn't in it. The version is found by (sport, market `spread`, name, version) or created with status `dev`; an existing one whose spec differs is refused. Under `LIVE=true` every target is refused.
2. **`as_of`** is the D-127 feature week's `as_of` (its first kickoff), so the fit sees what the backtest sees entering that week (answers TASK-034's open question; the fixture's Sunday `as_of` is test data only).
3. **Regular season only**: `team_ratings` has no `season_type`, so postseason week 1 would collide with regular week 1.
4. **FCS:** a row per FCS team at the pool's rating (what predictions use); ranks and SOS ranks cover FBS teams only (`team_seasons.division = 'fbs'`).
5. **Run a view reads:** the newest `succeeded` run per (version, season, week), by `finished_at` DESC then `id` DESC. Ties: `RANK()` (1, 2, 2, 4).
6. **SOS:** the mean over this season's `final` games finished (kickoff + 4 h; a TBA game kicks off at the end of its Eastern date) by the run's `as_of`, of the opponent's rating in the same run, + HFA when the opponent was at home, − HFA when away, 0 at a neutral site; HFA = that run's `fitted_params.home_field`. NULL with no game played, or when an opponent or HFA is missing. SOS rank 1 = the highest SOS.
7. **Failure:** the fit and predictions run before any transaction. A raised error or a NaN/±Infinity output records one `failed` run with its error and no ratings or predictions, exit 1.
8. **No new index:** a one-team read ranks its whole week through `(model_version_id, season, week)`; AC-4's reads filter version, team, season and week.

**Steps**
1. Tests first (below); confirm each fails for the expected reason.
2. `python/engine/src/engine/publish/models.py` (new): `rate_week()` loads `harness.load(lake)`, resolves the spec, finds the week's `as_of`, fits with `fit_games` + `_check_fit` + `check_reads`, predicts every staged week-N game with both teams; `publish_run()` maps CFBD source ids to `teams.id`/`games.id` (refusing unpublished ones), finds or creates the version, and inserts the run (`adhoc`, `fitted_params` = learned params + `choices`), ratings and predictions (drivers as `[{label, points}]`), refusing non-finite values.
3. `python/engine/src/engine/cli.py`: `engine rate`.
4. Views: `python/db/views/020_latest_team_ratings.sql` (new helper, not in "Files likely touched": the newest succeeded run's ratings with `fbs` and FBS `rank`), `030_team_rankings.sql` (`previous_rank`, `rank_change` = previous − current), `040_team_schedule_strength.sql` (`games_played`, `sos`, `sos_rank`).
5. Docs: `python/db/views/README.md`, `docs/03-data-model.md` › Views, D-136 in `docs/decisions.md`.

**Files:** the six above, `python/engine/tests/test_publish_models.py`, `python/db/tests/test_team_rankings.py`, `python/db/tests/test_team_schedule_strength.py`, `docs/03-data-model.md`, `docs/decisions.md`, this task file (12).

**Test strategy**
- AC-1 `test_publish_models.py::test_rate_inserts_a_run_and_a_rerun_inserts_another`: the season lake fixture published into `db_conn` (rolled back), week 5 of 2025 rated twice.
- AC-5 `test_publish_models.py::test_rate_refuses_under_live` (CLI, nothing opened) and `::test_failed_fit_records_a_failed_run_without_outputs`.
- AC-2 `test_team_rankings.py::test_seeded_week_6_order_and_change` (expected from `models.json`, FBS only) plus constructed newest-run and week-1 NULL cases.
- AC-3 `test_team_schedule_strength.py::test_sos_adjusts_for_site` and `::test_sos_rank`.
- AC-4 `test_team_rankings.py::test_single_team_read_uses_index`, `test_team_schedule_strength.py::test_single_team_read_uses_index` (`EXPLAIN`, `enable_seqscan = off`, every `team_ratings` node has an index condition).

**Risks:** rating a week before all earlier games are final gives a different fit on a re-run (the run records what it saw); a whole-season read of the views is heavier, and no screen needs one yet.

**Revisions during implementation** (both inside the plan's scope, reported in the PR)
1. `rate()` takes the lake, not a loaded `History`: the week's unplayed games aren't in `History` (it keeps final games and eligible ones), so `rate` reads them from staged `games` itself, leaving `harness.py` unchanged.
2. `python/db/tests/model_rows.py` (new): the constructed teams, version, runs, ratings and games both view test files share.

## Review log

_Filled by /implement-task. One line per round._

## Blocked

_Only if status is Blocked: what failed, what was tried, best hypothesis, decision needed._

## Metrics

- Verify rounds:
- Review rounds:
- First-pass AC FAILs:
- Plan revisions after approval:
