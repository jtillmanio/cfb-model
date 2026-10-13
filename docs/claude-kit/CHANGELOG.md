# Changelog

## v2.7: Destructive-command guard

Coding agents have deleted whole repositories, home folders, and drives with one bad shell command: `rm -rf $DIR/` with `DIR` unset, `rm -rf ~` where `~/project` was meant, a cleanup run from the wrong folder, `git clean -fdx` over someone's uncommitted work. Up to 2.6 the kit's only defence was a handful of deny rules, which match the start of a command, so `rm -fr /`, `Remove-Item -Recurse C:\`, or anything inside `bash -c` got past them. In 2.7 a hook reads every shell command, works out what it would delete, and stops it when the answer is outside the project, the project itself, or work git can't give back. Upgrading a 2.6.x project: `UPGRADING.md` § From 2.6 to 2.7.

### Added

- **`.claude/hooks/guard-destructive.ps1`** (PreToolUse on `Bash|PowerShell`). It tokenizes Git Bash, PowerShell, and cmd syntax, follows `cd`, variables the command assigns itself, `bash -c`, `powershell -Command`/`-EncodedCommand`, `cmd /c`, `wsl`, `$( )`, and heredocs, and resolves each delete target (`rm`, `Remove-Item` and its aliases, `del`/`rd`, `find -delete`, `xargs rm`, `rimraf`, `robocopy /MIR`, `Get-ChildItem | Remove-Item`) against the project and worktree roots.
  - **Denied**, with Claude told to stop and ask: deleting outside the project and the temp folder; the project, a folder containing it, everything in it, its `.git`, a nested repository or worktree, a `protectedPaths` file; a recursive delete of an unresolvable path; disk and OS tools; `gh repo delete`/`archive`/visibility changes; `git push --mirror`, force pushes (including `+refspec`), deleting the base branch on the remote.
  - **Asked**: a recursive delete inside the project of a folder holding tracked files or untracked, non-ignored files (git decides); `git clean -f` (not `-X`), `git reset --hard`, whole-tree `git checkout`/`restore`, `git stash drop`/`clear`, `git worktree remove --force`, history rewrites; inline `python -c`/`node -e` code that deletes folders. Under `bypassPermissions`, asks become denies.
  - **Allowed**: files and ignored folders inside the project, anything in the temp folder, `.kit-incoming/`.
  - Every deny and ask is appended to `.claude/state/guard-destructive.log`.
- **`destructiveGuard`** in `kit.json`: `allowPaths` (default `[".kit-incoming"]`) and `commands` (`{ pattern, decision, reason }` regex rules for project commands such as database resets).
- **Stop-and-ask lines** in the `CLAUDE.md` template: deleting outside the project, the project, `.git`, or a worktree; deleting folders git doesn't ignore; discarding uncommitted work. A bullet says the guard is a net, not permission, and must never be routed around.
- **Deny rule** `gh repo delete*` (Bash and PowerShell).

### Changed

- **Every kit hook is registered in exec form** (`"command": "powershell"` plus `args`, Claude Code 2.1.139+). The 2.6 shell form put `$CLAUDE_PROJECT_DIR` in a command string; on a machine where Claude Code finds no Git Bash it runs hooks through PowerShell, which reads that as an empty variable, so no kit hook ran and nothing said so.
- **`"onFailure": "block"`** on the two guards (Claude Code 2.1.295+; older versions ignore it): a guard that can't start or times out now blocks the action.
- **`/customize-kit`** detects a 2.6 configuration, proposes the 2.7 rows, asks which outside folders Claude may clean and which destructive commands need a `destructiveGuard.commands` rule, and smoke-tests the guard.

### Fixed

- **`install-kit.ps1`** no longer copies local state from Claude sessions run in the kit folder itself (`.claude/state/`, `worktrees/`, `tmp/`, `agent-memory-local/`, `settings.local.json`) into projects.

### Upgrade notes

- The guard stops some commands an existing project's instructions may tell Claude to run (`rm -rf` on a tracked folder, `git clean -fd`, `git reset --hard`). Step 3 of the upgrade finds them.
- In an unattended session an ask can't be answered, so the command doesn't run and the session reports it. A `--bg` session waits in Needs input.
- Known limits: a script file that deletes things (`python cleanup.py`) and spellings the tokenizer doesn't follow get through. The stop-and-ask list is the rule; the hook is the net.

## v2.6: Follow-up tracking

Until 2.5, a follow-up (work noticed during a task and deliberately left out) lived only in the PR body's Follow-ups section, and after the squash merge nothing read it again. One project's audit of 18 PRs over four days found an owner-requested change in no doc at all, three candidate decisions never recorded, notes for the very next task missing from its task file, a roadmap item promising "a follow-up task" that didn't exist, and two small bugs mentioned twice each and tracked nowhere. In 2.6 every follow-up is written where the work that will do it will read it, in the PR that noticed it, and the PR says where each one went. Upgrading a 2.5.x project: `UPGRADING.md` § From 2.5 to 2.6.

### Added

- **`workflow.followUps`** (default `apply`; a missing key means `apply`). `review` shows every placement in an attended session before writing; unattended it behaves as `propose`, which is the 2.5 behaviour (PR body only), with each bullet still naming its intended destination.
- **One classification** (`.claude/skills/track-follow-ups/classify.md`), first match wins: this task (a plan revision, attended only) → an existing not-Done task's Context (never its ACs; questions become open questions for its plan) → a roadmap item with no task file yet (never its Check line) → new work (a roadmap item with an ID, size and Check, or a `Draft` task file plus its task-list stub; never `Ready`) → a candidate decision → a planning doc (Features, Architecture, Data model, ...) → the Owner checklist → not tracked, with a reason.
- **Owner approval at both task gates.** Placements that change what the product is (planning-doc edits, and decisions under `workflow.decisions: propose`) need the owner's yes. Follow-ups found while planning are listed at the plan gate, and approving the plan approves them; the rest are asked about once at close-out, together with "Push and open a draft PR?". Anything not approved in the session is queued under Approvals in the **Owner checklist**; when the owner ticks it or says "approve", Claude makes the change.
- **`## Follow-ups` in the task file** (`docs/tasks/_TEMPLATE.md`). The PR's section is copied from it, so the list is in the diff for review and survives the merge in the archived task.
- **`/track-follow-ups [--since <PR#|date>] [--dry-run]`**: a backfill for projects upgrading mid-stream. It reads merged PRs' Follow-ups (default: since the PR that installed the kit), drops what is already tracked, done, or accepted, places the rest on a `docs/` branch with one PR, and applies Owner checklist approvals the owner has ticked.
- **`.claude/scripts/list-follow-ups.ps1`**: extracts each merged PR's Follow-ups bullets and their destinations (`-FromJson` reads a file instead of `gh`).
- **`.claude/scripts/next-id.ps1`**: the next free decision ID across the working tree, `origin/<base>`, and every open PR's branch; `-List` lists roadmap IDs in use the same way.
- **`docs/templates/owner-checklist.md`**: Actions, Approvals, Done.

### Changed

- **`/implement-task`**:
  - Phase 1 lists follow-ups found while planning, with their placements, at the plan gate.
  - Phase 6 has a Follow-ups step beside decisions, then a spec-reviewer "follow-ups check" on the close-out diff, then a link commit after `gh pr create` that turns the branch name in notes into `PR #n`.
  - The Blocked path places follow-ups too.
  - Preflight treats follow-up notes added to a task since its plan as a stale plan.
- **Candidate decisions** follow `workflow.decisions` when it is set, and `workflow.followUps` when it isn't. `propose` now means Claude records the decision once the owner approves it (in the session or by ticking it in the Owner checklist) instead of leaving it in the PR. Recording one also marks the decision it changes "Amended by D-n" and fixes rules files that state the old rule.
- **spec-reviewer** allows follow-up placements that trace to a Follow-ups bullet, and flags a bullet with no destination, an edit to another task's ACs or a roadmap Check line, new work marked `Ready`, an unapproved planning-doc edit, and a reused ID.
- **`/plan-batch`** and **`/skeleton`** place their follow-ups the same way; their PRs have a Follow-ups section.
- **`.claude/rules/git.md`**: follow-up placements join archive renames as the allowed changes to other files on a task branch; every PR Follow-ups bullet ends `→ <path> § <section>` or `→ not tracked: <reason>`.
- **PR template**: the Follow-ups comment shows the format; two reviewer-checklist lines.
- **`/customize-kit`** detects a 2.5 configuration, proposes the 2.6 rows, offers an Owner checklist, and adds allow rules for `gh pr list`, `gh pr view`, and the kit's scripts.

### Fixed

- **`/new-task` and a roadmap item with no Check**: it now proposes a Check, writes it into the roadmap once the owner agrees, and only then copies it as AC-1.
- **Decision ID collisions**: two open branches appending "the next" decision took the same ID. IDs now come from `next-id.ps1`, which reads every open PR's branch.

### Upgrade notes

- The default changes behaviour with no config edit: after `-Upgrade`, task PRs edit other task files, the roadmap, the decisions log, and the Owner checklist. Set `workflow.followUps: "propose"` for the 2.5 behaviour.
- A project with `workflow.decisions: "propose"` keeps it. Candidate decisions are recorded only after the owner approves them.
- Run `/track-follow-ups` once after the upgrade merges, to recover follow-ups from PRs merged under 2.5 and earlier.

## v2.5: Task archive

`docs/tasks/` fills up with finished work after a few milestones. In 2.5 Done task files move to an archive folder, and every script and skill that looks up tasks reads it. Upgrading a 2.4.x project: `UPGRADING.md` § From 2.4 to 2.5.

### Added

- **Task archive.** Done task files move to `docs/tasks/archive/` (`workflow.archiveDone`, default `true`), so `docs/tasks/` holds only live work.
  - `.claude/scripts/archive-done.ps1` moves every Done task with `git mv`, whoever finished it, and stages the renames. It refuses to run on the base branch.
  - `/implement-task` runs it at close-out (this sweeps other Done tasks) and at accept (this archives the task itself). `/plan-batch` runs it on the plans branch.
  - `lib-tasks.ps1` reads the archive too, so dependency checks, the dispatcher, and `/new-task` ID numbering still see archived tasks. `build-index.ps1` lists them in their own table and warns about a Done task outside the archive, or a reopened task still in it.
  - `.claude/rules/git.md` allows the archive renames as the one cross-task change a branch may carry, and spec-reviewer doesn't count them as scope creep.

### Upgrade notes

- Without an upgrade step, a project's first task close-out would archive every old Done task at once, a large rename diff in a task PR. The upgrade PR archives them instead (`UPGRADING.md` step 3).
- Links to task file paths in other docs (decision log, task list, notes) aren't rewritten. Links to archived tasks now point to the wrong folder; step 4 finds them.

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
- **Container images come from `public.ecr.aws/docker/library/`**, the AWS mirror of Docker's official images, instead of Docker Hub, which rate-limits anonymous pulls: the `ci.yml` service block, the backup template, and what `/skeleton` and `/customize-kit` write.
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
