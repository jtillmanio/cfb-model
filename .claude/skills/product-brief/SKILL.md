---
name: product-brief
description: Turns brainstorm notes (a file, pasted text, or an interview) into a product brief, a feature list with a screen inventory, and a ready-to-paste Claude Design brief. Use when the user runs /product-brief, is starting a new project, or asks to capture features, scope, or an MVP cut from a brainstorm.
argument-hint: (optional) path to brainstorm notes, e.g. docs/product/brainstorm.md
---

# Product brief: $ARGUMENTS

> **Doc roles:** names in **bold** such as **Architecture**, **Data model**, or **Design tokens** are roles in the "Project docs" table in `CLAUDE.md`. Always read and write the path the table gives for a role, including a `§ section` if it names one. The path in parentheses is only the default, used when the table is missing. If a role maps to `—`, follow the fallback stated in the step, or ask. Refer to sections by name, never by number.

> **Project overrides:** read `.claude/project/product-brief.md` if it exists. It holds this project's instructions for this skill and wins where it conflicts with this file, except that it can't lower the floor: never overwrite existing docs, and stop for the user's answers before writing.

Produce these outputs from the templates in `docs/templates/`, writing each to the path its role maps to in the Project docs table. When two roles map to the same file, write both into that file as separate sections. When a role maps to a `§ section` of a file, write or update only that section.

| Output | From template | Purpose |
|---|---|---|
| **Product brief** (default `docs/product/brief.md`) | `brief.md` | Problem, users, measurable goals, non-goals, constraints, MVP success |
| **Features** (default `docs/product/features.md`) | `features.md` | Feature list with IDs and priority, rough entities, cut list |
| **Screen inventory** (default `docs/product/features.md` § Screen inventory) | `features.md` § Screen inventory | Screen IDs, purpose, features, states to design |
| **Design brief / intent** (default `docs/product/design-brief.md`) | (written fresh) | The prompt to paste into Claude Design |

## Phase 1: Gather (read-only)

1. Read the input:
   - If `$ARGUMENTS` is a path, read that file.
   - If the user pasted notes, use those.
   - If there's neither, interview: ask the questions below in one batch.
2. Read whatever already exists for these roles, the **Design source of truth**, and the code, so you don't contradict what's there. If any of these outputs already exist, append or update sections. Never overwrite, and confirm before changing existing text.
3. Extract every feature idea mentioned, including passing ones. Nothing gets silently dropped: each idea becomes a feature row or a cut-list entry.

## Phase 2: Fill the gaps (one batch, at most 8 questions)

Ask only what the notes don't answer. Prefer multiple choice with a recommended option. Typical gaps:

- Who are the users and on what devices?
- What's the MVP cut? Propose one: MVP = the smallest set that replaces the current workaround.
- Budget and hosting limits, offline needs, import sources
- One or two measurable success targets

**Stop until the user answers.**

## Phase 3: Write

1. **Product brief**: one page. Goals must have a metric and a target. Every constraint gets a value or `UNKNOWN`.
2. **Features**:
   - IDs `F-01…`, user stories, priority MVP / Next / Later.
   - 2–3 acceptance notes per MVP feature, written as observable outcomes; they become ACs later.
   - Rough entities.
   - Cut list with a reason for each cut.
3. **Screen inventory**: `S-01…`. Every MVP feature maps to at least one screen, and every screen lists the states to design (default, empty, loading, error, plus any others).
4. **Design brief**: a self-contained prompt for Claude Design containing:
   - product summary, users, devices;
   - design-system requests (palette, type scale, spacing, components) to set up before any screens;
   - the MVP screen inventory with purpose and states;
   - interaction notes;
   - constraints: phone-first or desktop-first, 44 px touch targets, light/dark;
   - the request to use the screen IDs (S-01…) as screen names, so they carry through the handoff.

## Phase 4: Hand off (under 15 lines)

- Counts: features by priority, screens, entities, open questions.
- The 3 riskiest scope decisions for the user to double-check.
- Next step: paste the **Design brief** into Claude Design. When the design is done, export a handoff bundle into the **Design source of truth** folder (default `design/`) and run `/architecture`.
