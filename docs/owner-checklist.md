# Owner checklist

What only the owner can do, and follow-ups waiting for the owner's approval. Claude adds items and never ticks an action; the owner ticks them. Each item names where it came from.

## Actions

Things only you can do: secrets, dashboard and hosting settings, purchases, production data.

- [ ] Vercel › Settings › Environments › Production: confirm `main` builds aren't auto-promoted (custom production domains not auto-assigned), so only the `release` workflow puts a build live (from TASK-005, PR #24)
- [ ] Vercel › Production environment: confirm `LIVE=true` and `API_JWT_SECRET` (≥ 32 characters, its own value) are set; the release smoke test fails without the API guard's secret (from TASK-005, PR #24)
- [ ] Neon: delete old `release/*` snapshot branches now and then; each release with pending migrations makes one, and they count against the project's branch limit (from TASK-005, PR #24)

## Approvals

Follow-ups that change a planning doc, or decisions to record, that Claude makes only with your yes. Tick one (or say "approve <item>" in a session) and the session you told, or the next `/track-follow-ups` run, makes the change and adds where it went.

- [x] Update docs/02-architecture.md § Auth: previews already have Vercel Deployment Protection (Vercel Authentication) on, so replace "If we later turn on Vercel Deployment Protection, automation … sends the `x-vercel-protection-bypass` header" with a statement that previews are protected and automation (smoke tests, the Lighthouse job) sends that header (from TASK-004, PR #21) → docs/02-architecture.md § Auth (PR #21)
- [ ] Widen the deny rule in `.claude/settings.json` from `*--env-file .env.live*` to also cover `*--target live*`, so a session can't migrate production through the workflow's environment variable or a differently spelled path (`..\.env.live`) either (from TASK-005, PR #24)
- [ ] Update .claude/rules/git.md § Project notes: "Merging does not deploy" says the `release` workflow is "not built yet; roadmap Phase 0"; name `.github/workflows/release.yml` (README › Releasing), which the owner runs (from TASK-005, PR #24)

## Done

_None yet._
