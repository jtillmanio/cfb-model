# Task list: cfb-model

_Written by `/milestones` on 2026-10-08 from [06-roadmap.md](06-roadmap.md). Each milestone is a demoable increment. Convert one milestone at a time with `/new-task docs/08-tasklist.md M1`. The roadmap's checklists stay the status source of truth; this file is the build plan beneath them. In the **Done** column, `✅` means every task the row names is Done; `/implement-task` and `/sync-roadmap` fill it._

## Scope

| Milestones | Scope | Roadmap phases | Stubs |
|---|---|---|---|
| M1–M8 | **MVP** (all 19 MVP features in [01 › Feature index](01-product.md#feature-index-ids-priorities-outcomes)) | 0–4 | 67 |
| M9–M19 | **Future** (Next and Later features) | 5–8 | 64 |

- **M6 is the roadmap's Phase 4 acceptance:** paste the Splash page on Thursday, see the CFB + NFL slate ranked against the contest's lines with the top 4 marked, add your picks, follow results on your phone Saturday. M7–M8 finish the rest of the MVP feature list (D-081).
- **Sizing:** the kit's guideline is 3–6 milestones for an MVP. This MVP spans five roadmap phases and needs 8; cutting to fit would reopen D-081, so the full scope stays.
- **Future milestones are a rough plan.** Each one is re-shaped at the review gate of the phase before it, and its schema proposals are reviewed before any migration (CLAUDE.md › Stop and ask). Expect them to change.

**Changes from the roadmap's phase lists**
- Phase 4 is split into M5–M8; one milestone of ~31 tasks breaks the 3–8 rule.
- The Splash paste parser moves from the start of Phase 4 to M2: it's in the architecture's risk table, and the riskiest work goes first.
- shadcn/ui setup moves from Phase 0 to M5.2, the first task that uses it.
- Notebooks #1–3 are deliverables of M2.6 and M3.5 rather than their own stubs; they're built on those tasks' output.
- `drivers` is part of M4.3, with each unit's contribution in points, since both come from the same prediction step. The margin model itself is in M4.1 (owner, 2026-10-27): M4.1's tuning on margin MAE and its tier test need margins in points.
- Phase 5's "CLV on picks and contest picks" is already MVP (F-10, D-081): model-pick CLV is in M4.6, contest-entry CLV in M6.2.
- Phase 5 splits into M9–M11, Phase 6 into M12–M13, Phase 7 into M14–M16.
- Ratings depth (added 2026-10-20, F-46 to F-51, [04 § 10](04-model.md)) is Phase 5 parts 4–5, numbered M18–M19 so the IDs of M12–M17 stay stable. The MVP keeps its scope; three MVP stubs gain a note (M3.1's input registry, M3.7's SOS view, M4.1's conference-tier test), and position-group ratings are research in M16.5.

**Runs in parallel**
- M2 can start alongside M1. Only M2.6 (backfill reaching prod) and M2.7 (scheduled jobs) wait for M1.3 `release` and the R2 account from M1.4.
- M5.1–M5.4 (format module, components, app shell, generated client) need only M1. They're the design track's "implement the design system" item and can run during M2–M4.

**Applies to every UI stub**
- Cites its S-ID, design file and reference screenshot; `Pass … .dc.html` boards win over older boards (D-094).
- Adds its Lighthouse route(s) and budget in the same PR (D-101), measured on the in-job fixture build (D-125); Game Detail and Team add a small and a large instance, and the large one is fixture data.
- Has a `loading.tsx` drawn at the loaded size, an error state without saved copies (D-096), and e2e at 390 and 1440.
- Extends the fixture seed (`python/db/seeds/fixture/`) only through the schema task that owns the table (D-089).

## Coverage

| Check | Result |
|---|---|
| MVP features covered | 19/19 |
| MVP screens covered | 12/12 (S-01, S-02, S-03, S-04, S-06, S-07, S-08, S-13, S-14, S-15, S-16, S-17) |
| MVP entities covered | 20/20 tables (5 already built by the skeleton) and 9/9 views |
| Future features scheduled | 28 of 32 Next/Later features; F-12, F-25, F-34 and F-41 have no roadmap phase (below) |
| Future screens covered | 5/5 designed (S-05, S-09, S-10, S-11, S-12), plus the undesigned History, coach, SP+/FPI, matchup and ratings-depth screens (Rankings › Units, team Stats, Confidence plays, Lab › Inputs) |

**MVP features → tasks**

| Feature | Tasks |
|---|---|
| F-01 Weekly slate | M5.5, M5.6 |
| F-02 Pick recommendations | M4.4 (logic), M5.6, M7.2 |
| F-03 Contest mode | M2.8, M6.1, M6.4, M6.5, M6.6, M6.7 |
| F-04 Contest vs market | M6.2, M6.5, M6.7, M7.3 |
| F-05 Game detail | M7.6, M7.7, M7.8 |
| F-06 Line movement | M2.5 (`game_market`), M5.5, M5.6, M7.7 |
| F-07 Best lines board | M7.3 |
| F-09 Model track record | M4.6, M5.3 (sidebar card), M7.4, M7.5 |
| F-10 CLV | M4.6, M6.2, M5.6, M7.2, M7.5 |
| F-17 Power rankings | M3.7 (`team_rankings`), M8.1, M8.2 |
| F-18 Team page | M8.3, M8.4 |
| F-19 Historical rankings | M8.1, M8.2 |
| F-32 This week's record strip | M5.7, M6.7, M6.8 |
| F-33 Contest tracker | M6.1, M6.2, M6.5, M6.7 |
| F-37 Calibration charts | M3.3 (metrics), M7.3, M7.5 |
| F-42 Sign-in | M1.1, M1.2 |
| F-43 ⌘K palette | M8.6 |
| F-44 Teams index | skeleton (built), M8.5 |
| F-45 Settings › General | M8.7, M8.8 |

**MVP entities → tasks.** Already built: `sports`, `teams`, `team_seasons`, `venues`, `games`. M2.2: `seasons`, `team_aliases`, `sportsbooks`, `line_snapshots`. M3.6: `model_versions`, `model_runs`, `team_ratings`, `predictions`. M4.5: `picks`. M6.1: `users`, `contests`, `contest_lines`, `contest_entries`, `contest_standings`. M8.7: `user_settings`. Views: `game_market` (M2.5), `team_rankings`, `team_schedule_strength` (M3.7), `current_picks`, `pick_outcomes`, `model_record` (M4.6), `current_contest_lines`, `contest_results`, current contest standing (M6.2).

**Future features → milestones.** F-08 M10 · F-11 M15 · F-13 M10 · F-14 M11 · F-15 M16 (optional) · F-16 M16 (research) · F-20, F-21 M9 · F-22 M15 · F-23 M10 · F-24 M15 · F-26–F-31 M12–M13 · F-35, F-36 M9 · F-38 M14 · F-39 M16 · F-40 M17 · F-46, F-47, F-48 M18 (v1 units M4, SOS M3.7) · F-49 M19 · F-50 M19, M14.3 · F-51 M16.

**Future entities → milestones.** `season_simulations` M9 · `manual_adjustments` M10 · weather snapshots, external benchmark ratings M10 · watchlist, `alert_rules`, alert log, `push_subscriptions` M11 · rating kind, `coaches`, `coach_tenures` M12 · `team_game_stats` and its views M18.5 · schedule-strength outputs (SOR, remaining SOS) M18.4.

**Unscheduled** (no roadmap phase): F-12 moneyline edges, F-25 win totals vs market, F-34 bet tracker (and its `bets` table), F-41 college basketball. Add a phase if one becomes worth building.

---

# MVP

## M1: Rails (rest of Phase 0) — MVP

**Goal:** finish the safety rails before the first feature, so nothing later has to retrofit them.
**Demo at exit:** sign in on the production URL from your phone and see the Teams list; that build went out through the `release` workflow; last night's backup restored cleanly. (The roadmap's Phase 0 acceptance.)
**Features:** F-42
**Depends on:** — (the skeleton, PR #5)
**Owner prerequisite:** create the Cloudflare R2 account (needed by M1.4 and M2.1).

| Done | # | Task | Layer | Size | Depends on | Autonomy | Notes |
|------|---|------|-------|------|------------|----------|-------|
| ✅ | M1.1 → TASK-001, TASK-002 | Add GitHub sign-in with an allowlist and the login screen | web | M | — | attended | F-42, S-15. Auth.js + `proxy.ts`; bad session → `/login`, never a 500; 90-day session (D-095); denied state ("This GitHub account isn't allowed"); "Waking up the database…" state. The e2e session-mint helper lives in Playwright fixtures, never in `web/` source. Design: `App States Desktop.dc.html` / `App States Mobile.dc.html` (`frame="login"`), `Pass A - Decisions.dc.html` A1a–f; shots `22-login-desktop.png`, `23-login-mobile.png` |
| ✅ | M1.2 → TASK-003, TASK-004 | Require a signed JWT on every API route except health | api | M | M1.1 | attended | D-012. Short-lived JWT from Next server code (shared secret); `/api/py/health` stays open with no data; test that every other route rejects a missing or bad token |
| ✅ | M1.3 → TASK-005 | Add the `release` workflow | ops | M | — | attended | D-018, 02 › Release & operations: plan → Neon snapshot → migrate (unpooled) → re-apply views → promote → smoke-test health; dry-run input; `concurrency: release`. Brings in `.env.live` with its explicit flag and view re-apply on release (open Phase 0 partials). Test on the branch with `gh workflow run` |
| ✅ | M1.4 → TASK-006 | Add the nightly `backup` workflow with restore verification | ops | M | — | attended | D-019, D-099: `pg_dump` on `PG_MAJOR`, restore into a container, re-apply views, run view tests, compare row counts, then upload to R2. Writes the restore runbook (RTO ≤ 2 h, 02 › Non-functional requirements). Needs the R2 account |
| ✅ | M1.5 → TASK-007, TASK-008 | Add the `lighthouse` workflow on PR previews | ops | M | M1.1 | attended | D-101, 02 › Performance checks: `scripts/perf/` with pure logic in Vitest; mint session with the preview `AUTH_SECRET`; scrub + guard reports; one PR comment. Routes `/login` and `/teams`; budgets from the first preview run |
| ✅ | M1.6 → TASK-009 | Add Dependabot and the merged-migration CI check | ops | S | — | attended | D-020, D-021: ignores for Next majors and TypeScript ≥ 7 with reasons beside them; CI fails if a migration on `main` was edited, renamed or deleted |
| ✅ | M1.7 | Block whole-file reads of data files with a PreToolUse hook | tooling | S | — | attended | **Done in the kit 2.4 upgrade (`chore/kit-2.4`); no task file needed.** The kit's `guard-large-reads.ps1` is registered in `.claude/settings.json` and reads `largeFiles` in `.claude/kit.json`: `data/*`, `*.parquet`, `*.duckdb` always denied; design boards and lockfiles denied whole |
| ✅ | M1.8 → TASK-010 | Let the ui-verifier sign in to the local dev server | tooling | S | M1.1 | attended | From the kit 2.6 upgrade (`chore/kit-2.6`). `ui.auth` is null since sign-in shipped, so the ui-verifier stops at `/login`. Agent-run session mint in `web/e2e/` (D-090, D-012); production stays GitHub-only |
| ✅ | M1.9 → TASK-011 | Add the test that forbids `<Link>` to `/api/` | web | S | — | attended | From #18 (TASK-007). `.claude/rules/web.md` says a test enforces it; none exists. `ledger` has `no-prefetched-handlers.test.ts` |
| ✅ | M1.10 → TASK-012 | Lint the scripts in `scripts/perf/` | tooling | S | — | attended | From #18 (TASK-007). `pnpm lint` covers `web/` and `python/` only |
| | M1.11 | _Moved to M5.8 (TASK-014): it needs a second signed-in screen, which M5.6 ships_ | | | | | |

## M2: Data pipeline (Phase 1) — MVP

**Goal:** all the history the model needs, clean and reproducible, with weekly refresh.
**Demo at exit:** `engine transform --rebuild` recreates every staged table from raw with zero API calls; data-quality checks pass; the scheduled job picks up Saturday's results on its own; the production Teams page lists the real 2026 FBS teams; a fresh Splash paste parses into rows. (The roadmap's Phase 1 acceptance, plus the parser spike.)
**Features:** F-03 (parser), F-06 (`game_market`)
**Depends on:** M1.3 and the R2 account for M2.6–M2.7 only; the rest can run alongside M1.
**Riskiest:** CFBD data shape and the backfill call budget; the Splash paste format.

| Done | # | Task | Layer | Size | Depends on | Autonomy | Notes |
|------|---|------|-------|------|------------|----------|-------|
| ✅ | M2.1 → TASK-015 | Build the CFBD ingest client with call-budget tracking and a raw Parquet writer | etl | M | — | attended | D-027: every call counted, warn at 80% of the month; raw is append-only, local `./data` or R2 via `LAKE_URI`; never re-fetch completed weeks. Replaces the skeleton's JSON raw files (D-098). Tests on recorded responses, no network |
| ✅ | M2.2 → TASK-016 | Add `seasons`, `team_aliases`, `sportsbooks` and `line_snapshots` | data | M | — | attended | Schema change: stop and ask at the plan gate. 03 › Reference, Games & market; `source` accepts `'fixture'`; adds fixture rows for Week 6 lines (02 › Seed data) |
| ✅ | M2.3 → TASK-017, TASK-018 | Build DuckDB staging models, `transform --rebuild` and data-quality checks | etl | M | M2.1 | attended | 03 › Lake layout, Data quality checks; rebuild with zero API calls is asserted; publishing stops on a failed check (02 › Non-functional › Data correctness) |
| ✅ | M2.4 → TASK-019 | Build point-in-time `team_week_features` and `game_features` | etl | M | M2.3 | attended | D-042, 04 § 9.2: week N uses only games before week N; every feature row carries `as_of`; "no future data" assertion; leakage test changes a later game and checks week-N rows are unchanged |
| ✅ | M2.5 → TASK-020 | Publish reference data, games and line snapshots to Postgres, with the `game_market` view | data | M | M2.2, M2.3 | attended | D-030: upsert by `(source, source_id)`, never truncate; idempotency test. `game_market`: opening, current, closing (CFBD's close, else the last snapshot before kickoff, D-120), with view tests on the fixture and an `EXPLAIN` check |
| ✅ | M2.6 → TASK-021 | Backfill 2014–2025 and 2026 to date, then explore it in notebook #1 | etl | M | M2.1, M2.3, M2.5, M1.3 | attended | Estimate calls first (~500, D-026) and get the owner's OK before spending them. Endpoints per 03 › Data sources (incl. talent, returning production, recruiting, SP+/FPI/Elo, PBP and drives). Notebook #1: HFA over time, margin distribution, closing-line MAE 2014–2025 (the Phase 1 benchmark, 04 § 9.6) |
| ✅ | M2.7 → TASK-022 | Schedule the `results` and `lines` jobs | ops | M | M2.5, M1.3 | attended | 02 › Jobs: `results` Sun/Mon 6am, `lines` daily + Thu–Fri evenings; ≤ 10 min each. Confirm CFBD's scoreboard endpoint is in tier 1 (needed by M6.8) |
| ✅ | M2.8 → TASK-023 | Parse Splash pastes against `ContestRules` (risk spike) | engine | S | — | attended | F-03; 02 › Risks: tested on `design/sample-splash-10062026.txt`, the Week 6 paste and a fresh paste from the owner. `ContestRules` pydantic model with the Splash preset (03 › Your data). Team matching takes an alias lookup as input, so no DB yet; unmatched rows are returned, not guessed |
| ✅ | M2.9 → TASK-028 | Stop a late fallback run of `results` and `lines` repeating the dispatched run | ops | S | M2.7 | attended | Follow-up from TASK-026. D-122: GitHub starts scheduled runs 5–8 h late, past `skip-if-dispatched`'s 6 h window, so the fallback reruns the job (harmless upserts, a few CFBD calls). Widen the window or check what the job produced |

## M3: Measuring stick (Phase 2) — MVP

**Goal:** the backtest harness and baselines, which come before any serious model.
**Demo at exit:** one command runs the rolling-origin backtest (2014 warm-up through 2023) and produces a report comparing Rung 1 with the baselines, and you can explain every number in it. Rung 1 ratings are published to the dev DB. (The roadmap's Phase 2 acceptance, with D-076's protocol.)
**Features:** F-37 (calibration metrics), F-17 (`team_rankings`)
**Depends on:** M2.4, M2.6
**Riskiest:** leakage in the harness.

| Done | # | Task | Layer | Size | Depends on | Autonomy | Notes |
|------|---|------|-------|------|------------|----------|-------|
| ✅ | M3.1 → TASK-029 | Define `ModelSpec` v1, the `RatingModel` / `GamePredictor` interfaces and the probability math in `engine.core` | engine | M | — | attended | D-004, D-050, 04 § 6 Engineering contract: light core only (numpy, scipy, pydantic); edge, Φ(edge/σ), EV; pick rules read from the spec (D-055). Spec inputs name entries of a small input registry holding v1's inputs (id, label, definition; 04 § 10.6, D-117), so labels live in one place from the start; M18.1 extends it. *From TASK-023 (PR #52):* `engine/core/` already exists by then, holding `contest_rules.py` (D-113); this task adds the rest of the light core beside it |
| ✅ | M3.2 → TASK-030 | Build the walk-forward rolling-origin backtest harness | engine | M | M3.1, M2.4 | attended | D-076, 04 § 9.1–9.2: (season, week) units, settings tuned only on earlier seasons, leakage assertions, refuses holdout seasons without a flag and reason, records every holdout run. Golden-number determinism test on a two-season lake fixture. *From TASK-020 (PR #62):* market lines are targets and pick-time inputs, never features (04 § 9.2), so the point-in-time assertion never reads `line_snapshots`; an untimed `opening` row counts as before kickoff, and a `closing` row is a target only |
| ✅ | M3.3 → TASK-031 | Compute backtest metrics and write the markdown/HTML report | engine | M | M3.2 | attended | 04 § 9.3–9.5: MAE/RMSE vs closing, ATS (pushes excluded), edge trend (logistic), consistency, calibration bins, CLV, ROI at −110, week-level paired bootstrap (D-091) |
| ✅ | M3.4 → TASK-032 | Add the baselines: home field only, last season carried over, closing line, SP+/FPI | engine | S | M3.2 | unattended | 04 § 2 Rung 0, § 9.6. SP+/FPI count only if published before the game; otherwise labeled "hindsight benchmark" (04 § 9.2). *From TASK-018 (PR #62):* staged `benchmark_ratings` rows carry `season_final` and `known_at` (NULL when season-final); use only rows with `known_at` before kickoff. Backfilled SP+/FPI are season-final, so hindsight only. A weekly `/ratings/elo?week=` pull would give pre-game Elo, but the registry pulls Elo per season. *From TASK-021 (PR #62):* the closing-line baseline reuses `engine.transform.market.closing_lines()`, so it matches notebook #1's recorded benchmark. *From TASK-021 (PR #67):* CFBD's `consensus` line stops in late 2023 (29 of 792 games in 2023, none in 2024–2025), so later closing lines are medians across books; check that the closing-line baselines don't shift at that seam (notebook #1's per-season MAE: 12.11 in 2023, 12.07 in 2024) |
| ✅ | M3.5 → TASK-033 | Build Rung 1 least-squares power ratings, plus notebooks #2–3 | engine | M | M3.2 | attended | 04 § 2 Rung 1: margin cap, recency weighting, priors from last season. Must beat both Phase 2 baselines on pooled validation (04 § 9.6). Notebooks: ratings by hand; ratings → probabilities |
| ✅ | M3.6 → TASK-034 | Add `model_versions`, `model_runs`, `team_ratings` and `predictions` | data | M | — | attended | Schema change: stop and ask. 03 › Models & outputs: one production version per sport per market (partial unique index); `fitted_params` and `metrics` jsonb. Insert-only (hard rule 2) with a test. Fixture model registry rows per 02 › Seed data |
| ✅ | M3.7 → TASK-035 | Publish model runs, ratings and predictions, with the `team_rankings` and `team_schedule_strength` views | data | M | M3.5, M3.6 | attended | Hard rules 1–2: rank and Δ are a window-function view, never stored; re-runs insert new rows tied to a `model_run`. `team_schedule_strength`: SOS = average rating entering the week of opponents already played, site-adjusted, with its rank (04 § 10.5); F-17's "SOS 34" and F-18's "34th SOS rank" read it, and no task computed it before 2026-10-20. View tests on the fixture |

## M4: Model v1 and paper trading (Phase 3) — MVP

**Goal:** a model good enough to paper-trade the back half of 2026.
**Demo at exit:** a go/no-go report for v1 on 2016–2023 (or a written reason it fell short and what changes); the Sunday job rates, predicts and picks the coming week by itself, and the views grade last week's picks. (The roadmap's Phase 3 acceptance.)
**Features:** F-02 (logic), F-09, F-10 (views)
**Depends on:** M3
**Riskiest:** v1 fails the gates, which delays paper trading.

| Done | # | Task | Layer | Size | Depends on | Autonomy | Notes |
|------|---|------|-------|------|------------|----------|-------|
| ✅ | M4.1 → TASK-036 | Build Rung 2 ridge opponent-adjusted efficiency ratings and the margin model | engine | M | M3 | attended | 04 § 2 Rung 2: off/def with rush/pass splits, and the linear margin model that turns them into points (moved here from M4.3, owner 2026-10-27); settings tuned to margin MAE, not ATS (04 § 9.2). Tests `shrink_toward: tier` (Power 4 / G5 / FCS, per-season map in `sports/cfb`) against `zero` (04 § 10.4); `conference` waits for M19.1. *From TASK-031 (M3 task files):* the backtest report's conference-tier breakdown (04 § 9.4 › Breakdowns) waits for this task's tier map; TASK-031's breakdowns group by any per-game column, so this task supplies a tier per game and adds the breakdown. *From TASK-031 (PR #91):* the hook is `engine.backtest.metrics.breakdown(name, games, key)`, added to the tuple in `metrics.compute` with a key that returns a game's tier |
| ✅ | M4.2 → TASK-037 | Add preseason priors with fitted decay blending | engine | M | M4.1 | attended | 04 § 2 Preseason priors: returning production, talent, recruiting from values published before the season; decay fitted, not fixed. *From TASK-018 (PR #62):* CFBD's talent, returning production and recruiting carry no publication date, and backfilled pulls are fetched after the season, so "published before the season" has to be assumed per source. *From TASK-020 (PR #62):* Postgres `team_seasons.talent` and `returning_ppa_pct` stay NULL until this task publishes them from staging |
| ✅ | M4.3 → TASK-038 | Rate units in points, with `drivers` and the empirical margin distribution | engine, data | M | M4.1, M4.2 | attended | D-053, 04 § 6: `drivers` as `(label, points)` contributions that sum to the model margin (F-05's waterfall depends on this). The overall rating is the sum of the offense and defense contributions in points (special teams 0 until M18.3), with a test (04 § 10.2, D-117). The margin model is M4.1's (owner, 2026-10-27). `engine rate` also writes `team_ratings.off_rating`, `def_rating` and `components` (owner, 2026-10-27). *From TASK-031 (PR #91):* the backtest grades cover probabilities with `NormalMargin(margin_sd)` per row (`engine.backtest.metrics.grade_rows`); when the empirical distribution lands, the harness rows must carry what it needs and `grade_rows` must use it, or calibration and picks are graded on the wrong curve (D-132 › Revisit if) |
| ✅ | M4.4 → TASK-039 | Tune pick rules: thresholds, tiers and market shrinkage | engine | M | M4.3 | attended | D-055, 04 § 4, § 9.2: tuned on ATS vs closing, only on choices backed by ≥ 200 picks; shrinkage stays only if validation ATS is at least as good as k = 1; no picks on FBS vs FCS (D-047). *From TASK-038 (PR #103):* under `distribution: empirical`, when a key number makes the liked side the one the edge leans against (D-139), `core.picks.pick` still qualifies and tiers the pick on `abs(edge)`, so it can pick a side the model's own margin disagrees with: pass such a game or measure the edge for the liked side. Moot while v1 keeps `normal` |
| ✅ | M4.5 → TASK-040 | Add the `picks` table | data | S | M3.6 | attended | Schema change: stop and ask. 03 › Models & outputs: exactly one of `line_snapshot_id` / `contest_line_id`; insert-only. Fixture: the 9 week-6 picks and 56 graded 2026 picks (02 › Seed data) |
| ✅ | M4.6 → TASK-041 | Add the `current_picks`, `pick_outcomes` and `model_record` views | data | M | M4.5 | attended | Hard rule 1. Fixture expectations: v1.0 2026 = 31-24-1, 56.4%, +4.6u, ROI +7.6%, avg CLV +0.9 (F-09); pushes left out of win %, units at −110 (04 § 9.3). `EXPLAIN` check |
| ✅ | M4.7 → TASK-042, TASK-043 | Run the holdout evaluation and the go/no-go for v1 | engine | S | M4.4 | attended | D-076, D-077, 04 § 9.4: holdout 2024–2025 run once with a written reason; the owner decides promotion. Result decides whether the "uncalibrated" label shows (F-37). *From TASK-036 (PR #101):* `engine backtest --compare baselines` refuses an efficiency spec, since `home_field` and `last_season` wrap only a model that fits on games alone (D-133) and Rung 2 also reads `team_game_stats`; Rung 2 against Rung 1 is `engine compare RUN_A RUN_B` (D-137). If v1's go/no-go wants the Rung 0 rows too, the wrappers must hand the inner model its inputs. *From TASK-037 (PR #102):* under the fitted prior every 2016–2023 season picked `ridge_alpha` 2, the top of `efficiency-v1.json`'s grid {0.5, 1, 2}: widen it before the holdout run. The four preseason components beat the old last-season prior with linear decay (−0.13) but not yet last season alone with the fitted decay (−0.05, −0.12 to +0.01; D-138): recheck that on the final v1 before promotion. *From TASK-039 (PR #106):* market shrinkage was dropped on § 9.6's ATS bar (53.7% tuned against 55.1% at k = 1, D-141), yet it was what made the displayed cover probability honest (cover Brier 0.2500 against 0.2611; one calibration bin off against six), so at k = 1 the calibration gate fails: the go/no-go needs a way to calibrate the displayed probability without moving the pick threshold (a display-only shrinkage, or M19.2's per-game σ). Also read the final v1 run's week-of-season breakdown before deciding: 04 § 4's "skip early-season games where the prior still dominates" isn't a rule yet |
| | M4.8 → TASK-044, TASK-045, TASK-046 | Run the production weekly cycle: rate → predict → pick | ops | M | M4.6, M4.7, M2.7 | attended | 02 › Jobs: `rate-and-predict` Sun 9am, predictions out by Sun 10 AM ET (D-092); `lines` re-evaluates picks when lines move, inserting new pick rows. Paper trading 2026 starts here. *From TASK-022 (PR #62):* the `results` and `lines` jobs stage one season in a scratch lake, so they never refresh R2 `staging/` or the feature tables; `rate-and-predict` needs its own rebuild of history. *From TASK-035 (PR #97):* the transform stages only `final` and `scheduled` (from CFBD's `completed`), so `engine rate`'s canceled/postponed filter never matches and a canceled game gets a permanent prediction: stage those statuses (or find CFBD's signal) before predictions go out weekly. `engine rate` also re-reads staged `games` and re-derives a TBA kickoff in Python (`publish/models.py` `_kickoff`, a copy of `features.KICKOFF`); have `harness.load` keep each week's staged contexts instead. *From TASK-040 (PR #105):* the writer inserts a pick row only when the side or tier differs from the current pick (a pass row when the pick drops), so a pick keeps the line it was made at (Ole Miss stays "Picked at −2.5"); `edge_pts` and `model_prob` are on the blended margin `core.picks.pick()` returns; a pick points at one book's `line_snapshots` row (consensus when it quoted the pull; a pull with no consensus quote needs a rule for which book) and `line` is that row's spread, `price` −110 when the row quotes none (D-140). Consider a CHECK that `line` is NULL only for moneyline (schema change: stop and ask). *From TASK-039 (PR #106):* the writer picks through `core.picks.pick_game(game, …, pickable)` with `engine.sports.cfb.teams.pickable`, never `pick()` directly, so no game with an FCS team is picked (D-047) *From TASK-041 (PR #107):* the pick views count only rows made before the game's cutoff (kickoff, or the end of `game_date` in Eastern time when TBA), so a pick written at or after kickoff is silently ignored: have the writer refuse one, with a test. The views grade spread picks only: add total (combined points against `line`, CLV against `closing_total`) and moneyline (the winner, units from `price`) grading to `pick_outcomes` when the writer first writes those markets. A CHECK that `price` is ≤ −100 or ≥ +100 would keep units sane (schema change: stop and ask) (D-142) |

## M5: This Week (Phase 4, part 1) — MVP

**Goal:** the app's home screen on real data, on desktop and phone.
**Demo at exit:** signed in on production, This Week shows the real current week: Market (opener + sparkline), Model, Edge pill, cover %, tier, row states (final, live, no line, neutral), the record strip, and phone cards with no horizontal scroll.
**Features:** F-01, F-02, F-06, F-10, F-32
**Depends on:** M1 for M5.1–M5.4; M4.6 and M2.5 for M5.5–M5.7; M1.5 for M5.0; M1.5 and M5.6 for M5.8
**Riskiest:** getting the app shell's data (sidebar track-record card) into each page's single API call.

| Done | # | Task | Layer | Size | Depends on | Autonomy | Notes |
|------|---|------|-------|------|------------|----------|-------|
| ✅ | M5.0 → TASK-027 | Gate Lighthouse on an in-job build on the seeded fixture DB | ops | M | M1.5 | attended | D-125 (settles roadmap open question 5): build and serve the app and API in the job on the seeded test DB as e2e does; gates and budgets move there; the PR preview is measured and reported, never gated. Must land before M5.6 sets the first data-heavy budget |
| | M5.1 | Implement `format.ts` against the number-format card | ui | S | — | attended | D-068: every example in 02 › Testing strategy (Unit: web) as a Vitest case; true minus, padded whole spreads, model lines one decimal; zone-aware kickoff times |
| | M5.2 | Set up shadcn/ui and build the core components | ui | M | M5.1 | attended | The design track's design-system PR and review gate. Edge pill (filled ≥ 2.5, D-061), tier badge (D-063), team chip (D-075), result marker, market cell with sparkline, filter chips, data table densities (D-084). Hard rule 7: tokens only. Design: `Components.dc.html`, `Foundations.dc.html`, `Market Extras.dc.html`, `design/README.md` |
| | M5.3 | Build the app shell and global states | ui | M | M5.2, M1.1 | attended | S-16. Desktop sidebar with track-record card, top bar, mobile tabs + More, tablet nav at 768, API unreachable with Retry (no saved copy, D-096), wake-up note after 1.5 s and 10 s timeout (D-097); reuse `raceWakeNote` from `web/lib/login.ts` (from #15), stale-lines banner. Sport switcher shows CFB only. Decide at the plan gate how shell data rides in each page's one API call. Design: `App States Desktop.dc.html` / `App States Mobile.dc.html`, `This Week Tablet.dc.html`, `Pass B - New Screens.dc.html` B8a, `Pass C3 - Alerts Settings Shell.dc.html` C16a–c; shots `01-this-week-desktop.png`, `27-more-mobile.png`, `28-this-week-tablet.png` |
| | M5.4 | Generate the TypeScript API client from OpenAPI | web | S | — | attended | D-011: `openapi-typescript`; CI fails on drift; `/teams` moves onto it |
| | M5.5 | Build the `/slate` endpoint | api | M | M4.6, M2.5, M5.4 | attended | First screen endpoint (BFF pattern, D-010): games for a week with `game_market` opener/current/snapshots, latest prediction, current pick, pick outcomes for the record strip; ≤ 6 queries in one wave; fixture values from F-01. *From TASK-016 (PR #52):* the fixture still lacks the other 43 Week 6 games behind "54 games" (Tulane @ Memphis final 27-24, Iowa State @ Cincinnati, Arizona State @ Baylor, and filler with edges under 1.0; 02 › Seed data); this task adds them. *From TASK-034 (M3 task files):* TASK-034 seeds v1.0 predictions for the 11 Week 6 games seeded then; this task seeds a v1.0 prediction for each game it adds (filler edges under 1.0), in the same fixture file. *From TASK-040 (PR #105):* TASK-040 seeds Tulane @ Memphis, Iowa State @ Cincinnati and Arizona State @ Baylor (lines, v1.0 predictions and picks, in `picks.json`), so this task adds the other 40 Week 6 games, not 43 *From TASK-041 (PR #107):* `current_picks` is the pick frozen at kickoff; `pick_outcomes` gives each pick's `result`, `units`, `clv` (against the close, NULL until `closing_spread_home` is set) and `clv_so_far` (against the current line, for the "so far" label before kickoff) (D-142) |
| | M5.6 | Build the This Week slate | ui | M | M5.3, M5.5 | attended | S-01, F-01/F-02/F-06/F-10. Compact desktop table (D-084), 768 layout, 390 cards; row states (upcoming pick, line moved since pick, live, final, no line, neutral); day/time windows. Spread/Total/Both and the star are hidden until F-11/F-14. Set this route's budget on the fixture build (D-125, M5.0 → TASK-027); the fixture's full Week 6 slate from M5.5 is the large case. Design: `This Week Desktop.dc.html`, `This Week Mobile.dc.html`, `This Week Tablet.dc.html`, `Pass C1 - Slate Contest Game.dc.html` C1a–e; shots `01-this-week-desktop.png`, `02-this-week-mobile.png`, `28-this-week-tablet.png`. TASK-014 (M5.8) waits on this task: add its ID to TASK-014's `depends_on` when the file is created. *From TASK-016 (PR #59):* the fixture has each game's opener (Sun 6:00 AM ET) and current line (Thu 9:02 PM ET) only, plus Texas vs Oklahoma's four and BYU's three snapshots; if a sparkline AC cites `this-week-data.js`'s illustrative in-between points (e.g. LSU −2.5, −2.5, −3, −3.5), this task adds them |
| | M5.7 | Add the record strip, filters and empty states to This Week | ui | M | M5.6 | unattended | S-01, F-32: "This week 1-0 · 2 live …", live picks never shown as lost; All / Picks only; lines not posted, off-season, stale banner; loading skeleton. Design: `This Week.dc.html`, `App States Desktop.dc.html` (off-season), `Loading States.dc.html`; shots `20-offseason-empty-desktop.png`, `21-offseason-empty-mobile.png` |
| | M5.8 → TASK-014 | Time screen-to-screen taps in the lighthouse workflow | ops | M | M1.5, M5.6 | attended | Draft, from #29 (TASK-008); moved from M1.11. `ledger`'s tap → next-paint runner; This Week → Teams is the first tap to time. Needs an approved change to 02 › Performance checks and D-101 |

## M6: Contest (Phase 4, part 2) — MVP, Phase 4 acceptance

**Goal:** the Thursday Splash flow, from paste to graded picks.
**Demo at exit:** on a Thursday you paste the Splash page and see the whole CFB + NFL slate ranked against the contest's lines with the top 4 marked; you add your picks; on Saturday you follow results from your phone. (The roadmap's Phase 4 acceptance.)
**Features:** F-03, F-04, F-32, F-33
**Depends on:** M5, M4, M2.8
**Riskiest:** kickoff-lock enforcement; matching Splash's NFL names to nflverse teams.

| Done | # | Task | Layer | Size | Depends on | Autonomy | Notes |
|------|---|------|-------|------|------------|----------|-------|
| | M6.1 | Add `users`, `contests`, `contest_lines`, `contest_entries` and `contest_standings` | data | M | M2.2 | attended | Schema change: stop and ask. 03 › Your data and Proposed additions (`contest_standings`); soft delete (D-033); catalog vs per-user (D-034). Fixture: Splash work league, Week 6 contest lines, entries OU +7 / BUF −3, weeks 1–5 entries, standing 3rd of 14. *From TASK-040 (PR #105):* add `picks.contest_line_id` (foreign key to `contest_lines`), make `picks.line_snapshot_id` nullable with an exactly-one CHECK, and let `picks.price` be NULL for a no-vig contest pick (D-140) *From TASK-041 (PR #107):* `current_picks` and `pick_outcomes` derive `line_source` 'market' from `line_snapshot_id` (a CASE with no ELSE), and `pick_outcomes` grades at `price`: when `line_snapshot_id` becomes nullable, set `line_source` 'contest' for a `contest_line_id` pick and keep contest picks out of the market grading (a NULL price gives NULL units); `model_record` already counts `line_source = 'market'` only (D-142) |
| | M6.2 | Add the `current_contest_lines`, `contest_results` and current-standing views | data | M | M6.1, M4.6 | attended | Hard rule 1. Grades entries and the model's top N with the contest's push rule (Splash: push = 0, D-045); contest-entry CLV. Fixture: you 12-8, model top 4 11-9 |
| | M6.3 | Ingest the NFL schedule, scores and closing lines from nflverse | etl | M | M2.5 | attended | D-039: into `games` under `sport_id = 'nfl'`; NFL team aliases for Splash names. Raw lake + upsert by source key like CFBD. *From TASK-016 (PR #52):* the fixture still lacks the 5 NFL games (sample-data §3) and the `nfl` sports row; this task adds them |
| | M6.4 | Build the contest import API: paste → parse → match → confirm | api | M | M6.1, M2.8 | attended | F-03 AC-1: "9 rows match · 1 unmatched"; mapping saves a team alias; confirm writes a `contest_lines` snapshot; unparseable and no-match responses. *From TASK-016 (PR #52):* the fixture needs `splash` aliases for every Week 6 paste name except "Hou Texans" and "Jax", so the import shows "9 rows match · 1 unmatched". *From TASK-023 (PR #52):* build the parser's alias lookup from `team_aliases WHERE source = 'splash'` and pass the user's time zone to `parse_splash` |
| | M6.5 | Build the contest page API: ranked slate, entries with kickoff lock, results and standing | api | M | M6.2, M6.4 | attended | F-03 AC-2/3, F-04: rank by cover % against the contest line, market gap only for "No model yet" games (04 § 4); rejects entries after `kickoff_at` (test); standing entered by hand. Decide at the plan gate whether the model's contest picks are inserted on confirm or by the `lines` job |
| | M6.6 | Build the Contest paste flow | ui | M | M6.4, M5.3 | attended | S-02: empty hero "Paste from Splash", raw text beside parsed rows, inline team picker for unmatched rows, Confirm disabled until resolved, bad-paste states, re-paste diff. Design: `Contest Desktop.dc.html`, `Contest Mobile.dc.html`, `Contest.dc.html`, `Pass C1 - Slate Contest Game.dc.html` C2a–f; shots `03-contest-desktop.png`, `04-contest-mobile.png` |
| | M6.7 | Build the ranked contest slate, pick tray and results | ui | M | M6.5, M6.6 | unattended | S-02, F-03/F-04/F-32/F-33: "MODEL'S TOP 4" cutoff, ≠ chips, one-tap add (no "Lock" verbs, D-070), tray "2 of 4" with locked-in times, "Picks closed", Use the model's top 4, copy picks, results & standing with Edit, rules. Design and shots as M6.6 |
| | M6.8 | Refresh this week's scores during game windows (`scores` job) | ops | S | M2.7, M6.3 | attended | 02 › Jobs: about every 30 min Thu–Sat; CFBD scoreboard (~25 calls/week) and nflverse for NFL contest games; grading stays in the views |

## M7: Track record and why (Phase 4, part 3) — MVP

**Goal:** see whether the model is working, and why it likes a game.
**Demo at exit:** Picks shows this week's picks with Picked at / Now / CLV, Best lines (Splash vs Market) and past weeks; Performance shows the live 2026 record with backtest numbers framed apart; Texas vs Oklahoma's Game Detail shows The Number, the drivers waterfall, the margin distribution and the unit matchup.
**Features:** F-02, F-04, F-05, F-06, F-07, F-09, F-10, F-37
**Depends on:** M6 (contest lines for Best lines), M5
**Riskiest:** the "UNCALIBRATED" label must turn off everywhere at once from one source.

| Done | # | Task | Layer | Size | Depends on | Autonomy | Notes |
|------|---|------|-------|------|------------|----------|-------|
| | M7.1 | Build the `/picks` endpoint | api | M | M5.5, M6.2 | unattended | Week picks (picked-at line, now, CLV so far/final, edge now vs at pick, cover now vs at pick), best lines (better of market and contest line, tagged), past weeks, calibration status from the production run's metrics |
| | M7.2 | Build Picks › Week and Past weeks | ui | M | M7.1 | unattended | S-07, F-02/F-10: sorted by tier then edge; record strip; filters (mobile sheet); no picks this week; week 1 empty. Design: `Picks Desktop.dc.html`, `Picks Mobile.dc.html`, `Picks - Performance.dc.html`, `Pass C2 - Rankings Team Picks Lab.dc.html` C7a–h; shots `11-picks-desktop.png`, `12-picks-mobile.png` |
| | M7.3 | Build the Best lines board on Picks and This Week, with the UNCALIBRATED label | ui | M | M7.1, M5.6 | unattended | S-07, S-01, F-07/F-04/F-37: written as the bet, threshold cutoff line, "Splash only" chip, banner quoting the backtest; one source decides the label app-wide. Design: `Picks Desktop.dc.html`, `This Week.dc.html` 1b; shots `11-picks-desktop.png`, `01-this-week-desktop.png` |
| | M7.4 | Build the `/performance` endpoint | api | M | M4.6 | unattended | F-09/F-37: KPIs from `model_record`, units by week, pick buckets (display only, D-077), calibration bins, breakdowns; backtest numbers from `model_runs.metrics`, never added into live totals (D-071). *From TASK-040 (PR #105):* the fixture's picks don't follow `picks-data.js`'s conference and favorite/underdog splits (`byConf`, `byFav`); an AC citing them needs `python/db/seeds/fixture/generate_picks.py`'s weeks 1–4 draw fixed to them first *From TASK-041 (PR #107):* every `model_record` row runs through a week: the season KPIs are the newest week's `to_date` row, tiers and pick buckets its `tier` and `bucket` rows, units by week the `week` rows (the cumulative line is the `to_date` units); `win_pct` and `roi_pct` are 0–100; conference and favorite/underdog breakdowns read `pick_outcomes` (D-142) |
| | M7.5 | Build the Performance screen | ui | M | M7.4 | unattended | S-08: KPI tiles with break-even tick and 95% range, units chart (live solid, backtest dashed), edge buckets (y-axis from 50%), calibration chart with `--neg` gap lines and table, breakdowns; mobile summary + stacked detail (D-087). Version compare and menu wait for M9 (F-36). Split at `/new-task` if over 8 files. Design: `Performance Desktop.dc.html`, `Performance Mobile.dc.html`, `Pass B - New Screens.dc.html` B9a–d, `Pass C2` C8a–d; shots `13-performance-desktop.png`, `14-performance-mobile.png` |
| | M7.6 | Build the `/games/{id}` endpoint | api | M | M5.5 | unattended | F-05/F-06: The Number, prediction and pick history, drivers, σ and distribution, unit matchup percentiles, every line snapshot. *From TASK-038 (PR #103):* evaluate the run's distribution with `EmpiricalMargin.from_params(fitted_params)`, falling back to `NormalMargin(margin_sd)` when it returns None (every v1 run: v1 keeps `normal`, D-139). Drivers are labelled home/away (`<input label>: home offense vs away defense`) for the UI to name, and there's no special-teams entry until M18.3 rates it |
| | M7.7 | Build Game Detail: The Number, line movement and status states | ui | M | M7.6 | attended | S-03, F-05/F-06/F-10. First Recharts chart (D-006): line-movement step chart with kickoff marker, past seasons as open/close dashed. Status band for live/final ("Pregame · frozen at kickoff"), no line, not a pick. Design: `Game Detail Desktop.dc.html`, `Game Detail Mobile.dc.html`, `Game Detail States.dc.html`, `Pass C1` C3a–j; shots `05-game-detail-desktop.png`, `06-game-detail-mobile.png` |
| | M7.8 | Build Game Detail: drivers, margin distribution and unit matchup | ui | M | M7.7 | unattended | S-03, F-05 AC-2/3: neutral waterfall with running total (D-071), Plain English / Show the math, σ curve with 46/17/37 bar, percentile bars (D-073); manual adjustment drawn disabled, "Coming later". Design and shots as M7.7, plus `Charts.dc.html` |

## M8: Rank and navigate (Phase 4, part 4) — MVP

**Goal:** browse teams and rankings, jump anywhere, and set your preferences. Finishes the MVP.
**Demo at exit:** Rankings with the SEC chip and the time machine one week back; Ohio State's team page; the Teams index filtering "ohio" with the MAC chip; ⌘K finding Ohio State; Settings switching theme and time zone, with kickoff times following.
**Features:** F-17, F-18, F-19, F-43, F-44, F-45
**Depends on:** M5, M3.7
**Riskiest:** ⌘K needs data without the browser calling the API (hard rule 5).

| Done | # | Task | Layer | Size | Depends on | Autonomy | Notes |
|------|---|------|-------|------|------------|----------|-------|
| | M8.1 | Build the `/rankings` endpoint with the time machine | api | S | M3.7, M5.4 | unattended | F-17/F-19: ratings stored at the time for any (season, week) since 2014, never recomputed; rank and Δ from `team_rankings`, SOS from `team_schedule_strength`. *From TASK-040 (PR #105):* the weeks 1–5 final games TASK-040 seeds give the teams that played them a `team_schedule_strength` entering week 6, so the fixture's SOS ranks won't match sample-data § 4 (Ohio State 34, Texas 21, …); an AC citing those needs fixture games that produce them |
| | M8.2 | Build Rankings › Power | ui | M | M8.1, M5.3 | unattended | S-04: columns per F-17 AC-1, ratings in ink (D-064), FBS only default, conference chips, sortable headers, time machine popover/sheet, past-week banner, History tab disabled. Design: `Rankings Desktop.dc.html`, `Rankings Mobile.dc.html`, `Pass C2` C4a–f; shots `07-rankings-desktop.png`, `08-rankings-mobile.png` |
| | M8.3 | Build the `/teams/{id}` endpoint | api | M | M3.7, M5.5 | unattended | F-18: header numbers, trajectory with prior, schedule with market/model/edge/result/ATS, unit profile percentiles, preseason vs now. *From TASK-016 (PR #52):* the fixture still lacks Ohio State's weeks 1–7 lines (sample-data §6); this task adds them |
| | M8.4 | Build the Team page | ui | M | M8.3 | unattended | S-06, F-18: 3px team-color bar, trajectory chart with dashed prior line, schedule table, percentile bars, preseason state, FCS (schedule only). "Path to the playoff" waits for M9. Design: `Team Desktop.dc.html`, `Team Mobile.dc.html`, `Pass A` A5a–f, `Pass C2` C6a–f; shots `09-team-desktop.png`, `10-team-mobile.png` |
| | M8.5 | Finish the Teams index | api, ui | M | M8.1 | unattended | S-17, F-44: grows the skeleton's list into record, rating (rank) and next game · model line; filter box with match highlight, single-select conference chips, no-match empty state with "Clear filters". Design: `Teams Desktop.dc.html`, `Teams Mobile.dc.html`, `Pass B` B7a–j; shots `25-teams-desktop.png`, `26-teams-mobile.png` |
| | M8.6 | Build the ⌘K command palette | web | M | M5.3 | attended | S-14, F-43 (D-088): teams, this week's games and screens; "G then a letter" shortcuts; recent teams in browser storage; mobile full-screen sheet. Decide at the plan gate how it gets data server-side. Design: `Command Palette.dc.html`, `Palette Login Settings.dc.html`, `Pass C3` C14a–d; shot `19-command-palette.png` |
| | M8.7 | Add the `user_settings` table | data | S | M6.1 | attended | Schema change: stop and ask. 03 › Proposed additions: theme `dark|light|system` (D-095), time zone (NULL = device), default contest |
| | M8.8 | Build Settings › General, Contests and Account | api, ui | M | M8.7 | attended | S-13, F-45 (D-086): theme, default contest, time zone with device toggle and preview; kickoff times render in the chosen zone everywhere; Contests as a read-only list ("Add contest" isn't designed); Account with Sign out. Design: `App States Desktop.dc.html` (`frame="settings"`), `Palette Login Settings.dc.html`, `Pass A` A2a–h, `Pass C3` C12c/f; shot `24-settings-general-desktop.png` |

---

# Future

## M9: Season outlook and model weights (Phase 5, part 1) — Future

**Goal:** projected records and title odds, and the first read-only Model Lab.
**Demo at exit:** Rankings › Season Outlook shows each team's win distribution and conference odds; Ohio State's page shows "Path to the playoff" (no CFP %, D-081); the Lab shows v1.0's weights and compares two versions.
**Features:** F-20, F-21, F-35, F-36
**Depends on:** M8

| Done | # | Task | Layer | Size | Depends on | Autonomy | Notes |
|------|---|------|-------|------|------------|----------|-------|
| | M9.1 | Add the `season_simulations` table | data | S | — | attended | Schema change: stop and ask. 03 › Models & outputs; `p_playoff`/`p_title` stay NULL until M15 |
| | M9.2 | Simulate seasons: records, win distributions, conference title odds | engine | M | M9.1 | attended | 04 § 3: Monte Carlo over the remaining schedule with conference tiebreakers. Must beat frozen-prior sims on Brier at weeks 4, 8, 12 of 2016–2023 (04 § 9.6) |
| | M9.3 | Run season sims in the weekly job and publish them | ops | S | M9.2 | attended | Inside `rate-and-predict`; stays within ≤ 10 min (D-092) |
| | M9.4 | Build the `/outlook` endpoint and the team-page outlook data | api | M | M9.3 | unattended | F-20/F-21 |
| | M9.5 | Build Season Outlook and the team page's "Path to the playoff" | ui | M | M9.4 | unattended | S-05, S-06: histograms and odds cells; preseason with no sims. The conference view isn't designed: design it first or leave it out. Design: `Rankings Desktop.dc.html` (`tab="outlook"`), `Pass C2` C5a–f, `Team Desktop.dc.html` (`phase`); no screenshot for S-05 |
| | M9.6 | Build the `/lab` endpoints: weights, versions, compare | api | M | — | unattended | F-35/F-36: spec settings next to `fitted_params` with plain-English labels; also feeds Performance's version compare |
| | M9.7 | Build Model Lab › Weights, Versions and Compare | ui | M | M9.6 | unattended | S-09 (desktop only by design), plus Performance's version menu and compare (S-08). Design: `Lab Desktop.dc.html`, `Model Lab.dc.html`, `Pass C2` C9a–d; shot `15-lab-desktop.png` |

## M10: Adjustments, weather and benchmarks (Phase 5, part 2) — Future

**Goal:** your own injury adjustments, weather flags, and a side-by-side with SP+/FPI/Elo.
**Demo at exit:** enter "QB out, −4" on Game Detail and see the recomputed line, with adjusted and pure-model records kept apart; windy and rainy games carry a flag; the benchmark view compares our ratings with SP+, FPI and Elo.
**Features:** F-08, F-13, F-23
**Depends on:** M9 (or M8; nothing here needs sims)

| Done | # | Task | Layer | Size | Depends on | Autonomy | Notes |
|------|---|------|-------|------|------------|----------|-------|
| | M10.1 | Add the `manual_adjustments` table | data | S | — | attended | Schema change: stop and ask. 03 › Your data; soft delete; audit trail |
| | M10.2 | Apply adjustments in predictions and track adjusted vs pure results | engine, data | M | M10.1 | attended | `predictions.adjustments_applied`; `model_record` splits adjusted and pure (04 § 9.6) |
| | M10.3 | Build the adjustment API and enable Game Detail's adjustment panel | api, ui | M | M10.2 | attended | S-03: team, points, reason, recomputed line and edge (light core on the API). Design: `Game Detail Desktop.dc.html`; shot `05-game-detail-desktop.png` |
| | M10.4 | Add weather snapshots and the weather-flag view | data | S | — | attended | Schema proposal first (03 › Phase 5). Flag thresholds in the view (D-083) |
| | M10.5 | Snapshot Open-Meteo forecasts for this week's outdoor games | etl | M | M10.4 | attended | D-040: in the `lines` job; domes skipped; forecasts only, never observed weather in backtests |
| | M10.6 | Show weather flags on the slate and Game Detail | ui | M | M10.5 | unattended | S-01 tooltip and mobile tap, S-03 panel (forecast, dome, no data). Design: `Market Extras.dc.html`, `This Week Desktop.dc.html`, `Game Detail Desktop.dc.html` |
| | M10.7 | Design and build the SP+/FPI/Elo comparison view | data, ui | M | — | attended | F-23: not designed yet; needs a Claude Design pass and a storage proposal for published benchmark values (point-in-time labels per 04 § 9.2) |

## M11: Watchlist and alerts (Phase 5, part 3) — Future

**Goal:** star games and hear about it when they become picks or their lines move.
**Demo at exit:** star BYU; when the `lines` job sees its line move ≥ 1.0 or an edge cross the threshold, an alert arrives once by email (or push), and the bell shows it unread.
**Features:** F-14
**Depends on:** M8.7 (`user_settings`)
**Open question first:** the alert delivery channel (email or web push).

| Done | # | Task | Layer | Size | Depends on | Autonomy | Notes |
|------|---|------|-------|------|------------|----------|-------|
| | M11.1 | Add the watchlist, alert rules and alert log | data | M | M8.7 | attended | Schema change: stop and ask. 03 › Phase 5 and Proposed additions: `alert_rules` defaults per D-082, alert log with `read_at`, delivery on `user_settings` |
| | M11.2 | Send alerts from the `lines` job | ops | M | M11.1 | attended | Edge crossed (all games) and line moved (starred, ≥ 1.0); never sent twice; email delivery (02 › Hosting: e.g. Resend) |
| | M11.3 | Add web push with email fallback | web, ops | M | M11.2 | attended | Only if push is chosen; `push_subscriptions`; denied → email (D-095) |
| | M11.4 | Star games on This Week, Contest and Game Detail | api, ui | M | M11.1 | unattended | S-01 Starred filter and no-starred state, S-02, S-03 |
| | M11.5 | Build the alerts panel and bell | ui | M | M11.2 | unattended | S-11: grouped by week, Mark all read, empty/loading/error. Design: `Watchlist - Alerts.dc.html`, `Alerts Mobile.dc.html`, `Pass C3` C11a–f; shot `18-alerts-mobile.png` |
| | M11.6 | Build Settings › Alerts | ui | M | M11.1 | unattended | S-12: delivery, both rules with scope menus, half-point stepper, snapshot-lag note. Design: `Settings Desktop.dc.html`, `Pass C3` C12a/b/d/e; shot `17-settings-alerts-desktop.png` |

## M18: Ratings depth (Phase 5, part 4) — Future

_Added 2026-10-20 and numbered after M17 so the IDs of M12–M17 stay stable. It runs in Phase 5, alongside or after M9–M11._

**Goal:** every team rated unit by unit, with opponent-removed stats and schedule strength beside the ratings, entering any week.
**Demo at exit:** Rankings › Units sorts by rush defense; Power shows SOR beside SOS; Ohio State's Stats module reads "480 yds/game against defenses that allow 352 to everyone else, +128"; offense + defense + special teams add up to the overall rating; the time machine shows the same views for 2019 Week 8.
**Features:** F-46, F-47, F-48
**Depends on:** M8 (MVP done), M4.8 (weekly cycle); Prompt 13's frames for M18.7
**Riskiest:** our garbage-time filter on play-by-play disagreeing with CFBD's.

| Done | # | Task | Layer | Size | Depends on | Autonomy | Notes |
|------|---|------|-------|------|------------|----------|-------|
| | M18.1 | Extend the input registry and add the unit metric catalog to the feature tables | engine, etl | M | M2.4, M3.1 | attended | 04 § 10.2, § 10.6: every catalog metric registered (label, definition, unit, direction, source, garbage-time handling, first season, noisy flag). PBP-derived metrics use CFBD's garbage-time thresholds, with a test that our filtered EPA/play matches CFBD's on a fixture week. Explosive-play and scoring-opportunity thresholds set at the plan gate. The leakage test covers the new columns |
| | M18.2 | Compute opponent-removed stats, point-in-time | etl | M | M18.1 | attended | F-47, 04 § 10.3: per metric, offense and defense, entering each week: the team's average, its opponents' average without their games against the team, the difference (and ratio for count stats). Week 1 is NULL, never zero. Leakage test |
| | M18.3 | Rate every unit, including special teams | engine | M | M18.1 | attended | F-46, 04 § 10.2: ridge per catalog metric into `team_ratings.components` keyed by registry id, with percentiles; `st_rating` from the special-teams metrics; a test that offense + defense + special-teams contributions sum to the overall rating. Display only unless M19.1 promotes a unit |
| | M18.4 | Compute weekly SOR and remaining and full-season SOS | engine, data | M | M3.7, M4.8 | attended | Schema change: stop and ask (03 › Proposed additions for ratings depth). F-48, 04 § 10.5: Poisson binomial against the 25th-best rating; exact SOR matches a 100,000-run simulation within 0.5 (04 § 9.6); insert-only per model run; rank by SOR is a view. M12.6 reuses the code |
| | M18.5 | Publish team game stats to Postgres with season-to-date and opponent-removed views | data | M | M18.2 | attended | Schema change: stop and ask. `team_game_stats` upserted by source key (hard rule 3); views per 03 › Proposed additions for ratings depth; a test that the views equal the lake's feature table on the fixture; `EXPLAIN` check |
| | M18.6 | Extend `/rankings` and `/teams/{id}` with units, SOR and team stats | api | M | M18.3, M18.4, M18.5 | unattended | Still one API call per page (hard rule 5); labels come from the input registry, never hard-coded in `web/` |
| | M18.7 | Build Rankings › Units, the SOR column and the team page's Stats module | ui | M | M18.6 | unattended | S-04, S-06, F-46/F-47/F-48: "display only" markers, noisy and unfiltered stats labeled, schedule-strength card. Design: Prompt 13 frames (not drawn yet; 05 § 13). Adds the Units view's Lighthouse route and budget |

## M19: Model v1.1, confidence plays and inputs explainer (Phase 5, part 5) — Future

_Added 2026-10-20; numbered like M18._

**Goal:** find out which of the new numbers help predict, show how sure the model is about each play, and explain every input.
**Demo at exit:** a backtest report with a ship or don't-ship verdict for each new input and for game-specific σ; Picks › Confidence plays lists this week's strongest plays with levels, hit rates and reasons; Lab › Inputs shows a card for every input.
**Features:** F-49, F-50
**Depends on:** M18.1–M18.4; M9.6–M9.7 for M19.5; Prompt 13's frames for M19.4–M19.5
**Riskiest:** backtest overfitting from testing many inputs at once (04 § 6): every variant is counted and the holdout stays locked.

| Done | # | Task | Layer | Size | Depends on | Autonomy | Notes |
|------|---|------|-------|------|------------|----------|-------|
| | M19.1 | Test the new inputs in the model (v1.1) | engine | M | M18.1–M18.4 | attended | `model/` branch. 04 § 10, § 9.6: each candidate on its own (extra units, special teams, opponent-removed stats, SOS, SOR, `shrink_toward: conference`), kept only if MAE improves (§ 9.5) with ATS and calibration no worse; every variant counted (04 § 6). Expect little from SOS and SOR (04 § 10.5). *From TASK-037 (PR #102):* also test returning production as a modifier of how far last season's rating regresses (an RP × last-season interaction in the prior), not only the additive term D-138 fits. *From TASK-038 (PR #103):* the six v1 inputs overlap (overall, rushing and passing versions of two stats), so single per-input drivers can be large and offsetting while they sum exactly (D-139): test grouped units (one rushing, one passing) or a constrained margin fit |
| | M19.2 | Make σ game-specific from rating uncertainty | engine | M | M4.3 | attended | `model/` branch, 04 § 10.7: from rating uncertainty, games played and prior weight; kept only if the Brier score on cover probability improves with calibration no worse |
| | M19.3 | Add confidence levels with backtest hit rates and reasons | engine, api | M | M19.2 | attended | F-49, 04 § 10.7, D-118: levels are bins of the calibrated `model_prob`, with cutoffs in the spec, computed on read and never stored (hard rule 1); hit rate per level from pooled validation; each higher level must hit more often (04 § 9.6). Decide at the plan gate whether levels replace the A/B/C tiers |
| | M19.4 | Build Picks › Confidence plays | api, ui | M | M19.3, M7.2 | unattended | S-07, F-49: level, hit rate, reasons, UNCALIBRATED label. Design: Prompt 13 frames (05 § 13) |
| | M19.5 | Build Model Lab › Inputs, the inputs explainer | api, ui | M | M18.1, M9.7 | unattended | S-09, F-50, 04 § 10.6: registry text, `fitted_params` weights in plain English, share of the rating spread, league distribution with a team marked. The input card is a component M14.3 reuses. Design: Prompt 13 frames |

## M12: History data and hindsight ratings (Phase 6, part 1) — Future

**Goal:** the data and ratings behind season, program and coach rankings, with leakage proven impossible.
**Demo at exit:** for any season since the start year, a CLI report shows the best team (hindsight) and the best résumé side by side; the leakage test proves no prediction can read a hindsight rating.
**Features:** F-26, F-30, F-31
**Depends on:** M11 (Phase 5 done); the design track's History pass (Prompts 10a–10c) and roadmap open questions 3–4 decided

| Done | # | Task | Layer | Size | Depends on | Autonomy | Notes |
|------|---|------|-------|------|------------|----------|-------|
| | M12.1 | Find each CFBD endpoint's history depth and estimate the call budget | etl | S | — | attended | Roadmap Phase 6; the owner picks the start year (open question 3) |
| | M12.2 | Propose and add the rating kind, `coaches` and `coach_tenures` | data | M | M12.1 | attended | Schema change: stop and ask. Game-level attribution for mid-season and interim coaches (04 § 7) |
| | M12.3 | Backfill games, scores and coaches to the start year | etl | M | M12.1, M12.2 | attended | Season-level endpoints, ~1–2 calls per season; owner approves the budget |
| | M12.4 | Fit hindsight ratings and prove predictions refuse them | engine | M | M12.2 | attended | D-056: one full-season fit per season as its own kind; harness and production tests refuse it |
| | M12.5 | Add scores-only ratings for seasons before advanced stats | engine | M | M12.3 | attended | Labeled as such; reported beside efficiency hindsight ratings for 2014–2025 (04 § 9.6) |
| | M12.6 | Rank résumés by exact strength of record | engine | M | M12.4, M18.4 | attended | Reuses M18.4's weekly SOR code with hindsight ratings (04 § 10.5); must match a 100,000-run simulation within 0.5 (04 § 9.6) |
| | M12.7 | Add the cross-era scale | engine | S | M12.4 | unattended | Within-season z-score and percentile next to the raw rating (F-30) |

## M13: Programs, coaches and History screens (Phase 6, part 2) — Future

**Goal:** rank programs and coaches across history and browse it in the app.
**Demo at exit:** Rankings › History shows season finals, programs over any span and coaches; you can explain why each of the top 5 coaches is there; ⌘K finds coaches. (The roadmap's Phase 6 acceptance, with M12.)
**Features:** F-26, F-27, F-28, F-29
**Depends on:** M12; History screens handed off from Claude Design

| Done | # | Task | Layer | Size | Depends on | Autonomy | Notes |
|------|---|------|-------|------|------------|----------|-------|
| | M13.1 | Add program-ranking views over any span of seasons | data | M | M12.4 | attended | Average, peak, worst, top-10 finishes; views, never stored. Spans: all time (from the history start year), last N seasons, or a custom range (F-27, 05 § 11) |
| | M13.2 | Rank coaches by value over expectation | engine | M | M12.6 | attended | Shrunk for short tenures; with and without crediting recruiting (default per open question 4); ATS and close-game records |
| | M13.3 | Build the History endpoints | api | M | M13.1, M13.2 | unattended | Season final, programs, coaches, coach page |
| | M13.4 | Build Rankings › History | ui | M | M13.3 | unattended | Season final, Programs, Coaches tabs; era badge. Design from Prompt 10a–10b (not drawn yet) |
| | M13.5 | Build the coach page and add coaches to ⌘K | ui | M | M13.3 | unattended | Career by stop, value added by season, ATS and close-game records. Design from Prompts 10b–10c |

## M14: Model Lab builder (Phase 7, part 1) — Future

**Goal:** build, backtest and promote your own model versions from the UI.
**Demo at exit:** clone v1, fix home field at 2.0, run a backtest from the Lab, watch it queue and finish, compare it with production, and see the promote checklist and the variants-tried counter.
**Features:** F-38
**Depends on:** M9; S-10 hi-fi design (planned before Phase 7)

| Done | # | Task | Layer | Size | Depends on | Autonomy | Notes |
|------|---|------|-------|------|------------|----------|-------|
| | M14.1 | Add the `backtest` workflow for one model version | ops | M | — | attended | 02 › Jobs; writes results back to `model_runs`. *From TASK-034 (PR #96):* the test-DB fixture's `model_runs.metrics` (`validation`, `holdout` with seasons/picks/win_pct/roi, `accuracy` with mae/closing_mae, `pick_buckets`, `calibration`) is a placeholder shape; the real one comes from `engine.backtest.metrics.Metrics`, and M7.4 reads it, so match it or update `python/db/seeds/fixture/models.json` with it |
| | M14.2 | Queue backtests from the API through workflow dispatch | api | M | M14.1 | attended | 02 › Components 2: fine-grained token with only `actions:write`; `model_runs.status` queued → running → done. *From TASK-034 (PR #96):* nothing stops an UPDATE of a run's `season`, `week`, `as_of` or `fitted_params` after it has outputs (D-135 put no trigger on `model_runs`); the first code that updates runs in place should propose a column-scoped trigger allowing only `status`, `started_at`, `finished_at`, `error`, `metrics` and `github_run_id` (schema change: stop and ask) |
| | M14.3 | Generate the builder form from the `ModelSpec` JSON Schema | ui | M | M14.2, M19.5 | attended | D-011, S-10; clone, edit, run states; each input's toggle sits beside M19.5's input card (F-50), with options and labels from the input registry. Design: `Lab Wireframes.dc.html` (low fidelity until redrawn); shot `16-lab-builder-wireframe.png` |
| | M14.4 | Add promotion with the go/no-go checklist and variants-tried counter | api, ui | M | M14.3 | attended | 04 § 6, § 9.4: holdout use recorded; one production version per market. *From TASK-034 (PR #96):* `model_runs` has no holdout flag or reason yet (holdout openings are still in the lake's `backtests/holdout/`, D-131), and nothing defines a "variant" or records when a version was promoted, so 02 › Seed data's "7 variants since the last promotion" isn't in the fixture; this task adds both (schema change: stop and ask) and seeds them |

## M15: Totals, CFP odds and matchups (Phase 7, part 2) — Future

**Goal:** totals picks, playoff odds and the "who wins" tool.
**Demo at exit:** This Week's Spread / Total / Both control works with totals picks; the team page shows CFP %; the matchup tool answers "2026 Ohio State vs 2019 LSU at a neutral site".
**Features:** F-11, F-22, F-24
**Depends on:** M10 (weather snapshots), M12.6 (résumé ranking)

| Done | # | Task | Layer | Size | Depends on | Autonomy | Notes |
|------|---|------|-------|------|------------|----------|-------|
| | M15.1 | Build the totals model | engine | M | M10.5 | attended | Pace × efficiency plus weather snapshots; must pass the spread gates applied to totals (04 § 9.6) |
| | M15.2 | Pick totals and show them on This Week | engine, ui | M | M15.1 | attended | S-01 Spread / Total / Both (D-074). *From TASK-016 (PR #59):* the fixture's line snapshots carry no totals; this task adds sample-data §1's market totals (OSU/PUR 52.5, TEX/OU 61.5) |
| | M15.3 | Approximate committee selection and simulate the 12-team bracket | engine | M | M12.6, M9.2 | attended | Must beat "12 best by rating, 5 top conference champions in" on Brier (04 § 9.6) |
| | M15.4 | Show CFP % on the team page and Season Outlook | ui | S | M15.3 | unattended | S-06 CFP tile, S-05 (D-081) |
| | M15.5 | Build the hypothetical matchup endpoint | api | S | — | unattended | Light core, ≤ 2 s (D-092); cross-season ratings |
| | M15.6 | Design and build the matchup tool screen | ui | M | M15.5 | attended | F-24: not designed yet; Claude Design pass first |

## M16: Research and extras (Phase 7, part 3) — Future

**Goal:** try the riskier model ideas, ship only what wins, and add the nice-to-haves.
**Demo at exit:** a backtest report for each research branch with a ship or don't-ship verdict; Claude-written pick summaries on Game Detail.
**Features:** F-15, F-16, F-39, F-51
**Depends on:** M14 (Lab compare and promotion)

| Done | # | Task | Layer | Size | Depends on | Autonomy | Notes |
|------|---|------|-------|------|------------|----------|-------|
| | M16.1 | Research a drive-level game simulator | engine | M | — | attended | `model/` branch; ships only if it beats the empirical distribution near key numbers (04 § 9.6, D-053) |
| | M16.2 | Research the Rung 3 ML residual layer | engine | M | — | attended | `model/` branch; ships only if it beats production Rung 2 out of sample (D-049) |
| | M16.3 | Write plain-English pick summaries with Claude from `drivers` | api, ui | M | — | attended | F-39 |
| | M16.4 | Add multi-book lines from The Odds API (optional) | etl | M | — | attended | F-15: 500 free credits a month; lower value without a sportsbook |
| | M16.5 | Research position-group ratings | engine, etl | M | M18.3 | attended | F-51, 04 § 10.8: `model/` branch; estimate the CFBD player PPA and usage endpoints' call cost and get the owner's OK first; ships only if it beats production out of sample (04 § 9.6) |

## M17: Multi-sport, NFL first (Phase 8) — Future

**Goal:** an NFL model on the same engine, so NFL contest games stop being market-gap only.
**Demo at exit:** the sport switcher opens NFL rankings and slate; the contest ranks NFL games by the NFL model.
**Features:** F-40
**Depends on:** M13. Roadmap open question 2 may pull an NFL model forward to right after Phase 5; decide after M8.

| Done | # | Task | Layer | Size | Depends on | Autonomy | Notes |
|------|---|------|-------|------|------------|----------|-------|
| | M17.1 | Generalize the `Sport` plugin boundary | engine | M | — | attended | D-022: move anything CFB-specific that leaked into shared code |
| | M17.2 | Ingest full NFL data from nflverse | etl | M | M17.1 | attended | Beyond M6.3's schedule, scores and lines |
| | M17.3 | Rate and predict NFL games | engine | M | M17.2 | attended | Must pass the Phase 2 and Phase 3 bars against NFL closing lines (04 § 9.6) |
| | M17.4 | Rank NFL contest games by the model | api | S | M17.3 | unattended | Replaces the market-gap-only path once M17.3 passes |
| | M17.5 | Add the sport switcher | ui | M | M17.3 | unattended | S-16 sidebar and mobile More |
