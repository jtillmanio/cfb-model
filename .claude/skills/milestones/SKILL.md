---
name: milestones
description: Breaks the MVP into demoable milestones and task stubs in docs/tasklist.md, ordered by dependency and risk, with a coverage check that every MVP feature, screen, and entity lands in a task. Use when the user runs /milestones or asks for a task list, roadmap, backlog, or build plan.
argument-hint: (optional) scope, e.g. "MVP" (default) or "Next"
---

# Milestones and task list: $ARGUMENTS

Output: `docs/tasklist.md`, following `docs/templates/tasklist.md`. This is a stub-level plan. Full task files come later, one milestone at a time, via `/new-task docs/tasklist.md M1`.

## Phase 1: Read (read-only)

Read:
- `docs/product/features.md` (scope = MVP unless `$ARGUMENTS` says otherwise)
- `docs/architecture.md` (data model, components, feature traceability, risks)
- `docs/decisions.md`
- `design/`
- the current code; the walking skeleton should already exist

If the architecture doc is missing, stop and suggest `/architecture`.

## Phase 2: Shape the milestones

Rules:

1. **Every milestone is demoable.** It ends with something you can click through, so it's built from vertical slices (data → API → UI), not "all the schema first".
2. **Riskiest first.** Items in the architecture's risk table, imports and ETL, and anything with uncertain data shape go in M1 or M2.
3. **3–8 tasks per milestone; 3–6 milestones for an MVP.** If it doesn't fit, the MVP is too big; say so and propose cuts.
4. **Task stubs follow the sizing rules:**
   - S: ≤ 3 files, one layer
   - M: ≤ 8 files, ≤ 2 adjacent layers
   - Schema + UI together → split
5. **Dependencies are explicit**, between task stubs (M1.2 depends on M1.1) and between milestones.
6. **Autonomy guess per stub**, using `/new-task`'s rules. Schema, auth, ETL, and the first instance of any new pattern are `attended`. Later instances of an established pattern can be `unattended`.

## Phase 3: Coverage check

Fill the Coverage table:
- every MVP feature appears in at least one task's notes;
- every MVP screen is built by a task;
- every entity is created by a task.

List any gaps and fix them before showing the result.

## Phase 4: Gate and write

1. Show the milestone outline (name, goal, demo, task count, the riskiest item) in under 25 lines. **Stop for approval or changes.**
2. Write `docs/tasklist.md` and commit (`docs: task list`).

## Hand-off

Next steps:

1. Run `/new-task docs/tasklist.md M1` to create full task files for the first milestone only. Writing specs just in time keeps them accurate.
2. Review those files and set them to `Ready`.
3. Run `/next-task`.
4. Repeat for M2 when M1 is close to done.
