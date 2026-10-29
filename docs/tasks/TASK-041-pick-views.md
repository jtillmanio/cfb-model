---
id: TASK-041
title: Add the current_picks, pick_outcomes and model_record views
status: Ready
depends_on: [TASK-040]
size: M
model: opus
autonomy: attended
ui: false
plan_status: none
planned_at_commit:
---

# TASK-041 — Add the current_picks, pick_outcomes and model_record views

## Goal

The database answers "what is the model's pick on this game now", "did each pick win, lose or push, and did it beat the closing line" and "what is the model's record, units, ROI and average CLV, by season, week, tier and edge size" straight from the stored picks, scores and lines, with nothing graded or stored by a job.

## Context

- Task list: `docs/08-tasklist.md` › M4 › M4.6.
- Data model: `docs/03-data-model.md` › Views (`current_picks`: latest pick per game, model version, market and line source; `pick_outcomes`: per pick, result `won|lost|push|void|pending` from final scores, the closing line, CLV in points; `model_record`: rollups by model version, season, week, tier and edge bucket of W-L-P, win %, units, ROI, avg CLV; the footer: views re-applied after every migration, a test per view, single-item reads filter before aggregating, checked with `EXPLAIN`); › Models & outputs › `picks` (as TASK-040 settles it).
- Model: `docs/04-model.md` § 9.3 (pushes count in W-L-P, are left out of win %, and earn 0; units at −110, a win +1.0u and a loss −1.1u; live CLV is measured from each pick's own snapshot against the close); § 9.4 (pick buckets 2.5–3.5, 3.5–5.0, 5.0–7.0, 7.0+ are display only).
- Product: `docs/01-product.md` › F-09 (record strip and KPI tiles read these views; backtest numbers never added into live totals; "there is no grading job"), F-10 (CLV on every pick, "so far" before kickoff and final against the closing line after).
- Architecture: `docs/02-architecture.md` › Components ("Grading is not a job"); › Testing strategy › Levels › Integration: database (`model_record` for v1.0 in 2026 = 31-24-1, +4.6u); › Seed data, row "Predictions and picks".
- Decisions: D-132 (CLV sign: `moved = line picked at − close`, positive for a home pick when the close moved past it, negated for an away pick; ROI = units ÷ (1.1u × (wins + losses)), a push refunded), D-077 (pick buckets are display only), D-071 (live and backtest never summed), D-120 (`game_market`'s closing line, NULL until the cutoff), D-136 (a view reads its version's newest succeeded run), D-047.
- Rules: hard rule 1 (results, records, CLV and the current pick are views); `.claude/rules/database.md` › Views & queries; `python/db/views/README.md`.
- Pattern: `python/db/views/020_latest_team_ratings.sql` and `030_team_rankings.sql` with `python/db/tests/test_team_rankings.py` (a view over another view, the `EXPLAIN` check); `010_game_market.sql` for the closing line.
- **Concept:** a result stored in a column goes wrong the moment a score is corrected or a game is canceled; a view recomputes it from the score and line every time it's read, so the record can't drift from the games it grades.
- **Open question for the plan gate, CLV's sign:** F-10 and F-02 show Ole Miss "Picked at −2.5 → now −3.5 · CLV +1.0 · moved our way", but under D-132 an away pick at LSU −2.5 against a close of LSU −3.5 got Ole Miss +2.5 when the close offered +3.5, so its CLV is −1.0. Numbers follow 04 and the decisions log, not the design (CLAUDE.md › Which document wins); the plan confirms D-132's sign with the owner and the PR fixes F-10's example.
- **Decide at the plan gate:** which picks the record grades when a game has several (the current pick at kickoff only, as TASK-040's re-evaluation rule leaves them; never a superseded one twice); how a "no pick now" row from TASK-040, if it exists, shows in `current_picks`; `void` for canceled and postponed games and how it counts (0 units, out of win %); CLV before kickoff ("so far", against `game_market`'s current line) as a column or left to the API; the edge bucket's source (the pick's own `edge_pts`); whether `model_record` is one view with `GROUPING SETS` or one row per dimension and bucket; whether it counts contest picks (recommended: market picks only; M6.2 grades contest picks with the contest's push rule); week as the game's week.
- *From TASK-040 (feat/task-040-picks-table):* a re-evaluation that drops a pick is a pass row (`side` and `tier` NULL, `stake_units` 0; CHECK `ck_picks_pass_or_stake`): when it is the latest row per game, version and market, `current_picks` shows no pick and the record grades nothing for that game. A row is written only when the side or tier changes, so a game's earlier rows are superseded picks. `picks` carries `model_version_id` and `game_id`, indexed `(game_id, model_version_id, created_at DESC)` and `(model_version_id, game_id)` for these views; `edge_pts` is signed (> 0 likes home). D-140 has the rest, including the fixture's Ole Miss CLV sign conflict.

## Acceptance criteria

- [ ] AC-1: Given a game with two v1.0 market picks, the second made later at a new line snapshot, `current_picks` returns only the second for (game, v1.0, spread, market); a second version's pick on the same game is its own row; on the seeded test DB v1.0 has 9 current picks for 2026 week 6.
- [ ] AC-2: `pick_outcomes` grades each pick against the line it was made at: given test picks on final games, a home pick at −3 wins on a margin of 4, pushes on 3 and loses on 2 (units +1.0, 0, −1.1), an away pick mirrors it, a pick on a `scheduled` or `in_progress` game is `pending` with NULL units, and one on a `canceled` or `postponed` game is `void` with 0 units.
- [ ] AC-3: `pick_outcomes` CLV is the line picked at against `game_market`'s closing line with D-132's sign (a home pick at −2.5 closing at −3.5 is +1.0; an away pick at −2.5 closing at −3.5 is −1.0), and NULL while the closing line is NULL.
- [ ] AC-4: On the seeded test DB, `model_record` for v1.0, 2026, weeks 1–5 reads 31-24-1, win % 56.4 (pushes left out), +4.6u, ROI +7.6% and avg CLV +0.9; by tier A 7-3, B 12-9-1, C 12-12 with C at −1.2u; by week, units summing to +1.8, +0.5, +2.9, +2.2, +4.6 cumulatively; for week 6, 1-0 with 8 pending and +1.0u. Each pick bucket (2.5–3.5, 3.5–5.0, 5.0–7.0, 7.0+) counts exactly the weeks 1–5 picks whose `abs(edge_pts)` falls in it.
- [ ] AC-5: A game whose pick was superseded before kickoff counts once in `model_record`, graded at the current pick's line (a test inserts the two picks and reads the record).
- [ ] AC-6: Reading `current_picks` or `pick_outcomes` for one game, and `model_record` for one model version and season, uses an index on `picks` (the `EXPLAIN` check from `test_team_rankings.py` finds no sequential scan on `picks`), and all three views are listed in `python/db/views/README.md` with their tests.

## Out of scope

- Writing picks (M4.8) and the `picks` table itself (TASK-040).
- Contest grading with the contest's push rule and the model's contest top N (M6.2).
- Conference and favorite/underdog breakdowns and calibration bins for the Performance screen (M7.4, from `pick_outcomes` and `model_runs.metrics`).
- Any API endpoint or screen reading the views (M5.5, M5.6, M7.4).
- Backtest records (they live in `model_runs.metrics` and the lake, never in these views, D-071).

## Files likely touched

- `python/db/views/050_current_picks.sql`, `060_pick_outcomes.sql`, `070_model_record.sql`: the views (new).
- `python/db/views/README.md`: list the three views.
- `python/db/tests/test_current_picks.py`, `test_pick_outcomes.py`, `test_model_record.py`: AC-1 to AC-6 (new).
- `docs/03-data-model.md` › Views: the settled rules (which picks count, void, CLV sign).
- `docs/01-product.md` › F-10, F-02: the Ole Miss CLV example, if the sign is confirmed.
- `docs/decisions.md`: the views' rules as a D-### row.

## Verification

- Automated: the three new test files; `pnpm db:check`; `pnpm test`.
- Manual: `pnpm db:migrate:test`, `pnpm db:seed`, then in `psql` → `SELECT * FROM model_record WHERE season = 2026` shows 31-24-1 and +4.6u for weeks 1–5; `SELECT result, clv FROM pick_outcomes` for Ole Miss @ LSU is `pending` with NULL CLV.

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
