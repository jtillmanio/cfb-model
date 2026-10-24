---
id: TASK-019
title: Build point-in-time team_week_features and game_features
status: In progress
depends_on: [TASK-018]
size: M
model: opus
autonomy: attended
ui: false
plan_status: approved
planned_at_commit: 945fd7d
---

# TASK-019 — Build point-in-time team_week_features and game_features

## Goal

For any season and week, the lake holds each team's form entering that week and a home-vs-away row for each game, built only from games played earlier. Tests prove that a later game can't leak into them.

## Context

- Task list: `docs/08-tasklist.md` › M2 › M2.4.
- Data model: `docs/03-data-model.md` › Lake layout (`features/team_week_features/`: one row per team, season, week = as-of state; `features/game_features/`: home vs away features + target; week N aggregates only games with `week < N` or kickoff before `as_of`); › Data quality checks ("no future data": max source game time < `as_of`).
- Model: `docs/04-model.md` § 9.2 (unit of work is (season, week); feature rows carry `as_of`; the harness asserts no input postdates it); § 2 Rung 1 (margins) and Rung 2 (off/def efficiency, rush/pass splits, success rate, explosiveness), the first readers of these tables.
- Architecture: `docs/02-architecture.md` › Testing strategy › Levels › Model / backtest (leakage: changing any game after week N leaves week-N rows unchanged).
- Decisions: D-042 (point-in-time features with assertions), D-027.
- Rules: CLAUDE.md › Domain conventions (ratings at `(season, week=N)` mean "entering week N"; `margin = home_points − away_points`; never season aggregates in a backtest); `.claude/rules/python.md` (every feature table asserts max source timestamp < `as_of`).
- **Concept:** a feature row is a snapshot of what was knowable at a moment. If week 6's row for Ohio State included week 6's own game, a backtest would "predict" a game it had already seen and look far better than the live model will.
- **Decide at the plan gate:** the first feature columns (enough for Rung 1 and Rung 2: games played, points for and against, margin, off/def EPA per play, success rate, explosiveness, rush/pass splits, from garbage-time-filtered stats per TASK-018); how `as_of` is set for a week (for example the first kickoff of week N, or the calendar's week start); how postseason weeks order after the regular season; whether week 1 rows exist with NULL aggregates (unknown is NULL, never zero-filled).
- *Added 2026-10-20 (docs/ratings-depth-features):* M18.1 later adds the full unit metric catalog (`docs/04-model.md` § 10.2: PBP-derived metrics with our own garbage-time filter, special teams, finishing drives, havoc) and M18.2 adds opponent-removed aggregates (§ 10.3) to these tables. Name this task's columns so they extend by metric × split × side without renames; no new columns are in scope here.
- *From TASK-018 (PR #62):* TASK-018's approved plan stages `team_game_advanced` (one row per game and team, `garbage_time_excluded`, `off_*`/`def_*` columns for plays, ppa, success_rate, explosiveness, rush and pass splits, power_success, stuff_rate and line_yards) and `team_games` (box score `stats` as JSON text). Plays and drives are partitioned as `staging/{plays,drives}/season=YYYY/data.parquet` in a `SEASON_TABLES` registry, outside `TABLES`.
- *From TASK-018 (PR #64):* as built, plays and drives carry `offense_source_id`/`defense_source_id` (resolved from the game's home and away names; NULL if unmatched, and the rebuild lists it), and each game's plays and drives come from the newest pull that has the game, never merged across pulls. `team_game_advanced` holds only games in staged `games` (FCS-only games are dropped). Columns: `docs/03-data-model.md` › Lake layout; D-119.
- *From TASK-021 (PR #67):* the full 2014–2026 lake is backfilled. 103 team-games in 2014–2025 (mostly 2014–2016, 8 in 2024) have no `team_game_advanced` row because CFBD never computed them (missing or partial play-by-play); the `advanced_stats` check lists them as notes (D-121). The feature tables need a rule for those games: a box-score fallback, or leaving them out of the season-to-date averages. App State–Liberty 2024 (week 5) was canceled and stays `scheduled` in staged `games`.

## Acceptance criteria

- [ ] AC-1: Every `team_week_features` and `game_features` row has a non-null `as_of`, and the build asserts each row's newest source game kickoff is before its `as_of`. Given an injected input that violates it, the build fails and names the team, season and week.
- [ ] AC-2: Given the lake fixture, changing the score and stats of one week-7 game and rebuilding leaves every row for weeks ≤ 7 identical, and changes at least one week-8 row.
- [ ] AC-3: Given a fixture team that played in weeks 1, 2 and 3, its week-4 row has 3 games played and points for equal to the sum of those three games' points; its week-1 row has 0 games played and NULL averages.
- [ ] AC-4: `game_features` has one row per staged game, carrying the home and away teams' entering-week features, `neutral_site`, and the target `margin = home_points − away_points` (NULL for a game not yet played).
- [ ] AC-5: `engine transform --rebuild` builds the feature tables after staging, still with zero API calls.

## Out of scope

- Ratings of any rung (M3.5, M4.1), preseason priors (M4.2), the backtest harness (M3.2).
- Opponent adjustment: these are raw aggregates; adjusting for opponents is Rung 2's job.
- Season-level features from earlier seasons (priors read those in M4.2).

## Files likely touched

- `python/engine/src/engine/transform/features.py`: the feature SQL and the `as_of` assertion (new).
- `python/engine/src/engine/transform/__init__.py`: run features after staging.
- `python/engine/tests/test_features.py`: AC-1, AC-3, AC-4 (new).
- `python/engine/tests/test_leakage.py`: AC-2 (new).
- `python/engine/tests/fixtures/lake/`: enough weeks for one team to have 3+ games and a week-8 row.

## Verification

- Automated: `test_features.py`, `test_leakage.py`, `test_transform.py` (AC-5).
- Manual: on the local lake, rebuild and query one team's rows for weeks 1–8 with DuckDB → games played rises by at most one per week, and each row's `as_of` is after that team's previous game.

## Follow-ups

_Work noticed during this task and deliberately left out. Each bullet ends `→ <path> § <section>` (where it was placed) or `→ not tracked: <reason>`. See `.claude/skills/track-follow-ups/classify.md`; the PR's Follow-ups section is copied from here._

## Plan

Approved 2026-10-24 (attended), with both open questions settled as recommended.

**Decisions (recorded as a D-### row at close-out):**
- `as_of` for a (season, season_type, week) is the earliest kickoff among that week's staged games; a TBA kickoff counts as the start of its Eastern `game_date` here, so `as_of` is never late.
- A row includes the team's `final` games that season whose kickoff is before `as_of` (a TBA game counts as the end of its Eastern date, the existing cutoff convention). The cutoff is a time, not a week label, so postseason orders after the regular season and a rescheduled game can't leak. On the 2014–2026 lake no game kicks off after a later week's first kickoff (Army–Navy 2025 is 5 h before the first bowl).
- Rows: every team in the season's staged games × every week with a staged game. Week-1 rows exist with `games_played` 0, sums 0, averages NULL. A future live week's row holds the games final so far.
- `team_week_features` columns: `team_source_id, season, season_type, week, as_of, last_game_kickoff`; `games_played, points_for, points_against` (sums), `points_for_per_game, points_against_per_game, margin_per_game`; `advanced_games, off_plays, def_plays` (sums); season-to-date means of `{off,def}_{,rush_,pass_}{ppa,success_rate,explosiveness}` (side_split_metric, as `team_game_advanced` names them, so M18 extends without renames).
- Rates are **means of per-game values** (one game = one observation, as Rung 2 treats a game); staging has no rush/pass play counts, so play-weighting would need a staging column.
- Team-games with no advanced stats (D-121's 103) count in `games_played` and points but not in the efficiency means; `advanced_games` is their denominator. No box-score fallback (box scores aren't garbage-time filtered).
- `game_features`: one row per staged game: `game_source_id, season, season_type, week, as_of, kickoff_at, neutral_site, home_source_id, away_source_id`, `home_*`/`away_*` copies of every feature column, and `margin` (NULL unless final).
- AC-2 reading: every `team_week_features` row for weeks ≤ 7 is identical, and every week-≤7 `game_features` column except the changed game's own target `margin`.

**Steps:**
1. Season fixture helper in `lake_fixture.py`: clone the 5 week-1 games, their advanced stats and lines into weeks 2–8 (7 days apart, points varied, one bye); write the failing tests.
2. `transform/features.py`: the SQL for both tables, the inclusion rule as a module constant, and `check_point_in_time()` raising `PointInTimeError` naming team, season, season type and week.
3. `transform/__init__.py`: a `FEATURE_TABLES` registry built after staging, asserted, then written to `features/<name>.parquet` with the staged files; counts returned.
4. `cli.py`: `transform --rebuild` prints a `PointInTimeError` and exits 1.
5. `docs/03-data-model.md` › Lake layout (feature tables and columns) and › Data quality checks; a decisions row.

**Files:** `python/engine/src/engine/transform/features.py` (new), `transform/__init__.py`, `cli.py` (not listed), `tests/lake_fixture.py` (not listed: the fixture is generated in code, so existing counts don't move), `tests/test_features.py` (new), `tests/test_leakage.py` (new), `tests/test_transform.py` (not listed), `docs/03-data-model.md` (not listed), `docs/decisions.md` (not listed).

**Tests:**
- AC-1: `test_features.py::test_every_row_has_as_of_after_its_sources`, `::test_leaky_inclusion_fails_the_build_naming_the_row` (the rule monkeypatched from `<` to `<=`; rebuild exits 1 naming team, season and week)
- AC-2: `test_leakage.py::test_changing_a_week7_game_leaves_weeks_through_7_unchanged`
- AC-3: `test_features.py::test_week4_counts_three_games_and_week1_is_empty`
- AC-4: `test_features.py::test_one_game_row_per_staged_game_with_target`
- AC-5: `test_transform.py::test_rebuild_stages_every_table_with_no_api_calls` extended
- Manual: one local team's weeks 1–8.

## Review log

_Filled by /implement-task. One line per round._

## Blocked

_Only if status is Blocked: what failed, what was tried, best hypothesis, decision needed._

## Metrics

- Verify rounds:
- Review rounds:
- First-pass AC FAILs:
- Plan revisions after approval:
