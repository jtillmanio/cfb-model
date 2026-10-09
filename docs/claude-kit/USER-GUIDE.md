# User guide: Claude Code starter kit v2

How to install, set up, and use the kit day to day. For the reasoning behind the workflow (principles, autonomy levels, review layers, metrics), see `WORKFLOW.md`.

> **Starting a new project, or have only a brainstorm so far?** Follow `KICKOFF.md` first.
> **Existing project with docs, a design, CI, a database, or code already in place?** Follow `ADOPTING.md`. `/adopt` maps your files to the kit without renaming anything.
> **Project already on kit 2.3.x?** Follow `UPGRADING.md`.
> All of them hand back to §7 of this guide.

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
  implement ─► test-runner ─► test-auditor ─► spec / schema / UI review ─► draft PR ─► ready gates ─► ready
                 ▼
     you: owner gates + manual check ─► "accepted" ─► merge ─► (your deploy step, if any)
```

Done means merged and accepted, not deployed. If merging doesn't put the change live (a hand-run release, a deploy step), that step stays yours: Claude never starts it.

## 2. Prerequisites

| Requirement | Why | Check |
|---|---|---|
| Claude Code v2.1.139+ | Agent view and background sessions (Level 2) | `claude --version` |
| Git for Windows | Claude Code needs Git Bash on Windows; hooks run through it | `git --version` |
| Windows PowerShell 5.1 or PowerShell 7 | Hooks and scripts | `$PSVersionTable.PSVersion` |
| GitHub CLI, authenticated | PRs, CI watching | `gh auth status` |
| Node.js 18+ | The ui-verifier's Playwright browser server | `node --version` |
| A GitHub repository with a `main` (or other default) branch | PRs and CI | `git remote -v` |
| Claude Pro, Max, Team, or Enterprise | Agent view; subscription token for the GitHub Action | — |

## 3. Install

The kit lives in one central folder, **`C:\Development\tools\claude-code-starter-kit\`**, and an installer copies it into each project. You never copy files by hand.

### 3.1 One-time: put the kit in `C:\Development\tools`

```powershell
New-Item -ItemType Directory -Force C:\Development\tools | Out-Null
Expand-Archive "$HOME\Downloads\claude-code-starter-kit.zip" C:\Development\tools -Force
Get-ChildItem -Recurse C:\Development\tools\claude-code-starter-kit | Unblock-File
Get-Content C:\Development\tools\claude-code-starter-kit\VERSION
```

Result: `C:\Development\tools\claude-code-starter-kit\install-kit.ps1` plus the kit files and guides.

**Optional shortcut.** This adds an `Install-ClaudeKit` command to your PowerShell profile. It only works if your execution policy allows profiles to load (e.g. `RemoteSigned`).

```powershell
if (-not (Test-Path $PROFILE)) { New-Item -ItemType File -Force $PROFILE | Out-Null }
Add-Content $PROFILE 'function Install-ClaudeKit { powershell -NoProfile -ExecutionPolicy Bypass -File C:\Development\tools\claude-code-starter-kit\install-kit.ps1 @args }'
```

After that, `Install-ClaudeKit`, `Install-ClaudeKit -WhatIf`, and `Install-ClaudeKit -Upgrade` work from any project folder. The commands below use the full form so they work either way.

### 3.2 Install into a project (new or existing)

From the project root, with a clean working tree:

```powershell
git switch -c chore/add-claude-kit
powershell -NoProfile -ExecutionPolicy Bypass -File C:\Development\tools\claude-code-starter-kit\install-kit.ps1 -WhatIf   # preview
powershell -NoProfile -ExecutionPolicy Bypass -File C:\Development\tools\claude-code-starter-kit\install-kit.ps1
```

| Installer result | Meaning | Action |
|---|---|---|
| **Added** | New kit file copied | None |
| **Updated** | Guide refreshed in `docs/claude-kit/` | None |
| **To merge** | You already had this file and it differs (e.g. your own `CLAUDE.md` or `settings.json`). The kit's version went to `.kit-incoming\` | Ask Claude to merge (prompt below) |
| **Skipped** | The kit's placeholder `ci.yml`, because you already have CI | None |

If anything is listed under "To merge", tell Claude Code:

```text
Merge each file under .kit-incoming/ into the same path in the project. Keep all my existing content and
customizations; add only new kit sections, keys, rules, and steps. Show a one-line summary per file,
then delete .kit-incoming/.
```

The installer never overwrites your files, records the version in `.claude/kit-version`, and copies the guides to `docs/claude-kit/`. Commit by path and merge through a PR: `chore: add Claude Code starter kit`.

What the installer treats as whose:

| Kind | Files | On `-Upgrade` |
|---|---|---|
| **Owned** by the kit | `.claude/skills/<kit skills>/`, `.claude/hooks/`, `.claude/scripts/`, `docs/templates/`, `docs/tasks/_TEMPLATE.md`, the two `.gitignore` files | Overwritten. Never put project text in them |
| **Custom** (yours) | Agents, `CLAUDE.md`, `kit.json`, `settings.json`, `.claude/rules/`, `.github/` | Kit version written to `.kit-incoming/` for a merge |
| **Never shipped** | `.claude/project/*.md`, `.claude/skills/verify/`, your decisions log | Never touched |

Keep your own scripts out of the kit's folders (`.claude/scripts/`, `.claude/hooks/`). The installer won't overwrite a file it doesn't ship, but the file reads as part of the kit and an uninstall removes it. Put project scripts in `scripts/` or similar.

### 3.3 Updating the kit

1. Replace the central copy. It holds no project state, so this is safe:

   ```powershell
   Remove-Item -Recurse -Force C:\Development\tools\claude-code-starter-kit
   Expand-Archive "$HOME\Downloads\claude-code-starter-kit.zip" C:\Development\tools -Force
   Get-ChildItem -Recurse C:\Development\tools\claude-code-starter-kit | Unblock-File
   ```

2. In each project, on a `chore/` branch:

   ```powershell
   powershell -NoProfile -ExecutionPolicy Bypass -File C:\Development\tools\claude-code-starter-kit\install-kit.ps1 -Upgrade -WhatIf
   powershell -NoProfile -ExecutionPolicy Bypass -File C:\Development\tools\claude-code-starter-kit\install-kit.ps1 -Upgrade
   ```

   `-Upgrade` overwrites kit-owned files (skills, hooks, scripts, templates). Files you customize (agents, `CLAUDE.md`, `kit.json`, `settings.json`, `.claude\rules\`, `.github\`) go to `.kit-incoming\` for merging as usual.
3. Read the new entries in `docs/claude-kit/CHANGELOG.md`, and `docs/claude-kit/UPGRADING.md` for a minor-version upgrade. Re-run `/customize-kit` if it says so; from 2.4 it detects an older configuration and proposes each change.
4. Restart Claude Code.

Never fix a kit behaviour by editing a kit skill, hook, or script: the next `-Upgrade` overwrites it. Use a `workflow` switch in `kit.json` or a `.claude/project/<name>.md` file (§12, "Changing kit behaviour").

### 3.4 Upgrade a project from v1

1. Run the installer with `-Upgrade` (§3.3 step 2), then merge `.kit-incoming\`.
2. Add the new front matter fields to existing task files. Tell Claude Code: "Add `autonomy`, `ui`, `plan_status` and `planned_at_commit` to every task file per `docs/tasks/_TEMPLATE.md`. Use `attended` and `none` unless the task is clearly unattended-eligible."
3. Delete the committed board, since it is now generated locally: `git rm --cached docs/tasks/INDEX.md`
4. Restart Claude Code and run `/customize-kit`. It keeps your existing values and fills in the new sections.

## 4. First-time setup

1. **Restart Claude Code** in the project root, so it picks up the new agents and skills.
2. **Confirm everything loaded:**
   - Type `/` and confirm `implement-task`, `next-task`, `plan-batch`, `new-task`, `customize-kit`, `adopt`, `product-brief`, `architecture`, `skeleton`, and `milestones` appear.
   - Type `@` and confirm `spec-reviewer`, `test-runner`, `test-auditor`, `schema-reviewer`, and `ui-verifier` appear.
   - Run `/hooks` and confirm two PreToolUse entries (Read, and Edit|Write) and one PostToolUse entry.
3. **Run `/customize-kit` on Opus** (`/model opus` first). It:
   - detects your stack and asks you to confirm it, along with 3–6 hard rules, the files to protect, the commands Claude must never run (deploys, releases, production data), and whether parallel sessions would share a test database;
   - fills `kit.json`, including the `workflow` switches, and runs every command once, reporting timings;
   - adds permission allow-rules (Bash and PowerShell) so unattended sessions don't stall on prompts for routine commands, and deny rules for your deploy commands and production env files;
   - excludes `.claude/` from your linters, typechecker, and test runner, so worktree copies aren't scanned;
   - fills `CLAUDE.md` and `.claude/rules/git.md`, writes each agent's project file in `.claude/project/`, generates the `/verify` skill, and fills in `ci.yml`;
   - runs the smoke tests.

   Expect 20–40 minutes, with two stops for your input.
4. **Accept the Playwright browser server.** The first time the ui-verifier runs, Claude Code asks you to approve its server. If it reports a missing browser, run `npx playwright install chromium` once.
5. Commit the customization on a branch and merge it through a PR.

## 5. GitHub setup

Do these once per repository, in the GitHub web UI. Claude can't change them, and shouldn't.

### 5.1 Protect the base branch

Settings → Rules → Rulesets → **New branch ruleset**:

| Setting | Value |
|---|---|
| Enforcement | Active |
| Target branches | Default branch |
| Bypass list | Repository admin (for emergencies; plans and docs go through PRs like everything else) |
| Restrict deletions | On |
| Require a pull request before merging | On, required approvals **0** (you can't approve your own PR) |
| Require status checks to pass | On; add the CI job name (`workflow.ciJobName`, `verify` for the kit's `ci.yml`) |
| Block force pushes | On |

**No rulesets available?** GitHub returns 403 for rulesets on a private repository on the free plan. Then nothing on GitHub stops a push to the base branch. The settings deny rules (`Bash(...)` and `PowerShell(...)`) and `.claude/rules/git.md` are the only guard; `/customize-kit` checks this and writes it into `git.md`. Don't remove those deny rules.

### 5.2 Claude in GitHub Actions (optional, needed for the PR review and Level 3)

1. In Claude Code, in an attached terminal (not a background session), run `/install-github-app`.
2. Choose the subscription token option. It installs the Claude GitHub App and saves a `CLAUDE_CODE_OAUTH_TOKEN` secret.
3. When asked which workflows to add, skip them. The kit already includes `claude-pr-review.yml` and `claude.yml`, preconfigured for that secret.
4. Delete `claude.yml` if you don't want `@claude` in issues.

Until the secret exists, both workflows skip their steps and pass with a notice, so a PR leaving draft doesn't get a red check.

## 6. Writing tasks

| Step | You do | Result |
|---|---|---|
| 1 | `/milestones` (see KICKOFF.md Stage 6), or write your own task list | `docs/tasklist.md` with milestones and task stubs |
| 2 | `/new-task docs/tasklist.md M1` (Opus) | One `TASK-###-slug.md` per stub in that milestone, status `Draft`, with checkable ACs, sizing, autonomy, and ui flags |
| 3 | Review each file: tighten ACs, fix dependencies, adjust `autonomy` | Specs you trust |
| 4 | Set `status: Ready` on the ones to build next | Eligible for pickup |
| 5 | Commit them by path on a `docs/` branch, open a PR, merge it | The base branch (and background sessions) see them |

Add a single task any time with `/new-task <short description>`.

**Acceptance criteria never copy a number from a mockup or from prose.** Figures in designs are sample data. An AC asserts a relationship ("the filter hides exactly the blocked rows") or builds its own fixture ("given a run with 3 of 10 read, shows 3 / 10"); spec-reviewer flags one that doesn't.

**Roadmap-led projects.** If your project's phased roadmap (with a check line per item) stays the source of truth, set `workflow.roadmap` in `kit.json`. Then:

- `/new-task 1.2 1.1 1.6` converts one sitting at a time and copies each item's check line verbatim into the ACs;
- task files stay `TASK-###` (the scripts need that) but are titled `1.2 Undo`;
- branches, commit areas, and PR titles use the roadmap ID;
- spec-reviewer judges against the roadmap check, and reports a task file that disagrees as a SPEC GAP;
- `/milestones --coverage` checks that every feature, screen, and entity has a roadmap item, and adds the gaps to the roadmap rather than writing a task list.

Three status records, one owner each: the roadmap checkbox is ticked in the task's own PR (Claude); the task file goes to `Review` (Claude) and to `Done` only when you say "accepted"; an optional status page (`workflow.statusDoc`) is regenerated from the roadmap, never from task files, by you or by Claude on request.

**What makes a task `unattended`:** small or medium within one layer, Sonnet-implementable, follows an existing pattern, every AC automatable, and no schema, auth, ETL, or deletion. Everything else stays `attended`.

## 7. Level 1: attended, one task at a time

```
/clear
/model opus
/next-task            (or /implement-task TASK-014 to choose yourself)
```

What happens, and where you're needed:

| Phase | Claude does | You do |
|---|---|---|
| Preflight | Checks dependencies, checkable ACs, clean tree; creates `task/...` branch | Answer if it stops (vague AC, dirty tree) |
| Plan | Writes steps, files, a test per AC, risks | **Gate**: approve or amend. Then optionally `/model sonnet` for implementation |
| Implement | Tests first, then code; hooks check every edit | Answer questions |
| Verify | test-runner, then a checkpoint commit | — |
| Test audit | test-auditor proves the tests fail without the change | — |
| Review | spec-reviewer, plus schema-reviewer and ui-verifier as relevant | Answer spec gaps |
| Close out | Fills the task file; asks "Push and open a draft PR?" | Say yes |
| Ready gates | Checks each gate in `workflow.readyGates` it can (default: `verify.full`, then CI), fixes failures (max 2 rounds), marks the PR ready | Do the gates marked `owner` |
| Report | PR link, owner gates, manual steps with expected results, your next steps | Manual check → reply "accepted" → merge → deploy, if your project has that step |

Rough guide for an S/M task: 30–60 minutes end to end, of which 5–15 need you. Track your real numbers in the task metrics.

## 8. Level 2: batch-planned, unattended dispatch

Use this for `autonomy: unattended` tasks once your metrics are on target (see WORKFLOW.md).

### 8.1 Plan in a batch (one sitting)

```
/clear
/model opus
/plan-batch 4
```

Run it on an up-to-date base branch with a clean tree. Claude plans the next 4 Ready tasks, writes each `## Plan`, sets `plan_status: proposed`, and commits nothing, so each `planned_at_commit` is a base-branch commit that survives the squash merge below. Then:

1. Review with `git diff docs/tasks`. Edit plans directly, or ask Claude for changes.
2. Approve: change to `plan_status: approved`, or tell Claude "approve TASK-014 and TASK-016".
3. Move the plans to a branch and open a PR (Claude can do this): `git switch -c docs/plans-<date>`, commit the task files by path, push, `gh pr create`.
4. Merge the PR.
5. `git switch main; git pull --ff-only`, then dispatch (§8.2).

The dispatcher only sees plans committed on the base branch, and nothing is committed there directly, so plans always arrive through a PR.

### 8.2 Dispatch

From the main checkout, on the base branch:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .claude/scripts/dispatch-approved.ps1 -DryRun   # shows what would start and why others won't
powershell -NoProfile -ExecutionPolicy Bypass -File .claude/scripts/dispatch-approved.ps1
```

Each eligible task (Ready, plan approved, unattended, dependencies Done) starts as a background session named after its task ID, up to `workflow.wipLimit` (default 2).

**Shared test resources cap the WIP limit.** If parallel worktrees would share a stateful test resource (one test database that the tests reset or truncate, fixed ports, files on disk), two sessions running tests at once break each other. `/customize-kit` asks, and sets `wipLimit: 1` with the reason in `_wipLimitReason`, which the dispatcher prints. To raise it, give each worktree its own resource: a per-worktree test database created in `workflow.worktreeSetup`, ports derived from the task number. Each session moves into its own worktree under `.claude/worktrees/` before editing, runs `worktreeSetup`, and works through the full loop.

### 8.3 Monitor

```powershell
claude agents
```

| You see | Meaning | Action |
|---|---|---|
| Working | Session is running | Nothing |
| Needs input (yellow) | It asked a question or needs a permission | `Space` to peek, type the answer, `Enter`. Attach with `→` for permission dialogs |
| Ready for review, PR label yellow | PR open, CI running or failing | Wait; the session fixes CI itself (2 rounds) |
| Ready for review, PR label green | CI passed, PR marked ready | Review it (section 10) |
| Failed / Blocked report | Hit a round limit or a stale plan | See section 11 |

Each background session uses your subscription quota independently, so two in parallel use quota about twice as fast as one.

### 8.4 Accept and continue

1. Review the PR and do the manual check (section 10).
2. In agent view, peek at the session and reply `accepted`. It sets `status: Done`, commits, and pushes.
3. Merge the PR on GitHub (squash recommended). If your project deploys separately (the **Deploy** role), run that step; merged is not live.
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

1. **Acceptance criteria and "How it was verified".** Every reviewer and gate row should say PASS, APPROVE, or green. Rows marked `owner` are yours to check. A row that ran only in CI, or can only be checked after merge, says why. Anything else, ask in the session.
2. **Files changed tab.** Look for surprise files outside the plan. spec-reviewer flags these, but you're the last check.
3. **Claude's review comments**, if `claude-pr-review.yml` is installed. Resolve or dismiss each one.
4. **Manual verification steps.** Run them on the branch: `git fetch; git switch task/...`, start the app, follow the steps, compare against the expected results.
5. **Follow-ups.** Candidate tasks, and candidate decisions to record if `workflow.decisions` is `propose`.
6. **Reply `accepted`** to the session, or edit `status: Done` in the PR yourself.
7. **Merge.** Branch protection blocks the merge until the CI job is green. Then run your deploy step, if the project has one.

## 11. Handling problems mid-task

| Situation | What you'll see | What to do |
|---|---|---|
| Vague AC | Preflight stops with proposed rewrites | Edit the AC, commit, re-run |
| Plan stale (planned files changed since approval) | Unattended session stops: `plan stale` | `/plan-batch TASK-0xx` to re-plan, approve, push, re-dispatch (`-Release TASK-0xx` first) |
| Spec gap found in review | Session asks you | Decide; Claude never rewrites ACs itself |
| Round limit hit (verify 3, audit 2, review 2, ready gates 2) | `status: Blocked`, `## Blocked` section, `[BLOCKED]` draft PR | Read the hypothesis; fix the spec or split the task; or attach and pair with it |
| A ready gate needs something only you can do (a failed preview that needs its database reset, a secret) | The session stops and names the action; the PR stays draft | Do it, then tell the session to re-check the gates |
| Test audit can't restore the tree | `NOT RUN` in capitals | Stop. Inspect with `git status` and `git diff` in that worktree before doing anything else |
| Wrong task dispatched / want to abandon | — | Stop the session (`Ctrl+X`), then `dispatch-approved.ps1 -Release TASK-0xx` |

## 12. Reference

### Skills

| Command | Use it to |
|---|---|
| `/adopt [hints]` | Map an existing project's docs, design, and toolchain to kit roles; extract decisions; gap report |
| `/product-brief [notes path]` | Turn brainstorm notes into a brief, a feature list with IDs and a screen inventory, and a Claude Design prompt |
| `/architecture` | Choose the stack via option tables; write the architecture doc and seed decisions |
| `/skeleton` | Build the walking skeleton: scaffold, scripts, one end-to-end slice, tests, CI |
| `/milestones [MVP or Next]` | Break scope into demoable milestones and task stubs with a coverage check |
| `/milestones --coverage [roadmap]` | Check an existing roadmap's coverage of features, screens, and entities; add the gaps to it as numbered items with a check line. Writes no new file |
| `/customize-kit` | Tailor the kit to a project. Run once, and again after upgrades (it detects a 2.3.x setup) |
| `/new-task <description or path [M#] or roadmap IDs>` | Create task files with checkable ACs; bulk-convert a task list one milestone at a time, or a roadmap one sitting at a time |
| `/verify` | Generated per project by `/customize-kit`: run `verify.full` before a push and report the actual output |
| `/next-task [--dry-run]` | Pick the best Ready task (respecting WIP and dependencies) and implement it attended |
| `/implement-task <ID> [--unattended]` | Run the full loop for one task |
| `/plan-batch [N \| IDs]` | Plan several tasks for approval in one sitting |

### Agents

| Agent | Model | Writes? | Job |
|---|---|---|---|
| test-runner | Haiku | No | Runs `verify.full`; returns failures only |
| test-auditor | Sonnet | Temporary restore only | Proves tests fail without the change, with each configured runner |
| spec-reviewer | Opus | No | ACs and the roadmap check, plan, scope, hard rules, decisions, UX floor |
| schema-reviewer | Opus | No | Migrations, constraints, data safety, test isolation |
| ui-verifier | Sonnet | No (browser only) | Signs in if needed; clicks through UI ACs at each `ui.viewports` width; UX floor |

Each agent reads `.claude/project/<agent-name>.md` first, if it exists, as its project section: this stack's output formats, project checks, sign-in details, limits. `/customize-kit` writes these files. The agent's safety rules (read-only, the test-auditor's restore rules, never reading a production env file) can't be relaxed there.

**Model and effort.** The `model:` line in an agent's front matter picks its model (`haiku`, `sonnet`, `opus`, or `inherit`). An optional `effort:` line (`low`, `medium`, `high`, `xhigh`, `max`; availability depends on the model) sets its reasoning effort, e.g. `model: sonnet` plus `effort: high` for a cheaper reviewer that still thinks hard. `/customize-kit` offers to set both per reviewer. They're the only project edits that belong inside an agent file; keep them when you merge an upgrade.

### Scripts (`.claude/scripts/`)

| Script | Use it to |
|---|---|
| `build-index.ps1 [-Check]` | Regenerate `docs/tasks/INDEX.md` (local, git-ignored) and list warnings |
| `dispatch-approved.ps1 [-DryRun] [-Max N] [-PermissionMode m] [-Release IDs]` | Start background sessions for eligible tasks |

### Hooks (`.claude/hooks/`)

| Hook | When | Does |
|---|---|---|
| `guard-protected-paths.ps1` | Before Edit/Write | Blocks edits to `protectedPaths` |
| `guard-large-reads.ps1` | Before Read | Blocks a whole-file read of a `largeFiles` entry (any read, with `always`) and returns its hint |
| `post-edit-verify.ps1` | After Edit/Write | Runs the `verify.fast` checks whose extensions match the edited file |

For huge files Claude reads often (a design export with dozens of screens, a long roadmap), add a small section-printer script, e.g. `scripts/screen.ps1 <screen-id>` or `scripts/task.ps1 <roadmap-id>`, and name it in the `largeFiles` hint.

### Task front matter

| Field | Values | Set by |
|---|---|---|
| `status` | Draft, Ready, In progress, Review, Done, Blocked | You: Ready, Done. Claude: the rest |
| `depends_on` | `[TASK-012, ...]` | `/new-task`, you |
| `size` | S, M (L only with `workflow.splitPolicy: never-split`) | `/new-task` |
| `model` | sonnet, opus | `/new-task`, you |
| `autonomy` | attended, unattended | `/new-task`, you |
| `ui` | true, false | `/new-task` |
| `plan_status` | none, proposed, approved | Claude: proposed. You: approved |
| `planned_at_commit` | short SHA | Claude, when planning |

### kit.json keys

Every key is optional. A missing key takes the default below, which is the 2.3.1 behaviour except where marked **2.4 default**.

| Key | Default | Controls |
|---|---|---|
| `verify.sourceExtensions` | `[]` (every file) | Which edited files string `fast` entries run on |
| `verify.fast` | `[]` | Post-edit checks. Each entry is a command string (runs on `sourceExtensions`) or `{ "command", "extensions" }` (runs only on those extensions). `{file}` = the edited file |
| `verify.full` | `[]` | What test-runner and `/verify` run |
| `verify.maxOutputLines` | `60` | Lines of a failing fast check fed back to Claude |
| `protectedPaths` | secrets, keys, `INDEX.md` | `[{ pattern, reason }]`: files the Edit/Write tools can't touch |
| `largeFiles` | `[]` | `[{ pattern, hint, always? }]`: files the Read tool can't read whole (or at all, with `always`) |
| `workflow.baseBranch` | `main` | The branch PRs target; never committed on directly |
| `workflow.wipLimit` / `_wipLimitReason` | `2` / — | Tasks in progress or review at once; the reason it is lower, printed by the dispatcher |
| `workflow.openPullRequests` / `waitForCi` / `maxCiFixRounds` | `true` / `true` / `2` | Whether to open PRs, check the ready gates, and how many fix rounds |
| `workflow.unattendedPermissionMode` | `acceptEdits` | Permission mode for dispatched sessions |
| `workflow.worktreeSetup` / `worktreeCopyFiles` | `[]` | Commands and untracked files a fresh worktree needs |
| `workflow.staging` | `by-path` (**2.4 default**) | `by-path`: stage named files, never `git add -A`. `all`: the 2.3.1 behaviour |
| `workflow.commitFormat` | `conventional` | `conventional` (`feat(TASK-014): …`) or `area` (`task 1.3: …`) |
| `workflow.branchPrefixes` | `task/`, `fix/`, `docs/`, `chore/` | Allowed branch prefixes; `/customize-kit` adds a push allow-rule for each |
| `workflow.taskBranch` | `task/{id}-{slug}` | A task's branch name. `{type}/{id}-{slug}` picks the prefix that fits the task (`feat/`, `fix/`, …), as `.claude/rules/git.md` defines them |
| `workflow.ciJobName` | `verify` | The CI job branch protection and the `ci` gate require |
| `workflow.readyGates` | `["verify.full", "ci"]` | Ordered checks before `gh pr ready`. Built-ins `verify.full` and `ci`, or `{ name, check, by: claude\|owner, when: always\|ui\|[globs], failureLog, ownerFix }` |
| `workflow.decisions` | `append` | `append`: close-out adds decisions to the log. `propose`: they go under the PR's Follow-ups for the owner |
| `workflow.splitPolicy` | `split` | `split`: oversized tasks are split. `never-split`: one task, one branch, one PR, `attended` |
| `workflow.afterMerge` | `""` | A closing line for every final report, e.g. "After merge, run Release to put it live." |
| `workflow.allowForceWithLease` | `false` | `true` drops that deny rule; rebase, own branch only, never plain `--force` |
| `workflow.roadmap` | `null` | `{ path, idPattern, checkLabel }`: roadmap-led mode (§6) |
| `workflow.statusDoc` | `""` | A committed status page regenerated from the roadmap |
| `testAudit.testPathPatterns` | common test globs | What counts as a test file |
| `testAudit.run` | `""` | Runs specific test files, `{tests}`; the single-runner fallback |
| `testAudit.runners` | `[]` | `[{ pattern, run, each?, dir? }]`: one per test runner; `each: true` runs one file at a time; `dir` runs it from a subfolder with test paths relative to it (monorepos) |
| `testAudit.setup` | `""` | Runs once before the dynamic check, e.g. reset the test database to the pre-task schema |
| `testAudit.implementationExtensions` | `[]` (= `verify.sourceExtensions`) | Extensions the auditor reverts as implementation |
| `testAudit.implementationPaths` | `[]` | Paths always reverted as implementation, e.g. migration metadata |
| `ui.baseUrl` / `ui.startCommand` / `ui.portBase` | `""` / `""` / `3100` | Dev server, with `{port}` |
| `ui.viewports` | phone 390, tablet 768, desktop 1440 | Widths ui-verifier checks |
| `ui.designFiles` | `[]` | Committed design sources |
| `ui.redrawFiles` | `[]` | Design files a UI task updates in the same PR when it changes a screen; never protected |
| `ui.auth` | `null` | `{ loginPath, envFile, secretVar, steps }`: how ui-verifier signs in. It reads only that variable's line |

### Changing kit behaviour

The kit's skills, hooks, and scripts are overwritten by `-Upgrade`, so a project never edits them. Instead:

1. **A `workflow` switch**, when one exists for the behaviour (table above).
2. **`.claude/project/<name>.md`** for anything a switch can't express. `<name>` is a skill (`implement-task`, `new-task`, `plan-batch`, `milestones`, `next-task`, `customize-kit`, `adopt`, `architecture`, `skeleton`, `product-brief`) or an agent (`test-runner`, `test-auditor`, `spec-reviewer`, `schema-reviewer`, `ui-verifier`). The skill or agent reads it at the start, and it wins where it conflicts, except for the kit's floor: never push to or merge the base branch, never rewrite ACs, never deploy, never skip the plan gate, and the agents' read-only and restore rules.
3. **`CLAUDE.md` and `.claude/rules/`** for rules about the project itself. Don't write counter-instructions to the kit's skills there ("even though the skill says…"); that's what the first two are for.

### Project docs roles

Every skill and agent finds documents through the "Project docs" table in `CLAUDE.md`. Use `—` for a role the project doesn't have.

| Role | What it is | Used by |
|---|---|---|
| Product brief, Features, Screen inventory, Design brief | Scope and design intent | `/product-brief`, `/architecture`, `/milestones`, `/new-task` |
| Design source of truth, Design tokens, Reference screenshots, Design process notes | The design | `/new-task`, ui-verifier, `/skeleton` |
| UX floor | The minimum every UI task meets (`docs/templates/ux-floor.md`) | `/new-task` (one AC per UI task), spec-reviewer, ui-verifier |
| Architecture, Data model, Domain specs | The system | Everything |
| Roadmap, Task list, Tasks | The work | `/milestones`, `/new-task`, `/implement-task` |
| Decisions | The decisions log, with its ID prefix; any path | Everything; `/implement-task` appends (or proposes) rows |
| Review findings | Review protocol and findings ledger (`docs/templates/review-*.md`) | Commits and PRs cite finding IDs |
| Deploy | How merged code goes live; `—` if merging deploys | Final reports (`workflow.afterMerge`) |
| Owner runbook, Owner checklist | Steps and decisions only the owner takes | Final reports list your next steps; Claude never runs runbook commands unless asked |

### Permissions

The settings template denies, for both the `Bash` and `PowerShell` tools (on Windows the PowerShell tool could otherwise do what a Bash rule forbids):

| Denied | Why |
|---|---|
| `git push origin main` / `master` (and with arguments) | Nothing reaches the base branch except through a PR |
| `git push --force *`, `-f *`, `--force-with-lease *` | No rewriting pushed history (`allowForceWithLease` drops the last one) |
| `gh pr merge *` | You merge |
| `git reset --hard *`, `git clean -fdx *` | No destroying uncommitted work |
| `git add -A*`, `git add --all*`, `git add .`, `git commit -a*`, `git commit --all*` | Staging by path: never sweep in your edits, env files, or scratch output |

`/customize-kit` adds allow-rules for your verify, test, git, and gh commands and one push rule per branch prefix, plus deny rules for your deploy, release, production-data, and destructive-reload commands and `Read(...)` denies for production env files. Deny always beats allow.

## 13. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Skills or agents missing | Session started before install | Restart Claude Code |
| Hook never fires | Not registered or merge dropped it | `/hooks`; `claude --debug` and edit a file |
| `powershell: command not found` in hook output | Git Bash PATH | Use `C:/Windows/System32/WindowsPowerShell/v1.0/powershell.exe` in `settings.json` |
| Hook path error | Your version runs hooks in PowerShell | Change `$CLAUDE_PROJECT_DIR` to `$env:CLAUDE_PROJECT_DIR` and add `"shell": "powershell"` to each hook |
| Every edit reports failures | Baseline not green, or slow check in `fast` | Fix the baseline; move slow checks to `full` |
| Edits to `.css`, `.sql`, `.py` (or ignored paths) fail the linter | A `fast` command runs on extensions it doesn't accept | Use the object form `{ "command", "extensions" }`, or the linter's flag for ignored files (eslint `--no-warn-ignored`) |
| "Blocked: … matches largeFiles pattern" | The guard stopped a whole-file read | Read it in parts (offset/limit), or use the script the hint names |
| Claude committed or staged an owner's file | `workflow.staging` set to `all` | Set it to `by-path` and restore the deny rules |
| Lint or tests pick up duplicate files | `.claude/worktrees/` not excluded | Re-run `/customize-kit` Phase 3, or add `.claude/` to each tool's ignore list |
| `claude agents` lists agents and exits instead of opening agent view | Claude Code too old | `claude update` |
| Dispatcher: "docs/tasks has uncommitted changes" | Approved plans not committed on the base branch | Move them to a `docs/plans-<date>` branch, open a PR, merge it, pull, re-run |
| Dispatcher: nothing eligible | Shown under "Not eligible" with reasons | Fix the named reason |
| Session stuck in Needs input on a permission | Command not in allow-rules | Attach and approve; add the rule to `settings.json` so it doesn't recur |
| Session can't start: `Workspace not trusted` | Running the dispatcher before trusting the folder | Run `claude` once in the project and accept the trust dialog |
| Worktree session fails on missing dependencies or env | `worktreeSetup` / `worktreeCopyFiles` incomplete | Add the missing command or file in `kit.json` |
| Two sessions fight over the dev server port | Same task number mod 100 | Change `ui.portBase` or finish one first |
| Parallel sessions break each other's tests | One shared test database (or ports, files) | `wipLimit: 1` with a `_wipLimitReason`, or a per-worktree test database in `worktreeSetup` |
| Parallel schema tasks corrupt the local DB | Shared database | Keep schema tasks `attended` and serial (the default) |
| `gh pr checks --watch` never finishes | CI not triggered | Check the workflow's `on:` triggers and that Actions is enabled |
| A ready gate fails but `gh run view` shows nothing | The check isn't an Actions run (e.g. a hosting provider's preview build) | Give the gate a `failureLog` naming where its log lives |
| Claude PR review job fails on every PR | Workflow from before 2.4 and no `CLAUDE_CODE_OAUTH_TOKEN` | Take the 2.4 `claude-pr-review.yml`, which skips without the secret, or run `/install-github-app` |
| ui-verifier: browser missing | Playwright browsers not installed | `npx playwright install chromium` |
| ui-verifier stuck on a sign-in page | `ui.auth` not set | Set `ui.auth` (`loginPath`, `envFile`, `secretVar`, `steps`) |
| `/implement-task` starts when you only mention a task | Model-invoked skill | Say "don't start it" or ask about the task file instead of the task. Don't edit the skill: `-Upgrade` overwrites it |

## 14. Uninstall

```powershell
git rm -r .claude/agents .claude/skills .claude/hooks .claude/scripts .claude/project .claude/kit.json .claude/.gitignore docs/tasks/.gitignore docs/templates
git rm .github/workflows/claude.yml .github/workflows/claude-pr-review.yml
```

Then remove the `hooks` and kit `permissions` blocks from `.claude/settings.json`, the kit sections from `CLAUDE.md`, and `.claude/rules/git.md` if you don't want to keep its rules. Keep `docs/tasks/` and your decisions log; they're your project's history. Remove the GitHub App and secret only if no other Claude feature uses them.
