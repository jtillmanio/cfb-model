---
id: TASK-070
title: Build the contest import API (paste, parse, match, confirm)
status: Ready
depends_on: [TASK-067, TASK-023]
size: M
model: opus
autonomy: attended
ui: false
plan_status: none
planned_at_commit:
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
