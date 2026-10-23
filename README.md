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

## Dispatcher

The **dispatcher** is a small Cloudflare Worker (`infra/dispatcher/`, D-122) that starts this
repo's scheduled GitHub Actions workflows on time. It is an alarm clock, not a job runner: it does
none of the work itself. At each job's time it asks GitHub to start that workflow, exactly as if
you had pressed **Run workflow** in the Actions tab, and the workflow then runs in Actions as usual.

### Why it exists
- **GitHub's own schedule runs late.** A workflow's `on: schedule` cron is best effort. GitHub
  queues scheduled runs behind everyone else's and may delay or drop them under load. The backup's
  cron said 07:30 UTC, but its runs started at 15:13, 13:00 and 12:47 UTC (2026-10-13 to 10-15),
  5–8 hours late. A manually started run (`workflow_dispatch`) isn't queued that way and usually
  starts within a minute or so.
- **Lateness breaks the weekly rhythm.** The jobs depend on each other and on deadlines. Sunday's
  `results` job (06:00 ET, TASK-022) has to finish before ratings and predictions run, so that
  predictions are out by Sun 10 AM ET (D-092). The backup should run in the quiet hours before
  those jobs write. Five hours late, both slip past those times.
- **GitHub's cron only knows UTC.** 03:30 ET is 07:30 UTC in summer and 08:30 UTC in winter, so a
  GitHub cron drifts an hour at every daylight-saving change unless every job has two crons and a
  check. The dispatcher works in ET, so each job stays at the same ET time all year.
- **It's free.** It runs on Cloudflare's free Workers plan, on the same account as the R2 lake.

### What it does on each tick
Cloudflare runs the Worker every 15 minutes, all day (the Cron Trigger `*/15 * * * *` in
`wrangler.jsonc`: 96 ticks a day, at :00, :15, :30 and :45). On each tick it:

1. Converts the tick's time to `America/New_York` and rounds it down to the quarter hour, so
   07:30:04 UTC on 2026-10-17 becomes Saturday 03:30 ET.
2. Looks that weekday and time up in `SCHEDULE` (`infra/dispatcher/src/index.ts`).
3. For each job due at that time, sends `POST /repos/jtillmanio/cfb-model/actions/workflows/<file>/dispatches`
   with `{"ref": "main"}`, using the GitHub token (below).
4. Logs the result. On almost every tick nothing is due, and the Worker exits in a few
   milliseconds without calling GitHub.

GitHub then starts the workflow on `main`, and its run shows in the Actions tab with the event
`workflow_dispatch`.

### What it starts and when

| Workflow | When (ET) | Why then |
|---|---|---|
| `backup.yml` | Daily 03:30 | Quiet hours, before the morning jobs write |
| `results.yml` | Sun and Mon 06:00 | The weekend's finals; Monday's run settles the week, and both finish before Sunday's ratings and the 10 AM predictions (D-092) |
| `lines.yml` | Daily 08:00 | The daily line snapshot (02 › Non-functional requirements) |
| `lines.yml` | Thu and Fri 19:00 | The pick window, when lines move most before the weekend |

This table mirrors `SCHEDULE` in `infra/dispatcher/src/index.ts`; that file wins if they differ.
Until TASK-026, `backup.yml` also keeps its own 07:30 UTC cron, so the backup can run twice a day
(a same-day run replaces that day's dump; about 5 extra Actions minutes). `results.yml` and
`lines.yml` keep UTC crons as late fallbacks, which do nothing when the dispatcher's run succeeded
([Jobs](#jobs)).

### What it doesn't do
- **Retry.** A tick that runs late but inside its quarter hour still fires. A quarter hour Cloudflare
  skips entirely isn't made up later.
- **Tell GitHub when something fails.** A failed dispatch shows only in the Worker's logs and as a
  failed cron event in Cloudflare. TASK-026 adds a GitHub-side fallback for the backup.
- **Run anything itself, or change the workflows.** Each workflow keeps its `workflow_dispatch`
  trigger and can still be run by hand (`gh workflow run <file>`).

### Names

| Thing | Name | Where it's set |
|---|---|---|
| Cloudflare Worker | `cfb-dispatcher` | `name` in `wrangler.jsonc` |
| workers.dev subdomain | `jtillmanio` | Asked once per Cloudflare account, on the first deploy. It's shared by every Worker on the account, so name it after the account, not this project. The Worker's URL would be `cfb-dispatcher.jtillmanio.workers.dev`, but nothing uses it: the Worker only runs on its Cron Trigger |
| GitHub token | `cfb-dispatcher` | Token name on GitHub › Settings › Developer settings › Fine-grained tokens. Description: `Starts cfb-model workflows on schedule from the Cloudflare Worker cfb-dispatcher` |
| Worker secret holding that token | `GITHUB_DISPATCH_TOKEN` | `wrangler secret put` (never the repo or `wrangler.jsonc`) |
| Cloudflare API token, only if you don't use `wrangler login` | `wrangler-cfb-dispatcher` | Cloudflare dashboard › My Profile › API Tokens |
| Expiry reminder | `Rotate the cfb-dispatcher GitHub token` | Your calendar, a week before the token expires |

### First-time setup
Wrangler (Cloudflare's CLI) isn't a project dependency. Run a pinned version with `pnpm dlx`,
from `infra/dispatcher/`. Merging doesn't deploy the Worker; you deploy it by hand when it changes.

1. **Create the GitHub token.** GitHub › Settings › Developer settings › Personal access tokens ›
   **Fine-grained tokens** › Generate new token:
   - Token name `cfb-dispatcher`, with the description from the table above
   - Resource owner: your account
   - Expiration: the longest GitHub offers
   - Repository access: **Only select repositories** › `cfb-model`
   - Permissions › Repository permissions: **Actions: Read and write**, nothing else (GitHub adds
     Metadata: Read-only itself)

   Copy the token; GitHub shows it once. Add the expiry reminder to your calendar.
2. **Sign in to Cloudflare:** `pnpm dlx wrangler@4.149.0 login`.
   - pnpm first asks which packages may run their build scripts. Select **both** `esbuild` (which
     bundles the Worker when you deploy) and `workerd` (Cloudflare's local runtime, used by
     `wrangler dev`): space to select, Enter to confirm. pnpm asks again on later `dlx` runs.
   - A browser opens asking you to let Wrangler access your Cloudflare account. Check the page is on
     `dash.cloudflare.com`, then **Allow**. The list is Wrangler's default set, broader than this
     Worker needs. The token is saved in your user profile, never the repo, and
     `pnpm dlx wrangler@4.149.0 logout` revokes it. To keep access narrow instead, create a
     Cloudflare API token from the **Edit Cloudflare Workers** template, name it
     `wrangler-cfb-dispatcher`, and set `$env:CLOUDFLARE_API_TOKEN = "<token>"` in place of logging in.
3. **Deploy:** `pnpm dlx wrangler@4.149.0 deploy`. If the account has no workers.dev subdomain yet,
   Wrangler asks to register one: answer yes and enter `jtillmanio`.
4. **Store the GitHub token:** `pnpm dlx wrangler@4.149.0 secret put GITHUB_DISPATCH_TOKEN`, and
   paste the token when asked. It takes effect immediately.
5. **Check it:** Cloudflare dashboard › Workers & Pages › `cfb-dispatcher` › Settings › Triggers
   lists the cron `*/15 * * * *`. After the next 03:30 ET,
   `gh run list --workflow backup.yml --event workflow_dispatch --limit 1` shows a run that started
   within 5 minutes of it (TASK-025's AC-4).

The repo and branch are `vars` in `wrangler.jsonc`. Cloudflare's free plan allows a few Cron
Triggers per account (this uses one) and 100,000 Worker requests a day (this makes 96 runs); check
both on the Cloudflare plan page when you deploy.

### Add a job
A job is added by the task that builds its workflow, in the same PR, never ahead of it: a
`SCHEDULE` line for a workflow that isn't on `main` yet fails with `404` on every tick it's due.
TASK-022 adds `results` and `lines` this way.

1. Make sure the workflow has an `on: workflow_dispatch:` trigger and is on `main` (GitHub
   dispatches only workflow files on the default branch, D-108).
2. Add a line to `SCHEDULE`, e.g. `{ workflow: "<name>.yml", days: ["Sun", "Mon"], time: "06:00" }`.
   `days` is `"daily"` or a list of `Sun`…`Sat`. `time` is ET, `HH:MM`, on a quarter hour, and never
   between 01:00 and 02:59 (daylight saving repeats or skips those times; a test fails on one).
   Add its row to the table above.
3. Merge, then deploy again (`pnpm dlx wrangler@4.149.0 deploy` from `infra/dispatcher/`).

### Rotate the GitHub token
When the reminder comes up, or after any leak: create a new `cfb-dispatcher` token as in step 1,
run `pnpm dlx wrangler@4.149.0 secret put GITHUB_DISPATCH_TOKEN` from `infra/dispatcher/` and paste
it (it takes effect immediately, no deploy), then delete the old token on GitHub. An expired token
makes every dispatch fail with `401`.

### Try a tick locally
This dispatches for real, so it starts a real `backup` run, which reads production. Put
`GITHUB_DISPATCH_TOKEN=<token>` in `infra/dispatcher/.dev.vars` (git-ignored), run
`pnpm dlx wrangler@4.149.0 dev --test-scheduled`, then open
`http://localhost:8787/cdn-cgi/handler/scheduled?cron=*/15+*+*+*+*&time=<epoch>`, with `<epoch>` a
time inside a due quarter hour (e.g. `1792222200`, 2026-10-17 03:30 EDT). Check with
`gh run list --workflow backup.yml --event workflow_dispatch --limit 1`.

### Logs and failures
Cloudflare dashboard › Workers & Pages › `cfb-dispatcher` › **Logs** (Workers Logs, kept by
`observability` in `wrangler.jsonc`), or `pnpm dlx wrangler@4.149.0 tail` to watch live. Each
dispatch logs `dispatched <file> on main`. A failure logs `dispatch <file> failed: <status> <body>`,
the remaining jobs are still sent, and the tick ends in an error, so it shows as failed under the
Worker's cron events.

| Status | Meaning | Fix |
|---|---|---|
| `401` | The token expired, was deleted, or the secret is wrong | Rotate the token (above) |
| `403` or `404` | The token can't see the repo or lacks Actions: Read and write, or the workflow file isn't on `main` | Check the token's repository and permission; check the file name in `SCHEDULE` |
| `422` | The workflow has no `workflow_dispatch` trigger, or the branch in `vars` doesn't exist | Add the trigger on `main`, or fix `GITHUB_REF` |

Nothing on the GitHub side reports a missed dispatch yet (TASK-026 adds a fallback for the
backup). A run that didn't start shows as a gap in `gh run list --workflow <file>`.

## Backups

The **Backup** workflow (`.github/workflows/backup.yml`) runs nightly, started at 03:30 ET by the
[dispatcher](#dispatcher) (and, until TASK-026, by its own 07:30 UTC cron), and stores a dump only
after proving it restores:

1. **dump**: `pg_dump` of production through `BACKUP_DATABASE_URL` (a read-only role), and an exact
   row count of every table taken in the same snapshot as the dump.
2. **restore**: `pg_restore` into a `postgres:PG_MAJOR` container on the runner.
3. **verify**: re-applies the views of the commit production serves (from `/api/py/health`),
   queries each view, and compares row counts with production's.
4. **upload**: to R2, at every key for the run's UTC date (D-124). A re-run the same day replaces
   that day's dumps.

| Prefix | Written when the run's UTC date is | Expires after |
|---|---|---|
| `backups/daily/<date>.dump` | every day | 14 days |
| `backups/weekly/<date>.dump` | a Sunday | 90 days |
| `backups/monthly/<date>.dump` | the 1st of the month | 365 days |

The expiry periods are R2 lifecycle rules in the bucket's settings (Cloudflare › R2 ›
`cfb-backups` › Settings › Object lifecycle rules), set by the owner. The workflow never sets or
reads them: its token can write objects but not change the bucket. A failed Sunday or 1st isn't
made up later; the daily dumps cover the gap.

`PG_MAJOR` is set in one place, `.github/actions/start-postgres/action.yml`, which CI uses too.
To restore a dump, follow [docs/runbooks/restore.md](docs/runbooks/restore.md).

### Run one by hand
```powershell
gh workflow run backup.yml
gh run watch
```
The run's **Summary** lists each table's row count in production and in the restore, the views
queried, the dump size and every key it uploaded.

### Read a failed run
A failed step writes **Backup failed:** and the reason in the Summary. Before the upload, that
means nothing was uploaded and the previous nights' dumps are untouched; if the Upload step itself
failed, its summary lists which of the day's keys were written.

| Failed step | What it means | What to do |
|---|---|---|
| Dump production | `BACKUP_DATABASE_URL` is unset, pooled, or can't read a table; or `pg_dump` failed | Check the secret is `backup_reader`'s direct URL, and that the role can read every table |
| Find the commit production serves | `/api/py/health` on `PRODUCTION_URL` didn't answer (no release has put a build live yet, or the site is down), answered with Vercel's login page, or named no commit | Check `PRODUCTION_URL` is the production domain (Vercel › Settings › Domains), not a generated `*.vercel.app` alias, and that a release has run; re-run |
| Restore the dump | The dump has something a plain Postgres can't restore | Read the `pg_restore` error; production is unaffected |
| Re-apply views… | A view fails on production's data, or a table's counts differ | The summary names the view or table; a mismatch means the dump isn't trustworthy |
| Upload to R2 | A key wasn't written: the R2 token, bucket or account is wrong, or R2 refused one write | The summary lists each key as written or **Not written**. Check `R2_BACKUPS_ACCESS_KEY_ID`, `R2_BACKUPS_SECRET_ACCESS_KEY`, `R2_ACCOUNT_ID`, `R2_BUCKET`; re-run to write them all again |

### What it needs
Repository **secrets**: `BACKUP_DATABASE_URL` (the read-only `backup_reader` role's direct URL on
production), `R2_BACKUPS_ACCESS_KEY_ID` and `R2_BACKUPS_SECRET_ACCESS_KEY` (an R2 token with Object Read & Write on
the backup bucket only). Repository **variables**: `R2_ACCOUNT_ID`, `R2_BUCKET` (`cfb-backups`, a
bucket of its own, never the lake's), and `PRODUCTION_URL` (shared with the release workflow).
`PRODUCTION_URL` must be the production domain (`https://cfb-model-delta.vercel.app`), which only a
release moves; Vercel's generated aliases follow every `main` build and sit behind Vercel
Authentication. The health call also sends `x-vercel-protection-bypass` from the
`VERCEL_AUTOMATION_BYPASS_SECRET` secret (shared with the Lighthouse job), in case Deployment
Protection ever covers production (02 › Auth).

## Jobs

The **Results** and **Lines** workflows (`.github/workflows/results.yml`, `lines.yml`, TASK-022)
keep production's games, scores and lines current with nobody running anything. The
[dispatcher](#dispatcher) starts them at their ET times. Each run of `engine job results|lines`
(`python/engine/src/engine/jobs.py`, with `LIVE=true`) does, in order:

1. **pull** into the R2 lake (`LAKE_URI`), counted on its shared ledger. `results` pulls every week
   with a game in the last 14 days: `/games`, `/games/teams`, advanced stats, plays, drives and the
   post-kickoff `/lines` (6 calls a week). `lines` pulls `/games` and `/lines` for the earliest week
   with a game not yet kicked off (2 calls). A file that's already final costs no call, and a week
   becomes final 24 hours after its last kickoff, so Sunday's run is never final and Monday's
   settles it (03 › Lake layout).
2. **stage** the season alone: its raw files, plus `/venues` and `/conferences` from whichever
   season they're filed under, are copied from R2 into a scratch lake on the runner, which is
   rebuilt. The season's `/teams` is pulled once when missing, so teams and venues keep their
   details (staged from `/games` alone, they'd publish NULLs). R2's own `staging/` is never
   touched.
3. **check** the scratch staging with the data-quality checks. A failure ends the run (exit 1)
   before production is opened.
4. **publish** to production in one transaction (`PRODUCTION_DATABASE_URL_UNPOOLED`): teams, team
   seasons, venues, the season, games, and new line snapshots. Reference rows are upserted, so a
   second run adds no team or game rows.

| Workflow | When (ET) | Fallback cron (UTC) | Calls a run |
|---|---|---|---|
| `results.yml` | Sun and Mon 06:00 | `0 12 * * 0,1` | ~6 |
| `lines.yml` | Daily 08:00, Thu and Fri 19:00 | `0 14 * * *`, `0 1 * * 5,6` | 2 |

GitHub's cron knows only UTC, so each fallback fires 1–2 hours after its ET slot (an hour later in
EDT than in EST). It runs only when no dispatched run of that workflow succeeded in the last 6
hours (`.github/actions/skip-if-dispatched`). Both workflows share the `lake-publish` concurrency
group, so two runs never write the lake or publish at once; a queued one waits.

### Run one by hand
```powershell
gh workflow run results.yml
gh run watch
```
Every run writes production. The run's **Summary** lists the weeks pulled, the CFBD calls spent and
the month's total, each table's staged and new rows, and any game counted as done only because it's
unscored a week after its start (D-121): if CFBD postponed one under its old week, it needs a
manual pull when it's played. Locally, `--target dev` runs the same steps against your dev
database and `LAKE_URI`.

### Read a failed run
| Exit | What it means | What to do |
|---|---|---|
| 1 | A data-quality check failed; nothing was published | The Summary lists the failed check and the games. A late game missing advanced stats on Sunday clears on Monday's run |
| 2 | Refused: `LIVE` is unset, or `PRODUCTION_DATABASE_URL_UNPOOLED` is missing or pooled | Check the workflow's `env:` and the secret |
| 3 | The month's CFBD budget (5,000 calls) is spent | Wait for the next UTC month; nothing was published |

Any other failure (R2 credentials, a CFBD error) shows as a Python traceback in the step's log. The
lake keeps whatever was pulled before it, and the next run reuses it.

### What it needs
Repository **secrets**: `CFBD_API_KEY`, `R2_DATA_LAKE_ACCESS_KEY_ID` and
`R2_DATA_LAKE_SECRET_ACCESS_KEY` (an R2 token with Object Read & Write on the lake bucket only), and
`PRODUCTION_DATABASE_URL_UNPOOLED` (shared with the release workflow). Repository **variables**:
`LAKE_URI` (`s3://<lake bucket>`) and `R2_ACCOUNT_ID`.

## Performance checks

The **Lighthouse** workflow (`.github/workflows/lighthouse.yml`) measures every PR on its own,
twice (D-125). Each run signs in with a minted session, runs Lighthouse three times on each route
in `scripts/perf/routes.mjs` (mobile, Slow 4G, 4× CPU), and posts its own comment on the PR,
edited in place on every later run.

- **Fixture build (gated).** On every push to a PR, the job builds the app and serves it with the
  API on the seeded test database, as e2e does. The data never changes, so this run fails on what
  holds still between runs: an `/api/py/*` request from the browser, bytes or requests over
  `scripts/perf/budget.json`, CLS of 0.1 or more, accessibility below the recorded score, or a
  route that didn't measure or landed elsewhere. A PR that changes only `docs/`, `.claude/`,
  `backups/` or root `*.md` files has no fixture run.
- **Preview (reported only).** When Vercel reports the PR's preview ready, the same measurements on
  the preview's own data. Its comment shows the numbers and anything worth a look; it never fails.

Timings are shown against the last merged PR's run of the same kind and never fail either run.
Reports are the run's artifacts for 14 days. The full design is in
[02 › Performance checks](docs/02-architecture.md#performance-checks-lighthouse).

### Run one by hand
```powershell
gh workflow run lighthouse.yml --ref <branch>                          # fixture build of that branch
gh workflow run lighthouse.yml -f url=https://<preview>.vercel.app     # a preview, reported only
gh run watch
```
A hand run writes its report to the run's **Summary**, not the PR. It refuses `PRODUCTION_URL`
unless `-f allow_production=true` is passed.

### Read a failed run
Only the fixture run fails. Its PR comment (and the **report** job's Summary) lists every problem,
each naming its route.

| Problem | What it means | What to do |
|---|---|---|
| `requested /api/py/…` | A page made the browser call the API, usually a `<Link>` prefetch (hard rule 5) | Link to it with a plain `<a>` and fetch from server code |
| `… is over the budget of …` | The page got heavier | Make it lighter, or raise the budget with the reason written in the PR |
| `ended on /login` | The minted session didn't take | The **fixture** job's `AUTH_SECRET` and `AUTH_ALLOWED_GITHUB_ID` must equal `web/e2e/test-env.ts`'s (a test checks this). On a preview: `PREVIEW_AUTH_SECRET` must equal Vercel Preview's `AUTH_SECRET` |
| `never finished measuring` | Lighthouse failed on every run, or the job died | Open the **fixture** job log (a preview: that route's **measure** job; a 401 page means the bypass secret is wrong). `… never answered` in **Serve the app and the API** prints the last lines of both servers' logs |
| **No secret in the reports** step failed | A report still held a secret, so nothing was uploaded | The step names the files, never the value; fix the scrubbing in `scripts/perf/lib/perf.mjs` |

### Set a route's budget
A new screen adds its route to `scripts/perf/routes.mjs` and its budget in the same PR. A
data-heavy page's large instance is fixture data, added by the task that owns its table. Push it,
let the fixture run finish, then:
```powershell
gh run download <run id> -n lighthouse-metrics -D $env:TEMP\lh
node scripts/perf/report.mjs budget $env:TEMP\lh\metrics.json
```
It rewrites `budget.json` (median + 20%, bytes rounded up to the next 1,000, accessibility as
measured) and prints the table to paste into 02 › Performance checks. It refuses a preview run's
metrics: budgets come from the fixture build only.

### What it needs
The fixture build needs nothing: it uses e2e's test-only values. The preview run needs repository
**secrets** `PREVIEW_AUTH_SECRET` (the same value as Vercel Preview's `AUTH_SECRET`, never
production's, so the minted session can never open production) and
`VERCEL_AUTOMATION_BYPASS_SECRET` (Vercel › Settings › Deployment Protection › Protection Bypass for
Automation; sent as `x-vercel-protection-bypass` on every request to the preview), and repository
**variables** `AUTH_ALLOWED_GITHUB_ID` (the GitHub ID the session is minted for, the same as the
preview's allowlist) and `PRODUCTION_URL` (shared with the release workflow; refused unless
`allow_production` is set).

## Preview databases

Each PR preview gets its own Neon branch, `preview/<git branch>`, made by the Vercel integration.
The **Neon preview cleanup** workflow (`.github/workflows/neon-preview-cleanup.yml`) deletes it
when the PR closes, merged or not. A missing branch passes; a failed run names Neon's answer.
Delete a leftover by hand with `gh workflow run neon-preview-cleanup.yml -f branch=<git branch>`;
when nothing matches, the run lists the `preview/*` branches still in Neon. It uses the
`NEON_API_KEY` secret and `NEON_PROJECT_ID` variable the release workflow already has.

## Layout
`web/` Next.js app · `python/` uv workspace: `db` (models, migrations, views, fixture),
`engine` (CLI: ingest, seed), `api` (FastAPI) · `infra/dispatcher/` Cloudflare Worker that starts
the scheduled workflows ([Dispatcher](#dispatcher)) · `vercel.json` deploys `web` and `api` as one
Vercel project (Services).
