# CLAUDE.md

Personal sports-analytics app. A college football model makes game predictions, compares them to spreads (market and Splash pick'em contest lines), recommends picks, ranks teams (later also seasons, programs and coaches across history), projects seasons, and tracks its own record. Multi-sport later.

**Status:** planning complete, Phase 0 next. Status lives in the `docs/06-roadmap.md` checklists.

## Where things are
- `docs/01`–`07`: product, architecture, data model, model, UI brief, roadmap, Claude Design playbook. Read the relevant one before starting a phase task.
- `design/`: mock sample data, Claude Design exports (the visual reference) and handoff bundles.
- `.claude/rules/`: area rules (git always; python, database and web by path).
- **Precedence when sources disagree:** code and migrations > this file and `.claude/rules/` > `docs/`. Fix the loser in the same PR. Take counts and numbers from code or data, never from prose.

### Project docs (which file fills each starter-kit role)
The kit's skills and agents use these paths. `docs/claude-kit/` holds the kit's own guides, which use generic names (`docs/product/*`, `docs/architecture.md`, `docs/tasklist.md`); read them through this map.

| Kit role | This project |
|---|---|
| Brief (problem, users, goals, non-goals) | `docs/01-product.md` (What we're building · Who it's for · What "good" looks like · Non-goals) |
| Features (priorities, MVP cut) | `docs/01-product.md` › Feature set (MVP = end of Phase 4) |
| Screen inventory | `docs/05-ui-design-brief.md` › Screens; the as-designed list is `design/README.md` › Screens |
| Architecture | `docs/02-architecture.md` |
| Data model | `docs/03-data-model.md` (`python/db/` wins once it exists) |
| Model spec | `docs/04-model.md` |
| Design intent | `docs/05-ui-design-brief.md` |
| Design source of truth | `design/handoff/designs/` (board notes are the spec; bundle README is `design/README.md`) |
| Design tokens | `design/handoff/tokens/` (color; type, spacing, radius and elevation values are in `design/README.md` › Design tokens) |
| Reference screenshots | `design/handoff/screenshots/` (default state, dark, 1440 and 390) |
| Design playbook | `docs/07-claude-design-playbook.md` |
| Roadmap (status source of truth) | `docs/06-roadmap.md` |
| Task list | `docs/08-tasklist.md` (written by `/milestones`; task files in `docs/tasks/`) |
| Decisions | `docs/decisions.md` |
| Sample data / fixture seeds | `design/sample-data.md`, `design/sample-splash.txt`, `design/handoff/designs/*-data.js` |

**Designs vs 05:** where `design/handoff/designs/` and `docs/05-ui-design-brief.md` disagree, the designs win unless the user says otherwise. What the model computes and how numbers are defined still follow `04-model.md` and this file.

## Domain conventions
- `margin = home_points − away_points`. `spread_home` is negative when home is favored (CFBD convention). Home covers if `margin + spread_home > 0`; push if `= 0`.
- **Point-in-time:** anything used to predict a game uses only data available before kickoff. Ratings at `(season, week=N)` mean "entering week N". Never use season-aggregate stats in a backtest.
- Ratings, predictions and picks are **immutable**; re-runs insert new rows tied to a `model_run`. Results, records, ranks and CLV are **views**, never stored.
- The raw lake is append-only; transforms must rebuild from raw with zero API calls. Never re-fetch completed CFBD weeks (call budget).

## Stop and ask before
- Any schema change (new table or column, a type change, a dropped column) or changing how a stored date or line is interpreted
- Touching any database other than test/dev, or running anything with `.env.live`
- Deleting or rewriting user data (contest entries, adjustments, lab models) or live predictions/picks
- Creating GitHub repos, changing visibility, or editing secrets
- Anything where the task is ambiguous. Ask rather than guess.

## Working with the user
The user is an experienced software developer, new to statistical modeling. Explain modeling concepts and the reasoning behind choices briefly as you go, linking to `docs/04-model.md`. Engineering explanations can stay terse.

## Commands
_(Added in Phase 0.)_
