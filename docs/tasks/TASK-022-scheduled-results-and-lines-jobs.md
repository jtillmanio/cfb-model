---
id: TASK-022
title: Schedule the results and lines jobs
status: Ready
depends_on: [TASK-020, TASK-021]
size: M
model: opus
autonomy: attended
ui: false
plan_status: none
planned_at_commit:
---

# TASK-022 — Schedule the results and lines jobs

## Goal

With nobody running anything, Sunday and Monday mornings pick up the weekend's final scores and stats, and lines are snapshotted daily and on Thursday and Friday evenings. Everything is published to production, so the production Teams page lists the real 2026 FBS teams.

## Context

- Task list: `docs/08-tasklist.md` › M2 › M2.7, plus the production half of M2.6 ("backfill reaching prod"; see TASK-021).
- Architecture: `docs/02-architecture.md` › Components › 4 Jobs (`results` Sun 6am and Mon 6am ET: final scores, box scores, advanced stats, PBP for the week; `lines` daily plus Thu–Fri evenings: snapshot CFBD lines); › Environments & databases (`LIVE=true` on production, the unpooled URL for bulk publish); › Non-functional requirements (each run ≤ 10 min, ≤ 1,500 Actions minutes a month, lines refreshed at least daily, ≤ 40 CFBD calls a week in season).
- Data model: `docs/03-data-model.md` › Data sources (calls per week); `docs/02-architecture.md` › Components › 4 (`scores` needs CFBD's scoreboard endpoint, "confirm it's in tier 1 during Phase 1").
- Decisions: D-001 (batch-first), D-015 (`LIVE`, production URL only by explicit flag or workflow environment), D-016, D-027, D-092.
- Existing code: `.github/workflows/release.yml` and `backup.yml` (secrets through `env:`, `concurrency`, job summary), `python/db/src/db/config.py` (target URLs, `refuse_if_live`).
- **Stop and ask:** these workflows write to production. Running one on the branch (`gh workflow run <file> --ref <branch>`, a ready gate for changed workflows) needs the owner's go-ahead in the session.
- **Owner prerequisites:** Actions secrets for `CFBD_API_KEY`, the R2 lake token (read/write on the lake bucket only, not `cfb-backups`) and the production database URL the publish uses; Claude never edits secrets.
- **Decide at the plan gate:** cron in UTC for ET times across daylight saving (two entries per slot, or a time check in the job); how the job gets the lake it transforms (incremental staging, or DuckDB reading R2 directly) so a run stays under 10 minutes; where the call ledger lives (TASK-015's decision); which production URL secret publishing uses, given the release workflow already holds `PRODUCTION_DATABASE_URL_UNPOOLED`.

## Acceptance criteria

- [ ] AC-1: `.github/workflows/results.yml` is scheduled for Sunday and Monday at 6:00 AM ET and `lines.yml` daily plus Thursday and Friday evenings (UTC crons, with the daylight-saving handling written beside them). Both also have `workflow_dispatch` and share a `concurrency` group, so two runs never publish at once.
- [ ] AC-2: Each job runs ingest (the current week) → transform → data-quality checks → publish, with `LIVE=true`. A test on the job's Python entry point shows that, given staged data failing a check, publish is never called and the run exits non-zero.
- [ ] AC-3: An owner-approved branch run of each workflow finishes green in ≤ 10 minutes, and its job summary lists the CFBD calls spent, the month's total and the rows upserted per table.
- [ ] AC-4: After the first approved `results` run, production's `teams` has as many 2026 FBS teams as the staged 2026 data, and a second run inserts no new team or game rows.
- [ ] AC-5: `docs/03-data-model.md` › Data sources records whether CFBD's scoreboard endpoint answers on tier 1, from one counted call whose response is saved to the lake.

## Out of scope

- The `rate-and-predict` job (M4.8), the `scores` job (M6.8), NFL schedules from nflverse (M6), and watchlist alerts on the `lines` job (Phase 5).
- The Odds API.
- Re-planning job times beyond 02's table.

## Files likely touched

- `.github/workflows/results.yml`, `.github/workflows/lines.yml`: the two jobs (new).
- `python/engine/src/engine/jobs.py`: the ingest → transform → check → publish entry point (new).
- `python/engine/src/engine/cli.py`: `engine job results|lines`.
- `python/engine/tests/test_jobs.py`: AC-2 (new).
- `docs/03-data-model.md` › Data sources: AC-5.
- `README.md`: a Jobs section (schedule, secrets, how to run one by hand).
- `.env.example`: the "Lives elsewhere" block lists the new Actions secrets.

## Verification

- Automated: `test_jobs.py`; the ready gate "Changed workflow run on the branch" for both workflows (owner-approved).
- Manual: after the first scheduled `results` run on a Sunday, sign in on production → `/teams` lists the 2026 FBS teams; the Actions tab shows each run under 10 minutes.

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
