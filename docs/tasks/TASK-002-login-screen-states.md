---
id: TASK-002
title: Draw the login screen with its denied and waking states
status: Done
depends_on: [TASK-001]
size: M
model: sonnet
autonomy: attended
ui: true
plan_status: approved
planned_at_commit: 75a35fa
---

# TASK-002 — Draw the login screen with its denied and waking states

## Goal

The login screen matches the design at phone and desktop widths: a refused GitHub account is told why and offered another try, and on a cold database the owner sees "Waking up the database…" with a reason instead of a blank wait.

## Context

- Task list: `docs/08-tasklist.md` › M1 › M1.1 (second half; the gate itself is TASK-001).
- Features: `docs/01-product.md` › Feature acceptance › **F-42 Sign-in**, items 1 and 3.
- Screen: S-15 in `docs/05-ui-design-brief.md` › Screen inventory (from handoff). Design: `design/handoff/designs/App States Desktop.dc.html` and `App States Mobile.dc.html` (`frame="login"`, `loginState` default / waking / denied); `Pass A - Decisions.dc.html` A1a–c (desktop) and A1d–f (mobile), which win over older boards (D-094). Reference screenshots: `design/handoff/screenshots/22-login-desktop.png`, `23-login-mobile.png`.
- Design copy (read from the frames): wordmark "CFB Model"; heading "Sign in"; "Private app · one GitHub account"; button "Sign in with GitHub"; footnote "Stays signed in on this device for 90 days."; denied: "This GitHub account isn't allowed", "You're signed in to GitHub as <login>. Only the one allowlisted account can use this app.", "Use a different account"; waking: "Waking up the database…" with "GitHub said yes. The first request after a quiet spell can take a few seconds." (no number, D-097).
- Architecture: `docs/02-architecture.md` › Non-functional requirements › Cold start (note after 1.5 s; server-side API call times out at 10 s). Hard rule 5: the browser never calls the API, so the waking state must be driven from server code, not by the browser polling `/api/py/health`.
- Decisions: D-078 (GitHub only), D-102 (no GitHub sign-in on previews), D-072 (wake note after 1.5 s), D-097 (copy without a number), D-059 (dark default), D-066 (44 px touch targets).
- **Decide at the plan gate:** how the waking state is produced server-side after GitHub returns (e.g. a post-sign-in route that streams the waking card while it waits for the database, then redirects), how the denied account's GitHub login reaches the page, and what "Use a different account" does (GitHub's account picker, if the OAuth app supports `prompt=select_account`, or a GitHub sign-out link).

## Acceptance criteria

- [x] AC-1: Signed out, at 390 and 1440 px, `/login` shows the wordmark, "Sign in", "Private app · one GitHub account", exactly one button named "Sign in with GitHub", and "Stays signed in on this device for 90 days."; at 390 the button is ≥ 44 px tall and the page has no horizontal scroll.
- [x] AC-2: Given the denied redirect from TASK-001 for GitHub user `someone-else`, `/login` shows "This GitHub account isn't allowed" and "You're signed in to GitHub as someone-else", plus a "Use a different account" control that is a real link or button with that accessible name.
- [x] AC-3: Given the allowlisted account has just signed in and the database hasn't answered within 1.5 s, the login card shows "Waking up the database…" and "GitHub said yes. The first request after a quiet spell can take a few seconds."; once it answers, the browser lands on the page it asked for (or `/`). With the database awake, the waking state never shows.
- [x] AC-4: Given a deployment with no GitHub client ID configured (every Vercel preview, D-102), `/login` shows the same card with "Sign-in isn't available on preview deployments." in place of the button and footnote, renders no "Sign in with GitHub" button, and returns 200, not 500. This copy isn't in the design; it uses the card's existing text styles.
- [x] AC-5: The login page uses only design tokens (hard rule 7): no hex, `rgb(` or `oklch(` literals and no arbitrary pixel font sizes in the new files (checked in review), and the spinner stops under `prefers-reduced-motion`.

## Out of scope

- Light mode (Pass D, D15): theme switching arrives with Settings (M8.8).
- The app shell, sidebar and This Week (M5.3, M5.6); after sign-in the app still lands on `/` (currently Teams).
- Changing the auth gate, allowlist or session length (TASK-001).
- The Lighthouse route and budget for `/login` (TASK-008 adds both).

## Files likely touched

- `web/app/login/page.tsx` — the designed card and its three states.
- `web/app/login/login-card.tsx` — the card component shared by the states (new).
- `web/app/login/continue/page.tsx` — post-sign-in step that shows the waking state while the database wakes (new; exact route decided at the plan gate).
- `web/lib/login.ts`, `web/lib/login.test.ts` — pure mapping from the URL's search params to the login state and its copy (new).
- `web/auth.ts` — pass the denied account's login and the post-sign-in redirect to the page.
- `web/e2e/login.spec.ts` — AC-1 and AC-2 at both widths (new).

