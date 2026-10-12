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
| [Restore runbook](docs/runbooks/restore.md) | Getting production's database back from a nightly backup |

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
migrations. Only one release runs at a time; a second one waits. A real release runs only from
`main`; another ref (`--ref <branch>`) may only dry-run, for testing a change to the workflow.

### Read a failed run
Open the run's **Summary**: a refused step writes **Refused:** and the reason there.

| Failed job | What it means | What to do |
|---|---|---|
| plan | A real release started from a ref other than `main`, no ready build on `main`, CI didn't pass (or is still running) on that commit, or production is at a migration this commit doesn't know | Wait for CI or the Vercel build, or fix `main`; nothing changed |
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

## Backups

The **Backup** workflow (`.github/workflows/backup.yml`) runs nightly at 07:30 UTC and stores a
dump only after proving it restores:

1. **dump**: `pg_dump` of production through `BACKUP_DATABASE_URL` (a read-only role), and an exact
   row count of every table taken in the same snapshot as the dump.
2. **restore**: `pg_restore` into a `postgres:PG_MAJOR` container on the runner.
3. **verify**: re-applies the views of the commit production serves (from `/api/py/health`),
   queries each view, and compares row counts with production's.
4. **upload**: to R2 as `backups/<UTC date>.dump`. A re-run the same day replaces that day's dump.

`PG_MAJOR` is set in one place, `.github/actions/start-postgres/action.yml`, which CI uses too.
To restore a dump, follow [docs/runbooks/restore.md](docs/runbooks/restore.md).

### Run one by hand
```powershell
gh workflow run backup.yml
gh run watch
```
The run's **Summary** lists each table's row count in production and in the restore, the views
queried, the dump size and the object it uploaded.

### Read a failed run
A failed step writes **Backup failed:** and the reason in the Summary. Nothing was uploaded, and
the previous nights' dumps are untouched.

| Failed step | What it means | What to do |
|---|---|---|
| Dump production | `BACKUP_DATABASE_URL` is unset, pooled, or can't read a table; or `pg_dump` failed | Check the secret is `backup_reader`'s direct URL, and that the role can read every table |
| Find the commit production serves | `/api/py/health` on `PRODUCTION_URL` didn't answer, answered with Vercel's login page (a wrong `VERCEL_AUTOMATION_BYPASS_SECRET`), or named no commit | Check the site is up and the bypass secret matches Vercel › Settings › Deployment Protection; re-run |
| Restore the dump | The dump has something a plain Postgres can't restore | Read the `pg_restore` error; production is unaffected |
| Re-apply views… | A view fails on production's data, or a table's counts differ | The summary names the view or table; a mismatch means the dump isn't trustworthy |
| Upload to R2 | The R2 token, bucket or account is wrong | Check `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_ACCOUNT_ID`, `R2_BUCKET` |

### What it needs
Repository **secrets**: `BACKUP_DATABASE_URL` (the read-only `backup_reader` role's direct URL on
production), `R2_ACCESS_KEY_ID` and `R2_SECRET_ACCESS_KEY` (an R2 token with Object Read & Write on
the backup bucket only). Repository **variables**: `R2_ACCOUNT_ID`, `R2_BUCKET` (`cfb-backups`, a
bucket of its own, never the lake's), and `PRODUCTION_URL` (shared with the release workflow).
Production is behind Vercel Authentication, so the health call also sends the
`x-vercel-protection-bypass` header from the `VERCEL_AUTOMATION_BYPASS_SECRET` secret (shared with
the Lighthouse job).

## Layout
`web/` Next.js app · `python/` uv workspace: `db` (models, migrations, views, fixture),
`engine` (CLI: ingest, seed), `api` (FastAPI) · `vercel.json` deploys `web` and `api` as one
Vercel project (Services).
