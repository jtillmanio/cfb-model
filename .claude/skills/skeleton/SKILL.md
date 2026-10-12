---
name: skeleton
description: Builds the walking skeleton defined in the Architecture doc — project scaffold, toolchain scripts, one thin end-to-end slice with a unit test and an e2e smoke test, CI, and dev setup — so /customize-kit has a real stack to configure. Use when the user runs /skeleton or asks to scaffold or bootstrap the project.
---

# Walking skeleton

> **Doc roles:** names in **bold** such as **Architecture**, **Data model**, or **Decisions** are roles in the "Project docs" table in `CLAUDE.md`. Always read and write the path the table gives for a role, including a `§ section` if it names one. The path in parentheses is only the default, used when the table is missing. If a role maps to `—`, follow the fallback stated in the step, or ask. Refer to sections by name, never by number.

> **Project overrides:** read `.claude/project/skeleton.md` if it exists. It holds this project's instructions for this skill and wins where it conflicts with this file, except that it can't lower the floor: plan gate first, no real secrets written, nothing committed on the base branch.

Goal: the smallest running system that exercises every layer once, with every check the kit will rely on already working. **No product features beyond the slice.**

## Phase 0: Preflight

1. Read the **Architecture** doc (default `docs/architecture.md`): its Stack, Testing strategy, Environments, and Walking skeleton spec sections. Also read the **Data model** for the slice's entity, and the **Decisions** log. If there's no walking skeleton spec section, stop and suggest `/architecture`, or ask the user where the spec is.
2. The working tree must be clean. Create branch `task/skeleton`.
3. Confirm the toolchain exists locally: runtime versions, package manager, database access. List anything missing with the install command (PowerShell) and stop.
4. Secrets: you write `.env.example` with placeholder values only. If the app needs real secrets (a database URL, API keys), ask the user to create the real env file from it. That file is protected, so you can't and shouldn't write it.

## Phase 1: Plan (gate)

Present a plan of at most 35 lines covering:

- **Scaffold**: the official generator command for the framework, and the flags to use.
- **Scripts** to add, with exact names: `dev`, `typecheck`, `lint`, `test`, `test:e2e`, `build`, plus `db:migrate`, `db:seed` and `test:db:reset` if there's a database. Each must run under `cmd.exe /c` on Windows.
- **The slice**: one screen, the route or action behind it, and the entity it reads. Use the first screen of the main MVP flow.
- **Tests**: one unit test on real logic, one e2e smoke test that loads the slice and asserts real seeded data.
- **Data** (if there's a database):
  - the first migration (the slice's entity only), a seed script, and `.env.example`;
  - **a test-database guard**: one small module every test setup calls first. It reads `TEST_DATABASE_URL` only, refuses when it is unset, and refuses when it names the same host and database as `DATABASE_URL`. There is no fallback to `DATABASE_URL`. The guard gets its own unit test;
  - **a migration check script** that CI runs: migrations already on the base branch are append-only (no edit, rename, or delete; diff against the base), every migration file is in the tool's journal and the other way round, the schema definition has no change the generator hasn't turned into a migration, and, if the project chose down files, every migration that drops, retypes, or merges a column has one. This replaces protecting migrations by path: a glob blocks a branch from regenerating its own unmerged migration, and a list of applied files goes stale with the next merge;
  - the **Environments** the architecture chose: which env file names which database, a `.env.example` whose default points at development, never production; with the full ladder, the "live" switch that makes destructive scripts refuse.
- **CI**: replace the "not configured" step in `.github/workflows/ci.yml` with this stack's setup and checks; set `on.push.branches` to the default branch. With a database: enable the service block with the production database's major version, pulled from `public.ecr.aws/docker/library/` (the mirror of Docker's official images; Docker Hub rate-limits anonymous pulls), set `TEST_DATABASE_URL` only (no `DATABASE_URL` in the test job; a dummy one only on a build step that needs it), and run the migration check.
- **Ignores**: exclude `.claude/` from the linter, typechecker, test runner, and formatter.
- **Not included**: everything else. List the tempting extras you're deliberately leaving out.

**Stop for approval.**

## Phase 2: Build

1. Scaffold with the generator. Don't hand-write what the generator produces.
2. Add the scripts, the slice, the migration, the seed, the test-database guard, the migration check, the tests, `.env.example`, and the CI changes.
3. Apply the **Design tokens** (colors, type, spacing, radius) as the base styles, so later UI tasks start on-brand. If that role is `—`, take the tokens from the **Design source of truth**. Build the slice's screen to match its design in the **Design source of truth** and its **Reference screenshots**, and build only that screen.
4. Write `README.md` dev setup: prerequisites, install, env setup (which file names which database), migrate, seed, run, test. Use PowerShell commands.

## Phase 3: Verify (gate)

1. Run every script once from a clean state: install → migrate → seed → typecheck → lint → test → test:e2e → build. Run the migration check, and run the tests once with `TEST_DATABASE_URL` unset to confirm the guard refuses.
2. Report a table with script, exit code, and seconds. Everything must pass. Fix and re-run until it does, at most 3 rounds, then stop and report.
3. Start `dev` and confirm the slice renders seeded data at the expected URL.

## Phase 4: Hand off

1. Place what was deliberately left out as follow-ups, by `workflow.followUps` and `.claude/skills/track-follow-ups/classify.md` (usually a stub in the **Task list** or roadmap, an Architecture note, or an Owner checklist action), asking for the approvals it needs.
2. Commit by path (`chore(skeleton): walking skeleton`, placements included), push `task/skeleton`, and open a PR with `gh pr create`. Its body has a **Follow-ups** section: each left-out item ending `→ <path> § <section>` or `→ not tracked: <reason>`. The user merges after CI passes.
3. Report: the script table, the slice URL, the PR link, and where each left-out item went.
4. Next step, after merge: `/customize-kit`. It will now detect these scripts and fill `kit.json`.
