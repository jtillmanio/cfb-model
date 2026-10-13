# CLAUDE.md

Personal sports-analytics app. A college football model makes game predictions, compares them to spreads (market and Splash pick'em contest lines), recommends picks, ranks teams (later also seasons, programs and coaches across history), projects seasons, and tracks its own record. Multi-sport later.

**Status:** Phase 0 in progress. The walking skeleton is merged: Neon DB and migration `0001`, `/api/py/health` and `/teams`, CI and Vercel previews. The `release` workflow (TASK-005), the nightly `backup` workflow (TASK-006) and the `lighthouse` workflow on PR previews (TASK-008) are built. Not built yet: shadcn/ui, the R2 lake bucket, Dependabot. Status lives in the `docs/06-roadmap.md` checklists.

## Where things are
- `docs/01`–`07`: product, architecture, data model, model, UI brief, roadmap, Claude Design playbook. Read the relevant one before starting a phase task.
- `design/`: mock sample data, Claude Design exports (the visual reference) and handoff bundles.
- `.claude/rules/`: area rules (git always; python, database and web by path).
- `.claude/project/`: this project's sections for the kit's agents (and skills, if any); the kit never overwrites them.

## Project docs

Every kit skill and agent reads this table to find project documents. Use `—` for roles the project doesn't have. `docs/claude-kit/` holds the kit's own guides, which use the default names (`docs/product/*`, `docs/architecture.md`, `docs/tasklist.md`); read them through this table.

| Role | Path |
|---|---|
| Product brief | `docs/01-product.md` |
| Features (IDs, MVP cut, outcomes) | `docs/01-product.md` |
| Screen inventory (S-IDs, states) | `docs/05-ui-design-brief.md` § Screen inventory (from handoff) |
| Design brief / intent | `docs/05-ui-design-brief.md` |
| Design source of truth | `design/handoff/designs/` |
| Design tokens | `design/handoff/tokens/` |
| Reference screenshots | `design/handoff/screenshots/` |
| Design process notes | `docs/07-claude-design-playbook.md` |
| UX floor | — |
| Architecture | `docs/02-architecture.md` |
| Data model | `docs/03-data-model.md` |
| Domain specs (other) | `docs/04-model.md` |
| Roadmap (source, if separate) | `docs/06-roadmap.md` |
| Task list (milestones + stubs) | `docs/08-tasklist.md` |
| Tasks | `docs/tasks/` (fixed; Done tasks in `docs/tasks/archive/`) |
| Decisions | `docs/decisions.md` (IDs `D-###`) |
| Review findings | — |
| Deploy | `.github/workflows/release.yml` (README › Releasing); the owner runs it |
| Owner runbook | — |
| Owner checklist | `docs/owner-checklist.md` |

Where to look inside these files:
- **Product brief:** What we're building · Who it's for · What "good" looks like · Non-goals. **Features:** Feature index (F-01…; MVP = end of Phase 4).
- **Data model:** once `python/db/` exists, its models and migrations win (see "Which document wins").
- **Design source of truth:** board notes are the spec; the `Pass … .dc.html` boards win over older boards; the bundle README is `design/README.md`.
- **Design tokens:** color only; type, spacing, radius and elevation values are in `design/README.md` › Design tokens.
- **Reference screenshots:** default state, dark, 1440 and 390; This Week also at 768.
- **Roadmap:** the status source of truth; `/milestones` writes the task list from it.
- **Sample data / fixture seeds** (no kit role): `design/sample-data.md`, `design/sample-splash.txt`, `design/handoff/designs/*-data.js`.

## Which document wins
When two sources disagree, believe them in this order, and fix the loser in the same PR:
1. Code and migrations: what actually runs.
2. This file and `.claude/rules/`.
3. The task file's acceptance criteria: the contract for the work.
4. **Architecture**, **Data model** and **Domain specs** (`docs/02`–`04`): why the system is shaped this way.
5. Narrative docs (`docs/01`, `05`, `07`): drafted earliest, the most likely to have drifted.

On top of the order:
- **The design rules layout and copy.** Where the design source of truth and a doc disagree (including `docs/05-ui-design-brief.md`), the design wins unless the doc notes an override or the user says otherwise. It never wins on a number: what the model computes and how numbers are defined follow `docs/04-model.md` and this file.
- **Runbooks and prompts rank below the task file.** They say how work is driven, not what it must do; a disagreement is a bug to report.
- **Counts and numbers come from code or data, never from prose.** Prose about unbuilt work says so inline; until then the code wins.

## Domain conventions
- `margin = home_points − away_points`. `spread_home` is negative when home is favored (CFBD convention). Home covers if `margin + spread_home > 0`; push if `= 0`.
- **Point-in-time:** anything used to predict a game uses only data available before kickoff. Ratings at `(season, week=N)` mean "entering week N". Never use season-aggregate stats in a backtest.
- Ratings, predictions and picks are **immutable**; re-runs insert new rows tied to a `model_run`. Results, records, ranks and CLV are **views**, never stored.
- The raw lake is append-only; transforms must rebuild from raw with zero API calls. Never re-fetch completed CFBD weeks (call budget).

## Hard rules
Checkable against a diff; the spec-reviewer agent enforces them. Each restates a rule already in this file or `.claude/rules/`.
1. Never store derived values (results, records, ranks, CLV, current pick, current contest line). They are SQL views.
2. Ratings, predictions and picks are insert-only: no UPDATE or DELETE, ever.
3. Reference rows are upserted by `(source, source_id)`: never truncated and reloaded, and IDs never derived from load order.
4. Anything that predicts a game reads only data from before kickoff, and every feature table and backtest path asserts it.
5. `python/api` imports only the engine's light core, and the browser never calls the API directly (one server-side API call per page).
6. Never edit files matched by `protectedPaths` in `.claude/kit.json` (including `design/**` and `.env.live`) or a migration already on `main`. If one must change, stop and ask.
7. UI uses design tokens from `design/handoff/tokens/` (via `web/app/tokens.css` and the `@theme` in `web/app/globals.css`); no hard-coded colors, font sizes, or spacing.

## Stop and ask before
- Any schema change (new table or column, a type change, a dropped column) or changing how a stored date or line is interpreted
- Touching any database other than test/dev, or running anything with `.env.live`
- Deleting or rewriting user data (contest entries, adjustments, lab models) or live predictions/picks
- Creating GitHub repos, changing visibility, deleting or archiving one, or editing secrets
- Deleting anything outside the project and the temp folder, the project itself, its `.git`, or a worktree (use `git worktree remove`)
- Deleting a folder that holds files git doesn't ignore (remove tracked files with `git rm -r`), or discarding uncommitted work: `git clean -f`, `git reset --hard`, `git checkout -- .`, `git restore .`, `git stash drop`
- Anything where the task is ambiguous. Ask rather than guess.

`.claude/hooks/guard-destructive.ps1` denies or asks about the common forms of these deletes. It is a net, not permission: never route around a block with another command, tool, script, or path spelling. Stop and ask.

## Working with the user
The user is an experienced software developer, new to statistical modeling. Explain modeling concepts and the reasoning behind choices briefly as you go, linking to `docs/04-model.md`. Engineering explanations can stay terse.

## Commands
Windows; commands also run under `cmd.exe /c` (the hooks do). `.claude/kit.json` is the source of truth for verification (`verify.fast` after every edit, `verify.full` for the test-runner); keep this table in sync.

| Purpose | Command |
|---|---|
| Install dependencies | `pnpm bootstrap` (worktrees: `pnpm install --frozen-lockfile`, `uv --directory python sync`) |
| Dev server | `pnpm dev` (web :3000, API :8000) |
| Typecheck | `pnpm typecheck` (`next typegen && tsc`, pyright) |
| Lint | `pnpm lint` (ESLint, ruff) |
| Unit / integration tests | `pnpm test` (Vitest, pytest; pytest reads only `TEST_DATABASE_URL`) |
| Specific test files | `uv --directory python run pytest <paths>`, `pnpm --dir web exec vitest run <paths>`, `pnpm --dir web exec playwright test <paths>` (paths relative to `python/` or `web/`; `testAudit.runners` routes them the same way) |
| End to end | `pnpm test:e2e` (after `pnpm db:migrate:test` and `pnpm db:seed`) |
| Production build | `pnpm build` |
| Migrations | `pnpm db:migrate` (dev), `pnpm db:migrate:test`, `pnpm db:check` (one head, models match) |
| Seed | `pnpm db:seed` (fixture; test DB only) |

## Conventions
- Styling: Tailwind v4 utilities mapped to tokens in the `@theme` block of `web/app/globals.css` (colors, `text-caption`/`text-body`/…, radii). `web/app/tokens.css` is a byte copy of the handoff tokens.
- Data: server components fetch through `web/lib/api.ts` (`server-only`), one call per page. Response types and pure helpers live in `web/lib/*.ts` with Vitest tests beside them (`*.test.ts`).
- Every data route has a `loading.tsx` drawn at the loaded size (`web/app/teams/loading.tsx`).
- Python tests live in `python/<pkg>/tests/test_*.py`; DB tests use the `db_conn` fixture from `python/conftest.py` (test-DB guard, rolled back). E2E specs live in `web/e2e/` and run at phone and desktop widths.

## Workflow
- One task per session: `/implement-task TASK-###` or `/next-task`. No code before the task's `plan_status: approved`. Claude sets `Review`; only the user's "accepted" sets `Done`.
- Work noticed and left out is a follow-up: it is written where the work that will do it will read it (another task's Context, the roadmap, the decisions log, an approved doc edit, the Owner checklist), per `workflow.followUps`, and the PR lists where each went.
- Never hand-edit `docs/tasks/INDEX.md`; run `.claude/scripts/build-index.ps1`.
- Done task files move to `docs/tasks/archive/` (`workflow.archiveDone`). `.claude/scripts/archive-done.ps1` moves every Done task, not only the current one, at each task's close-out and accept. It never runs on the base branch.
- Post-edit check failures in the middle of a multi-file change are expected. Finish the change, then fix what still fails.
- Kit behaviour is changed through the switches in `.claude/kit.json` and the files in `.claude/project/`, never by editing the kit's skills, hooks or scripts (`install-kit.ps1 -Upgrade` overwrites those).
- Claude never starts a deploy or release, dry run included, unless the user says so for that release.

## Git
Branches, staging, commit messages, testing on the branch, pushing, PRs and merging are in `.claude/rules/git.md`, which loads in every session.
