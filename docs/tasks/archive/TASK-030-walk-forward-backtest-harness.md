---
id: TASK-030
title: Build the walk-forward rolling-origin backtest harness
status: Done
depends_on: [TASK-029]
size: M
model: opus
autonomy: attended
ui: false
plan_status: approved
planned_at_commit: 17289d8
---

# TASK-030 — Build the walk-forward rolling-origin backtest harness

## Goal

One command replays history week by week for any model spec, predicting each week with only what was known before it, choosing each season's settings only from earlier seasons, and refusing the locked holdout seasons unless asked on purpose.

## Context

- Task list: `docs/08-tasklist.md` › M3 › M3.2.
- Model: `docs/04-model.md` § 5 (walk-forward backtesting and leakage); § 9.1 Seasons (2014 warm-up, 2015 tuning only, 2016–2023 rolling-origin validation, 2024–2025 holdout; settings for season Y chosen on 2015…Y−1, learned weights fit only on games before the one predicted; the harness refuses holdout seasons without a flag and a written reason and records every holdout run); § 9.2 Leakage rules (unit of work is (season, week); feature rows carry `as_of`; learned weights refit once per season, ratings weekly; hindsight ratings never read; settings tuned to margin MAE, not ATS); § 9.3 (eligible games: FBS vs FBS, final, with a closing line; postseason included and reported apart); § 6 The lab workflow (holdout use is counted).
- Architecture: `docs/02-architecture.md` › Testing strategy › Levels › Model / backtest (a two-season lake fixture; golden-number determinism; changing any game after week N leaves week-N predictions unchanged; refuses hindsight ratings and unflagged holdout seasons); › Components › 1 (`backtest/` package; `engine backtest` CLI).
- Data model: `docs/03-data-model.md` › Lake layout › Feature tables (`team_week_features` and `game_features`, `as_of` = the week's first kickoff; a game counts once finished, 4 hours after kickoff).
- Decisions: D-076 (rolling-origin protocol), D-042 and D-127 (point-in-time features), D-056 (hindsight ratings refused), D-050 (models are pure functions of inputs + spec), D-121 (`engine.transform.market.closing_lines()`).
- Rules: CLAUDE.md › Domain conventions (point-in-time; never season aggregates in a backtest) and hard rule 4 (every backtest path asserts it); `.claude/rules/python.md`.
- *From TASK-020 (PR #62):* market lines are targets and pick-time inputs, never features (04 § 9.2), so the point-in-time assertion never reads `line_snapshots`; an untimed `opening` row counts as before kickoff, and a `closing` row is a target only.
- *From TASK-019 (D-127, Revisit if):* CFBD files every bowl and CFP round under postseason week 1, so a team has one postseason feature row and a later CFP round can't see its earlier rounds. The harness scores postseason games (04 § 9.3), so the plan says how it handles that week.
- **Concept:** rolling-origin means each validation season is scored as if it were the live season: the settings are picked before it starts, from earlier seasons only. Eight seasons scored that way give about 1,200 honest picks instead of 300.
- **Decide at the plan gate:** how tuning works (a grid over the spec's tunable settings, scored by pooled margin MAE on the tuning seasons); where results and the holdout log are written (the lake or a `backtests/` folder now; `model_runs` once TASK-034 lands); the results file's columns (what TASK-031's metrics read); how the postseason week is handled; how the two-season lake fixture is built from `python/engine/tests/lake_fixture.py`.
- *From TASK-029 (PR #87):* the spec's tuned settings are `{"tune": [...]}` objects (D-130). `ModelSpec.tunables()` lists every one by dotted path (`hyperparameters.recency_half_life_weeks`) with its candidates, and `ModelSpec.resolve({path: value})` returns the validated spec with each fixed to one candidate; the grid is the product of the candidates, and a model is built from a resolved spec (pick code refuses an unresolved one). Weights (`"fit"` or a number) are never tuned.

## Acceptance criteria

- [x] AC-1: Given the two-season lake fixture and a spec, `engine backtest --spec <file> --seasons <first>-<last>` predicts every eligible game of each scored season once, in (season, week) order, and writes one results row per game holding at least season, week, game id, `pred_margin`, `margin_sd`, the closing spread and the actual margin; FBS-vs-FCS games and games without a closing line get no row.
- [x] AC-2: Given a tuner that records the seasons it is shown, scoring season Y shows it exactly the seasons from the first tuning season through Y−1, skipping holdout seasons (so 2024 and 2025 both tune through 2023; reworded by the owner at review), and fitting week N of season Y passes the model only games that finished before that week's `as_of`.
- [x] AC-3: Given the two-season fixture, changing the score and stats of one week-N game of the second season and re-running leaves every prediction for weeks ≤ N identical and changes at least one later prediction.
- [x] AC-4: Given an input row whose source time isn't before its `as_of`, the run stops with a non-zero exit naming the season and week; given a model that asks for hindsight ratings or market lines as a fitting input, the run stops with an error naming the input.
- [x] AC-5: `--seasons` reaching 2024 or 2025 without `--holdout --reason "<text>"` exits non-zero and writes nothing; with both, the run completes and appends one holdout record (time, spec hash, seasons, reason) that a later run can count.
- [x] AC-6: Running the same spec on the same fixture twice gives byte-identical results, equal to a committed golden file; the golden file changes only in a commit whose message says why.

## Out of scope

- Metrics and the report (TASK-031), the baselines (TASK-032), Rung 1 (TASK-033): tests use a stub model.
- Tuning pick rules on ATS (M4.4); this task tunes model settings on margin MAE only.
- Writing backtest runs to Postgres (`model_runs`, TASK-034 and later) or a GitHub `backtest` workflow for the Lab (Phase 7).
- Fixing the single postseason feature row (D-127's revisit) beyond documenting how the harness treats it.

## Files likely touched

- `python/engine/src/engine/backtest/__init__.py` and `harness.py`: the walk-forward loop, tuning and the point-in-time assertion (new).
- `python/engine/src/engine/backtest/holdout.py`: the holdout guard and log (new).
- `python/engine/src/engine/cli.py`: `engine backtest`.
- `python/engine/tests/lake_fixture.py`: the two-season fixture.
- `python/engine/tests/test_backtest_harness.py`: AC-1, AC-2, AC-4, AC-5 (new).
- `python/engine/tests/test_backtest_leakage.py`: AC-3 (new).
- `python/engine/tests/test_backtest_golden.py` and `fixtures/backtest_golden.*`: AC-6 (new).
- `docs/04-model.md` § 9.1 or `docs/03-data-model.md` › Lake layout: where results and the holdout log live (approved at plan).
- `docs/decisions.md`: the harness's design as a D-### row.

## Verification

- Automated: the three new test files; `pnpm test`.
- Manual: on the local lake, `uv --directory python run engine backtest --spec <stub spec> --seasons 2016-2017` → finishes with the CFBD ledger unchanged and a results file covering both seasons; then `--seasons 2024` without the flag → refused.

## Follow-ups

_Work noticed during this task and deliberately left out. Each bullet ends `→ <path> § <section>` (where it was placed) or `→ not tracked: <reason>`. See `.claude/skills/track-follow-ups/classify.md`; the PR's Follow-ups section is copied from here._

- TASK-031 reads the results file: its key, its columns, and that it has no opening line, which 04 § 9.3's CLV needs (approved at plan) → docs/tasks/TASK-031-backtest-metrics-and-report.md § Context
- TASK-032's baselines register in `engine.backtest.MODELS` and run with `--model`; an SP+/FPI baseline needs a `benchmark_ratings` input with its own published-before-the-game check (approved at plan) → docs/tasks/TASK-032-backtest-baselines.md § Context
- TASK-033 registers the power model under `power`; the once-a-season refit of learned weights is the model's job, since the harness only calls `fit(games, as_of)` (approved at plan). Added at review: `GameResult` carries no team classification, so pooling FCS teams into tiers (04 § 2, D-047) needs a field or a new harness input → docs/tasks/TASK-033-rung-1-power-ratings.md § Context
- TASK-034: the results file and the holdout log move to `model_runs` (approved at plan); written as an open question for its plan → docs/tasks/TASK-034-model-registry-schema.md § Context
- `docs/03-data-model.md` › Lake layout gains `backtests/`, and `docs/04-model.md` § 9.2 says how the postseason week is scored (approved at plan) → docs/03-data-model.md § Lake layout and docs/04-model.md § 9.2 (fixed in this PR)
- Candidate decision: the harness's design (approved at plan) → docs/decisions.md § D-131
- Schema review: `staging/` and `features/` carry no shared build stamp, so a rebuild that stopped between them *and* a CFBD reschedule could give a game an old `as_of` → not tracked: needs both at once; the stale-features refusal catches the common case, and D-131's revisit covers it if a rebuild ever stops midway
- Schema review: one undated game anywhere in the lake refuses every backtest, like `check_point_in_time` → not tracked: the schema reviewer required no change; CFBD always sends `startDate`, and the refusal names the game
- Schema review: no TBA game in the backtest fixture → not tracked: the harness reuses `features.KICKOFF`, whose TBA rule the feature-table tests cover

## Plan

Approved 2026-10-26 at `17289d8`.

1. **Two-season fixture.** `lake_fixture.write_backtest_seasons(lake, (2022, 2023))`: the 2025 week-1 games, advanced stats and lines relabeled into weeks 1–8 of each season (scores varying by week and season) plus a postseason week 1 with a December and a January game; one FBS-vs-FBS game has no line.
2. **Load** (`harness.load`): staged `games`, `game_features` (each week's `as_of`) and `market.closing_lines()` (D-121) from the lake; re-run `features.check_point_in_time` on the feature rows. Eligible = FBS vs FBS, final, closing spread (04 § 9.3). The fit history is every final game, FCS included.
3. **Walk-forward** in (season, `as_of`, season type, week) order: each week `fit()` gets the games finished (kickoff + 4 h) by its `as_of`; the harness asserts that and raises `PointInTimeError` naming the season and week; each eligible game is predicted once.
4. **Tuning:** a `Tuner(spec, tuning_seasons, evaluate)` protocol; the default grid-searches `spec.tunables()` on pooled margin MAE, ties to the first grid point, with (choices, season) predictions cached. Tuning seasons for Y run from `--tune-from` (default 2015) to Y−1, never a holdout season (04 § 9.1). A spec with tunables and no tuning season, or a tuning season with no eligible games, is refused.
5. **Models:** `MODELS: name → factory(resolved spec)`; a model declares `reads`. `games` is allowed; `hindsight_ratings` (D-056) and `lines`, `line_snapshots`, `closing_lines` (04 § 9.2) are refused, unknown names too, naming the input. `power` is unregistered until TASK-033. `engine/backtest/stub.py`: a mean-margin-plus-home-field model with a tunable setting, for tests and the manual check.
6. **Holdout** (`holdout.py`): a season range reaching 2024 or 2025 needs `--holdout --reason "<text>"`, else exit 2 and nothing written. With both, everything is validated, then one record (time, spec hash, seasons, reason, model) is written to `backtests/holdout/<time>-<hash>.json`, then the run starts; `holdout.count(lake)` counts them.
7. **CLI:** `engine backtest --spec F --seasons A-B [--tune-from Y] [--model NAME] [--holdout --reason T]`; exit 1 on a point-in-time failure, 2 on a refusal.
8. **Output:** `backtests/<UTC time>-<spec hash>/predictions.parquet` (season, season_type, week, as_of, game_source_id, kickoff_at, home/away_source_id, neutral_site, pred_margin, margin_sd, home_win_prob, spread_home, spread_source, closing_from, home/away_points, margin; no timestamps of the run, so two runs are byte-identical) and `run.json` (spec, hash, choices per season, seasons, model).
9. **Docs:** 03 › Lake layout `backtests/`; 04 § 9.2 postseason note; a D-### row.

**Files:** `python/engine/src/engine/backtest/{__init__,harness,holdout,stub}.py` (new); `cli.py`; `transform/features.py` (not in Files likely touched: export the kickoff SQL so the harness reuses it); `tests/lake_fixture.py`; `tests/test_backtest_{harness,leakage,golden}.py` and `tests/fixtures/backtest_golden.csv` (new); `docs/03-data-model.md`, `docs/04-model.md`, `docs/decisions.md`.

**Tests:** AC-1, AC-2, AC-4, AC-5 in `test_backtest_harness.py` (AC-2 on a four-season in-memory set: the tuner sees [2015, 2016], [2015–2017], [2015–2018]); AC-3 in `test_backtest_leakage.py` (rescore a week-5 2023 game, compare prediction columns); AC-6 in `test_backtest_golden.py` (byte-identical parquet twice, and equal to a committed CSV, since a golden parquet breaks on a pyarrow upgrade).

**Decided at the gate:** postseason week 1 stays one unit, every postseason game predicted from ratings entering the first bowl (leak-free; later CFP rounds see slightly stale ratings; D-127's revisit is out of scope). Holdout seasons tune on 2015–2023 (04 § 9.1), so 2025 isn't tuned "through Y−1"; validation seasons are unaffected. Learned weights refit once per season inside the model.

## Review log

_Filled by /implement-task. One line per round._

- Verify R1 PASS (634e80c) → R2 PASS after the audit fixes (003e6fb) → R3 PASS (79e395b) → R4 PASS after the review fixes (2269845, pytest 422)
- Audit R1 CHANGES (not-final game UNPROVEN; holdout tuning UNPROVEN) → R2 CHANGES (not-final still UNPROVEN: the fixture's unplayed game had no score) → fixed in 79e395b and its mutant (`status == "final"` → True) shown failing by me, not an independent auditor round
- Spec R1 CHANGES (a custom tuner's `evaluate` could run the scored season, hard rule 4; AC-2 wording, a SPEC GAP the owner settled by rewording it; golden floats vs Linux CI; run.json doc fields) → R2 APPROVE
- Schema R1 APPROVE (4 MINOR: stale features silently dropped a game, an undated game crashed, no TBA fixture, doc wording; the first two and the docs fixed in 2269845) → R2 APPROVE
- Manual: local lake 2016-2017 → 1,536 games, 2016-2023 → 5,954, CFBD ledger hash unchanged; `--seasons 2024` without the flag → exit 2

## Blocked

_Only if status is Blocked: what failed, what was tried, best hypothesis, decision needed._

## Metrics

- Verify rounds: 4 (all PASS; re-runs after the audit and review fixes)
- Review rounds: 2 (spec), 2 (schema); audit 2 plus one self-checked mutant
- First-pass AC FAILs: 0 (spec R1 passed all six; its CHANGES were a rule-4 gap and the AC-2 wording)
- Plan revisions after approval: 0 (review fixes: the tuner guard and two `load` refusals)
