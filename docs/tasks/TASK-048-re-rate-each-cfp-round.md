---
id: TASK-048
title: Backtest re-rating each CFP round after the rounds before it
status: Ready
depends_on: [TASK-047]
size: M
model: opus
autonomy: attended
ui: false
plan_status: approved
planned_at_commit: faea7a4
---

# TASK-048 — Backtest re-rating each CFP round after the rounds before it

## Goal

The backtest can predict each College Football Playoff round from ratings that include the rounds already played, as a spec setting, and the owner gets a with-and-without comparison on 2016–2023 that decides whether live rating does the same (TASK-058). Target: before the 2027 postseason.

## Context

- Task list: `docs/08-tasklist.md` › M19 › M19.7. Split on 2026-11-02 (owner): this task is the backtest half (`model/` branch, no schema change); TASK-058 rates each round live, and runs only if this task's comparison adopts the split.
- Model: `docs/04-model.md` § 9.2 ("The postseason is one week"); D-127 (its revisit: a CFP round may need its earlier rounds' results), D-131 (the harness scores postseason week 1 as one unit, `as_of` the first bowl's kickoff), D-150 (production rates it the same way, re-run each Sunday at that same `as_of`).
- *From TASK-047 (PR #123):* CFBD files every bowl and CFP round under postseason week 1, and the harness, `team_week_features`/`game_features` and the weekly job all treat it as one week with one `as_of`. A 12-team CFP's title game is then predicted from ratings about five weeks old that never saw the playoff. Splitting it (for example a sub-week per round, each with its own `as_of`, the first kickoff of that round) touches the feature tables' week key (D-127), the harness's week walk (D-131), how `model_runs`/`team_ratings` name a sub-week (D-150 keys a week by `(season_type, week)`: a schema change, so stop and ask), and the weekly job's coming-week rule (`jobs.due_weeks`). Validate it in the backtest (postseason games are reported on their own, 04 § 9.3) before it runs live, so live still scores what was validated.
- *From TASK-047 (PR #123):* the header comment of `.github/workflows/lines.yml` still describes the old coming-week rule ("the earliest week with a game not yet kicked off"); D-150 made it the week of the earliest kickoff still to come. It was left alone because editing a workflow file makes its branch run a ready gate, and `lines` writes to production. Fix it when this task (or any change before it) touches `lines.yml` or the coming-week rule. (After the split this belongs to TASK-058, which changes the coming-week rule; this task touches neither.)
- **No round names in the data.** CFBD's `/games` has a `notes` field with the bowl or game name, but staging doesn't keep it and nothing reads it. A round is therefore derived from the bracket's shape: a postseason game's round is 1 + the highest round of any earlier postseason game either team played that season. Bowls and the 4-team semifinals are round 1, the 4-team title game round 2; in the 12-team bracket the first round is 1, quarterfinals 2, semifinals 3, the title game 4.
- **How little the backtest can show.** 2016–2023 used the 4-team bracket, so only the eight title games (one a season) get new ratings; the 12-team seasons, 2024–2025, are the holdout (04 § 9.1). Eight games can't move postseason MAE by more than noise, so the bar is "no clear harm", not "better" (owner's split, 2026-11-02; the bar is proposed at the plan gate).

## Acceptance criteria

- [ ] AC-1: After `engine transform --rebuild` on a lake fixture whose postseason has a December game between A and B, a December game between C and D and a January game between A and C, the two December games are round 1 and the January game round 2; `game_features` gives each game its `round` and `round_as_of` (round 2's = the January kickoff), and its `as_of` stays the week's (the first December kickoff).
- [ ] AC-2: `team_week_features` has a row per team for postseason week 1 round 2, whose `games_played` counts A's December game (finished 4 h before `round_as_of`), and `check_point_in_time` fails, naming the team, season and round, when the inclusion rule is loosened so that row reads a game that hadn't finished.
- [ ] AC-3: `ModelSpec` gains `postseason`: `one_week` (default) or `rounds`; the hashes of `specs/efficiency-v1.json` and `specs/power-v1.json` are unchanged, and the golden tests (`test_backtest_golden.py`, `test_backtest_report.py`) pass unchanged with the default.
- [ ] AC-4: With `postseason: rounds`, the harness fits the January game at its `round_as_of` on a history that includes A's and C's December games, and predicts every regular-season and round-1 game exactly as the `one_week` run does (equal rows).
- [ ] AC-5: `engine rate` with a spec whose `postseason` is `rounds` exits 2 and writes nothing, naming TASK-058, so live never runs the split before it is built and validated there.
- [ ] AC-6: `engine backtest compare RUN_A RUN_B --postseason` scores only postseason games (paired, whole weeks resampled; 04 § 9.5) and exits 2 when the runs share no postseason game.
- [ ] AC-7: `efficiency-v1` backtested over 2016–2023 with `one_week` and with `rounds`; the two runs' postseason MAE, the paired difference with its 95% interval, and the number of games whose prediction changed are recorded in a new decision and in `docs/model-guide.md`, with the verdict: adopt the split (TASK-058 goes ahead) unless the interval lies wholly above zero.

## Out of scope

- Rating each round live: model runs, ratings, views, the weekly job's coming week, `lines.yml` (TASK-058).
- Staging CFBD's `notes` (bowl and round names).
- Running the 2024–2025 holdout (needs `--holdout` and a reason; the owner's call).
- CFP bracket odds and season simulations (Phase 5, M9).

## Files likely touched

- `python/engine/src/engine/transform/features.py`, `backtest/harness.py`, `backtest/bootstrap.py`, `core/spec.py`, `publish/models.py`, `cli.py`
- `python/engine/tests/lake_fixture.py`, `test_features.py`, `test_leakage.py`, `test_backtest_harness.py`, `test_model_spec.py`, `test_publish_models.py`, `test_backtest_compare.py`
- `docs/04-model.md` § 9.2, `docs/03-data-model.md` (feature tables), `docs/model-guide.md`, `docs/decisions.md`

## Verification

- Automated: the tests named in the plan pass; the existing backtest golden tests pass unchanged.
- Manual: `engine backtest --spec specs/efficiency-v1.json --seasons 2016-2023` twice (default, and a copy with `"postseason": "rounds"`), then `engine backtest compare A B --postseason` → expected: only the eight title games differ; the numbers are recorded per AC-7.

## Follow-ups

_Work noticed during this task and deliberately left out. Each bullet ends `→ <path> § <section>` (where it was placed) or `→ not tracked: <reason>`. See `.claude/skills/track-follow-ups/classify.md`; the PR's Follow-ups section is copied from here._

- The live half of the split: rate, predict and pick each CFP round in production, gated on this task's verdict → docs/tasks/TASK-058-rate-each-cfp-round-live.md (new, Draft)
- Task list M19.7 now points at both halves → docs/08-tasklist.md § M19

## Plan

_Written by /plan-batch or /implement-task Phase 1. Approved by the user (plan_status: approved) before any code is written._

Split approved by the owner on 2026-11-02; the ACs above were drafted with this plan. Decided at the plan gate (2026-11-02): the AC-7 bar is "adopt unless the paired 95% interval lies wholly above zero"; rounds come from the bracket rule in Context.

**Steps**
1. Tests first (below); see each fail.
2. `features.py`: a `rounds` CTE gives each postseason game its round by the bracket rule in Context (a recursive CTE over the season's postseason games by kickoff; a regular-season game is round 1). `KEYS` gains `round`; the `weeks` CTE becomes `(season, season_type, week, round)` with `as_of` = the round's earliest kickoff, so postseason week 1 gets one row per team per round and every other week stays one row (round 1, values unchanged). `game_features` keeps `as_of` and its features from round 1 (entering the week, as now) and adds `round` and `round_as_of`. `check_point_in_time` covers every round row and names the round.
3. `core/spec.py`: `postseason: Literal["one_week", "rounds"] = "one_week"`, added to `ADDED_DEFAULTS` so existing hashes hold.
4. `harness.py`: `load()` keeps `History.weeks` as now (one postseason unit; `publish._week()` still reads it) and adds `History.rounds`: postseason round weeks, each a `Week` with `round` (new field, default 1) and `as_of` = `round_as_of`. `predict_season` takes the spec's `postseason`; with `rounds` it walks round weeks in place of the postseason unit, `fit_games`/`_check_fit` at each round's `as_of`. `predictions.parquet` keeps its schema: the row's `as_of` already says which fit made it.
5. `publish/models.py`: `fit_week` refuses (`RefusedError`, exit 2) a spec with `postseason: rounds`, naming TASK-058.
6. `cli.py` + `bootstrap.py`: `compare --postseason` filters both runs to postseason rows before pairing; refuses when none are shared.
7. `lake_fixture.py`: `write_backtest_seasons(lake, cfp_rematch=False)`; with `True` it adds a January postseason game between a team from each December game. The default fixture is unchanged, so no golden moves.
8. Run the AC-7 comparison on the dev lake; write the decision (ID from `next-id.ps1`) and the docs: 04 § 9.2 (the setting and the round rule), 03 (feature table `round`, `round_as_of`), `model-guide.md` (what the setting does and the result).

**Files**: the 17 in "Files likely touched" (all exist; each gains code or cases, none is new).

**Test strategy**
- AC-1: `test_features.py::test_postseason_rounds_follow_the_bracket`.
- AC-2: `test_features.py::test_a_round_row_counts_the_earlier_round`; `test_leakage.py::test_point_in_time_catches_a_round_leak`.
- AC-3: `test_model_spec.py::test_postseason_default_keeps_the_hash`; the existing golden tests, unchanged.
- AC-4: `test_backtest_harness.py::test_rounds_fit_each_round_after_the_rounds_before`, `::test_rounds_leave_other_predictions_alone`.
- AC-5: `test_publish_models.py::test_rate_refuses_a_rounds_spec`.
- AC-6: `test_backtest_compare.py::test_compare_postseason_only`, `::test_compare_postseason_refuses_no_shared_game`.
- AC-7: manual (Verification), its numbers in the decision.

**Risks / open questions**
- The bar (AC-7: adopt unless the interval is wholly above zero) is my proposal; the owner may prefer "the point estimate isn't worse" or to also look at the 2024–2025 holdout, which would be counted as a holdout look.
- A recursive CTE in DuckDB over ~45 postseason games a season is cheap; if it reads poorly, the rounds are computed in Python into a temp table before the feature SQL (same result, same test).
- A TBA-kickoff postseason game: rounds order by `KICKOFF` (end of its Eastern date), as inclusion does.

**Size check:** 17 files, one layer (engine) plus docs; no schema. M, attended.

## Review log

_Filled by /implement-task. One line per round._

## Blocked

_Only if status is Blocked: what failed, what was tried, best hypothesis, decision needed._

## Metrics

- Verify rounds:
- Review rounds:
- First-pass AC FAILs:
- Plan revisions after approval:
