# User guide: Claude Code starter kit v2

How to install, set up, and use the kit day to day. For the reasoning behind the workflow (principles, autonomy levels, review layers, metrics), see `WORKFLOW.md`.

> **Starting a new project, or have only a brainstorm or design so far?** Follow `KICKOFF.md` first. It goes from idea → scope → design → architecture → walking skeleton → first tasks, then hands back to §7 of this guide.

## Contents

1. What the kit does
2. Prerequisites
3. Install
4. First-time setup
5. GitHub setup
6. Writing tasks
7. Level 1: attended, one task at a time
8. Level 2: batch-planned, unattended dispatch
9. Level 3: `@claude` from GitHub (optional)
10. Reviewing and merging a PR
11. Handling problems mid-task
12. Reference
13. Troubleshooting
14. Uninstall

---

## 1. What the kit does

The kit turns a list of task files into reviewed, CI-green pull requests, with two human gates per task: you approve the plan, and you approve the PR.

```
/new-task ─► task files (Draft) ─► you set Ready
                 │
     ┌───────────┴────────────────────────────────┐
     │ Level 1                                     │ Level 2
     │ /next-task or /implement-task               │ /plan-batch ─► you approve plans
     │ plan gate in-session                        │ dispatch-approved.ps1 ─► background sessions
     └───────────┬────────────────────────────────┘
                 ▼
  implement ─► test-runner ─► test-auditor ─► spec / schema / UI review ─► draft PR ─► CI ─► ready
                 ▼
     you: manual check ─► "accepted" ─► merge
```

## 2. Prerequisites

| Requirement                                                 | Why                                                         | Check                       |
| ----------------------------------------------------------- | ----------------------------------------------------------- | --------------------------- |
| Claude Code v2.1.139+                                       | Agent view and background sessions (Level 2)                | `claude --version`          |
| Git for Windows                                             | Claude Code needs Git Bash on Windows; hooks run through it | `git --version`             |
| Windows PowerShell 5.1 or PowerShell 7                      | Hooks and scripts                                           | `$PSVersionTable.PSVersion` |
| GitHub CLI, authenticated                                   | PRs, CI watching                                            | `gh auth status`            |
| Node.js 18+                                                 | The ui-verifier's Playwright browser server                 | `node --version`            |
| A GitHub repository with a `main` (or other default) branch | PRs and CI                                                  | `git remote -v`             |
| Claude Pro, Max, Team, or Enterprise                        | Agent view; subscription token for the GitHub Action        | —                           |

## 3. Install

### New project

Run from your project root in PowerShell. The working tree should be clean.

```powershell
# Copy without overwriting existing files from your custom path. Robocopy exit codes 0-3 mean success.
robocopy "C:\Development\tools\claude-code-starter-kit-v2" . /E /XC /XN /XO /XF README.md USER-GUIDE.md WORKFLOW.md CHANGELOG.md KICKOFF.md

# Keep the docs with the project
New-Item -ItemType Directory -Force docs\claude-kit | Out-Null
Copy-Item "C:\Development\tools\claude-code-starter-kit-v2\*.md" docs\claude-kit\ -Exclude CLAUDE.md

```

If robocopy skipped files you already had (usually `CLAUDE.md`, `.claude\settings.json`, `.github\pull_request_template.md`), copy each kit version alongside yours with a `.kit` suffix and ask Claude to merge it:

```powershell
Copy-Item "C:\Development\tools\claude-code-starter-kit-v2\.claude\settings.json" .\.claude\settings.kit.json

```

Then tell Claude Code: "Merge `.claude/settings.kit.json` into `.claude/settings.json`, keeping all existing hooks and permissions, then delete the .kit file."

Commit on a branch and merge it through a PR: `chore: add Claude Code starter kit v2`.

### Upgrade from v1

1. Commit or stash your work. Copy the v2 files over v1, overwriting this time, but keep your customized files:

   ```powershell
   robocopy "$env:TEMP\cc-kit\claude-code-starter-kit-v2" . /E /XF README.md USER-GUIDE.md WORKFLOW.md CHANGELOG.md KICKOFF.md CLAUDE.md kit.json settings.json /XD .github
   ```

2. Bring over the v2 config without losing your values. Copy `kit.json`, `settings.json` and `.github\` in as `.kit` files (as above), then tell Claude Code: "Merge the v2 keys from `.claude/kit.kit.json` into `.claude/kit.json` and the deny rules from `.claude/settings.kit.json` into `.claude/settings.json`, keeping my existing values. Add any `.github` kit files that don't exist yet."
3. Add the new front matter fields to existing task files. Tell Claude Code: "Add `autonomy`, `ui`, `plan_status` and `planned_at_commit` to every task file per `docs/tasks/_TEMPLATE.md`. Use `attended` and `none` unless the task is clearly unattended-eligible."
4. Delete the committed board, since it is now generated locally: `git rm --cached docs/tasks/INDEX.md`
5. Restart Claude Code and run `/customize-kit`. It keeps your existing values and fills in the new sections.

## 4. First-time setup

1. **Restart Claude Code** in the project root, so it picks up the new agents and skills.
2. **Confirm everything loaded:**
   - Type `/` and confirm `implement-task`, `next-task`, `plan-batch`, `new-task`, `customize-kit`, `product-brief`, `architecture`, `skeleton`, and `milestones` appear.
   - Type `@` and confirm `spec-reviewer`, `test-runner`, `test-auditor`, `schema-reviewer`, and `ui-verifier` appear.
   - Run `/hooks` and confirm one PreToolUse and one PostToolUse entry.
3. **Run `/customize-kit` on Opus** (`/model opus` first). It:
   - detects your stack and asks you to confirm it, along with 3–6 hard rules;
   - fills `kit.json` and runs every command once, reporting timings;
   - adds permission allow-rules so unattended sessions don't stall on prompts for routine commands;
   - excludes `.claude/` from your linters, typechecker, and test runner, so worktree copies aren't scanned;
   - fills `CLAUDE.md`, tailors the agents, and fills in `ci.yml`;
   - runs the smoke tests.

   Expect 15–30 minutes, with two stops for your input.

4. **Accept the Playwright browser server.** The first time the ui-verifier runs, Claude Code asks you to approve its server. If it reports a missing browser, run `npx playwright install chromium` once.
5. Commit the customization on a branch and merge it through a PR.

## 5. GitHub setup

Do these once per repository, in the GitHub web UI. Claude can't change them, and shouldn't.

### 5.1 Protect the base branch

Settings → Rules → Rulesets → **New branch ruleset**:

| Setting                               | Value                                                                  |
| ------------------------------------- | ---------------------------------------------------------------------- |
| Enforcement                           | Active                                                                 |
| Target branches                       | Default branch                                                         |
| Bypass list                           | Repository admin (lets you push plan approvals directly; Claude can't) |
| Restrict deletions                    | On                                                                     |
| Require a pull request before merging | On, required approvals **0** (you can't approve your own PR)           |
| Require status checks to pass         | On; add `verify` (the CI job name)                                     |
| Block force pushes                    | On                                                                     |

### 5.2 Claude in GitHub Actions (optional, needed for the PR review and Level 3)

1. In Claude Code, in an attached terminal (not a background session), run `/install-github-app`.
2. Choose the subscription token option. It installs the Claude GitHub App and saves a `CLAUDE_CODE_OAUTH_TOKEN` secret.
3. When asked which workflows to add, skip them. The kit already includes `claude-pr-review.yml` and `claude.yml`, preconfigured for that secret.
4. Delete `claude.yml` if you don't want `@claude` in issues.

## 6. Writing tasks

| Step | You do                                                              | Result                                                                                                                |
| ---- | ------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------- |
| 1    | `/milestones` (see KICKOFF.md Stage 6), or write your own task list | `docs/tasklist.md` with milestones and task stubs                                                                     |
| 2    | `/new-task docs/tasklist.md M1` (Opus)                              | One `TASK-###-slug.md` per stub in that milestone, status `Draft`, with checkable ACs, sizing, autonomy, and ui flags |
| 3    | Review each file: tighten ACs, fix dependencies, adjust `autonomy`  | Specs you trust                                                                                                       |
| 4    | Set `status: Ready` on the ones to build next                       | Eligible for pickup                                                                                                   |
| 5    | Commit and push to the base branch (admin bypass)                   | Background sessions see them                                                                                          |

Add a single task any time with `/new-task <short description>`.

**What makes a task `unattended`:** small or medium within one layer, Sonnet-implementable, follows an existing pattern, every AC automatable, and no schema, auth, ETL, or deletion. Everything else stays `attended`.

## 7. Level 1: attended, one task at a time

```
/clear
/model opus
/next-task            (or /implement-task TASK-014 to choose yourself)
```

