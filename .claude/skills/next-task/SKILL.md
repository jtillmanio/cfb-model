---
name: next-task
description: Picks the next task that is ready to work on from docs/tasks/ (status Ready, dependencies Done, within the WIP limit) and starts /implement-task on it in this session. Use when the user runs /next-task or asks what to work on next or to pick up the next task.
argument-hint: (optional) --dry-run to only show the pick
---

# Next task $ARGUMENTS

> **Project overrides:** read `.claude/project/next-task.md` if it exists. It holds this project's instructions for this skill (for example, a build order the roadmap sets) and wins where it conflicts with this file, except that it can't raise the WIP limit or pick a task that isn't `Ready`.

## Procedure

1. Regenerate the board: `powershell -NoProfile -ExecutionPolicy Bypass -File .claude/scripts/build-index.ps1`. If PowerShell isn't available, read the task files' front matter directly.
2. Read `.claude/kit.json` → `workflow.wipLimit` (default 2) and `workflow._wipLimitReason` if present, and `.claude/state/dispatch.json` if it exists (tasks claimed by background sessions).
3. **In flight** = tasks with status `In progress` or `Review`, plus claimed tasks not yet `Done`. If in flight ≥ the WIP limit, stop. List the in-flight tasks, say which PRs to review or merge first, and quote `_wipLimitReason` if there is one.
4. **Candidates** = tasks with `status: Ready` whose `depends_on` tasks are all `Done` and that aren't claimed.
5. Pick one, using these tie-breakers in order:
   1. Unblocks the most other tasks (count of tasks listing it in `depends_on`, directly or transitively)
   2. Has an approved, fresh plan (`plan_status: approved`)
   3. Lowest ID
6. Report in under 12 lines: the pick, why it was chosen, the runner-up, and anything waiting (e.g. `TASK-018 waits on TASK-016 (Review)`).
7. If there are no candidates, say why: no Ready tasks, all blocked on dependencies, or all claimed. Suggest the next action, e.g. `/new-task`, approve Draft tasks, or review open PRs.
8. Unless `$ARGUMENTS` contains `--dry-run`, continue straight into `/implement-task <ID>` (attended mode) in this session.

Do not dispatch background sessions from here; that's `.claude/scripts/dispatch-approved.ps1`.
