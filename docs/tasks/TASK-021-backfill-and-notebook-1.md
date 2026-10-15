---
id: TASK-021
title: Backfill 2014–2025 and 2026 to date, then explore it in notebook #1
status: Draft
depends_on: [TASK-015, TASK-017, TASK-018, TASK-020]
size: M
model: opus
autonomy: attended
ui: false
plan_status: none
planned_at_commit:
---

# TASK-021 — Backfill 2014–2025 and 2026 to date, then explore it in notebook #1

## Goal

The lake holds every CFBD endpoint the model uses for 2014–2025 and 2026 to date, locally and in R2, and the dev database is published from it. Notebook #1 records the closing-line MAE that every later model is measured against.

## Context

- Task list: `docs/08-tasklist.md` › M2 › M2.6. Waits for M1.3 (`release`, TASK-005, done) and the R2 lake bucket (TASK-015's owner prerequisite).
- Data model: `docs/03-data-model.md` › Data sources › CFBD (the endpoints and the ~500-call backfill estimate: season-level ~120 calls, weekly plays and drives ~384).
- Model: `docs/04-model.md` § 9.6 (Phase 1's bar: record closing-line MAE for 2014–2025, the benchmark every later phase is compared with); § 9.3 (closing line: `consensus` when present, otherwise the median); § 9.1 (the lake starts in 2014); § 8 Learning path (the notebooks).
- Architecture: `docs/02-architecture.md` › Components › 4 Jobs (`backfill`: manual, historical pulls); › Repository layout (`python/notebooks/`, marimo or Jupyter); › Non-functional requirements (CFBD calls ≤ 5,000 a month).
- Decisions: D-026 (~500 calls, about 10% of a month), D-027 (never re-fetch completed weeks).
- **Stop and ask:** before spending any calls, the plan shows the dry-run estimate per endpoint and the total, and the owner approves it. The real run happens with the owner's go-ahead in the session.
- **Production:** the tasklist's "backfill reaching prod" happens through TASK-022's first workflow run, the only path that publishes to production (local commands against production are denied, D-015). This task publishes to dev.
- **Decide at the plan gate:** marimo or Jupyter, and where notebook dependencies live (a dependency group, not the API's); the pull order, so a run stopped by the budget resumes without re-fetching; how the local lake is copied to R2 (written to both during the run, or synced after); where the benchmark number is recorded (04 § 9.6 is a planning doc, so the edit needs the owner's approval).

## Acceptance criteria

- [ ] AC-1: `engine backfill --from 2014 --to 2026 --dry-run` prints the calls per endpoint and the total, makes zero API calls, and counts only pulls not already in the lake. After a partial backfill, the dry run estimates only what's left.
- [ ] AC-2: A backfill that would exceed the month's budget stops before the call that would exceed it, and a re-run resumes without re-fetching anything already saved for a completed week or season. The ledger's total across both runs equals the first dry-run estimate, apart from calls for the current, incomplete week.
- [ ] AC-3: After the owner-approved backfill, `engine transform --rebuild` and the data-quality checks exit 0 on the full lake, or the PR lists each failure with its cause and how it's handled. `engine publish --target dev` then loads it, and the dev database's 2026 FBS team count equals the staged 2026 FBS team count.
- [ ] AC-4: Notebook #1 (`python/notebooks/01-explore.*`) runs top to bottom from the lake with zero API calls and shows home-field advantage by season, the margin distribution, and closing-line MAE for each season 2014–2025 and pooled. The pooled MAE is recorded where the plan gate agreed.
- [ ] AC-5: The R2 lake holds the same `raw/cfbd/` files as the local lake: a listing of each shows the same file count and names.

## Out of scope

- Scheduled jobs and publishing to production (TASK-022).
- Notebooks #2–3 and any rating or model work (M3).
- NFL data from nflverse (M6, D-039).
- Weather and Odds API pulls (Phase 5, later).

## Files likely touched

- `python/engine/src/engine/ingest/backfill.py`: the plan, dry run and resumable run (new).
- `python/engine/src/engine/cli.py`: `engine backfill`.
- `python/engine/tests/test_backfill.py`: AC-1, AC-2 on a fake client and a small lake (new).
- `python/notebooks/01-explore.py` (or `.ipynb`): notebook #1 (new).
- `python/pyproject.toml`: the notebook dependency group.
- `docs/04-model.md` § 9.6, or the place agreed at the plan gate: the recorded benchmark.

## Verification

- Automated: `test_backfill.py` (AC-1, AC-2, no network); the existing transform and publish tests.
- Manual: the dry run, then the owner-approved backfill (calls shown by the ledger); rebuild, checks and dev publish; run the notebook top to bottom; list the R2 lake against `data/raw/cfbd/`.

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
