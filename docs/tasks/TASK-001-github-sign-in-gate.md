---
id: TASK-001
title: Gate every page behind GitHub sign-in with an allowlist
status: Review
depends_on: []
size: M
model: opus
autonomy: attended
ui: true
plan_status: approved
planned_at_commit: 809e207
---

# TASK-001 — Gate every page behind GitHub sign-in with an allowlist

## Goal

Only the owner's GitHub account can open the app: a signed-out visitor, a stale or forged session, or any other GitHub account lands on `/login` instead of seeing data, and the owner stays signed in on a device for 90 days.

## Context

- Task list: `docs/08-tasklist.md` › M1 › M1.1 (first half; the login screen's designed states are TASK-002).
- Features: `docs/01-product.md` › Feature acceptance › **F-42 Sign-in**, items 1–2. Item 3 (waking) and the designed copy are TASK-002.
- Architecture: `docs/02-architecture.md` › Auth (single user, done properly); › Testing strategy › Test-only sign-in and clock (the session-mint helper lives in the Playwright fixtures, never in `web/` source); › Testing strategy › End-to-end journeys #1; › Non-functional requirements › Security (90-day session).
- Rules: `.claude/rules/web.md` (`proxy.ts` replaces `middleware.ts` and runs on Node; a stale or invalid session redirects to `/login`, never a 500; read `node_modules/next/dist/docs/` before Next-specific code).
- Decisions: D-012 (Auth.js, GitHub OAuth, one allowlisted ID), D-102 (no GitHub sign-in on previews), D-078 (GitHub only, no password), D-095 (90-day session), D-100 (`/api/py/*` is routed to the API service before Next on Vercel), D-090 (e2e mints a session cookie).
- Design: S-15, `design/handoff/designs/Pass A - Decisions.dc.html` A1a (desktop) and A1d (mobile) default frames. This task ships a minimal `/login` with the one "Sign in with GitHub" button; TASK-002 draws the rest.
- **Size:** 10+ files, but most are one-line wiring (`package.json`, `.env.example`, Playwright and CI env). It can't split further: once the gate lands, the existing `/teams` e2e needs the minted session in the same PR or CI goes red.
- **Variables (settled; documented in `.env.example`):** `AUTH_SECRET`, `AUTH_GITHUB_ID`, `AUTH_GITHUB_SECRET` (Auth.js's default names) and `AUTH_ALLOWED_GITHUB_ID`, the numeric GitHub user ID, not the username (usernames can be renamed).
- **Previews have no GitHub sign-in (D-102).** Only minted sessions reach them (TASK-007, TASK-008). Previews set `AUTH_SECRET` and `AUTH_ALLOWED_GITHUB_ID` but no GitHub client ID or secret, so the Auth.js config must still load without them: signed out, a preview's `/login` renders instead of throwing. TASK-002 draws what it says there.
- **Owner setup:** done 2026-10-09 for production: the "CFB Model" OAuth app with the production callback only, and its values in Vercel Production. Done 2026-10-09 for previews: `AUTH_SECRET` (which must differ from production's, 02 › Auth) and `AUTH_ALLOWED_GITHUB_ID` in Vercel Preview. Still to do: the "CFB Model (dev)" app (callback `http://localhost:3000/api/auth/callback/github`) and its values in `.env.local`. Claude never edits secrets.

## Acceptance criteria

- [x] AC-1: Given no session cookie, when the browser requests `/` or `/teams`, then it ends on `/login` (HTTP redirect, not a 500), and `/login` shows a "Sign in with GitHub" button.
- [x] AC-2: Given a session cookie whose value is garbage, signed with a different `AUTH_SECRET`, or expired, when the browser requests `/teams`, then it ends on `/login` and no response in the chain has status 500 (e2e, one case each).
- [x] AC-3: The sign-in check admits only the allowlisted GitHub user ID: a profile with that ID is allowed; any other ID is refused and sent to `/login` with an error the login page can read; when the allowlist env var is unset or empty, every account is refused (fail closed). Covered by a Vitest test on the allowlist check.
- [x] AC-4: The session lasts 90 days: the Auth.js config's session max age is `90 × 24 × 60 × 60` seconds (Vitest), and the session cookie minted in e2e carries an expiry about 90 days out.
- [x] AC-5: Given a session cookie minted by the Playwright fixture with the test `AUTH_SECRET`, `/teams` shows the seeded "Ohio State · Big Ten" row as before; signed out, `GET /api/py/health` still returns 200 JSON with `db_reachable: true` (no redirect).
- [x] AC-6: The session-mint helper lives under `web/e2e/`, and no file under `web/` outside `web/e2e/` imports it or calls Auth.js's JWT `encode` (checked by `rg` in review).

## Out of scope

- The designed login layout, the denied-account copy, "Use a different account" and the waking state (TASK-002).
- The API's JWT check and signing API calls from Next (TASK-003, TASK-004).
- Sign out and Settings › Account (M8.8).
- The Lighthouse workflow's session minting (TASK-007).
- Vercel Deployment Protection and its bypass header.

## Files likely touched

- `web/auth.ts` — Auth.js config: GitHub provider, allowlist `signIn` callback, 90-day session, `pages.signIn`/`pages.error` → `/login` (new).
- `web/proxy.ts` — redirect signed-out and invalid sessions to `/login`; matcher skips `/login`, `/api/auth/*`, `/api/py/*`, `_next` and static files (new).
- `web/app/api/auth/[...nextauth]/route.ts` — Auth.js route handlers (new).
- `web/app/login/page.tsx` — minimal page with the sign-in button (new; TASK-002 finishes it).
- `web/lib/allowlist.ts`, `web/lib/allowlist.test.ts` — the pure allowlist check and its tests (new).
- `web/e2e/fixtures.ts` — test that mints an Auth.js session cookie with the test `AUTH_SECRET` (new).
- `web/e2e/auth.spec.ts` — AC-1, AC-2, AC-5 (new); `web/e2e/teams.spec.ts` — use the signed-in fixture.
- `web/playwright.config.ts`, `.github/workflows/ci.yml` — test `AUTH_SECRET` (a non-secret test value) for `next start`.
- `web/package.json` — Auth.js dependency (lockfile via pnpm).
- `.env.example` — the new variables, with comments.

## Verification

- Automated: `web/lib/allowlist.test.ts` (allowed ID, other ID, unset and empty allowlist); a Vitest case for the 90-day max age; `web/e2e/auth.spec.ts` (signed-out redirects for `/` and `/teams`; garbage, wrong-secret and expired cookies → `/login`; health open while signed out); `web/e2e/teams.spec.ts` passing with the minted session. All at 390 and 1440.
- Manual: on the PR preview (or locally with a dev OAuth app), sign in with the allowlisted account → lands on `/` (currently Teams). Sign in with another GitHub account → back on `/login` with an error parameter, no data shown.

## Plan

Approved 2026-10-09.

**Steps**
1. `web/package.json`: add `next-auth@5.0.0-beta.32`, pinned exactly (Auth.js v5 is still beta; 4.x is the Pages-era API; its peer range includes Next 16).
2. `web/lib/allowlist.ts`: a pure `isAllowedGitHubId(id, allowed)` that fails closed when the allowlist is unset or empty. Vitest first.
3. `web/auth.config.ts`: GitHub provider; a `signIn` callback using the allowlist (refusal → `/login?error=AccessDenied`); `session.maxAge` 90 days; `pages.signIn`/`pages.error` → `/login`. `web/auth.ts` exports `NextAuth(authConfig)`; `web/app/api/auth/[...nextauth]/route.ts` mounts the handlers.
4. `web/proxy.ts`: `auth()`-wrapped; no valid session, or a session whose `sub` isn't the allowlisted ID → 307 to `/login`. The matcher skips `/login`, `/api/auth`, `/api/py`, `_next` and files with an extension.
5. `web/app/login/page.tsx`: minimal token-styled page with one "Sign in with GitHub" button (a server-action form calling `signIn("github", { redirectTo: "/" })`). It is static and doesn't read the GitHub variables, so previews render it without them.
6. `web/e2e/test-env.ts` (test secret and allowlisted ID), `web/e2e/fixtures.ts` (mints the cookie with `encode` from `next-auth/jwt`; a `signedIn` fixture), and `web/playwright.config.ts` (passes `AUTH_SECRET`, `AUTH_ALLOWED_GITHUB_ID`, `AUTH_TRUST_HOST=true` to `next start`; readiness URL `/login`). `ci.yml` needs no change. *Revised after approval:* no dummy GitHub client ID or secret after all, so e2e proves `/login` renders without them, as on a preview (D-102). This settles the first risk below.
7. `web/e2e/auth.spec.ts` (new); `web/e2e/teams.spec.ts` moves onto the signed-in fixture, and its health test moves into the signed-out spec.
8. `web/next.config.ts`: load the repo root's `.env.local` with `process.loadEnvFile`, which never overrides variables already set. Today Next reads only `web/.env*`, so local sign-in can't see `AUTH_*` without it.
9. `.env.example` (drop "nothing reads these yet") and a new decision, D-103: Auth.js v5 beta pinned exactly, and the allowlist re-checked on every request.

**Files outside "Files likely touched":** `web/auth.config.ts` (keeps the config testable without `NextAuth()`), `web/lib/auth-config.test.ts`, `web/e2e/test-env.ts`, `web/next.config.ts`, `docs/decisions.md`. Size: about 17 files; kept whole per Context › Size.

**Test strategy**
- AC-1: `auth.spec` "signed out, / and /teams redirect to /login" (also checks the button).
- AC-2: `auth.spec`, one test each for a garbage, wrong-secret and expired cookie. Each records every response status and asserts that none is 500.
- AC-3: `lib/allowlist.test.ts` (allowed, other, unset, empty, numeric versus string ID) and `lib/auth-config.test.ts` (the `signIn` callback refuses other IDs; `pages.error` is `/login`).
- AC-4: `lib/auth-config.test.ts` (`maxAge === 7_776_000`). `auth.spec` mints a cookie that expires in 1 hour, visits `/teams`, and asserts that the cookie Auth.js re-issues expires about 90 days out. If the proxy doesn't re-issue it, fall back to the fixture's own expiry and say so.
- AC-5: `teams.spec` on the signed-in fixture; `auth.spec` checks that signed-out health returns 200 JSON with `maxRedirects: 0`.
- AC-6: an `rg` check in review.

**Risks**
- Previews have no GitHub variables: confirm that Auth.js doesn't fail its config check during session checks when the GitHub provider has no client ID. If it does, add the provider only when `AUTH_GITHUB_ID` is set.
- The proxy is the only check for now; TASK-003 adds a server-side session check in `lib/api.ts`.

## Review log

Verify R1 PASS | Audit R1 PASS (every AC-1..AC-5 proven against base; headline read "CHANGES REQUIRED" but listed no required change) | Spec R1 CHANGES (PLAN GAP: dummy GitHub variables dropped without updating the plan) → R2 APPROVE | UI R1 PASS (390, 768, 1440)

## Blocked

_Only if status is Blocked: what failed, what was tried, best hypothesis, decision needed._

## Metrics

- Verify rounds: 1
- Review rounds: 2
- First-pass AC FAILs: 0
- Plan revisions after approval: 1 (step 6: no dummy GitHub variables in e2e)
