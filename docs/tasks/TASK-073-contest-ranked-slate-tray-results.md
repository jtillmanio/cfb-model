---
id: TASK-073
title: Build the ranked contest slate, pick tray and results
status: Review
depends_on: [TASK-071, TASK-072]
size: M
model: sonnet
autonomy: unattended
ui: true
plan_status: approved
planned_at_commit: 60a9c78
---

# TASK-073 — Build the ranked contest slate, pick tray and results

## Goal

The Contest page ranks the week's games against the contest's lines and marks the model's top 4. You add picks with one tap, see them in a tray with when each line was locked in, and follow results and your league standing against the model.

## Context

- Task list: `docs/08-tasklist.md` › M6 › M6.7.
- Screen: S-02 (`docs/05-ui-design-brief.md` › Screen inventory; › Screens › 7. Contest).
- Design: `design/handoff/designs/Contest Desktop.dc.html` (`now` thu / fri / sun) and `Contest Mobile.dc.html`; boards `Contest.dc.html` and `Pass C1 - Slate Contest Game.dc.html`: C2c and C2f "pick failed to save" (desktop, mobile), C2d "every game locked"; light mode in `Pass D - Light Mode.dc.html` (D02); data shape in `contest-data.js` (`rank`, `tray`).
- Reference screenshots: `design/handoff/screenshots/03-contest-desktop.png`, `04-contest-mobile.png`.
- Product: `docs/01-product.md` › Observable outcomes › F-03 AC-2 and AC-3, F-04 AC-1 to AC-3, F-32 AC-3, F-33 AC-1 and AC-2.
- Architecture: `docs/02-architecture.md` › End-to-end journeys › 4, › Test-only sign-in and clock (Thu 10:00 PM and Fri 8:12 PM ET).
- Decisions: D-068 (every number through `web/lib/format.ts`), D-070 (users "add" picks; no "Lock" verbs), D-095 (all locked only after the last kickoff), D-096, D-157.
- **Pattern to copy:** TASK-072's page, Server Actions and signed POST (`web/app/contest/`, `web/lib/api.ts`). This Week's slate, filters and record strip (`web/app/(this-week)/slate.tsx`, `slate-filters.tsx`, `record-strip.tsx`). Shared components `web/components/team-chip.tsx`, `market-cell.tsx`, `edge-pill.tsx`, `tier-badge.tsx`, `result-marker.tsx`, `filter-chips.tsx`, `data-table.tsx`.
- **Numbers come from the response.** The screen prints TASK-071's cover %, gap and market-implied %, and counts the ≠ rows from its flag. F-04 AC-3's "Line ≠ market 7" is sample data; the fixture's lines give 8.
- **Clipboard:** "Copy picks to enter on Splash" writes plain text. No board draws the format (only the button), so the owner chose it at the plan gate: a header line `Splash work league · Week 6`, then one line per pick, `OU +7 (Texas vs Oklahoma, Sat 7:30 PM)` (`@` unless the game is at a neutral site, as Texas–Oklahoma is).
- *From TASK-069 (PR #157):* NFL teams from nflverse publish with no color (only the 8 fixture NFL teams carry `contest-data.js`'s colors), so a real NFL chip needs a fallback color or nflverse's team file (D-169).
- *From TASK-071 (PR #168):* `GET /contests/{id}` (`ContestPageOut`) serves the screen: each game's `rank`, `top_n`, `next_best`, `locked`, `differs`, `no_model`, `model` (CFB edge, side, cover) or `market_gap` (NFL points, side, `implied_prob`), your `entries`, `results` (season, weeks, this week, you and the model) and `standing`. Entries are `POST /contests/{id}/entries` (409 `locked` or `full`) and `DELETE /contests/{id}/entries/{game_id}`, and a standing is `POST /contests/{id}/standings`. Once a game has kicked off, `top_n` is the model's best among the **open** games (D-095), which can differ from the top 4 `results` grades (fixed at the week's first kickoff, D-171), so label it as the model's picks among open games, not the graded set (D-174).
- *From TASK-072 (PR #169):* the page's one call is now `GET /api/py/contest` (D-175): `GET /contests/{id}`'s page for `?contest=<id>`, else your first live contest, and `contest.rules` carries `sports` and `scoring`. `web/app/contest/page.tsx` draws the confirmed week as `<PasteFlow>`'s children, under its toolbar ("From Splash paste · Thu 9:10 PM · 10 games" and "Re-paste to update lines", or "Week 6 closed · results after the last game" once every game is locked): replace its placeholder `WeekGames` list with the ranked slate. `loading.tsx` already draws ten slate rows at 64 px (Loading States). Journey 4 runs on the default contest (the Splash work league), on the contest servers in `playwright.config.ts` (Thu 10:00 PM ET), beside journey 3's `engine seed paste-journey` contests, which are later and so never the default.

## Acceptance criteria

- [x] AC-1: At Thu 2026-10-08 10:00 PM ET on the seeded DB, the slate lists the week's games in the response's order with the "MODEL'S TOP 4" cutoff under row 4 and, beside it, "Next best #5" with that row's line and cover %. NFL rows read "No model yet", the gap as "<n> pts off mkt → <team>" and "~<n>% mkt-implied", each from the response.
- [x] AC-2: A row whose contest line differs from the market shows the market line under the contest line with a ≠ chip naming the difference and the side. The chip is blue (token) when the difference is better for the ranked side and orange (token) when it's worse. The "Line ≠ market" chip shows the count of flagged rows and filters to exactly those rows.
- [x] AC-3: One tap on a side adds a pick, a second tap on the same side removes it, and a tap on the other side switches it. No control or copy says "Lock". The tray reads "Your picks 2 of 4", with "Locked in at OU +7 · Thu 9:14 PM" and "BUF −3 · Thu 9:20 PM". "Use the model's top 4" fills the open slots from the top 4. "Copy picks" puts the picks on the clipboard.
- [x] AC-4: When a save fails, the tray keeps the picks it had and shows C2c's state (C2f on a phone). At Fri 2026-10-09 8:12 PM ET, UNLV @ Boise State is greyed with "Picks closed" and its side buttons are disabled. When the response marks every game locked, the page shows C2d's state (a component test).
- [x] AC-5: Results & standing shows "You 12-8", "Model top 4 11-9", "3rd of 14" and the W1–W5 rows, with this week at "0 pts" for both at Thu 10:00 PM. Edit standing saves a new standing that is still there after a reload. The rules panel (desktop only) lists the contest's rules.
- [ ] AC-6: At 390, 768 and 1440 px there's no horizontal scroll and every tap target is at least 44 px, with the phone's tray as drawn in `Contest Mobile.dc.html`. Colours, type and spacing come from tokens only (`web/components/tokens-only.test.ts` passes), and the fixture Lighthouse run for `/contest` is within budget. `web/e2e/contest.spec.ts` runs journey 4 (pick OU +7 and BUF −3 → "2 of 4"; at Fri 8:12 PM UNLV @ Boise State shows "Picks closed" and the API refuses an entry) at phone and desktop widths.

## Out of scope

- The paste flow and its states (TASK-072).
- Best lines on Picks and This Week (M7.3).
- Contest settings and the rules form (M8.8), and confidence-points contests.
- Live game clocks on contest rows (TASK-074 stores them; showing them is follow-up work).

## Files likely touched

- `web/app/contest/page.tsx`: the confirmed-week layout
- `web/app/contest/ranked-slate.tsx`, `pick-tray.tsx`, `results-standing.tsx`, `rules-panel.tsx`: new
- `web/app/contest/actions.ts`: add, switch and remove entry; save standing
- `web/lib/contest.ts`, `web/lib/contest.test.ts`: tray logic (tap, re-tap, switch, fill from top 4), the ≠ count, copy text
- `web/app/contest/ranked-slate.test.tsx`, `pick-tray.test.tsx`: new component states
- `web/e2e/contest.spec.ts`: journey 4
- `scripts/perf/budget.json`: only if the slate's bytes need the budget raised (say why in the PR)

## Verification

- Automated: `pnpm --dir web exec vitest run lib/contest.test.ts app/contest` and `pnpm --dir web exec playwright test e2e/contest.spec.ts` pass.
- Manual (ui-verifier, at 390, 768 and 1440 against `03-contest-desktop.png` and `04-contest-mobile.png`): at Thu 10:00 PM, tap OU +7 → expected: the tray reads "Your picks … of 4" and shows the line it was locked in at; at Fri 8:12 PM → expected: UNLV @ Boise State reads "Picks closed".

## Follow-ups

_Work noticed during this task and deliberately left out. Each bullet ends `→ <path> § <section>` (where it was placed) or `→ not tracked: <reason>`. See `.claude/skills/track-follow-ups/classify.md`; the PR's Follow-ups section is copied from here._

- The Context's clipboard line said the copy format "is drawn on the board"; no board draws it, so the line now records the owner's format (plan gate) → docs/tasks/TASK-073-contest-ranked-slate-tray-results.md § Context (fixed in this PR) (approved at plan)
- Candidate decision: the per-project `engine seed pick-journey` contest for journey 4, the second (Fri 8:12 PM) e2e server pair, and optimistic picks that roll back on a failed save (C2c/C2f) → docs/decisions.md § D-176 (approved at plan)
- Candidate decision: a page refreshed by a Server Action waits for its call instead of drawing the wake skeleton (found when the contest call, about 1.4 s, outran the 1.5 s race and swapped the tray for the skeleton) → docs/decisions.md § D-177
- The slate has no "Locks in" countdown, tier badge or "under 2.5" caption: `ContestPageOut` carries no clock, tier or pick threshold. Also: why the page's call takes about 1.4 s on the test DB and one call at a time → docs/tasks/TASK-081-contest-slate-clock-tier-threshold.md (new, Draft); docs/08-tasklist.md § M6.13
- Reading one contest's results or record reads every `contest_lines` row once the table has about 900 rows (3 pytest EXPLAIN tests fail on a local test DB that e2e has written to; base code too), and journey 4's seeds add to that pile: the note names the join to fix in `contest_results` and `contest_record` → docs/tasks/TASK-080-contest-views-filter-lines-by-contest.md § Context
- "This week so far" lists the model's top 4 but reads "0-0 · 0 pending" for a week with no model contest picks, until picks are written on confirm → docs/tasks/TASK-078-write-model-contest-picks-on-confirm.md § Context
- The board's compact 32px side buttons, 64px rows and tab bar beside the paste toolbar are not drawn as the board has them: AC-6 needs 44px targets (rows are about 110px at 1440) and the tab bar sits under the paste toolbar → not tracked: AC-6 rules out the board's sizes; shown in the PR for the owner's call
- The desktop sidebar's nav links are 34px tall (199×34), under AC-6's 44px, but they are the shell's, outside the contest page → not tracked: shared shell chrome; e2e measures `main` only
- C2c versus C2f (the failed-save wording on desktop and phone) is asserted together in jsdom, which can't tell the widths apart → not tracked: the ui-verifier saw only the "Saving…" and error-page states in the browser; the owner checks a failed save by hand (see the PR's manual steps)

## Plan

_Approved by the owner on 2026-11-20 (planned on Opus; implement on the task's model, sonnet)._

**Owner's answers at the plan gate**
1. Clipboard format: `Splash work league · Week 6` (the contest's name and the week), then one line per pick in tray order: `<side line> (<away school> <@|vs> <home school>, <kickoff>)`, e.g. `OU +7 (Texas @ Oklahoma, Sat 7:30 PM)`. Numbers through `format.ts`; kickoffs in `CONTEST_ZONE`.
2. Rules panel: the board's Rules tab (`Contest Desktop.dc.html` `frame="settings"`) drawn **read-only**: contest name, sports, picks per week, lock rule, scoring and push rule as text rows from `contest.rules`, plus the "This week, in plain English" summary card. No preset picker, no steppers or radios, no Cancel/Save (the form is M8.8). Desktop only (hidden below `lg`).
3. Cutoff label (D-174): "Model's top 4" while every game is open; "Model's top 4 · open games" once any game in the week has kicked off (`top_n` is then the best among the open games, not the graded set).

**Steps**
1. `web/lib/contest.ts` pure helpers, each tested in `web/lib/contest.test.ts`: slate rows and the cutoff (rows in the response's order; cutoff after the last `top_n` open row; "Next best #5" from the `next_best` row: its side line and cover %); each side's label (`OU +7`) via `formatLineNumber`; the ≠ chip (text = the side the contest line favors vs market and the point difference; tone `better` (blue token) when that side is the ranked side (`model.side`, else `market_gap.side`), `worse` (orange token) otherwise); the "Line ≠ market" count and filter from `differs`; the NFL text ("<n> pts off mkt → <team>", "~<n>% mkt-implied" from `market_gap`); tray logic (`tap(entries, game, side)` → add / remove (same side) / switch (other side) / refused when full (`rules.picks_per_period`)); `fillFromModel` (the open `top_n` games you haven't picked, on the model's side, up to the open slots); the copy text (answer 1); results rows (season, week rows W1…, this week's points) and the standing text ("3rd of 14", "1 pt behind 1st").
2. `web/lib/api.ts`: `addContestEntry` (POST `contests/{id}/entries`), `removeContestEntry` (a new `signedDelete`, DELETE `contests/{id}/entries/{game_id}`, 204), `addContestStanding` (POST `contests/{id}/standings`). `web/app/contest/actions.ts`: Server Actions `addEntry`, `removeEntry`, `saveStanding`; each validates its arguments (safe positive ints, side in home/away, standing ints ≥ 1, position ≤ field size), returns `{kind: "saved"} | {kind: "refused", code, message} | {kind: "failed", message}` (409 `locked`/`full` → refused), and calls `refresh()` after a write succeeds.
3. `web/app/contest/ranked-slate.tsx` (client): the board's table at desktop (#, Matchup, Contest · market, Model, Edge, Cover %, Locks in, Pick) and the mobile board's cards: rank badge (filled for `top_n` open rows, plain number otherwise, lock icon when locked), sport tag, `TeamChip`s, neutral "N", contest line over "mkt <n>" with the ≠ chip, model line or "No model yet", `EdgePill` + `TierBadge` (or "under 2.5", or the NFL gap text), cover % bar and sub-line, countdown + kickoff (or "Locked"), two side buttons (selected / model-dot / idle / full / locked states as `contest-data.js` `btnStyle`); a locked row is greyed with "Picks closed" (or "Your pick · <line>") and no enabled buttons; cutoff row and the "Locked" header row; filter chips All / CFB / NFL / "Line ≠ market" (`FilterChips`), "Ranked by cover % against the contest line", the legend. No "Lock" verbs (D-070).
4. `web/app/contest/pick-tray.tsx` (client, owns the picks state with `useOptimistic` over the response's `entries`): "Your picks n of 4" with the 4 segments and "<k> of <n> match the model · tap a side in the slate to add"; one card per entry (side line, model badge "Model #r" / "Against model" / "Your call", matchup · kickoff, "Locked in at <line> · <created_at>", the why line, Switch to <other> / Remove, or "Locked at kickoff · pick is final"); "Use the model's top 4" / "Fill N open slots with model's picks"; open slots with the model's next pick and Add; "Picks save the moment you tap…" and "Copy picks to enter on Splash" (`navigator.clipboard.writeText`). A failed save rolls the picks back to what they were and shows C2c (desktop toast with Retry) / C2f (phone); a refusal shows its message. All locked (every game `locked`) shows C2d. Layout: the 320 px side panel at ≥ `lg`; below `lg` the phone's bottom tray bar opening a sheet, as `Contest Mobile.dc.html`. The slate and the tray share the state through one client parent (`ContestPicks`) so a tap in the slate shows in the tray at once.
5. `web/app/contest/results-standing.tsx`: season cards ("You · season 12-8", "Model's top 4 · season 11-9", "You vs model"), league standing ("3rd of 14", "1 pt behind 1st", ENTERED BY HAND, Edit → Place / Of / Pts back → Save through `saveStanding`, which appends; the page reloads with the new one); "This week so far" (you and model's top 4, points, pending counts, both lists); week by week (cumulative chart as the board's SVG with tokens only, the W1… rows and Total). `web/app/contest/rules-panel.tsx`: answer 2.
6. `web/app/contest/page.tsx`: the board's tab bar (This week's picks · Results & standing · Rules; Rules hidden below `lg`), the header's season chip (Season 12-8 · 11-9 · 3rd, linking to Results), and `<ContestPicks>` replacing the `WeekGames` placeholder inside `<PasteFlow>`. `loading.tsx` only if the loaded layout's size moves (tray panel at ≥ `lg`).
7. E2E (journey 4) in `web/e2e/contest.spec.ts`:
   - `engine seed pick-journey --project <name>` (`python/engine/src/engine/fixture.py`, `cli.py`): soft-deletes the fixture user's live "Pick journey (<project>)" contest and inserts a fresh one with the work league's rules, season and Week 6 `contest_lines` copied (same games, spreads and captured_at), no entries; prints `{"contest_id": n}`. Test in `python/engine/tests/test_fixture_seed.py`.
   - Thu 10:00 PM (the existing contest servers): on the fresh contest, tap OU +7 and BUF −3 → "Your picks 2 of 4"; on the default contest (read only) the tray reads "Locked in at OU +7 · Thu 9:14 PM" and "BUF −3 · Thu 9:20 PM"; Results shows "You 12-8", "Model top 4 11-9", "3rd of 14"; Edit standing saves on the fresh contest and survives a reload.
   - Fri 8:12 PM: a second API + web server pair in `web/playwright.config.ts` (`FIXTURE_NOW=2026-10-09T20:12:00-04:00`) with its URLs in `web/e2e/test-env.ts`; on the default contest UNLV @ Boise State shows "Picks closed" with its side buttons disabled, and a signed POST of an entry for it is refused (409 `locked`); a refusal writes nothing.
   - Runs in both Playwright projects (phone 390, desktop 1440).

**Files**: in "Files likely touched": `web/app/contest/page.tsx`, `ranked-slate.tsx`, `pick-tray.tsx`, `results-standing.tsx`, `rules-panel.tsx`, `actions.ts`, `web/lib/contest.ts`, `web/lib/contest.test.ts`, `web/app/contest/ranked-slate.test.tsx`, `pick-tray.test.tsx`, `web/e2e/contest.spec.ts`, `scripts/perf/budget.json` (only if needed, with the reason in the PR). **Not listed (flagged):** `web/app/contest/results-standing.test.tsx` (AC-5's component test), `web/lib/api.ts` (entry/standing calls, `signedDelete`), `web/playwright.config.ts` and `web/e2e/test-env.ts` (the Fri servers), `python/engine/src/engine/fixture.py`, `python/engine/src/engine/cli.py`, `python/engine/tests/test_fixture_seed.py` (the pick-journey seed), `web/app/contest/loading.tsx` (only if the layout's size moves). About 19 files; no schema change.

**Test strategy**
- AC-1: `contest.test.ts` › slate rows, cutoff, next best, NFL text; `ranked-slate.test.tsx` › renders in response order with the cutoff under row 4 and "Next best #5"; e2e Thu.
- AC-2: `contest.test.ts` › ≠ chip text and tone, ≠ count; `ranked-slate.test.tsx` › market line + chip (token class per tone), "Line ≠ market 8" filters to exactly the flagged rows.
- AC-3: `contest.test.ts` › tap add / re-tap remove / switch / full, fill from top 4, copy text; `pick-tray.test.tsx` › "Your picks 2 of 4", "Locked in at OU +7 · Thu 9:14 PM", fill, copy writes the clipboard, no "Lock" text in controls; e2e Thu.
- AC-4: `pick-tray.test.tsx` › a failed save keeps the prior picks and shows C2c (C2f at phone), all locked → C2d; e2e Fri › "Picks closed", disabled buttons, refused entry.
- AC-5: `results-standing.test.tsx` › season, standing, W1–W5, this week 0 pts, Edit → save; `rules-panel` render test in the same file; e2e › standing survives a reload.
- AC-6: e2e at both widths (no horizontal scroll, tap targets ≥ 44 px); `web/components/tokens-only.test.ts`; ui-verifier at 390 / 768 / 1440 against `03-contest-desktop.png` and `04-contest-mobile.png`; the CI fixture Lighthouse run for `/contest`.

**Risks**
- Shared test DB: only the fresh pick-journey contest is written; the default contest is read only (the Fri entry is refused, so it writes nothing).
- The extra server pair adds e2e start-up time; it reuses the one build.
- Bundle size: the slate and tray are client components; if `/contest`'s JS passes its budget, raise it from a real fixture run with the reason in the PR.

**Plan revisions after approval** (all small, inside the task's scope; written at close-out, so the plan gate didn't see them)
1. `web/lib/format.ts` (and `format.test.ts`): `formatPoints` and `formatOrdinal`, so "0 pts", "2.5 pts" and "3rd" go through `format.ts` (D-068); there was no existing formatter for contest points or places.
2. No "Locks in" countdown, no tier badge and no "under 2.5" caption (step 3 listed them): the response has no clock, tier or pick threshold, and a countdown from the browser's clock would be wrong under the fixture clock. The Kickoff column shows the time. → TASK-081.
3. `web/app/contest/contest-tabs.tsx` (new): the tab bar, the season chip and the three panels need client tab state. The bar sits under the paste toolbar, not beside it, because the toolbar is `PasteFlow`'s.
4. `addEntries` (one Server Action for "Use the model's top 4", one refresh), `web/app/contest/actions.test.ts` (new) and `web/lib/contest-fixture.ts` (new test data): the fill as three actions meant three page refreshes, and the contest call takes about 1.4 s.
5. `web/app/contest/page.tsx` skips the 1.5 s wake race when the request carries `next-action` (a Server Action's refresh), with a test in `paste-flow.test.tsx` → D-177. Without it a save swapped the tray for the skeleton. `loading.tsx` is redrawn at the loaded size (the plan said "only if the layout moves"; it moved).
6. From the ui-verifier: the table starts at 1440 and a row is a card below it (it was 768, where the columns clipped names); the phone tray bar is compact and flush at the bottom from 768; a pick still being saved reads "Saving …"; a Server Action call that never reaches the server shows the failed-save state; the tray carries `data-saving` while a save is in flight (e2e waits for it).
7. `web/e2e/contest.spec.ts`: one pick-journey contest per project per run for the read-only tests and a second (`<project>own`) for the test that adds picks, so a run adds fewer `contest_lines` to the shared test DB; the spec's `expect` timeout is 30 s because the contest call is slow and serialised when the whole suite runs.

## Review log

Verify R1 FAIL(`api-types.test.ts` WeekRow copy; 3 e2e timeouts under full-suite load; pytest not reached) → R2 FAIL(3 pytest EXPLAIN tests on the shared test DB, whose `contest_lines` grew to ~935 rows; the diff touches no view or API code; CI starts from a fresh DB; vitest 605/605, dispatcher 17/17, typecheck, lint, db:check, build and e2e 108/108 PASS) | Audit R1 PASS | Spec R1 CHANGES (loading.tsx, plan revisions, rules heading) → fixed; follow-ups check at close-out | Schema R1 APPROVE | UI R1 CHANGES (Edge pill sign, 768 and 1440 layout, tray bar) → R2 CHANGES (matchup width at 1440, a rejected call reached the error page, Edge pill padding) → fixed; not re-verified by the ui-verifier (round limit) | AC-6 left unticked: its fixture Lighthouse budget for `/contest` can only be checked in CI (its e2e and token checks pass)

## Blocked

_Only if status is Blocked: what failed, what was tried, best hypothesis, decision needed._

## Metrics

- Verify rounds: 2 (the pytest EXPLAIN tests still fail locally on the accumulated test DB; see the review log)
- Review rounds: spec 1 (plus the close-out check), schema 1, UI 2
- First-pass AC FAILs: 0 (the ui-verifier found one data bug, the Edge pill's side on away picks, and layout drift; every AC passed in both rounds)
- Plan revisions after approval: 7 (listed under Plan)
