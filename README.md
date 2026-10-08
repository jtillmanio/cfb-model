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

### Layout
`web/` Next.js app · `python/` uv workspace: `db` (models, migrations, views, fixture),
`engine` (CLI: ingest, seed), `api` (FastAPI) · `vercel.json` deploys `web` and `api` as one
Vercel project (Services).
