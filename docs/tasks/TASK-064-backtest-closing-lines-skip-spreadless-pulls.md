---
id: TASK-064
title: Skip spread-less pulls in the backtest's closing_lines()
status: Review             # Draft | Ready | In progress | Review | Done | Blocked
depends_on: [TASK-060]            # e.g. [TASK-012, TASK-013]
size: S                   # S (<=3 files, one layer) | M (<=8 files, <=2 adjacent layers) | split if larger; L only with workflow.splitPolicy never-split
model: sonnet             # implementation model; planning always uses Opus
autonomy: attended        # attended | unattended (see /new-task rules)
ui: false                 # true if any AC has a visible or interactive outcome
plan_status: approved     # none | proposed | approved
planned_at_commit: 8a4cc66 # set when the plan is written; used for the staleness check
---

# TASK-064 — Skip spread-less pulls in the backtest's closing_lines()

## Goal

The backtest's closing line uses the last pull that quoted a spread, the way `game_market` does (D-162), so a final pull with only a total or moneyline doesn't drop the game's close.

## Context

- Task list: `docs/08-tasklist.md` › M5 › M5.12.
- *From TASK-060 (PR #143):* `engine.transform.market.closing_lines()` (`python/engine/src/engine/transform/market.py`) says it applies `game_market`'s rule but takes the last pull (or CFBD's close) even when it has no spread, giving the game a NULL closing spread. `game_market` now skips such pulls for the spread (D-162). `test_closing_lines_equal_game_market` compares the two.
- Check the backtest golden metrics (`python/engine/tests/test_backtest_golden.py`) before and after: if they move, say so in the plan.
- Decisions: D-120, D-121, D-162.

## Acceptance criteria

Each item names an observable result and an expected value or state.

- [x] AC-1: Given a game whose last pre-kickoff pull quoted only a total and whose earlier pull quoted −3.5, `closing_lines()` gives `spread_home` −3.5 and `closing_from` `last_snapshot` (expected: not NULL).
- [x] AC-2: Given a game whose untimed CFBD `closing` rows quote no spread, the spread falls to the last snapshot that did, as in `game_market`.
- [x] AC-3: `test_closing_lines_equal_game_market` also covers a spread-less pull, and the backtest golden metrics are unchanged, or the plan names each change and the owner approves it.

## Out of scope

- `game_market` itself (TASK-060).

## Files likely touched

- `python/engine/src/engine/transform/market.py`: skip spread-less rows for the spread
- `python/engine/tests/test_market.py`: AC-1 to AC-3

## Verification

- Automated: `uv --directory python run pytest engine/tests/test_market.py engine/tests/test_backtest_golden.py`
- Manual: none.

## Follow-ups

_Work noticed during this task and deliberately left out. Each bullet ends `→ <path> § <section>` (where it was placed) or `→ not tracked: <reason>`. See `.claude/skills/track-follow-ups/classify.md`; the PR's Follow-ups section is copied from here._

- A book whose first pull after the cutoff quotes no spread keeps that row as its close, and `map_lines` drops that book's later pulls; the view and `closing_lines()` still agree on it. → not tracked: already a D-120 revisit trigger (schema review R1 noted it as unchanged by this PR)
- Schema review R1 (MINOR): no test for the opener/CLV pair after a spread-less final pull, nor for total-only and moneyline-only games. → not tracked: done in this PR (plan revision), three tests in `test_market.py`, each failing on main's `market.py`

## Plan

_Written by /plan-batch or /implement-task Phase 1. Approved by the user (plan_status: approved) before any code is written._

Approved by the owner in session, 2026-11-10.

**Steps**
1. Tests first, in `python/engine/tests/test_market.py`, each seen failing on the old code:
   - `lines()` takes an optional `totals=`, and `_pull` accepts a `None` spread.
   - `test_a_spreadless_last_snapshot_keeps_the_earlier_spread` (AC-1): a pull quoting −3.5, then a later pull before kickoff with a total of 50 and no spread → spread −3.5, `closing_from` `last_snapshot`, total 50.
   - `test_a_spreadless_cfbd_close_falls_to_the_last_snapshot` (AC-2): CFBD's `closing` rows quote only a total (48) and an earlier snapshot quotes −4.0 → spread −4.0, `closing_from` `last_snapshot`, total 48 (from the close, as in `game_market`).
   - AC-3: add an `eq-spreadless` game to `test_closing_lines_equal_game_market`: a −7.0/55 snapshot, a later snapshot with a total and no spread, and a CFBD close with a total and no spread. The view and `closing_lines()` must both give (−7.0, 57.0, median, last_snapshot).
2. In `python/engine/src/engine/transform/market.py`, add `_closing_group(rows, cutoff, price)`: CFBD's `closing` rows that quoted the price, else the latest snapshot before the cutoff that quoted it. Choose the spread and the total through it separately (D-162). `source`, `closing_from` and the opener books (the CLV pair) follow the spread's pull; with no spread they are NULL, as in the view. A game gets a row when it has a closing spread or a closing total (a game priced only by moneyline no longer gets an all-NULL row; the harness grades only games with a spread). Update the module docstring.
3. Run `engine/tests/test_backtest_golden.py` before and after. The golden fixture's lines all quote spreads, so no change is expected; if a number moves, stop and show the owner.
4. Docs: correct any line in `docs/model-guide.md` that describes the closing line; at close-out, tick M5.12 in `docs/08-tasklist.md` and the roadmap.

**Files**
- `python/engine/src/engine/transform/market.py`: choose each price's closing pull separately
- `python/engine/tests/test_market.py`: AC-1 to AC-3
- `docs/model-guide.md` (not in "Files likely touched"): one line, only if it describes the closing line

**Test strategy**
- AC-1: `test_market.py::test_a_spreadless_last_snapshot_keeps_the_earlier_spread`
- AC-2: `test_market.py::test_a_spreadless_cfbd_close_falls_to_the_last_snapshot`
- AC-3: `test_market.py::test_closing_lines_equal_game_market` (the `eq-spreadless` game) and `test_backtest_golden.py` unchanged

**Risks:** low. `game_market`'s opening and current lines are out of scope and untouched.

**Follow-ups:** none at plan. No new decision: this applies D-162, whose revisit trigger names this change (M5.12).

## Review log

_Filled by /implement-task. One line per round._

Verify R1 PASS | Audit R1 PASS | Spec R1 APPROVE | Schema R1 APPROVE (2 MINOR test gaps, fixed in this PR)

## Blocked

_Only if status is Blocked: what failed, what was tried, best hypothesis, decision needed._

## Metrics

- Verify rounds: 1
- Review rounds: 1
- First-pass AC FAILs: 0
- Plan revisions after approval: 1 (three reviewer-requested tests added to `test_market.py`; no new file, no change to the approach)
