---
id: TASK-069
title: Ingest the NFL schedule, scores and closing lines from nflverse
status: In progress
depends_on: [TASK-020]
size: M
model: opus
autonomy: attended
ui: false
plan_status: approved
planned_at_commit: afcfc9a
---

# TASK-069 — Ingest the NFL schedule, scores and closing lines from nflverse

## Goal

The NFL games on a Splash slate exist in the app with their kickoff, score and market line, so the contest can match, show and grade them before any NFL model exists.

## Context

- Task list: `docs/08-tasklist.md` › M6 › M6.3. Built first in M6: TASK-067's fixture (the BUF −3 entry) needs NFL games, and TASK-070's import needs NFL teams to match.
- Data model: `docs/03-data-model.md` › Data sources › NFL schedules and scores (into `games` under `sport_id = 'nfl'`), › Conventions (upsert by `(source, source_id)`, aliases), › Games & market (`games`, `line_snapshots`, `sportsbooks`), › Views (`game_market`).
- Architecture: `docs/02-architecture.md` › Components › 1, › Jobs (`lines`), › Testing strategy › Seed data (Teams and venues: "the NFL teams on the contest slate"; Week 6 games: "The 5 NFL games from §3").
- Decisions: D-030 (stable IDs), D-036 (aliases), D-039 (nflverse into `games`), D-115 and D-120 (how a pull becomes a `snapshot` or the untimed `closing` row), D-123 (the `lines` job's entry point and summary), D-089 (fixture rows only in the test DB).
- **Source:** nflverse's schedule file (`nfldata`'s `games.csv`: one row per game with `game_id`, `season`, `game_type`, `week`, `gameday`, `gametime` in Eastern, `away_team`, `home_team`, scores, `spread_line`, `stadium`, `roof`). It's a free download outside CFBD's call budget. The raw lake stays append-only: each pull is a new file, never an overwrite.
- **Sign convention:** CLAUDE.md's `spread_home` is negative when home is favored, and nflverse's `spread_line` is positive when home is favored, so `spread_home = −spread_line`. The plan confirms this against a known game in the recorded file, because a flipped sign would silently flip every NFL row. CLAUDE.md asks you to stop before changing how a stored line is interpreted; this is a new source, so the plan gate is where the owner confirms it.
- **Schema change, stop and ask at the plan gate:** the `nfl` row in `sports` (seeded by migration, as 0001 seeds `cfb`) and `line_snapshots.source`'s CHECK (`cfbd|oddsapi|manual|fixture`), which refuses an `nflverse` line. The plan names the source value and the sportsbook row.
- **Weeks:** `game_type` `REG` is `regular`, and `WC`, `DIV`, `CON` and `SB` are `postseason`. NFL week numbers aren't CFB's, so contests key their weeks by the contest's own period (TASK-067), never by `games.week`.
- **Count:** sample-data § 3 lists 4 NFL games (Buffalo @ NY Jets, NY Giants @ Philadelphia, Kansas City @ Baltimore, Houston @ Jacksonville), and so does `design/handoff/designs/contest-data.js`. 02's "The 5 NFL games" is wrong; fix it in this PR.
- *From TASK-016 (PR #52):* the fixture still lacks the 5 NFL games (sample-data §3) and the `nfl` sports row; this task adds them.
- **This Week stays CFB:** `/slate` and the shell count CFB games and picks. NFL rows in `games` must not change the seeded "54 games · 9 picks".

## Acceptance criteria

- [ ] AC-1: Given a recorded nflverse schedule file in the engine's test fixtures (no network), the ingest saves it as a new raw-lake file under `raw/nflverse/`. A second pull adds a second file and never overwrites the first. `transform --rebuild` stages every 2026 game from the raw files with zero network calls.
- [ ] AC-2: Publishing upserts NFL teams and games by `(sport_id 'nfl', source, source_id)`. In the recorded file, a 2026 `REG` week-6 game lands with `season_type` `regular`, week 6, `kickoff_at` equal to its `gameday` + `gametime` Eastern in UTC, and status `final` with both scores when scored, else `scheduled`. Publishing again inserts nothing and changes no ID, and no `cfb` row changes.
- [ ] AC-3: A pull quoting `spread_line` 4.5 stores `spread_home` −4.5. A pull before kickoff is a `snapshot` at its fetch time, and the first pull at or after kickoff is the untimed `closing` row (D-120's rule). `game_market` then gives the NFL game an opening, current and closing spread, as it does a CFB game.
- [ ] AC-4: The daily `lines` job (or a job the plan names) also pulls and publishes the current NFL season, and its summary reports NFL games and line rows added. A failed nflverse download doesn't stop the CFB publish and makes the run fail visibly, with a non-zero exit and a summary line naming it.
- [ ] AC-5: The seeded test DB has the `nfl` sport, the 8 NFL teams and the 4 Week 6 NFL games from sample-data § 3, with their Sunday kickoffs (Sun 2026-10-11 1:00, 1:00, 4:25 and 8:20 PM ET) and market lines (BUF −4.5, HOU −1.5, BAL −2.5, PHI −7). On the seeded DB, `game_market`'s current `spread_home` for Buffalo @ NY Jets is +4.5. `/api/py/slate` still returns 54 games, and the shell still returns 9 picks.
- [ ] AC-6: The migration runs up → down → up on the test DB, and `pnpm db:check` passes.

## Out of scope

- An NFL model or NFL predictions (Phase 8).
- Live NFL scores during games (TASK-074, the `scores` job).
- `splash` aliases for NFL teams and the paste import (TASK-070).
- Showing NFL games on This Week, Rankings or Teams.
- The contest tables (TASK-067).
- Other nflverse datasets (play-by-play, rosters, injuries).

## Files likely touched

- `python/engine/src/engine/ingest/nflverse.py`: new. Downloads the schedule into the raw lake
- `python/engine/src/engine/ingest/lake.py`: the `raw/nflverse/` layout, if the lake needs a new root
- `python/engine/src/engine/transform/staging.py` (or a new `transform/nfl.py`): stages NFL games and teams
- `python/engine/src/engine/publish/reference.py`, `publish/lines.py`, `publish/staging.py`: NFL teams, games and line rows
- `python/engine/src/engine/cli.py`, `python/engine/src/engine/jobs.py`: the ingest command and the `lines` job step
- `python/engine/tests/test_nflverse.py`: new, AC-1 to AC-4. `python/engine/tests/fixtures/nflverse/`: the recorded file
- `python/db/migrations/versions/0006_nfl.py`: new. The `nfl` sport and the line source value
- `python/db/src/db/models.py`: the CHECK
- `python/db/seeds/fixture/nfl.json`: new. Teams, games and lines. `python/engine/src/engine/fixture.py`: loads it
- `python/db/tests/test_game_market.py`: the NFL case. `python/api/tests/test_api_slate.py`, `test_api_shell.py`: CFB-only counts
- `docs/03-data-model.md`, `docs/02-architecture.md` › Jobs and › Seed data, `docs/decisions.md`

## Verification

- Automated: `uv --directory python run pytest engine/tests/test_nflverse.py db/tests/test_game_market.py api/tests/test_api_slate.py` passes, and so does the whole suite on the reseeded fixture.
- Manual: `engine ingest nflverse --season 2026 --target dev` against the real file, then query `games WHERE sport_id = 'nfl'` on dev → expected: the 2026 schedule, with a favored home team's `spread_home` negative.

## Follow-ups

_Work noticed during this task and deliberately left out. Each bullet ends `→ <path> § <section>` (where it was placed) or `→ not tracked: <reason>`. See `.claude/skills/track-follow-ups/classify.md`; the PR's Follow-ups section is copied from here._

- NFL team colors for the contest screens: real nflverse teams publish with no color (approved at plan)
- `game_market.closing_from` reads `cfbd_close` for an NFL untimed close, and a canceled NFL game stays `scheduled` (nflverse has no cancel flag): recorded in the decision's revisit-when (approved at plan)

## Plan

Approved 2026-11-13. Sportsbook: `(nflverse, nflverse)` (the owner's choice at the plan gate). Sign confirmed in the recorded file: `2026_06_BUF_LV` (BUF away, moneyline −238, `spread_line` −5.5 → `spread_home` +5.5) and `2026_06_TEN_IND` (IND home, −298, `spread_line` 6.5 → −6.5).

1. **Migration `0006_nfl`**: insert `sports ('nfl', 'NFL')`; recreate `ck_line_snapshots_source` with `nflverse`. The downgrade refuses while NFL teams or games or `nflverse` line rows exist. `models.LINE_SOURCES` gains `nflverse`.
2. **Pull** (`ingest/nflverse.py`): download nfldata's `games.csv` (httpx, injectable), keep the requested season's rows, one record per CSV row as given, saved as a new Parquet raw file `raw/nflverse/games/season=Y/fetched_at=…` with params `{"season": Y}`. Skipped when the newest saved file has every game scored. No CFBD budget.
3. **Stage** (`transform/nfl.py`, registered in `TABLES`): `nfl_games`, `nfl_lines`, `nfl_venues` from every nflverse raw file; a game is its newest pull. `REG` → regular, `WC|DIV|CON|SB` → postseason, other types dropped; `kickoff_at` = `gameday` + `gametime` Eastern → UTC (NULL when blank); `final` when both scores are set, else `scheduled`; `neutral_site` = location `Neutral`; `conference_game` false. Lines: every pull's row per game, `spread_home = −spread_line`, `total_line`, moneylines, book `nflverse`.
4. **Publish** (`publish/nfl.py`): upsert teams (`engine/sports/nfl`: the 32 nflverse codes → design-style short name and nickname; an unknown code publishes its code as the name, printed), venues (`stadium_id`/`stadium`; `dome` true for `dome`, false for `outdoors`, else NULL; `grass` from `surface`) and games under `sport_id 'nfl'`, source `nflverse`; lines through `map_lines` and `publish_lines` (D-120's snapshot and closing rule). `publish_lake` runs it in the same transaction and returns NFL counts under separate keys.
5. **Job**: `lines` pulls the current NFL season first; a failed download is recorded and the CFBD pull, stage and publish carry on; the summary gains an NFL line (staged games, new games, new line rows, or the failure), and the run then raises `NflverseFailed` (exit 1). `sync_raw` also copies the `raw/nflverse/` files of the given seasons.
6. **CLI**: `engine ingest nflverse --season Y [--target dev|test]` pulls, stages NFL in memory and publishes it.
7. **Fixture**: `nfl.json` (8 teams with `contest-data.js` colors; 4 Week 6 games Sun 2026-10-11 1:00, 1:00, 4:25, 8:20 PM ET; one Thu 9:02 PM ET snapshot each: BUF@NYJ +4.5, HOU@JAX +1.5, KC@BAL −2.5, NYG@PHI −7, fixture book); `fixture.py` takes a sport.
8. **Docs**: 03 (NFL source, line sources, lake layout), 02 (Jobs `lines`, Seed data: 4 NFL games), a decision for the ingest.

**Files**: new `engine/ingest/nflverse.py`, `engine/transform/nfl.py`, `engine/publish/nfl.py`, `engine/sports/nfl/__init__.py`, `db/migrations/versions/0006_nfl.py`, `db/seeds/fixture/nfl.json`, `engine/tests/test_nflverse.py`, `engine/tests/fixtures/nflverse/games.csv`, `db/tests/test_nfl_schema.py` (instead of `test_game_market.py`); changed `engine/transform/__init__.py`, `engine/publish/staging.py`, `engine/ingest/backfill.py`, `engine/jobs.py`, `engine/cli.py`, `db/src/db/models.py`, `engine/fixture.py`, `engine/tests/test_fixture_seed.py`, `docs/02`, `docs/03`, `docs/decisions.md`.

**Tests**: AC-1–AC-4 `engine/tests/test_nflverse.py` (a recorded slice of the real file, fake HTTP, fixed clock; AC-3 on `2026_10_LAC_BAL`, `spread_line` 4.5); AC-5 `db/tests/test_nfl_schema.py` and `engine/tests/test_fixture_seed.py`, with the existing slate (54) and shell (9) tests; AC-6 `db/tests/test_nfl_schema.py` on a scratch DB, plus `pnpm db:check`.

**Risks**: `game_market.closing_from` says `cfbd_close` for an NFL untimed close (documented, view unchanged); nflverse has no cancel flag, so a canceled NFL game stays `scheduled`.

## Review log

_Filled by /implement-task. One line per round._

## Blocked

_Only if status is Blocked: what failed, what was tried, best hypothesis, decision needed._

## Metrics

- Verify rounds:
- Review rounds:
- First-pass AC FAILs:
- Plan revisions after approval:
