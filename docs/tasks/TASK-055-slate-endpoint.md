---
id: TASK-055
title: Build the /slate endpoint
status: Ready
depends_on: [TASK-052, TASK-053]
size: M
model: opus
autonomy: attended
ui: false
plan_status: none
planned_at_commit:
---

# TASK-055 — Build the /slate endpoint

## Goal

One API call returns everything This Week shows for a week: every game with its status and score, the market (opener, current line and every snapshot), the model's line, edge, cover and win probability, the current pick and how it's doing, and the week's counts, plus the shell block.

## Context

- Task list: `docs/08-tasklist.md` › M5 › M5.5. The first screen endpoint (BFF pattern).
- Architecture: `docs/02-architecture.md` › Components › 2 (one endpoint per screen), › Non-functional requirements (≤ 6 queries in one concurrent wave; a task that needs more records why), › Testing strategy (Integration: API, "each screen endpoint returns the fixture values"; Seed data: "54 CFB games", "54 games · 9 picks", the four fixture times).
- Data model: `docs/03-data-model.md` › Games & market, › Models & outputs, › Views (`game_market`: opening, current, closing, D-120; `current_picks`, `pick_outcomes`: `result`, `units`, `clv` against the close, `clv_so_far` against the current line before kickoff, D-142; `team_rankings` for the chip's rank).
- Model: `docs/04-model.md` § 4 (edge, cover probability, tiers), § 6 (engineering contract: the light core). `predictions` stores `pred_margin`, `home_win_prob` and `margin_sd`, not the edge or cover %, which depend on the line: for a game without a pick the API computes them from the latest prediction and the current line through `engine.core` (probability and pick math, `ModelSpec`, D-143's display shrinkage), so they match what `core.picks.pick()` gives. Pick thresholds come from the shown version's spec (D-055), returned so the UI never hard-codes them.
- Decisions: D-010, D-047 (no picks on FBS vs FCS), D-120, D-132/D-140 (CLV sign), D-142, D-143, D-144 and TASK-053's version rule (which version the slate shows), D-146 (screen endpoints return `teams.logo_url`), D-150 (a week is `(season_type, week)`; the coming week is the week of the earliest kickoff still to come).
- Clock: reads TASK-053's API clock; e2e's API runs at Sat 2026-10-10 2:15 PM ET.
- **Live clock not stored.** `games` has `status`, `home_points` and `away_points` but no period or game clock, so "Q3 9:12" (sample-data, F-01 AC-3) can't be served without a schema change (stop and ask). This task returns live status and scores; the period and clock wait for the task that adds them (proposed: M6.8, the `scores` job, which is what would fill them).
- *From TASK-016 (PR #52):* the fixture still lacks the other Week 6 games behind "54 games" (Tulane @ Memphis final 27-24, Iowa State @ Cincinnati, Arizona State @ Baylor, and filler with edges under 1.0; 02 › Seed data); this task adds them.
- *From TASK-034 (M3 task files):* TASK-034 seeds v1.0 predictions for the 11 Week 6 games seeded then; this task seeds a v1.0 prediction for each game it adds (filler edges under 1.0), in the same fixture file.
- *From TASK-040 (PR #105):* TASK-040 seeds Tulane @ Memphis, Iowa State @ Cincinnati and Arizona State @ Baylor (lines, v1.0 predictions and picks, in `picks.json`), so this task adds the other 40 Week 6 games, not 43.
- *From TASK-041 (PR #107):* `current_picks` is the pick frozen at kickoff; `pick_outcomes` gives each pick's `result`, `units`, `clv` (against the close, NULL until `closing_spread_home` is set) and `clv_so_far` (against the current line, for the "so far" label before kickoff) (D-142).
- Filler games need teams beyond the fixture's 53 (`python/db/seeds/fixture/teams.json`), each with lines and a v1.0 prediction; if they get ratings, they rank below the fixture's top 10 so `team_rankings`' seeded ranks don't move. Seeded through `python/engine/src/engine/fixture.py` (D-089: test DB only).
- *From TASK-052 (PR #134):* the web types in `web/lib/api-types.ts` are generated from the API's response models (D-155). Adding the `/slate` response models to `python/api/src/api/main.py` makes `pnpm test` fail until you run `pnpm api:types` and commit the file; type the screen's data from `components["schemas"][...]` in `web/lib/api-types.ts`, and don't hand-write a response type in `web/lib/`.

## Acceptance criteria

- [ ] AC-1: Given the seeded test DB and the clock at Sat 2026-10-10 2:15 PM ET, `GET /api/py/slate` (no week given) returns season 2026, season type `regular`, week 6, 54 games, a pick count of 9, the shown version's pick rules (min edge, min cover, tier cut-offs from its spec) and TASK-053's shell block.
- [ ] AC-2: For Purdue @ Ohio State the response gives the opening and current spreads, one entry per line snapshot captured before the clock, the model line, an edge of 3.7 to OSU, the cover probability, tier B and OSU's win probability, matching the fixture rows and `engine.core`'s calculation on them; for Kansas State @ Utah the edge is 0.6 to Utah with no pick.
- [ ] AC-3: Row states come back as data: UNLV @ Boise State `final` with 24 and 31 and its cover result; Purdue @ Ohio State and Iowa @ Wisconsin `in_progress` with their scores; Furman @ Clemson with no market lines and Furman marked FCS; Texas vs Oklahoma neutral-site with its venue's city; each team with id, abbreviation, school, colour, `logo_url` and its rank entering the week.
- [ ] AC-4: The Ole Miss @ LSU pick returns the line it was picked at (−2.5) and when, the current line (−3.5), and `clv_so_far` −1.0 before kickoff (D-140's sign), from `pick_outcomes`; a graded week-6 pick (Tulane @ Memphis) returns `result` won and its units.
- [ ] AC-5: `GET /api/py/slate?season=2026&season_type=regular&week=5` returns week 5's games; given the clock at Mon 2027-02-08 6:00 AM ET and no week, it returns 200 with no games and an off-season marker; given a week whose games have no lines yet, each game returns its model line with null market fields and null edge.
- [ ] AC-6: The endpoint runs at most 6 queries in one concurrent wave on the seeded DB (a test counts them; if the plan needs more, the reason is written in `docs/02-architecture.md` › Non-functional requirements); it rejects a missing or bad JWT; the generated TypeScript types include it (TASK-052's drift check passes).

## Out of scope

- The This Week screen (TASK-056) and its filters, record strip and empty states (TASK-057).
- Totals and moneylines (F-11, Phase 7): spread only.
- Best lines (M7.3) and contest lines (M6).
- Storing the live period and clock (schema change; proposed for M6.8).
- Weather and stars (F-08, F-14, Phase 5).
- The NFL games on the contest slate (M6.3).

## Files likely touched

- `python/api/src/api/slate.py` — new: the queries, the edge and cover calculation, the response models
- `python/api/src/api/main.py` — the route
- `python/api/tests/test_api_slate.py` — new: AC-1 to AC-6
- `python/db/seeds/fixture/week6.json` (or a new fixture file beside it), `python/db/seeds/fixture/teams.json`, `python/db/seeds/fixture/models.json` — the 40 games, their teams, lines and v1.0 predictions
- `python/engine/src/engine/fixture.py` — loads the new rows, if a new file
- `python/db/tests/test_model_record.py`, `test_team_rankings.py` — only if the added rows move a seeded expectation (they shouldn't; a moved one means the fixture is wrong)
- `web/lib/api-types.ts` — regenerated
- `docs/02-architecture.md` › Testing strategy › Seed data — the filler games as built

## Verification

- Automated: `uv --directory python run pytest api/tests/test_api_slate.py` passes; the whole pytest suite still passes on the reseeded fixture; the drift check passes.
- Manual: `pnpm db:seed`, then call `/api/py/slate` through the test client → expected: 54 games, 9 picks, Purdue @ Ohio State as in AC-2.

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