What happens, and where you're needed:

| Phase      | Claude does                                                               | You do                                                                         |
| ---------- | ------------------------------------------------------------------------- | ------------------------------------------------------------------------------ |
| Preflight  | Checks dependencies, checkable ACs, clean tree; creates `task/...` branch | Answer if it stops (vague AC, dirty tree)                                      |
| Plan       | Writes steps, files, a test per AC, risks                                 | **Gate**: approve or amend. Then optionally `/model sonnet` for implementation |
| Implement  | Tests first, then code; hooks check every edit                            | Answer questions                                                               |
| Verify     | test-runner, then a checkpoint commit                                     | —                                                                              |
| Test audit | test-auditor proves the tests fail without the change                     | —                                                                              |
| Review     | spec-reviewer, plus schema-reviewer and ui-verifier as relevant           | Answer spec gaps                                                               |
| Close out  | Fills the task file; asks "Push and open a draft PR?"                     | Say yes                                                                        |
| CI         | Watches checks, fixes failures (max 2 rounds), marks ready                | —                                                                              |
| Report     | PR link, manual steps with expected results                               | Manual check → reply "accepted" → merge                                        |

Rough guide for an S/M task: 30–60 minutes end to end, of which 5–15 need you. Track your real numbers in the task metrics.

## 8. Level 2: batch-planned, unattended dispatch

Use this for `autonomy: unattended` tasks once your metrics are on target (see WORKFLOW.md).

### 8.1 Plan in a batch (one sitting)

```
/clear
/model opus
/plan-batch 4
```

Claude plans the next 4 Ready tasks, writes each `## Plan`, and sets `plan_status: proposed`. Then:

1. Review with `git diff docs/tasks`. Edit plans directly, or ask Claude for changes.
2. Approve: change to `plan_status: approved`, or tell Claude "approve TASK-014 and TASK-016".
3. Commit (Claude can do this) and **push the base branch yourself**.

### 8.2 Dispatch

From the main checkout, on the base branch:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .claude/scripts/dispatch-approved.ps1 -DryRun   # shows what would start and why others won't
powershell -NoProfile -ExecutionPolicy Bypass -File .claude/scripts/dispatch-approved.ps1
```

Each eligible task (Ready, plan approved, unattended, dependencies Done) starts as a background session named after its task ID, up to `workflow.wipLimit` (default 2). Each session moves into its own worktree under `.claude/worktrees/` before editing, runs `worktreeSetup`, and works through the full loop.

### 8.3 Monitor

```powershell
claude agents
```

| You see                           | Meaning                                   | Action                                                                            |
| --------------------------------- | ----------------------------------------- | --------------------------------------------------------------------------------- |
| Working                           | Session is running                        | Nothing                                                                           |
| Needs input (yellow)              | It asked a question or needs a permission | `Space` to peek, type the answer, `Enter`. Attach with `→` for permission dialogs |
| Ready for review, PR label yellow | PR open, CI running or failing            | Wait; the session fixes CI itself (2 rounds)                                      |
| Ready for review, PR label green  | CI passed, PR marked ready                | Review it (section 10)                                                            |
| Failed / Blocked report           | Hit a round limit or a stale plan         | See section 11                                                                    |

Each background session uses your subscription quota independently, so two in parallel use quota about twice as fast as one.

### 8.4 Accept and continue

1. Review the PR and do the manual check (section 10).
2. In agent view, peek at the session and reply `accepted`. It sets `status: Done`, commits, and pushes.
3. Merge the PR on GitHub (squash recommended).
4. Locally: `git switch main; git pull`, then re-run the dispatcher. Claims for Done tasks clear automatically, and newly unblocked tasks dispatch.
5. Delete the finished session in agent view (`Ctrl+X` twice). This removes its worktree.

## 9. Level 3: `@claude` from GitHub (optional)

With `claude.yml` installed, comment on an issue or PR:

```
@claude implement docs/tasks/TASK-021-fix-date-format.md following .claude/skills/implement-task/SKILL.md in unattended mode
```

Claude runs in GitHub Actions and opens a PR. Notes:

- Use this for small, unattended-eligible tasks with approved plans.
- The kit's PowerShell hooks don't run on the Linux runner, so CI is the verification.
- It uses your subscription through the token and consumes Actions minutes.

## 10. Reviewing and merging a PR

The PR body is pre-filled from `.github/pull_request_template.md`. Spend your 5–10 minutes here:

1. **AC checklist and automated evidence table.** Every row should say PASS or APPROVE. Anything else, ask why in the session.
2. **Files changed tab.** Look for surprise files outside the plan. spec-reviewer flags these, but you're the last check.
3. **Claude's review comments**, if `claude-pr-review.yml` is installed. Resolve or dismiss each one.
4. **Manual verification steps.** Run them on the branch: `git fetch; git switch task/...`, start the app, follow the steps, compare against the expected results.
5. **Reply `accepted`** to the session, or edit `status: Done` in the PR yourself.
6. **Merge.** Branch protection blocks the merge until `verify` is green.

## 11. Handling problems mid-task

| Situation                                           | What you'll see                                               | What to do                                                                                 |
| --------------------------------------------------- | ------------------------------------------------------------- | ------------------------------------------------------------------------------------------ |
| Vague AC                                            | Preflight stops with proposed rewrites                        | Edit the AC, commit, re-run                                                                |
| Plan stale (planned files changed since approval)   | Unattended session stops: `plan stale`                        | `/plan-batch TASK-0xx` to re-plan, approve, push, re-dispatch (`-Release TASK-0xx` first)  |
| Spec gap found in review                            | Session asks you                                              | Decide; Claude never rewrites ACs itself                                                   |
| Round limit hit (verify 3, audit 2, review 2, CI 2) | `status: Blocked`, `## Blocked` section, `[BLOCKED]` draft PR | Read the hypothesis; fix the spec or split the task; or attach and pair with it            |
| Test audit can't restore the tree                   | `NOT RUN` in capitals                                         | Stop. Inspect with `git status` and `git diff` in that worktree before doing anything else |
| Wrong task dispatched / want to abandon             | —                                                             | Stop the session (`Ctrl+X`), then `dispatch-approved.ps1 -Release TASK-0xx`                |

## 12. Reference

### Skills

| Command                                | Use it to                                                                                                      |
| -------------------------------------- | -------------------------------------------------------------------------------------------------------------- |
| `/product-brief [notes path]`          | Turn brainstorm notes into a brief, a feature list with IDs and a screen inventory, and a Claude Design prompt |
| `/architecture`                        | Choose the stack via option tables; write the architecture doc and seed decisions                              |
| `/skeleton`                            | Build the walking skeleton: scaffold, scripts, one end-to-end slice, tests, CI                                 |
| `/milestones [MVP or Next]`            | Break scope into demoable milestones and task stubs with a coverage check                                      |
| `/customize-kit`                       | Tailor the kit to a project. Run once, and again after upgrades                                                |
| `/new-task <description or path [M#]>` | Create task files with checkable ACs; bulk-convert a task list, one milestone at a time                        |
| `/next-task [--dry-run]`               | Pick the best Ready task (respecting WIP and dependencies) and implement it attended                           |
| `/implement-task <ID> [--unattended]`  | Run the full loop for one task                                                                                 |
| `/plan-batch [N \| IDs]`               | Plan several tasks for approval in one sitting                                                                 |

### Agents

| Agent           | Model  | Writes?                | Job                                               |
| --------------- | ------ | ---------------------- | ------------------------------------------------- |
| test-runner     | Haiku  | No                     | Runs `verify.full`; returns failures only         |
| test-auditor    | Sonnet | Temporary restore only | Proves tests fail without the change              |
| spec-reviewer   | Opus   | No                     | ACs, plan, scope, hard rules, decisions           |
| schema-reviewer | Opus   | No                     | Migrations, constraints, data safety              |
| ui-verifier     | Sonnet | No (browser only)      | Clicks through UI ACs at phone and desktop widths |

### Scripts (`.claude/scripts/`)

| Script                                                                        | Use it to                                                               |
| ----------------------------------------------------------------------------- | ----------------------------------------------------------------------- |
| `build-index.ps1 [-Check]`                                                    | Regenerate `docs/tasks/INDEX.md` (local, git-ignored) and list warnings |
| `dispatch-approved.ps1 [-DryRun] [-Max N] [-PermissionMode m] [-Release IDs]` | Start background sessions for eligible tasks                            |

### Task front matter

| Field               | Values                                           | Set by                             |
| ------------------- | ------------------------------------------------ | ---------------------------------- |
| `status`            | Draft, Ready, In progress, Review, Done, Blocked | You: Ready, Done. Claude: the rest |
| `depends_on`        | `[TASK-012, ...]`                                | `/new-task`, you                   |
| `size`              | S, M                                             | `/new-task`                        |
| `model`             | sonnet, opus                                     | `/new-task`, you                   |
| `autonomy`          | attended, unattended                             | `/new-task`, you                   |
| `ui`                | true, false                                      | `/new-task`                        |
| `plan_status`       | none, proposed, approved                         | Claude: proposed. You: approved    |
| `planned_at_commit` | short SHA                                        | Claude, when planning              |

### kit.json sections

| Section          | Controls                                                                               |
| ---------------- | -------------------------------------------------------------------------------------- |
| `verify`         | Commands for the post-edit hook (`fast`) and test-runner (`full`)                      |
| `protectedPaths` | Files Claude's Edit/Write tools can't touch                                            |
| `workflow`       | Base branch, WIP limit, PR and CI behavior, unattended permission mode, worktree setup |
| `testAudit`      | How tests are identified and run individually                                          |
| `ui`             | Dev server command and URL (`{port}`), viewports, design files                         |

## 13. Troubleshooting

| Symptom                                                              | Likely cause                                      | Fix                                                                                                                                    |
| -------------------------------------------------------------------- | ------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------- |
| Skills or agents missing                                             | Session started before install                    | Restart Claude Code                                                                                                                    |
| Hook never fires                                                     | Not registered or merge dropped it                | `/hooks`; `claude --debug` and edit a file                                                                                             |
| `powershell: command not found` in hook output                       | Git Bash PATH                                     | Use `C:/Windows/System32/WindowsPowerShell/v1.0/powershell.exe` in `settings.json`                                                     |
| Hook path error                                                      | Your version runs hooks in PowerShell             | Change `$CLAUDE_PROJECT_DIR` to `$env:CLAUDE_PROJECT_DIR` and add `"shell": "powershell"` to each hook                                 |
| Every edit reports failures                                          | Baseline not green, or slow check in `fast`       | Fix the baseline; move slow checks to `full`                                                                                           |
| Lint or tests pick up duplicate files                                | `.claude/worktrees/` not excluded                 | Re-run `/customize-kit` Phase 3, or add `.claude/` to each tool's ignore list                                                          |
| `claude agents` lists agents and exits instead of opening agent view | Claude Code too old                               | `claude update`                                                                                                                        |
| Dispatcher: "docs/tasks has uncommitted changes"                     | Approved plans not committed                      | Commit, push, re-run                                                                                                                   |
| Dispatcher: nothing eligible                                         | Shown under "Not eligible" with reasons           | Fix the named reason                                                                                                                   |
| Session stuck in Needs input on a permission                         | Command not in allow-rules                        | Attach and approve; add the rule to `settings.json` so it doesn't recur                                                                |
| Session can't start: `Workspace not trusted`                         | Running the dispatcher before trusting the folder | Run `claude` once in the project and accept the trust dialog                                                                           |
| Worktree session fails on missing dependencies or env                | `worktreeSetup` / `worktreeCopyFiles` incomplete  | Add the missing command or file in `kit.json`                                                                                          |
| Two sessions fight over the dev server port                          | Same task number mod 100                          | Change `ui.portBase` or finish one first                                                                                               |
| Parallel schema tasks corrupt the local DB                           | Shared database                                   | Keep schema tasks `attended` and serial (the default)                                                                                  |
| `gh pr checks --watch` never finishes                                | CI not triggered                                  | Check the workflow's `on:` triggers and that Actions is enabled                                                                        |
| ui-verifier: browser missing                                         | Playwright browsers not installed                 | `npx playwright install chromium`                                                                                                      |
| `/implement-task` auto-triggers when you only mention a task         | Model-invoked skill                               | Add `disable-model-invocation: true` to its front matter, then test that `/implement-task` still runs (one bug report says it may not) |

## 14. Uninstall

```powershell
git rm -r .claude/agents .claude/skills .claude/hooks .claude/scripts .claude/kit.json .claude/.gitignore docs/tasks/.gitignore
git rm .github/workflows/claude.yml .github/workflows/claude-pr-review.yml
```

Then remove the `hooks` and kit `permissions` blocks from `.claude/settings.json` and the kit sections from `CLAUDE.md`. Keep `docs/tasks/` and `docs/decisions.md`; they're your project's history. Remove the GitHub App and secret only if no other Claude feature uses them.
