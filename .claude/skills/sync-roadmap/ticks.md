# Roadmap ticks: which items, when, by whom

The one home for keeping the roadmap's done marks in step with the task files. `/implement-task` (close-out and accept), `/sync-roadmap`, the `/customize-kit` upgrade, and spec-reviewer follow this file; none of them restates it.

> **Doc roles:** names in **bold** are roles in the "Project docs" table in `CLAUDE.md`. Read and write the path the table gives, including a `§ section`. A role mapped to `—` uses the fallback stated below.

A roadmap whose boxes nobody ticks stops saying what's built, and the next planning session trusts it anyway. The aim: an item is ticked in the PR that finishes its work, and any item a task finished without a tick (a task accepted by hand, or done before this rule existed) is caught by the next task that closes out or is accepted.

## The tick doc

1. Roadmap mode (`workflow.roadmap` set): `workflow.roadmap.path`.
2. Otherwise the **Roadmap (source)** role, unless it is `—`.
3. Otherwise the **Task list** role.

It is ticked only if it already marks items done: a checkbox (`[ ]` / `[x]`) or a glyph (`☐` / `☑`, `⬜` / `✅`, `✔`) at the start of a list item or heading. Use the doc's own mark, as its legend defines it. A doc with no marks has nothing to tick: never add checkboxes, a status column, or a legend to it.

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

## Reporting

The PR body's **What** (or the accept report) lists each tick and each partial item, one line each:

- `Roadmap: ticked 1.3c (this task); ticked 1.2 (TASK-001, accepted by hand)`
- `Roadmap: left "DuckDB staging models + team_week_features" open: staging done (TASK-017, TASK-018), features in TASK-019 (Ready)`

`Roadmap: nothing to tick (<tick doc> has no done marks)` when the doc has no marks, and nothing at all when the project has no tick doc.
