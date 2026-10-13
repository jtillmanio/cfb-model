---
id: TASK-009
title: Add Dependabot and the CI check that blocks edits to merged migrations
status: Review
depends_on: []
size: M
model: sonnet
autonomy: attended
ui: false
plan_status: approved
planned_at_commit: 5cbb932
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

- [x] AC-1: The merged-migration check is a tested Python function: given `git diff --name-status` lines between the base and the branch, it fails on any `M`, `R` or `D` entry under `python/db/migrations/versions/` and names each file, and passes when the only change there is an added file. Unit tests cover modified, renamed, deleted, added, and changes outside the folder.
- [x] AC-2: The `verify` job in `.github/workflows/ci.yml` runs the check on every PR and push to `main` (checkout with enough history for the merge base), before the migration steps.
- [x] AC-3: Shown on the branch before the PR is ready: a throwaway commit that edits `0001_reference_tables.py` makes the check exit non-zero naming that file; reverting it makes the check pass. (The throwaway commit never reaches the PR's final diff.)
- [x] AC-4: `.github/dependabot.yml` covers npm at `/` and `/web`, uv at `/python` and `github-actions` at `/`, and ignores `next` and `eslint-config-next` major versions and `typescript` versions ≥ 7, with a comment beside each ignore giving the reason (hand upgrade; TypeScript 7 ships no JS API).
- [x] AC-5: The `0001_*` entry is removed from `protectedPaths` in `.claude/kit.json`, as its reason asks; every other entry is unchanged.

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

## Follow-ups

- Candidate decision: the merged-migration check's diff bases (PR: `origin/<base_ref>` three-dot, so the merge base; push to `main`: `github.event.before`), Dependabot's weekly Monday schedule with a 7-day cooldown, minor+patch grouped per ecosystem with majors one PR each, and `@auth/core` ignored in `scripts/perf` → docs/decisions.md § D-110 (approved at plan)

## Plan

Approved 2026-10-13 at `5cbb932`.

1. Tests first, failing: AC-1 (`python/db/tests/test_merged_migrations.py`), AC-2, AC-4, AC-5 (`python/db/tests/test_ci_config.py`).
2. `python/db/src/db/merged_migrations.py`: `violations(name_status_lines) -> list[str]`, pure; fails `M`, `T`, `D`, and `R` whose old path is under `python/db/migrations/versions/`; `A` passes, `C` passes (the source is untouched). A git wrapper runs `git diff --name-status --find-renames <base>...HEAD`, prints each offending file and exits 1.
3. `python/db/src/db/__main__.py`: `python -m db merged-migrations --base <ref>`.
4. `.github/workflows/ci.yml`: checkout `fetch-depth: 0`; step "Merged migrations unchanged" after Install, before "Migrate the test DB"; base via `env`: PR → `origin/<base_ref>` (three-dot = merge base), push to `main` → `github.event.before`.
5. `.github/dependabot.yml`: npm `/` + `/web` (ignore `next` and `eslint-config-next` majors, `typescript` ≥ 7, reason beside each); npm `/scripts/perf` (ignore `@auth/core`: must equal next-auth's, `web/lib/perf.test.ts`); uv `/python`; github-actions `/`. Weekly Monday, 7-day cooldown, minor+patch grouped per ecosystem, majors one PR each.
6. `.claude/kit.json`: drop the `0001_*` protected path.
7. AC-3 locally before the PR: throwaway commit editing `0001_reference_tables.py` → the check exits 1 naming it; `git revert` → exits 0. Net zero diff; the squash drops both.

Files: `.github/dependabot.yml` (new), `.github/workflows/ci.yml`, `python/db/src/db/merged_migrations.py` (new), `python/db/src/db/__main__.py`, `python/db/tests/test_merged_migrations.py` (new), `python/db/tests/test_ci_config.py` (new, not in Files likely touched), `.claude/kit.json`.

Tests: AC-1 unit tests for each status plus outside-folder changes, and a temp git repo run of the CLI on an edited migration; AC-2/AC-4/AC-5 text and JSON checks in `test_ci_config.py` (the `test_backup.py` style), plus the PR's own CI run; AC-3 manual (above), output in the PR.

## Review log

Verify R1 PASS | AC-3 shown locally (1a8b156 edit → exit 1 naming `0001_reference_tables.py`; fe90352 revert → exit 0) | Audit R1 PASS (two optional strengthenings taken in 4fa7cab) | Spec R1 APPROVE (on the D-110 row at close-out)

## Blocked

_Only if status is Blocked: what failed, what was tried, best hypothesis, decision needed._

## Metrics

- Verify rounds: 1
- Review rounds: 1
- First-pass AC FAILs: 0
- Plan revisions after approval: 0
