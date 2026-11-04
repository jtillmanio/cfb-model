---
id: TASK-053
title: Carry the app shell's data in each screen endpoint
status: Ready
depends_on: [TASK-052]
size: M
model: opus
autonomy: attended
ui: false
plan_status: none
planned_at_commit:
---

# TASK-053 — Carry the app shell's data in each screen endpoint

## Goal

Every screen's single API response also carries what the app shell around it shows (the current season and week, the model's live track record for the sidebar card, when lines were last updated and whether they're stale, and the week's pick count), so the shell never needs a second API call.

## Context

- Task list: `docs/08-tasklist.md` › M5 › M5.3 (API half). M5.3 is split by layer (`workflow.splitPolicy: split`, over 20 files as one task): this task settles M5.3's "decide at the plan gate how shell data rides in each page's one API call" on the API side; TASK-054 builds the shell UI. M5's riskiest item ("getting the app shell's data … into each page's single API call").
- Architecture: `docs/02-architecture.md` › Components › 2 (one endpoint per screen, queries concurrent within a fixed budget), › Non-functional requirements (query budget ≤ 6 in one wave; data freshness: "Every data page shows its 'Updated' time, and a stale-data banner appears when lines are more than 24 h old"), › Testing strategy (Integration: API, query count within budget; Test-only sign-in and clock: the four fixture times).
- Data model: `docs/03-data-model.md` › Views (`model_record`, `current_picks`), › Games & market (`line_snapshots`: each `lines` pull inserts a row per book at the pull's `captured_at`, `engine/publish/lines.py`, so the newest `captured_at` is the newest pull), › Reference (`seasons.weeks`, the CFBD calendar).
- Design: `design/README.md` § Navigation (sidebar track-record card "Model · 2026 live · 31-24-1 56.4% · +4.6u · CLV +0.9 · Track record ›"; top bar "2026 · Week 6", "Updated Thu 9:02 PM ET"; Picks nav count badge); `App States Desktop.dc.html` (`frame="offseason"`: card "Model · 2026 final").
- Decisions: D-010, D-092, D-096 (stale banner means only "lines more than 24 h old"), D-142 (`model_record`: the season KPIs are the newest week's `to_date` row; `win_pct` 0–100), D-144 (v1.0 is paper-traded as `candidate`, not `production`), D-147 (one `production` version per market drives the default picks), D-149/D-150 (the coming week: the week of the earliest kickoff still to come, ties to the regular season).
- **Which version the shell (and `/slate`, TASK-055) shows, decided here at the plan gate.** The fixture's v1.0 is `production` (02 › Seed data); production's v1.0 is `candidate` (D-144), so "the production version" alone would show no model on the real app. Proposed: the (cfb, spread) `production` version if one exists, else the newest non-`retired` `candidate` with a succeeded `scheduled` run this season. Record it in `docs/decisions.md`; M23's model switcher replaces it later (D-147).
- **The stale rule against the fixture clock, decided here.** The fixture's newest pull is Thu 9:02 PM ET and the slate's clock is Sat 2:15 PM ET (41 h), so a 24 h rule marks the default fixture state stale, while `01-this-week-desktop.png` shows "Updated Thu 9:02 PM ET" and no banner. Options: keep 24 h and accept the banner in the default fixture state; add a Saturday-morning pull to the fixture (the "Updated" text then changes); or measure staleness against the `lines` schedule. 02 › Non-functional is the rule; a change to it needs the owner.
- **Clock:** the API has none yet. 02 says the engine and the web app each read "now" from one clock that honours `FIXTURE_NOW` only when `APP_ENV=test`; `engine/clock.py` isn't in the light core the API may import (hard rule 5, `.claude/rules/python.md`). The plan picks between moving it into `engine.core` and an API clock with the same rule. e2e's API server then gets `FIXTURE_NOW` = Sat 2026-10-10 2:15 PM ET in `web/playwright.config.ts`.
- **The card's record is the season to date, which on the fixture includes week 6.** `01-this-week-desktop.png`'s card reads 31-24-1 (weeks 1–5, sample-data § 7) while its record strip reads "This week 1-0"; the fixture's newest `to_date` row is 32-24-1 (Tulane @ Memphis, a week-6 win, `python/db/tests/test_model_record.py`). D-142 makes the newest week's `to_date` row the season, so the card follows the view, not the screenshot ("Counts and numbers come from code or data, never from prose").
- `/api/py/teams` is the only screen endpoint today, so it carries the shell block first; every later screen endpoint reuses the same helper.
- *From TASK-052 (PR #134):* the web types in `web/lib/api-types.ts` are generated from the API's response models (D-155). Adding the `shell` block to `/teams`'s response model in `python/api/src/api/main.py` makes `pnpm test` fail until you run `pnpm api:types` and commit the file; type the screen's data from `components["schemas"][...]` in `web/lib/api-types.ts`, and don't hand-write a response type in `web/lib/`.

## Acceptance criteria

- [ ] AC-1: Given the seeded test DB and the clock at Sat 2026-10-10 2:15 PM ET, `GET /api/py/teams` returns a `shell` block with season 2026, season type `regular`, week 6, the shown version's name and version (`v1.0`), a record equal to `model_record`'s `to_date` row for v1.0's newest 2026 week (W-L-P, win %, units, average CLV; on the fixture that's week 6, 32-24-1), record label `live`, lines updated at Thu 2026-10-08 9:02 PM ET (as UTC), the stale flag the plan gate's rule gives, and 9 picks for the week.
- [ ] AC-2: Given a DB whose only (cfb, spread) version is a `candidate` with a succeeded `scheduled` run this season, the shell shows that version; given a `production` version too, it shows the `production` one; given none, the record fields are null and the response is still 200 (pytest on rows the test inserts, rolled back).
- [ ] AC-3: Given the newest line pull 23 h before the clock, `stale` is false; given 25 h, it is true (pytest with its own snapshot times; the boundary follows the rule the plan gate keeps).
- [ ] AC-4: Given the clock at Mon 2027-02-08 6:00 AM ET (no game still to come in a stored season), the shell names the last season with games (2026), record label `final`, and no current week; the response is 200.
- [ ] AC-5: `GET /api/py/teams` runs at most 6 queries, all in one concurrent wave (a test counts them); the route still rejects a missing or bad JWT (`test_api_auth.py` covers the new field's route unchanged).
- [ ] AC-6: The generated TypeScript types include the `shell` block (TASK-052's drift check passes), and `FIXTURE_NOW` set without `APP_ENV=test` is ignored by the API clock (a test).

## Out of scope

- Drawing the shell (sidebar, top bar, tabs, banners, error and wake states): TASK-054.
- The `/slate` endpoint (TASK-055); it reuses this block.
- The "uncalibrated" label and calibration status (M7.3).
- A model-version switcher or showing several versions (M23, D-147).
- Changing the 24 h stale rule in `docs/02-architecture.md` without the owner's approval.

## Files likely touched

- `python/api/src/api/main.py` — the `shell` block on `/teams`
- `python/api/src/api/shell.py` — new: the shell queries, the version rule, the coming week
- `python/api/src/api/clock.py` or `python/engine/src/engine/core/clock.py` — the API's "now"
- `python/api/tests/test_api_shell.py` — new: AC-1 to AC-6
- `web/lib/api-types.ts` — regenerated
- `web/playwright.config.ts` — `FIXTURE_NOW` on e2e's API server
- `docs/decisions.md` — the version rule and the stale rule as applied
- `docs/02-architecture.md` › Components › 2 — the shell block every screen endpoint carries

## Verification

- Automated: `uv --directory python run pytest api/tests/test_api_shell.py` passes; the drift check passes; `pnpm test:e2e` still passes with the clock set.
- Manual: `pnpm dev`, signed in, read `/api/py/teams` through the page's server log or a test client → expected: the shell block shows the dev DB's current week and v1.0's live record.

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
