# 07 — Claude Design Playbook

Step by step: how to get the design system and screens out of [Claude Design](https://claude.ai/design), and what to do with the output. The *what* lives in [05-ui-design-brief.md](05-ui-design-brief.md). This doc covers the *how*: setup, the prompts in order, review checks, and handoff to Claude Code.

**When:** in parallel with Phases 1–3 (see [06-roadmap.md](06-roadmap.md)). Implementation happens in Phase 4, except the design tokens, which can land earlier. The History screens (Prompt 10) are designed later, between Phases 5 and 6; Prompt 11 belongs to the first design pass.

---

## 0. Setup

### Two projects
1. **Design system project:** "CFB Model — Design System". This holds tokens, type, components and chart styles. Claude Design applies a design system to every project created after it, so build it first.
2. **Screens project:** "CFB Model — Screens", using the design system above. Keep all screens in this one project so it shares context (nav, components, sample data) across screens.

### Context to attach (both projects)
| File | Why |
|---|---|
| `docs/05-ui-design-brief.md` | The brief: principles, screens, components, color semantics. **Required.** |
| `docs/01-product.md` | Who it's for and what each feature does, so design choices have reasons. **Required.** |
| `design/sample-data.md` | Consistent fake numbers for every screen, plus display conventions. **Required.** |
| `docs/04-model.md` | Only for the Model Lab, Game Detail and History (10a–10c) prompts (what drivers, priors, calibration and value over expectation mean). Optional. |
| 2–4 reference screenshots | Apps whose feel you like, e.g. a trading terminal, a sports scores app, Linear or Vercel's dashboard. Say what you like about each in one line. Optional but high-leverage. |
| A real Splash paste | Copy the text of your actual Splash contest page into a `.txt` file. It makes the parser preview realistic. Attach it for Prompt 3. |

Don't attach `02`/`03` (architecture, schema). They're noise for design.

### Working habits
- **Comment on the canvas instead of re-prompting.** Inline comments on a specific element are cheaper and more precise than a new prompt. Save new prompts for new screens.
- **Wireframe first for big screens.** If Claude Design offers a wireframe/low-fi mode, use it for layout on This Week, Contest and Game Detail, approve the structure, then ask for hi-fi. Layout changes are cheap in wireframe and expensive in hi-fi.
- **Always both breakpoints:** desktop 1440 and mobile 390, both in dark mode. Check light mode once per screen, not every iteration.
- **One screen per prompt.** The prompts below are sized for that.

---

## 1. Prompts

### Order, and when to run each
| Order | Prompt | When |
|---|---|---|
| 1 | 1: Design system | First, in the design-system project |
| 2 | 2–7: This Week, Contest, Game Detail, Rankings + Outlook + Team, Picks + Performance, Model Lab | In order, in the screens project |
| 3 | 11: Market extras | After 2, 3, 4 and 6, before 8 |
| 4 | 8: States and leftovers | After 11, so skeletons match the final layouts |
| 5 | 9: Consistency audit | Last of the first design pass |
| 6 | Export, record decisions, share links (§2a, §2b) | Right after 9. The first design pass is then **done** |
| later | 10a–10c: History | After Phase 5, before Phase 6 starts. Then re-run 9 on the new frames and re-export |


Paste these in order. Text in `[brackets]` is yours to fill in or delete.

### Prompt 1: Design system (design-system project)

```
You're designing the visual system for a private college-football analytics web app. A statistical model predicts every game, compares its numbers to betting spreads, recommends picks, ranks teams, and tracks its own record honestly.

Attached:
- 05-ui-design-brief.md: the brief. Its principles, color semantics and component list are requirements.
- 01-product.md: who uses it and why.
- sample-data.md: the only numbers you may use in any specimen. Follow its "Conventions" section exactly.
[- Reference screenshots: <one line each on what I like about it>]

This session is the design system only. No full screens yet.

Deliver, each in dark (default) and light mode:

1. COLOR TOKENS as CSS variables. Use shadcn/ui's names for the base set (--background, --foreground, --card, --popover, --primary, --secondary, --muted, --accent, --destructive, --border, --input, --ring, --chart-1..5) and add semantic app tokens:
   --edge (an edge that clears the pick threshold), --pos / --neg (covered/not, rating up/down, +/- units, CLV; colorblind-safe, blue/orange family, never red/green alone), --push, --tier-a / --tier-b / --tier-c (three steps of ONE hue), --live (game in progress), --locked, --breakeven (chart reference line).
   Give OKLCH values with hex beside them. Every text/background pair must meet WCAG AA (4.5:1 body, 3:1 large text and UI). Show the contrast ratio on the swatch card.

2. TYPOGRAPHY: one UI sans with true tabular figures (consider Inter, Geist or IBM Plex Sans; pick one and give the reason in one line). Optionally a mono or tabular style for line/score displays. Define a scale for: KPI number, page title, section title, table body, table header, caption/meta. Tabular numerals everywhere numbers appear. Use a true minus sign (−).

3. SPACE & SHAPE: 4px spacing scale, radii, border weights, elevation, two table densities (compact and comfortable row heights), breakpoints 390 / 768 / 1280 / 1536.

4. NUMBER FORMAT CARD: one reference card showing every format: spread (OSU −27.5, PK), price (−110), model line, edge (+3.7 OSU), cover % (59%), win % (TEX 54%), rating (+27.4), rank move (▲3 ▼1 —), record (31-24-1), units (+4.6u), CLV (+0.9 pts), kickoff (Sat 3:30 PM ET), lock countdown (Locks in 1d 14h), live score (Q3 9:12).

5. COMPONENTS, with every variant and state (default, hover, focus, disabled, loading skeleton): everything listed under "Components to define in the design system" in the brief. Group them: Numbers & badges · Team & game · Tables & lists · Charts · Forms & controls · Navigation · Feedback states.

6. CHART STYLE: axes, gridlines, labels, tooltips; reference lines (52.4% break-even, 50% contest break-even); live series solid vs backtest series dashed; distribution curve with a shaded cover area; sparkline; waterfall/driver bars; percentile bars. Charts must work in both modes and not rely on color alone.

7. SPECIMEN: one desktop frame (1440) with 3 rows of the slate table, and one mobile frame (390) with the same 3 games as cards, built only from the components above and the sample data. This proves the system holds together.

Rules:
- No casino aesthetics: no gold, no neon, no glow, no "LOCK" hype.
- Team brand colors are accents only (logo, thin bar). Never a large background, never text on team color without a contrast check.
- Color never carries meaning alone: pair it with a sign, icon or label.
- When something is a judgment call, make it, write the reason in one line next to it, and move on. I'll comment.
```

**Review before moving on** (comment on the canvas until these all pass):
- [ ] The edge pill reads in under a second at table size, and the "clears threshold" state is obvious without color (weight, fill or icon).
- [ ] Tier A/B/C are one hue in three steps, and still distinguishable in grayscale.
- [ ] Blue/orange pos/neg pair is distinguishable under a deuteranopia simulation. Ask: *"Show the pos/neg/edge/tier tokens under deuteranopia and protanopia simulation."*
- [ ] Numbers line up in columns (tabular figures, right-aligned).
- [ ] Dark mode doesn't use pure black (#000) or pure white text, which are harsh for long reading sessions.

### Prompt 2: App shell + This Week (screens project)

```
Using our design system, design the app shell and the This Week screen (brief §1 "This Week (Slate)" and "Navigation"). Use sample-data.md §1 for every row.

Start with a wireframe for layout. After I approve it, do hi-fi.

Frames:
1. Desktop 1440, dark: full shell (primary nav for This Week, Picks, Contest, Rankings, Teams, Performance, Lab; global season/week selector; ⌘K search; sport switcher showing CFB with NFL "coming later"; settings/account) + the slate table.
2. Mobile 390, dark: same screen with games as cards. Primary nav as a bottom tab bar (This Week, Contest, Picks, Rankings, More).
3. Desktop 1440, light: same as frame 1.

The slate must show every state in sample-data.md in one view: final (no pick), live, upcoming pick, no line yet (FCS game), line moved since pick with CLV, neutral site.

Requirements:
- The eye lands on market line → model line → edge in under a second. Everything else is secondary.
- Filters (All / Picks only / FBS vs FBS / conference / ranked / day-time window) and sort (kickoff, edge, confidence). On mobile, put filters in a sheet.
- Group rows by day/time window (Fri night, Sat noon, Sat afternoon, Sat night).
- Totals are hidden by default. Show where the toggle lives.
- Note interactions in margin annotations: row click → Game Detail; hover states; sticky header.
```

**Review:**
- [ ] Squint test: blur your eyes. Do the picks and edges pop and nothing else?
- [ ] Mobile card: matchup, market, model, edge and tier visible without expanding.
- [ ] "Line moved" state explains itself without a tooltip.
- [ ] 11 rows fit on a 1440×900 screen at compact density.

### Prompt 3: Contest (pick'em)

Attach your real Splash paste as a `.txt` file first.

```
Design the Contest screen (brief §7 "Contest (Pick'em)"). Use sample-data.md §3. Attached is a real paste from my Splash contest page; design the parser preview around its actual shape.

"Now" is Thursday 10:00 PM ET: I'm making picks at my desk. Saturday mobile use is for checking results.

Frames (desktop 1440 + mobile 390 for each unless noted):
1. Empty state: no slate loaded yet. A large "Paste from Splash" area is the hero. "Add game manually" is secondary.
2. Parsed preview: matched rows with team logos, lines and kickoff times; one unmatched row highlighted with an inline fix (team autocomplete). Confirm button.
3. Ranked slate: ranked by cover % against the CONTEST line, with a clear cutoff line under #4. Each row shows sport tag, matchup, contest line vs market line (flag differences), model line, edge, cover %, lock countdown. NFL rows show a "no model yet" state, ranked on the contest-vs-market gap. One locked (greyed, unpickable) game.
4. Pick tray: "Your picks: 2 of 4". One pick matches the model, one doesn't; show both clearly. Each shows the line and time it was locked in. Desktop: persistent side panel. Mobile: a bottom sheet.
5. Results & standing: you vs model's top 4 (season and by week), league standing entered by hand.
6. Contest settings (desktop only): rules form with the "Splash" preset selected (sports, picks per week, lock rule, scoring, push rule).

Picking should take one tap/click per game, and changing a pick must be easy until that game locks.
```

**Review:**
- [ ] From the paste to 4 picks made: count the clicks. Target ≤ 8.
- [ ] Your pick vs the model's recommendation is distinguishable at a glance.
- [ ] The cutoff line is visible but doesn't imply #5 is bad (show its cover % right there).
- [ ] Locked games can't be mistaken for pickable ones.

### Prompt 4: Game Detail

Attach `04-model.md` to this prompt.

```
Design Game Detail (brief §2) for Texas vs Oklahoma, sample-data.md §2. 04-model.md is attached so you know what the drivers and distribution mean.

Frames: desktop 1440 dark, mobile 390 dark.

Order of importance:
1. "The Number" panel: market (open → current) with a sparkline, model line, edge, cover %, win %, tier, "picked at". This is above the fold on both breakpoints.
2. Prediction drivers: diverging bars or a waterfall that visibly SUMS to the model margin (+1.3 TEX). Positive = Texas, negative = Oklahoma; label the sides with team chips, not just colors.
3. Projected margin distribution: bell curve (sd 13.8) with the market line marked and the OU-cover region shaded. Caption it in plain English, e.g. "Oklahoma covers in 63% of outcomes."
4. Unit matchup: percentile bars per unit, offense vs the defense it faces.
5. Recent form vs the spread, head-to-head (placeholder rows).
6. Placeholder for a later feature: "Apply adjustment" (e.g. −4 pts, QB out) with a recomputed line. Draw it as a disabled/"coming later" state.

This page answers "why does the model like this?" for someone learning modeling. Use short plain-English captions under each chart.
```

### Prompt 5: Rankings, Season Outlook, Team page

```
Design three related screens using sample-data.md §4–6:

A. Rankings (brief §4): table with rank, Δ, team, conference, record, rating, off/def with ranks, SOS, next game with model line, rating sparkline. Week "time machine" control (any week back to 2014). Conference filter. FBS only by default. Desktop + mobile.
B. Season Outlook (brief §8): as a tab inside Rankings. Projected record, a mini win-distribution histogram per row, and odds cells with subtle fill bars. Desktop + mobile.
C. Team page for Ohio State (brief §5): header with a team color accent, rating trajectory chart (overall/off/def), schedule with market vs model vs result vs ATS, unit profile, preseason vs now, and a "Path to the playoff" module (win distribution + swing games). Desktop + mobile.

Rankings has three tabs: Power · Season Outlook · History. Draw History as a disabled "coming later" tab for now.
Keep these visually consistent with This Week. Same table component, same team chip.
```

**Already ran this prompt?** Don't redo it. Leave a canvas comment on the Rankings frame: *"Add a third tab, History, after Season Outlook, shown as disabled / coming later."*

### Prompt 6: Picks + Performance

```
Design Picks (brief §3) and Performance (brief §6) using sample-data.md §7, plus §1 for the current picks.

Honesty is the design principle here:
- Live results and backtest results must never be confusable. Backtest gets a persistent label and a distinct visual treatment (e.g. dashed series, muted tile), everywhere it appears.
- Always show break-even next to win % (52.4% for -110; 50% for the contest).
- The edge-bucket chart's dip at 7+ and the calibration chart's overconfidence at the top are real. Show them plainly with a one-line caption; don't style them away.

Picks: current picks with "picked at" vs current line and CLV, record summary strip, past weeks collapsed by week, filters.
Performance: KPI tiles (season and all-time), cumulative units chart, win % by edge bucket, calibration chart, breakdown tables (tier, week of season, conference, favorite/underdog), model version selector.

Desktop + mobile for Picks; desktop for Performance plus a mobile version of just the KPI tiles and units chart.
```

### Prompt 7: Model Lab

Attach `04-model.md` to this prompt.

```
Design the Model Lab (brief §9) using sample-data.md §8. 04-model.md is attached; the user is a developer learning statistical modeling, so every number gets a plain-English label.

Hi-fi, desktop only:
1. Weights view for v1.0: "chosen" settings and "learned" weights side by side, each with its plain-English meaning. A prior-decay curve chart (100% → 10% by week 8). An input-importance bar chart.
2. Versions list: status pills (dev / candidate / production / retired), parent, created date, headline metrics, and a prominent "Variants tried since last promotion: 7" counter (an overfitting reminder).
3. Compare v1.0 vs v1.1: metric deltas, overlaid calibration charts, record by edge bucket, games where they disagree most.

Wireframe only (built later, so just structure):
4. Model builder: a form with sections (Inputs, Hyperparameters, Home field, Prior, Distribution, Pick rules). Each weight uses a "Fit from data / Fixed: [value]" toggle field. A "Run backtest" button with a queued → running → done/failed status pill.
5. Promote: go/no-go checklist with pass/fail per gate.
```

### Prompt 8: States and leftovers

```
Fill in the remaining states, using components from the design system:
1. Loading skeletons for This Week, Contest, Game Detail, Rankings and Performance, drawn at the loaded layout's exact size (the database can take a few seconds to wake). Note "pulse off under reduced motion".
2. Empty states: off-season (no games this week), no picks this week, contest with no slate, team with no games yet.
3. Error states: API unreachable (with retry), one panel failed while the rest of the page loaded.
4. ⌘K command palette: team search with recent teams, plus jump-to-screen commands.
5. Login screen (single user, minimal) and Settings (theme, default contest, timezone).
Desktop + mobile where it applies.
```

### Prompt 9: Consistency audit (run last in the first pass; re-run after Prompt 10)

```
Audit every frame in this project against the design system and sample-data.md. List the problems first, grouped by type, then fix them:
- Any number not from sample-data.md, or one that contradicts it (edges, tiers, records, units must agree).
- Spreads or edges that break the sign convention (true minus sign, favorite's side, edge labeled with its side).
- Components that drifted from the system (one-off colors, sizes, spacing, radii).
- Non-tabular or left-aligned numbers in tables.
- Color carrying meaning alone.
- Text/background pairs below WCAG AA, in both modes.
- Mobile frames with horizontal scroll or tap targets under 44px.
```

### Prompt 10: History (seasons, programs, coaches), run in three parts

**When:** after Phase 5 is done and **before Phase 6 starts**, not with the screens above. Two things have to be settled first, because they change what you draw:
1. The Phase 6 open questions in [06-roadmap.md](06-roadmap.md): how far back history goes (this decides whether the era badge exists at all) and the default coach measure (this decides the default sort and toggle).
2. `design/sample-data.md` §9 is fictional. Once the Phase 6 data work has produced real season ratings, swap in a few real rows, so the mocks have the real shape (name lengths, how many stops a coach has, how wide the rating range is).

**Attach:** `docs/05-ui-design-brief.md`, `docs/01-product.md`, `design/sample-data.md`, `docs/04-model.md` (§7 is the point of this prompt), and the Rankings frames from Prompt 5 so the History tab inherits the same table and tabs. Work in the screens project.

**Why three parts:** the habit is one screen per prompt, and this is three screens plus extras. Run them in order: 10a gives 10b its table style, and 10b's coach page needs the era badge from 10a.

#### Prompt 10a: Season final + Programs

```
Design the History tab inside Rankings (brief §11), using sample-data.md §9. 04-model.md §7 is attached: the user is learning modeling, so every measure gets a plain-English column tooltip or caption. Reuse the Rankings table, team chip and sparkline from the existing frames.

Replace the disabled "History" tab with a live one, with three sub-tabs: Season final · Programs · Coaches (Coaches is designed in 10b; show it as a stub).

1. Season final (2019): best team (hindsight rating) and best résumé side by side, sortable by either. Make the gap visible: Alabama is 4th by rating but 9th by résumé, with the caption from sample-data.md. Columns include the season z-score, with a tooltip explaining it's for comparing across eras. Season picker.
2. Programs (2014–2025): a season-range control (two year pickers or a range slider), average/peak/worst rating, top-10 finishes, a sparkline of seasonal ratings per row. Changing the range re-ranks, so show the loading state for that re-rank.
3. Era badge component ("Efficiency" / "Scores only"), shown wherever seasons of both kinds could appear together (the Season picker, a Programs row spanning both eras). Show a Season final for 1995 using the "Scores only" variant, noting what is missing (no offense/defense split).

Desktop + mobile. On mobile the tables collapse to cards as elsewhere; keep both ranks (rating and résumé) visible on the card.
```

#### Prompt 10b: Coaches + Coach page

```
Design the Coaches sub-tab and the coach page (brief §11), using sample-data.md §9. Same table component as 10a.

1. Coaches table: value over expectation (shrunk) as the default sort, then raw and "crediting recruiting" columns. A toggle switches between "controlling for recruiting" and "crediting recruiting"; the default is [whichever you picked in the Phase 6 open questions]. Interim stints are marked (*), and stints too small to judge are flagged.
2. Make Lanning's shrinkage visible (raw +3.4 → shrunk +2.0): for example a small "raw → shrunk" mark in the cell, plus a one-line caption explaining that short careers are pulled toward zero.
3. Coach page for Kirby Smart: header, a tenure timeline across schools, a chart of preseason prior vs hindsight rating by season with the gap shaded (above the prior = beat expectation), the value-added table, ATS and one-score records with a note that close-game records are mostly luck.
4. A coach with several stops (Chris Petersen: Boise State, then Washington): show how the timeline and the table read for multiple stops.

Desktop + mobile for the table and the coach header + chart; the rest desktop only.
```

#### Prompt 10c: Extras on existing screens

```
Add History's connections to existing screens:
1. Team page (Ohio State): an "All-time" module with season-by-season final rating and rank, coaching changes marked on the timeline.
2. ⌘K command palette: coaches appear in search alongside teams, with a small type tag (Team / Coach).
3. A coach name anywhere else in the app (e.g. the team page header) links to the coach page. Show the link style.
Desktop only.
```

**After all three:** run Prompt 9's audit on the new frames, then re-export and record the decisions (§2).

**Review:**
- [ ] The difference between "best team" and "best résumé" is obvious at a glance, and the user can say which one a column is.
- [ ] Hindsight ratings can't be mistaken for the weekly predictive ratings: a persistent label, or different column naming, on every History table.
- [ ] Shrunk vs raw coach values are never shown without saying which is which.
- [ ] A 1995 (scores-only) season looks deliberately different, not broken.

### Prompt 11: Market extras (line movement, best lines, record strip, watchlist, weather)

**When:** during the design window (in parallel with Phases 1–3), after Prompts 2, 3, 4 and 6 and **before Prompts 8 and 9**. The extras change the This Week row, so the loading skeletons (Prompt 8) must be drawn against the final layout, and the consistency audit (Prompt 9) should cover everything once.

If you've already run 8 and 9, don't redo them: run this, then re-run only the skeleton for This Week and the audit on the changed frames.

**Attach:** `docs/05-ui-design-brief.md` (§1, §2, §3, §7, §12), `docs/01-product.md`, and the latest `design/sample-data.md` (§1 Opened column, record strip, starred games, weather flags and alert; §3b best lines board). Work in the screens project, since it edits existing frames.

**Build order across the roadmap:** line movement, best lines and the record strip ship in Phase 4; watchlist and alerts and weather flags ship in Phase 5. Design all of it now anyway, because it changes the This Week row layout. A row that has to take a sparkline, star and weather icon later is a redesign, not an addition.

```
Add these features to the existing frames (brief §1, §2, §3, §7, §12). Use the new sample-data.md content in §1 (Opened column, record strip, starred games, weather flags, alert) and §3b (best lines board).

1. This Week: the Market cell shows current line, opening line and a tiny movement sparkline, without stealing attention from market → model → edge. Add the "This week" record strip under the header, a star toggle per row, a "Starred" filter, and weather icons on the two flagged games (tooltip with details). Desktop + mobile card.
2. Game Detail: star toggle and a weather line in the header (forecast for Texas vs Oklahoma; show the "Dome" variant as a small extra state). The full line-movement history chart goes here too (opening → current, with snapshot times on the axis).
3. Picks: a "Best lines" tab from §3b: one row per game, source tag (Splash / Market), the other source's line for comparison, a cutoff line at the pick threshold, and source chips ("Splash + Market" selected, "Splash only" shown). Draw an extra state where cover % carries an "uncalibrated" label. Add this week's record to the record strip. Desktop + mobile.
4. Contest: "this week so far" in Results & standing (you vs model's top 4, in points, no units).
5. Alerts: a bell with an unread count in the shell, an alerts panel with the BYU alert, and alert settings in Settings (delivery: email or push; edge crosses the threshold; line moves ≥ N pts) with a note that alerts follow the line-snapshot schedule and can lag by hours. Desktop + mobile.
6. Empty and edge states for the new pieces: no starred games, no alerts, a game with no weather data, a past season's game with only an opening and closing line (so no sparkline: show it as two points, not an error).

No injury indicators: injuries are tracked by hand and entered as manual adjustments. No sportsbook comparison either. Reuse existing components where you can, and list any new ones you add to the design system.
```

**Review:**
- [ ] Squint test on This Week still passes: the sparkline, star and weather icon read as secondary.
- [ ] The best-lines source tag is impossible to miss: you can't enter a market line in Splash.
- [ ] The record strip makes "live" and "final" distinct; a live game that's not covering isn't shown as a loss.
- [ ] The alerts note ("can lag by hours") is visible where alerts are configured, not buried.
- [ ] Any new component is added to the design system project too, not just drawn on a frame.

### Reusable follow-up prompts
- *"Tighter: increase information density by ~20% without shrinking body text below [13px]."*
- *"This feels like a sportsbook. Make it calmer: more like an analytics tool."*
- *"Show this frame in light mode."*
- *"Show this at 390px with the longest team names (e.g. 'Louisiana-Monroe', 'Massachusetts')."*
- *"Annotate the interactions on this frame (click, hover, sheet open/close) as margin notes."*

---

## 2. What to do with the output

### a. Save a reference copy in the repo
For each finished project (the design system, then the screens):
1. **Export → PDF** of all frames, and **Export → standalone HTML** for the screens project. Save to `design/exports/YYYY-MM-DD-<name>.pdf|html`. These are the visual source of truth Claude Code compares against.
2. Create a **share link** (view access) and record it in [Design links](#design-links) below.
3. Commit: `design: add Claude Design exports for <name>`.

### b. Record the decisions in the docs
Add a short **"Design decisions"** section to the end of [05-ui-design-brief.md](05-ui-design-brief.md): chosen fonts, key token values (background, edge, pos/neg, tiers), nav pattern, table densities, and anything that changed from the brief (e.g. "dropped the radar chart for percentile bars"). Future Claude Code sessions read the docs, not the canvas.

### c. Hand off to Claude Code
In Claude Design: **Export → Hand off to Claude Code.** This packages the design (components, tokens actually used, layout hierarchy, assets) into a bundle Claude Code can read directly, instead of guessing from screenshots. If it gives you a file, save it under `design/handoff/<name>/` and commit it. If it gives you an instruction or link to paste, paste it into the Claude Code prompts below in place of the path.

Do the handoff **when you're about to implement**, not when the design is finished. The bundle reflects the canvas at export time.

**Timing:**
| What | When | Why |
|---|---|---|
| Tokens + core components + styleguide page | Any time after the Phase 0 `web/` scaffold exists | No API needed; unblocks everything after it |
| This Week, Game Detail, Picks, Rankings, Team, Performance, Contest | Phase 4 | Needs the generated API client and real endpoints |
| Season Outlook, Model Lab weights/versions/compare | Phase 5 | Needs the simulations and model registry |
| History tab, coach page, team "All-time" module | Phase 6 | Needs hindsight ratings and coach data |
| Model builder, Promote | Phase 7 | |

### d. Claude Code prompts

**Design system (first):**
```
Implement the design system from the Claude Design handoff at design/handoff/design-system/ [or: <pasted handoff instruction>].
Read docs/05-ui-design-brief.md (incl. "Design decisions") and docs/07-claude-design-playbook.md first; design/exports/<date>-design-system.pdf is the visual reference.
- Tokens → CSS variables in web's global stylesheet (dark default + light), wired into the Tailwind theme, keeping shadcn/ui variable names.
- Fonts via next/font; tabular-nums on all numeric UI.
- One formatting module for spreads/edges/probabilities/records/units/times that implements the number format card exactly, with unit tests for every example on the card (incl. PK, half points, true minus sign, push).
- Shared components on top of shadcn primitives: edge pill, tier badge, team chip, game row/card, result marker, rank movement, probability bar, KPI tile, data table with responsive card collapse, skeletons.
- A /dev/styleguide route (unlinked) rendering every component and state with design/sample-data.md values, in both themes.
Don't build screens yet. When done, screenshot /dev/styleguide at 1440 and 390 in both themes and list differences from the export.
```

**Each screen (Phase 4+):**
```
Implement the <Screen> screen from the Claude Design handoff at design/handoff/<screen>/ [or: <pasted instruction>], using the existing design-system components (don't add one-off styles; extend the system if something is missing and say so).
Visual reference: design/exports/<date>-screens.pdf, frames "<Screen> desktop" and "<Screen> mobile".
- Data via the generated API client, one API call per page, server components only.
- loading.tsx skeleton at the loaded layout's size.
- Empty and error states per the design.
Then take Playwright screenshots at 1440 and 390 and list remaining differences from the export.
```

### e. When the first design pass is finished: next steps
"Finished" means Prompts 1–9 and 11 are done and the audit is clean. Then, in order:
1. **Export and share** (§a): PDF of every frame, standalone HTML of the screens project, share links in [Design links](#design-links). Commit.
2. **Record the decisions** (§b): the "Design decisions" section in the brief. Include anything that diverged from the brief and any new components Prompt 11 added.
3. **Sync the docs to what you drew.** If the design added, dropped or changed a feature, update `docs/01`, the brief and `design/sample-data.md` (the design wins on look and layout; the docs win on what the model does). Per `CLAUDE.md`, fix the loser in the same PR.
4. **Hand off the design system only** (§c), once the Phase 0 `web/` scaffold exists. Do not hand off screens yet: the bundle reflects the canvas at export time and screens need the Phase 4 API.
5. **Implement the design system** in Claude Code (prompt in §d) as its own PR with its styleguide route. Review it against the export at 1440 and 390, both themes. This is the review gate for the design track.
6. **Go back to the build phases.** Design work stops until a screen is about to be implemented (Phase 4: hand off This Week, Contest, Game Detail, Picks, Rankings, Team, Performance one at a time, using the screen prompt in §d). Run `/design-sync` once the component library exists, so later designs (Outlook, Lab, History) are drawn with the real components.
7. **Later passes:** Prompt 10 (History) between Phases 5 and 6; the Model builder and Promote wireframes from Prompt 7 are only implemented in Phase 7.

### f. Keep design and code in sync
- **After implementation, code is the source of truth.** Small tweaks happen in code. Bigger changes go: design in Claude Design → hand off → implement.
- Once the component library exists in `web/`, run **`/design-sync`** in Claude Code to push the implemented components back into the Claude Design design-system project. Later designs (Season Outlook, Lab, NFL) are then drawn with the real components instead of the original mocks.
- When a screen ships, tick its box in [06-roadmap.md](06-roadmap.md) Phase 4 and update the Status line in `CLAUDE.md`.

---

## Design links
| What | Link | Last export |
|---|---|---|
| Design system project | | |
| Screens project | | |
