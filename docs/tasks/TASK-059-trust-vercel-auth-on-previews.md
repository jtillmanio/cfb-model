---
id: TASK-059
title: Open previews to the owner through Vercel Authentication
status: In progress
depends_on: []
size: M
model: opus
autonomy: attended
ui: false
plan_status: approved
planned_at_commit: 80e65d8
---

# TASK-059 — Open previews to the owner through Vercel Authentication

## Goal

Opening any PR's Vercel preview, on desktop or phone, shows the app signed in as the owner, with no GitHub sign-in. Production and dev still need GitHub sign-in exactly as now.

## Context

- **Asked for by the owner on 2026-11-03.** Previews have no sign-in (D-102), so branches can't be tested on them.
- **Options considered (2026-11-03):**
  - An Auth.js redirect proxy behind a long-lived `auth-proxy` branch (built as PR #131, closed unmerged).
  - Production as the proxy (needs production's `AUTH_SECRET` on previews; breaks D-012).
  - A separate Vercel project as the proxy.
  - A custom domain with Vercel's Preview Deployment Suffix (Pro plan).
  - A hand-minted cookie (desktop only).
- **The owner chose to trust Vercel Authentication on previews.** Previews already sit behind Vercel Deployment Protection (02 › Auth), so only the owner's Vercel account can open one. On a preview, the app treats every request as the allowlisted user.
- **What "a preview" means here:** `process.env.VERCEL_ENV === "preview"`, read on each request. Vercel sets it, and a request can't change it. `web/app/design-system/page.tsx` already reads it the same way. Locally, in CI and in e2e it is unset unless a test sets it.
- **What this costs, accepted by the owner:**
  - App code gains a gate bypass.
  - A branch that changes sign-in itself can't be tested on its preview.
  - If Deployment Protection is ever turned off, previews are open to anyone with the URL.
  - This doesn't weaken anything that exists today: the Lighthouse job can already mint preview sessions (D-101), and Vercel's login already decides who reaches a preview.
- **Where the gate and the user ID live today:**
  - `web/proxy.ts` exports Auth.js's `auth` as the proxy, and the `authorized` callback in `web/auth.config.ts` re-checks the allowlist on every page request.
  - `signedGet` in `web/lib/api.ts` reads `auth()`'s `user.id` for the API JWT's `sub` (D-105) and throws without a session.
  - On a preview both must fall back to `AUTH_ALLOWED_GITHUB_ID`. If that is unset or empty, the gate stays shut (redirect to `/login`, as `isAllowedGitHubId` does today).
- **Guard against a mistake on production.** The release smoke test (`smoke_check` in `python/db/src/db/release.py`) checks health and that an unsigned API call gets 401. It should also check that a signed-out GET of production's `/` is redirected to `/login`. Then a production build that wrongly treats itself as a preview fails the release.
- **Unchanged:**
  - `/login`: the gate never sends a preview there.
  - The Lighthouse preview run's minted cookie, which still works since a session is still accepted.
  - The dev mint (D-111).
  - The API, which checks only the JWT.
- **Open question for the plan:** what the e2e proof runs on. Candidates: a third `next start` with `VERCEL_ENV=preview`, or the existing cold preview server on :3101 (`web/playwright.config.ts`), which TASK-002's specs also use.
- Architecture: `docs/02-architecture.md` § Auth (single user, done properly). Its last bullet states D-102 and changes here.
- Decisions: D-102 (superseded by a new row), D-012, D-101, D-105, D-107 (the smoke test's unsigned-call check), D-111.

## Acceptance criteria

- [ ] AC-1: Given `VERCEL_ENV=preview`, `AUTH_ALLOWED_GITHUB_ID` set and no session cookie, a request for `/teams` is not redirected. The page renders the seeded "Ohio State · Big Ten" row, and the API call it makes carries a JWT whose `sub` is `AUTH_ALLOWED_GITHUB_ID` (e2e at 390 and 1440 for the page; Vitest for the `sub`).
- [ ] AC-2: Given `VERCEL_ENV=preview` and `AUTH_ALLOWED_GITHUB_ID` unset or empty, a signed-out request for `/teams` is redirected to `/login`, the same as today (Vitest on the gate decision).
- [ ] AC-3: Given `VERCEL_ENV` unset, `development` or `production`, nothing changes: signed-out `/` and `/teams` go to `/login`, and garbage, wrong-secret and expired cookies go to `/login`. Vitest covers each value; the existing `web/e2e/auth.spec.ts` and `web/e2e/login.spec.ts` pass unchanged.
- [ ] AC-4: The release smoke test fails when production's signed-out `/` isn't a redirect to `/login`: `smoke_check` returns a failure line naming the status it got. It passes on a redirect whose `Location` path is `/login` (pytest, both cases).
- [ ] AC-5: The docs match:
  - a new decision row supersedes D-102, with the options considered and the accepted costs;
  - `docs/02-architecture.md` § Auth's last bullet says previews trust Vercel Authentication and production keeps GitHub sign-in;
  - the comments citing D-102 in `web/auth.config.ts`, `web/lib/login.ts` and `web/app/login/page.tsx` are updated;
  - `docs/owner-checklist.md` § Actions has an item to confirm Vercel › Settings › Deployment Protection has Vercel Authentication on for all preview deployments (Standard Protection).
- [ ] AC-6 (owner, after the PR's preview is up): opening the PR's preview signed out of the app (a private window, signed in to Vercel) shows `/teams` with data, on desktop and on a phone. Production's `/` in a private window still lands on `/login`.

## Out of scope

- Any redirect proxy, extra OAuth app, or long-lived branch (the closed PR #131's approach).
- Changing `/login` or its "Sign-in isn't available on preview deployments." copy.
- Turning on or changing Deployment Protection settings (owner checklist item only).
- Bypassing the gate anywhere but Vercel previews: no dev or test switch beyond `VERCEL_ENV` itself.

## Files likely touched

- `web/auth.config.ts`: the `authorized` callback's preview case.
- `web/lib/allowlist.ts` or a new `web/lib/preview.ts`, with its `*.test.ts`: the "is this a preview" decision and the fallback user ID.
- `web/lib/api.ts`: `signedGet`'s user ID on a preview.
- `web/lib/auth-config.test.ts`: AC-2 and AC-3's Vitest cases.
- `web/playwright.config.ts` and a spec in `web/e2e/`: AC-1's preview server and spec.
- `web/lib/login.ts` and `web/app/login/page.tsx`: comments only.
- `python/db/src/db/release.py` and `python/db/tests/test_release.py`: AC-4.
- `docs/02-architecture.md` § Auth, `docs/decisions.md`, `docs/owner-checklist.md`.

## Verification

- Automated:
  - Vitest (AC-1's `sub`, AC-2, AC-3) and pytest (AC-4), each failing on the old code first.
  - The new e2e spec (AC-1) at 390 and 1440.
  - `web/e2e/auth.spec.ts` and `login.spec.ts`, unchanged.
- Manual (owner, AC-6):
  1. Confirm the Deployment Protection checklist item.
  2. Open the PR's preview in a private window → Vercel's login, then `/teams` with data, no app sign-in.
  3. Repeat on a phone.
  4. Production `/` in a private window → `/login`.

## Follow-ups

_Work noticed during this task and deliberately left out. Each bullet ends `→ <path> § <section>` (where it was placed) or `→ not tracked: <reason>`. See `.claude/skills/track-follow-ups/classify.md`; the PR's Follow-ups section is copied from here._

- README › Performance checks › Read a failed run: the `ended on /login` row's "On a preview" cause is stale. A preview now lets every request in, so ending on `/login` there means Vercel Preview's `AUTH_ALLOWED_GITHUB_ID` is unset or blank (found in Phase 2; small, in scope)

## Plan

Approved by the owner 2026-11-03.

**Steps:**

1. Failing tests first: `web/lib/preview.test.ts`; `web/lib/auth-config.test.ts` (AC-2, AC-3: `VERCEL_ENV` unset, `development`, `production`; preview with the ID unset or empty); `web/lib/api-token.test.ts` (AC-1's `sub`: preview, no session → `sub` is `AUTH_ALLOWED_GITHUB_ID`); `python/db/tests/test_release.py` (AC-4).
2. `web/lib/preview.ts`: `previewUserId()` returns the trimmed `AUTH_ALLOWED_GITHUB_ID` only when `VERCEL_ENV === "preview"`, else `null` (also `null` for an unset, empty or blank ID). The `authorized` callback in `web/auth.config.ts` returns true when it is set; otherwise the allowlist check as today.
3. `web/lib/api.ts`: `signedGet` uses `previewUserId() ?? (await auth())?.user?.id`; on a preview every request is the allowlisted user.
4. E2E on the existing cold preview (:3101): add `VERCEL_ENV: "preview"` to its env in `web/playwright.config.ts` (it is already the one set up like a Vercel preview; TASK-002's waking specs still mint a cookie, still accepted; `/login` isn't gated). New `web/e2e/preview.spec.ts`: signed out, a `maxRedirects: 0` GET of `/teams` is not a redirect, and the page shows the "Ohio State · Big Ten" row at 390 and 1440.
5. `python/db/src/db/release.py`: `fetch_root(url)` (no redirect following) returns status and `Location`; `smoke_check` takes `root_status` and `root_location` and fails with a line naming the status (and Location) unless it is a 30x whose Location path is `/login`; `smoke()` passes them.
6. Docs: a new decision row superseding D-102 (options considered, accepted costs; keeps the two OAuth apps and "no GitHub client on previews"); `docs/02-architecture.md` § Auth's last bullet; D-102 comments repointed; `docs/owner-checklist.md` § Actions item for Deployment Protection.

**Files:** `web/lib/preview.ts` and `preview.test.ts` (new), `web/auth.config.ts`, `web/lib/api.ts`, `web/lib/auth-config.test.ts`, `web/lib/api-token.test.ts` (not in likely-touched: AC-1's `sub`), `web/playwright.config.ts`, `web/e2e/preview.spec.ts` (new), `web/e2e/test-env.ts` (comment; not in likely-touched), `web/lib/login.ts`, `web/app/login/page.tsx`, `web/app/login/login-card.tsx` (D-102 comment; not in likely-touched), `web/lib/login.test.ts` (D-102 in a test name; not in likely-touched), `python/db/src/db/release.py`, `python/db/tests/test_release.py`, `docs/02-architecture.md`, `docs/decisions.md`, `docs/owner-checklist.md`.

**Test strategy:** AC-1 `web/e2e/preview.spec.ts` (page) + `web/lib/api-token.test.ts` (`sub`); AC-2/AC-3 `web/lib/auth-config.test.ts` (+ `preview.test.ts`), `auth.spec.ts`/`login.spec.ts` unchanged; AC-4 `test_release.py` (307 → `/login` passes; 200 and a redirect elsewhere fail naming the status); AC-5 spec-reviewer; AC-6 owner.

**Risks:** with `cacheComponents` an unredirected page answers 200 and streams, so the spec asserts "not 30x". Garbage, wrong-secret and expired cookies reach `authorized` as `auth: null`; the existing e2e covers the real cookies.

## Review log

_Filled by /implement-task. One line per round._

## Blocked

_Only if status is Blocked: what failed, what was tried, best hypothesis, decision needed._

## Metrics

- Verify rounds:
- Review rounds:
- First-pass AC FAILs:
- Plan revisions after approval:
