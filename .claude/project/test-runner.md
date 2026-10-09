# test-runner: cfb-model

Project section for `.claude/agents/test-runner.md`. The kit never ships or overwrites this file.

## Reading this stack's output

Root scripts run per app with `--dir web` or `--directory python`, so most paths are relative to that app. Prefix `web/` or `python/` when you report them.

`pnpm typecheck`, `pnpm lint` and `pnpm test` are `&&` chains (web first, then python; see `package.json`). Each stops at its first failing half: if the web half fails, say the python half didn't run, rather than reporting it as passing.
- **tsc** (`pnpm typecheck`): `app/x.tsx(12,5): error TS2322: …`, relative to `web/`.
- **pyright**: `C:\…\python\db\src\db\x.py:12:5 - error: …`, absolute. Report the repo-relative path.
- **ESLint** (`pnpm lint`): an absolute file header, then `12:5  error  <message>  <rule-id>`.
- **ruff**: `db/src/db/x.py:12:5: F401 …`, relative to `python/`.
- **Vitest** (`pnpm test`, first half): `FAIL lib/x.test.ts > suite > test name`, then `AssertionError: expected … to be …` with a `- Expected` / `+ Received` diff and a `❯ lib/x.test.ts:12:5` location.
- **pytest** (`pnpm test`, second half; `-q`): the summary lists `FAILED db/tests/test_x.py::test_name - AssertionError: …`. The traceback shows `assert <left> == <right>` with values filled in and ends at `db/tests/test_x.py:42: AssertionError`. Errors mentioning `TEST_DATABASE_URL` come from the test-DB guard (env not set), not from code.
- **db:check**: success prints `One head: <rev>` and `No new upgrade operations detected.` Failure means several heads, or models and migrations diverge (Alembic lists the operations). It also fails if the test DB isn't migrated; say so and don't migrate it yourself.
- **next build**: `./app/x.tsx:12:5` then `Type error: …`, relative to `web/`.
- **Playwright** (`pnpm test:e2e`): `✘ [desktop] › e2e/teams.spec.ts:5:5 › test name`, then `Error: expect(locator).toHaveText(expected)` with `Expected:` / `Received:` and a code frame. One failure at both widths (`[phone]` and `[desktop]`) is one entry.

