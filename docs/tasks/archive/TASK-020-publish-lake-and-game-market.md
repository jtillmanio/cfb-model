---
id: TASK-020
title: Publish reference data, games and line snapshots to Postgres, with the game_market view
status: Done
depends_on: [TASK-016, TASK-017]
size: M
model: opus
autonomy: attended
ui: false
plan_status: approved
planned_at_commit: 57badb4
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
- *From TASK-017 (PR #61):* map staged columns by meaning, not by name. Staged `team_seasons.classification` (fbs/fcs) is Postgres `team_seasons.division` (the API filters `ts.division = 'fbs'`; `map_games` puts classification there too), and `cfbd_division` (East/West) has no Postgres column. Staged `venues.elevation` is CFBD's value: confirm its unit before writing `venues.elevation_m`. A venue filled in from `/games` can have a NULL `name`, while `venues.name` is NOT NULL. `games.closing_line_missing` is a staging-only flag for the check, never a `games` column (hard rule 1). A game that drops out of a newer `/games` pull (e.g. cancelled) keeps its older staged record.

## Acceptance criteria

- [x] AC-1: Publishing the staged lake fixture into the test DB twice leaves the IDs and row counts of `teams`, `venues`, `games`, `seasons`, `sportsbooks` and `line_snapshots` unchanged.
- [x] AC-2: Given staged data that fails a data-quality check, `engine publish` exits non-zero before writing anything, and every table's row count is unchanged.
- [x] AC-3: Given a game with consensus snapshots on Sun, Tue, Thu and Sat before kickoff, plus one captured after kickoff, `game_market` returns opening = Sun's spread, closing = Sat's, and current = the newest snapshot.
- [x] AC-4: Given a game with `kickoff_at` NULL, its closing line is the last snapshot before the end of `game_date` in Eastern time. Given a game with no consensus line but three providers, the view returns their median and marks it as a median.
- [x] AC-5: On the seeded test DB, `game_market` for Texas @ Oklahoma returns opening `spread_home` +7 and current +6.5, and Furman @ Clemson returns NULL lines.
- [x] AC-6: `EXPLAIN` of `SELECT * FROM game_market WHERE game_id = :id` on the seeded test DB shows no sequential scan of `line_snapshots`.

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

- `game_market` closing prefers CFBD's untimed `closing` row over the last snapshot, and is NULL until the cutoff (gate B). This amends 03 › Views and D-037's "closing = last snapshot before kickoff" → docs/03-data-model.md § Views (approved at plan)
- Backtest point-in-time: lines are targets and pick-time inputs, never features. Untimed `opening` rows count as before kickoff, and `closing` is a target only (gate F) → docs/08-tasklist.md § M3.2 (approved at plan)
- `team_seasons.talent` and `returning_ppa_pct` stay NULL: TASK-018 stages them in the lake, and publishing them waits for the priors → docs/08-tasklist.md § M4.2 (approved at plan)
- The jobs publish with `engine.publish.staging.publish_lake(lake, conn)`, which refuses on a failed check. `seasons.current_week` is set at each publish, so the daily `lines` run keeps it current → not tracked: already in TASK-022's approved plan (step 3: `publish_lake` after the check), and `current_week` is this task's gate E
- Candidate decision: how the lake is published, which kind each pull becomes, what `game_market` returns, how `current_week` is set (gates A–G), with `games.updated_at` meaning "last published" → docs/decisions.md § D-120 (amends D-037)
- Schema review R1: an untimed `opening`/`closing` row is the first pull's, even if a later pull has a spread it lacked; a game rescheduled after its close was stored keeps that close; `numeric(4,1)` would round a price finer than tenths. None occurs in the lake today (4 post-cutoff rows lack a spread, each one book among several, which the median skips) → docs/decisions.md § D-120 (Revisit if)
- `*_source` names the spread's source only; a total can be a median while `*_source` says `consensus` → not tracked: documented in docs/03-data-model.md § Views and D-120; no screen reads totals until M5, which reads that row

## Plan

**Gate decisions** (recommended)
- A. **Which kind each staged line pull becomes** (D-115). "Cutoff" means `kickoff_at`, or the end of `game_date` in Eastern time when the kickoff is TBA.
  - A pull before the cutoff is a `snapshot` at `fetched_at`.
  - A pull at or after the cutoff is one untimed `closing` row; the key keeps the first.
  - A non-NULL `spread_home_open` or `total_open` is one untimed `opening` row.
  - A row with no spread, total or moneyline is skipped.
- B. **`game_market` columns, one row per game:**
  - **Opening** comes from the `opening` rows, else the earliest snapshot.
  - **Current** is the newest snapshot, else the closing row, else the opening.
  - **Closing** is the `closing` row (CFBD's close, quoted nearer kickoff than our last daily snapshot), else the last snapshot before the cutoff. It's NULL until the cutoff has passed (`now()`), so a future game never shows a "closing" line.
  - This amends 03 › Views and D-037: needs approval (Follow-ups).
- C. **Source:** each of opening, current and closing uses the `consensus` book when it quoted that price, else the median (`percentile_cont(0.5)`) across books for the same kind and `captured_at`. `opening_source`, `current_source` and `closing_source` say `consensus` or `median`, and `closing_from` says `cfbd_close` or `last_snapshot`.
- D. **Totals:** exposed (`*_total`), from the same rows.
- E. **`seasons.current_week`:** each publish sets it from the clock and the staged calendar: the regular week containing `now()`, else NULL. The daily `lines` job keeps it within a day.
- F. **Untimed rows and point-in-time:** lines are never rating features (04 § 9.2), so the feature checks never read them. An untimed open is before kickoff by definition, and closing is a target (Follow-ups, M3.2).
- G. **Venues:** CFBD's `elevation` is meters (the fixture: Fresno 102.6, Ames 274.9), so it maps straight to `elevation_m`. A venue with a NULL `name` isn't published, and its games get `venue_id` NULL (counted). A team color that isn't `#RRGGBB` becomes NULL.

**Steps**
1. `publish/reference.py`: chunk every multi-row statement at 1,000 rows (`upsert_games` has 15 columns, under 65,535 binds). `RETURNING (xmax = 0)` counts new rows. Venues take every column.
2. `publish/lines.py` (new): `map_lines(lines, games)` implements rule A, plus `publish_lines(conn, …)` for sportsbooks and snapshots.
3. `publish/staging.py` (new): `publish_lake(lake, conn, source="cfbd") -> dict[str, int]`.
   - It calls `quality.run(lake)` first and raises `DataQualityFailed` when the report isn't ok.
   - It then reads the staged parquet and upserts teams, team_seasons (`classification` → `division`), venues, seasons (from `calendar`), games and lines in the caller's one transaction.
4. `cli.py`: `engine publish --target dev|test` uses `direct_url`. It exits 1 with the report on a failed check (before any connection) and prints new rows per table.
5. `python/db/views/010_game_market.sql`: `CREATE OR REPLACE VIEW game_market` as `games g` with a `LEFT JOIN LATERAL` per line, each lateral filtered `ls.game_id = g.id` (the `(game_id, captured_at)` index).
6. `python/db/views/README.md`: drop "Empty until…".
7. Docs: `03-data-model.md` › Views and the `line_snapshots` note (A–C); `decisions.md`: one D-### for A–G.

**Files** (12): `publish/reference.py`, `publish/lines.py` (new), `publish/staging.py` (new), `cli.py`, `db/views/010_game_market.sql` (new), `db/views/README.md`, `engine/tests/test_publish_staging.py` (new), `engine/tests/test_publish_reference.py`, `db/tests/test_game_market.py` (new), `docs/03-data-model.md`, `docs/decisions.md`, and `engine/tests/conftest.py` only if TASK-018 hasn't already moved the `lake` fixture there.

**Test strategy** (`db_conn`, rolled back; lines use `source='cfbd'`, which the CHECK allows, on the test DB only)
- AC-1 `test_publish_twice_keeps_ids_and_counts`: rebuild the fixture lake, `publish_lake` twice, then compare ids and counts for the 6 tables. The second run's new-row counts are all 0. Also `test_insert_line_snapshots_twice_inserts_nothing` and `test_upsert_games_chunks_past_bind_limit` (5,000 rows).
- AC-2 `test_failed_check_publishes_nothing`: inject a final game with no score and rebuild. `engine publish --target test` exits 1, and the counts of all 6 tables are unchanged.
- AC-3 `test_closing_is_last_snapshot_before_kickoff`: Sun/Tue/Thu/Sat snapshots plus one after kickoff. Also `test_closing_null_before_kickoff` (kickoff in 2099).
- AC-4 `test_tba_closing_uses_end_of_eastern_date`, `test_median_without_consensus`: 3 books, `closing_source = 'median'`.
- AC-5 `test_seeded_texas_oklahoma_and_furman`: +7 and +6.5; Furman's lines all NULL.
- AC-6 `test_single_game_read_uses_index`: `SET LOCAL enable_seqscan = off`, then `EXPLAIN` has no `Seq Scan on line_snapshots`.

**Risks / open questions**
- `now()` makes `closing` time-dependent. The tests use past or 2099 kickoffs, never today.
- B prefers CFBD's close. If its post-kickoff `spread` isn't the pre-game close, `closing_from` lets M3.4 tell the two apart.
- A full dev publish of 12 seasons (~50k games, ~500k lines) runs in one transaction on the unpooled URL. Watch the run time in TASK-021.

**Size check:** 11–12 files, a view but no table or column change, no UI: passes (limit 20).

## Review log

_Filled by /implement-task. One line per round._

- Preflight: plan stale by file (03, decisions, conftest changed in #62–#64); owner confirmed carry on
- Verify R1 PASS | Audit R1 PASS (1 non-discriminating extra test, strengthened) | Spec R1 CHANGES (04 § 9.3 stale) → R2 APPROVE | Schema R1 APPROVE (6 MINOR: 2 fixed, 3 recorded in D-120, 1 documented) | Verify R2 (after review fixes) PASS

## Blocked

_Only if status is Blocked: what failed, what was tried, best hypothesis, decision needed._

## Metrics

- Verify rounds: 1 (re-run once after review fixes)
- Review rounds: 2
- First-pass AC FAILs: 0
- Plan revisions after approval: 0
