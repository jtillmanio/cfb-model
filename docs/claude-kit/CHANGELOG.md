# Changelog

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
