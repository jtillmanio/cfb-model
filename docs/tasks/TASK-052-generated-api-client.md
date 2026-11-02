---
id: TASK-052
title: Generate the TypeScript API types from OpenAPI
status: Ready
depends_on: []
size: M
model: sonnet
autonomy: attended
ui: false
plan_status: none
planned_at_commit:
---

# TASK-052 — Generate the TypeScript API types from OpenAPI

## Goal

The web app's API response types are generated from the FastAPI schema, and CI fails when the API changes without the types being regenerated, so the two can't drift.

## Context

- Task list: `docs/08-tasklist.md` › M5 › M5.4. The stub said S; with the drift check in CI, the scripts and the docs it is M across web and tooling.
- Architecture: `docs/02-architecture.md` › Components › 3 ("A typed API client generated from FastAPI's OpenAPI schema (`openapi-typescript`)"), › Testing strategy › Levels (Contract: "The generated client matches the API's current OpenAPI schema; CI fails on drift").
- Decisions: D-011 (`openapi-typescript`), D-010 (one endpoint per screen; the browser never calls the API), D-012/D-105 (every route but health needs the JWT).
- Today: `web/lib/teams.ts` hand-writes `Team` and `TeamsResponse`, and `web/lib/api.ts` hand-writes `HealthResponse`. The API serves its schema only behind the JWT (`/api/py/openapi.json` on `router` in `python/api/src/api/main.py`), so generation should read `app.openapi()` in-process rather than call a running server.
- **Plan gate decides:** where the generated file lives and whether it's committed (committing it lets `tsc` and review see it, and makes the drift check a plain diff); how the schema is dumped (an `api` module entry point run with `uv`, per `.claude/rules/python.md` "scripts are … Python, never PowerShell/bash pairs"); and where the drift check runs (a CI step, a test, or both).
- `pnpm-lock.yaml` changes only through pnpm (protected path).
- A change to `.github/workflows/*` triggers the "Changed workflow run on the branch" ready gate.

## Acceptance criteria

- [ ] AC-1: Running the generate command (`pnpm api:types`, or the name the plan picks, listed in `docs/COMMANDS.md`) writes the TypeScript types for every route in the API's OpenAPI schema, and running it twice in a row leaves the file byte-identical.
- [ ] AC-2: `web/lib/teams.ts`, `web/lib/api.ts` and the Teams page use the generated `TeamsOut`/`HealthOut` types (or aliases of them); no hand-written response type for an API route remains in `web/lib/` (a Vitest case or grep in the test fails on one).
- [ ] AC-3: Given a field added to `TeamOut` in `python/api/src/api/main.py` and the types not regenerated, the drift check exits non-zero and names the generated file; after regenerating, it exits 0. CI runs the check on every PR (shown failing on the branch once, then passing).
- [ ] AC-4: `pnpm typecheck`, `pnpm lint` and `pnpm build` pass with the generated file in place, and the Teams page e2e (`web/e2e/teams.spec.ts`) still passes.

## Out of scope

- A typed fetch wrapper (`openapi-fetch` or similar): `web/lib/api.ts` keeps its `signedGet`, typed by the generated types. Add one only if the plan gate finds it simpler.
- New endpoints or fields (the shell block is TASK-053, `/slate` TASK-055).
- The lab's model-builder form generated from `ModelSpec`'s JSON Schema (D-011's second half, M14).

## Files likely touched

- `web/package.json` (`openapi-typescript` dev dependency), `pnpm-lock.yaml` (through pnpm), root `package.json` (`api:types` script)
- `python/api/src/api/openapi.py` (or a `__main__`) — dumps `app.openapi()` without a server
- `web/lib/api-types.ts` — generated
- `web/lib/api.ts`, `web/lib/teams.ts`, `web/app/teams/team-table.tsx` — use the generated types
- `web/eslint.config.mjs` — ignore the generated file, if needed
- `.github/workflows/ci.yml` — the drift step
- `docs/COMMANDS.md` — the new command

## Verification

- Automated: the drift check in CI; `pnpm typecheck`; `web/e2e/teams.spec.ts`; the AC-2 test.
- Manual: add a field to `TeamOut`, run the drift check → expected: non-zero exit naming the generated file; regenerate → expected: exit 0 and the field appears in the types.

## Follow-ups

_Work noticed during this task and deliberately left out. Each bullet ends `→ <path> § <section>` (where it was placed) or `→ not tracked: <reason>`. See `.claude/skills/track-follow-ups/classify.md`; the PR's Follow-ups section is copied from here._

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
