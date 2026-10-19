---
id: TASK-018
title: Stage box scores, advanced stats, play-by-play, preseason inputs and benchmark ratings
status: Ready
depends_on: [TASK-017]
size: M
model: opus
autonomy: attended
ui: false
plan_status: approved
planned_at_commit: 57badb4
---

# TASK-018 — Stage box scores, advanced stats, play-by-play, preseason inputs and benchmark ratings

## Goal

The same `engine transform --rebuild` also stages team box scores, advanced stats, plays, drives, talent, returning production, recruiting and SP+/FPI/Elo. These are the inputs the feature tables, preseason priors and baselines read.

## Context

- Task list: `docs/08-tasklist.md` › M2 › M2.3, second half (split from M2.3; TASK-017 is the first half and owns the runner this task extends).
- Data model: `docs/03-data-model.md` › Data sources › CFBD (`/games/teams`, `/stats/game/advanced` with garbage time filterable, `/plays`, `/drives`, `/talent`, `/player/returning`, `/recruiting/teams`, `/ratings/sp|fpi|elo`); › Lake layout (`staging/team_games.parquet`, `staging/plays/season=YYYY/…`); › Data quality checks ("every FBS game has advanced stats").
- Model: `docs/04-model.md` § 9.2 (preseason inputs use values published before that season; SP+, FPI and Elo count as baselines only if published before the game, otherwise they're labeled "hindsight benchmark"); § 2 Rung 2 (off/def efficiency with rush/pass splits, success rate, explosiveness: the columns TASK-019 reads).
- Decisions: D-027, D-042.
- **Decide at the plan gate:** which advanced-stats variant is pulled and staged (garbage time excluded, included, or both) and how the choice is recorded; how a benchmark row records when its value was published (a pre-game weekly value or season-final), so M3.4 can tell the two apart; play/drive partitioning by season; how many calls recording one fixture per endpoint costs (a handful, counted by the budget tracker).
- *From TASK-017 (PR #60):* `engine.transform` keeps a `TABLES` registry and `engine.transform.quality` a `CHECKS` registry: register the new staged tables and the advanced-stats check there. Raw files are read through the `Lake` protocol into pyarrow and registered in DuckDB in memory (no `httpfs`, D-112), so a full backfill of plays may need staging one season at a time.
- *From TASK-017 (PR #61):* staging skips a raw file whose `params` don't match its key and lists it in `staging/skipped_raw.parquet` (D-116). The local lake's `plays/season=2025/week=01/fetched_at=2025-09-02T120000Z.parquet` was pulled with a `team=Ohio State` filter, so it'll be skipped. DuckDB needs `pytz` to return a `TIMESTAMPTZ` to Python through `fetchall()`; read results through Arrow instead (as `rebuild` does) or add the dependency.

## Acceptance criteria

- [ ] AC-1: Given the lake fixture extended with one recorded response per endpoint, `engine transform --rebuild` writes staging tables for team box scores, team-game advanced stats, plays, drives, talent, returning production, recruiting and benchmark ratings. Each table's row count equals its raw fixture's record count after dedupe (one assertion per table).
- [ ] AC-2: Staged advanced stats have exactly one row per (game, team) and record whether garbage time was excluded. A raw pull that repeats a (game, team) keeps the newest pull's values.
- [ ] AC-3: Given a fixture FBS final game with no advanced-stats row, the data-quality run exits non-zero and names that game's `source_id`; with the row present it exits 0.
- [ ] AC-4: Every staged benchmark-rating row says whether its value was published before a given week or is season-final. Given a season-final SP+ fixture, every row is marked season-final.
- [ ] AC-5: The rebuild still makes zero API calls (TASK-017's no-network test covers the new tables).

## Out of scope

- Point-in-time feature tables (TASK-019).
- Computing our own EPA from plays (`/ppa/predicted`), and any use of the benchmarks (M3.4).
- Building priors from talent, returning production and recruiting (M4.2).
- Backfilling these endpoints (TASK-021).

## Files likely touched

- `python/engine/src/engine/transform/stats.py`: staging SQL for the stats and preseason endpoints (new).
- `python/engine/src/engine/transform/__init__.py`: register the new tables with the runner.
- `python/engine/src/engine/transform/quality.py`: the advanced-stats check.
- `python/engine/tests/test_transform_stats.py` (new); `python/engine/tests/fixtures/lake/`: one recorded response per endpoint.

## Verification

- Automated: `test_transform_stats.py` (AC-1, AC-2, AC-4), `test_quality.py` (AC-3), `test_transform.py` (AC-5).
- Manual: record one week of each week-level endpoint into the local lake (calls shown by the ledger), run `engine transform --rebuild` → each staged table is non-empty and the DQ report exits 0.

## Follow-ups

_Work noticed during this task and deliberately left out. Each bullet ends `→ <path> § <section>` (where it was placed) or `→ not tracked: <reason>`. See `.claude/skills/track-follow-ups/classify.md`; the PR's Follow-ups section is copied from here._

- Staged advanced-stats column names (`off_*`/`def_*`, rush/pass splits), `garbage_time_excluded`, and plays/drives partitioned by season for TASK-019's features → docs/tasks/TASK-019-point-in-time-features.md § Context (approved at plan)
- M3.4: benchmark rows carry `season_final`/`known_at`. Backfilled SP+/FPI are season-final (hindsight only). A weekly `/ratings/elo?week=` pull would give pre-game values, but the registry pulls Elo per season → docs/08-tasklist.md § M3.4 (approved at plan)
- M4.2: CFBD's talent, returning production and recruiting carry no publication date, and backfilled pulls are fetched after the season, so "published before the season" has to be assumed per source → docs/08-tasklist.md § M4.2 (approved at plan)

## Plan

**Gate decisions** (recommended)
- A. **Garbage time:** pull only the excluded variant. `stats_game_advanced` gets `fixed={"excludeGarbageTime": "true"}` in `ENDPOINTS` (no raw stats files exist yet, so nothing is skipped). The staged `garbage_time_excluded` comes from each raw file's `params`, so a later "included" endpoint would be a second registry entry, not a second row per (game, team).
- B. **Box scores:** `team_games` has one row per (game, team): `game_source_id`, `team_source_id`, `home_away`, `points`, and `stats` (JSON text of category→stat as CFBD sends it, e.g. `"20-31"`). Typed columns wait for the first reader.
- C. **Benchmarks:** one table, `benchmark_ratings`, with one row per (system `sp|fpi|elo`, season, team, `fetched_at`). Every pull is kept, as with lines. `season_final` is true when `fetched_at` ≥ the season's last staged `calendar.end_at`, false before it, and NULL when the season has no calendar. `known_at` is `fetched_at` when not season-final, else NULL. M3.4 uses only rows with `known_at` < kickoff.
- D. **Plays/drives:** `staging/{plays,drives}/season=YYYY/data.parquet`, from a new `SEASON_TABLES` registry built and written one season at a time after `TABLES`. `quality.run` doesn't load them.
- E. **Fixture cost:** 10 counted calls into the local `./data` lake: `games_teams`, `stats_game_advanced`, `plays`, `drives` for 2025 week 1, plus `talent`, `player_returning`, `recruiting_teams`, `ratings_sp|fpi|elo` for 2025. They're trimmed to the 5 fixture games and 10 fixture teams (plays and drives to 2 games).
- F. **`advanced_stats` check:** a final game's FBS side with no (game, team) row fails when the game is in `BACKTEST_SEASONS`, or when a non-empty stats pull fetched after kickoff covers its week. Otherwise it's listed as a note, so the live season's lines job isn't blocked before `results` runs.

**Steps**
1. Record and trim the 10 responses (a scratch script, not committed) into `fixtures/lake.json`. Confirm field names from them, including SP+'s `nationalAverages` row (dropped if present).
2. `staging.py`: `load_raw(lake, endpoint, season=None)` and `Staging.raw(endpoint, season=None)` walk one season's prefix.
3. `transform/stats.py` (new) holds the builders:
   - `team_games`, `team_game_advanced` (offense and defense: plays, ppa, success_rate, explosiveness, plus rush and pass ppa/success/explosiveness, plus power_success, stuff_rate, line_yards; newest pull per (game, team));
   - `talent`, `returning_production`, `recruiting`, `benchmark_ratings`;
   - `plays(s, season)` and `drives(s, season)`.
   - Name-keyed records resolve `team_source_id`: advanced stats by the game's home/away names in `latest_games`, season endpoints by staged `teams.school`. An unmatched name stays NULL.
4. `transform/__init__.py`: register the six tables before `skipped_raw`. Add `SEASON_TABLES` and season discovery from `raw/cfbd/{plays,drives}/season=*`. `rebuild` returns the totals under `plays` and `drives`.
5. `quality.py`: add the `advanced_stats` check (F).
6. `endpoints.py`: the fixed param (A).
7. `tests/conftest.py` (new): move `lake`, `write` and `engine` out of `test_transform.py`.
8. Docs: `03-data-model.md` › Lake layout gets the staged-table rows, and › Data quality checks gets the check. `decisions.md` gets one new D-### for A–F.

**Files** (12): `transform/stats.py` (new), `transform/__init__.py`, `transform/quality.py`, `transform/staging.py`, `ingest/endpoints.py`, `tests/conftest.py` (new), `tests/test_transform_stats.py` (new), `tests/test_transform.py`, `tests/fixtures/lake.json` (the fixture is one JSON file, not `fixtures/lake/`), `tests/test_cfbd_client.py` (the registry row, if it checks `fixed`), `docs/03-data-model.md`, `docs/decisions.md`.

**Test strategy**
- AC-1 `test_each_staged_table_matches_its_raw_record_count`: one assertion per table. `team_games` = 2 × records; benchmarks = the sum of the 3 systems minus any `nationalAverages` row; plays and drives are read from `season=2025`.
- AC-2 `test_advanced_stats_one_row_per_game_team_newest_wins`: a newer pull repeats one (game, team) with a changed `off_ppa`. One row remains, with the new value, and `garbage_time_excluded` is true on every row.
- AC-3 `test_advanced_stats_check_names_missing_game` (parametrized, row present or removed): exit 1 and the `source_id` under `FAIL advanced_stats`, or exit 0.
- AC-4 `test_season_final_sp_marked`: every row is `season_final`, with `known_at` NULL. A 2025-10-01 pull gives `season_final` false and `known_at` = `fetched_at`.
- AC-5: `test_rebuild_stages_every_table_with_no_api_calls` asserts the new counts and keys. `test_check_passes_on_clean_fixture` expects 5 passed. `test_marked_missing_line_passes` adds a stats row for its week-2 game.

**Risks / open questions**
- CFBD omits advanced stats for some old games, so TASK-021's full-lake check may list failures (its AC-3 allows that, with causes).
- Name matching: a school spelled differently in `/talent` or SP+ stays unmatched (NULL), and a note counts them.

**Size check:** 12 files, no schema, no UI: passes (limit 20).

## Review log

_Filled by /implement-task. One line per round._

## Blocked

_Only if status is Blocked: what failed, what was tried, best hypothesis, decision needed._

## Metrics

- Verify rounds:
- Review rounds:
- First-pass AC FAILs:
- Plan revisions after approval:
