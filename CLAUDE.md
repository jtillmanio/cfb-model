# CLAUDE.md

Personal sports-analytics app. A college football model makes game predictions, compares them to spreads (market and Splash pick'em contest lines), recommends picks, ranks teams (later also seasons, programs and coaches across history), projects seasons, and tracks its own record. Multi-sport later.

**Status:** planning complete, Phase 0 next. Status lives in the `docs/06-roadmap.md` checklists.

## Where things are
- `docs/01`–`07`: product, architecture, data model, model, UI brief, roadmap, Claude Design playbook. Read the relevant one before starting a phase task.
- `design/`: mock sample data, Claude Design exports (the visual reference) and handoff bundles.
- `.claude/rules/`: area rules (git always; python, database and web by path).
- **Precedence when sources disagree:** code and migrations > this file and `.claude/rules/` > `docs/`. Fix the loser in the same PR. Take counts and numbers from code or data, never from prose.

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
