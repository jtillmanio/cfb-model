---
id: TASK-052
title: Generate the TypeScript API types from OpenAPI
status: Review
depends_on: []
size: M
model: sonnet
autonomy: attended
ui: false
plan_status: approved
planned_at_commit: ef00231
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

- [x] AC-1: Running the generate command (`pnpm api:types`, or the name the plan picks, listed in `docs/COMMANDS.md`) writes the TypeScript types for every route in the API's OpenAPI schema, and running it twice in a row leaves the file byte-identical.
- [x] AC-2: `web/lib/teams.ts`, `web/lib/api.ts` and the Teams page use the generated `TeamsOut`/`HealthOut` types (or aliases of them); no hand-written response type for an API route remains in `web/lib/` (a Vitest case or grep in the test fails on one).
- [x] AC-3: Given a field added to `TeamOut` in `python/api/src/api/main.py` and the types not regenerated, the drift check exits non-zero and names the generated file; after regenerating, it exits 0. CI runs the check on every PR (shown failing on the branch once, then passing).
- [x] AC-4: `pnpm typecheck`, `pnpm lint` and `pnpm build` pass with the generated file in place, and the Teams page e2e (`web/e2e/teams.spec.ts`) still passes.

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

- TASK-053 changes `/teams`'s response model (the `shell` block), so its PR must run `pnpm api:types` and commit the file or `pnpm test` fails → docs/tasks/TASK-053-shell-data-in-screen-endpoints.md § Context
- TASK-055 adds the `/slate` response models, with the same rule → docs/tasks/TASK-055-slate-endpoint.md § Context
- Candidate decision: types generated and committed, drift checked by a Vitest case, generator in `web/`, no fetch client → docs/decisions.md § D-155
- `openapi-typescript` 7.13.0 declares a peer range of TypeScript ^5 and the repo is on 6, so pnpm prints a peer warning; the generator and `tsc` work → not tracked: informational, the plan accepted it (Risks); the PR says so
- The roadmap item and M5.4 stub say "API client", but the task delivers generated types and keeps `signedGet` → not tracked: item ticked as delivered, its text is not edited (ticks.md); D-155 records the choice
- The AC-2 scan flags a hand-written type that declares every property of a schema, so a copy that drops or renames fields would pass it → not tracked: a heuristic backed by `tsc`, which fails when a generated type no longer fits a use

## Plan

_Written by /plan-batch or /implement-task Phase 1. Approved by the user (plan_status: approved) before any code is written._

**Choices (for the plan gate):**
- **The file** is `web/lib/api-types.ts`, committed: `tsc`, review and Next's build all see it, and drift is a plain text comparison.
- **The dump** is `python -m api.openapi`, a new module in `python/api`: it imports `app` and prints `app.openapi()` as sorted, indented ASCII JSON. No server and no JWT, and no DB connection because `engine()` is lazy.
- **The drift check** runs as a Vitest case inside `pnpm test`, which CI runs on every PR and `verify.full` runs locally. So drift fails before a push, and `ci.yml` stays as it is (no "changed workflow" gate). Ruled out: a separate CI step, which would duplicate the same check and fire only after a push.
- **The generator** lives in `web/scripts/api-types.mjs` because `openapi-typescript` is a `web/` dev dependency, and pnpm doesn't hoist it to the root. It uses the programmatic API (`openapiTS` + `astToString`), so no temp file.

**Steps**
1. Tests first (below); see each fail.
2. `pnpm --dir web add -D openapi-typescript`.
3. `python/api/src/api/openapi.py`: `schema_json() -> str` (`json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n"`) and `if __name__ == "__main__": sys.stdout.write(schema_json())`.
4. `web/scripts/api-types.mjs`, with exports for the test:
   - `dumpSchema()` spawns `uv --directory ../python run python -m api.openapi` and parses its stdout.
   - `generate(schema)` returns a fixed header ("Generated by `pnpm api:types` from the FastAPI schema; do not edit") plus `astToString(await openapiTS(schema))`, LF only.
   - `checkDrift(generated, onDisk)` returns `{ code, message }`; it normalises CRLF on the disk side (Windows checkouts) and the message names `web/lib/api-types.ts` and the fix (`pnpm api:types`).
   - CLI: with no flag it writes the file; `--check` exits with `checkDrift`'s code.
5. Scripts: in `web/package.json`, `"api:types": "node scripts/api-types.mjs"`; in the root `package.json`, `"api:types": "pnpm --dir web api:types"`. Run it to create `web/lib/api-types.ts`.
6. `web/lib/teams.ts`: `export type Team = components["schemas"]["TeamOut"]`, `export type TeamsResponse = components["schemas"]["TeamsOut"]`. `web/lib/api.ts`: `HealthResponse = components["schemas"]["HealthOut"]`. `team-table.tsx` keeps importing `Team` (an alias), so it is touched only if `tsc` objects.
7. `web/eslint.config.mjs`: add `lib/api-types.ts` to `globalIgnores` only if `pnpm lint` flags the generated code.
8. Docs:
   - `docs/COMMANDS.md`: a row for `pnpm api:types`, run after any change to an API response model.
   - `docs/02-architecture.md` › Testing strategy › Levels (Contract): say where the check runs.
   - › Components › 3: generated *types* + `signedGet`, no fetch client.
   - One decision (ID from `next-id.ps1`): committed file, Vitest drift check, generator in `web/`.
