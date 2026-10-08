---
name: new-task
description: Creates one or more task files in docs/tasks/ from docs/tasks/_TEMPLATE.md, with checkable acceptance criteria and sizing rules applied. Use when the user runs /new-task, asks to add or write a task, or asks to convert a task list, backlog, or phase plan into task files.
argument-hint: short description, OR a task list path plus optional milestone (e.g. docs/tasklist.md M1)
---

# New task(s): $ARGUMENTS

> **Doc roles:** names in **bold** such as **Architecture**, **Data model**, or **Design tokens** are roles in the "Project docs" table in `CLAUDE.md`. Always read and write the path the table gives for a role, including a `§ section` if it names one. The path in parentheses is only the default, used when the table is missing. If a role maps to `—`, follow the fallback stated in the step, or ask. Refer to sections by name, never by number.

## Mode

- **Single**: `$ARGUMENTS` is a short description. Create one task (or a split set, if it fails the size rules).
- **Bulk**: `$ARGUMENTS` is a path to a task list, backlog, or phase plan, optionally followed by a milestone ID (e.g. `M1`). Convert only that milestone's stubs when one is given. Create one file per task, preserving the source order and dependencies. Map stub IDs (M1.2) to the new TASK IDs in `depends_on`, and write the TASK ID back next to each stub in the task list so later milestones can reference it.

## Procedure

1. Read `docs/tasks/_TEMPLATE.md`, the existing `docs/tasks/TASK-*.md` front matter, the **Architecture**, **Data model**, **Features**, and **Screen inventory** docs, any **Domain specs** the tasks touch, `docs/decisions.md`, and the CLAUDE.md hard rules.
2. Next ID = highest existing `TASK-###` across the task files + 1, zero-padded to 3 digits.
3. For each task, fill every template section:
   - **Goal**: the user-visible outcome in 1–2 sentences. No implementation detail.
   - **Context**: links to the exact architecture, data model, and domain-spec sections, plus relevant decision IDs. UI tasks cite their screen ID, design file in the **Design source of truth**, and **Reference screenshot**. Read the design file to cite real components.
   - **Acceptance criteria**: 2–6 items, each checkable (see the rules below).
   - **Out of scope**: at least one line. Name the adjacent work a reasonable engineer might wrongly include.
   - **Files likely touched**: based on the current codebase. Explore it; do not guess paths.
   - **Verification**: automated tests that must exist, plus manual steps with expected results.
   - **size**, **model**, **autonomy** and **ui** in the front matter (rules below).
   - `plan_status: none`, `planned_at_commit:` empty. Leave Plan, Review log, and Metrics empty.
4. File name: `docs/tasks/TASK-###-<kebab-slug>.md`. Status: `Draft`.
5. Regenerate the board: `powershell -NoProfile -ExecutionPolicy Bypass -File .claude/scripts/build-index.ps1`. Never hand-edit `INDEX.md`.
6. Show the user a summary table (ID, title, size, model, autonomy, ui, depends_on, AC count) plus any open questions. Do not set any task to `Ready`; the user does that after review.

## Acceptance-criteria rules

Each AC must name an observable result and an expected value or state.

| Weak (rewrite it) | Checkable |
|---|---|
| "Progress displays correctly" | "Run page shows `read/total` from the progress view; seed run X shows 47/120" |
| "Handles errors" | "Submitting with an empty title returns 400 and the form shows 'Title is required' under the field" |
| "Fast" | "List endpoint returns 500 rows in < 300 ms on seed data (measured locally)" |
| "Works on mobile" | "At 390 px width, the action bar is sticky and every button is ≥ 44 px tall" |

Prefer Given/When/Then for behavior. Use concrete seed-data values wherever the data allows.

## Sizing rules

- **S**: ≤ 3 files, one layer (UI, API, or data). One sitting.
- **M**: ≤ 8 files, at most two adjacent layers (e.g. API + UI). One sitting.
- **Larger** (more than 8 files, or schema + UI together): split. A typical split is (1) schema/migration + data access with tests, (2) API/service, (3) UI. Chain the splits with `depends_on`.

## Autonomy

Set `autonomy: unattended` only when **all** of these hold. Otherwise use `attended`.

- size S, or M within a single layer
- `model: sonnet`
- follows a pattern that already exists in the codebase, so a plan can name a file to copy from
- no migrations, schema, auth, permissions, ETL, payment, or data deletion
- every AC is automatable, or a UI check the ui-verifier agent can run

The user can override it. Unattended tasks still need an approved plan before they're dispatched.

## UI flag

`ui: true` when any AC has a visible or interactive outcome. The ui-verifier agent then checks it in a browser.

## Model suggestion

- `opus`: schema, migrations, auth/security, ETL, concurrency, anything with ambiguous requirements
- `sonnet`: well-specified UI, CRUD, and API work that follows an existing pattern
- Planning always uses Opus regardless of this field. The field covers implementation only.
