---
id: TASK-009
title: Add Dependabot and the CI check that blocks edits to merged migrations
status: Ready
depends_on: []
size: M
model: sonnet
autonomy: attended
ui: false
plan_status: none
planned_at_commit:
---

# TASK-009 — Add Dependabot and the CI check that blocks edits to merged migrations

## Goal

Dependency updates arrive as PRs on their own, except the majors that need a hand upgrade, and CI fails any PR that edits, renames or deletes a migration already on `main`.

## Context

- Task list: `docs/08-tasklist.md` › M1 › M1.6 (sized M here, not S: two concerns over about 6 files).
- Architecture: `docs/02-architecture.md` › Release & operations › Migration checks in CI ("No migration already on `main` was edited, renamed or deleted (a git diff check)") and › Dependabot (ignore Next.js majors and TypeScript 7, reason beside each).
- Rules: `.claude/rules/database.md` › Migrations (forward-only; never edit, rename or delete a migration on `main`); `.claude/rules/web.md` (Next.js and TypeScript ≥ 7 majors are hand upgrades); `.claude/rules/git.md` (a dependency bot's branches are the one naming exception; its PRs pass the same CI).
- Decisions: D-020 (CI migration checks), D-021 (Dependabot ignores), D-005 (Next.js 16).
- Existing code: `.github/workflows/ci.yml` (`verify` job; already runs one-head and `alembic check` via `pnpm db:check`); `python/db/src/db/__main__.py`; migrations in `python/db/migrations/versions/`. `.claude/kit.json` › `protectedPaths` has a `0001_*` entry whose reason says to remove it once this check exists.
- Ecosystems to watch: npm (pnpm workspace at `/` and `web/`), uv (`python/`), GitHub Actions. `scripts/perf/` (npm) is added by TASK-007; include it if that task has merged.
- **Decide at the plan gate:** the diff base for PRs (merge base with `origin/main`) and for pushes to `main` (the previous commit), and the update schedule and grouping.

## Acceptance criteria

- [ ] AC-1: The merged-migration check is a tested Python function: given `git diff --name-status` lines between the base and the branch, it fails on any `M`, `R` or `D` entry under `python/db/migrations/versions/` and names each file, and passes when the only change there is an added file. Unit tests cover modified, renamed, deleted, added, and changes outside the folder.
- [ ] AC-2: The `verify` job in `.github/workflows/ci.yml` runs the check on every PR and push to `main` (checkout with enough history for the merge base), before the migration steps.
- [ ] AC-3: Shown on the branch before the PR is ready: a throwaway commit that edits `0001_reference_tables.py` makes the check exit non-zero naming that file; reverting it makes the check pass. (The throwaway commit never reaches the PR's final diff.)
- [ ] AC-4: `.github/dependabot.yml` covers npm at `/` and `/web`, uv at `/python` and `github-actions` at `/`, and ignores `next` and `eslint-config-next` major versions and `typescript` versions ≥ 7, with a comment beside each ignore giving the reason (hand upgrade; TypeScript 7 ships no JS API).
- [ ] AC-5: The `0001_*` entry is removed from `protectedPaths` in `.claude/kit.json`, as its reason asks; every other entry is unchanged.

## Out of scope

- The hand-written downgrade and up → down → up test for destructive migrations (D-020's last check): no destructive migration exists yet; it lands with the first one.
- Merging or triaging Dependabot's first PRs.
- Auto-merge for Dependabot PRs.

## Files likely touched

- `.github/dependabot.yml` — update config with the reasoned ignores (new).
- `.github/workflows/ci.yml` — the merged-migration step.
- `python/db/src/db/merged_migrations.py` — the check as a pure function plus a git wrapper (new).
- `python/db/src/db/__main__.py` — a subcommand CI calls with the base ref.
- `python/db/tests/test_merged_migrations.py` — AC-1 (new).
- `.claude/kit.json` — drop the `0001_*` protected path.

## Verification

- Automated: `python/db/tests/test_merged_migrations.py`; CI green on the PR with the check running.
- Manual: AC-3's throwaway commit on the branch → CI (or the local subcommand) fails naming `0001_reference_tables.py`; after the revert → passes. After merge, the repo's Insights › Dependency graph › Dependabot tab shows the three ecosystems with no config errors.

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
