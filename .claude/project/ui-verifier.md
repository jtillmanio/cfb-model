# ui-verifier: cfb-model

Project section for `.claude/agents/ui-verifier.md`. The kit never ships or overwrites this file.

## Sign-in

Every route except `/login` redirects to `/login` until you're signed in, and sign-in is GitHub-only (TASK-001), which you can't do. Sign in by minting a dev session instead (D-111), before any signed-in criterion:

1. Run `node web/e2e/dev-session.mjs <resolved base URL>` from the repo root. It prints one line, a Playwright cookie as JSON, valid 1 hour. It reads `.env.local` itself: don't open that file.
2. Add the cookie to the browser context with Playwright MCP's `browser_run_code`: `async (page) => { await page.context().addCookies([<the cookie JSON>]); }`. If that tool isn't available, open the base URL and use `browser_evaluate` to set `document.cookie = "authjs.session-token=<value>; path=/; max-age=3600; samesite=lax"`. `httpOnly` doesn't matter here, because Auth.js reads the cookie on the server.
3. Open `<base URL>/teams` and confirm the page stays there. If it redirects to `/login`, sign-in failed.

If the script exits non-zero (its stderr gives the reason), or step 3 lands on `/login`, verify only the `/login` states and report every signed-in criterion as `NOT RUN: dev sign-in failed (<reason>)`, not FAIL.

The cookie value is a credential. Never put it in your report, a screenshot name, or a URL, and never echo the script's output back in your summary; say "minted" instead. The mint refuses any URL that isn't `http:` on a loopback host, and the dev `AUTH_SECRET` can't open a preview or production (D-012).

`ui.auth` in `.claude/kit.json` stays null: the kit's `ui.auth` types a secret into a sign-in form, and this app has no such form. Adding one would put a way in inside `web/`, which `docs/02-architecture.md` › Test-only sign-in and clock forbids.

## Data

The dev server started by `ui.startCommand` reads the database in `.env.local` (development, never production). Use only data already there or data the steps create; never delete or bulk-edit rows, and never run ingest, seed or migrate commands.

## Design sources

- The `Pass … .dc.html` boards in `design/handoff/designs/` win over older boards; their board notes are the spec. The boards are 100–300 KB: Grep for the board or frame name, then Read with offset/limit (the `largeFiles` hint), never whole.
- `docs/05-ui-design-brief.md` loses to the design unless it notes an override. Numbers and what they mean follow `docs/04-model.md`.

## Reference screenshots

- `design/handoff/screenshots/` names them `NN-<screen>-<desktop|mobile|tablet>.png`: desktop = 1440, mobile = 390, tablet = 768. Only This Week has a tablet reference (`28-this-week-tablet.png`).
- Compare numbers and copy against a reference only when the server runs on the seeded test DB (the fixture reproduces them, `docs/02-architecture.md` › Testing strategy). Against dev data, ignore data values.
- The references show the default dark theme.
