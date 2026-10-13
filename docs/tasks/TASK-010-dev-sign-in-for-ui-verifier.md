---
id: TASK-010
title: Let the ui-verifier sign in to the local dev server
status: Ready
depends_on: []
size: S
model: sonnet
autonomy: attended
ui: false
plan_status: approved
planned_at_commit: e02e2dc
---

# TASK-010 — Let the ui-verifier sign in to the local dev server

## Goal

The ui-verifier agent can open signed-in screens on the local dev server, so UI tasks get browser verification beyond `/login`. Production keeps GitHub as its only way in.

## Context

- Found during the kit 2.6 upgrade (`chore/kit-2.6`): GitHub sign-in shipped in TASK-001, but `ui.auth` in `.claude/kit.json` is still null, so the ui-verifier stops at `/login`. `.claude/project/ui-verifier.md` § Sign-in now tells it to report signed-in criteria as NOT RUN until this lands.
- Architecture: `docs/02-architecture.md` § Test-only sign-in and clock (the e2e mint lives in the Playwright fixtures, never in `web/` source); § Performance checks (the Lighthouse job mints with the preview `AUTH_SECRET`, `scripts/perf/mint-session.mjs`).
- Decisions: D-090 (e2e mints a session cookie), D-012 (each environment has its own `AUTH_SECRET`), D-101, D-102.
- The kit's `ui.auth` is `{ loginPath, envFile, secretVar, steps }`, and its steps type a secret into a sign-in form. A minted cookie doesn't fit that shape, so the plan must choose between a dev-only route or form that never ships to production, and a mint the agent runs before it opens the browser (via `.claude/project/ui-verifier.md`). Either way, a decision row records the choice.
- Open questions for the plan: which `.env.local` variables the mint may read (`AUTH_SECRET`, `AUTH_ALLOWED_GITHUB_ID`), and how a test proves the mechanism can't open production.
- Chosen when the ACs were written (2026-10-13): the agent-run mint. A dev-only route or form would put a way in inside `web/`, which D-101 already rejected for previews and § Test-only sign-in forbids. The mint reuses what e2e and the Lighthouse job already do.

## Acceptance criteria

- [ ] AC-1: `node web/e2e/dev-session.mjs <url>` prints exactly one line to stdout: a Playwright cookie as JSON (`authjs.session-token`, the given URL, `httpOnly`, `sameSite: "Lax"`, expiring in 1 hour). Its value is the session Auth.js would set after the allowlisted account signed in with GitHub. The script reads `AUTH_SECRET` and `AUTH_ALLOWED_GITHUB_ID` only, and only from the repo root's `.env.local`: no other file, no flag that picks a file, and no fallback to the process environment. It never prints `AUTH_SECRET`.
- [ ] AC-2: The script refuses (exit 1, reason on stderr, nothing on stdout) when the URL isn't `http:` on a loopback host (`localhost`, `127.0.0.1`, `[::1]`), or when `.env.local` lacks either variable. Vitest covers each refusal. It also shows that a minted cookie decodes with the secret it was minted with and not with any other, which is why it can't open a preview or production (D-012).
- [ ] AC-3: A test fails if any file under `web/app/` or `web/lib/` (tests excepted), or `web/proxy.ts`, `web/auth.ts` or `web/auth.config.ts`, imports from `e2e/`. The mint never becomes app source.
- [ ] AC-4: `.claude/project/ui-verifier.md` § Sign-in tells the ui-verifier to:
  - run the mint for the resolved base URL, add the cookie to the browser context, and then confirm a signed-in route doesn't redirect to `/login`;
  - report signed-in criteria as `NOT RUN: dev sign-in failed (<reason>)` if minting fails;
  - never put the cookie value in its report, a screenshot name or a URL.
  `ui.auth` stays null, and the section says why.
- [ ] AC-5: A new `docs/decisions.md` row records the agent-run mint, with the dev-only route or form as the rejected alternative and the reason. `docs/02-architecture.md` › Test-only sign-in and clock names the dev mint beside e2e's.
- [ ] AC-6: On the branch, the ui-verifier runs against a dev server started from `ui.startCommand`, signs in with the mint, and reports `/teams` rendering the Teams list at phone width (390) with no `NOT RUN` for sign-in. The cookie value appears nowhere in its report.

## Out of scope

- Sign-in on Vercel previews (D-102).
- Any change to production sign-in.
- Moving the e2e fixture (`web/e2e/fixtures.ts`) onto the new script.

## Files likely touched

