---
id: TASK-066
title: Carry the last game's date for the "season ended" line
status: Done
depends_on: [TASK-062]
size: S
model: sonnet
autonomy: attended
ui: true
plan_status: approved
planned_at_commit: dcf5942
---

# TASK-066 — Carry the last game's date for the "season ended" line

## Goal

The off-season frame says when the season ended, as the design draws it: "The 2026 season ended with the title game on Mon Jan 18."

## Context

- Task list: `docs/08-tasklist.md` › M5 › M5.14.
- Design: `design/handoff/designs/App States Desktop.dc.html` (`frame="offseason"`).
- *From TASK-062 (feat/task-062-name-next-season-off-season):* the response carries only the next season; the design's last-game date needs a field (the newest game's date, Eastern) on `/slate` or the shell, and the frame's body to print it.
- Decisions: D-164.

## Acceptance criteria

- [x] AC-1: Given the API at the off-season clock (Mon 2027-02-08 6:00 AM ET), `/slate` carries the date of the last game of the season that ended (expected: the fixture's newest game date).
- [x] AC-2: At that clock the frame body reads "The 2026 season ended with the title game on <weekday> <month> <day>", and omits the clause when the field is null.

## Out of scope

- Any change to how a stored date is interpreted.

## Files likely touched

- `python/api/src/api/shell.py` or `slate.py`, `python/api/tests/`: the field
- `web/lib/api-types.ts`, `web/lib/slate.ts`, `web/app/(this-week)/slate-empty.tsx`: the copy

## Verification

- Automated: the API test at the off-season clock; `web/lib/slate.test.ts`
- Manual: `pnpm dev` at the off-season clock → expected: `20-offseason-empty-desktop.png`.

## Follow-ups

_Work noticed during this task and deliberately left out. Each bullet ends `→ <path> § <section>` (where it was placed) or `→ not tracked: <reason>`. See `.claude/skills/track-follow-ups/classify.md`; the PR's Follow-ups section is copied from here._

- A decision row for `/slate`'s `last_game_date`, amending D-164 (whose "Not done" names this line) (approved at plan) → docs/decisions.md § D-168 (D-164 gains the pointer "Amended by D-167, D-168")
- The clause names the season's newest non-canceled game as "the title game", which is right only once the postseason is loaded; and a `postponed` game would count if the transform ever wrote one (schema review, minor) → docs/decisions.md § D-168 (Revisit if)

## Plan

Approved 2026-11-13 by the owner.

**Approach:** `/slate` gains `last_game_date` (a date, `YYYY-MM-DD`), set only when `offseason`: the newest `game_date` (Eastern, as stored) among the ended season's games that weren't canceled. It rides in the existing `weeks` statement as `max(game_date) FILTER (WHERE status <> 'canceled')` per week, so `/slate` adds no query (it is at its 6-query budget, D-163) and the shell statement every screen runs is unchanged.

**Steps**
1. Tests first (below); confirm each fails for the expected reason.
2. `python/api/src/api/slate.py`: `WEEKS_SQL` gains `last_date`; `SlateOut.last_game_date: date | None`, the latest `last_date` among the weeks of `shell.season`, set only when `offseason`, else None.
3. `pnpm --dir web api:types` regenerates `web/lib/api-types.ts`.
4. `web/lib/slate.ts` `offseasonNote`: a `lastGameDate` argument. With it the body reads "The 2026 season ended with the title game on Sat Oct 10." (weekday, month, day; formatted in UTC from the date so it never shifts a day); without it, "The 2026 season has ended." as now.
5. `web/app/(this-week)/slate-empty.tsx` and `slate.tsx`: pass `slate.last_game_date` through.

**Files**
- `python/api/src/api/slate.py`: the field and the `weeks` aggregate
- `python/api/tests/test_api_slate.py`: AC-1
- `web/lib/api-types.ts`: regenerated
- `web/lib/slate.ts`, `web/lib/slate.test.ts`: the copy, AC-2
- `web/app/(this-week)/slate-empty.tsx`, `web/app/(this-week)/slate.tsx`: pass it through (`slate.tsx` not in "Files likely touched")
- `web/app/(this-week)/slate.test.tsx`: the rendered frame (not in "Files likely touched")
- Close-out: `docs/decisions.md`, `docs/08-tasklist.md`

**Test strategy**
- AC-1: `test_api_slate.py` › `test_the_offseason_slate_carries_the_last_game_date`: the off-season clock gives `"2026-10-10"` (the fixture's newest game); null in season. A `load` test in `db_conn` adds a later canceled game to the ended season and the date doesn't move.
- AC-2: `slate.test.ts` › `offseasonNote` with a date gives "The 2026 season ended with the title game on Sat Oct 10. The 2027 slate fills in …"; without one, "The 2026 season has ended. …". `slate.test.tsx`: the off-season frame prints the dated sentence when the response carries `last_game_date`, the undated one when null.
- Manual: `pnpm dev` at the off-season clock → `20-offseason-empty-desktop.png`.

**Risks:** the fixture's newest game is a regular-season Saturday, so in tests the copy reads "title game on Sat Oct 10". The AC fixes the wording, and in production the off-season starts only once no game is left to come, so the newest game is the title game.

**Size:** 9 files, no schema change.

## Review log

Verify R1 PASS (full e2e: 2 phone specs, /teams and the waking-database note, timed out once in the `/verify` run, passed in isolation and in a full re-run; neither touches /slate) | Audit R1 PASS (static note: the season-filter test didn't discriminate; the earlier-season game is now dated after the newest, and removing the filter fails it) | Spec R1 APPROVE | Schema R1 APPROVE (2 minor, recorded in D-168) | UI R1 PASS (phone, tablet, desktop at the off-season clock)

## Blocked

_Only if status is Blocked: what failed, what was tried, best hypothesis, decision needed._

## Metrics

- Verify rounds: 1
- Review rounds: 1
- First-pass AC FAILs: 0
- Plan revisions after approval: 0
