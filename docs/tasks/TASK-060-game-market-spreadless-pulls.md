---
id: TASK-060
title: Keep game_market's spread when a pull quotes no spread
status: Draft
depends_on: []
size: S
model: sonnet
autonomy: attended
ui: false
plan_status: none
planned_at_commit:
---

# TASK-060 — Keep game_market's spread when a pull quotes no spread

## Goal

A game's opening, current and closing spreads stay the last ones a book quoted, even when the newest pull quoted only a total or a moneyline, so CLV and "CLV so far" don't go blank.

## Context

- Task list: `docs/08-tasklist.md` › M5 › M5.9.
- *From TASK-055 (PR #138):* the schema review found that `engine publish` writes a `snapshot` row when any price is set (`engine/publish/lines.py`), so a pull with a total or moneyline but no spread is a snapshot with `spread_home` NULL. `game_market` (`python/db/views/010_game_market.sql`) picks each line as one pull (same kind and `captured_at`), so its spread is that pull's NULL. `pick_outcomes`' `clv` and `clv_so_far` read it. `/slate` skips spread-less pulls in its line history and current line (D-158), so it already differs from the view here.
- Data model: `docs/03-data-model.md` › Views (`game_market`), › Games & market (`line_snapshots`). Decisions: D-120 (how the lines are chosen), D-132/D-140 (CLV), D-142.
- Open question for the plan: does the total follow the same rule separately (the newest pull with a total), or does the view keep one pull per line and only skip spread-less ones for the spread?

## Acceptance criteria

- [ ] AC-1: Given a game with a Sunday pull at −3.5 (total 48.5) and a newer pull before kickoff quoting only a total of 49.5, `game_market` gives `current_spread_home` −3.5 (expected: not NULL), and the current total the plan's rule gives.
- [ ] AC-2: Given the same game after kickoff with no CFBD close, `closing_spread_home` is −3.5 and `closing_from` is `last_snapshot`; a pick at −2.5 home there has `clv` +1.0 in `pick_outcomes`.
- [ ] AC-3: Given a game whose first snapshot quoted only a moneyline and whose second quoted −7, `opening_spread_home` is −7 when there is no untimed `opening` row.
- [ ] AC-4: The view's `EXPLAIN` test still shows no full scan of `line_snapshots` for one game (`.claude/rules/database.md` › Views & queries), and the existing `game_market` tests pass unchanged.

## Out of scope

- `/slate`'s own line history (already skips spread-less pulls).
- Which book a pick uses (D-148).

## Files likely touched

- `python/db/views/010_game_market.sql` — the spread laterals
- `python/db/tests/test_game_market.py` — AC-1 to AC-4
- `docs/03-data-model.md` › Views — the rule as built

## Verification

- Automated: `uv --directory python run pytest db/tests/test_game_market.py db/tests/test_pick_outcomes.py`
- Manual: none.

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
