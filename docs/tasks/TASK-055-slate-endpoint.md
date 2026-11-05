---
id: TASK-055
title: Build the /slate endpoint
status: Review
depends_on: [TASK-052, TASK-053]
size: M
model: opus
autonomy: attended
ui: false
plan_status: approved
planned_at_commit: af8e6d1
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

- [x] AC-1: Given the seeded test DB and the clock at Sat 2026-10-10 2:15 PM ET, `GET /api/py/slate` (no week given) returns season 2026, season type `regular`, week 6, 54 games, a pick count of 9, the shown version's pick rules (min edge, min cover, tier cut-offs from its spec) and TASK-053's shell block.
- [x] AC-2: For Purdue @ Ohio State the response gives the opening and current spreads, one entry per line snapshot captured before the clock, the model line, an edge of 3.7 to OSU, the cover probability, tier B and OSU's win probability, matching the fixture rows and `engine.core`'s calculation on them; for Kansas State @ Utah the edge is 0.6 to Utah with no pick.
- [x] AC-3: Row states come back as data: UNLV @ Boise State `final` with 24 and 31 and its cover result; Purdue @ Ohio State and Iowa @ Wisconsin `in_progress` with their scores; Furman @ Clemson with no market lines and Furman marked FCS; Texas vs Oklahoma neutral-site with its venue's city; each team with id, abbreviation, school, colour, `logo_url` and its rank entering the week.
- [x] AC-4: The Ole Miss @ LSU pick returns the line it was picked at (−2.5) and when, the current line (−3.5), and `clv_so_far` −1.0 before kickoff (D-140's sign), from `pick_outcomes`; a graded week-6 pick (Tulane @ Memphis) returns `result` won and its units.
- [x] AC-5: `GET /api/py/slate?season=2026&season_type=regular&week=5` returns week 5's games; given the clock at Mon 2027-02-08 6:00 AM ET and no week, it returns 200 with no games and an off-season marker; given a week whose games have no lines yet, each game returns its model line with null market fields and null edge.
- [x] AC-6: The endpoint runs at most 6 queries in one concurrent wave on the seeded DB (a test counts them; if the plan needs more, the reason is written in `docs/02-architecture.md` › Non-functional requirements); it rejects a missing or bad JWT; the generated TypeScript types include it (TASK-052's drift check passes).

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

- TASK-056's AC-2 expects "59%" for Purdue @ Ohio State, but the fixture's pick and `engine.core` give Φ(3.7/13.8) = 60.6%: the screen should print the response's number; also how `/slate` reads → docs/tasks/TASK-056-this-week-slate.md § Context (approved at plan)
- Decisions A–C (the engine in the API's install, the fixture's v1.0 k = 1, edge and cover against the current line), with the one-clock rule and the consensus-else-median current line (schema review), amending D-004 and D-126 → docs/decisions.md § D-158 (approved at plan)
- `.claude/rules/python.md` still described the API's dependency as the light core "(numpy, scipy, pydantic)" → .claude/rules/python.md § Python rules (approved at close-out)
- The live period and clock ("Q3 9:12") need two columns on `games`, which M6.8's `scores` job would fill; nothing M6.8 reads said so → docs/03-data-model.md § Proposed additions from the 2026-11-01 features (approved at close-out)
- `engine/core/__init__.py`'s docstring also said "numpy, scipy and pydantic only" → not tracked: done in this PR (plan revision, approved at close-out)
- `game_market` reports a pull that quoted only totals or moneylines as a NULL spread, so `pick_outcomes`' CLV and `clv_so_far` go NULL (schema review R2) → docs/tasks/TASK-060-game-market-spreadless-pulls.md (new, Draft)
- Under a fixture clock a pick superseded after it is hidden along with its successor (`is_current` is ranked over every pick) → not tracked: fixture-time only, production never has a pick after now; documented in `api/slate.py`, and no fixture game is picked twice
- `team_rankings` isn't bounded by the API clock → not tracked: a week's ranks come from the run entering it, which finishes before the week (schema review R1, accepted as is)
- The test auditor's backup copies in `C:/tmp_audit_bk/` (outside the project; the guard blocked its delete) → not tracked: asked the owner in the session

## Plan

Approved 2026-11-05 with decisions A–D.

**Decisions.** A: the API reaches `engine.core` by installing the engine package itself: `httpx` moves from the engine's base dependencies to its `train` extra (only `engine/ingest/cfbd.py` imports it; the jobs install `[train]` through the dev group), `cfb-api` depends on `cfb-engine`, `uv lock`. No third-party package joins the API install. B: the fixture's v1.0 spec fixes `picks.market_shrinkage_k` at 1.0 (D-141; its picks are unshrunk already) and its backtest drops the stale 0.6 choice, so `engine.core` can resolve its pick rules. C: each game's edge, side and cover are against the current line (the design's Ole Miss +4.9 now vs +3.9 at the pick); the `pick` block carries the pick's own line, edge, probability, tier, `picked_at`, `clv_so_far`, `clv`, result and units. D: the local test DB is rebuilt (drop and recreate `public` on `TEST_DATABASE_URL`, migrate, seed), since a re-seed reuses the v1.0 row.

**Steps**

1. Install: engine `httpx` → `train` extra; `cfb-api` depends on `cfb-engine`; `uv lock`. `test_bundle.py`: `API_PACKAGES` unchanged; the moot `cfb-engine` check (hidden by `--no-emit-workspace`) is replaced by a subprocess test that `import api.main` loads no numpy, httpx, pyarrow, duckdb, boto3 or `engine.sports`, and a scan that `api/src` imports only `engine.core`.
2. Filler: `python/db/seeds/fixture/generate_filler.py` (fixed seed) writes `week6_filler.json`: 40 week-6 games between the 18 unused teams whose schedules the design doesn't fix and 62 new FBS teams (ratings weeks 1–6 below Utah every week, no ties), kickoffs Sat 3:30 PM ET or later (scheduled, no scores), opening + Sun + Thu snapshots, v1.0 predictions with |edge| < 1.0 at the current line. `fixture.py` loads it.
3. `models.json`: v1.0 `market_shrinkage_k` 1.0, backtest choices without it.
4. `shell.py`: its coming-week and shown-version SQL as shared fragments (no behaviour change).
5. `slate.py`: one wave of 5 queries (shell; games with teams, division, rank entering the week, venue, `game_market` open/current/close and the prediction from the week's newest succeeded run; line pulls up to the clock; `current_picks` + `pick_outcomes`; the shown version's spec and the run's params). Rules = spec resolved with the run's choices; distribution = the run's empirical weights, else a normal margin at the prediction's σ; edge, side, cover against the current line through `engine.core`; a final game's cover result against the close, else the current line. Unresolvable rules → rules and computed fields null. Response models.
6. `main.py`: `GET /api/py/slate?season&season_type&week` (all three or none, else 422).
7. `pnpm api:types`; `docs/02` › Components 1 (what the API installs) and › Seed data (the filler as built).

**Files**: `python/engine/pyproject.toml`, `python/api/pyproject.toml`, `python/uv.lock` (by `uv lock`), `python/api/tests/test_bundle.py` (not in "Files likely touched": decision A), `python/db/seeds/fixture/generate_filler.py` + `week6_filler.json` (new; in place of editing `teams.json`/`week6.json`), `python/db/seeds/fixture/models.json`, `python/engine/src/engine/fixture.py`, `python/api/src/api/shell.py` (not listed: shared CTEs), `python/api/src/api/slate.py` (new), `python/api/src/api/main.py`, `python/api/tests/test_api_slate.py` (new), `python/db/tests/test_filler_schema.py` (new), `python/db/tests/test_model_schema.py` (FBS count, choices), `python/db/tests/test_team_rankings.py` (reads the filler file), `web/lib/api-types.ts`, `docs/02-architecture.md`, `docs/model-guide.md` (added in Phase 2: CLAUDE.md asks for it when the pipeline changes; the light-core bullet and § 7's This Week note). Review fixes added `python/engine/tests/test_fixture_seed.py` (the seeder's drift refusal). Close-out added `python/engine/src/engine/core/__init__.py` (its docstring, approved at close-out).

**Test strategy**

- AC-1 to AC-5: `python/api/tests/test_api_slate.py` — the fixture slate at the slate clock (counts, rules, shell), Purdue @ Ohio State and Kansas State @ Utah against the views and `engine.core` called directly, the row states, the Ole Miss @ LSU and Tulane @ Memphis picks, week 5, the off-season clock, and a no-lines week built under `model_rows`' throwaway sport through `slate.load(conn, …)`.
- AC-6: the same file — a barrier counts 5 statements in one wave; no token and a bad token are rejected; `pnpm test`'s drift check (`web/lib/api-types.test.ts`) covers the generated types.
- Filler: `python/db/tests/test_filler_schema.py` — the file equals `build()`, every edge < 1.0, ratings below Utah with no ties.

**Risks**: the engine as a workspace dependency of the API is proven on Vercel only by the preview deploy (and `/api/py/health` there, which imports `api.main`).

## Review log

_Filled by /implement-task. One line per round._

- Verify R1 PASS | Audit R1 CHANGES (1 non-discriminating: the light-core import scan passed with nothing to find) → fixed and checked against main | Spec R1 APPROVE | Schema R1 CHANGES (2 major: `pick_outcomes` read below its window unfiltered; the database's and the API's clocks mixed; 3 minor) → fixed (EXPLAIN tests, one clock, the shell's season rule, a drift refusal in the seeder) | Verify R2 PASS | Schema R2 APPROVE (2 minor docstrings, fixed) | UI not run (`ui: false`; the only web change is the generated types)

## Blocked

_Only if status is Blocked: what failed, what was tried, best hypothesis, decision needed._

## Metrics

- Verify rounds: 2
- Review rounds: 2
- First-pass AC FAILs: 0
- Plan revisions after approval: 2 (`docs/model-guide.md` added in Phase 2; `engine/core/__init__.py`'s docstring at close-out)
