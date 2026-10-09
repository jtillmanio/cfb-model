---
name: architecture
description: Produces the architecture doc (and data model) and seeds the decisions log from the product brief, feature list, and design — presenting each key technical decision as options with trade-offs for the user to choose. Use when the user runs /architecture or asks to design the system, pick a stack, or write the architecture doc.
argument-hint: (optional) focus area or constraint, e.g. "must use Postgres"
---

# Architecture $ARGUMENTS

> **Doc roles:** names in **bold** such as **Architecture**, **Data model**, or **Decisions** are roles in the "Project docs" table in `CLAUDE.md`. Always read and write the path the table gives for a role, including a `§ section` if it names one. The path in parentheses is only the default, used when the table is missing. If a role maps to `—`, follow the fallback stated in the step, or ask. Refer to sections by name, never by number.

> **Project overrides:** read `.claude/project/architecture.md` if it exists. It holds this project's instructions for this skill and wins where it conflicts with this file, except that it can't lower the floor: the user chooses every decision at the gate.

Output: the **Architecture** doc (default `docs/architecture.md`), following `docs/templates/architecture.md` section by section. If **Data model** maps to a separate file, put the data model there and link to it from the architecture doc. Also seed rows in the **Decisions** log (default `docs/decisions.md`); if it doesn't exist, create it from `docs/templates/decisions.md` and use the ID prefix the Project docs table names (default `D-`). If these docs already exist, amend them by appending or updating sections, never overwriting, and confirm before changing existing text.

## Phase 1: Read (read-only)

1. Read the **Product brief**, **Features**, and **Screen inventory**, plus any **Domain specs**. If the brief or features are missing, stop and suggest `/product-brief`.
2. Read the design:
   - The **Design source of truth** (default `design/`), **Design tokens**, and **Reference screenshots**, including any handoff README or manifest.
   - Note the screens, components, design tokens, and any data the screens display. That data implies the entities and queries.
3. Read existing code, `CLAUDE.md`, and the **Decisions** log if present.
4. Infer the entities from three sources: the features' data columns, what the screens display, and the import sources. List any conflicts between them.

## Phase 2: Decide (gate)

For each decision that matters (stack, database and migrations, ORM/data access, auth, hosting, testing tools, state management, anything the constraints force):

1. Present 2–3 options in a table: option, fit with the constraints, cost ($/month at the stated scale), complexity, lock-in, and recommendation.
2. Mark a decision **pre-decided** when the brief's constraints or the user's stated preferences already settle it, and say why.
3. Batch all decisions into one message. **Stop until the user chooses.**

Recommend boring, well-documented choices with free tiers that fit the stated scale. A solo project should not need more than one deployable unit.

If the project has a database, also offer these as decisions:

- **Environment ladder.** Options: (a) one development database plus a separate test database (the minimum: tests never touch development data); (b) the full ladder: production, a database per PR preview (if the host has previews), test, and development. With (b): the default env file is never production; the production connection string sits only in a gitignored file that a command reads only when given an explicit flag; and a "live" switch (an env var such as `APP_LIVE=true`) makes every destructive script (rebuild, reload, truncate) refuse. Recommend (b) once real data exists.
- **Down files for destructive migrations.** If the migration tool is forward-only: a migration that drops, retypes, or merges columns ships a hand-written down file and an up → down → up test that asserts row values, not just that it ran. Recommend yes whenever the data can't be regenerated.
- **How merged code goes live.** Deploy on merge, or a hand-run release (CI passed on the exact commit → snapshot the database → migrate → re-apply derived objects → promote → smoke-test a health route). Recommend the hand-run release when migrations touch data that can't be regenerated. `docs/templates/github/release.yml` is the starting point.

## Phase 3: Write

1. **Architecture doc** (and **Data model** doc if separate) with every template section:
   - Data model: a mermaid ER diagram plus a table per entity (fields, types, keys, constraints, indexes). Explicitly state what is stored vs. derived.
   - Feature traceability: every MVP feature maps to screens, components, and entities. Flag any MVP feature that maps to nothing.
   - NFRs: each one with a number.
   - Testing strategy: tools, coverage per level, the test database and how tests are kept off every other database, and the seed data ACs will cite.
   - Environments: the chosen ladder, which env file names which database, and which commands may touch which one.
   - Walking skeleton spec: the thinnest end-to-end slice that exercises every layer once.
   - Risks: each with a mitigation or a spike.
2. **Decisions** log: one row per decision, with the rejected alternatives and a "revisit if" condition.
3. **Hard-rule candidates**: list 3–6 rules for CLAUDE.md (e.g. "derived values are never stored"; "tests read the test database URL only, never the app's, with no fallback"). `/customize-kit` asks the user to confirm them later.

## Phase 4: Hand off (under 15 lines)

- Decisions made, entity count, NFRs, and the top 3 risks.
- Any spike that should run before the skeleton.
- Next step: `/skeleton`.
