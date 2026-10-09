---
id: TASK-003
title: Sign every API call from Next server code with a short-lived JWT
status: Ready
depends_on: [TASK-001]
size: M
model: opus
autonomy: attended
ui: false
plan_status: none
planned_at_commit:
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
