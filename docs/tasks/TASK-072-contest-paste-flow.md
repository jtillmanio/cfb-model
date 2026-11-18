---
id: TASK-072
title: Build the Contest paste flow
status: In progress
depends_on: [TASK-070, TASK-071, TASK-054]
size: M
model: opus
autonomy: attended
ui: true
plan_status: approved
planned_at_commit: 484101c
---

# TASK-072 — Build the Contest paste flow

## Goal

On the Contest page you paste a Splash page, see the raw text beside the parsed rows, fix unmatched names with an inline team picker, and confirm the week's slate. A paste that can't be read or matches nothing gets its own state, and a re-paste shows which lines moved.

## Context

- Task list: `docs/08-tasklist.md` › M6 › M6.6. Depends on TASK-071 as well as the task list's M6.4 and M5.3: the page's one API call is TASK-071's contest page route, which tells the page whether the week has a slate, and carries the `shell` block.
- Screen: S-02 (`docs/05-ui-design-brief.md` › Screen inventory; › Screens › 7. Contest).
- Design: `design/handoff/designs/Contest Desktop.dc.html` (`pasteError` none / unparsed / nomatch, `repaste`) and `Contest Mobile.dc.html`; boards `Contest.dc.html` and `Pass C1 - Slate Contest Game.dc.html`: C2a "paste can't be parsed", C2b "paste matches no team", C2e "re-paste moved lines" (the RepasteDiff component); skeleton in `Loading States.dc.html`; light mode in `Pass D - Light Mode.dc.html` (D02).
- Reference screenshots: `design/handoff/screenshots/03-contest-desktop.png`, `04-contest-mobile.png`.
- Product: `docs/01-product.md` › Observable outcomes › F-03 AC-1.
- Architecture: `docs/02-architecture.md` › End-to-end journeys › 3, › Test-only sign-in and clock (Thu 2026-10-08 10:00 PM ET).
- Decisions: D-058 (IBM Plex Mono for raw paste text), D-069 (Contest in the sidebar and tab bar: `web/components/shell/sidebar.tsx` and `mobile-tabs.tsx` already link it), D-070, D-096 (designed error states, no fallback data), D-155 (types from `web/lib/api-types.ts`), D-157 (each page renders `<AppShell shell={data.shell}>`).
- **Writes:** the first pages that write. The browser never calls the API (hard rule 5, `.claude/rules/web.md`). Paste, map and confirm go through Server Actions that call TASK-070's routes with the signed JWT, so `web/lib/api.ts` gains a signed POST beside `signedGet`.
- **The empty hero needs an empty week.** The fixture already holds Week 6's contest lines (TASK-067), and an alias saved in one e2e run would make the next run's paste fully matched. The plan says which contest week e2e pastes into, and how each run starts from the seeded state (e2e runs after `pnpm db:seed`).
- *From TASK-070 (PR #161):* e2e writes through the API persist in the test DB. `contest_lines` refuses DELETE, and a mapped "Hou Texans"/"Jax" alias stays, so journey 3 fails on a second run against the same DB unless the plan resets them (a re-seed doesn't remove either). Under a pinned FIXTURE_NOW a second confirm returns 409 `already_captured`. The API (D-172): `POST /contests/{id}/import/preview` and `/import/confirm` take `{text, period}` (the page prints no week, so the screen sends it); preview rows carry `status`, `unmatched[].candidates` for the inline picker (best first), `swapped` and the re-paste diff in `changes`; `POST /contests/{id}/aliases` takes `{mappings: [{alias, team_id}]}`. The web client has only `signedGet` today, so this task adds the signed POST.
- **Lighthouse:** `/contest` is a new top-level screen, so its route and budget go in `scripts/perf/routes.mjs` and `budget.json` in this PR (`web/lib/perf.test.ts` fails otherwise).

## Acceptance criteria

- [ ] AC-1: Given a contest week with no confirmed slate, `/contest` shows the "Paste from Splash" hero. Pasting the fixture Week 6 text shows the raw text (IBM Plex Mono) beside the parsed rows, with "9 rows match · 1 unmatched". The unmatched row ("Hou Texans" @ "Jax") is highlighted, and Confirm is disabled.
- [ ] AC-2: Mapping "Hou Texans" to Houston Texans and "Jax" to Jacksonville Jaguars with the inline team picker enables Confirm. Confirm saves the slate, and the page then shows the confirmed week (TASK-073 draws its ranked slate). After a reload the slate is still there, and pasting the same text again matches all 10 rows.
- [ ] AC-3: Unparseable text shows C2a's state and a paste that matches no team shows C2b's, each with a way back to edit the paste. Neither writes anything (the API's row counts are unchanged).
- [ ] AC-4: Pasting again with a moved line shows the RepasteDiff (C2e) listing each moved row with its old and new line before Confirm.
- [ ] AC-5: `/contest` has a `loading.tsx` skeleton at the loaded size, with the pulse off under reduced motion, and shows the designed error state when the API fails (D-096). At 390, 768 and 1440 px there's no horizontal scroll and every tap target is at least 44 px. Colours, type and spacing come from tokens only (`web/components/tokens-only.test.ts` passes).
- [ ] AC-6: `/contest` is in `scripts/perf/routes.mjs` with a budget, and the fixture Lighthouse run is within it. `web/e2e/contest.spec.ts` runs journey 3 (paste → "9 rows match · 1 unmatched" → map → Confirm) at phone and desktop widths.

## Out of scope

- The ranked slate, the pick tray, results and standing, and the rules panel (TASK-073).
- Manual "add game" entry.
- Contest settings (M8.8).
- The mobile versions of the bad-paste, all-locked and re-paste states (not drawn: 05 › Screen inventory lists them as missing).

## Files likely touched

- `web/app/contest/page.tsx`, `loading.tsx`, `error.tsx`: new
- `web/app/contest/paste-flow.tsx`, `team-picker.tsx`, `repaste-diff.tsx`: new client components
- `web/app/contest/actions.ts`: new Server Actions for preview, map and confirm
- `web/lib/api.ts`: the signed POST and the contest calls
- `web/lib/contest.ts`, `web/lib/contest.test.ts`: new pure helpers (match counts, Confirm enabled) and their tests
- `web/app/contest/paste-flow.test.tsx`: new component states
- `web/e2e/contest.spec.ts`: new, journey 3
- `scripts/perf/routes.mjs`, `scripts/perf/budget.json`: the route and its budget

## Verification

- Automated: `pnpm --dir web exec vitest run lib/contest.test.ts app/contest`, `pnpm --dir web exec playwright test e2e/contest.spec.ts`, and `web/lib/perf.test.ts` pass.
- Manual (ui-verifier, at 390, 768 and 1440): paste the fixture text → expected: "9 rows match · 1 unmatched" and Confirm disabled; map both names → Confirm enabled; paste "hello" → C2a's state.

## Follow-ups

_Work noticed during this task and deliberately left out. Each bullet ends `→ <path> § <section>` (where it was placed) or `→ not tracked: <reason>`. See `.claude/skills/track-follow-ups/classify.md`; the PR's Follow-ups section is copied from here._

## Plan

_Written by /plan-batch or /implement-task Phase 1. Approved by the user (plan_status: approved) before any code is written._

Approved by the owner up front in the `/next-task` request (2026-11-18: "approve plan … any questions go with recommendations"); the questions the plan gate would have asked are listed in the PR.

**Steps**

1. **The page's one API call** (`api/main.py`, `api/contest.py`). Nothing lists your contests and `user_settings` (the default contest) is M8.7, so add `GET /api/py/contest?contest_id=&period=`: the same wave as `GET /contests/{id}` (`contest.queries`), whose `mine` CTE takes the given id, else the caller's first live contest (lowest id) until M8.7; none is a 404. `ContestRulesOut` gains `sports` and `scoring` (C2b's "This contest is CFB + NFL" and the header's "Pick 4 · CFB + NFL · … · 1 pt per correct pick"). Regenerate `web/lib/api-types.ts`.
2. **e2e reset** (`engine/fixture.py`, `engine/cli.py`): `engine seed paste-journey --project <name>` (test DB only, refuses `LIVE`): soft-deletes user 4242's live "Paste journey (<name>)" contest, inserts a fresh one (Splash preset rules, platform `splash-e2e-<name>`), replaces that platform's aliases with copies of the `splash` ones except "Hou Texans" and "Jax", and prints `{"contest_id": n}`. Each test run (and retry) starts from the seeded state, and phone and desktop never share an alias row, so they run in parallel. The shared `splash` rows are never touched.
3. **`web/lib/api.ts`:** `signedPost` beside `signedGet` (returns status and body, so a 422's refusal reaches the screen; throws on a network failure or a 5xx); `getContest(contestId | null)` (null on 404); `previewContestImport`, `saveContestAliases`, `confirmContestImport`.
4. **`web/lib/contest.ts`** (pure, Vitest): the week to paste into (the shell's coming regular-season week when it's the contest's season and has no lines; else the newest week, or week 1 with none) and so hero or confirmed week; the summary ("Found 10 games", the date range, "6 CFB · 4 NFL", "9 rows match · 1 unmatched"); Confirm enabled (every row matched, or each unmatched name picked, and no problem, no-game, ambiguous or duplicate row); the raw lines (read, skipped, unmatched, selected); the C2a / C2b copy from the refusal; the RepasteDiff rows from `changes`.
5. **`/contest`:** `page.tsx` (one call, `?contest=<id>` optional; the confirmed week's toolbar "From Splash paste · <time> · N games", the game list TASK-073 replaces, and "Re-paste to update lines"; "No contest yet" when the API has none; "API unreachable" in the shell on failure); `loading.tsx` (the shell, header and slate skeleton as `Loading States.dc.html` draws it, pulse off under reduced motion); `error.tsx`; `paste-flow.tsx` (hero, paste and clipboard, the parsed view with raw text beside the rows at desktop and in a disclosure on a phone, C2a / C2b with "Clear and paste again", Confirm); `team-picker.tsx` (candidates best first, filter, Enter, Change); `repaste-diff.tsx`; `actions.ts` (`previewImport`, `confirmImport`: save the picked names as aliases, confirm, then `refresh()`). Picks stay local until Confirm, as the board's "Change" and "Remember" draw it. Every control is at least 44 px.
6. **e2e** (`playwright.config.ts`, `e2e/test-env.ts`, `e2e/contest.spec.ts`): a contest API at Thu 2026-10-08 10:00 PM ET and its own `next start`; each test runs the reset, then journey 3 (AC-1, AC-2), C2a / C2b (AC-3) and a re-paste with a moved line (AC-4), at phone and desktop.
7. **Perf:** `/contest` in `scripts/perf/routes.mjs`; its `budget.json` entry and the `docs/02` table row from the PR's first fixture Lighthouse run (budgets are never invented).
8. **Docs:** D-175 (the route, the first-contest default, the paste week, aliases saved at Confirm, the e2e reset); `docs/02` › End-to-end journeys (journey 3's reset) and the perf table.

**Files:** `python/api/src/api/main.py`, `contest.py`, `python/api/tests/test_api_contest.py`, `python/engine/src/engine/fixture.py`, `cli.py`, `python/engine/tests/test_fixture_seed.py` (not in Files likely touched: steps 1–2); `web/lib/api-types.ts` (not listed: regenerated), `web/lib/api.ts`, `web/lib/contest.ts`, `web/lib/contest.test.ts`; `web/app/contest/page.tsx`, `loading.tsx`, `error.tsx`, `paste-flow.tsx`, `team-picker.tsx`, `repaste-diff.tsx`, `actions.ts`, `paste-flow.test.tsx`; `web/e2e/contest.spec.ts`, `web/playwright.config.ts`, `web/e2e/test-env.ts` (not listed); `scripts/perf/routes.mjs`, `budget.json`; `docs/02-architecture.md`, `docs/decisions.md` (not listed).

**Test strategy**

- AC-1: `contest.test.ts` (summary, Confirm disabled, hero week); `paste-flow.test.tsx` "shows the raw text beside the rows and highlights the unmatched row"; `contest.spec.ts` "journey 3".
- AC-2: `contest.spec.ts` "journey 3" (map → Confirm → confirmed week → reload → re-paste matches 10); `paste-flow.test.tsx` "picking both names enables Confirm"; `test_api_contest.py` for the default contest.
- AC-3: `contest.spec.ts` "a bad paste shows its state and saves nothing" (C2a, C2b, Clear; after a reload the hero is still there and the good paste still reads 9 / 1); `paste-flow.test.tsx` C2a / C2b copy.
- AC-4: `contest.spec.ts` "a re-paste lists the moved line"; `repaste-diff` cases in `paste-flow.test.tsx`; `contest.test.ts` moved rows.
- AC-5: `contest.spec.ts` "no sideways scroll and 44 px targets" at 390 / 768 / 1440 (768 by resizing); a `paste-flow.test.tsx` case for the error state; `tokens-only.test.ts`; the loading skeleton checked by the ui-verifier.
- AC-6: `web/lib/perf.test.ts` (the route and budget); the fixture Lighthouse run on the PR; `contest.spec.ts` at both projects.
- Steps 1–2: `test_api_contest.py` (`GET /contest` picks the first live contest, takes `contest_id`, 404s with none, carries sports and scoring); `test_fixture_seed.py` (a reset makes a fresh contest, soft-deletes the last, copies the aliases without the two names, refuses a bad project name).

**Risks / open questions** (answered with recommendations; the owner asked for them listed at the end): no API lists contests (step 1); the board's "Skip it, confirm 9" can't work, because confirm re-reads the whole paste and refuses any unresolved row (left out); "Add game manually" is out of scope (left out); the parsed table's Market column isn't in the preview response (left out); RepasteDiff's cover % and rank columns aren't in the preview (left out; the board calls them illustrative); the 44 px targets make desktop controls taller than the board's 30–36 px.

**Size check:** about 25 files, over the project's 20. Kept whole (owner's "go with recommendations"): a split would turn steps 1–2 into a task this one depends on, and with a WIP limit of 1 it would wait for that PR's merge. Steps 1–2 are only the plumbing the screen needs.

## Review log

_Filled by /implement-task. One line per round._

## Blocked

_Only if status is Blocked: what failed, what was tried, best hypothesis, decision needed._

## Metrics

- Verify rounds:
- Review rounds:
- First-pass AC FAILs:
- Plan revisions after approval:
