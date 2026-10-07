---
name: customize-kit
description: One-time setup (or re-run after an upgrade) that tailors the Claude Code starter kit v2 to this project — kit.json, CLAUDE.md, agents, permissions, ignore files, and the GitHub workflow templates — from the real codebase. Use only when the user runs /customize-kit or explicitly asks to customize or re-customize the kit.
---

# Customize the starter kit (v2)

Goal: every `{{...}}` placeholder and every empty `kit.json` value that applies to this project is filled with facts from this repository. Every command has been run once, and nothing is invented.

## Ground rules

- Use only commands that exist in this repo's manifests and scripts. If a needed command doesn't exist, propose adding it and ask.
- The developer is on Windows. Commands in `kit.json` must run under `cmd.exe /c` from the project root (`gradlew.bat`, not `./gradlew`). GitHub workflow files run on Ubuntu, so use Linux syntax there.
- Before writing to any existing file, show a diff summary and wait for approval. New files can be written directly.
- Re-running is safe: keep existing non-placeholder values unless the user asks to change them.

## Phase 1: Discover (read-only)

1. Detect the stack: manifests, lockfiles, framework and test configs, lint configs, ORM/migration tooling and its directory, generated-code directories, existing CI workflows, dev server command and port flag.
2. Read `docs/02-architecture.md`, `docs/03-data-model.md`, the design (`design/README.md`, `design/handoff/designs/`, `design/handoff/tokens/`), `docs/decisions.md`, and the task list (`docs/08-tasklist.md`) if it exists. Paths follow "Project docs" in `CLAUDE.md`.
3. Run `git remote -v`, `gh auth status`, and `claude --version`. Agent view needs Claude Code v2.1.139 or later.
4. Present a findings table: languages, framework, package manager, test runner (and how to run specific test files), linter, typechecker, DB and migration tool, dev server command with port flag, design source files, GitHub remote, gh authenticated (y/n), Claude Code version. Mark anything unknown as `UNKNOWN`.
5. Ask the user to confirm or correct the table and to pick 3–6 hard rules (offer candidates from `docs/02-architecture.md`, `docs/03-data-model.md` and `.claude/rules/`). **Stop until they answer.**

## Phase 2: kit.json

| Key | Fill with |
|---|---|
| `verify.sourceExtensions` | Extensions that should trigger fast checks |
| `verify.fast` | Checks that finish in ≤ 20 s in total: typecheck/compile plus single-file lint with `{file}`. No tests |
| `verify.full` | typecheck → lint → tests → production build |
| `protectedPaths` | Keep the defaults; add applied migrations, generated code, vendored code, and anything the user names, each with a `reason` |
| `workflow.baseBranch` | The repo's default branch |
| `workflow.worktreeSetup` | What a fresh worktree needs: dependency install (`npm ci`, venv + pip install). A per-task DB setup only if the user wants one |
| `workflow.worktreeCopyFiles` | Untracked files a worktree needs to run: `.env.local` and similar |
| `workflow.unattendedPermissionMode` | Leave `acceptEdits` unless the user asks for `auto` |
| `testAudit.testPathPatterns` | Adjust to this repo's test layout |
| `testAudit.run` | The command that runs specific test files, with `{tests}` |
| `ui.startCommand` / `ui.baseUrl` | Dev server command and URL, with `{port}`. Leave empty if there's no UI |
| `ui.designFiles` | Paths to the committed design sources: `design/handoff/designs/`, `design/handoff/screenshots/`, `design/README.md` |

Run every `verify.fast` and `verify.full` command, and `testAudit.run` with one existing test file. Report a table: command, exit code, seconds. Don't add a command that fails on a clean checkout unless the user accepts it as a known baseline failure. If `fast` takes more than 20 s, propose a cheaper variant.

## Phase 3: Permissions and ignores

1. In `.claude/settings.json`, add `permissions.allow` rules so verification and PR steps don't prompt in unattended sessions:
   - For each `verify.*` and `testAudit.run` command: `Bash(<command>)` and `Bash(<command> *)`
   - `Bash(git add *)`, `Bash(git commit *)`, `Bash(git checkout *)`, `Bash(git push -u origin task/*)`, `Bash(git branch -m *)`
   - `Bash(gh pr create *)`, `Bash(gh pr checks *)`, `Bash(gh pr ready *)`, `Bash(gh run view *)`
   - Each `workflow.worktreeSetup` command
   
   Keep every existing `deny` rule. Deny overrides allow.
2. Make sure `.claude/.gitignore` exists, so `worktrees/`, `state/` and `tmp/` stay out of git.
3. Exclude `.claude/` from every tool that scans the tree, so worktree copies under `.claude/worktrees/` don't double-count: tsconfig `exclude`, eslint ignores, test runner excludes, formatter ignores, Tailwind or other content globs, Python tool excludes. Show each change.

## Phase 4: CLAUDE.md and agents

1. **CLAUDE.md**: fill the project paragraph, the Commands table (matching `kit.json`), "Where things live", the confirmed hard rules, and conventions observed in the code (cite the files). Keep it under ~100 lines.
2. **spec-reviewer**: add a "Project-specific checks" section with 3–6 checks derived from the hard rules.
3. **test-runner** and **test-auditor**: add a short "Reading this stack's output" section describing where file:line, test names, and expected/actual values appear.
4. **schema-reviewer**: fill "Project data rules" (from `docs/03-data-model.md` and `.claude/rules/database.md`) and the migration tool's specifics (directory, naming, rollback). If there's no database, propose deleting it and ask.
5. **ui-verifier**: if there's no UI, propose deleting it and ask. Otherwise confirm Node is installed (`node --version`) for the Playwright MCP server.

## Phase 5: GitHub files

1. **`.github/workflows/ci.yml`**:
   - Replace the "not configured" step with this stack's setup (runtime action at its current major version, dependency cache, install) and the `verify.full` equivalents in Linux syntax.
   - If there's a database, enable the Postgres (or matching) service block and the migrate step.
   - If there are end-to-end tests, enable that job.
   - Set `on.push.branches` to `workflow.baseBranch`.
   - Keep the task-file parse step and the job name `verify`.
2. **`.github/pull_request_template.md`**: leave as is unless the user wants changes.
3. **`claude-pr-review.yml`** and **`claude.yml`** (optional): explain what each does and ask whether to keep them. Tell the user that `/install-github-app` sets up the GitHub App and the `CLAUDE_CODE_OAUTH_TOKEN` secret, and that it must be run in an attached terminal.
4. List the GitHub settings the user must change by hand (Claude can't and shouldn't change them):
   - Protect the base branch: require a PR, require the CI check, block force pushes, allow only the repository admin to bypass.
   - Settings → Actions → General → Workflow permissions: allow GitHub Actions to create pull requests only if they plan to use `claude.yml`.

## Phase 6: Docs scaffolding

1. Make sure `docs/tasks/_TEMPLATE.md` and `docs/decisions.md` exist. Seed `decisions.md` with decisions already visible in `docs/02-architecture.md` and `docs/03-data-model.md` that it doesn't already hold, one row each, marked `(seeded)`.
2. Run `.claude/scripts/build-index.ps1` to generate `INDEX.md`. It's git-ignored via `docs/tasks/.gitignore` and regenerated on demand.
3. If a task list exists, offer `/new-task <path>`. Don't run it automatically.

## Phase 7: Smoke test and report

Run these and report each exit code:

```powershell
'{"tool_input":{"file_path":"<a real source file>"}}' | powershell -NoProfile -ExecutionPolicy Bypass -File .claude/hooks/post-edit-verify.ps1; $LASTEXITCODE   # expect 0
'{"tool_input":{"file_path":".env"}}' | powershell -NoProfile -ExecutionPolicy Bypass -File .claude/hooks/guard-protected-paths.ps1; $LASTEXITCODE        # expect 2
powershell -NoProfile -ExecutionPolicy Bypass -File .claude/scripts/build-index.ps1; $LASTEXITCODE                                                         # expect 0
powershell -NoProfile -ExecutionPolicy Bypass -File .claude/scripts/dispatch-approved.ps1 -DryRun                                                         # expect a summary, no dispatch
```

Final report:
- Files changed, one line each
- Command timing table
- Anything still `UNKNOWN`
- Manual GitHub steps remaining
- Suggested next step: commit (`chore: customize Claude Code kit v2`) and push via a PR
