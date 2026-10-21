# Commands

The full command list. `CLAUDE.md` › Commands keeps the ones used daily. Windows; commands also run under `cmd.exe /c` (the hooks do). `.claude/kit.json` is the source of truth for verification (`verify.fast` after every edit, `verify.full` for the test-runner); keep this table and the one in `CLAUDE.md` in sync with it.

| Purpose | Command |
|---|---|
| Install dependencies | `pnpm bootstrap` (worktrees: `pnpm install --frozen-lockfile`, `uv --directory python sync`) |
| Dev server | `pnpm dev` (web :3000, API :8000) |
| Typecheck | `pnpm typecheck` (`next typegen && tsc`, the dispatcher's `tsc`, pyright) |
| Lint | `pnpm lint` (ESLint on `web/`, `infra/dispatcher/` and `scripts/`, ruff) |
| Unit / integration tests | `pnpm test` (Vitest in `web/` and `infra/dispatcher/`, pytest; pytest reads only `TEST_DATABASE_URL`) |
| Specific test files | `uv --directory python run pytest <paths>`, `pnpm --dir web exec vitest run <paths>`, `pnpm --dir web exec playwright test <paths>`, `pnpm --dir infra/dispatcher exec vitest run <paths>` (paths relative to `python/`, `web/` or `infra/dispatcher/`; `testAudit.runners` routes them the same way) |
| End to end | `pnpm test:e2e` (after `pnpm db:migrate:test` and `pnpm db:seed`) |
| Production build | `pnpm build` |
| Migrations | `pnpm db:migrate` (dev), `pnpm db:migrate:test`, `pnpm db:check` (one head, models match) |
| Seed | `pnpm db:seed` (fixture; test DB only) |

## The post-edit typecheck

`verify.fast` runs `node scripts/typecheck/run.mjs`, not `pnpm typecheck` directly. It runs `pnpm typecheck` from the repo root and exits with its exit code, but on a failure prints only the first 10 errors (each with up to 4 detail lines) and a count of the rest, so one broken edit doesn't put the whole log in Claude's context. Output it can't parse falls back to the last 40 lines. Run `pnpm typecheck` yourself for the full log. The logic is `briefTypecheck` in `scripts/typecheck/brief.mjs`, tested by `web/lib/typecheck-brief.test.ts`.

tsc's exit code depends on its incremental cache, not on the wrapper: the first failing run after a source change exits 2 (it wrote `.tsbuildinfo`), and later runs on the same tree exit 1.
