---
id: TASK-017
title: Stage games, teams, venues, calendar and lines with transform --rebuild and data-quality checks
status: In progress
depends_on: [TASK-015]
size: M
model: opus
autonomy: attended
ui: false
plan_status: approved
planned_at_commit: 40debbf
---

# TASK-017 — Stage games, teams, venues, calendar and lines with transform --rebuild and data-quality checks

## Goal

`engine transform --rebuild` recreates the staged games, teams, venues, calendar and lines tables from the raw lake alone, with no API calls. The data-quality checks report every problem and stop anything downstream from publishing bad data.

## Context

- Task list: `docs/08-tasklist.md` › M2 › M2.3, first half. **Split from M2.3** under `workflow.splitPolicy: split`: one task for every staged table plus the checks would touch far more than 8 files. This half stages what TASK-020 publishes; TASK-018 stages the stats and preseason tables on the same runner.
- Data model: `docs/03-data-model.md` › Lake layout (`staging/` = cleaned, typed, deduped, "latest version" of each entity; DuckDB builds it from `raw/`); › Data quality checks.
- Architecture: `docs/02-architecture.md` › Components › 1 (`transform`); › Non-functional requirements › Data correctness (publishing stops when a check fails; nothing partial reaches Postgres); › Testing strategy › Levels › Data / ETL (`transform --rebuild` with zero API calls, on a small lake fixture of recorded responses).
- Model: `docs/04-model.md` § 9.3 (closing line: the `consensus` provider's spread when present, otherwise the median across providers). Staging keeps every provider's row; choosing between them happens in `game_market` (TASK-020) and the backtest.
- Decisions: D-027 (rebuild from raw with zero API calls), D-002, D-098 (raw `/games` JSON already in the lake).
- Rules: `.claude/rules/python.md` (destructive commands such as `--rebuild` check `LIVE` and refuse).
- **Roadmap note to resolve:** Phase 0's item "`python/db/views/` applied after every migration" says "rebuild pending, with `transform --rebuild` in M2.3". `transform` writes only to the lake. If this task doesn't touch Postgres, the plan says where a dev-DB rebuild (and its view re-apply) will land and updates that note. *Direction agreed with the owner (2026-10-15):* `transform --rebuild` stays lake-only. The roadmap note is reworded to say the database half lands with a dev-DB rebuild command when one is first needed, and that is recorded as a follow-up.
- **Decide at the plan gate:** how "latest version" is picked when one entity appears in several raw pulls (the newest `fetched_at` wins); whether lines stage every pull (each is a snapshot) or only the newest; the staging file layout; DuckDB as an `engine[train]` dependency (D-004); and how the DQ report is shown (CLI output and an exit code).
- *From TASK-015 (PR #54):* CFBD's `/lines` takes no `classification`, so a week's raw lines include games with no FBS team (2025 week 1 has Colgate–Monmouth, with one provider and null opening lines and moneylines). Staging lines should keep only games present in staged `/games`, or count the extras in a data-quality check.

## Acceptance criteria

- [ ] AC-1: Given the lake fixture of recorded responses, `engine transform --rebuild` writes `staging/` tables for games, teams, venues, calendar and lines. Running it twice gives identical rows. A test that makes any CFBD client or HTTP transport raise when constructed still passes, so the rebuild makes zero API calls.
- [ ] AC-2: Given two raw pulls of the same game (an earlier one scheduled, a later one final), staged games hold one row for that game, with the final score from the later pull.
- [ ] AC-3: With `LIVE=true`, `engine transform --rebuild` exits non-zero with a message naming `LIVE`, and `staging/` is unchanged.
- [ ] AC-4: Given a fixture final game with no score, or two games with the same teams on the same date, the data-quality run exits non-zero and names each offending game's `source_id`. On the clean fixture it exits 0.
- [ ] AC-5: Given an FBS-vs-FBS game in a 2014–2025 season with no line from any provider, staging marks it as missing a closing line, the DQ report lists it, and the check passes. An unmarked game with no line fails the check.

## Out of scope

- Staging box scores, advanced stats, plays, drives, talent, returning production, recruiting and benchmark ratings, and the "every FBS game has advanced stats" check (TASK-018).
- Feature tables (TASK-019).
- Publishing to Postgres (TASK-020).
- The team-mapping check for non-CFBD names (Splash): it applies once contest pastes are stored (M6).

## Files likely touched

- `python/engine/src/engine/transform/__init__.py`, `python/engine/src/engine/transform/staging.py`: the runner and the staging SQL (new).
- `python/engine/src/engine/transform/quality.py`: the data-quality checks (new).
- `python/engine/src/engine/cli.py`: `engine transform --rebuild` and `engine check`.
- `python/engine/pyproject.toml`: DuckDB in the heavy extra.
- `python/engine/tests/test_transform.py`, `python/engine/tests/test_quality.py` (new); `python/engine/tests/fixtures/lake/`: recorded responses.
- `docs/06-roadmap.md` › Phase 0: the views/rebuild note (a follow-up placement, if the plan changes where it lands).

## Verification

- Automated: `test_transform.py` (AC-1 to AC-3), `test_quality.py` (AC-4, AC-5).
- Manual: on the local lake from D-098, `uv --directory python run engine transform --rebuild` → staged games match the raw `/games` files' game count, and the DQ report prints with exit 0.

## Follow-ups

_Work noticed during this task and deliberately left out. Each bullet ends `→ <path> § <section>` (where it was placed) or `→ not tracked: <reason>`. See `.claude/skills/track-follow-ups/classify.md`; the PR's Follow-ups section is copied from here._

Found while planning (approved at plan, placed on `docs/plans-2026-10-19`):
- The roadmap's Phase 0 views/rebuild note already says `transform --rebuild` is lake-only and the dev-DB rebuild lands when first needed (PR #53), so this task changes nothing there → not tracked: already in docs/06-roadmap.md › Phase 0
- TASK-020: staged lines are one row per (game, provider, `fetched_at`) with `spread_home_open`; publish chooses which pulls become `opening`/`closing`/`snapshot` rows (D-115), and calls `engine.transform.quality.run(lake)` and refuses when `not report.ok` (its AC-2) → docs/tasks/TASK-020-publish-lake-and-game-market.md § Context (approved at plan)
- TASK-018: register tables in `engine.transform.TABLES` and the advanced-stats check in `quality.CHECKS`; raw is loaded into memory through the `Lake` protocol (no `httpfs`), so a full backfill of plays may need staging one season at a time → docs/tasks/TASK-018-stage-stats-and-preseason-data.md § Context (approved at plan)
- TASK-021: the `closing_line` check passes only for games covered by a `/lines` pull fetched after kickoff, so the backfill should pull `/lines` per season after it ends → docs/tasks/TASK-021-backfill-and-notebook-1.md § Context (approved at plan)

## Plan

**Plan-gate decisions** (recorded as a new D-### in `docs/decisions.md`; 03 › Lake layout gets the staged tables)
- **Latest version:** per entity id, the record from the newest `fetched_at` across every raw file of that endpoint (week and season files alike); ties break on the raw key, then `row`. Only `*.parquet` keys with `fetched_at=` are read, so D-098's JSON files stay unread (D-112).
- **Lines stage every pull:** one row per (game, provider, `fetched_at`), with `spread_home`, `spread_home_open`, `total`, `total_open`, `ml_home`, `ml_away`. TASK-020 decides how a pull becomes `opening`/`closing`/`snapshot` rows (D-115). Line rows for games not in staged games (no FBS team) are dropped, and `transform` prints how many.
- **Closing-line mark (AC-5):** staged games get `closing_line_missing`: `false` if any `/lines` pull fetched after the game's `startDate` has a non-null spread; `true` if such a pull covers the game's season/week/season type (from its key) but quotes no spread; NULL if no post-kickoff pull covers it. The check fails on NULL for completed FBS-vs-FBS games in 2014–2025 (04 § 9.1) and lists the `true` ones. So "unmarked" means lines were never pulled after kickoff, which keeps the check from passing by definition.
- **Layout:** single files `staging/{games,teams,team_seasons,venues,calendar,lines}.parquet`. Teams, team seasons and venues come from the newest `/teams`, `/venues` pulls, filled in from `/games` for ids those don't have (the local lake has no `/teams` pull yet).
- **DuckDB** joins `engine[train]` (D-004, D-114: dev group, never the API). Raw bytes come through the `Lake` protocol into pyarrow and are registered in DuckDB in memory, so R2 works without `httpfs` (D-112). The connection sets `autoinstall_known_extensions=false`, so a missing `json`/`icu` extension fails instead of downloading.
- **DQ report:** `engine transform --rebuild` stages and then runs the checks; `engine check` runs them on the existing `staging/`. Each prints a report (failures with every offending `source_id`, then notes) and exits 1 on any failure, 0 otherwise. A LIVE refusal or usage error exits 2.

**Steps**
1. `uv add --package cfb-engine --optional train duckdb`. In a scratch script, confirm `json_extract_string` and `AT TIME ZONE 'America/New_York'` run with autoinstall off and no network.
2. `ingest/lake.py`: `Lake.walk(prefix)` (every key below it, recursive, sorted) and `Lake.replace(key, data)` (atomic overwrite; refuses `raw/` keys) on `LocalLake` and `S3Lake`. Update the docstring: staging is derived, so it's overwritten.
3. `transform/__init__.py`: `TABLES` registry (TASK-018/019 append) and `rebuild(lake) -> dict[str, int]`: `refuse_if_live("rebuild staging")` first, then build every table in memory before any `replace` (ordered by key, so reruns give identical rows).
4. `transform/staging.py`: `load_raw(lake, endpoint)` → a pyarrow table (`key`, `season`, `week`, `season_type` parsed from the key, `fetched_at`, `row`, `record`), plus one SQL builder per table. Games mirror `GameRow` (Eastern `game_date`, `kickoff_at` NULL when TBD, `status`) plus home/away classification, `fetched_at` and `closing_line_missing`. A final game with no score is staged as-is, so the check can report it (`map_games` would raise).
5. `transform/quality.py`: `Report` (`failures`, `notes`, `ok`, `render()`), the `CHECKS` registry and `run(lake)`. Checks: `final_has_score`, `no_duplicate_games` (same unordered team pair and `game_date`), `closing_line`. TASK-020's publish calls `run`.
6. `cli.py`: `transform --rebuild` (`--rebuild` required for now) and `check`. `load_env()` runs before the LIVE check.
7. Docs: 03 › Lake layout (staged tables and columns), the D-### above (it also amends D-112's "only the ledger is overwritten").

**Files** (12): `python/engine/pyproject.toml`, `python/uv.lock` (by uv), `python/engine/src/engine/ingest/lake.py`, `python/engine/src/engine/transform/__init__.py`, `…/transform/staging.py`, `…/transform/quality.py` (new), `python/engine/src/engine/cli.py`, `python/engine/tests/fixtures/lake.json` (new: raw key → records), `python/engine/tests/test_transform.py` (new), `python/engine/tests/test_lake.py`, `docs/03-data-model.md`, `docs/decisions.md`. The quality tests go in `test_transform.py`, not a separate `test_quality.py`, to stay at 12 files.

**Test strategy** (`test_transform.py` writes `lake.json` into a `tmp_path` `LocalLake` with `encode_raw`; CLI runs through `cli.main` with `load_env` patched out)
- AC-1: `test_rebuild_stages_every_table_with_no_api_calls`. `CfbdClient.__init__`, `httpx.Client.__init__` and `httpx.HTTPTransport.__init__` are patched to raise. It asserts the six tables' row counts, identical rows on a second run, the non-FBS line row dropped, and staged games matching `map_games` on the clean records.
- AC-2: `test_newest_pull_wins` (week-1 game scheduled in the earlier pull, final in the later one: one row, the later score).
- AC-3: `test_rebuild_refuses_under_live` (a sentinel `staging/games.parquet` is byte-identical afterwards; exit code 2; stderr names `LIVE`).
- AC-4: `test_check_names_bad_games[final_no_score|duplicate]` (exit 1, each `source_id` in the output) and `test_check_passes_on_clean_fixture` (exit 0).
- AC-5: `test_marked_missing_line_passes` (a post-kickoff week-2 pull without game X: `closing_line_missing` true, X listed in the notes, exit 0) and `test_unmarked_missing_line_fails` (game Y's week has only a pre-kickoff pull: exit 1 naming Y).
- `test_lake.py`: `walk` and `replace` on local and moto S3; `replace` refuses a `raw/` key.

**Risks / open questions**
- **Fixture recording costs 3 CFBD calls** (`engine ingest teams|venues|calendar --season 2025` into the local lake), trimmed by hand into `lake.json`. Games and lines are trimmed from the lake's existing files. If you'd rather not spend the calls, the fixture is hand-written from CFBD's v2 schema instead.
- If the DuckDB wheel doesn't bundle `json`/`icu`, step 1 catches it. The fallback is to decode JSON with pyarrow and convert to Eastern time in Python.
- The raw lake is loaded into memory. That's fine for these tables; TASK-018's plays may need one season at a time (follow-up 2).
- A crash between `replace` calls can leave staging mixed. That's acceptable: staging is rebuilt, and publish re-runs the checks.

**Plan revision 1 (2026-10-19, agreed with the owner):** a raw file whose `params` disagree with its key (`year` ≠ `season=`, `week` ≠ `week=`, `seasonType` ≠ the key's season type) is skipped by every staged table, so it neither adds rows nor counts as `/lines` coverage, and the DQ report lists each skipped key as a note (`raw_files`). The keys persist in a seventh staged table, `staging/skipped_raw.parquet` (`key`, `reason`), so `engine check` can report them without reading raw. The local lake has one: `lines/season=2025/week=01/fetched_at=2025-09-02T120000Z.parquet` holds 2019 lines, pulled through `--param year=2019` before D-114. Test: `test_mismatched_raw_file_is_skipped`.

**Size check:** 12 files, data layer plus its docs, no schema or UI: M, passes.

## Review log

_Filled by /implement-task. One line per round._

## Blocked

_Only if status is Blocked: what failed, what was tried, best hypothesis, decision needed._

## Metrics

- Verify rounds:
- Review rounds:
- First-pass AC FAILs:
- Plan revisions after approval:
