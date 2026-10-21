# Owner checklist

What only the owner can do, and follow-ups waiting for the owner's approval. Claude adds items and never ticks an action; the owner ticks them. Each item names where it came from.

## Actions

Things only you can do: secrets, dashboard and hosting settings, purchases, production data.

- [x] Vercel › Settings › Environments › Production: confirm `main` builds aren't auto-promoted (custom production domains not auto-assigned), so only the `release` workflow puts a build live (from TASK-005, PR #24) (owner confirmed 2026-10-12)
- [ ] Vercel › Production environment: confirm `LIVE=true` and `API_JWT_SECRET` (≥ 32 characters, its own value) are set; the release smoke test fails without the API guard's secret (from TASK-005, PR #24) _(`API_JWT_SECRET` confirmed 2026-10-12; `LIVE=true` still to set)_
- [x] Neon: delete old `release/*` snapshot branches now and then; each release with pending migrations makes one, and they count against the project's branch limit (from TASK-005, PR #24) (owner confirmed 2026-10-12)
- [x] Neon production: confirm the role in `BACKUP_DATABASE_URL` (`backup_reader`) is read-only and reads every table and sequence, including future ones: `GRANT pg_read_all_data TO backup_reader;` and no write grants. Per-table grants would miss the next migration's tables and fail the nightly dump (from TASK-006, PR #27) (owner confirmed 2026-10-15)
- [x] Cloudflare R2: create a bucket for the data lake, separate from `cfb-backups`, and an API token with Object Read & Write on that bucket only. Needed by TASK-015's R2 check, the TASK-021 backfill and the TASK-022 jobs (from the M2 task files) (owner confirmed 2026-10-15)
- [x] GitHub Actions secrets for the TASK-022 jobs: `CFBD_API_KEY`, the lake bucket's R2 token as `R2_DATA_LAKE_ACCESS_KEY_ID` and `R2_DATA_LAKE_SECRET_ACCESS_KEY`, and the production database URL the publish step uses (TASK-022's plan names it). Needed before the jobs' first branch run (from the M2 task files) _(`CFBD_API_KEY` and both `R2_DATA_LAKE_*` secrets added 2026-10-15; TASK-022's plan reuses the release's `PRODUCTION_DATABASE_URL_UNPOOLED` secret, so no new production secret is needed)_
- [x] GitHub Actions › Variables: add `LAKE_URI` = `s3://<lake bucket>` (the R2 lake bucket, not `cfb-backups`) for the TASK-022 jobs. Needed before their first branch run (from TASK-022, PR #62)
- [x] Copy the current Splash contest page's text and save it for TASK-023 as its third parser fixture, noting how many games the page shows (from the M2 task files) (owner confirmed 2026-10-15: `design/sample-splash-10152026.txt`, a full-page copy with 73 game blocks, counted by Claude from its `Over` lines)
- [x] GitHub Actions: add secrets `R2_BACKUPS_ACCESS_KEY_ID` and `R2_BACKUPS_SECRET_ACCESS_KEY` with the values of `R2_ACCESS_KEY_ID` and `R2_SECRET_ACCESS_KEY` **before** merging the PR that renames them in `backup.yml` (from the owner, 2026-10-15) (owner confirmed 2026-10-15)
- [x] GitHub Actions: delete the old secrets `R2_ACCESS_KEY_ID` and `R2_SECRET_ACCESS_KEY` once the PR renaming them in `backup.yml` has merged; until then, the nightly backup on `main` still reads them (from the owner, 2026-10-15) (owner confirmed 2026-10-16: `gh secret list` shows neither)
- [ ] GitHub › Settings › Developer settings: create a fine-grained personal access token for `jtillmanio/cfb-model` only, with Actions: Read and write and nothing else. Then, from `infra/dispatcher/` once TASK-025 merges, run `pnpm dlx wrangler@4.149.0 login`, `pnpm dlx wrangler@4.149.0 deploy`, and `pnpm dlx wrangler@4.149.0 secret put GITHUB_DISPATCH_TOKEN` (README › Dispatcher › Deploy). After the next 03:30 ET, check `gh run list --workflow backup.yml --event workflow_dispatch --limit 1` shows a run started within 5 minutes of it. Needed for TASK-025's AC-4 (from TASK-025, PR #52)
- [x] R2 lake `cfb-data-lake`: accept, or tell Claude to remove, the 10 raw files TASK-018 wrote by mistake while recording its test fixtures (`.env.local`'s `LAKE_URI` pointed `engine ingest` at R2 instead of `./data`): 2025 week 1 `games_teams`, `stats_game_advanced`, `plays`, `drives` and 2025 `talent`, `player_returning`, `recruiting_teams`, `ratings_sp`, `ratings_fpi`, `ratings_elo`, all fetched 2026-10-20T0607–0608Z. They're valid, correctly keyed pulls counted by R2's ledger, the same files TASK-021's backfill would write; nothing in `staging/` was touched (from TASK-018, PR #64)

## Approvals

Follow-ups that change a planning doc, or decisions to record, that Claude makes only with your yes. Tick one (or say "approve <item>" in a session) and the session you told, or the next `/track-follow-ups` run, makes the change and adds where it went.

- [x] Update docs/02-architecture.md § Auth: previews already have Vercel Deployment Protection (Vercel Authentication) on, so replace "If we later turn on Vercel Deployment Protection, automation … sends the `x-vercel-protection-bypass` header" with a statement that previews are protected and automation (smoke tests, the Lighthouse job) sends that header (from TASK-004, PR #21) → docs/02-architecture.md § Auth (PR #21)
- [x] Widen the deny rule in `.claude/settings.json` from `*--env-file .env.live*` to also cover `*--target live*`, so a session can't migrate production through the workflow's environment variable or a differently spelled path (`..\.env.live`) either (from TASK-005, PR #24) → .claude/settings.json § permissions.deny (PR #24)
- [x] Update .claude/rules/git.md § Project notes: "Merging does not deploy" says the `release` workflow is "not built yet; roadmap Phase 0"; name `.github/workflows/release.yml` (README › Releasing), which the owner runs (from TASK-005, PR #24) → .claude/rules/git.md § Project notes (PR #24)

## Done

_None yet._