9. AC-3 on the branch: push a commit that adds a field to `TeamOut` without regenerating, so CI goes red with the file named. Revert it and CI goes green. Both runs go in the Review log.

**Files** (≤ 15): `web/package.json`, `pnpm-lock.yaml`, `package.json`, `python/api/src/api/openapi.py`, `python/api/tests/test_openapi.py` (new), `web/scripts/api-types.mjs` (new), `web/lib/api-types.ts` (generated), `web/lib/api-types.test.ts` (new), `web/lib/api.ts`, `web/lib/teams.ts`, `web/app/teams/team-table.tsx` (if needed), `web/eslint.config.mjs` (if needed), `docs/COMMANDS.md`, `docs/02-architecture.md`, `docs/decisions.md`.

**Test strategy** (`api-types.test.ts` dumps the schema once in `beforeAll`, with a 30 s timeout because it spawns uv)
- AC-1:
  - `api-types.test.ts`: "generates a path entry for every route in the schema" (each `paths` key appears in the output) and "two generations are byte-identical".
  - `test_openapi.py`: "the dump lists /api/py/teams and /api/py/health and not the schema route", and "two dumps are equal".
- AC-2: `api-types.test.ts` › "no hand-written response type in web/lib". It scans `web/lib/*.ts` (not tests, not `api-types.ts`) for object-literal `type`/`interface` bodies and fails if one's property names cover a schema's property set (e.g. `{ season, teams }`). A sample with the old `TeamsResponse` proves the scan.
- AC-3: `api-types.test.ts` covers three cases:
  - "a TeamOut with an extra field fails the check, naming web/lib/api-types.ts" (the real schema with `logo_url` added, generated, compared with the committed file).
  - "the unchanged schema passes".
  - "the committed file matches the API today" (the real `--check`, exit 0). This case is what CI runs.
  - Step 9 shows CI red, then green.
- AC-4: `pnpm typecheck`, `pnpm lint`, `pnpm build` and `web/e2e/teams.spec.ts` in `verify.full`.

**Risks / open questions**
- `openapi-typescript`'s peer range may not list TypeScript 6 yet. A peer warning is fine. If install fails, pin the newest version that installs and say so in the PR.
- Pydantic's `str | None` comes out as `anyOf [string, null]`, which should generate `string | null` (required). The AC-2 aliases make `tsc` prove it.
- `pnpm test` gains one `uv run` spawn (~2–3 s). `uv` is already on CI's PATH before `pnpm test`.

**Size check:** ≤ 15 files across web, the API and docs; no schema change and no UI change. M, attended.

## Review log

_Filled by /implement-task. One line per round._

Verify R1 PASS | Audit R1 PASS (every test PROVEN; the CI half of AC-3 needs plan step 9) | Spec R1 CHANGES (`beforeAll` lacked the 30 s timeout; AC-2 scan matched exact property sets, the plan said "cover") → R2 APPROVE | Verify R2 PASS (after the review fixes) | Schema and UI reviewers: not run (no migration, SQL or UI file in the diff)

AC-3, CI half (plan step 9), on PR #134: commit `2cc5bf8` added `logo_url: str | None = None` to `TeamOut` without regenerating → CI run 41865840869 RED at `pnpm test` only (typecheck and lint passed): `api-types.test.ts` failed, with the drift message ``web/lib/api-types.ts is out of date with the API's OpenAPI schema. Run `pnpm api:types` and commit the result.`` Commit `22ff128` reverted it → CI run 41867973989 GREEN. The red run also exposed a stale sample in one of my own tests (it hard-coded `TeamOut`'s properties, so it failed when `TeamOut` gained a field); fixed in the same push so the scan test now builds its sample from the schema, and shown to pass with the extra field present (only the 3 drift-dependent tests fail) and with it removed (12/12).

Ready gates on `22ff128`: verify.full PASS (R2, before the step 9 commits; the step 9 commits change one test and revert one line, and CI `verify` ran the whole suite green) | CI `verify` PASS | Vercel preview PASS | Lighthouse fixture PASS (within budget) | Changed workflow run: n/a (no workflow change).

## Blocked

_Only if status is Blocked: what failed, what was tried, best hypothesis, decision needed._

## Metrics

- Verify rounds: 2 (both PASS; the second followed the review fixes)
- Review rounds: 2 (R1 CHANGES, R2 APPROVE)
- First-pass AC FAILs: 0
- Plan revisions after approval: 0
