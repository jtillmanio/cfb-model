---
id: TASK-058
title: Rate, predict and pick each CFP round live after the rounds before it
status: Ready
depends_on: [TASK-048]
size: M
model: opus
autonomy: attended
ui: false
plan_status: approved
planned_at_commit: faea7a4
---

# TASK-058 — Rate, predict and pick each CFP round live after the rounds before it

## Goal

During the postseason, each College Football Playoff round is rated, predicted and picked live from ratings that include the rounds already played, the same way TASK-048's backtest scored it. Built only if TASK-048's comparison adopts the split; before the 2027 postseason.

## Context

- Task list: `docs/08-tasklist.md` › M19 › M19.7 (second half of the 2026-11-02 split; first half TASK-048).
- *From TASK-048 (PR #125):* TASK-048 adds the spec setting `postseason: rounds`, the feature tables' `round`/`round_as_of`, `History.rounds` in the harness, and a refusal in `fit_week` for a `rounds` spec naming this task. This task lifts that refusal. If TASK-048's verdict is not to adopt, close this task as not needed.
- Decisions: D-150 (a rated week is `(season_type, week)`; postseason week 1 re-rated each Sunday at the first bowl's `as_of`; the coming week is the week of the earliest kickoff still to come), D-127, D-131, D-148 (no pick after a game's cutoff).
- *From TASK-047 (PR #123), moved here by the split:* the header comment of `.github/workflows/lines.yml` still describes the old coming-week rule ("the earliest week with a game not yet kicked off"); D-150 made it the week of the earliest kickoff still to come. Editing a workflow file makes its branch run the "Changed workflow run on the branch" ready gate, and `lines` writes to production, so the owner decides at the PR whether that run happens.
- **Plan gate decides how a round is stored** (CLAUDE.md: changing how a stored week is interpreted is a stop-and-ask). Proposed: no migration. A postseason run's and its ratings' `week` is the round (1–4), not CFBD's week (always 1), so `latest_team_ratings`, `team_rankings` (its "week − 1 of the same season type" already gives round r − 1) and `team_schedule_strength` work as they are. Alternative: a `postseason_round` column on `model_runs` and `team_ratings` (migration, views 020/030/040/070 changed), which keeps `week` meaning CFBD's week.

## Acceptance criteria

- [ ] AC-1: Given a version whose spec has `postseason: rounds` and staged postseason games where round 1 is final and both teams of a round-2 game are known, the weekly `rate-and-predict` job inserts a `scheduled` run with `season_type` postseason and week 2, `as_of` the round's first kickoff, ratings that count the round-1 games, and predictions for the round-2 games; the round-1 run and its rows are untouched (hard rule 2).
- [ ] AC-2: `team_rankings` for postseason week 2 gives each team's `previous_rank` from postseason week 1 of the same version.
- [ ] AC-3: The coming week (`jobs.due_weeks("lines")` and the job's rated week) during the postseason is the round of the earliest postseason kickoff still to come; with a `one_week` version, the job rates postseason week 1 exactly as D-150 does now (existing tests unchanged).
- [ ] AC-4: `engine rate --season-type postseason --week 2` fits round 2 for a `rounds` spec and refuses (exit 2) for a `one_week` spec; `engine pick` writes picks for the round-2 run's games only, and none for a game past its cutoff (D-148).
- [ ] AC-5: The header comment of `.github/workflows/lines.yml` states the D-150 coming-week rule and the round rule.

## Out of scope

- The backtest and the decision to adopt (TASK-048).
- Screens showing a postseason round (the slate and rankings tasks read whatever runs exist).
- Staging CFBD's `notes` (round names).

## Files likely touched

- `python/engine/src/engine/publish/models.py`, `publish/picks.py`, `jobs.py`, `cli.py`
- `python/engine/tests/test_rate_and_predict.py`, `test_jobs.py`, `test_publish_models.py`, `test_publish_picks.py`; `python/db/tests/test_team_rankings.py`
- `.github/workflows/lines.yml` (comment only)
- `docs/04-model.md` § 9.2, `docs/03-data-model.md` (`model_runs.week` for the postseason), `docs/model-guide.md`, `docs/decisions.md`

## Verification

- Automated: the tests named in the plan pass; the D-150 postseason tests pass unchanged.
- Manual: on the dev database, `engine rate --season 2025 --season-type postseason --week 2` with a `rounds` version → expected: a run with week 2, `as_of` the first quarterfinal's kickoff.

## Follow-ups

_Work noticed during this task and deliberately left out. Each bullet ends `→ <path> § <section>` (where it was placed) or `→ not tracked: <reason>`. See `.claude/skills/track-follow-ups/classify.md`; the PR's Follow-ups section is copied from here._

## Plan

_Written by /plan-batch or /implement-task Phase 1. Approved by the user (plan_status: approved) before any code is written._

Provisional: depends on TASK-048 (its `History.rounds`, the spec setting and the refusal this lifts). Re-plan if TASK-048 changes those names. Decided at the plan gate (2026-11-02): a postseason round is stored as `model_runs.week`/`team_ratings.week` (no migration).

**Steps**
1. Tests first (below); see each fail.
2. `publish/models.py`: `fit_week(…, season_type, week)` for a `rounds` spec and `season_type == "postseason"` reads round `week` from `History.rounds` (its `as_of`, its games); a `one_week` spec asked for postseason week > 1 is refused. Lift TASK-048's refusal. The run and its ratings store `week` = the round (the proposed storage).
3. `publish/picks.py`: `_run` already selects by `(season, season_type, week)`; picks cover the run's own games only (round r's), not every postseason game.
4. `jobs.py`: during the postseason, the rated week for a `rounds` version is the round of the earliest postseason kickoff still to come whose teams are both known (from `History.rounds`); `due_weeks("lines")` keeps pulling CFBD's postseason week 1 (the pulls name CFBD's week, `run()` passes it straight through); `reevaluate` re-picks the newest scheduled run's `(season_type, week)` as now. Docstring updated.
5. `cli.py`: help text for `--week` says it is the round for a postseason `rounds` spec.
6. `.github/workflows/lines.yml`: header comment only.
7. Docs: a decision amending D-150 (ID from `next-id.ps1`); 04 § 9.2; 03 › Models & outputs (`model_runs.week` is the round for a postseason `rounds` run); `model-guide.md`.

**Files**: the 14 in "Files likely touched". No migration and no view change with the proposed storage; the column alternative adds the migration, `python/db/src/db/models.py` and four views (about 20).

**Test strategy**
- AC-1: `test_rate_and_predict.py::test_rounds_version_rates_the_next_round`.
- AC-2: `db/tests/test_team_rankings.py::test_postseason_round_2_ranks_against_round_1`.
- AC-3: `test_jobs.py::test_coming_week_is_the_next_round`; the existing D-150 tests unchanged.
- AC-4: `test_publish_models.py::test_rate_cli_fits_a_round`, `::test_rate_refuses_a_round_for_a_one_week_spec`; `test_publish_picks.py::test_round_picks_cover_only_its_games`.
- AC-5: manual check of the comment in review.

**Risks / open questions**
- Storage (Context): the owner picks `week` = round (proposed) or a new column.
- Reader drift: anything that joins a postseason run's `week` to `games.week` would miss rounds 2–4; today nothing does (predictions and picks join by game id). Screen endpoints must read the newest postseason run, not week 1's.
- Cadence: the job runs Sundays; a 12-team bracket's rounds are a week or more apart, so each round is rated before it kicks off. A round whose teams are known only the day before (none in 2024–2025) would wait for an ad hoc run.
- `lines.yml` ready gate: running `lines` on the branch writes to production; the owner decides.

**Size check:** 14 files, engine plus docs and one workflow comment; no schema with the proposed storage. M, attended.

## Review log

_Filled by /implement-task. One line per round._

## Blocked

_Only if status is Blocked: what failed, what was tried, best hypothesis, decision needed._

## Metrics

- Verify rounds:
- Review rounds:
- First-pass AC FAILs:
- Plan revisions after approval:
