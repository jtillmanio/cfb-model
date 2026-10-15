---
id: TASK-012
title: Lint the scripts in scripts/perf
status: Review
depends_on: []
size: S
model: sonnet
autonomy: attended
ui: false
plan_status: approved
planned_at_commit: 6e3169e
---

# TASK-012 — Lint the scripts in scripts/perf

## Goal

`pnpm lint`, and so CI, also lints the Node scripts in `scripts/perf/`.

## Context

- *From #18 (TASK-007):* `scripts/perf/*.mjs` isn't linted: root `pnpm lint` runs `pnpm --dir web lint` (ESLint over `web/` only) and ruff on `python/`. `scripts/perf/` has its own `package.json` and lockfile.
- TASK-008 adds `measure.mjs` to the same folder.
- Keep `.claude/kit.json` › `verify` and the Commands table in `CLAUDE.md` in sync if the lint command changes.
- *From #44 (chore/token-trim):* the full Commands table moved to `docs/COMMANDS.md`; `CLAUDE.md` › Commands keeps the daily rows, Lint included, so AC-4's Lint row now lives in both files: update both. `verify.fast`'s first entry is now `node scripts/typecheck/run.mjs`, and `scripts/typecheck/*.mjs` falls under AC-1's `scripts/**/*.mjs` lint.
- Found while planning (2026-10-13): web's ESLint can't reach `scripts/perf/`. ESLint 9 ignores files outside the config file's folder ("outside of the base path"). A config placed in `scripts/perf/` can't import `@eslint/js` or `globals` either, because nothing is installed there except by the lighthouse workflow. A spike ran `@eslint/js` recommended rules with Node globals over a copy of `scripts/perf/`: zero findings.

## Acceptance criteria

- [x] AC-1: `pnpm lint` also runs ESLint over `scripts/**/*.mjs`, with `@eslint/js` recommended rules and Node globals, from a repo-root `eslint.config.mjs` that ignores `web/`, `python/` and every `node_modules/`. It passes on the current tree.
- [x] AC-2: A Vitest test proves the config: linting a `scripts/perf/` source with an unused variable and an undefined name fails with `no-unused-vars` and `no-undef`, a clean source that uses `process` and `console` passes, and a `web/` path is ignored. On the branch, a throwaway unused variable in `scripts/perf/lib/perf.mjs` makes `pnpm lint` exit non-zero naming the file and line; reverting it makes it pass. The throwaway never reaches the PR's final diff.
- [x] AC-3: `eslint` (major 10, matching web's), `@eslint/js` and `globals` are root devDependencies added through `pnpm`. `pnpm install` (and so `pnpm bootstrap`, CI's Install step and the worktree setup) installs them with no new step.
- [x] AC-4: `.claude/kit.json` › `verify` lints an edited `.mjs`: `.mjs` is in `sourceExtensions`, web's `verify.fast` ESLint entry covers `.mjs`, and a new entry runs the root ESLint on `.mjs` files. The `CLAUDE.md` Commands table's Lint row says ESLint covers `web/` and `scripts/`.

## Out of scope

