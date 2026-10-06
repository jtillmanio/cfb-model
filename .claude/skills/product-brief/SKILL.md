---
name: product-brief
description: Turns brainstorm notes (a file, pasted text, or an interview) into docs/product/brief.md, docs/product/features.md, and a ready-to-paste Claude Design brief. Use when the user runs /product-brief, is starting a new project, or asks to capture features, scope, or an MVP cut from a brainstorm.
argument-hint: (optional) path to brainstorm notes, e.g. docs/product/brainstorm.md
---

# Product brief: $ARGUMENTS

Produce three files from the templates in `docs/templates/`:

| Output | From template | Purpose |
|---|---|---|
| `docs/product/brief.md` | `brief.md` | Problem, users, measurable goals, non-goals, constraints, MVP success |
| `docs/product/features.md` | `features.md` | Feature list with IDs and priority, screen inventory, rough entities, cut list |
| `docs/product/design-brief.md` | (written fresh) | The prompt to paste into Claude Design |

## Phase 1: Gather (read-only)

1. Read the input:
   - If `$ARGUMENTS` is a path, read that file.
   - If the user pasted notes, use those.
   - If there's neither, interview: ask the questions below in one batch.
2. Read any existing `docs/product/*`, `design/`, and code, so you don't contradict what exists.
3. Extract every feature idea mentioned, including passing ones. Nothing gets silently dropped: each idea becomes a feature row or a cut-list entry.

## Phase 2: Fill the gaps (one batch, at most 8 questions)

Ask only what the notes don't answer. Prefer multiple choice with a recommended option. Typical gaps:

- Who are the users and on what devices?
- What's the MVP cut? Propose one: MVP = the smallest set that replaces the current workaround.
- Budget and hosting limits, offline needs, import sources
- One or two measurable success targets

**Stop until the user answers.**

## Phase 3: Write

1. **brief.md**: one page. Goals must have a metric and a target. Every constraint gets a value or `UNKNOWN`.
2. **features.md**:
   - IDs `F-01…`, user stories, priority MVP / Next / Later.
   - 2–3 acceptance notes per MVP feature, written as observable outcomes; they become ACs later.
   - Screen inventory `S-01…`: every MVP feature maps to at least one screen, and every screen lists the states to design (default, empty, loading, error, plus any others).
   - Rough entities.
   - Cut list with a reason for each cut.
3. **design-brief.md**: a self-contained prompt for Claude Design containing:
   - product summary, users, devices;
   - design-system requests (palette, type scale, spacing, components) to set up before any screens;
   - the MVP screen inventory with purpose and states;
   - interaction notes;
   - constraints: phone-first or desktop-first, 44 px touch targets, light/dark;
   - the request to use the screen IDs (S-01…) as screen names, so they carry through the handoff.

## Phase 4: Hand off (under 15 lines)

- Counts: features by priority, screens, entities, open questions.
- The 3 riskiest scope decisions for the user to double-check.
- Next step: paste `docs/product/design-brief.md` into Claude Design. When the design is done, export a handoff bundle into `design/` and run `/architecture`.
