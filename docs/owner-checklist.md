# Owner checklist

What only the owner can do, and follow-ups waiting for the owner's approval. Claude adds items and never ticks an action; the owner ticks them. Each item names where it came from.

## Actions

Things only you can do: secrets, dashboard and hosting settings, purchases, production data.

- [x] Vercel › Settings › Environments › Production: confirm `main` builds aren't auto-promoted (custom production domains not auto-assigned), so only the `release` workflow puts a build live (from TASK-005, PR #24) (owner confirmed 2026-10-12)
- [ ] Vercel › Production environment: confirm `LIVE=true` and `API_JWT_SECRET` (≥ 32 characters, its own value) are set; the release smoke test fails without the API guard's secret (from TASK-005, PR #24) _(`API_JWT_SECRET` confirmed 2026-10-12; `LIVE=true` still to set)_
- [x] Neon: delete old `release/*` snapshot branches now and then; each release with pending migrations makes one, and they count against the project's branch limit (from TASK-005, PR #24) (owner confirmed 2026-10-12)
- [ ] Neon production: confirm the role in `BACKUP_DATABASE_URL` (`backup_reader`) is read-only and reads every table and sequence, including future ones: `GRANT pg_read_all_data TO backup_reader;` and no write grants. Per-table grants would miss the next migration's tables and fail the nightly dump (from TASK-006, PR #27)
- [ ] Vercel › Deployments: check which deployment `PRODUCTION_URL` serves. The backup's branch run on 2026-10-12 got commit `ad36d65` (the #26 merge, minutes old) from production's health, though no real release has run. If `main` builds are reaching the production domain, turn off auto-assignment for every production domain, including the `.vercel.app` one, so only the `release` workflow promotes (D-018). Production's database also has no tables yet; the first real release migrates it (from TASK-006, PR #27)

## Approvals

Follow-ups that change a planning doc, or decisions to record, that Claude makes only with your yes. Tick one (or say "approve <item>" in a session) and the session you told, or the next `/track-follow-ups` run, makes the change and adds where it went.

- [x] Update docs/02-architecture.md § Auth: previews already have Vercel Deployment Protection (Vercel Authentication) on, so replace "If we later turn on Vercel Deployment Protection, automation … sends the `x-vercel-protection-bypass` header" with a statement that previews are protected and automation (smoke tests, the Lighthouse job) sends that header (from TASK-004, PR #21) → docs/02-architecture.md § Auth (PR #21)
- [x] Widen the deny rule in `.claude/settings.json` from `*--env-file .env.live*` to also cover `*--target live*`, so a session can't migrate production through the workflow's environment variable or a differently spelled path (`..\.env.live`) either (from TASK-005, PR #24) → .claude/settings.json § permissions.deny (PR #24)
- [x] Update .claude/rules/git.md § Project notes: "Merging does not deploy" says the `release` workflow is "not built yet; roadmap Phase 0"; name `.github/workflows/release.yml` (README › Releasing), which the owner runs (from TASK-005, PR #24) → .claude/rules/git.md § Project notes (PR #24)

## Done

_None yet._
