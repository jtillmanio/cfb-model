---
id: TASK-005
title: Add the release workflow that migrates, promotes and smoke-tests
status: Ready
depends_on: []
size: M
model: opus
autonomy: attended
ui: false
plan_status: none
planned_at_commit:
---

# TASK-005 — Add the release workflow that migrates, promotes and smoke-tests

## Goal

Production changes only when the owner runs one `release` workflow: it picks a build CI has passed, backs up the database before any migration, migrates, puts the build live and proves it's healthy, and a dry run shows all of that without changing anything.

## Context

- Task list: `docs/08-tasklist.md` › M1 › M1.3. Also closes two Phase 0 partials in `docs/06-roadmap.md` › Phase 0: `.env.live` with its explicit flag, and views re-applied on release.
- Architecture: `docs/02-architecture.md` › Release & operations (plan → snapshot → migrate → views → promote → smoke test; schema first, code second); › Environments & databases (`.env.live` read only when passed explicitly; unpooled URL for migrations; `LIVE=true` on production); › Testing strategy › Levels › Operations.
- Decisions: D-018 (merge is not deploy), D-015 (env guards), D-016 (unpooled for migrations), D-100 (one Vercel project with services; health at `/api/py/health`; the preview build refuses production's host).
- Existing code: `python/db/src/db/__main__.py` (`migrate|check --target dev|test|preview`), `python/db/src/db/migrate.py` (`upgrade` re-applies views after migrating), `python/db/src/db/config.py` (`direct_url`, `preview_migration_url`, `refuse_if_live`); `python/api/src/api/main.py` `health()` returns `commit`, `db_reachable`, `migration_head`.
- Rules: `.claude/rules/python.md` (scripts are engine/db CLI commands in Python, not bash pairs).
- **Decide at the plan gate:** how "plan" finds the newest ready production build for a commit on `main` (Vercel API or CLI) and checks CI's `verify` on that exact commit (GitHub API); how the Neon snapshot branch is named and created (Neon API); the `workflow_dispatch` inputs (`dry_run`, defaulting to true, and optionally a commit).
- **Owner prerequisites:** repository **secrets** `VERCEL_TOKEN`, `NEON_API_KEY` and `PRODUCTION_DATABASE_URL_UNPOOLED`; repository **variables** `VERCEL_ORG_ID`, `VERCEL_PROJECT_ID`, `NEON_PROJECT_ID` (set 2026-10-09) and `PRODUCTION_URL`. IDs are variables because they're identifiers, useless without the token or key, and a variable shows in logs where a masked secret hides it. Also: Vercel set so `main` builds aren't auto-promoted, and `LIVE=true` in Vercel Production. Claude lists them; the owner creates them. Names are in `.env.example` › Lives elsewhere.
- **Stop and ask:** Claude never starts this workflow, dry run included, unless the owner says so for that run (CLAUDE.md › Workflow). Testing it on the branch with `gh workflow run release.yml --ref <branch> -f dry_run=true` needs the owner's go-ahead in the session.

## Acceptance criteria

- [ ] AC-1: The plan step is a tested Python function: given a list of deployments and CI results, it picks the newest ready production build whose commit is on `main` and refuses (non-zero exit, message naming the commit) when that commit's `verify` check didn't pass. Unit tests cover pass, failed CI, CI still running, and no ready build.
- [ ] AC-2: The smoke check is a tested Python function: given a `/api/py/health` response, it fails when `commit` differs from the planned commit, `db_reachable` is false, or `migration_head` differs from the repo's single Alembic head, and names which one failed. Unit tests cover each case and the passing case.
- [ ] AC-3: `.env.live` is read only through an explicit flag: `python -m db migrate --target live` refuses unless `--env-file .env.live` is passed (or the workflow passes the URL in the environment), and nothing reads `.env.live` implicitly. Unit tests in `python/db/tests/` cover the refusal and the explicit path.
- [ ] AC-4: `.github/workflows/release.yml` has only a `workflow_dispatch` trigger, `concurrency: release` (no cancel-in-progress), `permissions` scoped per job, and runs in order: plan → Neon snapshot (only when Alembic reports pending migrations) → migrate with the unpooled URL and re-apply views → promote → smoke test against the production domain. Secrets reach steps only through `env:`.
- [ ] AC-5: With `dry_run: true`, a run on the branch (owner-approved) goes green and its job summary names the commit, the build, CI's result and the pending migrations (or "none"), and records that no snapshot was made, no migration ran and nothing was promoted.
- [ ] AC-6: The README (or the doc the plan names) lists the workflow's secrets and the steps to run a release and to read a failed one.

## Out of scope

- Running a real (non-dry-run) release: the owner does that after merge.
- The nightly backup (TASK-006).
- `rebuild` applying views (the other Phase 0 partial; it arrives with `transform --rebuild` in M2.3).
- Rollback automation beyond the Neon snapshot the run creates.
- Scheduled jobs (M2.7).

## Files likely touched

- `.github/workflows/release.yml` — the workflow (new).
- `python/db/src/db/release.py` — plan selection, pending-migration check and smoke check as pure functions (new).
- `python/db/src/db/__main__.py` — `--target live`, `--env-file`, and the release subcommands.
- `python/db/src/db/config.py` — the explicit `.env.live` path.
- `python/db/tests/test_release.py` — AC-1, AC-2 (new); `python/db/tests/test_db_config.py` — AC-3.
- `README.md` — secrets and how to run a release.

## Verification

- Automated: `python/db/tests/test_release.py`; `python/db/tests/test_db_config.py`; the dry-run workflow run on the branch (AC-5), once the owner approves it.
- Manual: read the dry run's job summary → it names the latest green `main` commit and its build, and says nothing was changed. After merge, the owner runs a real release → the smoke step passes and `/api/py/health` on production shows the released commit.

## Plan

_Written by /plan-batch or /implement-task Phase 1. Approved by the user (plan_status: approved) before any code is written._

## Review log

_Filled by /implement-task. One line per round._

## Blocked

_Only if status is Blocked: what failed, what was tried, best hypothesis, decision needed._

## Metrics

- Verify rounds:
- Review rounds:
- First-pass AC FAILs:
- Plan revisions after approval:
