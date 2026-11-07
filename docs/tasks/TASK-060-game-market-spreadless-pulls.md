---
id: TASK-060
title: Keep game_market's spread when a pull quotes no spread
status: Review
depends_on: []
size: S
model: sonnet
autonomy: attended
ui: false
plan_status: approved
planned_at_commit: a6beb60
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

- [x] AC-1: Given a game with a Sunday pull at −3.5 (total 48.5) and a newer pull before kickoff quoting only a total of 49.5, `game_market` gives `current_spread_home` −3.5 (expected: not NULL), and the current total the plan's rule gives.
- [x] AC-2: Given the same game after kickoff with no CFBD close, `closing_spread_home` is −3.5 and `closing_from` is `last_snapshot`; a pick at −2.5 home there has `clv` +1.0 in `pick_outcomes`.
- [x] AC-3: Given a game whose first snapshot quoted only a moneyline and whose second quoted −7, `opening_spread_home` is −7 when there is no untimed `opening` row.
- [x] AC-4: The view's `EXPLAIN` test still shows no full scan of `line_snapshots` for one game (`.claude/rules/database.md` › Views & queries), and the existing `game_market` tests pass unchanged.

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

- `docs/04-model.md` › Closing line (backtest): the "Live, the `game_market` view's closing line…" sentence becomes "…else the last snapshot *that quoted a spread* before kickoff…" (approved at plan) → docs/04-model.md § Closing line (backtest)
- Candidate decision, amends D-120: each of `game_market`'s prices is the newest pull (by its line's rule) that quoted that price; spread and total are chosen separately; `*_captured_at`, `*_source` and `closing_from` describe the spread's pull (approved at plan) → docs/decisions.md § D-162
- `engine.transform.market.closing_lines()` says it applies `game_market`'s rule but still takes a last pull (or CFBD close) with no spread; make it skip spread-less pulls for the spread the same way, checking the backtest golden metrics (approved at plan) → docs/tasks/TASK-064-backtest-closing-lines-skip-spreadless-pulls.md (new, Draft)

## Plan

**Open question settled (option B, owner 2026-11-07):** each price follows its line's rule separately. The spread is the newest (or earliest, for the opening) pull that quoted a spread; the total is the same over pulls that quoted a total. `*_captured_at`, `*_source` and `closing_from` describe the spread's pull. AC-1's current total is therefore **49.5**.

**Steps**
1. Tests first, shown failing on the current view: AC-1 and AC-3 in `test_game_market.py`, AC-2 in `test_pick_outcomes.py`.
2. View: the three spread laterals (opening, current, closing) add `ls.spread_home IS NOT NULL`, so untimed `opening`/`closing` rows without a spread also fall through to snapshots. Three matching total laterals (`ls.total IS NOT NULL`) give `*_total`. Each lateral still reads only the game's rows through the `(game_id, captured_at)` index. Header comment updated.
3. AC-4: the existing `test_single_game_read_uses_index` walks every `line_snapshots` scan node, so it covers the new laterals unchanged; the existing tests run unchanged.
4. Docs and comments (below).

**Files**
- `python/db/views/010_game_market.sql` — spread laterals skip spread-less pulls; total laterals; header comment
- `python/db/tests/test_game_market.py` — AC-1, AC-3; `_line` accepts `spread=None` (existing calls unchanged)
- `python/db/tests/test_pick_outcomes.py` — AC-2 *(not in Files likely touched)*
- `python/db/tests/model_rows.py` — `line()` takes optional `total`, `spread_home` may be None *(not in Files likely touched)*
- `docs/03-data-model.md` › Views — `game_market`'s rule as built
- `python/api/src/api/slate.py` — `_market` docstring's "game_market then reports its NULL spread" is no longer true *(comment only, not in Files likely touched)*

**Test strategy**
- AC-1: `test_game_market.py::test_current_spread_skips_a_total_only_pull` (current −3.5 at the Sunday pull, current total 49.5)
- AC-2: `test_pick_outcomes.py::test_clv_skips_a_total_only_last_pull` (closing −3.5, `last_snapshot`, home pick at −2.5 → clv +1.0)
- AC-3: `test_game_market.py::test_opening_skips_a_moneyline_only_first_pull` (opening −7)
- AC-4: existing `test_single_game_read_uses_index` and the rest of the file, unchanged

**Risks:** six laterals instead of three (each one index read). `/slate`'s current line already follows the new rule, so API and web output don't change.

## Review log

Verify R1 PASS | Audit R1 PASS | Spec R1 APPROVE | Schema R1 APPROVE (two optional MINOR tests added after)

## Blocked

_Only if status is Blocked: what failed, what was tried, best hypothesis, decision needed._

## Metrics

- Verify rounds: 1
- Review rounds: 1
- First-pass AC FAILs: 0
- Plan revisions after approval: 0
