---
name: milestones
description: Breaks the MVP into demoable milestones and task stubs in the task list doc, ordered by dependency and risk, with a coverage check that every MVP feature, screen, and entity lands in a task. With --coverage it only checks an existing roadmap and adds the gaps to it. Use when the user runs /milestones or asks for a task list, roadmap, backlog, build plan, or a coverage check.
argument-hint: (optional) scope and/or a source roadmap, e.g. "MVP", "Next", "docs/06-roadmap.md", or "--coverage docs/roadmap.md"
---

# Milestones and task list: $ARGUMENTS

> **Doc roles:** names in **bold** such as **Architecture**, **Data model**, or **Decisions** are roles in the "Project docs" table in `CLAUDE.md`. Always read and write the path the table gives for a role, including a `§ section` if it names one. The path in parentheses is only the default, used when the table is missing. If a role maps to `—`, follow the fallback stated in the step, or ask. Refer to sections by name, never by number.

> **Project overrides:** read `.claude/kit.json` first, then `.claude/project/milestones.md` if it exists. The project file holds this project's instructions for this skill and wins where it conflicts with this file, except that it can't lower the floor: nothing is written before the gate, and nothing is committed on the base branch.

## Modes

- **Plan** (default): output is the **Task list** (default `docs/tasklist.md`), following `docs/templates/tasklist.md`. This is a stub-level plan. Full task files come later, one milestone at a time, via `/new-task <task list path> M1`.
- **Coverage** (`--coverage [roadmap path]`, or whenever `workflow.roadmap` is set): the project already has a roadmap that stays the source of truth. Writes **no new file**. It checks coverage (Phase 3) against the roadmap (the path given, else `workflow.roadmap.path`, else the **Roadmap (source)** role) and, after the gate, adds each gap to that roadmap as a new numbered task with a check line. Skip Phase 2.

## Phase 1: Read (read-only)

Read:
- **Features** (scope = MVP unless `$ARGUMENTS` says otherwise) and the **Screen inventory**
- the **Architecture** doc (components, feature traceability, risks), the **Data model**, and any **Domain specs**
- the **Decisions** log
- the **Design source of truth** and **Reference screenshots**
- the current code; the walking skeleton should already exist
- in coverage mode, the whole roadmap (if it's in `largeFiles`, read it in sections with offset/limit or the hint's printer)

If the architecture doc is missing, stop and suggest `/architecture`.

**Existing projects:**
- If `$ARGUMENTS` names a roadmap file, or `docs/kit-adoption.md` lists one, use its phases as the starting milestone structure. Keep a phase unless it breaks a rule below, and say why for every change.
- Exclude items marked **built** in `docs/kit-adoption.md`. Scope only the missing part of **partial** items.
- Schedule its toolchain-gap stubs in the first milestone.
- Every UI stub cites its S-ID, design file, and reference screenshot when the project has them.

## Phase 2: Shape the milestones (plan mode)

Rules:

1. **Every milestone is demoable.** It ends with something you can click through, so it's built from vertical slices (data → API → UI), not "all the schema first".
2. **Riskiest first.** Items in the architecture's risk table, imports and ETL, and anything with uncertain data shape go in M1 or M2.
3. **3–8 tasks per milestone; 3–6 milestones for an MVP.** If it doesn't fit, the MVP is too big; say so and propose cuts.
4. **Task stubs follow the sizing rules:**
   - S: ≤ 3 files, one layer
   - M: ≤ 8 files, ≤ 2 adjacent layers
   - Schema + UI together → split, unless `workflow.splitPolicy` is `never-split`
5. **Dependencies are explicit**, between task stubs (M1.2 depends on M1.1) and between milestones.
6. **Autonomy guess per stub**, using `/new-task`'s rules. Schema, auth, ETL, and the first instance of any new pattern are `attended`. Later instances of an established pattern can be `unattended`.

## Phase 3: Coverage check

Check that:
- every MVP feature appears in at least one task;
- every MVP screen is built by a task;
- every entity (table, view, or stored file the data model defines) is created, loaded, and edited where the features say it is, by some task.

Plan mode: fill the Coverage table, and fix any gaps before showing the result.

Coverage mode: list each gap with a proposed roadmap entry: the next free number in the right phase (following the roadmap's own numbering and `workflow.roadmap.idPattern`), a one-line description, and a check line starting with `workflow.roadmap.checkLabel` that a test or a person can pass or fail. A check asserts a relationship or a fixture, never a figure copied from a mockup or prose. Also list existing entries that need amending (scope moved, duplicates), with the proposed wording.

## Phase 4: Gate and write

1. Show the result in under 25 lines. Plan mode: the milestone outline (name, goal, demo, task count, the riskiest item). Coverage mode: the gap table and the proposed amendments. **Stop for approval or changes.**
2. Write:
   - Plan mode: the **Task list**.
   - Coverage mode: the approved entries and amendments, appended into the roadmap's phases. Never renumber or rewrite existing entries beyond the approved amendments.
3. Commit on a `docs/<slug>` branch, never on the base branch (`docs: task list` or `docs: close roadmap coverage gaps`; stage the file by path), push it, and open a PR. If the user prefers to commit themselves, leave the change uncommitted and say so.

## Hand-off

Next steps:

1. Run `/new-task <task list path> M1` to create full task files for the first milestone only (in roadmap mode, `/new-task <roadmap IDs of the first sitting>`). Writing specs just in time keeps them accurate.
2. Review those files and set them to `Ready`.
3. Run `/next-task`.
4. Repeat for M2 when M1 is close to done.
