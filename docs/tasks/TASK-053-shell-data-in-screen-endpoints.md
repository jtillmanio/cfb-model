---
id: TASK-053
title: Carry the app shell's data in each screen endpoint
status: Review
depends_on: [TASK-052]
size: M
model: opus
autonomy: attended
ui: false
plan_status: approved
planned_at_commit: 1fbc8a5
---

# TASK-053 — Carry the app shell's data in each screen endpoint

## Goal

Every screen's single API response also carries what the app shell around it shows (the current season and week, the model's live track record for the sidebar card, when lines were last updated and whether they're stale, and the week's pick count), so the shell never needs a second API call.

## Context

- Task list: `docs/08-tasklist.md` › M5 › M5.3 (API half). M5.3 is split by layer (`workflow.splitPolicy: split`, over 20 files as one task): this task settles M5.3's "decide at the plan gate how shell data rides in each page's one API call" on the API side; TASK-054 builds the shell UI. M5's riskiest item ("getting the app shell's data … into each page's single API call").
- Architecture: `docs/02-architecture.md` › Components › 2 (one endpoint per screen, queries concurrent within a fixed budget), › Non-functional requirements (query budget ≤ 6 in one wave; data freshness: "Every data page shows its 'Updated' time, and a stale-data banner appears when lines are more than 24 h old"), › Testing strategy (Integration: API, query count within budget; Test-only sign-in and clock: the four fixture times).
- Data model: `docs/03-data-model.md` › Views (`model_record`, `current_picks`), › Games & market (`line_snapshots`: each `lines` pull inserts a row per book at the pull's `captured_at`, `engine/publish/lines.py`, so the newest `captured_at` is the newest pull), › Reference (`seasons.weeks`, the CFBD calendar).
- Design: `design/README.md` § Navigation (sidebar track-record card "Model · 2026 live · 31-24-1 56.4% · +4.6u · CLV +0.9 · Track record ›"; top bar "2026 · Week 6", "Updated Thu 9:02 PM ET"; Picks nav count badge); `App States Desktop.dc.html` (`frame="offseason"`: card "Model · 2026 final").
- Decisions: D-010, D-092, D-096 (stale banner means only "lines more than 24 h old"), D-142 (`model_record`: the season KPIs are the newest week's `to_date` row; `win_pct` 0–100), D-144 (v1.0 is paper-traded as `candidate`, not `production`), D-147 (one `production` version per market drives the default picks), D-149/D-150 (the coming week: the week of the earliest kickoff still to come, ties to the regular season).
- **Which version the shell (and `/slate`, TASK-055) shows, decided here at the plan gate.** The fixture's v1.0 is `production` (02 › Seed data); production's v1.0 is `candidate` (D-144), so "the production version" alone would show no model on the real app. Proposed: the (cfb, spread) `production` version if one exists, else the newest non-`retired` `candidate` with a succeeded `scheduled` run this season. Record it in `docs/decisions.md`; M23's model switcher replaces it later (D-147).
- **The stale rule against the fixture clock, decided here.** The fixture's newest pull is Thu 9:02 PM ET and the slate's clock is Sat 2:15 PM ET (41 h), so a 24 h rule marks the default fixture state stale, while `01-this-week-desktop.png` shows "Updated Thu 9:02 PM ET" and no banner. Options: keep 24 h and accept the banner in the default fixture state; add a Saturday-morning pull to the fixture (the "Updated" text then changes); or measure staleness against the `lines` schedule. 02 › Non-functional is the rule; a change to it needs the owner.
- **Clock:** the API has none yet. 02 says the engine and the web app each read "now" from one clock that honours `FIXTURE_NOW` only when `APP_ENV=test`; `engine/clock.py` isn't in the light core the API may import (hard rule 5, `.claude/rules/python.md`). The plan picks between moving it into `engine.core` and an API clock with the same rule. e2e's API server then gets `FIXTURE_NOW` = Sat 2026-10-10 2:15 PM ET in `web/playwright.config.ts`.
- **The card's record is the season to date, which on the fixture includes week 6.** `01-this-week-desktop.png`'s card reads 31-24-1 (weeks 1–5, sample-data § 7) while its record strip reads "This week 1-0"; the fixture's newest `to_date` row is 32-24-1 (Tulane @ Memphis, a week-6 win, `python/db/tests/test_model_record.py`). D-142 makes the newest week's `to_date` row the season, so the card follows the view, not the screenshot ("Counts and numbers come from code or data, never from prose").
- `/api/py/teams` is the only screen endpoint today, so it carries the shell block first; every later screen endpoint reuses the same helper.
- *From TASK-052 (PR #134):* the web types in `web/lib/api-types.ts` are generated from the API's response models (D-155). Adding the `shell` block to `/teams`'s response model in `python/api/src/api/main.py` makes `pnpm test` fail until you run `pnpm api:types` and commit the file; type the screen's data from `components["schemas"][...]` in `web/lib/api-types.ts`, and don't hand-write a response type in `web/lib/`.

## Acceptance criteria

- [x] AC-1: Given the seeded test DB and the clock at Sat 2026-10-10 2:15 PM ET, `GET /api/py/teams` returns a `shell` block with season 2026, season type `regular`, week 6, the shown version's name and version (`v1.0`), a record equal to `model_record`'s `to_date` row for v1.0's newest 2026 week (W-L-P, win %, units, average CLV; on the fixture that's week 6, 32-24-1), record label `live`, lines updated at Sat 2026-10-10 9:00 AM ET (`2026-10-10T13:00:00Z`, the fixture's newest line snapshot), stale `false` (24 h rule), and 9 picks for the week.
- [x] AC-2: Given a DB whose only (cfb, spread) version is a `candidate` with a succeeded `scheduled` run this season, the shell shows that version; given a `production` version too, it shows the `production` one; given none, the record fields are null and the response is still 200 (pytest on rows the test inserts, rolled back).
- [x] AC-3: Given the newest line pull 23 h before the clock, `stale` is false; given 25 h, it is true (pytest with its own snapshot times; the boundary follows the rule the plan gate keeps).
- [x] AC-4: Given the clock at Mon 2027-02-08 6:00 AM ET (no game still to come in a stored season), the shell names the last season with games (2026), record label `final`, and no current week; the response is 200.
- [x] AC-5: `GET /api/py/teams` runs at most 6 queries, all in one concurrent wave (a test counts them); the route still rejects a missing or bad JWT (`test_api_auth.py` covers the new field's route unchanged).
- [x] AC-6: The generated TypeScript types include the `shell` block (TASK-052's drift check passes), and `FIXTURE_NOW` set without `APP_ENV=test` is ignored by the API clock (a test).

## Out of scope

- Drawing the shell (sidebar, top bar, tabs, banners, error and wake states): TASK-054.
- The `/slate` endpoint (TASK-055); it reuses this block.
- The "uncalibrated" label and calibration status (M7.3).
- A model-version switcher or showing several versions (M23, D-147).
- Changing the 24 h stale rule in `docs/02-architecture.md` without the owner's approval.

## Files likely touched

- `python/api/src/api/main.py` — the `shell` block on `/teams`
- `python/api/src/api/shell.py` — new: the shell queries, the version rule, the coming week
- `python/api/src/api/clock.py` or `python/engine/src/engine/core/clock.py` — the API's "now"
- `python/api/tests/test_api_shell.py` — new: AC-1 to AC-6
- `web/lib/api-types.ts` — regenerated
- `web/playwright.config.ts` — `FIXTURE_NOW` on e2e's API server
- `docs/decisions.md` — the version rule and the stale rule as applied
- `docs/02-architecture.md` › Components › 2 — the shell block every screen endpoint carries

## Verification

- Automated: `uv --directory python run pytest api/tests/test_api_shell.py` passes; the drift check passes; `pnpm test:e2e` still passes with the clock set.
- Manual: `pnpm dev`, signed in, read `/api/py/teams` through the page's server log or a test client → expected: the shell block shows the dev DB's current week and v1.0's live record.

## Follow-ups

_Work noticed during this task and deliberately left out. Each bullet ends `→ <path> § <section>` (where it was placed) or `→ not tracked: <reason>`. See `.claude/skills/track-follow-ups/classify.md`; the PR's Follow-ups section is copied from here._

- Off-season and pre-season shell: AC-4's rule names the last season with games, no week, and that season's record; the design's off-season top bar reads "2027 · Week 0" (the next season's `seasons.weeks`, App States `frame="offseason"`) and its pre-season card "Model · 2025 final" (`frame="team"`). Open question for that task's plan → docs/tasks/TASK-057-record-strip-filters-empty-states.md § Context (approved at plan)
- `01-this-week-desktop.png` and `design/README.md` § Navigation say "Updated Thu 9:02 PM ET", but the fixture's newest pull is Sat 9:00 AM ET (see Plan › Risks) → not tracked: the design rules copy, not numbers; recorded in this task's decision
- The shell's week pick count reads `current_picks` with `line_source = 'market'` only; no test can prove that filter until contest picks exist (`picks.line_snapshot_id` is NOT NULL today, D-140). When M6.1 adds them, add a contest pick to a `test_api_shell.py` case and check `picks` leaves it out (test audit R2) → docs/08-tasklist.md § M6 › M6.1
- The shell statement reads every one of the sport's games for the coming week and every snapshot of the season for the newest pull; fine at today's volume (schema review R1) → docs/decisions.md § D-156 (Revisit if)
- The `lines` read had no `captured_at <= now` bound, so a fixture time before a stored pull showed a future pull (schema review R1) → not tracked: done in this PR (plan revision 2)

## Plan

_Written by /plan-batch or /implement-task Phase 1. Approved by the user (plan_status: approved) before any code is written._

**AC change (approved by the owner 2026-11-04, applied to AC-1):** the fixture's newest line pull is **Sat 2026-10-10 9:00 AM ET** (`2026-10-10T13:00Z`, Texas vs Oklahoma's Sat −6.5 snapshot in `python/db/seeds/fixture/week6.json`), not Thu 9:02 PM. AC-1 expects that time and `stale: false` (5 h 15 m before the clock). The 24 h rule stays as 02 states it, so the stale-rule question goes away. TASK-054 AC-1's "Updated" text follows ("Updated Sat 9:00 AM ET").

Steps:
1. `python/api/src/api/clock.py`: `now()` uses the same rule as `engine/clock.py` (`FIXTURE_NOW` only with `APP_ENV=test`). It can't live in `engine.core`: the API install has no engine at all (`api/tests/test_bundle.py` keeps `cfb-engine` and numpy out).
2. `python/api/src/api/wave.py`: `QUERY_BUDGET = 6`; `run_wave(engine, {name: (sql, params)})` refuses more than 6, runs each on its own connection in a `ThreadPoolExecutor`, waits for all and re-raises the first failure.
3. `python/api/src/api/shell.py`: `SPORT = "cfb"`; `ShellOut` (`season`, `season_type`, `week`, `model` {name, version} | null, `record` {wins, losses, pushes, win_pct 0–100 (D-142), units, avg_clv} | null, `record_label` `live|final` | null, `lines_updated_at`, `stale`, `picks` | null). `SHELL_SQL` is one statement with params `:now` and `:sport`, built from CTEs:
   - **coming:** the game with the earliest cutoff after now (`coalesce(kickoff_at, end of game_date ET)`, the same cutoff as `current_picks`), regular season before postseason on a tie (D-150's `due_weeks`).
   - **season:** the coming game's season, else `max(games.season)`.
   - **shown:** the (sport, `spread`) version, not deleted. `production` comes first; otherwise the newest `candidate` (by `created_at`, then `id`) with a `succeeded` `scheduled` run in that season.
   - **record:** `model_record`'s `to_date` row for the shown version and season, taking the newest week (postseason after regular). It filters by scalar subqueries, so the view's version and season pushdown still applies.
   - **picks:** a count of `current_picks` (`line_source` `market`) for the shown version on the coming week's games.
   - **lines_updated_at:** the newest `captured_at` among `snapshot` rows on that season's games for the sport.
   `shell_from(row, now)`: `stale` = a week exists and now − `lines_updated_at` > 24 h, so exactly 24 h is not stale. `record_label` is `live` when there's a coming week, otherwise `final` (null when there's no record). `load(conn, now, sport)` runs the statement on one connection, which lets tests use `db_conn`.
4. `main.py`: add `TeamsOut.shell: ShellOut`. `/teams` runs `run_wave` over `teams` and `shell`: 2 queries in one wave.
5. Run `pnpm api:types` (regenerates `web/lib/api-types.ts`). In `web/playwright.config.ts`, give the API webServer `FIXTURE_NOW: "2026-10-10T14:15:00-04:00"`.
6. Docs: `docs/decisions.md` gets one D-### row, with the ID from `next-id.ps1`. It covers the shell block, the version rule, "lines updated" = newest snapshot, the 24 h rule as applied, the API's own clock and `run_wave`. In `docs/02-architecture.md`: › Components › 2 (every screen endpoint carries `shell` inside its one wave); › Test-only sign-in and clock ("the engine, the API and the web app"; e2e's API runs at the slate time, and a journey at another fixture time starts its own API server).

Files: `python/api/src/api/{clock,wave,shell}.py` (new), `main.py`; `python/api/tests/test_api_shell.py` (new); `python/api/tests/conftest.py` (puts `db/tests` on `sys.path` for `model_rows`); `web/lib/api-types.ts`; `web/playwright.config.ts`; `docs/decisions.md`; `docs/02-architecture.md` (11 files).

**Plan revision 1 (Phase 3):** `web/lib/api-types.test.ts` too (12 files). TASK-052's scan test used the old hand-written `TeamsResponse` (`season`, `teams`) as its sample of a copy; with `shell` on `TeamsOut` it no longer copies it, so the scan rightly passed it and the test failed. The sample is now built from `TeamsOut`'s schema keys, as the next test's is.

**Plan revision 2 (Phase 5, schema review; approved by the owner 2026-11-04):** the `lines` read takes the newest snapshot with `captured_at <= :now`, so at a fixture time before a stored pull (Contest's Thu 10 PM ET) the shell doesn't show a future pull as not stale. Test: `test_a_pull_after_now_is_not_an_update_yet`; D-156 says "up to now".

Test strategy (`test_api_shell.py`; each test fails on `main`, where there's no `shell`):
- AC-1: `client` with `FIXTURE_NOW` at Sat 2:15 PM ET. The record equals the `model_record` row the test reads (32-24-1); the rest as the AC says, plus `lines_updated_at` 13:00Z, `stale` false and `picks` 9.
- AC-2: `load(db_conn, now, m.SPORT)` on `model_rows` rows: a candidate with a scheduled run is shown; add a production version and it wins; a candidate with only a backtest run, or a run from last season, isn't shown. Route with `shell.SPORT` monkeypatched to an unused sport → 200 with null `model` and `record`.
- AC-3: `load` with a future game and its newest snapshot 23 h, 24 h and 25 h before now → false, false, true.
- AC-4: `client` at 2027-02-08T06:00-05:00 → 2026, `final`, `week` null, 200.
- AC-5: a `before_cursor_execute` listener on `main.engine()` counts statements and waits on `threading.Barrier(2, timeout=5)`. Serial queries break the barrier, so the request fails. Expect 200 and exactly 2 queries, after one warm call. `run_wave` refuses 7. An EXPLAIN check (`m.explain`/`m.scans`) shows the record read filters `picks` by version. `test_api_auth.py` runs unchanged.
- AC-6: `web/lib/api-types.test.ts` passes after regeneration. `clock.now()` ignores `FIXTURE_NOW` when `APP_ENV` is unset and honours it with `APP_ENV=test`.

Risks / open questions:
- The AC-1 change above.
- If Postgres won't push a subquery-param filter into `model_record`, the EXPLAIN test catches it; the fallback is a LATERAL join on the shown version.
- psycopg's first-connect queries skip SQLAlchemy events; the warm call keeps them out of the count.
- With NullPool, each request opens 2 pooled Neon connections. That's within PgBouncer's limits.
- e2e's one API server has one clock (Sat); journeys at other fixture times need their own server (written into 02 in step 6).

Size check: 11 files, no schema change, no UI → passes.

## Review log

_Filled by /implement-task. One line per round._

Verify R1 FAIL(1: api-types.test.ts scan sample, plan revision 1) → R2 PASS → R3 PASS (after plan revision 2) | Audit R1 CHANGES (AC-4 last season UNPROVEN; lines season filter, week tie and `line_source` filter unguarded) → R2 PASS (`line_source` untestable until M6.1: follow-up) | Spec R1 CHANGES (follow-up with no destination) → R2 APPROVE, follow-ups check passed | Schema R1 APPROVE (3 MINOR: `captured_at <= now` fixed as plan revision 2; growth → D-156 Revisit if) → R2 APPROVE | UI not run (no UI change)

## Blocked

_Only if status is Blocked: what failed, what was tried, best hypothesis, decision needed._

## Metrics

- Verify rounds: 3
- Review rounds: 2
- First-pass AC FAILs: 0
- Plan revisions after approval: 2