- `web/e2e/dev-session.mjs` (new) — the mint
- `web/lib/dev-session.test.ts` (new) — AC-2, AC-3
- `.claude/project/ui-verifier.md` — § Sign-in
- `docs/decisions.md` — the new decision
- `docs/02-architecture.md` — § Test-only sign-in and clock
- `.claude/kit.json` — `ui.auth` stays null (no change expected)

## Verification

- Automated: `pnpm --dir web exec vitest run lib/dev-session.test.ts`.
- Manual: AC-6. Start the dev server (`ui.startCommand` on a free port), delegate the ui-verifier with a one-line check ("`/teams` shows the Teams list"), and paste its verdict table in the PR. Also run `node web/e2e/dev-session.mjs https://example.com` → exit 1 with the loopback refusal.

## Follow-ups

_Work noticed during this task and deliberately left out. Each bullet ends `→ <path> § <section>` (where it was placed) or `→ not tracked: <reason>`. See `.claude/skills/track-follow-ups/classify.md`; the PR's Follow-ups section is copied from here._

## Plan

Approved 2026-10-13 at `e02e2dc`.

1. Test first: `web/lib/dev-session.test.ts` against an empty `web/e2e/dev-session.mjs` that exports stubs. Watch AC-2 and AC-3 fail.
2. `web/e2e/dev-session.mjs`, with pure exports for the test and a `main` that runs only when it is the entry script:
   - `loopbackOrigin(url)`: throws unless `http:` and host is `localhost`, `127.0.0.1` or `[::1]`.
   - `devSecrets(envText)`: `util.parseEnv` and pick the two variables, or throw naming the missing one (never its value).
   - `devSessionCookie({ url, secret, githubId, encode, now })`: `encode({ token: { sub, name: "Dev owner" }, secret, salt: "authjs.session-token", maxAge: 3600 })` from `next-auth/jwt`. This is the same shape as `web/e2e/fixtures.ts` and `scripts/perf/lib/perf.mjs` › `mintSession`.
   - `main`: reads `new URL("../../.env.local", import.meta.url)`, writes one JSON line to stdout, and on error writes `dev-session: <reason>` to stderr and exits 1.
3. Test cases: each refusal; a minted value decodes with `decode({ secret, salt })` and returns `null` under another secret; the stdout of a spawned run against a temp `.env.local` never contains the secret (spawn the module with its env-path seam pointed at a temp file). AC-3: walk the listed paths and grep for imports from `e2e/` or `../e2e`.
4. `.claude/project/ui-verifier.md` § Sign-in, replacing the NOT RUN paragraph:
   - Run `node web/e2e/dev-session.mjs <base URL>` and add the printed cookie with Playwright MCP `browser_run_code` (`await page.context().addCookies([cookie])`).
   - If that tool is missing, use `browser_evaluate` to set `document.cookie` on the base URL's origin. Auth.js reads the cookie on the server, so `httpOnly` doesn't matter there.
   - Then open `/teams` and confirm the URL isn't `/login`.
   - Plus the NOT RUN wording, the never-print rule, and why `ui.auth` stays null.
5. `docs/decisions.md`: a new row via `.claude/scripts/next-id.ps1`, alternatives as in Context.
6. `docs/02-architecture.md` › Test-only sign-in and clock: one bullet for the dev mint (loopback only, `.env.local` only, 1 hour).
7. AC-6 on the branch (Manual).

Files: `web/e2e/dev-session.mjs` (new), `web/lib/dev-session.test.ts` (new), `.claude/project/ui-verifier.md`, `docs/decisions.md`, `docs/02-architecture.md`.

Tests: AC-1 and AC-2 by `dev-session.test.ts` (pure functions plus one spawned run); AC-3 by the import scan in the same file; AC-4 and AC-5 by reading the diff; AC-6 manual, with the verifier's table in the PR.

Risks / open questions:
- The cookie value passes through the agent's tool calls, so it lands in the local session transcript. That is acceptable: the token is dev-only (the dev `AUTH_SECRET` can't open preview or production, D-012), loopback-only, and expires in an hour. It never goes into the report.
- `.env.local` must hold `AUTH_ALLOWED_GITHUB_ID` and a dev `AUTH_SECRET`. Worktrees get it through `worktreeCopyFiles`.
- Which Playwright MCP tool sets cookies depends on the `@playwright/mcp@latest` version. Step 4 documents both paths, and AC-6 proves the one that works.

Size check: S/M. Two new files and three doc edits; no app code.

## Review log

_Filled by /implement-task. One line per round._

## Blocked

_Only if status is Blocked: what failed, what was tried, best hypothesis, decision needed._

## Metrics

- Verify rounds:
- Review rounds:
- First-pass AC FAILs:
- Plan revisions after approval:
