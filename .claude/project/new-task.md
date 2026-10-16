# new-task: project section

Read by `/new-task` at the start. It wins where it conflicts with the skill, except for the kit's floor. `/milestones`, `/plan-batch` and `/implement-task` point here for the size limits, so this is the one place they're set.

## Size limits

These replace the skill's file counts. Layers and the schema-plus-UI rule are unchanged.

- **S**: ≤ 4 files, one layer (UI, API, or data). One sitting.
- **M**: ≤ 12 files, at most two adjacent layers (e.g. API + UI). One sitting.
- **Larger** (more than 12 files, or schema + UI together): split, by `workflow.splitPolicy` as the skill says.

Every file counts, docs included (README, `docs/`, the decisions log). The task file itself doesn't count.

- **Why:** 8 files for M was too tight. A task's doc edits (README, architecture, decisions, owner checklist) pushed coherent one-sitting tasks over the limit and forced splits that only separated code from its docs (owner's instruction, 2026-10-16; TASK-025 was the example).
- **Autonomy is unchanged:** `unattended` still needs size S, or M within a single layer, plus the skill's other conditions.
- **The template's comment is stale:** `docs/tasks/_TEMPLATE.md` still says `<=3` and `<=8` files. It's a kit file and an upgrade overwrites it, so the numbers here win.
