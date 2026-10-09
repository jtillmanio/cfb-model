---
id: TASK-002
title: Draw the login screen with its denied and waking states
status: Ready
depends_on: [TASK-001]
size: M
model: sonnet
autonomy: attended
ui: true
plan_status: none
planned_at_commit:
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
- Decisions: D-078 (GitHub only), D-072 (wake note after 1.5 s), D-097 (copy without a number), D-059 (dark default), D-066 (44 px touch targets).
- **Decide at the plan gate:** how the waking state is produced server-side after GitHub returns (e.g. a post-sign-in route that streams the waking card while it waits for the database, then redirects), how the denied account's GitHub login reaches the page, and what "Use a different account" does (GitHub's account picker, if the OAuth app supports `prompt=select_account`, or a GitHub sign-out link).

## Acceptance criteria

- [ ] AC-1: Signed out, at 390 and 1440 px, `/login` shows the wordmark, "Sign in", "Private app · one GitHub account", exactly one button named "Sign in with GitHub", and "Stays signed in on this device for 90 days."; at 390 the button is ≥ 44 px tall and the page has no horizontal scroll.
- [ ] AC-2: Given the denied redirect from TASK-001 for GitHub user `someone-else`, `/login` shows "This GitHub account isn't allowed" and "You're signed in to GitHub as someone-else", plus a "Use a different account" control that is a real link or button with that accessible name.
- [ ] AC-3: Given the allowlisted account has just signed in and the database hasn't answered within 1.5 s, the login card shows "Waking up the database…" and "GitHub said yes. The first request after a quiet spell can take a few seconds."; once it answers, the browser lands on the page it asked for (or `/`). With the database awake, the waking state never shows.
- [ ] AC-4: The login page uses only design tokens (hard rule 7): no hex, `rgb(` or `oklch(` literals and no arbitrary pixel font sizes in the new files (checked in review), and the spinner stops under `prefers-reduced-motion`.

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

- Automated: `web/lib/login.test.ts` (default, denied with a login name, unknown error falls back to default); `web/e2e/login.spec.ts` (AC-1 and AC-2 at 390 and 1440). The waking state's timing is covered by whatever test the plan picks for its server-side mechanism (e.g. a test-only slow-health switch honored only when `APP_ENV=test`).
- Manual: compare `/login` at 1440 and 390 with `22-login-desktop.png` and `23-login-mobile.png` → same layout and copy. Let the dev database idle more than 5 minutes, then sign in → the waking state shows, then the app opens.

## Plan

_Written by /plan-batch or /implement-task Phase 1. Approved by the user (plan_status: approved) before any code is written._

## Review log

_Filled by /implement-task. One line per round._

## Blocked

_Only if status is Blocked: what failed, what was tried, best hypothesis, decision needed._

## Metrics

- Verify rounds:
- Review rounds:
- First-pass AC FAILs:
- Plan revisions after approval:
