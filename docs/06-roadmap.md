# 06 — Roadmap

Each phase ends with a **review gate**: we demo what was built, check it against the acceptance criteria, and decide whether to adjust the plan before starting the next phase. Phases are sized for a few focused Claude Code sessions each. **This file's checklists are the source of truth for project status.**

**Timing context:** it's early October 2026, mid-season. Getting through Phase 3 quickly means the model can paper-trade the back half of 2026 plus bowls/CFP, which is a free out-of-sample test. The real target is being fully live and battle-tested for the **2027 season**.

```
Phase 0  Foundations + guardrails ─┐
Phase 1  Data pipeline             │  ← Claude Design work runs in parallel with 1–3
Phase 2  Baselines + backtest      │
Phase 3  Core model v1 + picks    ─┘
Phase 4  Web app MVP (incl. contest mode)
Phase 5  Season outlook, model weights, tracking
Phase 6  Rankings & history (seasons, programs, coaches)
Phase 7  Model builder + extensions
Phase 8  Multi-sport (NFL)
```

---

## Phase 0 — Foundations + guardrails
**Goal:** a skeleton that deploys end to end, with the safety rails in place *before* the first feature. (Each rail was retrofitted on a previous project, and retrofitting cost more.)

**Repo bootstrap**
- [x] Create the private GitHub repo (Claude asks first) and push the bootstrap commit (planning docs, `.claude/rules`, `.gitignore`) as the initial `main`. This is the only direct commit to `main`; everything after goes through PRs.

**Accounts & scaffolding**
- [x] Accounts: CFBD key (Patreon tier 1, already active), Neon, Cloudflare R2, Vercel _(R2 holds the backup bucket `cfb-backups` (TASK-006) and the lake bucket for the Phase 1 raw writer (TASK-015))_
- [x] Install `uv` and `pnpm`; uv workspace (`python/engine`, `python/api`, `python/db`), Python 3.13
- [x] Next.js 16 app in `web/` (TS strict, Tailwind, shadcn/ui, `agentRules: false`) _(shadcn/ui moved to M5.2, the first task that uses it; [08-tasklist](08-tasklist.md))_
- [x] One Vercel project serving Next.js + the FastAPI function, or two projects if that doesn't work (decide and record)

**Databases & environments**
- [x] Four Neon branches: `main` (prod), `dev`, `test`, and per-PR `preview/*` via the Vercel integration
- [x] `.env` → dev; prod URL only in gitignored `.env.live`, used only with an explicit flag _(`db migrate --target live` reads it only through `--env-file`, or the release workflow's environment; TASK-005)_
- [x] Test DB guard: tests require `TEST_DATABASE_URL`, distinct from `DATABASE_URL`, with no fallback
- [x] `LIVE=true` guard on every destructive command
- [x] Pooled URL for the app (`prepare_threshold=None`, `NullPool`), unpooled for migrations/jobs
- [x] `PG_MAJOR` set once and used by CI's service container and backup tooling _(TASK-006: set in the `start-postgres` action that CI and the backup share, D-109)_

**Schema & migrations**
- [x] SQLAlchemy models + Alembic; first migration: `sports`, `teams`, `team_seasons`, `venues`, `games`
- [x] `python/db/views/` applied after every migration (rebuild, preview build, release) _(every `db migrate`, the preview build and the release apply them. `transform --rebuild` (M2.3) is lake-only, so the database rebuild and its view re-apply land with a dev-DB rebuild command when one is first needed; TASK-017 › Context)_
- [x] CI migration checks: single head, `alembic check`, no edits to merged migrations, downgrade test for destructive changes _(single head, `alembic check` and the merged-migration check run in CI (TASK-009, D-110). The up → down → up test is written with the first migration that drops or retypes a column (D-020, `.claude/rules/database.md`); none exists yet)_

**Deploy & ops**
- [x] FastAPI `/api/py/health` (outside auth, no data) + `/teams`; Next.js page renders teams from the API
- [x] Auth.js with GitHub login + allowlist; bad session → redirect to `/login`; API JWT check _(TASK-001–TASK-004)_
- [x] CI on PR: ruff, pyright, pytest, eslint, tsc, vitest, migration checks
- [x] `release` workflow: plan → snapshot → migrate → views → promote → smoke test (with dry run) _(TASK-005; README › Releasing)_
- [x] Nightly `backup` workflow with restore verification → R2 _(TASK-006; README › Backups, docs/runbooks/restore.md)_
- [x] Dependabot with documented ignores (Next majors, TypeScript ≥ 7) _(TASK-009, D-110)_
- [x] `lighthouse` workflow on every PR preview, after Auth.js (D-101, [02 › Performance checks](02-architecture.md#performance-checks-lighthouse)): gates bytes, requests, CLS, accessibility and forbidden requests; reports timings in one PR comment; signs in by minting a session with the preview `AUTH_SECRET`; reports scrubbed and kept private. Routes `/login` and `/teams` to start, budgets set from the first preview run. Repo secrets documented in the setup docs _(TASK-007, TASK-008; README › Performance checks)_

**Claude Code setup**
- [x] `.claude/rules/` in place (git, database, web): **done in planning**
- [x] `PreToolUse` hook blocking whole-file reads of `data/**`, `*.parquet`, `*.duckdb`, large fixtures/mockups _(the kit 2.4 `guard-large-reads.ps1`, configured by `largeFiles` in `.claude/kit.json`; add a fixture there once one grows past ~100 KB)_
- [x] A schema-reviewer subagent for schema/view/query PRs
- [x] CLAUDE.md "Commands" section filled in

**Acceptance:** log in on the deployed production URL from your phone and see a team list read from Neon through the API. It was deployed through the release workflow, and last night's backup restored cleanly.

## Phase 1 — Data pipeline
**Goal:** all the history we need, clean and reproducible, plus weekly refresh.

- [x] CFBD ingest client with call budget tracking + raw Parquet writer (local + R2)
- [x] Backfill 2014–2025 + 2026 to date: games, team box scores, advanced stats, lines, talent, returning production, recruiting, SP+/FPI/Elo, venues, conferences, PBP + drives
- [x] DuckDB staging models + `team_week_features` (point-in-time safe)
- [x] Publish reference + games + line snapshots to Postgres (upsert by source key, never truncate)
- [x] Data quality checks (see [03-data-model.md](03-data-model.md))
- [x] Scheduled `results` and `lines` jobs
- [x] Notebook #1: explore the data (HFA over time, margin distribution, closing-line MAE)

**Acceptance:** `engine transform --rebuild` recreates every staged table from raw with zero API calls; data quality checks pass; the scheduled job picks up this Saturday's results on its own.

## Phase 2 — Baselines & backtest harness
**Goal:** the measuring stick, which comes before any serious model.

- [x] `ModelSpec` (v1 schema) + `RatingModel` / `GamePredictor` interfaces in `engine.core`
- [x] Walk-forward backtest harness by (season, week), with leakage assertions
- [x] Metrics + markdown/HTML backtest report (MAE, ATS by edge bucket, calibration, ROI)
- [ ] Baselines: HFA-only, closing line, SP+/FPI comparison
- [ ] Rung 1: least-squares power ratings with margin cap, recency weighting, priors from last season
- [ ] Notebooks #2–3: build ratings by hand; ratings → probabilities
- [ ] `model_versions` / `model_runs` (with `fitted_params`) / `team_ratings` / `predictions` + publish

**Acceptance:** one command runs a 2014–2023 backtest and produces a report comparing Rung 1 to the baselines. You can explain every number in it.

## Phase 3 — Core model v1 + picks
**Goal:** a model good enough to paper-trade.

- [ ] Rung 2: ridge opponent-adjusted efficiency ratings (off/def, rush/pass splits); overall rating = sum of unit contributions in points; shrinking toward the conference tier (Power 4 / G5 / FCS) tested against shrinking toward zero ([04 § 10.4](04-model.md))
- [ ] Preseason priors (returning production, talent, recruiting) + fitted decay blending
- [ ] Margin model mapping efficiency to points; σ and empirical margin distribution
- [ ] `drivers` output for explainability
- [ ] Pick logic: thresholds, tiers, optional market shrinkage, tuned on validation seasons
- [ ] `picks` table + views: `game_market`, `current_picks`, `pick_outcomes`, `model_record`, `team_rankings`, `team_schedule_strength` (SOS, [04 § 10.5](04-model.md))
- [ ] Holdout evaluation on 2024–2025, then go/no-go per [04-model.md §5](04-model.md)
- [ ] Production weekly cycle live: rate → predict → pick (paper trading 2026)

**Acceptance:** model v1 passes the go/no-go gates on validation seasons (or we understand why not and adjust); weekly picks are generated automatically and graded by the views.

## Phase 4 — Web app MVP
**Goal:** the app you open every Thursday, Friday and Saturday. Built from the Claude Design output.

- [ ] Design system tokens + core components implemented
- [ ] Generated TypeScript API client from OpenAPI
- [ ] Screens: This Week, Game Detail, Picks, Rankings, Team, Performance
- [ ] **Contest mode (generic, Splash preset):** `ContestRules`, `contests`, `contest_lines` (snapshots), `contest_entries` with kickoff-lock enforcement; Splash paste parser + alias matching; top-N ranking against contest lines; you-vs-model results (`contest_results` view)
- [ ] NFL schedule/scores/closing lines from nflverse (no NFL model yet) so mixed CFB + NFL slates can be shown and graded
- [ ] `loading.tsx` skeleton on every data route; one API call per page
- [x] Lighthouse gates measure a build served inside the job on the seeded fixture DB; PR previews are measured and reported, never gated (D-125, open question 5)
- [ ] Each screen's PR adds its Lighthouse route(s) and budget (a small and a large instance for Game Detail and Team), measured on the fixture build; the large instance is fixture data (D-125)
- [ ] Mobile layouts for This Week, Contest, Game Detail and Picks
- [ ] Line movement: opening → current + sparkline in the slate's Market cell, full history on Game Detail
- [ ] Best lines board (in Picks): upcoming games ranked by cover % against the better of market/contest line, with an *uncalibrated* label until calibration passes
- [ ] This week's record strip (This Week, Picks, Contest) + a `scores` job refreshing this week's scores during game windows

**Acceptance:** on a Thursday you paste the Splash page and see the whole CFB + NFL slate ranked against the contest's lines, with the top 4 marked. You record your picks, and on Saturday you follow results from your phone.

## Phase 5 — Season outlook, model weights, tracking
- [ ] Season simulations: projected records, win distributions, conference title game/title odds
- [ ] Season Outlook screen + team-page module
- [ ] **Model Lab, part 1:** weights view (spec + fitted params), versions list, compare two versions
- [ ] Manual adjustments UI + audit trail
- [ ] CLV on picks and contest picks
- [ ] SP+/FPI comparison view
- [ ] Watchlist & alerts: star games; email/web-push alert when a starred game's edge crosses the pick threshold or its line moves (schema proposal reviewed before migration)
- [ ] Weather flags: Open-Meteo forecast snapshots for outdoor venues; flag icon on slate rows and weather panel on Game Detail

**Ratings depth** (added 2026-10-20; [04 § 10](04-model.md), D-117; M18–M19 in [08-tasklist](08-tasklist.md))
- [ ] Design first: the ratings-depth pass (Prompt 13) is done
- [ ] Input registry + the unit metric catalog in the feature tables, with our own garbage-time filter for PBP-derived metrics
- [ ] Opponent-removed stats (each opponent's numbers with games against the team taken out), point-in-time
- [ ] Every unit rated (offense, defense, special teams and sub-units), adding up to the overall rating
- [ ] Weekly SOR and remaining/full-season SOS (schema proposal reviewed before migration)
- [ ] Team stats in Postgres with views for season-to-date and opponent-removed stats (schema proposal reviewed before migration)
- [ ] Rankings › Units, the SOR column, and the team page's Stats module
- [ ] Model v1.1: the new units, special teams, opponent-removed stats, SOS/SOR and conference shrinkage tested as inputs, each kept only if it wins; game-specific σ kept only if calibration improves
- [ ] Confidence plays: levels from the calibrated cover %, each with its backtest hit rate and reasons
- [ ] Model Lab › Inputs: the inputs explainer

## Phase 6 — Rankings & history
**Goal:** rank seasons, programs and coaches across history, not just this week's teams. Design: [04-model.md §7](04-model.md).

- [ ] Design first: History pass of the design track (Prompts 10a–10c) is done, with the two open questions below decided
- [ ] Find how far back each CFBD endpoint goes (games, advanced stats, coaches); pick the history start year and estimate the call budget before backfilling
- [ ] Backfill games/scores and coaches to the start year (season-level endpoints, ~1–2 calls per season)
- [ ] Schema proposal, reviewed before any migration: a rating kind (predictive vs hindsight), `coaches`, `coach_tenures` (game-level attribution for mid-season changes)
- [ ] Hindsight ratings: one full-season fit per season, stored as their own kind. A test proves the backtest harness and production predictions refuse to read them
- [ ] Scores-only ratings for seasons before advanced stats exist, labeled as such
- [ ] Résumé ranking: strength of record (exact, no simulation needed), reusing Phase 5's weekly SOR code with hindsight ratings
- [ ] Cross-era scale: within-season z-score/percentile next to the raw rating
- [ ] Program rankings over any span of seasons: all time, last N seasons, or a custom range (views)
- [ ] Coach rankings: value over expectation, shrunk for short tenures, with and without crediting recruiting; ATS and close-game records
- [ ] Screens: Rankings → History tab (Season final, Programs, Coaches) and a coach page; ⌘K finds coaches

**Acceptance:** for any season since the start year you can see the best team and the best résumé side by side; you can rank programs over any span; you can explain why each of the top 5 coaches is there; the leakage test proves no prediction can read a hindsight rating.

## Phase 7 — Model builder + extensions
- [ ] **Model Lab, part 2:** builder form generated from the `ModelSpec` JSON Schema, with the inputs explainer's card beside each input; run backtests from the UI (GitHub Actions dispatch); promote with the go/no-go checklist; variants-tried counter
- [ ] Totals model + picks (uses the Phase 5 weather snapshots)
- [ ] CFP odds: committee-selection approximation (uses Phase 6's résumé ranking), 12-team bracket simulation
- [ ] Hypothetical matchup tool (cross-season)
- [ ] Research: drive-level game simulator (ships only if it improves calibration/totals)
- [ ] Research: Rung 3 ML residual layer (ships only if it wins)
- [ ] Research: position-group ratings from player-level data (estimate the player endpoints' call cost first; ships only if it wins)
- [ ] Claude-generated pick write-ups from `drivers`
- [ ] Optional: The Odds API multi-book lines

## Phase 8 — Multi-sport
- [ ] Generalize `Sport` plugin boundaries (refactor anything CFB-specific that leaked)
- [ ] NFL via nflverse: ingest, ratings, predictions
- [ ] Sport switcher in UI

---

## Design track (Claude Design; parallel to the phases)
Playbook: [07-claude-design-playbook.md](07-claude-design-playbook.md). Design work is free of the API and database, so it runs alongside Phases 1–3 and doesn't block them.

**First pass (during Phases 1–3)**
- [x] Prompt 1: design system
- [x] Prompts 2–7: This Week, Contest, Game Detail, Rankings + Outlook + Team, Picks + Performance, Model Lab
- [x] **Prompt 11: market extras** (line movement, best lines, record strip, watchlist & alerts, weather), after 2, 3, 4 and 6
- [x] Prompt 8: states and leftovers (after 11)
- [x] Prompt 9: consistency audit. Complete for every frame drawn through Prompt 12 (the Prompt 12 frames were audited on `Pass Audit.dc.html`); it runs again after Prompt 10, in the History pass below
- [x] Handoff bundle in `design/handoff/` (replaced the PDF + HTML export), share links, "Design decisions" section in the brief, docs synced to the design
- [ ] Design-system handoff, then implement it as its own PR (needs the Phase 0 `web/` scaffold). **Review gate**

**Gap-fill pass (2026-10-07, before Phase 4 handoffs)**
- [x] Prompt 12: decisions applied to existing frames, Teams index, More menu, mobile Performance sections, missing states, light mode ([07 § Prompt 12](07-claude-design-playbook.md#prompt-12-gap-fill-after-the-starter-kit-review-2026-10-07))
- [x] Re-export the handoff; update the states columns in [05 › Screen inventory](05-ui-design-brief.md#screen-inventory-from-handoff)

**Per-screen handoff:** each Phase 4 screen is handed off and implemented one at a time (see the Phase 4 checklist).

**Ratings-depth pass (after Phase 4, before Phase 5's ratings-depth screens)**
- [ ] Add the sample rows to `design/sample-data.md` (owner approves; protected path), then run **Prompt 13** ([07 § Prompt 13](07-claude-design-playbook.md)): Rankings › Units and SOR, team page Stats, Confidence plays, Lab › Inputs
- [ ] Re-run Prompt 9's audit on the new frames; re-export; update "Design decisions"

**History pass (after Phase 5, before Phase 6)**
- [ ] Decide the Phase 6 open questions (history start year, default coach measure) and swap real rows into `design/sample-data.md` §9
- [ ] **Prompt 10a** (season final + programs + era badge), **10b** (coaches + coach page), **10c** (team page module, ⌘K coaches)
- [ ] Re-run Prompt 9's audit on the new frames; re-export; update "Design decisions"
- [ ] Hand off the History screens when Phase 6 reaches its screens task

## Decisions made (from planning review, 2026-10-03)
| Question | Decision |
|---|---|
| Repo visibility | **Private** for now; can change later |
| CFBD tier | **Tier 1 ($1/mo, 5,000 calls)** already active; upgrade only if the budget runs short |
| Sportsbook | None today. You play a **Splash Sports pick'em in a work league**, so contest mode is MVP. Sportsbook-style features stay in the plan at lower priority |
| Bet timing | **End of week**, so closing/contest lines are the primary evaluation lines |
| FCS games | Rate FCS teams, but **don't make picks** on FBS-vs-FCS games |
| Splash format | 4 picks/week from **CFB + NFL** games; each line locks at its game's kickoff; 1 point per correct pick, no confidence points; the slate is a webpage, so we import by paste |
| Generality | Build general and default to the current use: contests are generic `ContestRules` with Splash as a preset; nothing in the data model assumes Splash or no-sportsbook |
| Claude Design extras (2026-10-04) | **Added:** line movement, best lines board, this week's record (Phase 4); watchlist & alerts, weather flags (Phase 5). **Dropped:** injury flags (no free data feed; you track injuries yourself, via manual adjustments once they exist), multi-book "best available line" (stays Later). Lock countdown was already in contest mode |

## Open questions
1. **Pushes in your league:** does a push score 0, half a point, or void the pick? (Splash slates often use half-point lines, so it may rarely come up.) The default is 0 until you know.
2. **NFL timing:** your slate includes NFL games, but the NFL model is Phase 8. Until then, NFL picks get only the contest-vs-market comparison. If you find yourself picking NFL games often, we could pull a basic NFL rating model forward to right after Phase 5. It reuses the same engine, so it's much cheaper than a from-scratch build. Decide after Phase 4.
3. **How far back should history go?** Scores exist back to the 1800s, but efficiency stats only from about the mid-2000s. The 1970s (~50–100 extra calls) covers every modern coach's career. Decide at the start of Phase 6.
4. **Default coach measure:** value over expectation *controlling for* recruiting (credits coaching only) or *crediting* recruiting (credits roster-building too)? Both will be shown; this only picks the default sort. Decide at the start of Phase 6.
5. **Where Lighthouse byte gates measure data pages (decided 2026-10-23, D-125):** gates run on a build served inside the job on the seeded fixture DB, as e2e does; each PR preview is still measured on real data but only reported. Previews had started carrying real data, and `/teams` grew from 5,861 to 12,444 bytes with no code change (PR #74). Built by TASK-027, before the first data-heavy budget (This Week).
