---
name: adopt
description: Adopts the starter kit into an existing project that already has some combination of planning docs, a finished design, code, CI, a database, and hosting. Maps existing docs and design to kit roles without renaming anything, extracts decisions, inventories the design and toolchain, checks what's already built, and produces a gap report with fixes that unblock tasks. Use when the user runs /adopt or asks to integrate or adopt the kit into an existing project.
argument-hint: (optional) hints, e.g. "design in design/handoff; roadmap is docs/06-roadmap.md; designs win over docs"
---

# Adopt the kit into this project: $ARGUMENTS

> **Project overrides:** read `.claude/project/adopt.md` if it exists. It holds this project's instructions for this skill and wins where it conflicts with this file, except that it can't lower the floor: never rename, move, or rewrite existing files, and stop at both gates.

Output:
- `docs/kit-adoption.md`: role map, inventories, gap report, and inputs for `/customize-kit` and `/milestones`
- the "Project docs" table, "Which document wins", and "Stop and ask before" list in `CLAUDE.md`
- the **Decisions** log, at whatever path the role map gives it

The user's existing files stay where they are and keep their names.

## Ground rules

- **Never rename, move, reformat, or rewrite** existing docs, design files, or code. Gap fixes are appended as new sections, and only after approval.
- **Never edit anything in the design source of truth.** Design changes come from the design tool.
- **Read-only until the first gate.** No installs, migrations, or deploys at any point. Don't connect to any database or hosting environment. Never open an env file; list variable names from `.env.example` or the code only.
- Treat `$ARGUMENTS` as hints, not facts. Verify each one against the repo.

## Phase 0: Preconditions

1. `git status --porcelain` must be clean, apart from freshly copied kit files. Otherwise stop and ask.
2. Check for leftovers from installing the kit:
   - If `.kit-incoming/` exists, merge each file in it into the same path in the project first. Keep all the user's content; add only new kit sections, keys, rules, and steps. Show a one-line summary per file, then delete `.kit-incoming/`.
   - If the kit's placeholder `.github/workflows/ci.yml` (it contains "CI not configured") exists alongside another CI workflow, ask to delete it. The existing CI wins.
3. List open PRs and unmerged branches (`gh pr list`, `git branch -r --no-merged`). In-flight work is noted in the report; the user decides whether to finish it before adopting.

## Phase 1: Discover (read-only)

Inventory everything, citing paths:

| Area | Look for |
|---|---|
| Planning docs | Every Markdown file under `docs/` and the root (README, ADRs, specs, roadmaps, runbooks, checklists, review findings, notes). Summarize each in one line |
| Design | Handoff bundles, HTML/PDF exports, screenshots, tokens, design links in docs. Read any README or manifest; look at the screenshots |
| Code and stack | Languages, frameworks, package managers, app entry points, monorepo layout |
| Toolchain | Scripts for dev, typecheck, lint, test, e2e, build, migrate, seed. Run none of them yet; just list them |
| Tests | Test frameworks and runners (more than one?), test count per area, e2e presence, which database tests use |
| CI | Workflow files, job names, what each runs, required checks if visible (`gh api repos/{owner}/{repo}/rules/branches/<default>`; a 403 means rulesets aren't available on this plan: note it) |
| Database | Engine, ORM/migration tool (forward-only?), migrations directory and count, any migration check script, seed scripts, how a local or dev DB is created, how many databases exist (dev, test, preview, production). Flag any production connection string in tracked files or `.env.example` |
| Hosting | Config files (vercel.json, Dockerfile, fly.toml, netlify.toml, etc.), preview deploys, release or deploy workflows, env var names (never values) |
| Work tracking | Roadmap/backlog docs (phased? check lines per item?), status pages, TODO files, open GitHub issues (`gh issue list --limit 50`) |
| Large files | Tracked text files over ~100 KB that agents will need to read in parts (design exports, roadmaps, data), and any script that prints one section |

## Phase 2: Role map and questions (gate)

1. Map each kit role to existing paths, with confidence (high / medium / low):
   - product brief
   - features
   - screen inventory
   - design brief / intent
   - design source of truth
   - design tokens
   - reference screenshots
   - design process notes
   - UX floor (a standing list of states, contrast, targets, and widths every UI task must meet)
   - architecture
   - data model
   - domain specs (list each extra spec, e.g. a model or algorithm spec)
   - roadmap (source)
   - task list (where `/milestones` writes)
   - decisions (and its ID prefix, e.g. `D-`)
   - review findings
   - deploy (how merged code goes live)
   - owner runbook, owner checklist
2. **Built-state check.** For each feature or roadmap item you can identify, classify it as **built**, **partial**, or **not built** by checking the code, with evidence (`file:line`).
3. Ask **one batch** of at most 8 questions, covering:
   - low-confidence mappings;
   - **which document wins**: propose an order (code and schema → the task list's acceptance checks → architecture → narrative docs) and what the design files rule, and ask the user to confirm or reorder;
   - **roadmap-led mode**, if the project has a phased task list whose items carry a check line: keep it as the source of truth (`workflow.roadmap`) and convert one sitting at a time, or let `/milestones` write a kit task list;
   - where the task list should live otherwise (default: the next number in an existing numbered docs series, otherwise `docs/tasklist.md`);
   - the **stop-and-ask list**: the kit's generic five (schema columns, how stored data or dates are interpreted, repositories and visibility, any database but test, deleting user data), tailored to this project's tables and data;
   - how to handle in-flight branches;
   - which open issues are in scope.

   **Stop until the user answers.**

## Phase 3: Write the map, decisions, and inventories

1. **CLAUDE.md**:
   - "Project docs" table: replace the default paths with the confirmed mapping; use `—` for roles with no file. The Decisions row names its ID prefix.
   - "Which document wins": the confirmed order and the three rules, with what the design files rule.
   - "Stop and ask before": the tailored list.
   - If `CLAUDE.md` existed before the kit, merge the kit's sections into it rather than replacing it, and show the diff.
2. **Decisions log**: extract decisions already made in the docs and the design (stack, data, hosting, design system). One row each, marked `(extracted from <file> §<section>)`. If the log exists, append only decisions not already recorded; if there is none, create it from `docs/templates/decisions.md` at the mapped path.
3. **docs/kit-adoption.md**, with these sections:
   - **Role map**: the confirmed table.
   - **Design inventory** (if there's a design): every screen with its design file, reference screenshot(s), states shown, widths shown, related features, and a proposed S-ID. Mismatches between the design and the docs go in a separate table.
   - **Toolchain inventory**: each script, whether it exists, and whether it runs under `cmd.exe /c` on Windows; CI jobs and what they run; DB and migration details; hosting.
   - **Built-state table**: feature or roadmap item, status, evidence.
   - **Inputs for /customize-kit**:
     - `verify`: `sourceExtensions` and `fast` so that every fast command accepts every listed extension. A linter that rejects a file type, or ignores a path and exits non-zero, gets the object form `{ "command", "extensions" }` or its "no warning on ignored files" flag (e.g. eslint's `--no-warn-ignored`). Files no fast command accepts get no fast check; `verify.full` covers them
     - `testAudit`: test path patterns, and `runners` (one per test runner, each with `{tests}`), `setup` (e.g. reset the test database), and `implementationExtensions` / `implementationPaths` for implementation files no fast check lints (SQL, migration metadata)
     - proposed `ui.designFiles`, `ui.viewports`, `ui.auth` (if the app has a sign-in), and `ui.redrawFiles` (design files a UI task updates in the same PR)
     - `protectedPaths`, each with a reason: production env files, design sources exported from a design tool, the owner's source data, generated folders, vendored assets. **Not** migrations: recommend a CI migration check instead (a glob blocks a branch from regenerating its own unmerged migration; a list of applied files goes stale)
     - `largeFiles` entries and their hints
     - the workflow switches the project needs: `staging`, `commitFormat`, `branchPrefixes`, `readyGates` (preview deploys, performance checks, workflow runs on the branch), `decisions`, `splitPolicy`, `afterMerge`, `allowForceWithLease`, `ciJobName`, `roadmap`, `statusDoc`, and `wipLimit` (1 if parallel worktrees would share a stateful test resource)
     - deploy, release, production-data, and destructive-reload commands to deny
     - 3–6 hard-rule candidates (e.g. "use design tokens; no hard-coded colors or spacing")
     - spec-reviewer and schema-reviewer project checks, for their `.claude/project/` files
     - existing CI job names for branch protection, and whether rulesets are available
     - whether to delete the kit's `ci.yml`, and whether `CLAUDE_CODE_OAUTH_TOKEN` is set for the Claude workflows
   - **Inputs for /milestones**: the source roadmap path, the mode (plan, or coverage only in roadmap mode), built items to exclude, and toolchain gaps to schedule as early task stubs.
   - **Gap report**: see Phase 4.

## Phase 4: Gap report

Check each item and classify every gap:
- **BLOCKS TASKS**: ACs can't be written or checked without it
- **BLOCKS UNATTENDED**: fine for attended work, but needed before Level 2
- **NICE**

| Area | Check |
|---|---|
| Scope | Feature IDs; MVP / Next / Later cut; 2–3 observable outcomes per MVP feature |
| Screens | S-IDs; every MVP feature has a screen; every screen has empty / loading / error states or a UX floor that covers them; design-vs-doc mismatches resolved |
| Architecture | Stored vs. derived explicit; performance and reliability targets with numbers; feature → component/entity mapping |
| Testing | Strategy per level; a separate test database that tests can't miss; seed data or fixtures ACs can cite (never figures copied from mockups) |
| Domain specs | Measurable acceptance for non-UI logic (e.g. evaluation metrics, a fixed backtest protocol, a baseline) |
| Toolchain | typecheck, lint, test, test-file-specific run, e2e, build, migrate, seed scripts exist and run on Windows; baseline green |
| CI | Runs the full gate on PRs; has a job name usable as a required check; branch protection available or not |
| Data safety | Development and test databases separate from production; no production credentials in tracked files; destructive scripts refuse production |
| Workflow | The kit's defaults (staging by path, ready gates, PR body, decisions, task splitting, merged vs. live) fit the project's own git rules, or the switches to set are listed |
| Roadmap | Phases are demoable vertical slices (not layers); riskiest work early; built items excluded |

For each gap, give the fix as one of:
- **doc**: a section to append, naming the file and section
- **config**: a `kit.json` switch, a `.claude/project/<name>.md` file, or a settings rule, for `/customize-kit`
- **task**: a stub for `/milestones`
- **decision**: a question for the user

Never fix a workflow mismatch by writing counter-instructions to the kit's skills into `CLAUDE.md`; use a switch or a project file.

## Phase 5: Gate and fix

1. Summarize in under 25 lines: role map highlights, built-state counts, gap counts by class, and the top 5 gaps.
2. Ask which gaps to fix now. **Stop until the user answers.**
3. Fix the approved **doc** gaps by appending sections to the mapped files; never rewrite existing text. Record **config** and **task** gaps under the inputs for `/customize-kit` and `/milestones`. Ask any **decision** questions in one batch.
4. Commit on a `docs/` or `chore/` branch, staging by path: `docs: adopt Claude Code kit (role map, decisions, gap fixes)`. Push it and open a PR; never commit on the base branch.

## Hand-off

Next steps, in order:

1. `/customize-kit`. It reads `docs/kit-adoption.md` first.
2. Configure GitHub: the branch ruleset should use the existing CI job name (if rulesets are available).
3. `/milestones <roadmap path>` (coverage only, in roadmap mode). It reads the milestone inputs from `docs/kit-adoption.md`.
4. `/new-task <task list> M1` (or the first sitting's roadmap IDs) → review → `Ready` → `/next-task`.
