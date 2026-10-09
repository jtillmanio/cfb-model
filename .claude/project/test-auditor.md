# test-auditor: cfb-model

Project section for `.claude/agents/test-auditor.md`. The kit never ships or overwrites this file.

## Runners

`testAudit.runners` in `.claude/kit.json` routes each test file. Each runner runs from its `dir`, so the paths in its output are relative to `python/` or `web/`; prefix them when you report.

- **pytest** (`python/*/tests/test_*.py`, from `python/`): an assertion failure is `FAILED api/tests/test_x.py::test_name - AssertionError: …`, which is **DISCRIMINATING**. **FAILS-TO-LOAD** looks like `ERROR … - ModuleNotFoundError` / `ImportError while importing test module`, or `ImportError: cannot import name …` during collection. Exit 4 means a path wasn't found and exit 5 means no tests were collected; neither is a test result. `conftest.py` and fixtures have no runner; report them as `no runner`, not as a gap.
- **Vitest** (`web/*.test.ts*`, from `web/`): an assertion failure is `FAIL lib/x.test.ts > … > name` with `AssertionError` and an Expected/Received diff. **FAILS-TO-LOAD** looks like `Failed to resolve import "…"` / `Cannot find module` / `Failed to load url`, reported against the file rather than a test name.
- **Playwright** (`web/e2e/*.spec.ts`, from `web/`): it needs the migrated, seeded test DB and runs `pnpm build` first (`web/playwright.config.ts`). A `webServer` startup error or a `next build` error against base is **FAILS-TO-LOAD**, not discrimination. An `expect(…)` failure with Expected/Received is **DISCRIMINATING**. One test fails at both widths (`[phone]`, `[desktop]`); count it once.

## The test database

Database tests read only `TEST_DATABASE_URL` through the test-DB guard. If they error on the guard, report `NOT RUN` for those tests instead of classifying them.

`testAudit.setup` is empty on purpose. `pnpm db:migrate:test` only upgrades (there is no reset), so after you delete a migration the task added, it fails with "Can't locate revision" and would make every audit NOT RUN. The test DB therefore stays at the task branch's schema during the dynamic check. A DB test that fails against base only because a reverted migration's model or module is missing is **FAILS-TO-LOAD**; one that fails on an assertion about values is **DISCRIMINATING**.
