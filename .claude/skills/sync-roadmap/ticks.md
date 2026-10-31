# Roadmap ticks: which items, when, by whom

The one home for keeping the roadmap's done marks, and the task list's Done column, in step with the task files. `/implement-task` (close-out and accept), `/sync-roadmap`, the `/customize-kit` upgrade, `/milestones`, `/new-task`, and spec-reviewer follow this file; none of them restates it.

> **Doc roles:** names in **bold** are roles in the "Project docs" table in `CLAUDE.md`. Read and write the path the table gives, including a `§ section`. A role mapped to `—` uses the fallback stated below.

A roadmap whose boxes nobody ticks stops saying what's built, and the next planning session trusts it anyway. The aim: an item is ticked in the PR that finishes its work, and any item a task finished without a tick (a task accepted by hand, or done before this rule existed) is caught by the next task that closes out or is accepted.

## The tick doc

1. Roadmap mode (`workflow.roadmap` set): `workflow.roadmap.path`.
2. Otherwise the **Roadmap (source)** role, unless it is `—`.
3. Otherwise the **Task list** role.

It is ticked only if it already marks items done: a checkbox (`[ ]` / `[x]`) or a glyph (`☐` / `☑`, `⬜` / `✅`, `✔`) at the start of a list item or heading. Use the doc's own mark, as its legend defines it. A doc with no marks has nothing to tick: never add checkboxes, a status column, or a legend to it. The one exception is the **Task list**'s Done column, below, which exists only when `workflow.taskListDone` is on.

Never edit `workflow.statusDoc`: it is regenerated from the roadmap, by the owner or by Claude on request. If the tick doc is in `largeFiles`, read it the way `largeFiles` says: Grep, then Read with offset and limit.

## Helper

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .claude/scripts/list-roadmap-ticks.ps1 [-Include TASK-014] [-Path <tick doc>]
```

Read-only. It finds the tick doc (as above; `-Path` overrides) and prints:

- Roadmap mode: the open items whose task is Done (**to tick**), ticked items whose task isn't Done or in Review (report only), and Done tasks whose roadmap ID has no marked item.
- Otherwise: every Done task with its Context lines that cite the roadmap or task list, then every open item under its heading, with any task IDs the item names.

`-Include` adds a task that isn't Done yet: this task at close-out, which is in `Review`.

## What gets ticked

An item is ticked when everything it describes is delivered by tasks that are Done, or by this task's own PR at close-out.

- **Roadmap mode**: the item whose ID is the task's roadmap ID (the first match of `workflow.roadmap.idPattern` in the task's title). Exact; no judgement.
- **Otherwise**, match by evidence, never by similar words alone:
  - the item names the task (`_(TASK-015)_`), or the task's Context cites the item (`<roadmap> § <section>`), or the **Task list** row the task came from (`M2.1 → TASK-015`) covers the item;
  - and the task's Goal and acceptance criteria deliver everything the item lists. Read them.
  - An item delivered by several tasks waits until all of them are Done. An item only partly delivered stays open: report it as **partial** (what is done, what remains, and which task or item covers the rest, if any).

Only the mark changes: never edit an item's text, its **Check:** line (`workflow.roadmap.checkLabel`), or its order. **Never untick.** An item ticked without a Done task may have been finished another way (by hand, in a kit upgrade, before the task files existed). Report one whose task is Draft, Ready, In progress, or Blocked, and leave it.

## When

| Moment | What is ticked | Where it is committed |
|---|---|---|
| `/implement-task` close-out | This task's items (run the helper with `-Include <this task>`), then the sweep | The close-out commit, so the tick merges with the work |
| `/implement-task` accept | The sweep: items tasks accepted by hand left open, and an item this task shares with a task accepted since its close-out | The accept commit |
| `/sync-roadmap` | The sweep, across every Done task; the backfill after a kit upgrade | Its own `docs/` branch, or the upgrade branch |

**The sweep**: every open item that Done tasks deliver in full, whichever task finished them. Unattended sessions sweep too: tick only what the rules above make certain, and report the rest as partial.

A tick of another task's item is allowed on a task branch (`.claude/rules/git.md`). It isn't a follow-up and needs no Follow-ups bullet; the PR lists it.

## The task list's Done column

Owners check progress by milestone in the **Task list**, but in a project whose roadmap and task list are separate docs the roadmap is ticked and the task list never shows progress. `workflow.taskListDone` (boolean in `.claude/kit.json`) adds a **Done** column to the task list's milestone tables, filled as tasks reach Done. It is `true` in a new project. On upgrade `/customize-kit` turns it on when the **Task list** role is set and differs from the tick doc. A missing key, `false`, or a project with no **Task list** means nothing in this section applies.

**The column**
- It is the first column of every milestone stub table in the **Task list**, the tables whose header starts `| Done | # | Task |` (before the upgrade, `| # | Task |`). First, because the Notes cells are long and a last column scrolls out of view. Scope, coverage, and mapping tables don't get it.
- The mark is `✅`. A row that isn't done has a blank cell.
- The doc's intro paragraph says so in one sentence: what the column means and that `/implement-task` and `/sync-roadmap` fill it.

