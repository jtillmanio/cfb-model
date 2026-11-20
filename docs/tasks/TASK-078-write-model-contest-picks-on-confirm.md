---
id: TASK-078
title: Write the model's contest picks when a contest import is confirmed
status: Draft
depends_on: [TASK-071]
size: M
model: opus
autonomy: attended
ui: false
plan_status: none
planned_at_commit:
---

# TASK-078 — Write the model's contest picks when a contest import is confirmed

## Goal

Every confirmed contest paste also records the model's pick on each slate game it predicts, at that paste's contest line, so the Contest page's "model's top 4" record (`contest_results`) grades real production weeks, not only the fixture's.

## Context

- Task list: `docs/08-tasklist.md` › M6 › M6.10.
- Decided at TASK-071's plan gate (D-174): the model's contest picks are written **on the import's confirm**, in the confirm's transaction. Confirm is the only writer sure to run between a paste and the week's first kickoff, which is where `contest_results` fixes the model's top N (D-171). The `lines` job (10 AM ET daily, 9 PM ET Thu and Fri) would miss a Saturday-morning paste before a noon kickoff.
- *From TASK-073 (feat/073-contest-ranked-slate-tray-results):* Results & standing's "This week so far" lists the model's top 4 from the slate, but its record, points and pending count come from `contest_results`, so on a week whose contest has no model contest picks (a freshly pasted week, until this task) it reads "0-0 · 0 pending" beside four listed picks. Once this task writes the picks on confirm the two agree; check that screen then.
- What to write (D-170, D-171, TASK-068's note in TASK-071): one `picks` row per slate game with a prediction from the shown version (CFB only: NFL has no prediction, D-170). The row sits on the game's new `contest_line_id`, with no `line_snapshot_id` or price, and side and `model_prob` equal to what `GET /contests/{id}` shows for the game (`engine.core`'s `displayed_prob` at the contest line, as `api/contest.py` `_model` computes it). It also carries `edge_pts` (the blended edge), `expected_value` = 2p − 1 at even money, `tier` NULL, `stake_units` 1 and `created_at` the API's clock.
- **Open question for the plan:** a game with an FCS team is never picked in the market (D-047, `engine.sports.cfb.teams.pickable`), but the API can import only `engine.core` (hard rule 5). Decide whether the API checks the teams' `team_seasons.division`, or the rule moves into the light core.
- **Open question for the plan:** a new prediction after the paste (a re-rate mid-week) leaves the contest picks on the older prediction until the next paste. Decide whether that is acceptable or whether `rate-and-predict` also re-writes them.
- Code: `python/api/src/api/contest_import.py` (`confirm`), `python/api/src/api/contest.py` (`_model`, the page's computation, which must agree), `python/engine/src/engine/publish/picks.py` (the market writer's rules).
- Decisions: D-047, D-140, D-143, D-158, D-170, D-171, D-172, D-174.

## Acceptance criteria

- [ ] AC-1: Given the seeded DB and the clock at Thu 2026-10-08 10:00 PM ET, confirming the Week 6 paste inserts exactly 6 `picks` rows with a `contest_line_id`, one per CFB slate game, and none for the 4 NFL games. Each row's `contest_line_id` is the line that confirm inserted, its side and `model_prob` equal the side and `cover_prob` that `GET /contests/{id}` returns for that game, its `expected_value` is 2 × `model_prob` − 1, its `tier` is NULL and its `created_at` is the confirm's time (test).
- [ ] AC-2: After that confirm, `contest_results`' model rows for the shown version and Week 6 are the 4 games the page marks `top_n`: Texas vs Oklahoma, Ole Miss @ LSU, Purdue @ Ohio State and Colorado @ BYU (test).
- [ ] AC-3: A confirm the API refuses (422 `unresolved`) writes no pick, and a game at or past its cutoff when confirm runs gets no pick (test).
- [ ] AC-4: A second confirm before the first kickoff with one line changed writes a new pick on each new contest line, and `contest_results`' top N reads the newest ones (test).

## Out of scope

- NFL contest picks (no NFL model until Phase 8, D-170).
- Re-ranking or storing the top N (it stays a view, hard rule 1).
- The Contest screen (TASK-072, TASK-073).

## Files likely touched

- `python/api/src/api/contest_import.py`: write the picks inside `confirm`
- `python/api/src/api/contest.py`: share the page's per-game computation with the writer
- `python/api/tests/test_api_contest_import.py`: AC-1 to AC-4
- `docs/decisions.md`, `docs/model-guide.md`

## Verification

- Automated: `uv --directory python run pytest api/tests/test_api_contest_import.py api/tests/test_api_contest.py` passes, and so does the whole suite.
- Manual: through the test client at Thu 10:00 PM, confirm the Week 6 paste, then GET the contest page → expected: its `top_n` games are the four `contest_results` grades as the model's.

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
