---
name: plan-batch
description: Writes implementation plans for the next several Ready tasks in one sitting, so the user can review and approve them together before unattended dispatch. Use when the user runs /plan-batch or asks to plan several tasks ahead.
argument-hint: (optional) N tasks to plan (default 3) and/or specific IDs, e.g. 5  or  TASK-014 TASK-015
---

# Plan batch: $ARGUMENTS

> **Doc roles:** names in **bold** such as **Architecture**, **Data model**, or **Design tokens** are roles in the "Project docs" table in `CLAUDE.md`. Always read and write the path the table gives for a role, including a `§ section` if it names one. The path in parentheses is only the default, used when the table is missing. If a role maps to `—`, follow the fallback stated in the step, or ask. Refer to sections by name, never by number.

Planning only. Edit nothing except the selected task files' `## Plan` section and their `plan_status` / `planned_at_commit` front matter. Never write code, run migrations, or create branches.

## Select tasks

1. Must be on `workflow.baseBranch` with a clean working tree (`git status --porcelain` empty). Otherwise stop: plans have to be committed to the base branch so dispatched sessions see them.
2. If `$ARGUMENTS` names IDs, plan exactly those. Otherwise take the first N (default 3) tasks with `status: Ready` and `plan_status` of `none` or `proposed`, in ID order. Prefer tasks whose dependencies are `Done`.
3. A task whose dependencies are not yet `Done` may still be planned, but mark its plan **provisional**. The staleness check in `/implement-task` will force a re-plan if the dependency changes the planned files.
4. Show the selection (ID, title, autonomy, dependency state) and continue without waiting.

## Plan each task

Use the same plan format as `/implement-task` Phase 1, at the same quality bar, for each task in turn:

1. Read the task file, the cited architecture and design sections, the CLAUDE.md hard rules, and `docs/decisions.md`.
2. Explore the code it touches (delegate broad searches to Explore). Plan against the code as it is now.
3. Write `## Plan` with Steps, Files, Test strategy (one test per AC), Risks / open questions, and Size check. Add `Provisional: depends on <IDs>` where it applies.
4. Set `plan_status: proposed` and `planned_at_commit: <git rev-parse --short HEAD>`.
5. If the size check fails, don't plan the task. Propose a split and move on.

Keep each plan under ~40 lines. Unattended sessions follow these plans literally, so name files and tests precisely.

## Hand-off (under 20 lines)

1. Table: ID, files planned, ACs → tests mapped (n/n), risks count, provisional (y/n).
2. The two or three plan decisions most worth the user's attention, such as a new pattern, a risky migration, or an ambiguous AC.
3. Tell the user how to approve, in their words:
   - Review with `git diff docs/tasks`, then edit plans directly or ask for changes.
   - Approve by changing `plan_status: proposed` to `approved`, or by telling you "approve TASK-014 and TASK-015".
   - Commit (`docs(tasks): approve plans TASK-014..016`). **The user pushes the base branch.** Claude's permissions deny pushing to it, and branch protection should allow only the repository admin to bypass.
   - Dispatch: `powershell -NoProfile -ExecutionPolicy Bypass -File .claude/scripts/dispatch-approved.ps1 -DryRun`, then without `-DryRun`.

If the user asks you to approve plans, update `plan_status` for exactly the IDs they name, then commit with the message above and remind them to push. Never approve a plan on your own initiative, and never push the base branch.
