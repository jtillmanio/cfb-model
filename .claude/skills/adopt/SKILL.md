---
name: adopt
description: Adopts the starter kit into an existing project that already has some combination of planning docs, a finished design, code, CI, a database, and hosting. Maps existing docs and design to kit roles without renaming anything, extracts decisions, inventories the design and toolchain, checks what's already built, and produces a gap report with fixes that unblock tasks. Use when the user runs /adopt or asks to integrate or adopt the kit into an existing project.
argument-hint: (optional) hints, e.g. "design in design/handoff; roadmap is docs/06-roadmap.md; designs win over docs"
---

# Adopt the kit into this project: $ARGUMENTS

Output:
- `docs/kit-adoption.md`: role map, inventories, gap report, and inputs for `/customize-kit` and `/milestones`
- the "Project docs" table in `CLAUDE.md`
- `docs/decisions.md`

The user's existing files stay where they are and keep their names.

## Ground rules

- **Never rename, move, reformat, or rewrite** existing docs, design files, or code. Gap fixes are appended as new sections, and only after approval.
- **Never edit anything in the design source of truth.** Design changes come from the design tool.
- **Read-only until the first gate.** No installs, migrations, or deploys at any point. Don't connect to any database or hosting environment.
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
| Planning docs | Every Markdown file under `docs/` and the root (README, ADRs, specs, roadmaps, playbooks, notes). Summarize each in one line |
| Design | Handoff bundles, HTML/PDF exports, screenshots, tokens, design links in docs. Read any README or manifest; look at the screenshots |
| Code and stack | Languages, frameworks, package managers, app entry points, monorepo layout |
| Toolchain | Scripts for dev, typecheck, lint, test, e2e, build, migrate, seed. Run none of them yet; just list them |
| Tests | Test frameworks, test count per area, e2e presence |
| CI | Workflow files, job names, what each runs, required checks if visible (`gh api repos/{owner}/{repo}/rules/branches/<default>`; skip if it fails) |
| Database | Engine, ORM/migration tool, migrations directory and count, seed scripts, how a local or dev DB is created. Flag any production connection string in tracked files or `.env.example` |
| Hosting | Config files (vercel.json, Dockerfile, fly.toml, netlify.toml, etc.), preview deploys, env var names (never values) |
| Work tracking | Roadmap/backlog docs, TODO files, open GitHub issues (`gh issue list --limit 50`) |

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
   - architecture
   - data model
   - domain specs (list each extra spec, e.g. a model or algorithm spec)
   - roadmap (source)
   - task list (where `/milestones` writes)
   - decisions
2. **Built-state check.** For each feature or roadmap item you can identify, classify it as **built**, **partial**, or **not built** by checking the code, with evidence (`file:line`).
3. Ask **one batch** of at most 8 questions, covering:
   - low-confidence mappings;
   - precedence when the design and docs disagree (default: the design wins);
   - where the task list should live (default: the next number in an existing numbered docs series, otherwise `docs/tasklist.md`);
   - how to handle in-flight branches;
   - which open issues are in scope.
   
   **Stop until the user answers.**

## Phase 3: Write the map, decisions, and inventories

1. **CLAUDE.md "Project docs" table**: replace the default paths with the confirmed mapping; use `—` for roles with no file; write the precedence rule.
   - If `CLAUDE.md` existed before the kit, merge the kit's sections into it rather than replacing it, and show the diff.
2. **docs/decisions.md**: extract decisions already made in the docs and the design (stack, data, hosting, design system). One row each, marked `(extracted from <file> §<section>)`. If the file exists, append only decisions not already recorded.
3. **docs/kit-adoption.md**, with these sections:
   - **Role map**: the confirmed table.
   - **Design inventory** (if there's a design): every screen with its design file, reference screenshot(s), states shown, widths shown, related features, and a proposed S-ID. Mismatches between the design and the docs go in a separate table.
   - **Toolchain inventory**: each script, whether it exists, and whether it runs under `cmd.exe /c` on Windows; CI jobs and what they run; DB and migration details; hosting.
   - **Built-state table**: feature or roadmap item, status, evidence.
   - **Inputs for /customize-kit**:
     - proposed `ui.designFiles`
     - `protectedPaths` (the design source of truth, applied migrations, generated code)
     - 3–6 hard-rule candidates (e.g. "use design tokens; no hard-coded colors or spacing")
     - spec-reviewer project checks
     - existing CI job names for branch protection
     - whether to delete the kit's `ci.yml`
   - **Inputs for /milestones**: the source roadmap path, built items to exclude, and toolchain gaps to schedule as early task stubs.
   - **Gap report**: see Phase 4.

## Phase 4: Gap report

Check each item and classify every gap:
- **BLOCKS TASKS**: ACs can't be written or checked without it
- **BLOCKS UNATTENDED**: fine for attended work, but needed before Level 2
- **NICE**

| Area | Check |
|---|---|
| Scope | Feature IDs; MVP / Next / Later cut; 2–3 observable outcomes per MVP feature |
| Screens | S-IDs; every MVP feature has a screen; every screen has empty / loading / error states or an explicit "use defaults" note; design-vs-doc mismatches resolved |
| Architecture | Stored vs. derived explicit; performance and reliability targets with numbers; feature → component/entity mapping |
| Testing | Strategy per level; seed data with concrete values ACs can cite (match the screenshots where practical) |
| Domain specs | Measurable acceptance for non-UI logic (e.g. evaluation metrics, a fixed backtest protocol, a baseline) |
| Toolchain | typecheck, lint, test, test-file-specific run, e2e, build, migrate, seed scripts exist and run on Windows; baseline green |
| CI | Runs the full gate on PRs; has a job name usable as a required check |
| Data safety | Local/dev DB separate from production; no production credentials in tracked files |
| Roadmap | Phases are demoable vertical slices (not layers); riskiest work early; built items excluded |

For each gap, give the fix as one of:
- **doc**: a section to append, naming the file and section
- **task**: a stub for `/milestones`
- **decision**: a question for the user

## Phase 5: Gate and fix

1. Summarize in under 25 lines: role map highlights, built-state counts, gap counts by class, and the top 5 gaps.
2. Ask which gaps to fix now. **Stop until the user answers.**
3. Fix the approved **doc** gaps by appending sections to the mapped files; never rewrite existing text. Record **task** gaps under "Inputs for /milestones". Ask any **decision** questions in one batch.
4. Commit on a branch: `docs: adopt Claude Code kit (role map, decisions, gap fixes)`. Open a PR if the default branch is protected; otherwise ask before committing to it.

## Hand-off

Next steps, in order:

1. `/customize-kit`. It reads `docs/kit-adoption.md` first.
2. Configure GitHub: the branch ruleset should use the existing CI job name.
3. `/milestones <roadmap path>`. It reads the milestone inputs from `docs/kit-adoption.md`.
4. `/new-task <task list> M1` → review → `Ready` → `/next-task`.
