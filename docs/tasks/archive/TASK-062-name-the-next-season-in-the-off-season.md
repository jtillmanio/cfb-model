---
id: TASK-062
title: Name the next season in the off-season
status: Done
depends_on: [TASK-057]
size: M
model: sonnet
autonomy: attended
ui: true
plan_status: approved
planned_at_commit: 2ec3c70
---

# TASK-062 — Name the next season in the off-season

## Goal

In the off-season the app names the coming season and its week 0 (the design's "2027 · Week 0 · off-season" and "Week 0 kicks off Sat Aug 28, 2027"), instead of naming the season that just ended.

## Context

- Design: `design/handoff/designs/App States Desktop.dc.html` and `App States Mobile.dc.html` (`frame="offseason"`); shots `20-offseason-empty-desktop.png`, `21-offseason-empty-mobile.png`.
- Decisions: D-156 (the shell block rides in each screen's one call), D-157, D-158 (`/slate`).
- *From TASK-057 (PR #141), open question for the plan:* TASK-053's open question stayed open. TASK-057 left the shell as it was: in the off-season `/slate` sends `season: null`, `shell.season` is the last season with games and the top bar, the caption and the empty frame's copy name that season ("2026 · off-season", "The 2026 season has ended"). The design names the next season ("2027 · Week 0") and adds "title game on Mon Jan 18". Decide: whether the shell block names the next season and its week 0 (from `seasons.weeks`); whether a season with no record yet shows the previous season's final record ("Model · 2025 final"); and whether the response carries the last game's date for the "season ended" line.
- TASK-057 reads an optional `next_kickoff_at` on `/slate` (`web/lib/slate.ts` `Slate`, `offseasonNote`): add the field to the API and the web type then, and the "Week 0 kicks off …" line appears with no web change.
- The web app never guesses the next season; any new name comes from the API.

## Acceptance criteria

- [x] AC-1: Given the API at the off-season clock (Mon 2027-02-08 6:00 AM ET), `/slate` carries `next_kickoff_at`, the next season's first kickoff from `seasons.weeks` (expected: the fixture's value; null when the next season has no weeks yet).
- [x] AC-2: At that clock This Week's frame shows "Week 0 kicks off <weekday> <month> <day>, <year>" from that field, and hides the line when the field is null.
- [x] AC-3: The plan settles and records (a decisions-log row, if it needs one) whether the shell's season and week name the next season, and AC-4 follows that ruling.
- [x] AC-4: The caption and top bar name the season the ruling picks (expected: "2027 · Week 0 · off-season" if the next season is named).

## Out of scope

- The stale-lines banner and the week selector (TASK-061).
- Any change to how a stored date or line is interpreted.

## Files likely touched

- `python/api/src/api/slate.py`, `python/api/tests/test_api_slate.py` — `next_kickoff_at` and the shell block
- `web/lib/api-types.ts` — regenerated
- `web/lib/slate.ts`, `web/app/(this-week)/slate-empty.tsx` — drop the optional type
- `docs/decisions.md` — the ruling, if it needs a row

## Verification

- Automated: the API test at the off-season clock; a component test of the frame with the field set and null.
- Manual: `pnpm dev` at the off-season clock → expected: `20-offseason-empty-desktop.png`.

## Follow-ups

_Work noticed during this task and deliberately left out._

- Pull the next season's calendar in the off-season so the kickoff line and the next season's name show before July (the jobs pull a season's calendar only from July, with its games) → docs/tasks/TASK-065-pull-next-seasons-calendar-in-the-off-season.md (new, Draft)
- The design's "The 2026 season ended with the title game on Mon Jan 18" line: the response would carry the last game's date → docs/tasks/TASK-066-carry-the-last-games-date-for-the-season-ended-line.md (new, Draft)
- D-164: the off-season shell names the next season and its first week from `seasons.weeks` (amends D-156) → docs/decisions.md § D-164
- `docs/02-architecture.md` § Seed data said `"offseason": 2027 week 0`; D-164's fixture is week 1 → docs/02-architecture.md § Seed data (approved at close-out)
- AC-2 and AC-4 still quote "Week 0"; the owner's ruling at the plan gate (D-164) made it "Week 1". The ACs are the owner's to reword → not tracked: owner's ACs; raised in the PR

## Plan

**Ruling (AC-3, D-164, amends D-156):** the shell keeps `season` as the season that just ended (its record stays "Model · 2026 final", as the design draws it) and gains `next_season` and `next_week`, set only when there is no coming week and `seasons` holds a later season whose first week starts after now. `/slate` gains `next_kickoff_at`, that week's `start`. Week numbers come from the data: CFBD numbers the opening Saturday week 1, so "2027 · Week 1 · off-season" and "Week 1 kicks off Sat Aug 28, 2027", not the design's fixed "Week 0" (owner, plan gate). The "season ended with the title game on …" line stays out (follow-up).

**Findings:** `/slate`'s wave is at the 6-query budget (D-163), so the fields ride in the shell statement as one more CTE over `seasons`. CFBD's calendar `start` equals its `firstGameStart` (Sat 07:00Z, 3 AM ET), so its Eastern date is the opening Saturday. Production pulls a season's calendar only from July (`jobs.current_season`), with its games, so until then the next season is unknown and the app shows "2026 · off-season" with no kickoff line.

**Steps**

1. Tests first (AC-1, AC-4): API tests at the off-season clock; see them fail.
2. `SHELL_SQL`: a `next_week` CTE (the earliest week `start` after now in a season after `season`, only with no coming week); `ShellOut.next_season`, `next_week`; `SlateOut.next_kickoff_at` from the shell row (no new query).
3. Fixture: `week6.json` gains `next_season` (2027, CFBD-shaped, week 1 from Sat 2027-08-28 07:00Z); `engine/fixture.py` upserts it.
4. `pnpm api:types`; drop the optional `next_kickoff_at` type in `web/lib/slate.ts`.
5. Web: `shell.ts` `weekLabel` and `slateCaption` name the next season and week ("2027 · Week 1 · off-season"); the empty frame's kickoff line and copy use the data's week and season.
6. D-164 in `docs/decisions.md`; D-156 "Amended by D-164".

**Files:** `python/api/src/api/shell.py`, `python/api/src/api/slate.py`, `python/api/tests/test_api_shell.py`, `python/api/tests/test_api_slate.py`, `python/db/seeds/fixture/week6.json`\*, `python/engine/src/engine/fixture.py`\*, `web/lib/api-types.ts`, `web/lib/slate.ts`, `web/lib/slate.test.ts`, `web/lib/shell.ts`\*, `web/lib/shell.test.ts`\*, `web/app/(this-week)/slate-empty.tsx`, `web/app/(this-week)/slate.tsx`\*, `web/app/(this-week)/slate.test.tsx`, `docs/decisions.md` (\* not in Files likely touched).

**Test strategy**

- AC-1: `test_api_slate.py`: the off-season clock gives `next_kickoff_at` 2027-08-28T07:00Z; null with no later season (a `load` test); null in season.
- AC-2: `slate.test.tsx` off-season cases on the required type: the line shows with the field, hidden when null.
- AC-3: the D-164 row (spec-reviewer).
- AC-4: `test_api_shell.py` next-season fields at the off-season clock and null otherwise; `shell.test.ts` label; `slate.test.tsx` caption "2027 · Week 1 · off-season".

**Risks:** no schema change (reads `seasons.weeks`). The e2e clock is in season, where the CTE gives null.

## Review log

Verify R1 PASS | Audit R1 PASS | Spec R1 CHANGES (follow-up paths, frame body names 2027) → fixed | Schema R1 APPROVE | UI not run (no off-season clock in the dev server; covered by component tests)

## Blocked

_Only if status is Blocked: what failed, what was tried, best hypothesis, decision needed._

## Metrics

- Verify rounds: 1
- Review rounds: 2
- First-pass AC FAILs: 0
- Plan revisions after approval: 0
