---
id: TASK-071
title: Build the contest page API (ranked slate, entries with kickoff lock, results and standing)
status: In progress
depends_on: [TASK-068, TASK-070]
size: M
model: opus
autonomy: attended
ui: false
plan_status: approved
planned_at_commit: 379fbc5
---

# TASK-071 — Build the contest page API (ranked slate, entries with kickoff lock, results and standing)

## Goal

One API call returns everything the Contest page shows for a week: the slate ranked against the contest's lines with the model's top N marked, your entries, and results and standing. The API takes your picks and your standing, and refuses any pick on a game that has kicked off.

## Context

- Task list: `docs/08-tasklist.md` › M6 › M6.5.
- Product: `docs/01-product.md` › Observable outcomes › F-03 AC-2 and AC-3, F-04, F-32 AC-3, F-33.
- Model: `docs/04-model.md` › § 4 › Contest mode (no vig, so break-even is 50%; rank the eligible slate by cover probability against the contest's line; top N; per-game locks; NFL ranked on the contest-vs-market gap and labelled "no model"), › § 6 › Engineering contract (the light core).
- Architecture: `docs/02-architecture.md` › Components › 2 (one endpoint per screen, the `shell` block), › Testing strategy (Integration: API, "a contest entry after kickoff is rejected"), › Non-functional requirements (≤ 6 queries in one concurrent wave), › Test-only sign-in and clock (Thu 2026-10-08 10:00 PM ET for Contest, Fri 2026-10-09 8:12 PM ET for the locked game).
- Decisions: D-045, D-070 (users "add" picks; no "Lock" verbs in copy the API returns), D-095 (a contest's games are all locked only after its last kickoff), D-143 (displayed cover probability), D-156 (`shell`), D-158 (edges and cover through `engine.core`, as `/slate` does).
- **CFB rows:** the cover probability against the contest line, computed through `engine.core` from the shown version's newest prediction, the way `/slate` computes it against the current line.
- **NFL rows ("No model yet"):** no formula in the docs gives the "~54% mkt-implied" figure. Decide it at the plan gate and record it in 04 § 4 and a decision. `contest-data.js`'s figures (1.5 points → ~54%, 1 → ~53%, 0.5 → ~51%) fit Φ(gap / σ) with σ ≈ 13.5, but NFL margins cluster on 3 and 7, which a normal curve ignores.
- **Order:** cover % descending, ties broken by edge (`contest-data.js`'s `rank`). Locked games drop out of the open ranking until every game is locked (D-095). The top N comes from `rules.picks_per_period`.
- **The model's contest picks:** decide whether they're inserted on confirm (TASK-070) or by the `lines` job, if TASK-070's plan hasn't already (task list note).
- **The ≠ count:** F-04 AC-3's "Line ≠ market 7" is sample data. On the fixture's lines, 8 of the 10 games differ from the market, so the API returns a per-row flag and the screen counts it.
- **Lock:** an entry or change is refused when the API clock is at or past the game's `kickoff_at`. A game with a TBA kickoff locks at the end of `game_date` in Eastern time, as `current_picks`' cutoff does. A change is a soft delete plus a new entry at the current contest line (D-033).
- *From TASK-068 (PR #160):* read `contest_results` and `contest_record` filtered to the shown model version: each version with contest picks has its own `model` rows. Whoever writes the model's contest picks in production writes every slate game's pick before the contest week's first kickoff (D-171: a later pick never enters the graded top N, so a job that runs after a Thursday-night game would drop the week), with `expected_value` = 2p − 1 at even money and tier NULL unless that plan decides otherwise.
- *From TASK-068 (PR #160):* `current_contest_lines` repeats the shell's shown-version rule (`api/shell.py` `SHOWN`) in SQL, per game's sport and season; if this task changes `SHOWN` or reads the model line from the view, keep the two in step.
- *From TASK-070 (PR #161):* TASK-070's plan left the model's contest picks (inserted on confirm, or by the `lines` job) to this task's plan, which owns the ranking; the import's confirm writes only `contest_lines`. Its write routes run on one connection per request (`main.connection`, `Depends(..., scope="function")`, so a write commits before its response) and upsert the caller's `users` row first (D-172); the entry and standing routes can reuse both.

## Acceptance criteria

- [ ] AC-1: Given the seeded DB and the clock at Thu 2026-10-08 10:00 PM ET, the contest page route for the Splash work league's Week 6 returns the 10 games with the `shell` block. Games are ranked by cover % descending, ties by edge. Each CFB row's edge and cover % equal `engine.core`'s result on the fixture's v1.0 prediction and the contest line. The first 4 rows, Texas vs Oklahoma, Ole Miss @ LSU, Purdue @ Ohio State and Colorado @ BYU, are marked as the model's top 4, and row 5 is returned as "next best".
- [ ] AC-2: The 4 NFL rows carry no model fields and are marked "no model yet". Each carries the gap between contest and market lines in points and the side it favours, plus a market-implied % from the plan's formula. Kansas City @ Baltimore, with no gap, has no side and 50%. Every row carries its contest and market spreads and a flag that is true exactly when they differ.
- [ ] AC-3: Posting an entry for an open game at Thu 10:00 PM inserts a `contest_entries` row at that game's current contest line. Posting the other side soft-deletes the first and inserts the new one. Removing an entry soft-deletes it. With the contest's 4 picks already live for the week, a fifth is refused with 409.
- [ ] AC-4: With the clock at Fri 2026-10-09 8:12 PM ET, the response marks UNLV @ Boise State locked. Posting, changing or removing an entry on it returns 409 and writes nothing (test). The other games are still open.
- [ ] AC-5: The response lists your Week 6 entries, OU +7 made Thu 9:14 PM and BUF −3 made Thu 9:20 PM ET, each with its line and time. Results come from TASK-068's views: season you 12-8 and model's top 4 11-9, the W1–W5 rows, and this week 0 points each. The standing is 3rd of 14, 1 point behind. Posting a standing writes a `contest_standings` row, and the next GET returns it.
- [ ] AC-6: The GET runs at most 6 queries in one concurrent wave on the seeded DB (a test counts them). Every route returns 401 without a valid JWT. The generated TypeScript types include the routes, and the drift check passes.

## Out of scope

- The Contest screen: ranked slate, tray and results (TASK-073); the paste flow (TASK-072).
- An NFL model (Phase 8).
- Best lines across market and contest (M7.3).
- Contest settings and the rules form (M8.8: Settings › Contests is read-only).
- Picking for any contest but the user's own, or more than one user.

## Files likely touched

- `python/api/src/api/contest.py`: new. The page query, entries and standing routes, response models
- `python/api/src/api/main.py`: the routes
- `python/engine/src/engine/core/contest.py`: new. Ranking, top N and the market-implied % (light core)
- `python/engine/tests/test_core_contest.py`: new
- `python/api/tests/test_api_contest.py`: new, AC-1 to AC-6
- `python/engine/src/engine/publish/picks.py`: only if this task writes the model's contest picks
- `web/lib/api-types.ts`: regenerated
- `docs/04-model.md` › § 4 › Contest mode (the market-implied formula); `docs/decisions.md`

## Verification

- Automated: `uv --directory python run pytest api/tests/test_api_contest.py engine/tests/test_core_contest.py` passes, and so do the whole suite and the drift check.
- Manual: through the test client at Thu 10:00 PM, GET the Week 6 page, POST an entry on Notre Dame @ Stanford, then GET again → expected: three entries; then at Fri 8:12 PM, POST on UNLV @ Boise State → expected: 409.

## Follow-ups

_Work noticed during this task and deliberately left out. Each bullet ends `→ <path> § <section>` (where it was placed) or `→ not tracked: <reason>`. See `.claude/skills/track-follow-ups/classify.md`; the PR's Follow-ups section is copied from here._

- Write the model's contest picks in production on import confirm, in the confirm's transaction (decided at this plan gate: the only writer sure to run before the week's first kickoff, D-171; the `lines` job runs 10 AM ET daily and 9 PM ET Thu/Fri, so it misses a Saturday-morning paste) → docs/tasks/TASK-078-….md (new, Draft) and docs/08-tasklist.md § M6 (approved at plan)
- An NFL market-implied % that knows the key numbers (3 and 7) instead of a normal curve, from nflverse margins → docs/06-roadmap.md § Phase 8 (approved at plan)

## Plan

Approved 2026-11-18 at 379fbc5.

**Decisions taken at the gate:** the NFL "~%" is Φ(gap / 13.5) (the market line as the expected margin, the contest line priced on a normal curve at σ 13.5, labelled approximate); the model's contest picks are written on import confirm, built in a new Draft task, not here (D-174 records both).

**Steps**

1. `engine/core/contest.py` (light core): `NFL_MARGIN_SD = 13.5`; `market_implied(contest_spread_home, market_spread_home)` → gap in points, the side it favours (None at no gap) and the probability (`cover_probability` with the market line as the expected margin: Φ(gap / 13.5), 50% at no gap). `rank(rows, picks_per_period)`: open rows by cover % descending, then edge, kickoff, game id; locked rows drop out of the open ranking until every row is locked (D-095), then the whole slate is ranked; locked rows keep their place in the all-games ranking. Top N = the first `picks_per_period` rows with a model (CFB only, D-170, so it is what `contest_results` grades); next best = the first open row ranked below the Nth.
2. `api/contest.py`, the page read: `GET /contests/{contest_id}?period=` (default: the contest's newest period with lines). One wave of 6: shell; slate (each game's contest line as of the API clock and before its cutoff, as the import's rule; the market's current spread priced like `/slate`, newest pull by now; the shown version's prediction from a succeeded run finished by now); rules (spec and run params, as `/slate`); your live entries for the period with line and time; `contest_record` for you and the shown version; the contest (owner check, 404 otherwise) with the standing entered by the API clock. CFB rows: edge, side and cover % through `displayed_prob` (`/slate`'s `_rules`, `_distribution`). Every row: contest and market spreads, `differs`, `locked`, `rank`, `top_n`, `next_best`.
3. Writes, each on one connection (`main.connection`), `upsert_user` first, the contest row locked `FOR UPDATE`: `POST /contests/{id}/entries {game_id, side}` inserts at the current contest line; the other side soft-deletes the live entry and inserts the new one; the same side changes nothing. `DELETE /contests/{id}/entries/{game_id}` soft-deletes. 409 at or past the game's cutoff (`kickoff_at`, else the end of `game_date` ET), and for a new entry past `picks_per_period`. `POST /contests/{id}/standings` inserts a row at the API clock.
4. Routes in `main.py`; regenerate `web/lib/api-types.ts` (`pnpm --dir web api:types`).
5. Docs: 04 § 4 › Contest mode (the formula and the ranking), `docs/model-guide.md`, D-174.

**Files:** `python/engine/src/engine/core/contest.py` (new), `python/engine/src/engine/core/__init__.py` (exports; not in Files likely touched), `python/engine/tests/test_core_contest.py` (new), `python/api/src/api/contest.py` (new), `python/api/src/api/main.py`, `python/api/tests/test_api_contest.py` (new), `web/lib/api-types.ts`, `docs/04-model.md`, `docs/model-guide.md` (not in Files likely touched), `docs/decisions.md`. Close-out also writes the follow-ups' task file, task list row and roadmap line.

**Test strategy**

- AC-1: `test_api_contest.py::test_week_6_ranks_by_cover_against_the_contest_line` (order, edge and cover equal to `engine.core` on v1.0's prediction; top 4 and next best).
- AC-2: `test_nfl_rows_carry_the_gap_and_the_market_implied_share`, `test_the_differs_flag_marks_8_of_10`; `test_core_contest.py` for the formula and ranking.
- AC-3: `test_an_entry_is_added_at_the_current_contest_line`, `test_the_other_side_replaces_the_entry`, `test_removing_soft_deletes`, `test_a_fifth_pick_is_refused`.
- AC-4: `test_the_locked_game_refuses_every_write` (Fri 8:12 PM; row count unchanged), `test_the_locked_game_is_marked_and_the_rest_stay_open`.
- AC-5: `test_entries_results_and_standing`, `test_a_posted_standing_is_read_back`.
- AC-6: `test_the_page_runs_in_one_wave_within_budget`, `test_every_contest_route_needs_a_token`, `test_the_contest_routes_are_in_the_schema`; the drift check in `pnpm typecheck`/CI.
- Manual: the task's Verification steps through the test client.

**Risks:** writes are tested on the rolled-back `db_conn` (the dependency override TASK-070 uses), since `contest_lines` and entries refuse DELETE. If v1.0's week-6 run finished after Thu 10:00 PM the predictions would be hidden; checked first.

**Size:** 10 files, no schema, no UI.

## Review log

_Filled by /implement-task. One line per round._

## Blocked

_Only if status is Blocked: what failed, what was tried, best hypothesis, decision needed._

## Metrics

- Verify rounds:
- Review rounds:
- First-pass AC FAILs:
- Plan revisions after approval:
