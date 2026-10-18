---
id: TASK-017
title: Stage games, teams, venues, calendar and lines with transform --rebuild and data-quality checks
status: Ready
depends_on: [TASK-015]
size: M
model: opus
autonomy: attended
ui: false
plan_status: none
planned_at_commit:
---

# TASK-017 — Stage games, teams, venues, calendar and lines with transform --rebuild and data-quality checks

## Goal

`engine transform --rebuild` recreates the staged games, teams, venues, calendar and lines tables from the raw lake alone, with no API calls. The data-quality checks report every problem and stop anything downstream from publishing bad data.

## Context

- Task list: `docs/08-tasklist.md` › M2 › M2.3, first half. **Split from M2.3** under `workflow.splitPolicy: split`: one task for every staged table plus the checks would touch far more than 8 files. This half stages what TASK-020 publishes; TASK-018 stages the stats and preseason tables on the same runner.
- Data model: `docs/03-data-model.md` › Lake layout (`staging/` = cleaned, typed, deduped, "latest version" of each entity; DuckDB builds it from `raw/`); › Data quality checks.
- Architecture: `docs/02-architecture.md` › Components › 1 (`transform`); › Non-functional requirements › Data correctness (publishing stops when a check fails; nothing partial reaches Postgres); › Testing strategy › Levels › Data / ETL (`transform --rebuild` with zero API calls, on a small lake fixture of recorded responses).
- Model: `docs/04-model.md` § 9.3 (closing line: the `consensus` provider's spread when present, otherwise the median across providers). Staging keeps every provider's row; choosing between them happens in `game_market` (TASK-020) and the backtest.
- Decisions: D-027 (rebuild from raw with zero API calls), D-002, D-098 (raw `/games` JSON already in the lake).
- Rules: `.claude/rules/python.md` (destructive commands such as `--rebuild` check `LIVE` and refuse).
- **Roadmap note to resolve:** Phase 0's item "`python/db/views/` applied after every migration" says "rebuild pending, with `transform --rebuild` in M2.3". `transform` writes only to the lake. If this task doesn't touch Postgres, the plan says where a dev-DB rebuild (and its view re-apply) will land and updates that note. *Direction agreed with the owner (2026-10-15):* `transform --rebuild` stays lake-only. The roadmap note is reworded to say the database half lands with a dev-DB rebuild command when one is first needed, and that is recorded as a follow-up.
- **Decide at the plan gate:** how "latest version" is picked when one entity appears in several raw pulls (the newest `fetched_at` wins); whether lines stage every pull (each is a snapshot) or only the newest; the staging file layout; DuckDB as an `engine[train]` dependency (D-004); and how the DQ report is shown (CLI output and an exit code).
- *From TASK-015 (PR #54):* CFBD's `/lines` takes no `classification`, so a week's raw lines include games with no FBS team (2025 week 1 has Colgate–Monmouth, with one provider and null opening lines and moneylines). Staging lines should keep only games present in staged `/games`, or count the extras in a data-quality check.

## Acceptance criteria

- [ ] AC-1: Given the lake fixture of recorded responses, `engine transform --rebuild` writes `staging/` tables for games, teams, venues, calendar and lines. Running it twice gives identical rows. A test that makes any CFBD client or HTTP transport raise when constructed still passes, so the rebuild makes zero API calls.
- [ ] AC-2: Given two raw pulls of the same game (an earlier one scheduled, a later one final), staged games hold one row for that game, with the final score from the later pull.
- [ ] AC-3: With `LIVE=true`, `engine transform --rebuild` exits non-zero with a message naming `LIVE`, and `staging/` is unchanged.
- [ ] AC-4: Given a fixture final game with no score, or two games with the same teams on the same date, the data-quality run exits non-zero and names each offending game's `source_id`. On the clean fixture it exits 0.
- [ ] AC-5: Given an FBS-vs-FBS game in a 2014–2025 season with no line from any provider, staging marks it as missing a closing line, the DQ report lists it, and the check passes. An unmarked game with no line fails the check.

## Out of scope

- Staging box scores, advanced stats, plays, drives, talent, returning production, recruiting and benchmark ratings, and the "every FBS game has advanced stats" check (TASK-018).
- Feature tables (TASK-019).
- Publishing to Postgres (TASK-020).
- The team-mapping check for non-CFBD names (Splash): it applies once contest pastes are stored (M6).

## Files likely touched

- `python/engine/src/engine/transform/__init__.py`, `python/engine/src/engine/transform/staging.py`: the runner and the staging SQL (new).
- `python/engine/src/engine/transform/quality.py`: the data-quality checks (new).
- `python/engine/src/engine/cli.py`: `engine transform --rebuild` and `engine check`.
- `python/engine/pyproject.toml`: DuckDB in the heavy extra.
- `python/engine/tests/test_transform.py`, `python/engine/tests/test_quality.py` (new); `python/engine/tests/fixtures/lake/`: recorded responses.
- `docs/06-roadmap.md` › Phase 0: the views/rebuild note (a follow-up placement, if the plan changes where it lands).

## Verification

- Automated: `test_transform.py` (AC-1 to AC-3), `test_quality.py` (AC-4, AC-5).
- Manual: on the local lake from D-098, `uv --directory python run engine transform --rebuild` → staged games match the raw `/games` files' game count, and the DQ report prints with exit 0.

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
