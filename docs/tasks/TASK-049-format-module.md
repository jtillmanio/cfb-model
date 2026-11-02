---
id: TASK-049
title: Implement format.ts against the number-format card
status: Ready
depends_on: []
size: S
model: sonnet
autonomy: unattended
ui: false
plan_status: none
planned_at_commit:
---

# TASK-049 — Implement format.ts against the number-format card

## Goal

Every number the app shows (spreads, model lines, edges, percentages, records, units, CLV, kickoff times, live scores) comes from one formatting module, so each kind of number looks the same on every screen and a model line never looks like a market line.

## Context

- Task list: `docs/08-tasklist.md` › M5 › M5.1.
- Design: `design/README.md` § Number formats (the card: every number on every screen is one of these); `design/handoff/designs/Foundations.dc.html`; `Review Checks.dc.html` §04 (whole-number spreads padded with U+2008 + U+2007 so units digits align).
- Architecture: `docs/02-architecture.md` › Testing strategy › Levels (Unit: web) lists the card's examples this task turns into Vitest cases: `OSU −27.5`, `BSU −10` padded, `PK`, `−110`, `CLEM −34.0`, `+3.7 OSU`, `59%`, `~54%`, `TEX 54%`, `+27.4`, `▲3 ▼1 —`, `31-24-1`, `5-0`, `+4.6u`, `−1.1u`, `+0.9 pts`, `Sat 3:30 PM ET`, `Locks in 1d 14h`, `PUR 3 · OSU 24`, `Q3 9:12`.
- Decisions: D-068 (one `format.ts`, true minus U+2212, model lines one decimal, whole spreads padded), D-064 (ratings in ink: formatting only, no color), D-132 and D-140 (CLV sign: positive means the pick beat the close; the design's "+1.0" on Ole Miss has it backwards), D-097 (no "up to 30 seconds" copy; not a number this module formats, noted so it isn't reintroduced).
- Conventions: `spread_home` is negative when home is favored (CLAUDE.md › Domain conventions). The formatter takes `spread_home` and both abbreviations and names the favorite.
- `games.kickoff_at` is NULL while the kickoff is TBA (`python/db/src/db/models.py`, `.claude/rules/database.md` "Unknown is NULL"); the formatter is given `game_date` too. The design draws no TBA kickoff, so the copy here (`Sat TBA`) is proposed; change it at the plan gate if the owner wants other words.
- "Now" is an argument, never read inside the module (lock countdown), so tests need no clock and the screens pass the page's own time. The kickoff zone is an argument too (America/New_York until M8.8's time-zone setting).
- `.claude/rules/web.md`: "All number display goes through the shared formatting module"; pure helpers live in `web/lib/*.ts` with a Vitest test beside them (`web/lib/teams.ts` / `teams.test.ts` is the pattern).

## Acceptance criteria

- [ ] AC-1: Given each example on the number-format card listed in 02 › Testing strategy (Unit: web), the matching `format.ts` function returns exactly that string, one Vitest case per example (expected: `OSU −27.5` from spread_home −27.5 with home OSU; `BSU −10`; `PK` from 0; `No line` from null; `−110`; `CLEM −34.0`; `+3.7 OSU`; `59%`; `~54%` for a market-implied value; `TEX 54%`; `56.4%`; `+27.4`; `▲3`, `▼1`, `—`; `31-24-1`; `5-0`; `+4.6u`; `−1.1u`; `+0.9 pts`).
- [ ] AC-2: Every negative number any function returns uses U+2212, never a hyphen-minus (a test runs every function over negative inputs and finds no `-`), and none returns a negative zero (`−0.0`, `−0.0u`, `−0.0 pts`) for a value that rounds to zero.
- [ ] AC-3: Given a whole-number spread with the align flag, the spread formatter returns it followed by U+2008 + U+2007 (`BSU −10` + `  `), so it is as wide in tabular figures as `BSU −9.5`; without the flag it returns `BSU −10` bare; a model line from 34 returns `CLEM −34.0` with or without the flag.
- [ ] AC-4: Given kickoff `2026-10-10T19:30:00Z` and zone America/New_York, the kickoff formatter returns `Sat 3:30 PM ET`, and `Sat 3:30 PM` with the in-table option (header says ET); with zone America/Chicago it returns `Sat 2:30 PM CT`; given a NULL kickoff and `game_date` 2026-10-10 it returns `Sat TBA`.
- [ ] AC-5: Given kickoff minus now of 1 d 14 h 5 m, 3 h 20 m 40 s and 12 m 30 s, the lock countdown returns `Locks in 1d 14h`, `Locks in 3h 20m` and `Locks in 12m`; at or after kickoff it returns `Locked`.
- [ ] AC-6: The live-score formatter returns `PUR 3 · OSU 24` (away first) and the clock `Q3 9:12`; the final formatter returns `Final · UNLV 24, BSU 31`.

## Out of scope

- Components that use these strings (edge pill, tier badge, team chip, market cell): TASK-050 and TASK-051.
- Choosing the colour of a number (pos/neg for units and CLV, ink for ratings): that's the component's job; this module returns text only.
- The user's time-zone setting and the device toggle (M8.8); this task only takes the zone as an argument.
- Reading pick thresholds from the spec (the edge pill's filled state): TASK-050.

## Files likely touched

- `web/lib/format.ts` — new: the formatting functions.
- `web/lib/format.test.ts` — new: one case per card example, plus AC-2 to AC-6.

## Verification

- Automated: `pnpm --dir web exec vitest run lib/format.test.ts` passes, with a case for each AC; the AC-2 sweep fails if any function is changed to emit a hyphen-minus.
- Manual: none (no screen uses the module yet).

## Follow-ups

_Work noticed during this task and deliberately left out. Each bullet ends `→ <path> § <section>` (where it was placed) or `→ not tracked: <reason>`. See `.claude/skills/track-follow-ups/classify.md`; the PR's Follow-ups section is copied from here._

## Plan

_Written by /plan-batch or /implement-task Phase 1. Approved by the user (plan_status: approved) before any code is written._

## Review log

_Filled by /implement-task. One line per round._

## Blocked

_Only if status is Blocked: what failed, what was tried, best hypothesis, decision needed._

## Metrics

- Verify rounds:
- Review rounds:
- First-pass AC FAILs:
- Plan revisions after approval:
