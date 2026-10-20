---
id: TASK-021
title: Backfill 2014–2025 and 2026 to date, then explore it in notebook #1
status: Ready
depends_on: [TASK-015, TASK-017, TASK-018, TASK-020]
size: M
model: opus
autonomy: attended
ui: false
plan_status: approved
planned_at_commit: 57badb4
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
- *From TASK-015 (PR #52), open question for the plan:* TASK-015's `pull()` treats a week-level file as final once a saved `/games` file shows every game of that week completed, but has no rule for season-level files, which it always fetches. A resumable backfill needs one, e.g. a season's file is final when it was saved after the season's last game completed.
- *From TASK-017 (PR #60):* the `closing_line` data-quality check passes only for completed FBS-vs-FBS games covered by a `/lines` pull fetched after kickoff (or marked `closing_line_missing` from one), so the backfill should pull `/lines` for each season after it ends.
- *From TASK-017 (PR #61):* an empty `/lines` pull isn't coverage for the `closing_line` check (CFBD can answer empty just after the games, D-114), so a week that comes back empty needs another pull before the check passes. The 2025 week-1 `/games` and `/lines` files, and the 2025 `/teams`, `/venues` and `/calendar` pulls TASK-017 recorded for its fixture (3 calls on 2026-10-19), are in the local `./data` lake with their calls on its ledger, not in the R2 dev lake `LAKE_URI` points at. Three local files carry the test clock's stamp `fetched_at=2025-09-02T120000Z` (ledger month `2025-09`), and its `/lines` one holds 2019 lines, which staging skips.
- *From TASK-018 (PR #64):* the season endpoints (talent, returning production, recruiting, SP+/FPI/Elo) resolve `team_source_id` by each team's newest staged `teams.school`, so a school renamed since (e.g. "Sam Houston State" → "Sam Houston") stays NULL in older seasons; the rebuild lists every unmatched name. The full-lake rebuild will show how many; matching per season or on `/teams` `alternateNames` is the fix if backtest teams are hit (D-119's revisit) (arrived after the plan was approved)

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

- 02 › Environments & databases lists the development lake as local `./data/`. From this task on, R2 is the lake every CFBD call writes to, and `./data` is a mirror made by `engine lake sync` → docs/02-architecture.md § Environments & databases (approved at plan)
- The jobs read and write the same R2 lake and ledger as the backfill. The season-level final rule (gate C) also covers a `results` run's season files → not tracked: already in TASK-022's approved plan (gate B for the shared lake and ledger; its dependency line names the season-level final rule)
- M3.4's closing-line baseline reuses `engine.transform.market.closing_lines()`, so it matches notebook #1's benchmark → docs/08-tasklist.md § M3.4 (approved at plan)

## Plan

Provisional: depends on TASK-018 and TASK-020. The closing-line rule below follows TASK-020's gate B, and the stats endpoints come from TASK-018.

**Gate decisions** (recommended)
- A. **Notebook:** marimo, `python/notebooks/01-explore.py`. It's a plain `.py` file, so it diffs and lints, and it also runs headless as a script. Its dependencies go in a `notebooks` dependency group in `python/pyproject.toml` (marimo, matplotlib), never the API's.
- B. **Pull order** for each season 2014→2026:
  - First `calendar` and season-level `games` (regular, then postseason).
  - Then each week from the saved calendar: `games_teams`, `plays`, `drives`.
  - Then the season-level `lines` and `stats_game_advanced` (both season types), and `teams`, `talent`, `player_returning`, `recruiting_teams`, `ratings_sp|fpi|elo`.
  - `venues` and `conferences` once, under 2026 (they take no year).
  - Skipped: `teams_fbs`, and `ppa_predicted` (M3+).
  - Each pull goes through `pull()`, so a re-run reuses every final file.
- C. **Season-level final rule** (TASK-015's open question; amends D-114): a season-level file is final when a saved `/games` file is no newer than it and shows every game of that season type completed. An endpoint with no season type needs the postseason completed. An empty file counts as final only if it was saved ≥ 7 days after the last game.
- D. **R2:** the backfill runs with `LAKE_URI=s3://<lake bucket>`, so its calls land on the ledger the jobs share (D-112). Then `engine lake sync --from s3://… --to ./data` and back copy every `raw/cfbd/` file missing on either side. `write_new` never overwrites, and the sync makes no CFBD calls. The local mirror feeds the rebuild, the notebook and the dev publish.
- E. **Benchmark:** the pooled 2014–2025 closing-line MAE (with the date and commit) goes in `docs/04-model.md` § 9.6, Phase 1 row, Bar cell. That's a planning-doc edit, approved with this plan. The per-season table stays in the notebook.
- F. **Closing line from the lake:** `engine/transform/market.py` holds `closing_lines()`, the same rule as `game_market`. Per provider, it takes the first pull at or after the cutoff, else the last pull before it; then `consensus` if quoted, else the median. The notebook uses it now, and M3.4 later. MAE = mean of |margin + closing `spread_home`| over final FBS-vs-FBS games (04 § 9.3).
- **Estimate (by hand; the real dry run is shown before any call):**
  - 12 past seasons × (14 season-level + 3 × ~16 weeks) ≈ 744.
  - 2026: about 11 season-level plus 3 × 7 finished weeks, ≈ 32.
  - Plus `venues` and `conferences`: total ≈ 780.
  - That's above D-026's ~500, which counted only plays and drives weekly, and about 16% of a month.

**Steps**
1. `endpoints.py`: rule C in `_is_final`.
2. `ingest/backfill.py` (new):
   - `plan(lake, first, last) -> list[Pull]` (pulls not final yet). Weekly pulls in a season with no saved calendar are counted at 16 weeks and labeled "estimated".
   - `run(lake, plan, client, max_calls=None)`. On `BudgetExceededError` it stops before the call, prints what's left, and exits 3.
   - `sync_raw(src, dst)`.
3. `cli.py`: `engine backfill --from Y --to Y [--dry-run] [--max-calls N]` and `engine lake sync --from URI --to URI`.
4. `transform/market.py`: `closing_lines()` (F).
5. Notebook #1 has home-field advantage by season (mean margin for non-neutral games), the margin histogram, and closing-line MAE for each season and pooled. `uv lock` adds the group.
6. Docs:
   - `03-data-model.md` › Lake layout (rule C) and › Data sources (the dry-run total in place of ~500).
   - `04-model.md` § 9.6 (E).
   - `decisions.md`: one D-### for A–F, amending D-026 and D-114.
7. **Stop and ask** before the run, with the dry run in hand. Then, with the owner's go-ahead: the run → sync → rebuild → checks → `engine publish --target dev` → notebook.

**Files** (12): `ingest/backfill.py` (new), `ingest/endpoints.py`, `cli.py`, `transform/market.py` (new), `tests/test_backfill.py` (new), `tests/test_market.py` (new), `python/notebooks/01-explore.py` (new), `python/pyproject.toml`, `python/uv.lock` (by uv), `docs/03-data-model.md`, `docs/04-model.md`, `docs/decisions.md`.

**Test strategy** (fake client, `LocalLake` in `tmp_path`, no network)
- AC-1 `test_dry_run_counts_missing_pulls_without_calls` (client construction refused), `test_dry_run_after_partial_run_counts_the_rest`.
- AC-2 `test_budget_stop_then_resume_matches_estimate`: limit k, exit 3, the limit raised, a re-run. The ledger total equals the first estimate, and no key is fetched twice. Plus `test_season_file_final_after_season_completes` and `test_empty_season_file_final_after_seven_days`.
- AC-3 (manual): the rebuild and checks output in the PR; the dev `teams` 2026 FBS count against `team_seasons` staged `classification = 'fbs'`.
- AC-4: `test_closing_lines_median_on_fixture` (Kansas–Fresno −14, `median`, from the post-kickoff pull), then the notebook run headless.
- AC-5: `test_sync_copies_missing_both_ways_never_overwrites` (two `LocalLake`s), then the two listings compared in the PR.

**Risks / open questions**
- A failed HTTP call is counted before the request (`CallBudget.spend`), so the AC-2 ledger can exceed the estimate by failed calls. The PR lists them.
- The full-lake `closing_line`/`advanced_stats` checks may fail for games CFBD lacks. AC-3 lists each failure with its cause.

**Size check:** 12 files, no schema, no UI: passes (limit 20).

## Review log

_Filled by /implement-task. One line per round._

## Blocked

_Only if status is Blocked: what failed, what was tried, best hypothesis, decision needed._

## Metrics

- Verify rounds:
- Review rounds:
- First-pass AC FAILs:
- Plan revisions after approval:
