---
name: verify
description: Full local verification gate for this project — every command in verify.full, the same set CI runs. Run before pushing any branch.
---

# Verify

Run these in order from the project root and report the actual output, not a summary. Don't stop at the first failure: run every command, because a failing typecheck and a failing test are separate signals. Fix root causes; never suppress an error to get a pass.

```powershell
pnpm typecheck
pnpm lint
pnpm db:check
pnpm test
pnpm build
pnpm test:e2e
```

`pnpm typecheck` (tsc via `next typegen`, then pyright), `pnpm lint` (ESLint, then ruff) and `pnpm test` (Vitest, then pytest) are `&&` chains: each stops at its first failing half, so say when the python half didn't run.

`pnpm db:check` needs the test database migrated (`pnpm db:migrate:test`): it checks one Alembic head and that the models match the migrations. pytest's database tests read only `TEST_DATABASE_URL` through the test-DB guard. `pnpm test:e2e` needs the test database migrated and seeded (`pnpm db:migrate:test`, then `pnpm db:seed`), and builds the app before it starts `next start` and the API (`web/playwright.config.ts`).

Tests touch the test database only. If `TEST_DATABASE_URL` is unset, run the commands that don't need a database (`pnpm typecheck`, `pnpm lint`, `pnpm build`, and Vitest via `pnpm --dir web test`), say plainly which suites ran only in CI, and never point them at another database.

This is the local half of "Test on the branch" in `.claude/rules/git.md`. CI and any other ready gates in `workflow.readyGates` still have to pass on the branch.

Then show evidence: each command you ran, its exit code, and the lines that matter. Do not claim success without it.
