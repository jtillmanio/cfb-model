---
name: plan-batch
description: Writes implementation plans for the next several Ready tasks in one sitting, so the user can review and approve them together before unattended dispatch. Use when the user runs /plan-batch or asks to plan several tasks ahead.
argument-hint: (optional) N tasks to plan (default 3) and/or specific IDs, e.g. 5  or  TASK-014 TASK-015
---

# Plan batch: $ARGUMENTS

> **Doc roles:** names in **bold** such as **Architecture**, **Data model**, or **Decisions** are roles in the "Project docs" table in `CLAUDE.md`. Always read and write the path the table gives for a role, including a `§ section` if it names one. The path in parentheses is only the default, used when the table is missing. If a role maps to `—`, follow the fallback stated in the step, or ask. Refer to sections by name, never by number.

> **Project overrides:** read `.claude/kit.json` first, then `.claude/project/plan-batch.md` if it exists. The project file holds this project's instructions for this skill and wins where it conflicts with this file, except that it can't lower the floor: never approve a plan on your own initiative, never commit on or push to the base branch.

Planning only. Edit nothing except the selected task files' `## Plan` section and their `plan_status` / `planned_at_commit` front matter. Never write code, run migrations, or commit. The plans stay uncommitted until the user approves them (see Hand-off).

## Select tasks

1. Must be on `workflow.baseBranch`, up to date with `origin/<base>` (`git fetch`, then `git status -sb` shows no "behind"), with a clean working tree (`git status --porcelain` empty). Otherwise stop. Each plan's `planned_at_commit` must be a base-branch commit, so it still exists after the plans PR is squash-merged.
2. If `$ARGUMENTS` names IDs, plan exactly those. Otherwise take the first N (default 3) tasks with `status: Ready` and `plan_status` of `none` or `proposed`, in ID order. Prefer tasks whose dependencies are `Done`.
3. A task whose dependencies are not yet `Done` may still be planned, but mark its plan **provisional**. The staleness check in `/implement-task` will force a re-plan if the dependency changes the planned files.
4. Show the selection (ID, title, autonomy, dependency state) and continue without waiting.

## Plan each task

Use the same plan format as `/implement-task` Phase 1, at the same quality bar, for each task in turn:

1. Read the task file, the cited architecture and design sections, the CLAUDE.md hard rules, and the **Decisions** log. In roadmap mode (`workflow.roadmap`), also read the task's roadmap entry and its check line.
2. Explore the code it touches (delegate broad searches to Explore). Plan against the code as it is now.
3. Write `## Plan` with Steps, Files, Test strategy (one test per AC), Risks / open questions, and Size check. Add `Provisional: depends on <IDs>` where it applies.
4. Set `plan_status: proposed` and `planned_at_commit: <git rev-parse --short HEAD>`.
5. If the size check fails: with `workflow.splitPolicy` `split` (default), don't plan the task; propose a split and move on. With `never-split`, plan it whole, make sure it is `autonomy: attended`, and say why it is large.

Keep each plan under ~40 lines. Unattended sessions follow these plans literally, so name files and tests precisely.

## Hand-off (under 20 lines)

1. Table: ID, files planned, ACs → tests mapped (n/n), risks count, provisional (y/n).
2. The two or three plan decisions most worth the user's attention, such as a new pattern, a risky migration, or an ambiguous AC.
3. How plans reach the base branch. The dispatcher only sees plans committed there, and nobody commits on the base branch, so they go through a PR:
   1. Review with `git diff docs/tasks`, then edit plans directly or ask for changes.
   2. Approve by changing `plan_status: proposed` to `approved`, or by telling you "approve TASK-014 and TASK-015".
   3. Move the approved plans to a branch and open a PR: `git switch -c docs/plans-<YYYY-MM-DD>` (uncommitted plans come along), commit the task files by path (`git add docs/tasks/TASK-014-….md …`), push, `gh pr create`.
   4. The user merges the PR.
   5. `git switch <base>`, `git pull --ff-only`, then `powershell -NoProfile -ExecutionPolicy Bypass -File .claude/scripts/dispatch-approved.ps1 -DryRun`, then without `-DryRun`.

If the user asks you to approve plans, set `plan_status: approved` for exactly the IDs they name. Then, if they ask, do step 3: create the `docs/plans-<date>` branch, stage those task files by path, commit (`docs(tasks): approve plans TASK-014..016`, or the `area` form `docs: approve plans for tasks 1.2, 1.1`), push the branch, and open the PR. Never approve a plan on your own initiative, never commit on the base branch, never merge.
