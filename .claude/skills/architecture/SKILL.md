---
name: architecture
description: Produces the architecture doc (and data model) and seeds docs/decisions.md from the product brief, feature list, and design — presenting each key technical decision as options with trade-offs for the user to choose. Use when the user runs /architecture or asks to design the system, pick a stack, or write the architecture doc.
argument-hint: (optional) focus area or constraint, e.g. "must use Postgres"
---

# Architecture $ARGUMENTS

> **Doc roles:** names in **bold** such as **Architecture**, **Data model**, or **Design tokens** are roles in the "Project docs" table in `CLAUDE.md`. Always read and write the path the table gives for a role, including a `§ section` if it names one. The path in parentheses is only the default, used when the table is missing. If a role maps to `—`, follow the fallback stated in the step, or ask. Refer to sections by name, never by number.

Output: the **Architecture** doc (default `docs/architecture.md`), following `docs/templates/architecture.md` section by section. If **Data model** maps to a separate file, put the data model there and link to it from the architecture doc. Also seed rows in `docs/decisions.md`. If these docs already exist, amend them by appending or updating sections, never overwriting, and confirm before changing existing text.

## Phase 1: Read (read-only)

1. Read the **Product brief**, **Features**, and **Screen inventory**, plus any **Domain specs**. If the brief or features are missing, stop and suggest `/product-brief`.
2. Read the design:
   - The **Design source of truth** (default `design/`), **Design tokens**, and **Reference screenshots**, including any handoff README or manifest.
   - Note the screens, components, design tokens, and any data the screens display. That data implies the entities and queries.
3. Read existing code, `CLAUDE.md`, and `docs/decisions.md` if present.
4. Infer the entities from three sources: the features' data columns, what the screens display, and the import sources. List any conflicts between them.

## Phase 2: Decide (gate)

For each decision that matters (stack, database and migrations, ORM/data access, auth, hosting, testing tools, state management, anything the constraints force):

1. Present 2–3 options in a table: option, fit with the constraints, cost ($/month at the stated scale), complexity, lock-in, and recommendation.
2. Mark a decision **pre-decided** when the brief's constraints or the user's stated preferences already settle it, and say why.
3. Batch all decisions into one message. **Stop until the user chooses.**

Recommend boring, well-documented choices with free tiers that fit the stated scale. A solo project should not need more than one deployable unit.

## Phase 3: Write

1. **Architecture doc** (and **Data model** doc if separate) with every template section:
   - Data model: a mermaid ER diagram plus a table per entity (fields, types, keys, constraints, indexes). Explicitly state what is stored vs. derived.
   - Feature traceability: every MVP feature maps to screens, components, and entities. Flag any MVP feature that maps to nothing.
   - NFRs: each one with a number.
   - Testing strategy: tools, coverage per level, and the seed data that ACs will cite.
   - Walking skeleton spec: the thinnest end-to-end slice that exercises every layer once.
   - Risks: each with a mitigation or a spike.
2. **docs/decisions.md**: one row per decision (D-001…), with the rejected alternatives and a "revisit if" condition.
3. **Hard-rule candidates**: list 3–6 rules for CLAUDE.md (e.g. "derived values are never stored"). `/customize-kit` asks the user to confirm them later.

## Phase 4: Hand off (under 15 lines)

- Decisions made, entity count, NFRs, and the top 3 risks.
- Any spike that should run before the skeleton.
- Next step: `/skeleton`.
