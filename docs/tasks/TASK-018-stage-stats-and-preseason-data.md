---
id: TASK-018
title: Stage box scores, advanced stats, play-by-play, preseason inputs and benchmark ratings
status: Ready
depends_on: [TASK-017]
size: M
model: opus
autonomy: attended
ui: false
plan_status: none
planned_at_commit:
---

# TASK-018 — Stage box scores, advanced stats, play-by-play, preseason inputs and benchmark ratings

## Goal

The same `engine transform --rebuild` also stages team box scores, advanced stats, plays, drives, talent, returning production, recruiting and SP+/FPI/Elo. These are the inputs the feature tables, preseason priors and baselines read.

## Context

- Task list: `docs/08-tasklist.md` › M2 › M2.3, second half (split from M2.3; TASK-017 is the first half and owns the runner this task extends).
- Data model: `docs/03-data-model.md` › Data sources › CFBD (`/games/teams`, `/stats/game/advanced` with garbage time filterable, `/plays`, `/drives`, `/talent`, `/player/returning`, `/recruiting/teams`, `/ratings/sp|fpi|elo`); › Lake layout (`staging/team_games.parquet`, `staging/plays/season=YYYY/…`); › Data quality checks ("every FBS game has advanced stats").
- Model: `docs/04-model.md` § 9.2 (preseason inputs use values published before that season; SP+, FPI and Elo count as baselines only if published before the game, otherwise they're labeled "hindsight benchmark"); § 2 Rung 2 (off/def efficiency with rush/pass splits, success rate, explosiveness: the columns TASK-019 reads).
- Decisions: D-027, D-042.
- **Decide at the plan gate:** which advanced-stats variant is pulled and staged (garbage time excluded, included, or both) and how the choice is recorded; how a benchmark row records when its value was published (a pre-game weekly value or season-final), so M3.4 can tell the two apart; play/drive partitioning by season; how many calls recording one fixture per endpoint costs (a handful, counted by the budget tracker).
- *From TASK-017 (docs/plans-2026-10-19):* `engine.transform` keeps a `TABLES` registry and `engine.transform.quality` a `CHECKS` registry: register the new staged tables and the advanced-stats check there. Raw files are read through the `Lake` protocol into pyarrow and registered in DuckDB in memory (no `httpfs`, D-112), so a full backfill of plays may need staging one season at a time.

## Acceptance criteria

- [ ] AC-1: Given the lake fixture extended with one recorded response per endpoint, `engine transform --rebuild` writes staging tables for team box scores, team-game advanced stats, plays, drives, talent, returning production, recruiting and benchmark ratings. Each table's row count equals its raw fixture's record count after dedupe (one assertion per table).
- [ ] AC-2: Staged advanced stats have exactly one row per (game, team) and record whether garbage time was excluded. A raw pull that repeats a (game, team) keeps the newest pull's values.
- [ ] AC-3: Given a fixture FBS final game with no advanced-stats row, the data-quality run exits non-zero and names that game's `source_id`; with the row present it exits 0.
- [ ] AC-4: Every staged benchmark-rating row says whether its value was published before a given week or is season-final. Given a season-final SP+ fixture, every row is marked season-final.
- [ ] AC-5: The rebuild still makes zero API calls (TASK-017's no-network test covers the new tables).

## Out of scope

- Point-in-time feature tables (TASK-019).
- Computing our own EPA from plays (`/ppa/predicted`), and any use of the benchmarks (M3.4).
- Building priors from talent, returning production and recruiting (M4.2).
- Backfilling these endpoints (TASK-021).

## Files likely touched

- `python/engine/src/engine/transform/stats.py`: staging SQL for the stats and preseason endpoints (new).
- `python/engine/src/engine/transform/__init__.py`: register the new tables with the runner.
- `python/engine/src/engine/transform/quality.py`: the advanced-stats check.
- `python/engine/tests/test_transform_stats.py` (new); `python/engine/tests/fixtures/lake/`: one recorded response per endpoint.

## Verification

- Automated: `test_transform_stats.py` (AC-1, AC-2, AC-4), `test_quality.py` (AC-3), `test_transform.py` (AC-5).
- Manual: record one week of each week-level endpoint into the local lake (calls shown by the ledger), run `engine transform --rebuild` → each staged table is non-empty and the DQ report exits 0.

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
