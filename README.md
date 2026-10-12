# cfb-model

A college football prediction model and web app: game predictions, picks against the spread, power rankings and an honest track record. Other sports later.

## Docs
| Doc | What's in it |
|---|---|
| [01 — Product](docs/01-product.md) | Vision, features, priorities, what "good" means |
| [02 — Architecture](docs/02-architecture.md) | System design, hosting ($0–5/mo), repo layout |
| [03 — Data model](docs/03-data-model.md) | Sources, data lake, Postgres schema, conventions |
| [04 — Model](docs/04-model.md) | Modeling approach + primer, validation, pick logic |
| [05 — UI design brief](docs/05-ui-design-brief.md) | Brief for Claude Design |
| [06 — Roadmap](docs/06-roadmap.md) | Phases, acceptance criteria, open questions |
| [07 — Claude Design playbook](docs/07-claude-design-playbook.md) | Prompts, review checks and handoff for the UI design |
| [Decisions](docs/decisions.md) | Settled decisions, each with its source |

## Stack
Python (uv, DuckDB, scikit-learn, FastAPI) · Next.js + Tailwind + shadcn/ui · Postgres (Neon) · Parquet on Cloudflare R2 · GitHub Actions · Vercel

## Dev setup (Windows, PowerShell)

### Prerequisites
```powershell
scoop install nodejs uv pnpm git gh   # Node 24+, uv (installs Python 3.13 itself), pnpm 12
```
You also need a Neon project with `dev` and `test` branches, and a CFBD API key.

### Install
```powershell
pnpm install; pnpm bootstrap   # uv sync and Playwright's Chromium too
```

### Environment
```powershell
Copy-Item .env.example .env.local
```
Fill in `.env.local`: `CFBD_API_KEY`, the dev branch's `DATABASE_URL` (pooled) and
`DATABASE_URL_UNPOOLED` (direct), and the test branch's `TEST_DATABASE_URL` (direct).
It's gitignored; never commit it. Tests refuse to run if `TEST_DATABASE_URL` is unset or names
the dev database.

### Database
```powershell
pnpm db:migrate        # dev DB: Alembic to head, then re-apply python/db/views/*.sql
pnpm db:migrate:test   # the same for the test DB
pnpm db:check          # one migration head; models match the migrations (test DB)
pnpm db:seed           # load the fixture (python/db/seeds/fixture/) into the TEST DB only
```
Dev starts empty, so `/teams` shows "No teams yet". To pull real teams into dev, fetch one week of
CFBD games (one API call; a completed week is never fetched twice):
```powershell
pnpm ingest:games --season 2025 --week 1
```

### Run
```powershell
pnpm dev               # Next.js on :3000 and FastAPI on :8000 together
```
Open http://localhost:3000/teams. Health: http://localhost:3000/api/py/health.

### Test
```powershell
pnpm typecheck         # tsc + pyright
pnpm lint              # eslint + ruff
pnpm test              # vitest + pytest (DB tests use the test DB)
pnpm test:e2e          # Playwright: builds, starts next + uvicorn on the seeded test DB
pnpm build             # next build
```
Every script runs from the repo root under `cmd.exe /c` too.

## Releasing

Merging to `main` doesn't deploy. Vercel builds every `main` commit without promoting it, and the
**Release** workflow (`.github/workflows/release.yml`) is the only thing that changes production:

1. **plan**: picks the newest ready Vercel production build for a commit on `main` (or the
   `commit` you name), refuses unless CI's `verify` passed on that exact commit, and lists the
   migrations production still needs (a read-only connection).
2. **snapshot**: only when migrations are pending, creates the Neon branch
   `release/<YYYYMMDD-HHMM>-<sha7>` from production's branch, as a restore point.
3. **migrate**: runs the planned commit's `python -m db migrate --target live` on the unpooled URL,
   then re-applies `python/db/views/*.sql`.
4. **promote**: points production's domains at the planned build.
5. **smoke**: `/api/py/health` on `PRODUCTION_URL` must report the planned commit, a reachable
   database and the commit's migration head, and an unsigned `GET /api/py/teams` must answer 401.
   It retries for about five minutes while the promotion reaches the domain.

### Run a release
```powershell
gh workflow run release.yml                          # dry run: plan only, changes nothing
gh workflow run release.yml -f dry_run=false         # the real release
gh workflow run release.yml -f dry_run=false -f commit=<sha>   # a specific commit on main
gh run watch                                         # follow it
```
Read the dry run's summary first: it names the commit, the build, CI's result and the pending
migrations. Only one release runs at a time; a second one waits.

### Read a failed run
Open the run's **Summary**: a refused step writes **Refused:** and the reason there.

| Failed job | What it means | What to do |
|---|---|---|
| plan | No ready build on `main`, CI didn't pass (or is still running) on that commit, or production is at a migration this commit doesn't know | Wait for CI or the Vercel build, or fix `main`; nothing changed |
| snapshot | Neon refused the branch (often the branch limit) | Delete old `release/*` branches in Neon and re-run; nothing changed |
| migrate | A migration failed partway | Production may be partly migrated; the summary names the snapshot branch to restore from. Old code is still live |
| promote | Vercel refused the promotion | Schema is migrated, old code still serves; re-run once fixed (migrations are then already applied) |
| smoke | The live site isn't the planned commit, can't reach the DB, is on another migration head, or serves data without a token | Check `API_JWT_SECRET` and `LIVE=true` in Vercel Production; roll back in Vercel (Instant Rollback) if needed |

### What it needs
Repository **secrets**: `VERCEL_TOKEN`, `NEON_API_KEY`, `PRODUCTION_DATABASE_URL_UNPOOLED`
(production's direct, non-pooler URL). Repository **variables**: `VERCEL_ORG_ID`,
`VERCEL_PROJECT_ID`, `NEON_PROJECT_ID`, `PRODUCTION_URL`. In Vercel: `main` builds aren't
auto-promoted, and Production has `LIVE=true` and `API_JWT_SECRET`.

To migrate production by hand (rare), put `PRODUCTION_DATABASE_URL_UNPOOLED=…` in the gitignored
`.env.live` and name it explicitly; nothing reads that file otherwise:
```powershell
uv --directory python run python -m db migrate --target live --env-file ..\.env.live
```

### Layout
`web/` Next.js app · `python/` uv workspace: `db` (models, migrations, views, fixture),
`engine` (CLI: ingest, seed), `api` (FastAPI) · `vercel.json` deploys `web` and `api` as one
Vercel project (Services).
