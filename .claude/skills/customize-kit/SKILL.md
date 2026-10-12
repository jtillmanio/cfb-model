---
name: customize-kit
description: One-time setup (or re-run after an upgrade) that tailors the Claude Code starter kit v2 to this project — kit.json, CLAUDE.md, rules, agent project files, permissions, ignore files, the /verify skill, and the GitHub workflow templates — from the real codebase. Detects a 2.3.x, 2.4.x, or 2.5.x configuration and proposes the upgrade to the installed version. Use only when the user runs /customize-kit or explicitly asks to customize, re-customize, or upgrade the kit.
---

# Customize the starter kit (v2)

> **Doc roles:** names in **bold** such as **Architecture**, **Data model**, or **Decisions** are roles in the "Project docs" table in `CLAUDE.md`. Always read and write the path the table gives for a role, including a `§ section` if it names one. The path in parentheses is only the default, used when the table is missing. If a role maps to `—`, follow the fallback stated in the step, or ask. Refer to sections by name, never by number.

> **Project overrides:** read `.claude/project/customize-kit.md` if it exists. It holds this project's instructions for this skill and wins where it conflicts with this file, except that it can't lower the floor: show a diff and wait for approval before changing any existing file, and never weaken a deny rule the user didn't ask to remove.

Goal: every `{{...}}` placeholder and every empty `kit.json` value that applies to this project is filled with facts from this repository. Every command has been run once, and nothing is invented. Project-specific text lives only in files the kit never overwrites: `kit.json`, `settings.json`, `CLAUDE.md`, `.claude/rules/`, `.claude/project/`, and `.claude/skills/verify/`.

## Ground rules

- Use only commands that exist in this repo's manifests and scripts. If a needed command doesn't exist, propose adding it and ask.
- The developer is on Windows. Commands in `kit.json` must run under `cmd.exe /c` from the project root (`gradlew.bat`, not `./gradlew`). GitHub workflow files run on Ubuntu, so use Linux syntax there.
- Before writing to any existing file, show a diff summary and wait for approval. New files can be written directly.
- Re-running is safe: keep existing non-placeholder values unless the user asks to change them.
- Never put project text into a kit-owned file (`.claude/skills/<kit skill>/`, `.claude/hooks/`, `.claude/scripts/`, `docs/templates/`): `install-kit.ps1 -Upgrade` overwrites them. Project instructions for a kit skill or agent go in `.claude/project/<name>.md`. A project script goes in the project's own folder (e.g. `scripts/`), not in `.claude/scripts/`: the installer wouldn't overwrite it there, but it reads as a kit file and an uninstall removes it.
- Never open an env file whole. To learn which variables exist, read `.env.example` or the code.

## Phase 0: Upgrade from 2.3.x, 2.4.x, or 2.5.x (only when it applies)

Run this phase when `.claude/kit-version` is 2.4 or later and any of these hold; otherwise skip to Phase 1.

- 2.6: `.claude/kit.json` has no `workflow.followUps` key.
- 2.5: `.claude/kit.json` has no `workflow.archiveDone` key, or it isn't `false` and task files with `status: Done` sit in `docs/tasks/` outside `archive/`.

- `.claude/kit.json` has no `workflow.staging`, `workflow.readyGates`, `largeFiles`, or `testAudit.runners` key.
- `.claude/settings.json` doesn't register `guard-large-reads.ps1`, or has `Bash(...)` deny rules without `PowerShell(...)` twins.
- `.kit-incoming/` exists.
- An agent in `.claude/agents/` contains a project section (headings or lines naming this project, "override", or text not in the kit's version of that agent).
- `CLAUDE.md` contains instructions that counter the kit's skills (a "Kit task loop" section, "even though the skill says", "instead of the kit's"), or names `docs/decisions.md` as a fixed path.
- A `.claude/skills/verify/SKILL.md` exists that the kit didn't generate, or none exists.
- A project file sits in a kit-owned folder (a script in `.claude/scripts/` or a hook in `.claude/hooks/` that the kit doesn't ship), or a leftover copy of a kit file from an earlier merge (e.g. a `CLAUDE.kit.md` beside `CLAUDE.md`).

Then, reading `docs/claude-kit/UPGRADING.md` for the mapping:

1. Merge `.kit-incoming/` first: keep the user's content, add the kit's new sections, keys, and rules. For agents, take the kit's body and keep the user's `model:` and `effort:` frontmatter. `.kit-incoming/.github/workflows/ci.yml` is the kit's unfilled template: never merge it into a filled-in `ci.yml`; only check that the project's CI keeps the parse step, `timeout-minutes`, `concurrency`, the job name, and test-database isolation. One-line summary per file.
2. Build an upgrade table, one row per proposed change: what changes, why (the 2.4 item, or the 2.5 or 2.6 change), the exact edit, and what text it lets you delete.
   - From 2.5, only the 2.6 rows apply (UPGRADING.md § From 2.5 to 2.6):
     - `kit.json`: `"followUps": "apply"` in `workflow` (or `review` / `propose` if the owner wants to see placements first). Say what candidate decisions will do: an explicit `workflow.decisions` keeps winning (`propose` now means Claude records a decision once the owner approves it); a missing one follows `followUps`.
     - The **Owner checklist** role: if it is `—`, offer to create one from `docs/templates/owner-checklist.md` (approvals and owner actions are queued there) and add the row. If one exists, propose adding Actions and Approvals headings in its own style.
     - `.claude/rules/git.md`: the follow-up placements paragraph after "One task per branch, one branch per PR", and the `→` sentence on the PR body.
     - `spec-reviewer.md`: the follow-ups check (step 11), the "Follow-ups check only" mode, and the scope sentence. Keep `model:` and `effort:`.
     - PR template: the Follow-ups comment and the two checklist lines.
     - `CLAUDE.md`: the Workflow bullet on follow-ups.
     - `settings.json`: allow `gh pr list *`, `gh pr view *`, and the kit's scripts (Phase 3).
     - `.claude/project/*.md` files that say how follow-ups or candidate decisions are handled (e.g. "decisions are proposed, the owner adds them"): replace them with the switches, or keep them as the project's rule; they win.
     - After merge, run `/track-follow-ups` once (it defaults to every PR since the kit was installed).
   - From 2.4, the 2.5 rows as well (UPGRADING.md § From 2.4 to 2.5): the `archiveDone` key; the `CLAUDE.md`, `git.md`, spec-reviewer, and PR-template lines; archiving the existing Done tasks with `archive-done.ps1` on the upgrade branch; and links or project files that read task file paths.
   - From 2.3, cover all of these as well:
   - new `kit.json` keys, with values derived from what the project already does (its git rules, CLAUDE.md overrides, CI, hosting);
   - settings: the staging deny rules, `PowerShell(...)` twins, the large-read hook, branch-prefix push rules, deploy-command denies, `Read(...)` denies for production env files;
   - project sections moved out of agent bodies into `.claude/project/<agent>.md`;
   - CLAUDE.md workarounds replaced by switches or `.claude/project/<skill>.md` files, and the prose to delete;
   - new Project docs rows (Deploy, UX floor, Review findings, Owner runbook, Owner checklist; Decisions with its ID prefix);
   - `.claude/rules/git.md` created or merged;
   - project scripts moved out of kit-owned folders (update every reference to them in `kit.json`, `settings.json`, and docs), or replaced by a switch (a test-routing script by `testAudit.runners`); leftover copies of kit files deleted;
   - CI: job name, the parse step, the test database, Docker Hub images switched to the `public.ecr.aws/docker/library/` mirror; the Claude workflows' secret gate; action versions;
   - optional templates worth offering.
3. **Stop for approval.** The user may approve rows one by one.
4. Apply the approved rows, then continue with Phase 1 to fill anything still empty. Skip questions the upgrade table already settled.

## Phase 1: Discover (read-only)

0. If `docs/kit-adoption.md` exists (written by `/adopt`), read it first. Use its role map, design inventory, toolchain inventory, and "Inputs for /customize-kit" as confirmed facts, and don't re-ask anything it settles.
1. Detect the stack: manifests, lockfiles, framework and test configs (how many test runners?), lint configs (which file types and paths each linter accepts or ignores), ORM/migration tool and its directory, generated-code directories, existing CI workflows, dev server command and port flag, sign-in on the dev server, hosting and deploy or release workflows.
2. Read the **Architecture**, **Data model**, and **Domain specs** docs, the **Design source of truth**, **Design tokens**, **Reference screenshots**, the **Decisions** log, any **Task list** or roadmap, any **UX floor**, **Deploy**, and **Owner runbook** docs, and `.claude/rules/`.
3. Run `git remote -v`, `gh auth status`, and `claude --version`. Agent view needs Claude Code v2.1.139 or later. Probe branch protection: `gh api repos/{owner}/{repo}/rulesets`. A 403 or 404 on a private free-plan repository means rulesets aren't available.
4. Find large files: tracked text files over ~100 KB under `docs/`, `design/`, and data folders, and any script that prints one section of one.
5. Present a findings table: languages, framework, package manager, test runners (and how to run specific test files for each), linter and the extensions it accepts, typechecker, DB and migration tool, dev server command with port flag, sign-in (y/n), design source files, large files, hosting and deploy path, GitHub remote, rulesets available (y/n), gh authenticated (y/n), Claude Code version. Mark anything unknown as `UNKNOWN`.
6. Ask in one batch, and **stop until the user answers**:
   - confirm or correct the table;
   - pick 3–6 hard rules (offer candidates from the architecture doc);
   - **shared test resources**: would two parallel worktree sessions share a stateful test resource (one test database that tests reset or truncate, fixed ports, files on disk)? If yes, `wipLimit` becomes 1;
   - **commands Claude must never run**: deploy, release, production-data, and destructive reload commands (offer candidates from the manifests and workflows);
   - **files to protect**, by category: production env files, design sources exported from a design tool, the owner's source data, generated folders, vendored assets;
   - **workflow switches** that differ from the defaults (see Phase 2), when the project's own git rules or docs already say how it works;
   - the stop-and-ask list in `CLAUDE.md`, tailored to this project's data.

## Phase 2: kit.json

| Key | Fill with |
|---|---|
| `verify.sourceExtensions` | Extensions that should trigger fast checks. List only extensions that **every** string entry in `verify.fast` accepts |
| `verify.fast` | Checks that finish in ≤ 20 s in total: typecheck/compile plus single-file lint with `{file}`. No tests. A command that only accepts some extensions is an object `{ "command", "extensions" }`. A linter that exits non-zero on ignored files needs its flag for that (eslint: `--no-warn-ignored`) |
| `verify.full` | typecheck → lint → tests → production build |
| `protectedPaths` | Keep the defaults; add each category the user confirmed, each with a `reason`. Never migrations (a CI migration check enforces append-only; see `/skeleton`), and never a file in `ui.redrawFiles` |
| `largeFiles` | One entry per large file found, with a `hint` naming the cheap way to read part of it (a section-printer script, Grep, or offset/limit); `"always": true` for generated data that should be queried, never read |
| `workflow.baseBranch` | The repo's default branch |
| `workflow.wipLimit` | 2, or 1 when parallel worktrees would share a stateful test resource; then also `workflow._wipLimitReason` with the resource named, e.g. "Every worktree uses the same test database, which the tests reset" |
| `workflow.worktreeSetup` | What a fresh worktree needs: dependency install (`npm ci`, venv + pip install). A per-task DB setup only if the user wants one (that is also how the WIP limit can go back up) |
| `workflow.worktreeCopyFiles` | Untracked files a worktree needs to run: the development env file and similar. Never a production env file |
| `workflow.unattendedPermissionMode` | Leave `acceptEdits` unless the user asks for `auto` |
| `workflow.staging` | `by-path` (default). `all` only if the user insists; then remove the matching deny rules |
| `workflow.commitFormat` | `conventional` (default), or `area` if the project's history or git rules use `<area>: <subject>` |
| `workflow.branchPrefixes` | Default `task/`, `fix/`, `docs/`, `chore/`; add any the project uses |
| `workflow.taskBranch` | `task/{id}-{slug}` (default). If the project names branches by kind (`feat/…`, `fix/…`), `{type}/{id}-{slug}`, with each prefix's meaning written in `.claude/rules/git.md` |
| `workflow.ciJobName` | The CI job branch protection should require (`verify` for the kit's `ci.yml`) |
| `workflow.readyGates` | `["verify.full", "ci"]`, plus a gate for each check the project runs on a branch before merge: preview deployed, performance budget green, UI walked on the preview, changed workflow run with `gh workflow run <file> --ref <branch>`. Each with `by` (can Claude check it?), `when`, and `failureLog` when its log isn't an Actions run. `ownerFix` for a known failure only the owner can clear |
| `workflow.decisions` | `append` (default), or `propose` if the owner records decisions themselves |
| `workflow.splitPolicy` | `split` (default), or `never-split` if one roadmap item must stay one PR |
| `workflow.afterMerge` | The closing line when merging doesn't deploy, e.g. "After merge, run the Release workflow to put it live." Empty otherwise |
| `workflow.allowForceWithLease` | `false` unless the project's git rules allow it after a rebase |
| `workflow.archiveDone` | `true` (default). `false` only if the user wants Done task files kept in `docs/tasks/`, e.g. because other docs link to task file paths |
| `workflow.followUps` | `apply` (default): follow-ups are written where the work will read them, in the PR that found them. `review` if the owner wants to approve every placement in the session first; `propose` to keep them in the PR body only |
| `workflow.roadmap` / `workflow.statusDoc` | Only in roadmap-led mode (`/adopt` asks): `{ path, idPattern, checkLabel }`, and the status page regenerated from the roadmap |
| `testAudit.testPathPatterns` | Adjust to this repo's test layout |
| `testAudit.run` | The command that runs specific test files, with `{tests}`, when there is one runner |
| `testAudit.runners` | With several runners: one `{ "pattern", "run" }` per runner, `"each": true` for a runner that takes one file at a time, `"dir"` for a runner that must run from a subfolder (a monorepo app); its test paths are then made relative to that folder. This replaces a hand-written routing script |
| `testAudit.setup` | Run once before the dynamic check, e.g. reset the test database so it matches the pre-task schema |
| `testAudit.implementationExtensions` / `implementationPaths` | Implementation files that `sourceExtensions` leaves out because no fast check lints them (SQL, Python next to TypeScript), and paths such as migration metadata. The test-auditor reverts these too |
| `ui.startCommand` / `ui.baseUrl` | Dev server command and URL, with `{port}`. Leave empty if there's no UI |
| `ui.viewports` | Phone, tablet (768×1024), desktop by default; offer the extra phone and desktop widths the design draws |
| `ui.designFiles` | Paths to the committed design sources |
| `ui.redrawFiles` | Design files a UI task updates in the same PR when it changes a screen (only if the user wants that rule) |
| `ui.auth` | If the dev server needs a sign-in: `{ loginPath, envFile, secretVar, steps }`. `envFile` is the development env file, never production |

Run every `verify.fast` and `verify.full` command, and each `testAudit` runner with one existing test file. Report a table: command, exit code, seconds. Don't add a command that fails on a clean checkout unless the user accepts it as a known baseline failure. If `fast` takes more than 20 s, propose a cheaper variant.

## Phase 3: Permissions and ignores

1. In `.claude/settings.json`, add `permissions.allow` rules so verification and PR steps don't prompt in unattended sessions. Add each rule twice, as `Bash(...)` and as `PowerShell(...)`:
   - For each `verify.*` command and each `testAudit` run or setup command: `<command>` and `<command> *`
   - `git add *`, `git commit *`, `git checkout *`, `git switch *`, `git branch -m *`
   - `git push -u origin <prefix>*` for each `workflow.branchPrefixes` entry
   - `gh pr create *`, `gh pr checks *`, `gh pr ready *`, `gh pr list *`, `gh pr view *`, `gh run view *`, and `gh workflow run *` / `gh run watch *` if a ready gate uses them
   - The kit's scripts the skills run: `powershell -NoProfile -ExecutionPolicy Bypass -File .claude/scripts/*`
   - Each `workflow.worktreeSetup` command
2. Deny rules (deny overrides allow). Keep every existing one, then:
   - Make sure every `Bash(...)` deny rule has a `PowerShell(...)` twin. On Windows the PowerShell tool can otherwise push to the base branch.
   - Keep the staging denies (`git add -A*`, `git add --all*`, `git add .`, `git commit -a*`, `git commit --all*`) unless `workflow.staging` is `all`.
   - Add a deny for each deploy, release, production-data, and destructive-reload command the user named, e.g. `Bash(gh workflow run release.yml*)`. Claude never starts a deploy.
   - Add `Read(./<file>)` for each production env file.
   - Remove `git push --force-with-lease *` only if `workflow.allowForceWithLease` is true.
3. Make sure `.claude/.gitignore` exists, so `worktrees/`, `state/` and `tmp/` stay out of git.
4. Exclude `.claude/` from every tool that scans the tree, so worktree copies under `.claude/worktrees/` don't double-count: tsconfig `exclude`, eslint ignores, test runner excludes, formatter ignores, Tailwind or other content globs, Python tool excludes. Show each change.

## Phase 4: CLAUDE.md, rules, agents, and /verify

1. **CLAUDE.md**: fill the project paragraph, the Commands table (matching `kit.json`), the Project docs table, "Which document wins" (with what the design files rule), the confirmed hard rules, the stop-and-ask list, and conventions observed in the code (cite the files). Keep it under ~100 lines. If a section runs long (domain rules, design rules), offer to move it into `.claude/rules/<topic>.md` with `paths:` frontmatter so it loads only when Claude touches those files, and leave a one-line pointer. Each rule has one home: delete the copy you moved, don't keep both.
2. **`.claude/rules/git.md`**: if it doesn't exist, it comes from the kit. Fill "Project notes": files never to commit (env variants, generated data, backups), and, if rulesets aren't available, "No branch protection is available on this repository: these rules and the settings deny rules are the only guard."
3. **Agent project files**, in `.claude/project/<agent-name>.md`. The kit never ships these, so an upgrade never touches them. Never write project text into the agent files themselves.
   - `test-runner.md`: for each `verify.full` command, how its failures look (where file:line, test names, and expected/actual appear), which output is noise, which failures are environmental (missing database, unset variable), and whether it is an `&&` chain that stops at its first failure (name the step that failed; the later ones didn't run).
   - `test-auditor.md`: how each runner reports an assertion failure versus a load failure, and anything `testAudit.setup` can fail on.
   - `spec-reviewer.md`: 3–6 checks derived from the hard rules, the roadmap check in roadmap mode, and the UX floor and redraw rule for UI tasks.
   - `schema-reviewer.md`: the project data rules and the migration tool's specifics (directory, naming, generated files, the migration check script, down files and their test).
   - `ui-verifier.md`: sign-in details beyond `ui.auth`, which database the dev server writes to and what it may change, how to read large design files (the `largeFiles` hint), and which design source wins for which screens.
   - Delete a file's topic if it doesn't apply. If there's no database, propose deleting the schema-reviewer agent and ask. If there's no UI, propose deleting ui-verifier and ask; otherwise confirm Node is installed (`node --version`) for the Playwright MCP server.
4. **Reviewer model and effort** (optional): offer to set `model:` (`opus`, `sonnet`, `haiku`) and `effort:` (`low` … `max`) in the reviewer agents' frontmatter. The kit default is Opus for spec-reviewer and schema-reviewer. These two lines are the only project edits inside an agent file; keep them when merging an upgrade.
5. **`/verify` skill**: generate `.claude/skills/verify/SKILL.md` from `docs/templates/verify-skill.md`, filled from `verify.full` and the stack's test database rule. It runs before every push and reports actual output. If the project already has its own `/verify`, show the diff and ask.

## Phase 5: GitHub files

0. **If the repo already has CI** (any workflow besides the kit's three): keep it. Propose deleting the kit's `ci.yml` and ask. Check that the existing CI runs the `verify.full` equivalents on pull requests, and propose additions if not. Propose adding the kit's "Task files parse cleanly" step (`./.claude/scripts/build-index.ps1` with `shell: pwsh`) to its main job, and switching any Docker Hub image (a `services:` image, `docker run`, `container:`) to its `public.ecr.aws/docker/library/` mirror. Set `workflow.ciJobName` to its job name. Skip step 1.
1. **`.github/workflows/ci.yml`** (new CI only):
   - Replace the "not configured" step with this stack's setup (runtime action at its current major version, dependency cache, install) and the `verify.full` equivalents in Linux syntax.
   - If there's a database, enable the service block with the production database's major version and `TEST_DATABASE_URL`. Every container image comes from `public.ecr.aws/docker/library/<image>:<tag>`, the mirror of Docker's official images, never a bare Docker Hub name (`postgres:16`): Docker Hub rate-limits anonymous pulls; don't set `DATABASE_URL` in the test job (only a dummy on a build step that needs one). Add the migration check step if `/skeleton` built one.
   - If there are end-to-end tests, enable that job.
   - Set `on.push.branches` to `workflow.baseBranch`.
   - Keep the task-file parse step, `timeout-minutes`, `concurrency`, and the job name (`workflow.ciJobName`).
2. **`.github/pull_request_template.md`**: if the project had its own template, merge the kit's sections into it (What, Why, Acceptance criteria, How it was verified with one row per ready gate, Manual verification, Follow-ups, Reviewer checklist). Otherwise leave as is.
3. **`claude-pr-review.yml`** and **`claude.yml`** (optional): explain what each does and ask whether to keep them. They skip cleanly while the `CLAUDE_CODE_OAUTH_TOKEN` secret is missing. Tell the user that `/install-github-app` sets up the GitHub App and the secret, and that it must be run in an attached terminal.
4. **Optional templates** in `docs/templates/github/`: offer each that fits, and copy it into `.github/` only if the user says yes: `release.yml` (hand-run release), `perf-budget.yml` (performance budget on previews), `backup.yml` (nightly backup with a restore drill), `dependabot.yml`. Fill their placeholders from the project.
5. List the GitHub settings the user must change by hand (Claude can't and shouldn't change them):
   - Protect the base branch, if rulesets are available: require a PR, require the `workflow.ciJobName` check, block force pushes, allow only the repository admin to bypass. If they aren't, say so: the deny rules and `.claude/rules/git.md` are the only guard.
   - Settings → Actions → General → Workflow permissions: allow GitHub Actions to create pull requests only if they plan to use `claude.yml`.

## Phase 6: Docs scaffolding

1. Make sure `docs/tasks/_TEMPLATE.md` exists, and that the **Decisions** log exists at its mapped path; if it doesn't, create it from `docs/templates/decisions.md` with the role's ID prefix. Seed it with decisions already visible in the architecture doc, one row each, marked `(seeded)`.
   If the **Owner checklist** role is `—`, offer one from `docs/templates/owner-checklist.md` (e.g. `docs/owner-checklist.md`): follow-ups that only the owner can do, or that wait for the owner's approval, are queued there. Without it, an unattended session can only leave them in the PR.
2. Offer a **UX floor** from `docs/templates/ux-floor.md` if the project has a UI and no floor yet; add it to the Project docs table. Offer the **Review findings** templates (`docs/templates/review-protocol.md`, `review-ledger.md`) if the project runs independent review rounds.
3. Run `.claude/scripts/build-index.ps1` to generate `INDEX.md`. It's git-ignored via `docs/tasks/.gitignore` and regenerated on demand.
4. If a task list exists, offer `/new-task <path>`. Don't run it automatically.

## Phase 7: Smoke test and report

Run these and report each exit code:

```powershell
'{"tool_input":{"file_path":"<a real source file>"}}' | powershell -NoProfile -ExecutionPolicy Bypass -File .claude/hooks/post-edit-verify.ps1; $LASTEXITCODE     # expect 0
'{"tool_input":{"file_path":"<a file no fast check applies to>"}}' | powershell -NoProfile -ExecutionPolicy Bypass -File .claude/hooks/post-edit-verify.ps1; $LASTEXITCODE   # expect 0, instantly
'{"tool_input":{"file_path":".env"}}' | powershell -NoProfile -ExecutionPolicy Bypass -File .claude/hooks/guard-protected-paths.ps1; $LASTEXITCODE          # expect 2
'{"tool_input":{"file_path":"<a largeFiles path>"}}' | powershell -NoProfile -ExecutionPolicy Bypass -File .claude/hooks/guard-large-reads.ps1; $LASTEXITCODE   # expect 2 (skip if largeFiles is empty)
powershell -NoProfile -ExecutionPolicy Bypass -File .claude/scripts/build-index.ps1; $LASTEXITCODE                                                           # expect 0
powershell -NoProfile -ExecutionPolicy Bypass -File .claude/scripts/dispatch-approved.ps1 -DryRun                                                           # expect a summary, no dispatch
```

Final report:
- Files changed, one line each
- Command timing table
- Anything still `UNKNOWN`
- Manual GitHub steps remaining
- Suggested next step: commit by path on a `chore/` branch (`chore: customize Claude Code kit`), push, and open a PR