## Verification

- Automated: `web/lib/login.test.ts` (default, denied with a login name, unknown error falls back to default, no GitHub client ID → unavailable); `web/e2e/login.spec.ts` (AC-1 and AC-2 at 390 and 1440). The waking state's timing is covered by whatever test the plan picks for its server-side mechanism (e.g. a test-only slow-health switch honored only when `APP_ENV=test`).
- Manual: compare `/login` at 1440 and 390 with `22-login-desktop.png` and `23-login-mobile.png` → same layout and copy. Let the dev database idle more than 5 minutes, then sign in → the waking state shows, then the app opens.

## Plan

Approved 2026-10-10 as one task (size check: 11 files, 5 of them tests or e2e setup; split into card/denied/preview and waking was offered and declined).

Decisions at the plan gate:
- **Waking state:** sign-in's `redirectTo` is `/login/continue?to=<path>` (behind the gate). That page races the server-side health call against 1.5 s. Health first: plain `redirect(to)` (a 307, nothing drawn). Timer first: the waking card streams, and a Suspense child awaits the same call, then `redirect(to)` (Next's streamed redirect). No browser polling (hard rule 5). Health failing or timing out at 10 s still redirects; the target page shows its own error.
- **Denied login name:** the `signIn` callback returns `/login?error=AccessDenied&login=<github login>` instead of `false`; the page shows the name only if it is a valid GitHub login (`[A-Za-z0-9-]{1,39}`), else omits that sentence.
- **Use a different account:** a button that re-runs `signIn("github", …, { prompt: "select_account" })` (GitHub's account picker).
- **Return path:** Auth.js's `callbackUrl` is reduced to a same-origin path; `//…`, `/\…`, and `/login…` fall back to `/`.
- **Footnote:** "Stays signed in on this device for 90 days." at both widths (AC-1; the mobile board's "phone" is not used).

Steps:
1. `web/lib/login.ts` + `login.test.ts`: `loginState(params, githubConfigured)` (default / denied / unavailable, with copy), `safeNextPath`, `raceWakeNote(promise, ms)`.
2. `web/auth.config.ts` + `web/lib/auth-config.test.ts`: refused GitHub sign-in returns the denied URL with the login.
3. `web/lib/api.ts`: `getHealth()`.
4. `web/app/login/login-card.tsx` (new), `web/app/login/page.tsx`, `web/app/login/continue/page.tsx` (new): card per the App States boards, inline SVG icons, `motion-safe:animate-spin`.
5. `web/playwright.config.ts`: main server gets a dummy GitHub client ID (dev/production behaviour); a second `next start` on :3101 with the preview config (no GitHub client, D-102) whose API_URL points at `web/e2e/cold-api.mjs` (new, test-only proxy that answers every request 3 s late).
6. `docs/decisions.md`: one row for the waking mechanism.

Test strategy:
- AC-1: `web/e2e/login.spec.ts` "default card" at phone and desktop (copy, one button, ≥ 44 px at phone, no horizontal scroll).
- AC-2: `auth-config.test.ts` (denied URL carries the login); `login.spec.ts` "denied" (copy and the "Use a different account" button by role).
- AC-3: `login.spec.ts` "database awake" (lands on /teams, no waking copy) and "database waking" (:3101 via the cold proxy: waking copy, then /teams); `login.test.ts` `raceWakeNote` with fake timers.
- AC-4: `login.spec.ts` "preview" on :3101 (200, unavailable copy, no sign-in button); `login.test.ts` unavailable state.
- AC-5: `login.spec.ts` reduced motion (spinner animation-name `none`); token use checked in review.

Risks: Next's streamed `redirect()` after the waking card has flushed is unproven here; the cold-API e2e proves it, and if it fails, stop and ask.

Revision 1 (2026-10-10, approved): with `cacheComponents`, Next commits a 200 before the 1.5 s race settles, so the awake path is a client-side redirect with nothing drawn, not a 307. The "database awake" e2e asserts the browser lands on /teams and the response never contains the waking copy, instead of a 307. Recorded in D-104.

## Review log

Verify R1 PASS | Audit R1 CHANGES (AC-5 token use review-only; signed-out gate test non-discriminating) → R2 PASS | Spec R1 APPROVE | UI R1 PASS (AC-1, AC-2 at 390 / 768 / 1440; AC-3–5 proven by e2e)

## Blocked

_Only if status is Blocked: what failed, what was tried, best hypothesis, decision needed._

## Metrics

- Verify rounds: 1
- Review rounds: 1
- First-pass AC FAILs: 0
- Plan revisions after approval: 1
