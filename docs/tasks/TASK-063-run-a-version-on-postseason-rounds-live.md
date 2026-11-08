---
id: TASK-063
title: Run a version on postseason rounds live and show each round's predictions
status: Review
depends_on: [TASK-058]
size: M
model: opus
autonomy: attended
ui: false
plan_status: approved
planned_at_commit: ff61b81
---

# TASK-063 — Run a version on postseason rounds live and show each round's predictions

## Goal

The paper-traded model rates each College Football Playoff round after the rounds before it, and This Week shows those predictions. The owner wants this landed before the first 2026 bowl (owner, 2026-11-07), so it needs to be Ready and merged, and the release run, before the Sunday that first rates the postseason.

## Context

- Task list: `docs/08-tasklist.md` › M19 › M19.8.
- *From TASK-058 (PR #142):* TASK-058 built the engine (`engine rate`, the weekly job, `lines` re-picks; D-161), but no live version uses it. `efficiency-v1.json` is `one_week`, and `postseason: rounds` changes the spec hash (it's left out of the hash only at the default, D-151), so three things stand in the way:
  - `models._version` refuses v1.0 with another spec, so a `rounds` spec needs its own version name or number.
  - `models.settings` refuses a `run.json` of another spec hash, so it needs its own, from a backtest of that spec that scored 2026 (as `efficiency-v1-2026.run.json` was, D-149).
  - `.github/workflows/rate-and-predict.yml` names the spec, the choices and the version.
- *From TASK-058 (PR #142):* `/slate` reads one run for the week: `week_run` in `python/api/src/api/slate.py` matches `r.week` to the week from `games`, which is 1 for every postseason game. A `rounds` version's quarterfinals onward are predicted in runs with `week` 2–4, so they'd show no prediction or model line, and `RULES_SQL` reads its `fitted_params` from that one run too. Picks are unaffected: `PICKS_SQL` reads by game. `GAMES_SQL`'s `ranks` would keep showing round 1's ranks.
- *From TASK-058 (PR #142), open question for the plan:* which version shows in the app? `shell.SHOWN` takes the newest live candidate with a scheduled run this season, so a new version would replace v1.0 on screen in December with a record of zero games. Options: keep v1.0 the shown one and run the new version beside it (the job rates one version today; many versions are M23.1, D-147), or switch and accept the short record. The owner decides at the plan gate.
- *From TASK-058 (PR #142), open question for the plan:* does the version start at round 1 (the first postseason Sunday) or at the first round after it? `lines` re-picks every round of a `rounds` version's own runs, but a version's first run needs round 1's games rated if the bowls are to be picked by it.
- *From TASK-058 (PR #142), open question for the plan:* a `rounds` version rates round 1 on only one Sunday, then moves to round 2. A bowl whose teams appear or change after that Sunday gets no new prediction, which `one_week` would have given it, and nothing says so (D-161). Should the job warn in its summary when a game still to come with both teams has no prediction in any of the version's runs?
- `.github/workflows/rate-and-predict.yml` is a workflow file: changing it runs the "Changed workflow run on the branch" ready gate, and the job writes to production, so the owner decides at the PR whether that run happens (a `dry_run` hand run does every step and rolls back).
- Decisions: D-161, D-151, D-150, D-149, D-144, D-156, D-158.

## Acceptance criteria

- [x] AC-1: Given postseason games predicted in a round-1 run and a round-2 run of the shown version, `/slate` for postseason week 1 returns each game's `pred_margin` from the newest succeeded run that predicted it (expected: a bowl's from round 1's run, a quarterfinal's from round 2's), and each game's blended line is computed with that run's `fitted_params`.
- [x] AC-2: A spec file with `postseason: rounds` and a `run.json` with its `spec_hash` and a 2026 entry exist under `python/engine/specs/`, and `engine job rate-and-predict --dry-run` with them exits 0 on the dev database.
- [x] AC-3: `.github/workflows/rate-and-predict.yml` names the chosen spec, choices and version, and the shown version on `/slate` is the one the owner chose at the plan gate.
- [x] AC-4: `/slate`'s query count for a postseason week stays within `QUERY_BUDGET` (`api/wave.py`).

## Out of scope

- Engine changes to how a round is chosen or fit (TASK-058).
- Opening the 2024–2025 holdout to score the 12-team rounds (D-151: the owner's call).
- Rating several versions in one job (M23.1).

## Files likely touched

- `python/api/src/api/slate.py`, `python/api/tests/` (the slate tests)
- `python/engine/specs/` (the new spec and `run.json`)
- `.github/workflows/rate-and-predict.yml`
- `docs/decisions.md`, `docs/model-guide.md`, `README.md` › Jobs

## Verification

- Automated: the `/slate` test named in the plan passes.
- Manual: `engine job rate-and-predict --dry-run` on the dev database with the new spec → expected: exit 0, "Week rated" naming the coming week.

## Follow-ups

_Work noticed during this task and deliberately left out. Each bullet ends `→ <path> § <section>` (where it was placed) or `→ not tracked: <reason>`. See `.claude/skills/track-follow-ups/classify.md`; the PR's Follow-ups section is copied from here._

- The first postseason run's timing (approved at plan as "Sun 2026-12-06 comes before the bowl announcements"; corrected at close-out: the coming week turns postseason only once Army–Navy has kicked off, D-150, so the first postseason run is the Sunday after it, and round 1 is rated then, once). A bowl before that Sunday gets no prediction; the hand dispatch after Army–Navy that the existing item asks for now rates round 1 → not tracked: already tracked in docs/owner-checklist.md § Actions ("Before the 2026 bowls", from TASK-047)
- v1.1 takes over at the first Sunday `rate-and-predict` run after this merges (the workflow checks out `main`; no Release needed for that), but production's `/slate` reads each round's run only after a Release run, which has to come before round 2 is rated (approved at plan; corrected at close-out, which first said the switch itself needed the Release) → docs/owner-checklist.md § Actions
- Candidate decision: efficiency v1.1, the switch, `/slate` reading each game's run by game id, the summary's warning (approved at plan) → docs/decisions.md § D-165
- The roadmap and the task list planned "v1.1" for the inputs variant (M19.1); production's `efficiency v1.1` is now the CFP-rounds variant, so that variant is renumbered v1.2 (owner approved at close-out) → docs/06-roadmap.md § Phase 5 (Model v1.2 item); the same note in docs/08-tasklist.md § M19 (heading and M19.1)
- `engine job … --summary` crashes with `UnicodeEncodeError` printing the summary's "→" when stdout is redirected on Windows (cp1252); the job's work is done by then, and `PYTHONIOENCODING=utf-8` avoids it → not tracked: a local Windows console with redirected output only (CI runs on Linux, and an interactive Windows console prints UTF-8); noted in the PR

## Plan

_Approved 2026-11-08 at `ff61b81`. Owner's choices at the gate: switch to v1.1 now (record restarts, weeks before its first run show no model line); the job warns about postseason games with no prediction._

**Steps**
1. **Spec and settings:** `python/engine/specs/efficiency-v1.1.json` = `efficiency-v1.json` + `"postseason": "rounds"` (hash `1d0d7c48c354`, D-151's); `efficiency-v1.1-2026.run.json` copied from `backtests/20261108T062910249111Z-1d0d7c48c354/run.json` (tuned on 2015–2023: α 2, half-life 16, min edge 8, display k 0.1, as v1.0's).
2. **Workflow:** `rate-and-predict.yml` passes `--spec engine/specs/efficiency-v1.1.json --choices engine/specs/efficiency-v1.1-2026.run.json --version v1.1`; v1.1 becomes the shown version (`shell.SHOWN`: the newest candidate with a scheduled run) from its first run; v1.0 stops being rated, its rows stay.
3. **`/slate`:** `week_run` becomes `slate_runs`: the shown version's succeeded `scheduled`/`adhoc` runs of the week's season and season type, finished by now, that predicted a game of the week. Each game's prediction is from the newest of them that predicted it (by game id, D-161); its rank is entering that run's week (a quarterfinal shows the rank entering round 2), else the slate week's; `RULES_SQL` returns one row per run (id, `fitted_params`), newest first, so each game's edge uses its run's choices and weights and the top-level `rules` are the newest run's. Still 6 statements.
4. **Job warning:** when the week rated is postseason, the weekly summary lists postseason games of the season still to come with no prediction in any of the version's succeeded runs that postseason (one read-only query in the job's transaction).
5. **Docs:** a decision row (v1.1, the switch, by-game reads, the warning), amending D-149 and D-158; `docs/model-guide.md` (v1.1's status); `README.md` › Jobs.

**Files:** `python/api/src/api/slate.py`, `python/api/tests/test_api_slate.py`, `python/engine/specs/efficiency-v1.1.json`, `python/engine/specs/efficiency-v1.1-2026.run.json`, `.github/workflows/rate-and-predict.yml`, `python/engine/src/engine/jobs.py` (not in Files likely touched: the warning), `python/engine/tests/test_jobs.py` (not listed: it pins the workflow's arguments), `python/engine/tests/test_rate_and_predict.py` (added in Phase 2: the warning's tests), `docs/decisions.md`, `docs/model-guide.md`, `README.md`.

**Test strategy**
- AC-1: `test_api_slate.py::test_each_postseason_game_reads_the_newest_run_that_predicted_it`: round-1 and round-2 runs with different weights and choices; the bowl's `pred_margin` and edge match round 1's run, the quarterfinal's round 2's (values from `engine.core`), and the quarterfinal's rank is round 2's.
- AC-2: `test_jobs.py::test_the_committed_settings_match_the_spec_the_workflow_runs` on v1.1, also asserting `postseason == "rounds"`; manual `engine job rate-and-predict --target dev --dry-run` → exit 0.
- AC-3: `test_jobs.py::test_rate_and_predict_workflow_runs_the_weekly_job` on v1.1 and `--version v1.1`; `test_api_slate.py::test_v1_1_replaces_v1_0_on_the_slate` (added after the test audit): with an older v1.0 candidate and a newer v1.1 candidate both rating the postseason, the shell names v1.1 and each game shows v1.1's rounds.
- AC-4: `test_api_slate.py::test_a_postseason_slate_stays_in_the_query_budget` counts a postseason `load`'s statements (≤ `QUERY_BUDGET`); an EXPLAIN test that predictions are read by `game_id`. Both are regression guards: the old slate also ran six statements, so they pass on the base too.
- Warning: `test_rate_and_predict.py::test_the_summary_names_postseason_games_with_no_prediction`, and a "none" line asserted in `test_rounds_version_rates_the_next_round` (revised in Phase 2: the job's rounds fixtures live in `test_rate_and_predict.py`, not `test_jobs.py`; that file is added to Files).

**Risks:** the record strip restarts and earlier weeks show no model line (accepted); by-game reads mean a regular-week game the newest run left out shows an earlier run's prediction instead of none; the Dec 6 timing above.

## Review log

_Filled by /implement-task. One line per round._

Verify R1 PASS | Audit R1 CHANGES (AC-3's shown version proven only by the workflow text) → R2 PASS | Spec R1 APPROVE | Schema R1 not independent (the agent stopped on an API rate limit; its checklist run by the implementer: plans on the test DB, no change needed) APPROVE

## Blocked

_Only if status is Blocked: what failed, what was tried, best hypothesis, decision needed._

## Metrics

- Verify rounds: 1
- Review rounds: 1
- First-pass AC FAILs: 0
- Plan revisions after approval: 2 (the warning's tests in `test_rate_and_predict.py`; `test_v1_1_replaces_v1_0_on_the_slate` added after the test audit)
