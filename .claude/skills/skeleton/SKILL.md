---
name: skeleton
description: Builds the walking skeleton defined in docs/architecture.md — project scaffold, toolchain scripts, one thin end-to-end slice with a unit test and an e2e smoke test, CI, and dev setup — so /customize-kit has a real stack to configure. Use when the user runs /skeleton or asks to scaffold or bootstrap the project.
---

# Walking skeleton

Goal: the smallest running system that exercises every layer once, with every check the kit will rely on already working. **No product features beyond the slice.**

## Phase 0: Preflight

1. Read `docs/architecture.md` §2 (Stack), §8 (Testing strategy), §9 (Walking skeleton spec), and `docs/decisions.md`. If §9 is missing, stop and suggest `/architecture`.
2. The working tree must be clean. Create branch `task/skeleton`.
3. Confirm the toolchain exists locally: runtime versions, package manager, database access. List anything missing with the install command (PowerShell) and stop.
4. Secrets: you write `.env.example` with placeholder values only. If the app needs real secrets (a database URL, API keys), ask the user to create `.env.local` from it. That file is protected, so you can't and shouldn't write it.

## Phase 1: Plan (gate)

Present a plan of at most 30 lines covering:

- **Scaffold**: the official generator command for the framework, and the flags to use.
- **Scripts** to add, with exact names: `dev`, `typecheck`, `lint`, `test`, `test:e2e`, `build`, plus `db:migrate` and `db:seed` if there's a database. Each must run under `cmd.exe /c` on Windows.
- **The slice**: one screen, the route or action behind it, and the entity it reads. Use the first screen of the main MVP flow.
- **Tests**: one unit test on real logic, one e2e smoke test that loads the slice and asserts real seeded data.
- **Data**: the first migration (the slice's entity only), a seed script, and `.env.example`.
- **CI**: replace the "not configured" step in `.github/workflows/ci.yml` with this stack's setup and checks; set `on.push.branches` to the default branch.
- **Ignores**: exclude `.claude/` from the linter, typechecker, test runner, and formatter.
- **Not included**: everything else. List the tempting extras you're deliberately leaving out.

**Stop for approval.**

## Phase 2: Build

1. Scaffold with the generator. Don't hand-write what the generator produces.
2. Add the scripts, the slice, the migration, the seed, the tests, `.env.example`, and the CI changes.
3. Apply the design tokens from `design/` (colors, type, spacing) as the base styles, so later UI tasks start on-brand. Build only the slice's screen.
4. Write `README.md` dev setup: prerequisites, install, env setup, migrate, seed, run, test. Use PowerShell commands.

## Phase 3: Verify (gate)

1. Run every script once from a clean state: install → migrate → seed → typecheck → lint → test → test:e2e → build.
2. Report a table with script, exit code, and seconds. Everything must pass. Fix and re-run until it does, at most 3 rounds, then stop and report.
3. Start `dev` and confirm the slice renders seeded data at the expected URL.

## Phase 4: Hand off

1. Commit (`chore(skeleton): walking skeleton`), push `task/skeleton`, and open a PR with `gh pr create`. The user merges after CI passes.
2. Report: the script table, the slice URL, the PR link, and what was deliberately left out.
3. Next step, after merge: `/customize-kit`. It will now detect these scripts and fill `kit.json`.
