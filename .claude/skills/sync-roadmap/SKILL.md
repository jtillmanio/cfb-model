---
name: sync-roadmap
description: Ticks the roadmap items that Done tasks have finished but nobody ticked (tasks accepted by hand, or finished before the kit ticked the roadmap), on a docs/ branch with one PR, or on the kit upgrade branch. Reports items only partly delivered and ticked items whose task isn't Done. Use when the user runs /sync-roadmap, after upgrading to kit 2.8, or asks to bring the roadmap's checkboxes up to date with the task files.
argument-hint: "[--dry-run]"
---

# Sync roadmap ticks: $ARGUMENTS

> **Doc roles:** names in **bold** such as **Roadmap** or **Task list** are roles in the "Project docs" table in `CLAUDE.md`. Always read and write the path the table gives for a role, including a `§ section` if it names one. Refer to sections by name, never by number.

> **Project overrides:** read `.claude/kit.json` first (`workflow.roadmap`, `workflow.statusDoc`, `workflow.baseBranch`, `workflow.commitFormat`, `largeFiles`), then `.claude/project/sync-roadmap.md` if it exists. It wins where it conflicts with this file, except that it can't lower the floor: never untick, never edit an item's text or **Check:** line, never edit `workflow.statusDoc`, never commit on or push to the base branch.

Which doc is ticked, what counts as finished, and the report format are in `.claude/skills/sync-roadmap/ticks.md`. Read it first and follow it; this file adds only what a backfill needs.

Parse `$ARGUMENTS`: `--dry-run` (report only; write nothing, create no branch).

## Phase 0: Preflight

1. `git status --porcelain` shows nothing but the work of the branch you are on. Otherwise stop: unrelated changes are the owner's.
2. Where the ticks will be committed:
   - On `workflow.baseBranch`: it must be up to date (`git fetch`, then `git status -sb` shows no "behind"). The branch is created in Phase 3.
   - On a `chore/` or `docs/` branch, such as the kit upgrade branch: commit there, and that branch's PR carries the ticks.
   - On a task branch: stop. That task's close-out and accept sweep the roadmap (ticks.md § When).

## Phase 1: Collect

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .claude/scripts/list-roadmap-ticks.ps1
```

If it finds no tick doc, or the doc has no done marks, report that and stop: nothing to tick, and marks are never added.

## Phase 2: Decide

- **Roadmap mode**: the "To tick" list is the answer. Check each line number points at that item (Read a few lines around it).
- **Otherwise**: for each open item, find the Done tasks that deliver it, by the evidence ticks.md asks for. Read the candidate tasks' Goal and acceptance criteria (Grep the archive by the item's distinctive words, then read the file). Skip phases no Done task reaches.

Show one table, under 40 rows per screen:

`Line | Item | Tasks | Verdict (tick / partial / leave) | Evidence`

Then the script's report-only rows (ticked items whose task isn't finished; finished tasks with no item). With `--dry-run`, stop here.

**Stop for approval.** The owner may strike rows or tick extra ones. Ticks for items no Done task delivers (done by hand, before the task files) are the owner's call: tick them only when the owner says so, and say so in the PR.

## Phase 3: Apply

1. On the base branch: `git switch -c docs/sync-roadmap-<YYYY-MM-DD>`.
2. Change each approved item's mark and nothing else (ticks.md § What gets ticked), in the doc's own style. Re-run the script: in roadmap mode "To tick" is now empty.
3. Stage the tick doc by path, read `git diff --staged` (only marks changed), and commit: `docs: tick roadmap items finished by done tasks` (`area`: `docs: tick roadmap items finished by done tasks`). On the upgrade branch, this can be its own commit or part of the upgrade commit.
4. If this run made the branch: push and open the PR (`gh pr create --base <base> --title "<the subject>" --body-file <temp file outside the repo>`). Body:
   - **What**: one line per tick, `Ticked <item> (<task IDs>)`, then the partial items, as ticks.md § Reporting says.
   - **Why**: the items were finished by Done tasks but left open, so the roadmap understated what's built.
   - **How it was verified**: the script's output before and after, and `git diff` showing only marks changed.
   - **Follow-ups**: none, unless the owner asked for something during Phase 2.

## Final report (under 15 lines)

The PR link, or the branch and commit; counts (ticked, partial, left, report-only); the partial items, one line each; then `workflow.afterMerge` if set. Never merge.
