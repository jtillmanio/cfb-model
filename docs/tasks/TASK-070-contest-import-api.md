---
id: TASK-070
title: Build the contest import API (paste, parse, match, confirm)
status: In progress
depends_on: [TASK-067, TASK-023]
size: M
model: opus
autonomy: attended
ui: false
plan_status: approved
planned_at_commit: b3cbfde
---

# TASK-070 — Build the contest import API (paste, parse, match, confirm)

## Goal

Pasting a Splash contest page into the app returns its rows matched to games. You can map the names it couldn't match, and the mapping is saved for next time. Confirming saves that week's contest lines as a new snapshot.

## Context

- Task list: `docs/08-tasklist.md` › M6 › M6.4. The API's first write routes.
- Product: `docs/01-product.md` › Observable outcomes › F-03 AC-1.
- Data model: `docs/03-data-model.md` › Data sources › Contest lines (import by paste, one-time alias fix, each paste a snapshot), › Reference › `team_aliases` (UQ `(source, alias)`), › Your data › `contest_lines`.
- Architecture: `docs/02-architecture.md` › Components › 2 (writes: contest entries; the browser never calls the API), › Testing strategy (Integration: API).
- Decisions: D-036, D-038, D-105 and D-107 (the JWT on every route), D-113 (the parser: `parse_splash(text, aliases, tz)`; problem rows `no line` and `lines disagree` are returned, never dropped), D-155 (generated types), D-158 (how the API reaches the engine).
- **Hard rule 5:** the API imports only `engine.core` (`python/api/tests/test_bundle.py` enforces it), but the parser is `engine/contests/splash.py`. It's stdlib-only and sport-agnostic, so the plan either moves it into the light core (amending D-113) or names another way that keeps the rule. The API never imports `engine.contests` as it stands.
- **Time zone:** `user_settings` arrives in M8.7, so until then the import passes America/New_York, the parser's default and the owner's zone.
- **Matching a row to a game:** both teams through the alias lookup, plus the kickoff date, among the contest's sports (`rules.sports`).
- **Settle at the plan gate: a real first paste.** Real Splash pages name CFB teams by school and NFL teams by nickname (`design/sample-splash-10062026.txt`: "Giants", "Jets", "Texans") and list about 100 games. Production starts with no `splash` aliases, so every row of the first real paste would be unmatched. The plan decides whether a name with no `splash` alias falls back to an exact, unique match on `teams.school` (CFB) or `teams.mascot` (NFL), saving nothing, or whether the inline picker carries the first paste.
- **The model's contest picks:** whether they're inserted on confirm or by the `lines` job is decided at this task's plan gate or TASK-071's, whichever comes first (task list M6.5 note).
- *From TASK-016 (PR #52):* the fixture needs `splash` aliases for every Week 6 paste name except "Hou Texans" and "Jax", so the import shows "9 rows match · 1 unmatched".
- *From TASK-023 (PR #52):* build the parser's alias lookup from `team_aliases WHERE source = 'splash'` and pass the user's time zone to `parse_splash`.
- **Fixture paste:** `contest-data.js`'s Week 6 paste, copied into a test fixture. Nothing reads `design/` at runtime (02 › Seed data).
- **The fixture's Week 6 lines already exist** (TASK-067), so tests that confirm a paste use a contest week with no lines or check the new snapshot by its `captured_at`.
- *From TASK-069 (PR #157):* NFL teams publish under `sport_id 'nfl'`, source `nflverse`, with `school` the design's short name ("Buffalo", "NY Jets"), `mascot` the nickname ("Bills", "Jets", "Texans") and `abbreviation` nflverse's code (`engine/sports/nfl`, D-169), so a fallback match on `teams.mascot` finds an NFL team by the nickname Splash prints.
- *From TASK-067 (PR #159):* this import is the production writer of `users`: on its first write it upserts the row by `github_id` from the JWT's `sub` (`INSERT … ON CONFLICT (github_id)`), since no migration seeds the real account; `email` and `name` stay NULL because the token carries only `sub` (D-170). The test DB's user is the fixture's, `github_id` 4242.

## Acceptance criteria

- [ ] AC-1: Given the seeded DB and the fixture Week 6 paste, the preview route returns 10 rows: 9 matched to their game IDs with each row's `spread_home` and kickoff, and 1 unmatched ("Hou Texans" @ "Jax"), with counts of 9 matched and 1 unmatched. It writes nothing: row counts in `contest_lines` and `team_aliases` are unchanged.
- [ ] AC-2: Saving the mappings "Hou Texans" → Houston Texans and "Jax" → Jacksonville Jaguars writes two `team_aliases` rows with `source` `splash`, and saving them again writes nothing. Previewing the same paste then returns 10 matched and 0 unmatched.
- [ ] AC-3: Confirming a fully matched paste inserts one `contest_lines` row per row, all with the API clock's `captured_at`, `source` `paste` and the contest's period. Confirming with an unmatched or problem row returns 422 naming the rows and writes nothing.
- [ ] AC-4: For a re-paste, the preview lists each matched row whose line differs from the contest's current line, with the old and new line (the re-paste diff). Confirming it inserts a new snapshot and never changes an earlier one.
- [ ] AC-5: Text with no game block returns 422 with an "unparseable" code. A paste in which no row matches any team returns the "no match" response, listing the rows. A row the parser flags (`no line`, `lines disagree`) comes back with its problem and blocks confirm.
- [ ] AC-6: Every route returns 401 without a valid JWT. `test_bundle.py` still passes, so the API still imports only `engine.core`. The generated TypeScript types include the routes, and TASK-052's drift check passes.

## Out of scope

- The Contest screen and its paste flow (TASK-072).
- The ranked slate, entries, results and standing (TASK-071).
- Manual "add game" entry (the design's secondary option).
- Parsers for other platforms.
- Saving the user's time zone (M8.7, `user_settings`).

## Files likely touched

- `python/api/src/api/contest_import.py`: new. Routes, matching and response models
- `python/api/src/api/main.py`: the routes
- `python/engine/src/engine/contests/splash.py` → `python/engine/src/engine/core/` (if the plan moves it) and `python/engine/tests/test_splash_parser.py`'s import
- `python/api/tests/test_api_contest_import.py`: new, AC-1 to AC-6. `python/api/tests/fixtures/week6-paste.txt`: new
- `python/db/seeds/fixture/contest.json`: the `splash` aliases. `python/engine/src/engine/fixture.py`: loads them
- `web/lib/api-types.ts`: regenerated
- `docs/02-architecture.md` › Components › 2; `docs/decisions.md` (amending D-113 if the parser moves)

## Verification

- Automated: `uv --directory python run pytest api/tests/test_api_contest_import.py api/tests/test_bundle.py engine/tests/test_splash_parser.py` passes, and `pnpm test`'s drift check passes.
- Manual: through the test client on the seeded DB, preview `design/sample-splash-10062026.txt` → expected: every block returned with a status and none dropped; the unmatched count follows the plan's fallback decision.

## Follow-ups

_Work noticed during this task and deliberately left out. Each bullet ends `→ <path> § <section>` (where it was placed) or `→ not tracked: <reason>`. See `.claude/skills/track-follow-ups/classify.md`; the PR's Follow-ups section is copied from here._

- Production has no contest and nothing creates one ("Add contest" isn't designed; M8.8's Settings › Contests is read-only), so every import 404s until one exists: a new Draft task, an `engine contest add` CLI the owner runs (upserts the user too), with its task list stub (approved at plan)
- E2E writes through the API persist in the test DB (`contest_lines` refuses DELETE; a mapped alias stays), so TASK-072's journey 3 ("9 rows match · 1 unmatched", then mapping "Hou Texans"/"Jax") fails on a second run against the same DB → docs/tasks/TASK-072-contest-paste-flow.md § Context (approved at plan)
- The model's contest picks (on confirm or by the `lines` job) are left to TASK-071's plan, which owns the ranking → docs/tasks/TASK-071-contest-page-api.md § Context (approved at plan)
- Candidate decision: the contest import API (routes, the school/mascot fallback with game pairing, the parser in the light core amending D-113, `period` in the request, one connection per write request through a dependency the tests override) → docs/decisions.md (approved at plan)

## Plan

Approved 2026-11-15 (attended, with decisions A–E and the follow-ups).

**Routes** (`router`, JWT; `python/api/src/api/contest_import.py`):
1. `POST /api/py/contests/{contest_id}/import/preview` `{text, period}`: writes nothing. Every block back with a status (`matched`, `unmatched`, `no_game`, `ambiguous`, `problem`), `matched_by` (`alias`/`name`), game id, `spread_home`, kickoff, source lines, the names left unresolved and up to 8 picker candidates per unmatched name; counts; `lock_at`; the re-paste diff (matched rows whose line differs from the contest's current line: the newest snapshot captured at or before the API clock and before the game's cutoff). 422 `unparseable` (no game block); 422 `no_match` with the rows (no name resolves to any team).
2. `POST /api/py/contests/{contest_id}/aliases` `{mappings: [{alias, team_id}]}`: inserts `team_aliases` with `source` = the contest's platform, skipping existing identical ones; an alias mapped to another team → 409, nothing written; a team outside the contest's sports → 422.
3. `POST /api/py/contests/{contest_id}/import/confirm` `{text, period}`: re-parses and re-matches server-side; any unmatched, ambiguous, problem or duplicate-game row → 422 naming the rows, nothing written; else one `contest_lines` row per row at `captured_at` = the API clock, `source` `paste`, the given `period`.
4. Each write upserts `users` by `github_id` = the token's `sub` (D-170); a contest not the caller's, or deleted → 404. Time zone `America/New_York` (M8.7 brings `user_settings`).
5. Write routes take one connection per request from a FastAPI dependency (`engine().begin()`: commit or roll back as a whole); tests override it with `db_conn`, so every write is rolled back (`contest_lines` refuses DELETE).

**Decisions:** A. A name with no alias falls back to an exact `teams.school` or `teams.mascot` match within the contest's sports; a row is matched only when exactly one game on its date pairs the two sides' candidates; nothing is saved. B. Picker candidates: teams of the contest's sports playing on the row's date, ranked by a name word prefixing school, mascot or abbreviation, at most 8. C. The parser moves to `engine/core/splash.py` (stdlib only, sport-agnostic); `engine/contests/` is removed; a new decision amends D-113. D. `period` comes in the request (the page prints no week). E. The model's contest picks are left to TASK-071's plan.

**Steps:** 1. `git mv` the parser into core, fix the parser test's import; parser tests pass. 2. Fixture: 18 `splash` aliases in `contest.json`, loaded by `fixture.py` (`ON CONFLICT (source, alias) DO NOTHING`); re-seed. 3. Tests first (`python/api/tests/test_api_contest_import.py`), failing. 4. `contest_import.py` (pure matching functions + routes) and `main.py`. 5. `pnpm api:types`. 6. Docs: 02 › Components › 2, 03 › Data sources › Contest lines (the fallback), the decision.

**Files:** `python/api/src/api/contest_import.py` (new); `python/api/src/api/main.py`; `python/engine/src/engine/contests/{splash,__init__}.py` → `python/engine/src/engine/core/splash.py`; `python/engine/tests/test_splash_parser.py`; `python/api/tests/test_api_contest_import.py` (new; reads the existing `python/engine/tests/fixtures/splash_week6.txt` instead of a second copy); `python/db/seeds/fixture/contest.json`; `python/engine/src/engine/fixture.py`; `web/lib/api-types.ts`; `docs/02-architecture.md`; `docs/03-data-model.md` (not in Files likely touched); `docs/decisions.md`; follow-up placements (TASK-071, TASK-072, a new Draft task, `docs/08-tasklist.md`).

**Test strategy** (clock Thu 2026-10-08 10:00 PM ET, `db_conn` override): AC-1 `test_preview_matches_nine_of_ten_and_writes_nothing`; AC-2 `test_mapping_saves_two_aliases_once_and_then_all_match`; AC-3 `test_confirm_inserts_one_line_per_row_at_the_api_clock`, `test_confirm_with_an_unmatched_row_is_422_and_writes_nothing`; AC-4 `test_repaste_lists_moved_lines_and_confirm_adds_a_new_snapshot`; AC-5 `test_unparseable_text_is_422`, `test_no_team_matched_is_the_no_match_response`, `test_a_problem_row_is_returned_and_blocks_confirm`; AC-6 the existing route walk in `test_api_auth.py`, `test_bundle.py`, `web/lib/api-types.test.ts`. Also the fallback (aliases deleted in the transaction) and the candidates.

**Revision 1 (Verify R1):** `python/db/tests/test_market_schema.py`'s `test_every_row_in_the_new_tables_is_fixture` counted every non-`fixture` source as foreign data, and the fixture's aliases are `splash` by design; it now counts an alias as fixture when it names a fixture team. **Revision 2 (implementation):** a matched row carries the stored game's sides and a `swapped` flag, so a neutral-site game the page lists the other way round reads consistently with its `spread_home` (D-172).

**Risks:** FastAPI re-raises a route's HTTPException into a `yield` dependency, so the `begin()` block rolls back; the 422 paths also validate before any write. Two confirms at the same instant collide on UQ `(contest_id, game_id, captured_at)`; tests confirm at distinct clocks.

## Review log

_Filled by /implement-task. One line per round._

## Blocked

_Only if status is Blocked: what failed, what was tried, best hypothesis, decision needed._

## Metrics

- Verify rounds:
- Review rounds:
- First-pass AC FAILs:
- Plan revisions after approval:
