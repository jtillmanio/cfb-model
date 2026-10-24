# Upgrading a project

For the owner of a project on an earlier kit 2.x, and for the Claude session that does the upgrade. What changed and why is in `CHANGELOG.md`; this guide is how to apply it. `.claude/kit-version` says which version a project is on.

| Project is on | Do |
|---|---|
| 2.7.x | [From 2.7 to 2.8](#from-27-to-28) |
| 2.6.x | One branch, one installer run (it puts 2.8 in place directly): step 1 of [From 2.7 to 2.8](#from-27-to-28), then steps 2–4 of [From 2.6 to 2.7](#from-26-to-27), then steps 2–6 of [From 2.7 to 2.8](#from-27-to-28) |
| 2.5.x | One branch, one installer run (it puts 2.8 in place directly): step 1 of [From 2.7 to 2.8](#from-27-to-28), then steps 2–4 of [From 2.5 to 2.6](#from-25-to-26), steps 2–4 of [From 2.6 to 2.7](#from-26-to-27), and steps 2–6 of [From 2.7 to 2.8](#from-27-to-28), and step 6 of [From 2.5 to 2.6](#from-25-to-26) after merging |
| 2.4.x | One branch, one installer run (it puts 2.8 in place directly): step 1 of [From 2.7 to 2.8](#from-27-to-28), then steps 2–4 of [From 2.4 to 2.5](#from-24-to-25), steps 2–4 of [From 2.5 to 2.6](#from-25-to-26), steps 2–4 of [From 2.6 to 2.7](#from-26-to-27), and steps 2–6 of [From 2.7 to 2.8](#from-27-to-28), and step 6 of [From 2.5 to 2.6](#from-25-to-26) after merging |
| 2.3.x | [From 2.3 to 2.4](#from-23-to-24) on one branch (the installer puts 2.8 in place directly; the branch name doesn't matter), then steps 3–4 of [From 2.4 to 2.5](#from-24-to-25), steps 2–4 of [From 2.5 to 2.6](#from-25-to-26), steps 2–4 of [From 2.6 to 2.7](#from-26-to-27), and steps 2–6 of [From 2.7 to 2.8](#from-27-to-28) on the same branch, and step 6 of [From 2.5 to 2.6](#from-25-to-26) after merging |

## From 2.7 to 2.8

2.8 has one change: the roadmap's checkboxes are kept in step with the task files, in every project whose roadmap (or task list) has them, not only in roadmap mode. A task's close-out ticks the items it finishes; close-out and accept also tick items other Done tasks finished and nobody ticked. The upgrade is one branch and one PR, and that PR also ticks the items finished before the upgrade.

### Behaviour changes

These apply as soon as `-Upgrade` replaces the skills, before you merge anything.

| Change | What you'll see | Opt out |
|---|---|---|
| **Tick doc** | Claude ticks the roadmap in roadmap mode (`workflow.roadmap.path`, as before), otherwise the **Roadmap** role's doc, or the **Task list** if there is no roadmap. Only a doc that already has done marks (`[ ]`/`[x]`, `☐`/`☑`, `⬜`/`✅`) is ticked; marks are never added | A doc with no marks is never touched |
| **Close-out ticks, without roadmap mode too** | `/implement-task` close-out ticks the items the task finishes, in the close-out commit. Without roadmap mode Claude matches items to the task's Goal and ACs and ticks only what it delivers in full. A partly delivered item stays open and the PR's **What** says what remains | A line in `.claude/project/implement-task.md`, e.g. "Never tick the roadmap; the owner does" |
| **The sweep** | Close-out and "accepted" also tick open items that Done tasks finished, so a task you marked Done by hand is caught by the next one. The ticks are listed in the PR's **What** (or the accept report) | As above |
| **Accept commit** | Can carry roadmap ticks besides the status change and archive renames | As above |
| **Never untick** | A ticked item whose task isn't Done is reported, never unticked. An item's text and **Check:** line are never edited | — |
| **spec-reviewer** | The full review flags `ROADMAP OVERTICK` (a tick for work not delivered in full, or an untick). The close-out check flags `ROADMAP UNTICKED`, and now runs whenever close-out changed a file besides the task file, except roadmap mode's own tick. Roadmap mode's "must be ticked in this diff" moved from the full review to the close-out check, which runs after the tick | — |
| **`/sync-roadmap [--dry-run]`** | New skill: the sweep across every Done task, after you approve the list, on a `docs/` branch with one PR (or the branch you're on, if it's `chore/` or `docs/`) | — |

### Steps

1. **Run the installer** on a new branch, from the project root:
   ```powershell
   git switch main; git pull --ff-only; git switch -c chore/kit-2.8
   powershell -NoProfile -ExecutionPolicy Bypass -File C:\Development\tools\claude-code-starter-kit\install-kit.ps1 -Upgrade -WhatIf
   powershell -NoProfile -ExecutionPolicy Bypass -File C:\Development\tools\claude-code-starter-kit\install-kit.ps1 -Upgrade
   ```
   Expect: **Added** for `.claude/skills/sync-roadmap/` (`SKILL.md`, `ticks.md`) and `.claude/scripts/list-roadmap-ticks.ps1`; **Updated** for the `implement-task` and `customize-kit` skills, `track-follow-ups/classify.md`, and four guides under `docs/claude-kit/` (`README.md`, `USER-GUIDE.md`, `UPGRADING.md`, `CHANGELOG.md`); **To merge** for `spec-reviewer.md`, `.claude/rules/git.md`, and the PR template, plus `kit.json` and `CLAUDE.md`, which list because yours are customized (the kit's copies didn't change; nothing to merge in them). The same with or without roadmap mode. Restart Claude Code.
2. **Merge `.kit-incoming/`**, or run `/customize-kit`, which detects a 2.7 configuration (`git.md` doesn't mention roadmap ticks) and proposes these as rows:
   - `.claude/rules/git.md`: the **Roadmap ticks** bullet, first of the allowed changes to other files on a task branch ("Two kinds" becomes "Three kinds").
   - `spec-reviewer.md`: step 3 (Roadmap, with the ticks check), the scope sentence in step 6, the close-out check sentence under Inputs, the OVERREACH wording in step 11, and the two output blocks. Keep your `model:` and `effort:` lines.
   - PR template: the roadmap-ticks comment under **What**, and "the roadmap ticks and" in the diff checklist line.
3. **Check the tick doc**:
   ```powershell
   powershell -NoProfile -ExecutionPolicy Bypass -File .claude/scripts/list-roadmap-ticks.ps1
   ```
   Its first line names the doc and why it was picked (`workflow.roadmap.path`, or the Project docs **Roadmap** or **Task list** row). If that's the wrong doc, fix the Project docs table in `CLAUDE.md`. "No done marks" means nothing will be ticked, which is correct for a task list without checkboxes.
4. **Tick what's already finished, in this PR**:
   ```text
   /sync-roadmap --dry-run
   /sync-roadmap
   ```
   On the `chore/kit-2.8` branch it commits there instead of opening its own PR. Approve, strike, or add to its table: an item done before the task files existed is yours to tick. In roadmap mode the list is exact (the item with each Done task's ID); otherwise each tick cites the Done tasks that deliver it. Partial items are listed and left open.
5. **Find project text that says who ticks the roadmap.** `git grep -n -i -e "tick" -e "checkbox" -- CLAUDE.md .claude/project .claude/rules`. A line like "Tick the task's checkbox in the roadmap in the same PR" now says what the kit does: delete it, or keep it if it adds a project rule. A `.claude/project/*.md` line wins over the kit.
6. **Commit by path**, push, and open the PR, e.g. `chore: upgrade claude kit to 2.8`. Its **What** lists the backfilled ticks.

### Verification

On the upgrade branch:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .claude/scripts/list-roadmap-ticks.ps1; $LASTEXITCODE   # expect 0; roadmap mode: "To tick (0)" after step 4
powershell -NoProfile -ExecutionPolicy Bypass -File .claude/scripts/build-index.ps1; $LASTEXITCODE          # expect 0
git diff main -- <tick doc>                                                                                  # expect only marks changed
```

The next task after merging: its close-out commit ticks the items it finishes, its PR's **What** has a `Roadmap:` line (or none when nothing was ticked), and after "accepted" the accept commit carries any item that became finished.

### Projects with and without roadmap mode

- **Roadmap mode** (e.g. ledger: `docs/05-roadmap.md`, `☐`/`☑` in headings): close-out still ticks the task's own item, exactly as before. New are the sweep (an item whose task was accepted by hand gets ticked by the next close-out) and spec-reviewer checking the tick in the close-out check. If your roadmap was already in step, `/sync-roadmap` finds nothing to do.
- **No roadmap mode, roadmap with checkboxes** (e.g. cfb-model: `docs/06-roadmap.md` as the **Roadmap** role, `- [ ]` items): new behaviour. Items have no IDs, so Claude matches them to tasks by evidence: the item names the task, or the task's Context cites the item or its **Task list** row, and the task's Goal and ACs cover everything the item lists. The backfill is where you'll see the most change; review its table.
- **No roadmap, task list without checkboxes** (the kit's `docs/templates/tasklist.md`): nothing changes.

### Rolling back

- To stop ticking without rolling back: `.claude/project/implement-task.md` with "Never tick the roadmap; the owner does." Ticks already made stay; they're true.
- To return to 2.7, reinstall it with its `install-kit.ps1 -Upgrade` and revert `spec-reviewer.md`, `git.md`, and the PR template from git. Delete `.claude/skills/sync-roadmap/` and `.claude/scripts/list-roadmap-ticks.ps1`; the installer doesn't remove files.

## From 2.6 to 2.7

2.7 has one change: a PreToolUse hook, `guard-destructive.ps1`, reads every command the Bash and PowerShell tools are about to run and stops the ones that destroy work nobody can give back. On the way, every kit hook moves to exec form, because the shell form silently doesn't run on a machine where Claude Code has no Git Bash. The upgrade is one branch and one PR.

### Behaviour changes

These apply once the merged `settings.json` registers the hook (step 2) and Claude Code restarts. The hook file itself arrives with `-Upgrade`, but does nothing until it is registered.

| Change | What you'll see | Opt out |
|---|---|---|
| **Denied deletes** | Claude is blocked, told why, and told to stop and ask, when a command deletes outside the project (other than the temp folder or `destructiveGuard.allowPaths`), the project itself or a folder containing it, everything in it, its `.git`, a nested repository or worktree, or a `protectedPaths` file; when a recursive delete's path can't be resolved (an unset variable, `$( )`, `xargs`); disk tools; `gh repo delete`/`archive`/visibility changes; `git push --mirror`, force pushes, deleting the base branch on the remote | Add a folder to `destructiveGuard.allowPaths`. Run the command yourself |
| **Asked deletes** | A permission prompt labelled `guard-destructive:` before a recursive delete of a folder holding tracked files or untracked files git doesn't ignore, `git clean -f`, `git reset --hard`, `git checkout -- .`, `git restore .`, `git stash drop`/`clear`, `git worktree remove --force`, history rewrites, and inline code that deletes folders. Unattended, the command doesn't run; a `--bg` session waits in Needs input. `bypassPermissions` turns these into denies | Approve the prompt. There is no switch to silence it: use `git rm -r`, or `git clean -fdX` for ignored files only |
| **Not affected** | Deleting files, and ignored folders (`node_modules`, build output, caches), inside the project; anything inside the temp folder; `git checkout <ref> -- <file>` (test-auditor's revert); `git worktree remove` without `--force` | — |
| **Exec-form hooks** | `settings.json` registers each kit hook as `"command": "powershell"` with an `args` array. Claude Code fills in `${CLAUDE_PROJECT_DIR}` itself, so the hooks run whether or not it found Git Bash. Under 2.6, a machine with only the PowerShell tool ran no kit hook at all, silently | — |
| **`onFailure: "block"`** | On the destructive-command guard and the protected-paths guard: if the hook can't start or times out, the action is blocked instead of going ahead. Needs Claude Code 2.1.295; older versions ignore the field | Remove the field |
| **New deny rule** | `gh repo delete*`, for both tools | — |
| **One more process per shell call** | Each Bash or PowerShell call starts one short PowerShell process (about half a second) | Remove the `Bash\|PowerShell` entry from `hooks.PreToolUse`. Not recommended |

### Steps

1. **Run the installer** on a new branch, from the project root:
   ```powershell
   git switch main; git pull --ff-only; git switch -c chore/kit-2.7
   powershell -NoProfile -ExecutionPolicy Bypass -File C:\Development\tools\claude-code-starter-kit\install-kit.ps1 -Upgrade -WhatIf
   powershell -NoProfile -ExecutionPolicy Bypass -File C:\Development\tools\claude-code-starter-kit\install-kit.ps1 -Upgrade
   ```
   Expect: **Added** for `.claude/hooks/guard-destructive.ps1`; **Updated** for the `customize-kit` skill and five guides under `docs/claude-kit/` (`README.md`, `USER-GUIDE.md`, `WORKFLOW.md`, `UPGRADING.md`, `CHANGELOG.md`); **To merge** for `settings.json`, `kit.json`, and `CLAUDE.md`. Restart Claude Code.
2. **Merge `.kit-incoming/`**, or run `/customize-kit`, which detects a 2.6 configuration (`guard-destructive.ps1` not registered, or hooks in shell form) and proposes these as rows:
   - `settings.json`: the `Bash|PowerShell` PreToolUse entry for `guard-destructive.ps1` (timeout 30, `"onFailure": "block"`); every kit hook rewritten in exec form, keeping your timeouts; `"onFailure": "block"` on `guard-protected-paths.ps1`; deny `Bash(gh repo delete*)` and `PowerShell(gh repo delete*)`. Keep your allow and deny rules.
   - `kit.json`: `"destructiveGuard": { "allowPaths": [".kit-incoming"], "commands": [] }`. Add folders outside the project Claude may clean freely, and a `commands` rule for each destructive command whose wording varies too much for a deny rule (a database reset run through `npx`, a truncating seed script).
   - `CLAUDE.md`: under **Stop and ask before**, the two lines on deleting outside the project and discarding uncommitted work, "or deleting or archiving one" on the repository line, and the bullet on `guard-destructive.ps1` after the list.
3. **Find project text that tells Claude to run what now prompts.** `git grep -n -e "rm -rf" -e "Remove-Item" -e "git clean" -e "reset --hard" -e "rd /s" -- CLAUDE.md .claude/project .claude/rules .claude/skills/verify scripts`. A step that deletes a tracked folder becomes `git rm -r`; one that cleans build output can stay if the output is git-ignored; one that must wipe untracked work becomes an owner step.
4. **Check the Claude Code version**: `claude --version`. Exec form needs 2.1.139 or later (the kit already needs it for agent view). `onFailure` needs 2.1.295; on an older version, `claude update`, or accept that a guard that can't start lets the command through.
5. **Commit by path**, push, and open the PR, e.g. `chore: upgrade claude kit to 2.7`.

### Verification

On the upgrade branch:

```powershell
'{"tool_name":"Bash","tool_input":{"command":"rm -rf ~"}}' | powershell -NoProfile -ExecutionPolicy Bypass -File .claude/hooks/guard-destructive.ps1; $LASTEXITCODE         # expect 2 and "targets the home folder"
'{"tool_name":"PowerShell","tool_input":{"command":"git reset --hard"}}' | powershell -NoProfile -ExecutionPolicy Bypass -File .claude/hooks/guard-destructive.ps1 # expect JSON with "permissionDecision":"ask"
'{"tool_name":"Bash","tool_input":{"command":"rm -rf node_modules"}}' | powershell -NoProfile -ExecutionPolicy Bypass -File .claude/hooks/guard-destructive.ps1; $LASTEXITCODE  # expect 0, no output (if node_modules is git-ignored)
(Get-Content .claude/settings.json -Raw | ConvertFrom-Json).hooks.PreToolUse | ForEach-Object { $_.matcher }                                                          # expect Read, Edit|Write|MultiEdit|NotebookEdit, Bash|PowerShell
```

In a Claude session after restarting: `/hooks` shows three PreToolUse entries and one PostToolUse entry. Ask Claude to run `rm -rf ~/nonexistent-test-folder`: it is blocked, and `.claude/state/guard-destructive.log` has a `deny` line. Ask it to run `git stash clear` when the stash is empty: you get a `guard-destructive:` prompt (decline it).

### Rolling back

- Remove the `Bash|PowerShell` entry from `hooks.PreToolUse` in `settings.json` to turn the guard off; the rest of 2.7 stays.
- To return to 2.6, reinstall it with its `install-kit.ps1 -Upgrade` and revert `settings.json`, `kit.json`, and `CLAUDE.md` from git. Keep the exec-form hooks if you can: they work with 2.6's hook scripts unchanged. The `destructiveGuard` key is harmless to 2.6.

## From 2.5 to 2.6

2.6 has one change: follow-ups (work noticed during a task and deliberately left out) are written where the work that will do it will read it, in the PR that noticed them, instead of only in the PR body. The upgrade is one branch and one PR, then one backfill run after it merges.

### Behaviour changes

These apply as soon as `-Upgrade` replaces the skills, before you merge anything: a missing `workflow.followUps` key means `apply`.

| Change | What you'll see | Opt out |
|---|---|---|
| **Follow-ups placed** | At close-out, `/implement-task` writes each follow-up to one destination: another task's `## Context` (never its ACs), a roadmap item's body (never its **Check:** line), a new roadmap item or `Draft` task file, the decisions log, a planning doc, or the **Owner checklist**. The close-out commit carries those edits; each PR Follow-ups bullet ends `→ <path> § <section>` or `→ not tracked: <reason>` | `workflow.followUps: "propose"` (2.5 behaviour, plus the intended destination on each bullet), or `"review"` to approve every placement in the session first |
| **Approval at both gates** | The plan gate lists follow-ups planning found, with their placements; approving the plan approves them. Close-out asks once, with "Push and open a draft PR?", about placements that need your yes: planning-doc edits, and decisions under `decisions: propose`. Unattended sessions, and anything you don't answer, queue them under Approvals in the **Owner checklist**; tick one, or say "approve", and Claude makes the change | `"propose"` writes nothing outside the task |
| **Candidate decisions** | An explicit `workflow.decisions` still wins. `append`: recorded at close-out, as before. `propose`: no longer left in the PR; recorded by Claude once you approve it. A missing `decisions` key follows `followUps`. IDs come from `next-id.ps1`, so two open branches no longer take the same one | `workflow.decisions` |
| **Task file `## Follow-ups`** | New section (template updated; older task files get it at close-out). The PR's section is copied from it | — |
| **Edits to other files on a task branch** | `.claude/rules/git.md` and spec-reviewer allow follow-up placements that trace to a bullet. spec-reviewer runs a short "follow-ups check" on the close-out diff | — |
| **Link commit** | Right after `gh pr create`, one commit replaces the branch name in follow-up notes with `PR #n`. The squash merge hides it | — |
| **Stale plan from new notes** | A note another task added to this task's Context after its plan was approved makes the plan stale: attended sessions ask, unattended ones stop with `plan stale` | — |
| **`/plan-batch`, `/skeleton`** | Their PRs place follow-ups the same way and have a Follow-ups section | `"propose"` |
| **`/new-task` on a roadmap item with no Check** | Proposes a Check and writes it into the roadmap once you agree, then copies it as AC-1 | — |

### Steps

1. **Run the installer** on a new branch, from the project root:
   ```powershell
   git switch main; git pull --ff-only; git switch -c chore/kit-2.6
   powershell -NoProfile -ExecutionPolicy Bypass -File C:\Development\tools\claude-code-starter-kit\install-kit.ps1 -Upgrade -WhatIf
   powershell -NoProfile -ExecutionPolicy Bypass -File C:\Development\tools\claude-code-starter-kit\install-kit.ps1 -Upgrade
   ```
   Expect: **Updated** for the `implement-task`, `plan-batch`, `new-task`, `skeleton`, `customize-kit`, and `adopt` skills, `docs/tasks/_TEMPLATE.md`, and four guides under `docs/claude-kit/` (`README.md`, `USER-GUIDE.md`, `UPGRADING.md`, `CHANGELOG.md`); **Added** for `.claude/skills/track-follow-ups/` (`SKILL.md`, `classify.md`), `.claude/scripts/list-follow-ups.ps1`, `.claude/scripts/next-id.ps1`, and `docs/templates/owner-checklist.md`; **To merge** for `kit.json`, `CLAUDE.md`, `spec-reviewer.md`, `.claude/rules/git.md`, and the PR template. The same with or without roadmap mode. Restart Claude Code.
2. **Merge `.kit-incoming/`**, or run `/customize-kit`, which detects a 2.5 configuration (no `workflow.followUps`) and proposes these as rows:
   - `kit.json`: `"followUps": "apply"` in `workflow` (or `"review"` / `"propose"`). Leave `decisions` as it is.
   - `.claude/rules/git.md`: the paragraph after "One task per branch, one branch per PR" (follow-up placements and archiving as the two allowed changes to other files), and the `→` sentence after the PR body line.
   - `spec-reviewer.md`: step 11 (Follow-ups), the "Follow-ups check only" paragraph under Inputs, the scope sentence in step 6, step 12 (was 11), and the two output blocks. Keep your `model:` and `effort:` lines.
   - PR template: the Follow-ups comment and the two reviewer-checklist lines.
   - `CLAUDE.md`: the Workflow bullet on follow-ups, after "Change files outside the plan's file list only after explaining why".
   - `settings.json` (the kit's copy doesn't change, so `/customize-kit` proposes it): allow `gh pr list *`, `gh pr view *`, and `powershell -NoProfile -ExecutionPolicy Bypass -File .claude/scripts/*`, each as `Bash(...)` and `PowerShell(...)`, so unattended sessions aren't stopped by a prompt.
3. **Give approvals somewhere to wait: the Owner checklist.** If the **Owner checklist** row in `CLAUDE.md` is `—`, create one from `docs/templates/owner-checklist.md` (e.g. `docs/owner-checklist.md`) and add the row. If you have one, add an Actions and an Approvals heading in its own style. Without it, attended sessions still ask you, but an unattended session can only leave approvals in the PR.
4. **Find project text that says how follow-ups or decisions are handled.** `git grep -n -i -e "follow-up" -e "candidate decision" -e "owner adds" -- CLAUDE.md .claude/project .claude/rules`. A `.claude/project/*.md` line wins over the kit: delete it if the switch now says the same, keep it if it's the project's rule.
5. **Commit by path**, push, and open the PR, e.g. `chore: upgrade claude kit to 2.6`.
6. **After merging, run the backfill once**, on an up-to-date `main` with a clean tree:
   ```text
   /track-follow-ups --dry-run
   /track-follow-ups
   ```
   It reads the Follow-ups of every PR merged since the one that installed the kit (the commit that first added `.claude/kit-version`; pass `--since <PR#|date>` to choose), drops what is already tracked, done, or accepted, and places the rest on a `docs/track-follow-ups-<date>` branch with one PR that lists every follow-up as tracked (where) or not tracked (why). Review the placements in that PR like any other. It also applies any Owner checklist approval you've ticked, so it is worth re-running now and then.

### Verification

On the upgrade branch:

```powershell
(Get-Content .claude/kit.json -Raw | ConvertFrom-Json).workflow.followUps                                                     # expect apply (or your choice)
powershell -NoProfile -ExecutionPolicy Bypass -File .claude/scripts/next-id.ps1 -Path <Decisions log path> -Prefix <ID prefix>   # expect one line per branch read, then "Next: <prefix><n>"
powershell -NoProfile -ExecutionPolicy Bypass -File .claude/scripts/list-follow-ups.ps1                                        # expect "Since: <n> (the PR that installed the kit)" and a count
powershell -NoProfile -ExecutionPolicy Bypass -File .claude/scripts/build-index.ps1; $LASTEXITCODE                               # expect 0
```

The next task after merging: its plan gate has a Follow-ups line, its PR's Follow-ups bullets each end in `→`, and the "How it was verified" table has a spec-reviewer row for the follow-ups check if anything was placed outside the task.

### Projects with and without roadmap mode

- **Roadmap mode** (`workflow.roadmap` set; e.g. ledger: `docs/TASKS.md`, `decisions: "propose"`, commit format `area`):
  - A follow-up for an item with no task file goes into that item's body. New work becomes a roadmap item with the next free ID in its phase (`next-id.ps1 -List -Pattern '\d+\.\d+[a-z]?' -Path docs/TASKS.md`), a size, a **Check:**, and a place in the build order, never a task file.
  - If the roadmap is in `largeFiles`, placements read it through the hint or a ranged Read; keep the hint working.
  - With `decisions: "propose"`, candidate decisions become approvals, asked at close-out or queued in the Owner checklist. The 2.4-era rule "the owner adds it as the next D-n" becomes "Claude adds it once the owner approves".
  - A "next new decision: D-n" line is updated with each recorded decision; `next-id.ps1` ignores it and reads the rows, so two branches can still conflict on that line's text, but never on an ID.
- **No roadmap** (e.g. cfb-model: `{type}/{id}-{slug}` branches, `decisions: "append"`):
  - New work becomes a `Draft` task file plus a stub in the **Task list** under its milestone.
  - The backfill branch is `docs/…`, so `docs/` must stay in `workflow.branchPrefixes`.
  - Zero-padded IDs (`D-007`) keep their padding.

### Rolling back

- `workflow.followUps: "propose"` stops new placements; notes already placed stay where they are, and the 2.5 skills ignore them.
- To return to 2.5, reinstall it with its `install-kit.ps1 -Upgrade`. The `## Follow-ups` section in task files, the `followUps` key, and the Owner checklist are harmless to 2.5.

## From 2.4 to 2.5

2.5 has one change: Done task files move to `docs/tasks/archive/`, so `docs/tasks/` holds only live work. The upgrade is one branch and one PR.

### Behaviour changes

| Change | What you'll see | Opt out |
|---|---|---|
| **Task archive** | At close-out, `/implement-task` moves every Done task file still in `docs/tasks/` into `docs/tasks/archive/` (`git mv`) in the close-out commit and lists them in the PR's **What**. At "accepted" it moves the task itself. A `/plan-batch` plans PR does the same | `workflow.archiveDone: false` |
| **Archive renames in task PRs** | `.claude/rules/git.md` allows them as the one change a branch makes to other tasks' files; spec-reviewer doesn't count them as scope creep | — |
| **Board** | `INDEX.md` lists archived tasks in their own table, metrics included. New warnings: a Done task outside the archive, and a task in the archive that isn't Done | — |
| **Task lookups** | Dependency checks, the dispatcher, `/new-task` ID numbering, and `/implement-task` preflight read `docs/tasks/archive/` too | — |

### Steps

1. **Run the installer** on a new branch, from the project root:
   ```powershell
   git switch main; git pull --ff-only; git switch -c chore/kit-2.5
   powershell -NoProfile -ExecutionPolicy Bypass -File C:\Development\tools\claude-code-starter-kit\install-kit.ps1 -Upgrade -WhatIf
   powershell -NoProfile -ExecutionPolicy Bypass -File C:\Development\tools\claude-code-starter-kit\install-kit.ps1 -Upgrade
   ```
   Expect: **Updated** for the `implement-task`, `new-task`, `next-task`, `plan-batch`, and `customize-kit` skills, `lib-tasks.ps1`, `build-index.ps1`, and the guides; **Added** for `archive-done.ps1`; **To merge** for `kit.json`, `CLAUDE.md`, `spec-reviewer.md`, `.claude/rules/git.md`, and the PR template. Restart Claude Code.
2. **Merge `.kit-incoming/`**, or run `/customize-kit`, which detects a 2.4 configuration and proposes these as rows:
   - `kit.json`: `"archiveDone": true` in `workflow` (`false` to opt out; a missing key means `true`).
   - `CLAUDE.md`: the Tasks row in Project docs ("Done tasks in `docs/tasks/archive/`") and the Workflow bullet on `archive-done.ps1`.
   - `.claude/rules/git.md`: the archiving exception after "One task per branch, one branch per PR".
   - `spec-reviewer.md`: the sentence on archive renames in the scope check. Keep your `model:` and `effort:` lines.
   - PR template: the archive clause on the "Task file set to `status: Done`" checklist line.
3. **Archive the existing Done tasks in this PR**, so the first task PR after the upgrade doesn't carry them. Skip this step if you opted out.
   ```powershell
   powershell -NoProfile -ExecutionPolicy Bypass -File .claude/scripts/archive-done.ps1 -DryRun
   powershell -NoProfile -ExecutionPolicy Bypass -File .claude/scripts/archive-done.ps1
   ```
   The renames are staged. A file reported as untracked was moved but not staged; stage its new path if it belongs in git.
4. **Find what reads task paths.** `git grep -n "tasks/TASK-"` outside `docs/tasks/` shows links in the decision log, task list, and notes; repoint the ones to archived tasks, or accept that they now point one folder up. Check `.claude/project/*.md` and project scripts too: anything that globs `docs/tasks/TASK-*.md` must also read `docs/tasks/archive/`. Merged PR bodies keep their old links; GitHub can't rewrite them.
5. **Commit by path** (the renames are already staged; add the merged files by name), push, and open the PR, e.g. `chore: upgrade claude kit to 2.5`.

### Verification

On the upgrade branch:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .claude/scripts/archive-done.ps1 -DryRun    # expect: No Done tasks outside docs/tasks/archive/.
powershell -NoProfile -ExecutionPolicy Bypass -File .claude/scripts/build-index.ps1; $LASTEXITCODE   # expect 0; INDEX.md has an Archive table and no "not archived" warning
(Get-Content .claude/kit.json -Raw | ConvertFrom-Json).workflow.archiveDone                    # expect True (False if you opted out)
```

After merging, on `main`: `dispatch-approved.ps1 -DryRun` doesn't list a task as "waiting on" an archived task, and CI's "Task files parse cleanly" step is green.

### Rolling back

- `workflow.archiveDone: false` stops new moves; files already archived stay where they are and are still read.
- To return to 2.4, first move the files back on a branch (`git mv docs/tasks/archive/TASK-*.md docs/tasks/`), then reinstall 2.4 with its `install-kit.ps1 -Upgrade`. The 2.4 scripts don't read `archive/`, so without the move every dependency on an archived task shows as unknown.

## From 2.3 to 2.4

The short version: on a `chore/kit-2.4` branch, run `install-kit.ps1 -Upgrade`, then run `/customize-kit`. It detects the 2.3.x configuration and proposes each change below for your approval. The rest of this guide is what it will propose, and how to check it.

### 1. Before you start

- **Work on a branch.** `git switch main; git pull --ff-only; git switch -c chore/kit-2.4`. Everything below lands in one PR that you review and merge.
- **Clean tree.** `git status` empty, apart from untracked files you know about. The upgrade stages by path, but a clean tree makes the PR diff easy to read.
- **What isn't reversible.**
  - Untracked files: `.kit-incoming/` is deleted after the merge. The installer can recreate it, so this is harmless. Your untracked `.claude/settings.local.json` is never touched.
  - Anything outside git: GitHub settings (rulesets, secrets, repo variables), a `/install-github-app` run, and a pushed branch. The upgrade itself changes none of these. Only steps you choose to do in step 10 and the PR do.
  - Everything else is a commit on your branch, so reverting it is reversible.
- **Rolling back.**
  - Before merging: close the PR and delete the branch. `main` is untouched.
  - After merging: `git revert <the squash commit>` on a new branch, through a PR. That restores every file, kit-owned ones included, and `.claude/kit-version`.
  - Keep a 2.3.1 copy of the central kit (e.g. `C:\Development\tools\claude-code-starter-kit-2.3.1-backup`). From the project root, `powershell -NoProfile -ExecutionPolicy Bypass -File C:\Development\tools\claude-code-starter-kit-2.3.1-backup\install-kit.ps1 -Upgrade` puts the kit-owned files (skills, hooks, scripts, templates) back to 2.3.1 and records 2.3.1 in `.claude/kit-version`. Use this when you want 2.3.1 behaviour without reverting your own changes. Your custom files (agents, `CLAUDE.md`, `kit.json`, `settings.json`) keep whatever you merged. Revert those from git if you need them back too. The 2.4 skills read keys a 2.3.1 skill ignores, so leaving the new `kit.json` keys in place is harmless.

### 2. Behaviour changes

These change what Claude does with no config edit, once the kit-owned files are upgraded (and, for the settings rules, once the new `settings.json` is merged).

| Change | What you'll see | Opt out |
|---|---|---|
| **Staging by path** | `/implement-task` commits run `git status` and `git diff --staged` and stage named files; your uncommitted edits stay out of its commits | `workflow.staging: "all"` and remove the staging deny rules. Not recommended |
| **New deny rules** | `git add -A*`, `git add --all*`, `git add .`, `git commit -a*`, `git commit --all*` are denied | Remove them from `settings.json` (only with `staging: "all"`) |
| **`PowerShell(...)` deny rules** | Every `Bash(...)` deny rule has a `PowerShell(...)` twin, so the PowerShell tool can't push to the base branch, force-push, merge, or `git add -A` either | Remove the `PowerShell(...)` lines. Only sensible if you have branch protection on GitHub |
| **Large-read guard** | A new PreToolUse hook on Read. It does nothing until `largeFiles` lists a file; then a whole-file read of it is denied with your hint. Each Read starts a short PowerShell process | Remove the `Read` entry from `hooks.PreToolUse`, or leave `largeFiles` empty |
| **Ready gates** | Before `gh pr ready`, `/implement-task` checks `verify.full` on the branch head (re-running test-runner if code changed since its last pass), then CI, then your gates. Owner gates are listed, not checked | Set `workflow.readyGates: ["ci"]` for CI only (close to 2.3.1) |
| **PR body and title** | Sections: What · Why · Acceptance criteria · How it was verified (table) · Manual verification · Follow-ups · Reviewer checklist. The title is a commit subject (`feat(TASK-014): …`), not `TASK-014: …` | Keep your own `.github/pull_request_template.md`; the skill fills the sections it finds |
| **Plans go through a PR** | `/plan-batch` commits nothing. Approving plans creates a `docs/plans-<date>` branch and a PR instead of a commit on the base branch | None: committing on the base branch is what the kit now forbids |
| **No commits on the base branch** | `/milestones`, `/adopt`, and `/plan-batch` commit on `docs/` branches and open PRs | None |
| **Claude workflows skip without the secret** | With no `CLAUDE_CODE_OAUTH_TOKEN`, `claude-pr-review.yml` and `claude.yml` pass with a notice instead of failing (after you merge them from `.kit-incoming/`) | Keep your old copies |
| **ACs never copy a mockup number** | `/new-task` writes relationship or fixture ACs; spec-reviewer flags an AC or test asserting a figure from a mockup or prose | Say so in `.claude/project/new-task.md` |
| **WIP limit question** | `/customize-kit` asks whether parallel worktrees share a test resource, and may set `wipLimit: 1` | Answer no |
| **`docs/decisions.md` no longer shipped** | The installer stops proposing it. Skills read the decisions log through the **Decisions** role (default path unchanged) | None needed; your file stays |
| **Fast checks** (only if you use the new object form) | `post-edit-verify.ps1` runs an object entry only on its `extensions`. String entries behave exactly as in 2.3.1 | — |

### 3. Every item

"Action" is one of: *none*, *automatic with `-Upgrade`*, *merge from `.kit-incoming/`*, *manual edit*, *owner decision*. `/customize-kit`'s upgrade pass proposes every *merge*, *manual edit*, and *owner decision* row.

| # | What changed | Action | The exact edit | How to verify |
|---|---|---|---|---|
| 1 | Stage by path | automatic with `-Upgrade` (skill); merge (`settings.json`) | `kit.json`: `workflow.staging: "by-path"` (optional; it's the default). `settings.json` deny: `Bash(git add -A*)`, `Bash(git add --all*)`, `Bash(git add .)`, `Bash(git commit -a*)`, `Bash(git commit --all*)`, and the same as `PowerShell(...)` | Ask Claude to run `git add -A`: denied. A task's checkpoint commit lists only its files |
| 2 | Commit format | owner decision | `workflow.commitFormat: "conventional"` (default) or `"area"` | The next task's commits and PR title follow it |
| 3 | Branch prefixes | merge (`settings.json`); owner decision (`taskBranch`) | `workflow.branchPrefixes: ["task/","fix/","docs/","chore/"]`; `workflow.taskBranch: "task/{id}-{slug}"` (or `"{type}/{id}-{slug}"`); allow `Bash(git push -u origin <prefix>*)` and `PowerShell(...)` per prefix | A push of a `docs/` branch doesn't prompt |
| 4 | Ready gates | automatic (skill); owner decision (gates) | `workflow.readyGates: ["verify.full","ci", …your gates]`, each `{ name, check, by, when?, failureLog?, ownerFix? }` | A task's PR stays draft until every Claude gate passes; the final report lists owner gates |
| 5 | PR body | merge `.github/pull_request_template.md` | Sections What · Why · Acceptance criteria · How it was verified · Manual verification · Follow-ups · Reviewer checklist | The next task PR has a `Check | Where | Result` table with one row per gate |
| 6 | Decisions proposed | owner decision | `workflow.decisions: "append"` (default) or `"propose"` | With `propose`, the PR's Follow-ups list candidate decisions and the log is untouched |
| 7 | Never split | owner decision | `workflow.splitPolicy: "split"` (default) or `"never-split"` | An oversized task stays whole, `size: L`, `autonomy: attended` |
| 8 | Merged is not live | manual edit | Project docs row `\| Deploy \| <path or —> \|`; `workflow.afterMerge: "<closing line>"`; deny your deploy commands (item 31) | The final report's last line is the after-merge text |
| 9 | Gates that aren't Actions runs | owner decision | A gate's `failureLog` (where its log lives) and `ownerFix` (what only you can fix) | A failed preview makes the session read that log or stop with the owner action, not loop |
| 10 | `--force-with-lease` | owner decision | `workflow.allowForceWithLease: false` (default). If true, remove `Bash/PowerShell(git push --force-with-lease *)` from deny | Matches your `settings.json` |
| 11 | Stop-and-ask list | merge (`CLAUDE.md`) | Add "Stop and ask before" under Workflow; tailor it | The section exists; Claude asks before a schema column change |
| 12 | Roadmap-led mode | owner decision | `workflow.roadmap: { "path", "idPattern", "checkLabel" }` | `/new-task <ids>` copies the check line verbatim; the title starts with the roadmap ID; the branch uses it |
| 13 | `/milestones --coverage` | automatic (skill) | — | `/milestones --coverage <roadmap>` proposes gaps and writes no new file |
| 14 | Three status records | owner decision (with 12) | `workflow.statusDoc: "<path>"` if you have a status page | The task PR ticks the roadmap box; the task file goes Review → Done on "accepted" |
| 15 | Plans through a PR | automatic (skill, dispatcher message) | — | `/plan-batch` leaves plans uncommitted; approval opens a `docs/plans-<date>` PR |
| 16 | Shared test resources | owner decision | `workflow.wipLimit: 1`, `workflow._wipLimitReason: "<resource>"` | `dispatch-approved.ps1 -DryRun` prints the reason when the limit is reached |
| 17 | Mockup numbers are sample data | automatic (skill, agent after merge) | — | spec-reviewer flags an AC asserting a mockup figure |
| 18 | UX floor and redraws | owner decision | Project docs row `\| UX floor \| <path> \|` (template `docs/templates/ux-floor.md`); `ui.redrawFiles: [...]` and remove those files from `protectedPaths` | A new UI task has a UX floor AC |
| 19 | Which document wins | merge (`CLAUDE.md`) | Replace the "Precedence:" line with the "Which document wins" section (order + three rules) | The section exists and matches your precedence |
| 20 | Decisions as a role | manual edit | Decisions row: `\| Decisions \| <path> (IDs <prefix>) \|`, without "(fixed)". A pointer file that existed only because the path was fixed can go | Skills cite your log's path |
| 21 | Review findings | owner decision | Row `\| Review findings \| <protocol>, <ledger> \|`; templates in `docs/templates/review-*.md` | Commits cite finding IDs |
| 22 | Owner runbook, checklist | manual edit | Rows `\| Owner runbook \| … \|`, `\| Owner checklist \| … \|` (or `—`) | Final reports list your next steps |
| 23 | `.claude/rules/git.md` | merge from `.kit-incoming/` | Create it, or merge the kit's into yours. The `CLAUDE.md` Git section becomes a pointer. Move long sections to path-scoped rules; one home per rule | `/memory` lists `git.md`; `CLAUDE.md` no longer repeats it |
| 24 | Override mechanism | manual edit | Replace `CLAUDE.md` counter-instructions with switches or `.claude/project/<skill>.md` (section 5) | No `CLAUDE.md` line contradicts a kit skill |
| 25 | Fast checks fit their files | manual edit (optional) | `verify.fast` entries as `{ "command", "extensions" }` where a linter rejects some extensions; eslint `--no-warn-ignored` | Edit a file of each extension: the hook passes or reports a real error |
| 26 | Several test runners | owner decision | `testAudit.runners: [{ "pattern", "run", "each"?, "dir"? }]`, `testAudit.setup` | test-auditor's report names each runner's result |
| 27 | Implementation ≠ lintable | manual edit | `testAudit.implementationExtensions`, `testAudit.implementationPaths` | test-auditor reverts those files in its dynamic check |
| 28 | Migrations not protected by path | manual edit | Remove any migration glob from `protectedPaths` and `_examples.protected_migration`; add a CI migration check | `protectedPaths` has no migration pattern; CI runs the check |
| 29 | Wider protected paths | owner decision | `protectedPaths` for production env files, design exports, source data, generated folders, vendored assets, each with a reason | An edit to each is blocked |
| 30 | Large-read guard | automatic (hook); merge (`settings.json`); manual edit (`largeFiles`) | Register `guard-large-reads.ps1` (PreToolUse, matcher `Read`); `largeFiles: [{ "pattern", "hint", "always"? }]` | A Read of a listed file without offset/limit is denied with the hint |
| 31 | Deny dangerous commands | owner decision | Deny `Bash(...)` and `PowerShell(...)` for deploy, release, production-data, and destructive-reload commands | Ask Claude to run one: denied |
| 32 | Project sections in agents | merge agents; manual edit | Take the kit's agent bodies; move project text to `.claude/project/<agent>.md` | Each agent file matches the kit's apart from `model:`/`effort:`; each project file exists |
| 33 | Reviewer model and effort | owner decision | `model:` and `effort:` in the reviewer agents' front matter | `@` → agent shows the model |
| 34 | Viewports | owner decision | `ui.viewports` gains `{ "name": "tablet", "width": 768, "height": 1024 }` | ui-verifier reports a tablet column |
| 35 | Login step for UI checks | manual edit | `ui.auth: { "loginPath", "envFile", "secretVar", "steps" }` | ui-verifier signs in; its report never shows the secret |
| 36 | Generated `/verify` | owner decision | `/customize-kit` writes `.claude/skills/verify/SKILL.md` from `docs/templates/verify-skill.md` (keep yours if you have one) | `/verify` runs `verify.full` and reports output |
| 37 | Claude workflows without the secret | merge from `.kit-incoming/` | Take the kit's `claude-pr-review.yml` and `claude.yml` (job env `HAS_TOKEN`, gated steps) | A PR leaving draft without the secret gets a passing job with a notice |
| 38 | Action versions | merge from `.kit-incoming/`; manual edit (your own workflows) | `actions/checkout@v7`, `actions/setup-node@v7`, `actions/setup-python@v7`, `actions/upload-artifact@v7` | `git grep -n "uses: actions/"` shows no older majors |
| 39 | CI layout | manual edit | `workflow.ciJobName: "<your job>"`; add the "Task files parse cleanly" step (`./.claude/scripts/build-index.ps1`, `shell: pwsh`) to your CI | CI shows the step; the gate watches the right job |
| 40 | Isolated test database | manual edit (if needed) | CI test job sets `TEST_DATABASE_URL` only (a dummy `DATABASE_URL` only on build); service image = production major, from `public.ecr.aws/docker/library/` instead of Docker Hub (also any `docker run` or `container:` image); a test guard with no fallback | Tests refuse with `TEST_DATABASE_URL` unset; every `image:` and `docker run` in `.github/` names a `public.ecr.aws/docker/library/` image |
| 41 | Environment ladder | owner decision | Via `/architecture`; then `protectedPaths` and `Read(...)` denies for production env files | A Read of the production env file is denied |
| 42 | Release template | owner decision | Copy `docs/templates/github/release.yml` to `.github/workflows/` and fill it | A dry run reports the plan |
| 43 | Performance-budget template | owner decision | Copy `perf-budget.yml`, add `perf/budget.json` | A preview gets a budget comment |
| 44 | Backup template | owner decision | Copy `backup.yml` | A manual run restores the dump and passes |
| 45 | Dependency-bot template | owner decision | Copy `dependabot.yml` to `.github/` | Dependabot opens grouped PRs |
| 46 | Down files | owner decision | A hard rule plus schema-reviewer's project file: drops, retypes, and merges ship a down file and an up → down → up test | schema-reviewer flags a drop without one |
| 47 | No branch protection | merge (`settings.json`); manual edit (`git.md`) | `PowerShell(...)` twin for every `Bash(...)` deny; `git.md` "Project notes" says the deny rules are the only guard if rulesets return 403 | `gh api repos/{owner}/{repo}/rulesets`; the deny list has both tools |

### 4. Upgrade steps, in order

`/customize-kit` (2.4) runs an upgrade pass when it detects a 2.3.x configuration. It does steps 2–12 for you, proposing each as a row in one table for your approval. Step 1 and the GitHub settings in step 10 are yours.

1. **Run the installer** from the project root, on the `chore/kit-2.4` branch:
   ```powershell
   powershell -NoProfile -ExecutionPolicy Bypass -File C:\Development\tools\claude-code-starter-kit\install-kit.ps1 -Upgrade -WhatIf
   powershell -NoProfile -ExecutionPolicy Bypass -File C:\Development\tools\claude-code-starter-kit\install-kit.ps1 -Upgrade
   ```
   Expect: **Updated** for every kit skill, `post-edit-verify.ps1`, `dispatch-approved.ps1`, `docs/tasks/_TEMPLATE.md`, `docs/templates/architecture.md`, and the guides; **Added** for `guard-large-reads.ps1` and the new templates; **To merge** for `CLAUDE.md`, `kit.json`, `settings.json`, each agent, `.claude/rules/git.md` (if you have one; otherwise Added), the PR template, the two Claude workflows, and `ci.yml` if yours is the kit's filled-in one. Nothing under `.claude/project/`, `.claude/rules/` other than `git.md`, `.claude/skills/verify/`, or your decisions log is touched. Restart Claude Code.
2. **Merge `.kit-incoming/`** *(customize-kit)*. Keep all your content and add the kit's new sections, keys, and rules. For each agent, take the kit's body and keep your `model:` and `effort:` lines; your project text moves in step 5, so don't merge it back into the body. If `.kit-incoming/.github/workflows/ci.yml` appears, it is the kit's unfilled template: don't merge it into your filled-in CI; step 9 covers what to check.
3. **Add the new `kit.json` keys** *(customize-kit)*: the `workflow` switches (item table: 1–4, 6–8, 10, 12, 14, 16), `largeFiles`, the `testAudit` keys (26, 27), and `ui.auth` / `ui.redrawFiles` / `ui.viewports` (18, 34, 35). Remove `_examples.protected_migration` and any migration glob in `protectedPaths`.
4. **Update `settings.json`** *(customize-kit)*: the staging denies, a `PowerShell(...)` twin for every `Bash(...)` rule (allow and deny), push allow-rules per branch prefix, deny rules for deploy and production commands, `Read(...)` denies for production env files, and the `guard-large-reads.ps1` hook entry.
5. **Move project text out of agent bodies** *(customize-kit)* into `.claude/project/<agent>.md`: output formats (test-runner, test-auditor), project checks (spec-reviewer, schema-reviewer), sign-in and limits (ui-verifier).
6. **Replace `CLAUDE.md` workarounds with switches** *(customize-kit)*, and delete the prose they replace (section 5).
7. **Add the new Project docs rows** *(customize-kit)*: Deploy, UX floor, Review findings, Owner runbook, Owner checklist, and a Decisions row with its ID prefix and without "(fixed)". Replace the "Precedence:" line with "Which document wins", and add "Stop and ask before".
8. **Create or merge `.claude/rules/git.md`** *(customize-kit)*, fill its "Project notes", and make the `CLAUDE.md` Git section a pointer to it.
9. **Update CI** *(customize-kit proposes; you review)*: `workflow.ciJobName` = your job's name, the "Task files parse cleanly" step in your CI, and the test-database isolation if your CI sets `DATABASE_URL` in the test job.
10. **Gate the Claude workflows on their secret** *(customize-kit, from `.kit-incoming/`)*. Then decide: run `/install-github-app` (attached terminal) to set `CLAUDE_CODE_OAUTH_TOKEN`, or leave them skipping. Check rulesets (`gh api repos/{owner}/{repo}/rulesets`) and set branch protection if they're available (yours, on GitHub).
11. **Bump action versions** *(customize-kit)* in your own workflows to `@v7` for checkout, setup-node, setup-python, and upload-artifact.
12. **Offer the optional templates** *(customize-kit)*: release, performance budget, backup, dependency bot, UX floor, review protocol and ledger, and the generated `/verify`.

Then commit by path on `chore/kit-2.4`, push, open the PR, and run the checks in section 7 before merging.

### 5. Projects that worked around 2.3.1

On 2.3.1 the only way to change `/implement-task` was to write counter-instructions into `CLAUDE.md` (because `-Upgrade` overwrites skills), and to add project sections and "override" lines inside agent bodies (which then needed a hand merge on every upgrade). In 2.4 each of those has a home the kit never overwrites. Find them by searching `CLAUDE.md` and `.claude/agents/` for "Kit task loop", "override", "even though the skill says", "instead of the kit's", and any heading that names your project.

**Worked example: the Ledger project** (a Next.js + Postgres app on Neon and Vercel). Its 2.3.1 adoption put a "§ Kit task loop" section in `CLAUDE.md` and "Ledger" sections in its agents. Each maps to a 2.4 switch or project file:

| 2.3.1 workaround (Ledger) | 2.4 replacement | Delete |
|---|---|---|
| Kit task loop: "PRs … are marked ready only when git.md § Test on the branch has passed, not CI alone: the Vercel preview has deployed, Lighthouse is green, and a UI change has been walked on the preview" | `workflow.readyGates`: `["verify.full", "ci", { "name": "Vercel preview deployed", "check": "gh pr checks <n> shows the Vercel status as pass", "by": "claude", "failureLog": "the Vercel deployment log", "ownerFix": "A migration regenerated after the first preview needs the Neon branch preview/<branch> deleted and the preview redeployed (START-HERE 10f)" }, { "name": "Lighthouse green", "check": "gh pr checks <n> shows Lighthouse as pass and its comment shows nothing over budget", "by": "claude" }, { "name": "Changed workflow run on the branch", "check": "gh workflow run <file> --ref <branch>; gh run watch <id> --exit-status", "by": "claude", "when": [".github/workflows/*"] }, { "name": "Preview walked at 360–412px", "check": "Walk the changed screen and its states on the preview against the mockup", "by": "owner", "when": "ui" }]` | That bullet |
| "Stage by path … even though the skill says `-A`" | Default `workflow.staging: "by-path"` | That bullet |
| "A failed preview build is not an Actions run … that is the owner's step; say so and stop" | The preview gate's `failureLog` and `ownerFix` (above) | That bullet |
| "Decisions are proposed, not written … the owner adds it to `docs/review/decisions.md` as the next D-n" | `workflow.decisions: "propose"`; Decisions row `docs/review/decisions.md (IDs D-n)` | That bullet |
| "A TASKS.md task is never split" | `workflow.splitPolicy: "never-split"` | That bullet |
| "Merged is not live. Every final report ends with: 'After merge, run Release (START-HERE Step 13) to put it live.' Claude never starts Release." | `workflow.afterMerge: "After merge, run Release (START-HERE Step 13) to put it live."`; the Deploy row already exists; the deny rule `gh workflow run release.yml*` stays | That bullet |
| "One task, two IDs" (TASK-### file titled `1.2 Undo`; branch `task/1.2-undo`; commit `task 1.2: …`) | `workflow.roadmap: { "path": "docs/TASKS.md", "idPattern": "\\d+\\.\\d+[a-z]?", "checkLabel": "**Check:**" }` and `workflow.commitFormat: "area"` | That bullet |
| "Three status records, one owner each" | Roadmap mode, plus `workflow.statusDoc: "docs/STATUS.md"` | That bullet |
| The first eight Kit task loop bullets (copies of the template's Workflow lines) | The template's Workflow section | The duplicates |
| "Precedence: … `.claude/rules/git.md` beats the kit's flow on branch names, commit and PR format, and when a PR is ready" | `git.md` and the kit now agree through the switches | That sentence; keep "Which document wins (D-1)" |
| Decisions row: "`docs/decisions.md` (fixed) points there and holds stack rows K-n" | Decisions row names the D-log and its prefix. The pointer file existed only because the path was fixed | *Decided (owner, 2026-10-09)*: move K-1…K-8 into `docs/review/decisions.md` as the next D-rows, each noting its old K-ID, then delete `docs/decisions.md` and anything that cites it by path |
| `wipLimit: 1` with the reason in `kit-adoption.md` (G-14) | `workflow._wipLimitReason: "Every worktree's .env names the same test database, which test:db:reset rebuilds and vitest truncates"` | — |
| G-19: `--force-with-lease` deny dropped by hand | `workflow.allowForceWithLease: true` | — |
| G-3: no `PowerShell(...)` deny rules (owner accepted) | 2.4 adds them by default (a behaviour change) | *Decided (owner, 2026-10-09)*: keep them; rulesets return 403 on this repository, so they are the only guard. Record the reversal of G-3 in `docs/kit-adoption.md` |
| `.claude/hooks/guard-large-reads.js` (Node) blocking `seed/*`, sidecar CSVs, `*.xlsx`, the Metron cache, and whole reads of `design/mockups.html` | `largeFiles`: `{ "pattern": "design/mockups.html", "hint": "Print one screen with: powershell -NoProfile -File scripts/screen.ps1 <data-id> (ids in design/mockups-index.md)" }`, `{ "pattern": "docs/TASKS.md", "hint": "Print one task with: powershell -NoProfile -File scripts/task.ps1 <id>" }`, and `"always": true` entries for `seed/*`, `etl/data/cover_dates.csv`, `etl/data/why_review.csv`, `etl/data/volume_map.csv`, `etl/data/workbook_run_fields.csv`, `*.xlsx`, `*.metron-cache.sqlite` | The `.js` hook and its `settings.json` entry, once the PowerShell guard is registered |
| test-auditor "Ledger override" line (count `.sql`, `.py`, `drizzle/meta/` as implementation) | `testAudit.implementationExtensions: [".ts", ".tsx", ".mjs", ".sql", ".py"]`, `testAudit.implementationPaths: ["drizzle/meta/*"]` | The override line |
| test-auditor "Reading this stack's output" | `.claude/project/test-auditor.md` (same text). `testAudit.run: "node scripts/test-files.mjs {tests}"` keeps working; `runners` + `setup` could replace the script later | The section in the agent |
| test-runner "Reading this stack's output" (the `test:all` `&&` chain, tsc, eslint, token and migration checks, vitest, SQL and Python output) | `.claude/project/test-runner.md` | The section in the agent |
| spec-reviewer "Project-specific checks (Ledger)" | `.claude/project/spec-reviewer.md` with checks 2–6. Check 1 (the TASKS.md Check and its checkbox) and the "task file ranks below TASKS.md" paragraph are built in with roadmap mode | The section in the agent |
| schema-reviewer's 12 Ledger checks and "Migration tool (drizzle-kit)" section | `.claude/project/schema-reviewer.md`. Keep `model: sonnet` and `effort: high` in the agent's front matter | The checks in the agent body |
| ui-verifier "Ledger specifics": Sign in first | `ui.auth: { "loginPath": "/login", "envFile": ".env", "secretVar": "APP_PASSCODE", "steps": ["Type the passcode into the Passcode field", "Press Open ledger", "Wait for the redirect away from /login"] }` | That bullet |
| ui-verifier "Ledger specifics": dev database, design files, viewports, targets | `.claude/project/ui-verifier.md` | The section in the agent |
| `.claude/rules/schema.md` repeating `CLAUDE.md` § Non-obvious rules (and drifting from it) | One home per rule: keep each rule in `rules/schema.md` (path-scoped) or in `CLAUDE.md`, not both, and leave a pointer | The copy that loses |
| CI job `check` | `workflow.ciJobName: "check"`; add the "Task files parse cleanly" step to `ci.yml` (the kit's `ci.yml` was skipped) | — |
| `ci.yml` and `backup.yml` pull `postgres:18` from Docker Hub | `public.ecr.aws/docker/library/postgres:18` in both (the backup check that the scratch server matches `PG_MAJOR` still applies) | The Docker Hub names |
| Kit workflows bumped to `checkout@v7` by hand (G-18) | The 2.4 kit's workflows use `@v7` and skip without the secret (G-4) | Take the kit's two files wholesale |

**Worked example: the cfb-model project** (a pnpm monorepo: a Next.js app in `web/`, a uv Python workspace in `python/`, Alembic migrations, Neon and Vercel). Its 2.3.1 adoption kept the kit's own `ci.yml` (filled in), wrote project rules into `.claude/rules/` (git always; database, python, web by path), and put project text in four agents.

| 2.3.1 workaround (cfb-model) | 2.4 replacement | Delete |
|---|---|---|
| `CLAUDE.md`: "Where a kit guide or skill conflicts with `.claude/rules/git.md` (branch names, staging, committing to `main`), `git.md` wins" | `workflow.branchPrefixes: ["feat/","fix/","chore/","docs/","model/"]`, `workflow.taskBranch: "{type}/{id}-{slug}"` (the prefixes' meanings stay in `git.md`); staging by path and never committing on `main` are now kit defaults | That sentence |
| Two precedence lines ("code and migrations > this file and rules > docs"; "the design wins … still follow `docs/04-model.md`") | One "Which document wins" section: code and migrations → the roadmap/task checks → architecture → narrative docs, with "the design rules layout and copy; numbers follow the model doc" | Both lines |
| Decisions row `docs/decisions.md (fixed)` | `\| Decisions \| docs/decisions.md (IDs D-###) \|` | "(fixed)" |
| `git.md`: "Before calling a PR ready: the full CI suite passes locally, CI is green, and the Vercel preview has deployed" and "Test a changed workflow on its branch" | `workflow.readyGates: ["verify.full", "ci", { "name": "Vercel preview deployed", "check": "gh pr checks <n> shows the Vercel status as pass", "by": "claude", "failureLog": "the Vercel deployment log" }, { "name": "Changed workflow run on the branch", "check": "gh workflow run <file> --ref <branch>; gh run watch <id> --exit-status", "by": "claude", "when": [".github/workflows/*"] }]` | Keep the lines in `git.md` if you like the prose; the gates now enforce them |
| `git.md`: "Merging does not deploy. Production changes go out only through the `release` workflow" | `workflow.afterMerge: "After merge, run the release workflow to put it live."` and the Deploy row, once `release.yml` exists (start from `docs/templates/github/release.yml`); until then Deploy is `—` | — |
| `.claude/scripts/run-tests.ps1` (a project script in a kit-owned folder) as `testAudit.run` | Either `testAudit.runners` with `dir` (`{ "pattern": "python/*/tests/*.py", "dir": "python", "run": "uv run pytest {tests}" }`, `{ "pattern": "web/e2e/*.spec.ts", "dir": "web", "run": "pnpm exec playwright test {tests}" }`, `{ "pattern": "web/*.test.ts*", "dir": "web", "run": "pnpm exec vitest run {tests}" }`) plus `testAudit.setup: "pnpm db:migrate:test && pnpm db:seed"`, or keep the script but move it to `scripts/` and update `kit.json`, `settings.json` and `CLAUDE.md` | The script, if the runners replace it |
| `verify.fast` runs `pnpm typecheck`, eslint and `ruff check .` on every `.ts`, `.tsx`, `.mts` and `.py` edit | Object entries: `{ "command": "pnpm --dir web exec eslint --no-warn-ignored ..\\{file}", "extensions": [".ts",".tsx",".mts"] }`, `{ "command": "uv --directory python run ruff check .", "extensions": [".py"] }`, and `pnpm typecheck` as a string (it covers both) | — |
| `protectedPaths` entry `python/db/migrations/versions/0001_*` | A CI check that migrations on `main` are never edited (decision D-020; `pnpm db:check` covers one head and models-match only so far). Keep the entry until that check exists, then remove it; a per-file entry goes stale with every merged migration | The migration entry, once the check lands |
| `protectedPaths` has both `design/*` and `design/handoff/*` | `design/*` already matches everything below `design/` (`*` crosses folders) | `design/handoff/*` (optional) |
| schema-reviewer "Project data rules" and "Migration tool: Alembic" | `.claude/project/schema-reviewer.md` | The text in the agent |
| spec-reviewer project checks; test-runner and test-auditor output notes | `.claude/project/spec-reviewer.md`, `test-runner.md`, `test-auditor.md` | The text in the agents |
| ui-verifier "Reference screenshot check" | Built into the 2.4 ui-verifier (compare with the **Reference screenshots** at the same width). The project specifics (file names `NN-<screen>-<desktop\|mobile\|tablet>.png`, numbers compared only on the seeded test database, dark theme) go in `.claude/project/ui-verifier.md` | The step in the agent |
| Screenshots exist at 768 for This Week | `ui.viewports` gains the 768×1024 tablet | — |
| The seed fixture reproduces the mockup's sample numbers on purpose | Allowed: an AC cites the fixture ("on the seeded test database …"), not the mockup | — |
| `CLAUDE.kit.md` at the repository root: an unfilled copy of the 2.3.1 template left from the first merge | Nothing reads it | The file |
| `wipLimit: 2` with one shared `TEST_DATABASE_URL` (the e2e suite needs it migrated and seeded) | *Owner decision*: `wipLimit: 1` with `_wipLimitReason`, or a test database per worktree in `worktreeSetup` | — |
| `ui.auth` | Not needed yet. When GitHub sign-in lands, a passcode field won't work: give the dev server a dev-only sign-in that `ui.auth.steps` can drive, and never let it reach production | — |
| `.github/workflows/ci.yml` (the kit's template, filled in) | `.kit-incoming/` gets the kit's unfilled template: don't merge it. Yours already has the parse step, `timeout-minutes`, `concurrency`, job `verify`, and `TEST_DATABASE_URL` only. Its one change: the "Start Postgres" step's `docker run "postgres:${PG_MAJOR}"` becomes `docker run "public.ecr.aws/docker/library/postgres:${PG_MAJOR}"` | The Docker Hub name |

### 6. A prompt for the upgrade

Paste this into Claude Code in the project, after step 1 (the installer) and a restart:

```text
We're upgrading this project's Claude Code starter kit from 2.3.x to 2.4. The guides are in docs/claude-kit/
(UPGRADING.md and CHANGELOG.md). The installer has already run with -Upgrade.

1. Read docs/claude-kit/UPGRADING.md, CLAUDE.md, .claude/kit.json, .claude/settings.json, .claude/rules/,
   every file in .claude/agents/ and .kit-incoming/, and the CI workflows. Don't open any .env* file.
2. Run /customize-kit. Its upgrade pass builds one table: every change from UPGRADING.md's item table that
   applies here, with the exact edit, the CLAUDE.md or agent text it lets us delete, and how to verify it.
   Mark the rows that need my decision. Then stop and wait for my approval. Change nothing before that.
3. After I approve (row by row is fine), apply only the approved rows. Follow this project's own git rules
   (.claude/rules/git.md and CLAUDE.md): work on a chore/kit-2.4 branch, stage by path, commit with this
   project's commit format, and never commit on or push to the base branch.
4. Run the checks in UPGRADING.md section 7 and report each result.
5. Push the branch and open one PR. Its body says what changed, which 2.4 behaviour changes now apply,
   what you deleted from CLAUDE.md and the agents and what replaced it, and how it was verified. Leave it
   for me to merge.
```

### 7. Verification after upgrading

Run these on the upgrade branch before merging, and report each result:

```powershell
# Task files still parse
powershell -NoProfile -ExecutionPolicy Bypass -File .claude/scripts/build-index.ps1; $LASTEXITCODE                                  # expect 0

# The fast checks fire on a source file, and skip a file no check applies to
'{"tool_input":{"file_path":"<a real source file>"}}' | powershell -NoProfile -ExecutionPolicy Bypass -File .claude/hooks/post-edit-verify.ps1; $LASTEXITCODE        # expect 0
'{"tool_input":{"file_path":"<a .md file>"}}' | powershell -NoProfile -ExecutionPolicy Bypass -File .claude/hooks/post-edit-verify.ps1; $LASTEXITCODE                  # expect 0 at once

# A whole-file Read of a large file is denied; a ranged one isn't
'{"tool_input":{"file_path":"<a largeFiles path>"}}' | powershell -NoProfile -ExecutionPolicy Bypass -File .claude/hooks/guard-large-reads.ps1; $LASTEXITCODE           # expect 2
'{"tool_input":{"file_path":"<same path>","offset":1,"limit":50}}' | powershell -NoProfile -ExecutionPolicy Bypass -File .claude/hooks/guard-large-reads.ps1; $LASTEXITCODE  # expect 0 (2 if the entry has "always")

# An edit to a protected path is blocked
'{"tool_input":{"file_path":".env"}}' | powershell -NoProfile -ExecutionPolicy Bypass -File .claude/hooks/guard-protected-paths.ps1; $LASTEXITCODE                    # expect 2

# The dispatcher still reads the config
powershell -NoProfile -ExecutionPolicy Bypass -File .claude/scripts/dispatch-approved.ps1 -DryRun                                                                   # expect a summary, no dispatch
```

Then:

- **In a Claude session**, `/hooks` shows two PreToolUse entries (Read, Edit|Write) and one PostToolUse entry. Editing a source file runs the fast checks, reading a large file whole is refused with the hint, and editing `.env` is blocked. Asking Claude to run `git add -A` is denied.
- **`verify.full` passes**: delegate to test-runner, or run `/verify`.
- **JSON parses**: `Get-Content .claude/kit.json -Raw | ConvertFrom-Json` and the same for `.claude/settings.json` don't throw.
- **CI is green on the upgrade PR**, including the "Task files parse cleanly" step. The Claude review job passes (or skips with its notice).
- **Nothing project-specific is left in an agent body**: each `.claude/agents/*.md` matches the kit's apart from `model:` / `effort:`, and each project section is in `.claude/project/`.
- **No counter-instructions are left in `CLAUDE.md`**: search it for "Kit task loop", "even though the skill", and "instead of the kit".
