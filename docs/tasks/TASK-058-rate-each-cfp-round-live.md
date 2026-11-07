---
id: TASK-058
title: Rate, predict and pick each CFP round live after the rounds before it
status: In progress
depends_on: [TASK-048]
size: M
model: opus
autonomy: attended
ui: false
plan_status: approved
planned_at_commit: 6cc4dae
---

# TASK-058 — Rate, predict and pick each CFP round live after the rounds before it

## Goal

During the postseason, each College Football Playoff round is rated, predicted and picked live from ratings that include the rounds already played, the same way TASK-048's backtest scored it. Built only if TASK-048's comparison adopts the split; before the 2027 postseason.

## Context

- Task list: `docs/08-tasklist.md` › M19 › M19.7 (second half of the 2026-11-02 split; first half TASK-048).
- *From TASK-048 (PR #125):* TASK-048 adds the spec setting `postseason: rounds`, the feature tables' `round`/`round_as_of`, `History.rounds` in the harness, and a refusal in `fit_week` for a `rounds` spec naming this task. This task lifts that refusal. If TASK-048's verdict is not to adopt, close this task as not needed.
- *From TASK-048 (PR #126):* the comparison adopted the split (D-151: postseason MAE rounds − one_week −0.014, 95% −0.039 to +0.012; only the 8 title games changed), so this task goes ahead. Built under the names this plan reads: `ModelSpec.postseason`, `game_features.round`/`round_as_of`, `History.rounds` (each a `Week` with `round` and its round's `as_of`), `History.walk(season, postseason)`, and the refusal at the top of `publish.models.fit_week` (`RateRefused`).
- *From TASK-048 (PR #126), open question for the plan:* a CFP game whose teams aren't both known yet (NULL) chains only through its known side, and one with neither known is round 1, so its `round` and `round_as_of` can change between rebuilds until the bracket fills in. How does the coming round treat such a game (e.g. rate a round only once each of its games has both teams)? (arrived after the plan was approved)
- Decisions: D-150 (a rated week is `(season_type, week)`; postseason week 1 re-rated each Sunday at the first bowl's `as_of`; the coming week is the week of the earliest kickoff still to come), D-127, D-131, D-148 (no pick after a game's cutoff).
- *From TASK-047 (PR #123), moved here by the split:* the header comment of `.github/workflows/lines.yml` still describes the old coming-week rule ("the earliest week with a game not yet kicked off"); D-150 made it the week of the earliest kickoff still to come. Editing a workflow file makes its branch run the "Changed workflow run on the branch" ready gate, and `lines` writes to production, so the owner decides at the PR whether that run happens.
- **Plan gate decides how a round is stored** (CLAUDE.md: changing how a stored week is interpreted is a stop-and-ask). Proposed: no migration. A postseason run's and its ratings' `week` is the round (1–4), not CFBD's week (always 1), so `latest_team_ratings`, `team_rankings` (its "week − 1 of the same season type" already gives round r − 1) and `team_schedule_strength` work as they are. Alternative: a `postseason_round` column on `model_runs` and `team_ratings` (migration, views 020/030/040/070 changed), which keeps `week` meaning CFBD's week.

## Acceptance criteria

- [ ] AC-1: Given a version whose spec has `postseason: rounds` and staged postseason games where round 1 is final and both teams of a round-2 game are known, the weekly `rate-and-predict` job inserts a `scheduled` run with `season_type` postseason and week 2, `as_of` the round's first kickoff, ratings that count the round-1 games, and predictions for the round-2 games; the round-1 run and its rows are untouched (hard rule 2).
- [ ] AC-2: `team_rankings` for postseason week 2 gives each team's `previous_rank` from postseason week 1 of the same version.
- [ ] AC-3: During the postseason `jobs.due_weeks("lines")` stays `("postseason", 1)`. For a `rounds` version the job's rated week is the highest round with a game still to come whose teams are both known; on the 2025 dates, the Sundays Dec 21 and 28 rate round 2, Jan 4 round 3, Jan 11 and 18 round 4. With no such game it writes nothing and says why. A `one_week` version rates postseason week 1 exactly as D-150 does now (existing tests unchanged). *(Rewritten by the owner at the re-plan, 2026-11-07: the original named `due_weeks` as the round, which would stop the CFP line pulls, and "the earliest kickoff", which never rates the quarterfinals.)*
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

- New Draft task, "Run a version on `postseason: rounds` live": `/slate` reads each game's round run, plus a new version (`efficiency-v1` is `one_week`, `rounds` changes the spec hash, so it needs its own `run.json` and new arguments in `rate-and-predict.yml`); the owner wants it landed before the first 2026 bowl (approved at plan)
- Candidate decision: the coming-round rule and the bowl re-picks, amending D-150 and D-151 (approved at plan)

## Plan

_Written by /plan-batch or /implement-task Phase 1. Approved by the user (plan_status: approved) before any code is written._

Re-planned 2026-11-07 (approved): the plan of 2026-11-02 went stale after TASK-048, and AC-3 was rewritten by the owner. Still decided (2026-11-02): a postseason round is stored as `model_runs.week`/`team_ratings.week` (no migration). Open question answered: a round is rated as soon as any of its games has both teams; games without both are left out, and a game's round can't change once both are known.

**Steps**
1. Tests first (below); see each fail, except the three guards named under Test strategy.
2. `publish/models.py`: lift TASK-048's refusal. `fit_week` for a `rounds` spec and `season_type == "postseason"` reads round `week` from `History.rounds` (its `as_of`, its games); a `one_week` spec asked for postseason week > 1 is refused. The run and its ratings store `week` = the round. Add `coming_round(history, season, now)` (revised at review: it takes the history, so the job reads the rebuilt lake once): the highest round with a game still to come whose teams are both known.
3. `jobs.py`: `rate_and_predict`, after the rebuild, takes the round for a `rounds` version when the coming week is postseason, and writes nothing (with a note) if there is none. `due_weeks("lines")` keeps CFBD's postseason week 1. `reevaluate` re-picks every postseason round's newest scheduled run for a version whose newest scheduled run is postseason, so bowls still to come keep being re-picked once round 2 is rated.
4. `publish/picks.py`, `cli.py`, `core/spec.py`: docstrings and `--week` help only.
5. `.github/workflows/lines.yml`: header comment only.
6. Docs: a decision amending D-150 and D-151 (ID from `next-id.ps1`); 04 § 9.2; 03 › Models & outputs; `model-guide.md`; README › Jobs.

**Files**: the 14 in "Files likely touched", plus `python/engine/src/engine/core/spec.py` (docstring) and `README.md` (Jobs), and the new Draft task file; at review, with the owner's OK, comments in `python/db/src/db/models.py` and views 020/030 and the `lines` row of `docs/02-architecture.md`. No migration and no view logic change: 020/030/040 work with `week` = round, and 070 reads `games`.

**Test strategy**
- AC-1: `test_rate_and_predict.py::test_rounds_version_rates_the_next_round`.
- AC-2: `db/tests/test_team_rankings.py::test_postseason_round_2_ranks_against_round_1` (guard: passes on today's view).
- AC-3: `test_publish_models.py::test_coming_round_rates_past_bowls_still_to_come`; `test_jobs.py::test_lines_stays_on_cfbd_week_1` (guard: `due_weeks` deliberately doesn't change); `test_rate_and_predict.py::test_a_known_round_is_rated_past_a_bowl_still_to_come` (added at the test audit), `::test_no_round_with_both_teams_writes_nothing`, `::test_lines_reevaluates_every_open_round`; the existing D-150 tests unchanged.
- AC-4: `test_publish_models.py::test_rate_cli_fits_a_round`, `::test_rate_refuses_a_round_for_a_one_week_spec`; `test_publish_picks.py::test_round_picks_cover_only_its_games` (guard: passes on today's `write_picks`).
- AC-5: read in review.

**Risks / open questions**
- Live vs backtest: the Sunday run for a round misses games played between Sunday and the round's `as_of`, which the backtest counts (D-151's revisit trigger). Recorded in the decision.
- Two Sunday runs of a round share an `as_of` but can differ in ratings, unlike D-150's identical re-runs. Both are point-in-time clean.
- `/slate` reads a run by `games.week`, so rounds 2+ show no prediction until the new Draft task lands; no live version is `rounds` until then.
- `lines.yml` ready gate: the owner waived the branch run (comment-only change; `lines` writes to production).

**Size check:** about 17 files, engine plus docs and one workflow comment; no schema. Under the 20-file limit. M, attended.

## Review log

_Filled by /implement-task. One line per round._

## Blocked

_Only if status is Blocked: what failed, what was tried, best hypothesis, decision needed._

## Metrics

- Verify rounds:
- Review rounds:
- First-pass AC FAILs:
- Plan revisions after approval:
