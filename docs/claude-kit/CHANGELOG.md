# Changelog

## v2.4: Lessons from adoption

Every change comes from a real project that adopted 2.3.1 and had to work around the kit, mostly by writing counter-instructions into `CLAUDE.md`. In 2.4 a project changes the kit's behaviour through switches and project files instead, and the defaults are the ones that project needed. Upgrading a 2.3.x project: `UPGRADING.md`.

### Added

- **Workflow switches** in `kit.json` (`workflow.*`), read by the skills instead of hard-coded behaviour:
  - `staging`, `commitFormat`, `branchPrefixes`, `taskBranch` (e.g. `{type}/{id}-{slug}` for projects that name branches `feat/…`, `fix/…`), `ciJobName`;
  - `readyGates`: ordered checks before a PR is marked ready, each checked by Claude or the owner, with `when`, `failureLog`, and `ownerFix`;
  - `decisions` (`append` or `propose`), `splitPolicy` (`split` or `never-split`), `afterMerge`, `allowForceWithLease`;
  - `roadmap` and `statusDoc`: **roadmap-led mode**. The roadmap outranks task files, `/new-task` converts one sitting at a time and copies each check line verbatim, titles carry the roadmap ID, and spec-reviewer judges against the roadmap check;
  - `_wipLimitReason`, printed by the dispatcher and `/next-task`.
- **Project override files.** A skill or agent reads `.claude/project/<name>.md` first and treats it as its project section. The kit never ships these files, so an upgrade never needs a hand merge of project text inside agent bodies or skills.
- **`.claude/rules/git.md`**: branches, staging, commits, testing on the branch, PRs, merging, and rebasing, driven by the switches. The `CLAUDE.md` template's Git section now points to it.
- **`guard-large-reads.ps1`** (PreToolUse on Read) and the `largeFiles` key: a whole-file Read of a listed file is denied and the hint returned.
- **`testAudit.runners`, `testAudit.setup`, `testAudit.implementationExtensions`, `testAudit.implementationPaths`**: test audits with more than one test runner (each optionally run from its own folder, for monorepos), a setup step (e.g. reset the test database to the pre-task schema), and implementation files no fast check lints.
- **`ui.auth`** (ui-verifier signs in, reading only one variable's line), **`ui.redrawFiles`** (a UI task updates its design file in the same PR), and a 768×1024 tablet in the default `ui.viewports`.
- **Project docs roles**: Deploy, UX floor, Review findings, Owner runbook, Owner checklist. Decisions is now a real role with an ID prefix.
- **`CLAUDE.md` template**: "Which document wins" (an order plus three rules), a "Stop and ask before" list, a test-database hard-rule example, and the rule that kit behaviour changes through switches and project files.
- **Templates** in `docs/templates/`: `decisions.md`, `ux-floor.md`, `verify-skill.md` (for the generated `/verify` skill), `review-protocol.md`, `review-ledger.md`; and in `docs/templates/github/`: `release.yml` (hand-run release), `perf-budget.yml` (performance budget on previews), `backup.yml` (nightly backup with a restore drill), `dependabot.yml`.
- **`/milestones --coverage`**: checks an existing roadmap's coverage and adds the gaps to it, writing no new file.
- **`/customize-kit`**:
  - an "upgrade from 2.3.x" pass;
  - asks about shared test resources (sets `wipLimit: 1`), commands to deny (deploy, release, production data), and five categories of protected files;
  - writes the agents' project files and generates `/verify`;
  - adds `PowerShell(...)` twins of every rule and a push rule per branch prefix;
  - probes for rulesets and records in `git.md` when there's no branch protection;
  - offers reviewer `model:` and `effort:`.
- **`/skeleton`**: a test-database guard (refuses when the test URL is unset or names the app's database, with no fallback) and a CI migration check (append-only against the base branch, down files, schema fully generated).
- **`/architecture`**: offers an environment ladder, down files for destructive migrations, and deploy-on-merge versus a hand-run release as decisions. The architecture template gains an Environments section.
- **`UPGRADING.md`**, copied to `docs/claude-kit/` by the installer.

### Changed

- **Staging is by path** (default). Checkpoint and close-out commits stage named files after reading `git status` and `git diff --staged`; `git add -A`, `--all`, `.`, and `git commit -a` / `--all` are denied.
- **`settings.json` denies everything twice**, as `Bash(...)` and `PowerShell(...)`. On Windows the PowerShell tool could otherwise push to the base branch.
- **A PR is ready only when every ready gate Claude can check has passed** (default: `verify.full` on the branch head, then CI). Owner gates are listed in the PR and the final report.
- **PR body**: What · Why · Acceptance criteria · How it was verified (one row per reviewer and ready gate) · Manual verification · Follow-ups · Reviewer checklist. The PR title is a commit subject.
- **Plans reach the base branch through a PR.** `/plan-batch` commits nothing; approved plans go to a `docs/plans-<date>` branch. Claude never commits on the base branch, and `/milestones` commits on a `docs/` branch.
- **Merged is not live.** Done means merged and accepted. Final reports end with `workflow.afterMerge`, and Claude never starts a deploy.
- **`verify.fast` entries** can be `{ "command", "extensions" }`; the hook runs each only on matching files. The Node example is now `npx eslint {file} --no-warn-ignored`.
- **Agents** read `.claude/project/<agent>.md` and lost their `{{...}}` project slots. spec-reviewer checks the roadmap check, the UX floor, and the redraw rule, and flags ACs that copy a number from a mockup. schema-reviewer checks append-only migrations against the base branch, down files, parameterized SQL, and test isolation. test-auditor supports several runners. ui-verifier signs in, checks the UX floor, and compares each screenshot with the reference screenshot at the same width.
- **`/new-task`**: an AC never asserts a figure from a mockup or prose (a seed fixture built to reproduce the mockup is fine; the AC cites the fixture); every UI task gets a UX floor AC; `never-split` keeps oversized tasks whole (`size: L`, attended).
- **`/adopt`**: confirms "Which document wins" and the stop-and-ask list, offers roadmap-led mode, and produces config fixes (switches, project files) instead of `CLAUDE.md` overrides.
- **The Claude workflows skip cleanly** when `CLAUDE_CODE_OAUTH_TOKEN` is missing, instead of failing every PR that leaves draft.
- **Action versions**: `actions/checkout@v7`, `actions/setup-node@v7`, `actions/setup-python@v7`, `actions/upload-artifact@v7`.
- **`ci.yml`**: the test database block uses `TEST_DATABASE_URL` only (a dummy `DATABASE_URL` only on a build that needs one), and the job name is `workflow.ciJobName`.
- **The kit no longer ships `docs/decisions.md`**: the template is `docs/templates/decisions.md`, and skills read the log through the Decisions role. Your existing log stays where it is.

### Fixed

- `implement-task` swept the owner's uncommitted edits and env files into commits (`git add -A`).
- A project could only change kit behaviour by writing counter-instructions into `CLAUDE.md`, because `-Upgrade` overwrites skills. The kit's docs no longer advise editing skills by hand.
- `post-edit-verify.ps1` ran every fast command on every source file, so a linter that rejects `.css`, `.sql`, or `.py` files, or ignored paths, failed every such edit.
- The test audit assumed one test runner and treated only lintable files as implementation, so it couldn't restore SQL, migrations, or migration metadata to the pre-task state.
- The `protected_migration` example blocked a branch from regenerating its own unmerged migration, and a list of applied migrations goes stale. It's removed; a CI migration check replaces it.
- The CI-fix loop couldn't see a failure that isn't an Actions run (e.g. a hosting provider's preview build), and looped where only the owner could fix it.
- Parallel worktrees sharing one test database broke each other's tests at the default WIP limit.
- The dispatcher needed plans committed on the base branch, which the kit's own rules forbid.

### Upgrade

See `UPGRADING.md`. In short: `install-kit.ps1 -Upgrade`, then run `/customize-kit`, which detects the 2.3.x configuration and proposes each change for approval.

## v2.3.1: Doc-role fixes

### Fixed

- **Skills and agents now refer to document roles, not default paths.** Every reference resolves through the "Project docs" table, so projects with their own doc names (numbered docs, `design/handoff/`) get the right files. Specific fixes:
  - `/skeleton` took design tokens from `design/` (the design source of truth) instead of the **Design tokens** role.
  - `/skeleton` referred to architecture sections by number (§2/§8/§9), which non-kit docs don't have.
  - `schema-reviewer` pointed at the architecture doc where it should read the **Data model** role.
  - `/product-brief` wrote the screen inventory into the features file regardless of the **Screen inventory** role, and could overwrite existing docs. It now appends or updates sections only.
  - `/architecture`, `/milestones`, `/new-task`, and `/customize-kit` read **Data model**, **Domain specs**, **Screen inventory**, **Design tokens**, and **Reference screenshots** through the table.
- **The doc-roles note** at the top of each skill and agent now says explicitly that table paths (including `§ section`) take precedence over defaults, and that sections are referenced by name, not number.

## v2.3: Central install location

### Added

- **`install-kit.ps1`**: installs or upgrades the kit from the central folder `C:\Development\tools\claude-code-starter-kit\` into any project.
  - Never overwrites customized files; differences go to `.kit-incoming\` for Claude to merge.
  - Skips the placeholder `ci.yml` when the project already has CI.
  - Copies the guides to `docs/claude-kit/` and records the version in `.claude/kit-version`.
  - `-Upgrade` refreshes kit-owned files (skills, hooks, scripts, templates); `-WhatIf` previews.
- **`VERSION`** file.
- Optional `Install-ClaudeKit` profile shortcut (USER-GUIDE §3.1).

### Changed

- The zip's root folder is now `claude-code-starter-kit` (no version suffix), so updates replace the central folder in place.
- USER-GUIDE §3, KICKOFF Stage 0, ADOPTING Step 2, and README use the installer instead of `robocopy` and manual copies.
- `/adopt` merges `.kit-incoming\` first if it exists.

## v2.2: Adopting existing projects

### Added

- **`ADOPTING.md`**: a generic guide for projects that already have docs, design, a repo, CI, a database, hosting, or code.
  - Covers pre-flight checks, install collisions, the 9-step adoption pipeline, and common situations.
  - Includes an example role map and a fallback prompt for when the skill isn't available.
- **`/adopt`**:
  - Discovers docs, design, toolchain, CI, database, hosting, and issues.
  - Maps existing files to kit roles without renaming anything.
  - Checks what's already built against the code.
  - Extracts decisions, then writes `docs/kit-adoption.md` (role map, inventories, gap report classed BLOCKS TASKS / BLOCKS UNATTENDED / NICE, and inputs for `/customize-kit` and `/milestones`).
- **"Project docs" table in `CLAUDE.md`**: every skill and agent now resolves document paths through it, so the kit works with any doc naming scheme without editing skills.

### Changed

- `/customize-kit` reads `docs/kit-adoption.md` first, keeps existing CI (proposes deleting the kit's `ci.yml`), and merges the PR template.
- `/milestones` accepts a source roadmap, excludes built work, schedules toolchain gaps in M1, and requires design citations on UI stubs.

## v2.1: Kickoff

### Added

- **`KICKOFF.md`**: a staged plan from idea to first Ready tasks.
  - Each stage lists where it happens, the model, outputs, exit criteria, and copy-paste prompts for Claude chat and Claude Design.
  - Includes a fast path for projects with a brainstorm and a nearly finished design but no task list.
- **`/product-brief`**: brainstorm notes → `docs/product/brief.md`, `features.md` (F-/S- IDs, MVP cut, screen inventory with states, cut list), and `design-brief.md` for Claude Design.
- **`/architecture`**: decision option tables with a gate, then `docs/architecture.md` (data model, traceability, NFRs with numbers, testing strategy, skeleton spec, risks) and seeded `docs/decisions.md`.
- **`/skeleton`**: walking skeleton.
  - Scaffold, all kit-required scripts, one end-to-end slice, a unit test and an e2e smoke test, CI, and dev-setup README.
  - Every script is verified before the PR.
- **`/milestones`**: demoable, risk-first milestones with task stubs and a coverage check (features, screens, entities) → `docs/tasklist.md`.
- **`docs/templates/`**: `brief.md`, `features.md`, `architecture.md`, `tasklist.md`.

### Changed

- `/new-task` bulk mode accepts a milestone filter (`/new-task docs/tasklist.md M1`) and writes TASK IDs back next to each stub.
- USER-GUIDE and README point new projects to `KICKOFF.md` and list the new skills.

## v2

### Added

- **Level 2 unattended workflow:**
  - `/plan-batch` plans several tasks for one approval sitting.
  - `.claude/scripts/dispatch-approved.ps1` starts one background session per approved unattended task (`claude --bg`), within a WIP limit, with claims tracked in `.claude/state/dispatch.json`.
- **`/next-task`:** picks the best Ready task (dependency-unblocking first) within the WIP limit and runs it attended.
- **`test-auditor` agent:** runs the task's tests against the pre-task implementation to prove they discriminate, plus a static review of each test.
- **`ui-verifier` agent:** Playwright browser checks of UI ACs at phone and desktop widths, with screenshots, console errors, and design deviations.
- **PR flow in `/implement-task`:**
  - Checkpoint commits on `task/...` branches, then a draft PR.
  - Watches CI, fixes failures (max 2 rounds), then marks the PR ready.
  - Replying "accepted" sets `Done`.
- **Unattended mode:** `/implement-task <ID> --unattended` requires an approved, fresh plan; questions surface as Needs input in agent view; round limits end in Blocked with a `[BLOCKED]` draft PR.
- **Plan staleness check:** `planned_at_commit` is compared against the planned files before work starts.
- **Task front matter:** `autonomy`, `ui`, `plan_status`, `planned_at_commit`, and a `## Blocked` section.
- **`kit.json` sections:** `workflow`, `testAudit`, `ui`.
- **`settings.json` deny rules:** no pushes to main/master, no force-push, no `gh pr merge`, no hard reset or `clean -fdx`.
- **GitHub templates:** `ci.yml`, `claude-pr-review.yml`, `claude.yml` (subscription token), `pull_request_template.md`.
- **`.claude/.gitignore` and `docs/tasks/.gitignore`.**
- **Docs:** `USER-GUIDE.md` (install and usage); `README.md` is now an overview.

### Changed

- `docs/tasks/INDEX.md` is generated by `build-index.ps1` and git-ignored. Task files are the only source of truth, so parallel PRs never conflict on the board.
- `/customize-kit`:
  - adds permission allow-rules;
  - excludes `.claude/` from tools that scan the tree;
  - fills `ci.yml`;
  - lists the manual GitHub settings;
  - is safe to re-run.
- `/new-task` sets `autonomy` and `ui` and regenerates the board instead of editing it.
- `spec-reviewer` adds a PLAN GAP check. Reviewers read the base branch from `kit.json`.
- `CLAUDE.md` template has v2 workflow rules and a Git section.

### Fixed

- The v1 README said `claude agents` lists subagents. In current Claude Code it opens agent view. To check that agents loaded, type `@` in a session instead.
- Hook scripts now use forward-slash paths throughout, so they also run under PowerShell 7 on Linux/macOS (CI, WSL).

### Upgrade

See USER-GUIDE §3, "Upgrade from v1".
