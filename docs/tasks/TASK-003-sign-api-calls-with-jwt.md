---
id: TASK-003
title: Sign every API call from Next server code with a short-lived JWT
status: In progress
depends_on: [TASK-001]
size: M
model: opus
autonomy: attended
ui: false
plan_status: approved
planned_at_commit: 49afe9d
---

# TASK-003 — Sign every API call from Next server code with a short-lived JWT

## Goal

Every request the web app's server code makes to the API carries a short-lived token proving it came from the signed-in owner, so the API can start refusing everyone else (TASK-004).

## Context

- Task list: `docs/08-tasklist.md` › M1 › M1.2 (first half; the API's check is TASK-004). Split so each PR leaves CI green: the API ignores the header until TASK-004 enforces it.
- Architecture: `docs/02-architecture.md` › Auth (short-lived JWT signed with a shared secret; the API verifies it on every request except health); › Components › 3. `web/` (server components call the API; the browser never does).
- Rules: `.claude/rules/web.md` (the browser never calls FastAPI; server components call it with the signed JWT; one API call per page). Hard rule 5.
- Decisions: D-012, D-010 (BFF, one call per page), D-097 (10 s timeout stays).
- Existing code: `web/lib/api.ts` (`server-only` fetch helper with the 10 s timeout) is the one place every call goes through.
- **Decide at the plan gate:** the shared-secret env var's name (distinct from `AUTH_SECRET`, so the browser-session key and the service key can rotate separately), the token lifetime (≤ 5 minutes), the claims (`sub` = the session's GitHub user ID, `iat`, `exp`, and an `aud`/`iss` pair the API checks), and the signing library (`jose` or Auth.js's own).
- **Owner prerequisite:** set the shared secret in Vercel for preview and production (the API service reads the same variable). Claude never edits secrets.

## Acceptance criteria

- [ ] AC-1: Given a signed-in session, when `web/lib/api.ts` calls the API, the request carries `Authorization: Bearer <token>`, where the token is an HS256 JWT that verifies with the shared secret and has `sub` equal to the session's GitHub user ID (Vitest with the fetch call captured).
- [ ] AC-2: The token's `exp − iat` is at most 300 seconds, and a fresh token is minted for each request rather than cached across requests (Vitest: two calls produce two tokens with their own `iat`).
- [ ] AC-3: Given no session (or the shared secret unset), `web/lib/api.ts` throws before sending any request, and the thrown error message doesn't contain the secret (Vitest).
- [ ] AC-4: The signing code imports `server-only`, and `next build` fails if a client component imports it (the existing `server-only` guard; checked by review of the import chain).
- [ ] AC-5: `/teams` still renders the seeded "Ohio State · Big Ten" row in e2e with the minted session, with the shared secret set for both the web and API processes in `web/playwright.config.ts` and `.github/workflows/ci.yml`.

## Out of scope

- Verifying the token in FastAPI and rejecting requests without it (TASK-004).
- The generated OpenAPI client (M5.4).
- Changing the page-level session check in `proxy.ts` (TASK-001).

## Files likely touched

- `web/lib/api.ts` — attach the token to every call.
- `web/lib/api-token.ts`, `web/lib/api-token.test.ts` — mint the JWT from the session (new).
- `web/package.json` — JWT library, if not Auth.js's own (lockfile via pnpm).
- `web/playwright.config.ts` — the shared secret for both web servers.
- `.github/workflows/ci.yml` — a test value for the shared secret.
- `.env.example` — the new variable, with a comment.

## Verification

- Automated: `web/lib/api-token.test.ts` (AC-1 to AC-3); the existing `web/e2e/teams.spec.ts` (AC-5).
- Manual: run `pnpm dev`, sign in, open `/teams`, and log the API's request headers → each request has a Bearer token whose decoded payload shows the owner's GitHub ID and an `exp` a few minutes out.

## Plan

Approved 2026-10-10.

**Plan-gate decisions (D-105):** secret `API_JWT_SECRET` (separate from `AUTH_SECRET`; at least 32 characters, or minting throws); lifetime 60 s, minted per request; claims `sub` (the session's GitHub user ID), `iat`, `exp`, `iss: "cfb-model-web"`, `aud: "cfb-model-api"`, HS256; library `jose@6.2.12` as a direct dependency (the version `@auth/core` already installs; Auth.js's `encode` makes an encrypted JWE, not an HS256 JWS).

**Steps**
1. Write `web/lib/api-token.test.ts` first (mocks `server-only` and `@/auth`, stubs `fetch` and env) and see it fail.
2. `web/lib/api-token.ts` (`server-only`): `mintApiToken(sub)` reads `API_JWT_SECRET` per call; a missing or short secret, or an empty `sub`, throws a fixed message that never includes the value.
3. `web/lib/api.ts`: authenticated calls (`getTeams` and every future one) call `auth()`, throw without `user.id`, and send `Authorization: Bearer <token>`. `getHealth` stays unsigned: `/api/py/health` is the one open route (02 › Auth), so AC-3 applies to the authenticated calls.
4. `web/e2e/test-env.ts`: `TEST_API_JWT_SECRET`; `web/playwright.config.ts` passes it to the API and both `next start` servers.
5. `.github/workflows/ci.yml`: the same value as job-level `API_JWT_SECRET`, with a comment that it must match `test-env.ts` (pytest reads it from TASK-004).
6. `.env.example`: drop "nothing reads this yet"; state the 32-character minimum.

**Files:** `web/lib/api-token.ts` (new), `web/lib/api-token.test.ts` (new), `web/lib/api.ts`, `web/package.json` (+ lockfile via pnpm), `web/e2e/test-env.ts` (not in "Files likely touched": the shared test constant), `web/playwright.config.ts`, `.github/workflows/ci.yml`, `.env.example`, `docs/decisions.md`.

**Tests**
- AC-1: `api-token.test.ts`: the captured fetch's Bearer token passes `jwtVerify` with the secret, issuer and audience; header `alg` HS256; `sub` `"4242"`.
- AC-2: `api-token.test.ts`: `exp − iat ≤ 300`; two calls 2 s apart carry two different tokens with their own `iat`.
- AC-3: `api-token.test.ts`: no session, no secret and a short secret each throw with fetch never called; the message excludes the secret.
- AC-4: review of the import chain (`api-token.ts` imports `server-only`; only `api.ts` imports it).
- AC-5: `web/e2e/teams.spec.ts` with the secret wired in.

**Risks:** `ci.yml` has no `workflow_dispatch`, so the "changed workflow" ready gate is met by the PR's own CI run on the branch. Owner prerequisite: `API_JWT_SECRET` set in Vercel Preview and Production before merge, or the deployed `/teams` throws.

## Review log

_Filled by /implement-task. One line per round._

## Blocked

_Only if status is Blocked: what failed, what was tried, best hypothesis, decision needed._

## Metrics

- Verify rounds:
- Review rounds:
- First-pass AC FAILs:
- Plan revisions after approval:
