---
name: architecture
description: Produces docs/architecture.md and seeds docs/decisions.md from the product brief, feature list, and design — presenting each key technical decision as options with trade-offs for the user to choose. Use when the user runs /architecture or asks to design the system, pick a stack, or write the architecture doc.
argument-hint: (optional) focus area or constraint, e.g. "must use Postgres"
---

# Architecture $ARGUMENTS

Output: `docs/architecture.md`, following `docs/templates/architecture.md` section by section, plus seeded rows in `docs/decisions.md`.

## Phase 1: Read (read-only)

1. Read `docs/product/brief.md` and `docs/product/features.md`. If either is missing, stop and suggest `/product-brief`.
2. Read the design:
   - Everything under `design/`, including a Claude Design handoff bundle if present.
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

1. **docs/architecture.md** with every template section:
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
