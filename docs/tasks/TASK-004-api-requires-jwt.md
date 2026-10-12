---
id: TASK-004
title: Require a valid JWT on every API route except health
status: Ready
depends_on: [TASK-003]
size: M
model: opus
autonomy: attended
ui: false
plan_status: none
planned_at_commit:
---

# TASK-004 — Require a valid JWT on every API route except health

## Goal

The API's public URL serves no data to anyone without a valid token from the web app's server code; `/api/py/health` stays open and returns no data.

## Context

- Task list: `docs/08-tasklist.md` › M1 › M1.2 (second half; signing is TASK-003).
- Architecture: `docs/02-architecture.md` › Auth; › Components › 2. `python/api` (health is the **only** route outside the auth gate); › Testing strategy › Levels › Integration: API ("every route except `/api/py/health` requires the JWT").
- Rules: `.claude/rules/python.md` (the API depends only on the light core; a JWT library is fine, nothing heavy).
- Decisions: D-012, D-100 (on Vercel `/api/py/*` reaches FastAPI directly, so the API can't rely on Next's gate).
- Existing code: `python/api/src/api/main.py` (one `APIRouter` under `/api/py`; FastAPI also serves `/api/py/openapi.json`, which must be gated too); `python/api/tests/test_api_health.py`.
- The token's claims, lifetime and env var name are fixed by TASK-003's plan.
- *From #16 (TASK-003):* verification details AC-2 doesn't name: accept HS256 only (refuse every other `alg`, not just `none`), enforce the same 32-character floor on `API_JWT_SECRET` that `web/lib/api-token.ts` does, and allow a few seconds of leeway for clock skew between the Next and Python functions.

## Acceptance criteria

- [ ] AC-1: A test enumerates every route the app registers (`app.routes`) and asserts that each one except `GET /api/py/health` returns 401 without an `Authorization` header, so a route added later without the guard fails CI. This includes `/api/py/openapi.json`.
- [ ] AC-2: Given a token that is expired, signed with another secret, signed with `alg: none`, missing `sub`, or carrying the wrong audience/issuer, `GET /api/py/teams` returns 401 and its body contains no team data (one test per case).
- [ ] AC-3: Given a valid token, `GET /api/py/teams` returns the seeded fixture season (2026, "Ohio State · Big Ten") as before.
- [ ] AC-4: With the shared secret unset in the API's environment, every gated route returns 401 (fail closed), while `GET /api/py/health` still returns 200 with `commit`, `db_reachable` and `migration_head` and nothing else.
- [ ] AC-5: The 401 response doesn't echo the token or the secret (test asserts the body is a fixed message).

## Out of scope

- Signing tokens in Next (TASK-003).
- Per-user authorization or roles: one allowlisted user, so a valid token is enough.
- Rate limiting, CORS changes, and Vercel Deployment Protection.

## Files likely touched

- `python/api/src/api/auth.py` — the FastAPI dependency that verifies the token (new).
- `python/api/src/api/main.py` — apply it to the router and to the OpenAPI route; leave health outside.
- `python/api/pyproject.toml` — JWT library (lockfile via uv).
- `python/api/tests/test_api_auth.py` — AC-1, AC-2, AC-4, AC-5 (new).
- `python/api/tests/test_api_health.py` — the `client` fixture sends a valid token for `/teams`; health is still called without one.

## Verification

- Automated: `python/api/tests/test_api_auth.py`; `python/api/tests/test_api_health.py` (AC-3, health open); the existing e2e `/teams` and health specs still pass end to end.
- Manual: on the PR preview, `curl <preview>/api/py/teams` → 401; `curl <preview>/api/py/health` → 200 JSON; signed in, `/teams` in the browser still lists teams.

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
