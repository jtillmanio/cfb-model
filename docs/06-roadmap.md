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
- [ ] Create the private GitHub repo (Claude asks first) and push the bootstrap commit (planning docs, `.claude/rules`, `.gitignore`) as the initial `main`. This is the only direct commit to `main`; everything after goes through PRs.

**Accounts & scaffolding**
- [ ] Accounts: CFBD key (Patreon tier 1, already active), Neon, Cloudflare R2, Vercel
- [ ] Install `uv` and `pnpm`; uv workspace (`python/engine`, `python/api`, `python/db`), Python 3.13
- [ ] Next.js 16 app in `web/` (TS strict, Tailwind, shadcn/ui, `agentRules: false`)
- [ ] One Vercel project serving Next.js + the FastAPI function, or two projects if that doesn't work (decide and record)

**Databases & environments**
- [ ] Four Neon branches: `main` (prod), `dev`, `test`, and per-PR `preview/*` via the Vercel integration
- [ ] `.env` → dev; prod URL only in gitignored `.env.live`, used only with an explicit flag
- [ ] Test DB guard: tests require `TEST_DATABASE_URL`, distinct from `DATABASE_URL`, with no fallback
- [ ] `LIVE=true` guard on every destructive command
- [ ] Pooled URL for the app (`prepare_threshold=None`, `NullPool`), unpooled for migrations/jobs
- [ ] `PG_MAJOR` set once and used by CI's service container and backup tooling

**Schema & migrations**
- [ ] SQLAlchemy models + Alembic; first migration: `sports`, `teams`, `team_seasons`, `venues`, `games`
- [ ] `python/db/views/` applied after every migration (rebuild, preview build, release)
- [ ] CI migration checks: single head, `alembic check`, no edits to merged migrations, downgrade test for destructive changes

**Deploy & ops**
- [ ] FastAPI `/api/health` (outside auth, no data) + `/teams`; Next.js page renders teams from the API
- [ ] Auth.js with GitHub login + allowlist; bad session → redirect to `/login`; API JWT check
- [ ] CI on PR: ruff, pyright, pytest, eslint, tsc, vitest, migration checks
- [ ] `release` workflow: plan → snapshot → migrate → views → promote → smoke test (with dry run)
- [ ] Nightly `backup` workflow with restore verification → R2
- [ ] Dependabot with documented ignores (Next majors, TypeScript ≥ 7)

**Claude Code setup**
- [ ] `.claude/rules/` in place (git, database, web): **done in planning**
- [ ] `PreToolUse` hook blocking whole-file reads of `data/**`, `*.parquet`, `*.duckdb`, large fixtures/mockups
- [ ] A schema-reviewer subagent for schema/view/query PRs
- [ ] CLAUDE.md "Commands" section filled in

**Acceptance:** log in on the deployed production URL from your phone and see a team list read from Neon through the API. It was deployed through the release workflow, and last night's backup restored cleanly.

## Phase 1 — Data pipeline
**Goal:** all the history we need, clean and reproducible, plus weekly refresh.

- [ ] CFBD ingest client with call budget tracking + raw Parquet writer (local + R2)
- [ ] Backfill 2014–2025 + 2026 to date: games, team box scores, advanced stats, lines, talent, returning production, recruiting, SP+/FPI/Elo, venues, conferences, PBP + drives
- [ ] DuckDB staging models + `team_week_features` (point-in-time safe)
- [ ] Publish reference + games + line snapshots to Postgres (upsert by source key, never truncate)
- [ ] Data quality checks (see [03-data-model.md](03-data-model.md))
- [ ] Scheduled `results` and `lines` jobs
- [ ] Notebook #1: explore the data (HFA over time, margin distribution, closing-line MAE)

**Acceptance:** `engine transform --rebuild` recreates every staged table from raw with zero API calls; data quality checks pass; the scheduled job picks up this Saturday's results on its own.

## Phase 2 — Baselines & backtest harness
**Goal:** the measuring stick, which comes before any serious model.

- [ ] `ModelSpec` (v1 schema) + `RatingModel` / `GamePredictor` interfaces in `engine.core`
- [ ] Walk-forward backtest harness by (season, week), with leakage assertions
- [ ] Metrics + markdown/HTML backtest report (MAE, ATS by edge bucket, calibration, ROI)
- [ ] Baselines: HFA-only, closing line, SP+/FPI comparison
- [ ] Rung 1: least-squares power ratings with margin cap, recency weighting, priors from last season
- [ ] Notebooks #2–3: build ratings by hand; ratings → probabilities
- [ ] `model_versions` / `model_runs` (with `fitted_params`) / `team_ratings` / `predictions` + publish

**Acceptance:** one command runs a 2014–2023 backtest and produces a report comparing Rung 1 to the baselines. You can explain every number in it.

## Phase 3 — Core model v1 + picks
**Goal:** a model good enough to paper-trade.

- [ ] Rung 2: ridge opponent-adjusted efficiency ratings (off/def, rush/pass splits)
- [ ] Preseason priors (returning production, talent, recruiting) + fitted decay blending
- [ ] Margin model mapping efficiency to points; σ and empirical margin distribution
- [ ] `drivers` output for explainability
- [ ] Pick logic: thresholds, tiers, optional market shrinkage, tuned on validation seasons
- [ ] `picks` table + views: `game_market`, `current_picks`, `pick_outcomes`, `model_record`, `team_rankings`
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

## Phase 6 — Rankings & history
**Goal:** rank seasons, programs and coaches across history, not just this week's teams. Design: [04-model.md §7](04-model.md).

- [ ] Design first: History pass of the design track (Prompts 10a–10c) is done, with the two open questions below decided
- [ ] Find how far back each CFBD endpoint goes (games, advanced stats, coaches); pick the history start year and estimate the call budget before backfilling
- [ ] Backfill games/scores and coaches to the start year (season-level endpoints, ~1–2 calls per season)
- [ ] Schema proposal, reviewed before any migration: a rating kind (predictive vs hindsight), `coaches`, `coach_tenures` (game-level attribution for mid-season changes)
- [ ] Hindsight ratings: one full-season fit per season, stored as their own kind. A test proves the backtest harness and production predictions refuse to read them
- [ ] Scores-only ratings for seasons before advanced stats exist, labeled as such
- [ ] Résumé ranking: strength of record (exact, no simulation needed)
- [ ] Cross-era scale: within-season z-score/percentile next to the raw rating
- [ ] Program rankings over any span of seasons (views)
- [ ] Coach rankings: value over expectation, shrunk for short tenures, with and without crediting recruiting; ATS and close-game records
- [ ] Screens: Rankings → History tab (Season final, Programs, Coaches) and a coach page; ⌘K finds coaches

**Acceptance:** for any season since the start year you can see the best team and the best résumé side by side; you can rank programs over any span; you can explain why each of the top 5 coaches is there; the leakage test proves no prediction can read a hindsight rating.

## Phase 7 — Model builder + extensions
- [ ] **Model Lab, part 2:** builder form generated from the `ModelSpec` JSON Schema; run backtests from the UI (GitHub Actions dispatch); promote with the go/no-go checklist; variants-tried counter
- [ ] Totals model + picks (uses the Phase 5 weather snapshots)
- [ ] CFP odds: committee-selection approximation (uses Phase 6's résumé ranking), 12-team bracket simulation
- [ ] Hypothetical matchup tool (cross-season)
- [ ] Research: drive-level game simulator (ships only if it improves calibration/totals)
- [ ] Research: Rung 3 ML residual layer (ships only if it wins)
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
- [ ] Prompt 1: design system
- [ ] Prompts 2–7: This Week, Contest, Game Detail, Rankings + Outlook + Team, Picks + Performance, Model Lab
- [ ] **Prompt 11: market extras** (line movement, best lines, record strip, watchlist & alerts, weather), after 2, 3, 4 and 6
- [ ] Prompt 8: states and leftovers (after 11)
- [ ] Prompt 9: consistency audit
- [ ] Handoff bundle in `design/handoff/` (replaced the PDF + HTML export), share links, "Design decisions" section in the brief, docs synced to the design
- [ ] Design-system handoff, then implement it as its own PR (needs the Phase 0 `web/` scaffold). **Review gate**

**Gap-fill pass (2026-10-07, before Phase 4 handoffs)**
- [x] Prompt 12: decisions applied to existing frames, Teams index, More menu, mobile Performance sections, missing states, light mode ([07 § Prompt 12](07-claude-design-playbook.md#prompt-12-gap-fill-after-the-starter-kit-review-2026-10-07))
- [x] Re-export the handoff; update the states columns in [05 › Screen inventory](05-ui-design-brief.md#screen-inventory-from-handoff)

**Per-screen handoff:** each Phase 4 screen is handed off and implemented one at a time (see the Phase 4 checklist).

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