**When a row is done**
- The row's `#` cell names its tasks (`M4.7 → TASK-042, TASK-043`). The row is done when every task it names has `status: Done`, wherever the file lives (including `docs/tasks/archive/`). A named task with no file isn't Done.
- At close-out, this task (in `Review`) counts as Done.
- A row that names no task is ticked only if its Notes say it was done another way, for example "Done in the kit 2.4 upgrade". A row moved elsewhere ("_Moved to M5.8_") stays blank. A row with no task and no such note stays blank.
- A row with a named task still Draft, Ready, In progress, or Blocked stays blank and is reported as **partial**.

**Limits**
- Only the Done cell changes. Never edit another cell, never untick, never reorder.
- A tick of another task's row is allowed on a task branch (`.claude/rules/git.md`), like a roadmap tick. It isn't a follow-up.
- The task list is often in `largeFiles`. Grep for the row (`^\| [^|]*\| M4\.7 `), then Read with offset and limit; never read it whole. To tick, Edit the one row.

**Helper**: `list-roadmap-ticks.ps1` prints, after the roadmap part, **Task list Done column**: the rows **to tick**, the **partial** rows, and ticked rows whose tasks aren't all finished (report only). It matches rows to tasks exactly through the `#` cell, so no judgement is needed, and it runs even when there is no tick doc or the tick doc has no marks. A table that has no Done column yet is counted ("have no Done column yet"); its rows are listed as what the upgrade would tick.

**Who fills it, and when**

| Moment | What is ticked | Where it is committed |
|---|---|---|
| `/customize-kit` upgrade | Adds the column to every milestone table, then backfills it with the rules above | The upgrade branch |
| `/implement-task` close-out | This task's row (run the helper with `-Include <this task>`), then the sweep | The close-out commit |
| `/implement-task` accept | The sweep | The accept commit |
| `/sync-roadmap` | The sweep, which catches tasks accepted by hand | Its own `docs/` branch, or the upgrade branch |

The sweep ticks every blank row whose named tasks are all Done. Unattended sessions sweep too.

**Kept intact**: `/milestones` (including `--coverage`) keeps the column and the existing marks when it writes or extends the task list, and gives new rows a blank Done cell. `/new-task` writes `→ TASK-###` into the `#` cell (the second column) and leaves Done blank.

**Review**: spec-reviewer allows a Done-cell change on a task branch and reports **TASKLIST OVERTICK** (a row ticked while a task it names isn't Done, or a `✅` removed) and, in the close-out check, **TASKLIST UNTICKED** (this task's row is blank although all its tasks are Done or are this task). Both are CHANGES REQUIRED.

## Reporting

The PR body's **What** (or the accept report) lists each tick and each partial item, one line each:

- `Roadmap: ticked 1.3c (this task); ticked 1.2 (TASK-001, accepted by hand)`
- `Roadmap: left "DuckDB staging models + team_week_features" open: staging done (TASK-017, TASK-018), features in TASK-019 (Ready)`

`Roadmap: nothing to tick (<tick doc> has no done marks)` when the doc has no marks, and nothing at all when the project has no tick doc.

When `workflow.taskListDone` is on, one line beside them, listing each tick and each partial row:

- `Task list: ticked M4.7 (TASK-042, TASK-043)`
- `Task list: left M4.8 open: TASK-045, TASK-046 Ready`
