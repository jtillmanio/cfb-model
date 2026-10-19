---
id: TASK-020
title: Publish reference data, games and line snapshots to Postgres, with the game_market view
status: Ready
depends_on: [TASK-016, TASK-017]
size: M
model: opus
autonomy: attended
ui: false
plan_status: none
planned_at_commit:
---

# TASK-020 — Publish reference data, games and line snapshots to Postgres, with the game_market view

## Goal

The dev database receives every team, venue, game and line from the staged lake. A publish can be re-run without duplicating rows or renumbering IDs. A `game_market` view gives each game's opening, current and closing line.

## Context

- Task list: `docs/08-tasklist.md` › M2 › M2.5.
- Data model: `docs/03-data-model.md` › Views (`game_market`: opening, current and closing consensus line; closing = last snapshot before kickoff, or before the end of `game_date` when the kickoff time is unknown); › Conventions (upsert by `(source, source_id)`, never truncate); › Games & market.
- Model: `docs/04-model.md` § 9.3 (the `consensus` provider's spread when present, otherwise the median across providers; each game records which source it used).
- Architecture: `docs/02-architecture.md` › Components › 1 (`publish`); › Non-functional requirements › Data correctness (publishing stops on a failed data-quality check; nothing partial reaches Postgres); › Testing strategy › Levels › Integration: database (view tests on the fixture, `EXPLAIN` shows no full scan for single-item reads, upsert is idempotent).
- Decisions: D-029 (derived values are views), D-030 (stable IDs), D-037 (append-only snapshots, closing line), D-016 (bulk publish uses the unpooled URL).
- Rules: CLAUDE.md hard rules 1 and 3; `.claude/rules/database.md` › Views & queries (filter before aggregating, `EXPLAIN` test, CTEs read once); `python/db/views/README.md` (`CREATE OR REPLACE VIEW`, one test per view).
- Existing code: `python/engine/src/engine/publish/reference.py` (the upsert pattern) and `python/engine/tests/test_publish_reference.py` (the idempotency test pattern, `source = 'pytest'`, rolled back).
- **Where publishing goes:** this task publishes to the dev database from the CLI. Production is published only by the scheduled workflows (TASK-022): the settings and the destructive guard deny local commands that target production (D-015).
- **Decide at the plan gate:** what `game_market` returns as "closing" for a game that hasn't kicked off (the latest snapshot so far, or NULL until kickoff); how backfilled open/close lines (stored per TASK-016's decision) feed the view; which column records whether the line came from `consensus` or a median; whether the view also exposes totals.
- *From TASK-016 (PR #52), open question for the plan:* `seasons.current_week` is stored (03 › Reference; TASK-016's AC-4), though it follows from `seasons.weeks` and the clock. Who keeps it current: the `/calendar` publish, or a view over `weeks`?
- *From TASK-016 (PR #59):* `engine/publish/reference.py` has `upsert_season`, `upsert_sportsbooks` and `insert_line_snapshots` for this task to reuse; D-115 has the `kind` column and the key. `insert_line_snapshots` sends one multi-row statement, so a season of `/lines` (15 columns a row) must go in chunks under Postgres's 65,535 bind parameters (`upsert_games` has the same limit). It is exercised only through the fixture seed so far, so give it a direct idempotency test. An untimed `opening` row keeps the first value published: a later pull whose `spreadOpen` differs is skipped (the raw lake keeps it).
- *From TASK-016 (PR #59), open question for the plan:* backfilled `opening`/`closing` rows have `captured_at` NULL (D-115). Does `game_market` prefer a `closing` row over the last snapshot before kickoff (03 › Views gives only the latter)? How do the feature and backtest point-in-time checks (hard rule 4, max source timestamp < `as_of`) treat untimed rows, which are before kickoff by definition?
- *From TASK-017 (PR #60):* staged lines are one row per (game, provider, `fetched_at`) with `spread_home`, `spread_home_open`, `total`, `total_open`, `ml_home` and `ml_away`, for every pull; which pulls become `opening`, `closing` or `snapshot` rows (D-115) is this task's call. Publish calls `engine.transform.quality.run(lake)` and refuses when `not report.ok` (AC-2).
- *From TASK-017 (feat/017-transform-rebuild-and-quality-checks):* map staged columns by meaning, not by name. Staged `team_seasons.classification` (fbs/fcs) is Postgres `team_seasons.division` (the API filters `ts.division = 'fbs'`; `map_games` puts classification there too), and `cfbd_division` (East/West) has no Postgres column. Staged `venues.elevation` is CFBD's value: confirm its unit before writing `venues.elevation_m`. A venue filled in from `/games` can have a NULL `name`, while `venues.name` is NOT NULL. `games.closing_line_missing` is a staging-only flag for the check, never a `games` column (hard rule 1). A game that drops out of a newer `/games` pull (e.g. cancelled) keeps its older staged record.

## Acceptance criteria

- [ ] AC-1: Publishing the staged lake fixture into the test DB twice leaves the IDs and row counts of `teams`, `venues`, `games`, `seasons`, `sportsbooks` and `line_snapshots` unchanged.
- [ ] AC-2: Given staged data that fails a data-quality check, `engine publish` exits non-zero before writing anything, and every table's row count is unchanged.
- [ ] AC-3: Given a game with consensus snapshots on Sun, Tue, Thu and Sat before kickoff, plus one captured after kickoff, `game_market` returns opening = Sun's spread, closing = Sat's, and current = the newest snapshot.
- [ ] AC-4: Given a game with `kickoff_at` NULL, its closing line is the last snapshot before the end of `game_date` in Eastern time. Given a game with no consensus line but three providers, the view returns their median and marks it as a median.
- [ ] AC-5: On the seeded test DB, `game_market` for Texas @ Oklahoma returns opening `spread_home` +7 and current +6.5, and Furman @ Clemson returns NULL lines.
- [ ] AC-6: `EXPLAIN` of `SELECT * FROM game_market WHERE game_id = :id` on the seeded test DB shows no sequential scan of `line_snapshots`.

## Out of scope

- Publishing to production, and the scheduled jobs (TASK-022).
- Publishing stats, plays or features to Postgres: they stay in the lake.
- Publishing CFBD's alternate team names into `team_aliases`, and Splash aliases (M6).
- Any API endpoint or screen reading `game_market` (M5).

## Files likely touched

- `python/engine/src/engine/publish/reference.py`: publish teams, venues, games and seasons from staging.
- `python/engine/src/engine/publish/lines.py`: sportsbooks and line snapshots (new).
- `python/engine/src/engine/cli.py`: `engine publish --target dev`.
- `python/db/views/010_game_market.sql`: the view (new).
- `python/engine/tests/test_publish_staging.py`: AC-1, AC-2 (new).
- `python/db/tests/test_game_market.py`: AC-3 to AC-6 (new).
- `python/db/views/README.md`: drop "Empty until the first view lands".

## Verification

- Automated: `test_publish_staging.py`, `test_game_market.py`; the backup's view check still passes with one view (it queries every view).
- Manual: `engine transform --rebuild && engine publish --target dev` on the local lake → `pnpm dev` `/teams` lists the published teams; running publish again reports 0 new rows.

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