- Fixing lint findings beyond what turning the linter on requires.
- Type-checking the scripts (`// @ts-check` / `checkJs`).
- Adding ESLint to `scripts/perf/package.json` (the lighthouse workflow's own install).

## Files likely touched

- `package.json` — root `lint` script and devDependencies
- `pnpm-lock.yaml` — through `pnpm add` only
- `eslint.config.mjs` (new, repo root)
- `web/lib/lint-scripts.test.ts` (new)
- `.claude/kit.json` — `verify`
- `CLAUDE.md` — Commands table
- `docs/COMMANDS.md` — Commands table (Lint row)

## Verification

- Automated: `pnpm --dir web exec vitest run lib/lint-scripts.test.ts`; `pnpm lint`; CI's `verify` job runs `pnpm lint` on the PR.
- Manual: AC-2's throwaway edit on the branch → `pnpm lint` fails naming `scripts/perf/lib/perf.mjs:<line>`; after the revert → passes.

## Follow-ups

_Work noticed during this task and deliberately left out. Each bullet ends `→ <path> § <section>` (where it was placed) or `→ not tracked: <reason>`. See `.claude/skills/track-follow-ups/classify.md`; the PR's Follow-ups section is copied from here._

- None.

## Plan

Approved 2026-10-13 at `e02e2dc`; re-planned 2026-10-15 at `6e3169e` because the plan was stale. #41 moved web to ESLint 10, so the owner amended AC-3 from major 9 to major 10. #44 added `docs/COMMANDS.md`'s Lint row and `scripts/typecheck/*.mjs`. A spike with ESLint 10.12.0 over every `scripts/**/*.mjs` found nothing.

1. Test first: `web/lib/lint-scripts.test.ts` (30 s timeout, it spawns a process). From the repo root, run `node node_modules/eslint/bin/eslint.js --stdin --stdin-filename <path> --format json` with `spawnSync`, then assert:
   - `scripts/perf/x.mjs` with `const unused = 1; undefinedName();` → exit 1, rule IDs `no-unused-vars` and `no-undef`.
   - `scripts/perf/x.mjs` with `console.log(process.env.X);` → exit 0.
   - `web/x.mjs` → the JSON shows the file ignored (a warning, no errors).
   It fails before step 2: there is no root ESLint.
2. `pnpm add -D -w eslint@^10 @eslint/js@^10 globals`. The lockfile changes only through this command.
3. Root `eslint.config.mjs`: `defineConfig` / `globalIgnores` from `eslint/config`. Ignore `web/**`, `python/**`, `**/node_modules/**`, `design/**`, `data/**`, `docs/**` and `.claude/**`. Then one block for `files: ["scripts/**/*.mjs"]` with `js.configs.recommended` and `languageOptions: { globals: globals.node }`.
4. Root `package.json` `lint`: `pnpm --dir web lint && eslint scripts && uv --directory python run ruff check .`
5. `.claude/kit.json` › `verify`:
   - Add `.mjs` to `sourceExtensions`.
   - Add `.mjs` to the web ESLint entry's `extensions`.
   - Add `{ "command": "pnpm exec eslint --no-warn-ignored {file}", "extensions": [".mjs"] }`.
   The new entry pins `--config eslint.config.mjs`: ESLint 10 uses the config nearest the file, so unpinned the root run would re-lint `web/` files with web's config (revision 1, from the spec review).
6. The Lint row in both `CLAUDE.md` › Commands and `docs/COMMANDS.md`: "`pnpm lint` (ESLint on `web/` and `scripts/`, ruff)".
7. AC-2's throwaway edit → `pnpm lint` fails; revert → passes. Paste both outputs in the PR.

Files: `package.json`, `pnpm-lock.yaml` (via pnpm), `eslint.config.mjs` (new), `web/lib/lint-scripts.test.ts` (new), `.claude/kit.json`, `CLAUDE.md`, `docs/COMMANDS.md`.

Tests: AC-1 by `pnpm lint` passing locally and in CI, plus the test's clean case. AC-2 by `lint-scripts.test.ts` and the throwaway edit. AC-3 by CI's `pnpm install --frozen-lockfile` and the root `package.json` diff. AC-4 by editing a `.mjs` after step 5 and seeing the post-edit hook run the root ESLint, plus reading the kit.json and CLAUDE.md diff.

Risks / open questions:
- A second ESLint install (root and `web/`). pnpm's store shares the files. Moving web's lint to the root config would be a larger change to `web/eslint.config.mjs`; not now.
- The root ESLint also runs on `web/e2e/*.mjs` edits through verify.fast. With `--config eslint.config.mjs` pinned, its `web/**` ignore plus `--no-warn-ignored` makes that a no-op; web's ESLint lints those files. (Web's own entry still lints `scripts/*.mjs` with the root config, so those edits are linted twice; harmless.)
- `.mjs` in `sourceExtensions` also runs `verify.fast`'s first entry (`node scripts/typecheck/run.mjs`) on every `.mjs` edit. Its output is capped since #44, so the cost is acceptable.

Size check: S. Seven files, no runtime code.

## Review log

Verify R1 PASS | Audit R1 PASS | Spec R1 APPROVE (one non-blocking note: pin `--config` in the verify.fast entry, applied)

## Blocked

_Only if status is Blocked: what failed, what was tried, best hypothesis, decision needed._

## Metrics

- Verify rounds: 1
- Review rounds: 1
- First-pass AC FAILs: 0
- Plan revisions after approval: 1 (pin `--config` in the root verify.fast entry; the test pins it too)
