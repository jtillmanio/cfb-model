---
name: product-brief
description: Turns brainstorm notes (a file, pasted text, or an interview) into the brief and feature list (docs/01-product.md) and the Claude Design brief (docs/05-ui-design-brief.md), amending them in place. Use when the user runs /product-brief, is starting a new project, or asks to capture features, scope, or an MVP cut from a brainstorm.
argument-hint: (optional) path to new brainstorm notes to fold into docs/01-product.md
---

# Product brief: $ARGUMENTS

In this project the three kit outputs already exist under other names (see "Project docs" in `CLAUDE.md`). Amend them in place against the templates in `docs/templates/`; never regenerate, rename or restructure them:

| Kit output | This project | Template | Purpose |
|---|---|---|---|
| brief | `docs/01-product.md` (What we're building · Who it's for · What "good" looks like · Non-goals) | `brief.md` | Problem, users, measurable goals, non-goals, constraints, MVP success |
| features | `docs/01-product.md` › Feature set; screen inventory in `docs/05-ui-design-brief.md` › Screens | `features.md` | Feature list with IDs and priority, screen inventory, rough entities, cut list |
| design brief | `docs/05-ui-design-brief.md` (prompts in `docs/07-claude-design-playbook.md`) | (written fresh) | The prompt to paste into Claude Design |

## Phase 1: Gather (read-only)

1. Read the input:
   - If `$ARGUMENTS` is a path, read that file.
   - If the user pasted notes, use those.
   - If there's neither, interview: ask the questions below in one batch.
2. Read `docs/01-product.md`, `docs/05-ui-design-brief.md`, `docs/06-roadmap.md`, the design (`design/README.md`, `design/handoff/designs/`, `design/handoff/screenshots/`), and code, so you don't contradict what exists. Where the designs and 05 disagree, the designs win.
3. Extract every feature idea mentioned, including passing ones. Nothing gets silently dropped: each idea becomes a feature row or a cut-list entry.

## Phase 2: Fill the gaps (one batch, at most 8 questions)

Ask only what the notes don't answer. Prefer multiple choice with a recommended option. Typical gaps:

- Who are the users and on what devices?
- What's the MVP cut? Propose one: MVP = the smallest set that replaces the current workaround.
- Budget and hosting limits, offline needs, import sources
- One or two measurable success targets

**Stop until the user answers.**

## Phase 3: Write

1. **brief** (`docs/01-product.md`): one page. Goals must have a metric and a target. Every constraint gets a value or `UNKNOWN`.
2. **features** (`docs/01-product.md` › Feature set; screen inventory in `docs/05-ui-design-brief.md`):
   - IDs `F-01…`, user stories, priority MVP / Next / Later.
   - 2–3 acceptance notes per MVP feature, written as observable outcomes; they become ACs later.
   - Screen inventory `S-01…`: every MVP feature maps to at least one screen, and every screen lists the states to design (default, empty, loading, error, plus any others).
   - Rough entities.
   - Cut list with a reason for each cut.
3. **design brief** (`docs/05-ui-design-brief.md`; prompts live in `docs/07-claude-design-playbook.md`): a self-contained prompt for Claude Design containing:
   - product summary, users, devices;
   - design-system requests (palette, type scale, spacing, components) to set up before any screens;
   - the MVP screen inventory with purpose and states;
   - interaction notes;
   - constraints: phone-first or desktop-first, 44 px touch targets, light/dark;
   - the request to use the screen IDs (S-01…) as screen names, so they carry through the handoff.

## Phase 4: Hand off (under 15 lines)

- Counts: features by priority, screens, entities, open questions.
- The 3 riskiest scope decisions for the user to double-check.
- Next step: run the design prompts from `docs/07-claude-design-playbook.md` in Claude Design. When the design is done, replace the handoff bundle in `design/handoff/` (its README is `design/README.md`) and run `/architecture`.
