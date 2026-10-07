# 05 — UI Design Brief (for Claude Design)

> **How to use this doc:** attach it to Claude Design along with `01-product.md` and `design/sample-data.md`, then follow the prompts in [07-claude-design-playbook.md](07-claude-design-playbook.md), which also covers what to do with the output. When designs are done, hand off to Claude Code to implement in `web/` (Next.js + Tailwind + shadcn/ui).

---

## Design source

**`design/handoff/` is the source of truth for UI; where it disagrees with this brief, the design wins unless noted.** Noted exceptions: what the model computes and how numbers are defined stay with [04-model.md](04-model.md) and `CLAUDE.md` (the design wins on look and layout; see [07 §2e](07-claude-design-playbook.md#e-when-the-first-design-pass-is-finished-next-steps)), plus the [open items](#open-items-found-in-the-handoff) under Design decisions.

- **Project:** [CFB Model on Claude Design](https://claude.ai/design/p/2730c87c-4f7e-4cbe-87f7-a41113416ce8). Needs the owner's login; Claude Code works from the handoff, not the canvas.
- **Example screen:** [This Week Mobile](https://claude.ai/design/p/2730c87c-4f7e-4cbe-87f7-a41113416ce8?file=This+Week+Mobile.dc.html)
- **Handoff bundle (2026-10-06):** exported with the [07 §2c](07-claude-design-playbook.md#c-hand-off-to-claude-code) handoff, replacing the PDF/HTML export. Read `design/README.md` first: it is the bundle's README (tokens, components, per-screen specs, file map).

| Folder | What's in it |
|---|---|
| `design/handoff/designs/` | HTML design files. **Boards** (`This Week.dc.html`, `Contest.dc.html`, …, `CFB Design System.dc.html`) lay out every state with numbered notes (1a, 1b…); the notes are the spec. **Screen files** (`* Desktop.dc.html`, `* Mobile.dc.html`) take their states as props. `*-data.js` holds sample data (fixture seeds); `support.js` is only needed to view the mocks. View through a local static server (`npx serve design/handoff/designs`), boards rather than single screens. References, not code to port. |
| `design/handoff/screenshots/` | 2x PNGs of each screen's default state, dark mode, `01-this-week-desktop` … `21-offseason-empty-mobile`. Mobile shots are full scroll length. Other states live only in the boards. |
| `design/handoff/tokens/` | `tokens.css`: drop-in CSS variables (dark default on `:root`/`.dark`, `.light`), oklch with hex comments. `tokens.json`: the same tokens with notes and WCAG contrast checks. |

`.gitattributes` marks `design/**` as `-text` so Git stores these files byte-for-byte (no line-ending conversion). Don't edit, reformat or move anything under `design/`; to update, re-export and replace the bundle.

---

## Brief

**Product:** A private college football analytics app. A statistical model predicts every game, compares its numbers to sportsbook point spreads, recommends picks where it disagrees with the market, ranks all teams, and honestly tracks its own performance. One user for now: a software developer who plays a weekly against-the-spread pick'em contest in a work league. They research on weekday evenings at a desk, make picks late in the week (Thursday/Friday), and follow results on a phone on Saturdays. They're also learning statistical modeling and want to look inside the model: its weights, and building their own variants.

**Feel:** a sharp, trustworthy analytics tool, like a cross between a trading terminal and a modern sports site. Data-dense but scannable. Confident, not flashy. No casino aesthetics: no gold, no neon, no flashing "LOCK OF THE WEEK." Numbers are the hero.

**Design principles**
1. **Edge first.** On any game, the eye should land on *model line vs market line* and the *edge* in under a second.
2. **Honest by design.** The model's track record is always one click away and never hidden. Show uncertainty (probabilities, confidence tiers), not certainty.
3. **Dense but calm.** Tables are the primary pattern. Use tabular/monospaced numerals, restrained color, and generous row height. Color carries meaning (edge direction, win/loss), never decoration.
4. **Team colors as accents only.** Teams have brand colors and logos. Use them in small doses (logo, thin accent bar), never as large backgrounds.
5. **Desktop and phone are both first-class.** Desktop for research, phone for Saturday. Tables must collapse into readable cards on mobile.
6. **Light and dark mode**, with dark as the default.

**Navigation (primary)**
- **This Week**: the slate (home)
- **Picks**: the model's recommendations + record
- **Contest**: the pick'em league: this week's contest slate, recommended picks, your entries and standing
- **Rankings**: power ratings, plus season outlook (projected records, conference and playoff odds), and later history (season finals, programs, coaches)
- **Teams**: team pages (via search/rankings)
- **Performance**: model track record and calibration
- **Lab**: model weights, model builder, backtest comparisons (builder later)
- Global: season/week selector, team search (⌘K command palette), sport switcher placeholder (CFB now, NFL later), alerts (bell with unread count), settings, account

## Screens

### 1. This Week (Slate) — **highest priority**
Purpose: see every game this week, how the model sees it, and where the edges are.
- Header: season and week selector (e.g. "2026 · Week 6"), last updated time, counts ("54 games · 9 picks").
- **This week's record strip** under the header: the model's picks graded as games finish, e.g. "This week 1-0 · 2 live (1 covering) · 6 to play · +1.0u". Tapping it filters to picks.
- Filters: All / Picks only / Starred / FBS vs FBS / conference / ranked teams / day-time window; sort by kickoff, edge size, or confidence.
- **Game row/card** content:
  - Kickoff (day/time, TV network optional), away @ home with logos and current model rank, neutral-site marker
  - **Market spread** (e.g. OSU −13.5) with the opening line and a tiny movement sparkline ("opened −14"), and **Model spread** (OSU −17.2)
  - **Edge** in points with direction (e.g. "+3.7 OSU"), visually emphasized when it clears the pick threshold
  - **Cover probability** for the edge side (e.g. 59%) and pick tier badge (A/B/C) if it's a pick
  - Model win probability
  - Total (market vs model): secondary, can be hidden at first
  - After the game: final score and result (✓ covered / ✗ / push) for our pick
  - **Star** toggle (watchlist), and a small **weather icon** on outdoor games with notable conditions (wind, rain/snow, extreme cold), with the details in a tooltip
- States: upcoming, in progress, final; game with no line yet; line moved since pick (show "picked at −13.5, now −15").

### 2. Game Detail
Purpose: answer "why does the model like this?"
- Header: teams, logos, records, model ranks, kickoff, venue, star toggle, weather (forecast wind, precipitation, temperature; "Dome" for indoor venues)
- **The Number** panel: market line (open → current), model line, edge, cover probability, win probability, pick tier, and a small line-movement sparkline
- **Prediction drivers**: a waterfall or diverging bar list of contributions, e.g. "Home field +2.1 · OSU pass offense vs Purdue pass defense +6.4 · Purdue rush offense vs OSU rush defense −1.2 · ...", summing to the model margin
- **Unit matchup**: offense vs defense comparison (EPA/play, success rate, explosiveness, rushing vs passing), shown as percentile bars for each side
- **Projected score distribution**: bell curve of margin with the market line marked and the cover area shaded
- Manual adjustment control (later): "Apply adjustment: −4 pts OSU (QB out)", with a re-computed line
- Head-to-head history and each team's recent form (last 5 vs spread)

### 3. Picks
- **Current picks**: list of this week's recommendations, sorted by tier/edge, each showing the line picked at, current line, CLV so far, and status
- **Record summary** strip: season ATS W-L-P, win %, units, ROI, avg CLV, with a comparison to break-even (52.4%), plus this week's record so far
- **Best lines** tab: every upcoming game ranked by the model's cover probability against the best line available to you, one row per game. Each row shows the line, a source tag (Market or the contest's name), cover %, edge, tier, and the other source's line for comparison. Games below the pick threshold sit under a visible cutoff line. Source chips filter which lines count (default: the active contest + market). Until the model's calibration is proven, cover % carries an "uncalibrated" label
- Past weeks: collapsible by week with results
- Filters: tier, conference, favorite/underdog, home/away

### 4. Rankings
- Table: rank, Δ from last week (▲3 / ▼1), team (logo, name, conference, record), **overall rating** (points vs average team), **offense** and **defense** ratings with ranks, SOS, next game with model spread
- Toggle: model ratings vs comparison (SP+, FPI) side by side (later)
- Season/week time machine: view rankings as of any past week, back to 2014
- Mini-sparkline of rating trajectory per row
- Filter by conference; FBS only by default
- Tabs: **Power** (this screen) · **Season Outlook** (§8) · **History** (§11, later)

### 5. Team Page
- Header with team color accent, logo, record (straight up + ATS), current rank/rating
- Rating trajectory chart over the season (overall, off, def), optionally overlaid with last season
- Schedule table: every game with market line, model line, result, ATS result
- Unit profile: radar or percentile bars (rush/pass offense/defense, explosiveness, havoc, etc.)
- Preseason vs now: prior rating vs current, returning production, talent rank

### 6. Performance (Model Track Record)
- KPI tiles: ATS win %, units, ROI, avg CLV, number of picks, for this season and all-time (live), plus the backtest shown separately and labeled as such
- Cumulative units chart over time (live picks only, backtest as a dashed reference)
- **Win % by edge bucket** bar chart with the 52.4% break-even line
- **Calibration chart**: predicted probability vs actual hit rate
- Breakdown tables: by tier, by week of season, by conference, favorite vs underdog
- Model version selector (compare v1 vs v2)

### 7. Contest (Pick'em) — **high priority**
Purpose: make this week's league picks quickly and confidently on Thursday or Friday. Contests are generic (any platform and rules); the default is a Splash league: **4 picks per week from college + NFL games, each game locks at its kickoff, 1 point per correct pick.**
- **Load the slate:** a large "Paste from Splash" text area. The user copies the contest webpage's text and pastes it. The app shows a parsed preview (matched teams with logos, lines, kickoff times), with unmatched rows highlighted for a quick fix. Re-pasting later updates lines. Manual "add game" is a secondary option.
- **Recommended picks:** the slate ranked by cover probability against the **contest's** line, with the top 4 highlighted and a visible cutoff line under #4. Each row: sport tag (CFB/NFL), matchup, contest line, consensus market line, model line, edge, cover %, kickoff and lock countdown.
  - Flag where the contest line differs from the market ("contest −3 · market −5.5").
  - NFL games show a "no model yet" state, ranked on the contest-vs-market gap only.
  - Locked games (kickoff passed) are greyed and can't be picked.
- **Pick tray:** "Your picks: 2 of 4", where the user's chosen picks may differ from the model's. Each pick shows the line it was locked at and when.
- **Results & standing:** this week so far (you vs the model's top 4, in points), weekly results, season record **you vs the model's top 4**, and an optional league standing entered by hand.
- **Contest settings:** rules form (sports, picks per week, lock rule, scoring, push rule) with "Splash" as a preset.

### 8. Season Outlook (inside Rankings or its own tab)
- Table: team, current record, **projected final record** (expected wins), win-distribution mini-histogram, **P(conference title game)**, **P(conference title)**, and later **P(CFP)** and seed
- Team page module: "Path to the playoff", with the win distribution and the remaining games that swing the odds most
- Conference view: projected standings for one conference

### 9. Model Lab
Purpose: look inside the model and, later, build variants.
- **Weights view (Next):** for the production model or any version, show the settings you chose (hyperparameters, fixed weights) and the **learned weights** side by side, with plain-English labels ("Home field: +2.3 pts", "Pass offense EPA: 1 point of EPA/play = 31 pts", "Preseason prior fades to 10% by week 8"). Include a chart of the prior-decay curve and a bar chart of input importance.
- **Versions list:** each model version with status (dev/candidate/production/retired), parent, created date and headline backtest metrics.
- **Model builder (Later):** clone a version, then use a form (sections: Inputs, Hyperparameters, Home field, Prior, Distribution, Pick rules) where each weight is a toggle of "Fit from data" or "Fixed: [value]". A "Run backtest" button shows queued → running → done.
- **Compare:** two versions side by side: metric deltas, overlaid calibration charts, record by edge bucket, and the games where they disagree most.
- **Promote:** a go/no-go checklist (MAE vs closing, ATS vs closing, calibration, consistency across seasons) with pass/fail per item. A "variants tried since last promotion" counter is shown prominently as an overfitting reminder.

### 10. Matchup Tool (Later)
- Pick any two teams (any season), choose home/away/neutral, and see model line, win probability, distribution, and drivers. Good for fun and for sanity checks.

### 11. History (Later, a tab inside Rankings)
Purpose: browse football history through the model: who was best in a season, which programs and coaches have been best over time. Built after the betting model; the model behind it is in [04-model.md §7](04-model.md).
- **Season final:** pick a season. Table: rank, team, record, **hindsight rating**, within-season z-score (for comparing across eras), **résumé rank** and strength of record ("an average top-25 team goes this well 0.3% of the time"). The point is the gap between the two: the best team and the best résumé aren't always the same. Sort by either.
- **Programs:** pick a span of seasons (range control, default 2014–2025). Table: rank, program, average rating, peak season, worst season, top-10 finishes, sparkline of seasonal ratings.
- **Coaches:** table: rank, coach, stops with years, seasons coached (partial seasons shown as decimals, interim stints marked), **value over expectation** (default), raw (unshrunk) value, and value crediting recruiting. A toggle switches the default between "controlling for recruiting" and "crediting recruiting". Every column gets a plain-English header tooltip.
- **Coach page:** header (name, current job, career summary), a tenure timeline across schools, a season-by-season chart of prior vs actual rating with the gap shaded, value-added table, ATS and close-game records (with a note that close-game records are mostly luck).
- **Era badge:** every season is rated either by efficiency stats or, before they exist, by scores only. Show a small badge wherever ratings from both kinds could appear together.
- Team pages gain an "All-time" module: season-by-season final rating and rank, with coaching changes marked.

### 12. Watchlist & alerts (Next)
- Star any game from This Week, Game Detail or Contest. Starred games get a "Starred" filter on the slate.
- **Alerts panel** (from the bell): newest first, e.g. "Colorado @ BYU: line moved BYU −7 → −6; edge now +3.1 BYU, tier C". Each links to the game.
- **Alert settings** (in Settings): delivery (email or push), alert when a starred game's edge crosses the pick threshold, alert when its line moves by ≥ N points. Note in the UI that alerts follow the line-snapshot schedule, so they can lag a move by hours.

## Components to define in the design system
- Spread/odds display (handles −, +, PK, half points, prices like −110)
- Edge pill (direction + magnitude + threshold state)
- Tier badge (A/B/C)
- Probability bar / meter
- Team chip (logo + abbreviation + rank), team row
- Game card (mobile) / game row (desktop)
- Result marker (W/L/P, covered/not)
- Rank movement indicator (▲▼—)
- Sparkline, waterfall/driver bars, percentile bar, distribution curve
- Line-movement cell (current line, opening line, tiny sparkline), star toggle, weather flag icon (wind / rain / snow / cold, with tooltip)
- Live record strip (W-L so far, live, to play), line-source tag (Market / contest name), "uncalibrated" label, alert list item
- KPI stat tile
- Win-distribution mini-histogram, odds percentage cell (e.g. 37% with a subtle fill bar)
- Slate entry row (team autocomplete + line input), drag-to-reorder list (confidence points)
- "Fit / Fixed [value]" toggle field, run-status pill (queued/running/done/failed), pass/fail checklist item
- Data table with sticky header, sortable columns, responsive card collapse
- Week selector, filter bar, command palette (team search; coaches later)
- Season-range control and era badge (History, later), tenure timeline
- Empty, loading (skeleton) and error states

## Color semantics
- **Edge/positive** and **negative** need a clear pair that also works for colorblind users. Prefer blue/orange over pure green/red, with icons/text so color isn't the only signal.
- Pick tiers: three steps of one hue, not three unrelated colors.
- Team brand colors are only for accents. Never put text on team-color backgrounds without a contrast check.

## Sample data (use in mocks)
Full, internally consistent sample data for every screen lives in [`design/sample-data.md`](../design/sample-data.md). Highlights:

| Kickoff | Away | Home | Market | Model | Edge | Cover % | Tier |
|---|---|---|---|---|---|---|---|
| Sat 12:00 FOX | Purdue | #1 Ohio State | OSU −27.5 | OSU −31.2 | +3.7 OSU | 59% | B |
| Sat 3:30 CBS | #6 Ole Miss | #9 LSU | LSU −3.5 | Ole Miss −1.4 | +4.9 MISS | 62% | B |
| Sat 7:00 ESPN | Kansas State | #10 Utah | UTAH −4 | UTAH −4.6 | +0.6 UTAH | 51% | — |
| Sat 7:30 ABC | #2 Texas | #4 Oklahoma (neutral, Dallas) | TEX −6.5 | TEX −1.3 | +5.2 OU | 63% | A |
| Fri 8:00 FS1 | UNLV | Boise State | BSU −10 | BSU −9.1 | +0.9 UNLV | 52% | — |

Ranks are the model's power ranks. Rankings sample: 1. Ohio State +27.4 (Off 3rd, Def 1st) ▲1 · 2. Texas +25.9 ▼1 · 3. Oregon +24.8 — · 4. Oklahoma +24.4 ▲5 · 5. Georgia +23.1 —

Record sample: 2026 season 31-24-1 ATS (56.4%), +4.6 units, ROI +7.6%, avg CLV +0.9 pts.

## Design sequence (suggested)
1. Design system: type scale (with tabular numerals), color tokens (light/dark), spacing, core components above
2. This Week (desktop + mobile)
3. Contest (desktop + mobile)
4. Game Detail
5. Rankings + Season Outlook + Team page
6. Picks + Performance
7. Market extras: line movement, best lines, record strip, watchlist & alerts, weather (playbook Prompt 11)
8. Model Lab (weights view first, builder after)
9. Empty/loading/error states and the remaining screens
10. History: season finals, programs, coaches (later; design closer to Phase 6)

## Handoff notes for implementation
- Target stack: Next.js App Router, Tailwind, shadcn/ui, Recharts (or visx), lucide icons
- Keep tokens as CSS variables, so light/dark and future per-sport theming are trivial
- Numbers right-aligned in tables, with tabular-nums everywhere
- Every data screen needs a skeleton state drawn at the loaded size, because the database can take a few seconds to wake up. Turn the pulse off under reduced motion.

## Design decisions

From the first design pass (handoff of 2026-10-06; see [Design source](#design-source)). Full values live in `design/README.md` and `design/handoff/tokens/`; this section records the choices and the places the design departs from the brief above. "Where" names the design file in `design/handoff/designs/` and/or the screenshot in `design/handoff/screenshots/`.

### Foundations
| Decision | Where |
|---|---|
| **Fonts:** IBM Plex Sans (400–700) for UI, IBM Plex Mono (400–600) **only** for scores, clocks and raw paste text. Chosen over Inter/Geist for real tabular figures, a true − glyph, distinct 1/l/I and 0/O at 12px, and a matched mono. `tabular-nums lining-nums` on body, everywhere. Table headers in sentence case ("Cover %"). | `Foundations.dc.html` (Call notes); every screenshot |
| **Base (dark default):** background `#0c0f12`, card `#13161a`, popover `#1b1e23`, foreground `#eef0f3`, muted-fg `#9fa5ad`, border `#2a2e33`. No pure black or white. Primary is ink (`#e5e8ec`), not a hue: color is reserved for meaning. Light: background `#f5f7f9`, foreground `#13161b`. | `tokens/tokens.css`; `Review Checks.dc.html` §05 |
| **Edge gets its own violet:** `--edge` `#b699eb` dark / `#6d41a9` light, deliberately **not** `--pos`, so "model disagrees" doesn't read as good news. Filled pill only when edge ≥ 2.5; below that, plain muted text. | `Components.dc.html`; `01-this-week-desktop.png` |
| **Pos/neg are blue/orange:** `--pos` `#68b5f5` / `#0465af`, `--neg` `#f19a4b` / `#a64b00` (dark/light), `--push` grey. Used only for signed outcomes (covered, units, CLV, rank move, line moved our way). `--destructive` red is only for errors and deletes, never a loss. | `tokens/tokens.json` (notes); `13-performance-desktop.png` |
| **Tiers are one violet hue in three lightness steps:** A `#bd9ff2`, B `#8a70b8`, C `#392a51` (dark; the ramp flips in light so A always has the most contrast). The letter is always printed; C has a 1px outline. | `Review Checks.dc.html` §02; `01-this-week-desktop.png` |
| **Ratings take no color** (`+27.4` in ink): "+" means above average, not good news. | `Foundations.dc.html`; `09-team-desktop.png` (header) |
| **Flat cards, tight radii:** cards are a surface step + 1px border with no shadow; shadows only on popovers, dialogs and ⌘K. Radius 4/6/8/12/full, `--radius` 6px. | `Foundations.dc.html` |
| **Table densities:** comfortable (header 40, row 48) is the system default; compact (header 32, row 36) is a per-table toggle. See open items for This Week's default. | `Foundations.dc.html`; `This Week Desktop.dc.html` (`density` prop) |
| **Whole-number spreads align with half points:** keep `BSU −10` (no ".0"), but table cells pad whole spreads with U+2008 + U+2007 so units digits line up; `format.ts` gets an align flag. Model lines always carry one decimal so they never look like market lines. | `Review Checks.dc.html` §04; `Foundations.dc.html` |

### Navigation
| Decision | Where |
|---|---|
| **Desktop:** 224px left sidebar (This Week, Picks, Contest, Rankings, Teams, Performance, Lab) with sport switcher on top and a track-record card at the bottom linking to Performance. Top bar: week selector, ⌘K search, "Updated …" time, alerts bell. | `01-this-week-desktop.png`; `This Week Desktop.dc.html` |
| **Mobile:** bottom tab bar **This Week, Picks, Contest, Rankings, More** (More = Teams, Performance, Lab, Settings). Note the order: Picks before Contest, unlike playbook Prompt 2. Filters, sort, week picker, time machine, pick tray and ⌘K open as sheets. | `02-this-week-mobile.png`; `This Week Mobile.dc.html` |
| **No "Lock" verbs:** users "add" picks; picks lock at kickoff by themselves. | `Components.dc.html` (Buttons) |

### Changes from the brief
| Brief said | Design does | Where |
|---|---|---|
| Edge and positive share one color pair | Edge is a separate violet (above); blue/orange is only for outcomes | `Components.dc.html` |
| Totals "secondary, can be hidden at first" | A Spread / Total / Both segmented control on This Week, Spread by default | `01-this-week-desktop.png`; `This Week.dc.html` |
| Best lines is a Picks tab | Also a second view on This Week (Slate \| Best lines), written as the bet ("MISS +3.5"); the Picks tab remains | `This Week.dc.html` 1b; `01-this-week-desktop.png` |
| Market cell: line + opening + sparkline | Opening line and sparkline sit muted *before* the current line inside the Market column; the separate Move column from the first hi-fi pass was removed | `This Week.dc.html` turn 2; `01-this-week-desktop.png` |
| "picked at −13.5, now −15" | Pick history goes on a second line ("Picked at −2.5 → now −3.5 · CLV +1.0") so the current number never shifts column | `Components.dc.html`; `01-this-week-desktop.png` (Ole Miss row) |
| Unit profile: "radar or percentile bars" | Percentile bars (no radar) | `Team Desktop.dc.html`; `09-team-desktop.png` |
| Drag-to-reorder list for confidence points | Kept as a component, but Splash scores 1 pt per pick, so order means priority; the list takes a points column only if a contest needs it | `Components.dc.html` |
| Waterfall drivers (color unspecified) | All driver bars neutral (`--chart-5`); direction comes from position and sign plus "Helps OU / Helps TEX" chips | `Charts.dc.html`; `05-game-detail-desktop.png` |
| Win % by edge bucket (axis unspecified) | Y-axis starts at 50%, stated on the axis | `Charts.dc.html`; `13-performance-desktop.png` |
| Calibration chart | Overconfidence drawn as gap lines in `--neg` (orange) with a gap table; the board note calls them "red", but the file uses `--neg` | `Performance Desktop.dc.html`; `13-performance-desktop.png` |
| Weather icon for wind / rain / snow / cold | Icon only past a threshold, next to the network; info only, not a model input (thresholds: see open items) | `Market Extras.dc.html`; `01-this-week-desktop.png` |
| Contest: pick tray | Added "Use the model's top 4" / "Fill N open slots with model's picks", "Copy picks to enter on Splash", a ≠ chip when the contest line differs from market (blue = better for the ranked side, orange = worse), and a purple dot for the model's side | `Contest.dc.html`; `03-contest-desktop.png` |
| Pass/fail checklist (color unspecified) | Uses `--pos`/`--neg`, keeping destructive red for errors | `Components.dc.html` |
| Login, Settings (brief: minimal) | Single account (no sign-up/reset); the sign-in button says "Waking the database" on a cold start; Settings › General has theme, default contest and time zone with a "use this device's time zone" toggle | `Palette Login Settings.dc.html` |
| Manual adjustment (later) | Drawn in full (team, points, reason, recomputed line and edge) but disabled, tagged "Coming later" | `Game Detail Desktop.dc.html`; `05-game-detail-desktop.png` |
| Season Outlook conference view; SP+/FPI comparison; last-season overlay on the trajectory | Not drawn (listed as "Try next" on the boards). Still in the brief; design them before building | `Rankings.dc.html` |

### Open items found in the handoff
Unresolved in the design. Decide each before implementing the affected screen; until then, the default below applies.
- **Edge color under color blindness.** `--pos` and `--edge` collapse to nearly the same blue under deuteranopia/protanopia (ΔE 2–7). It works today only because edge is always a filled pill and pos is always signed text. The design offered an ink-filled edge pill instead and leaned that way; the tokens still ship violet. *Default: violet, as in `tokens.css`.* (`Review Checks.dc.html` §03)
- **Weather thresholds disagree.** `This Week.dc.html` and `design/README.md` say wind ≥ 15 mph or rain ≥ 50%; `Market Extras.dc.html` says sustained wind ≥ 15 mph, rain or snow ≥ 60%, or ≤ 25°F (which also covers the brief's snow and cold).
- **Line-move alert default.** `This Week.dc.html` (turn 1) says starred games alert on moves ≥ 0.5; the empty alerts panel says 1 pt; Settings makes it a half-point stepper (N).
- **This Week density.** `Foundations.dc.html` makes comfortable the default and compact a toggle for Rankings and Lab; `This Week Desktop.dc.html` defaults to `compact` and `design/README.md` lists the This Week desktop slate as a compact table.
- **Paths in `design/README.md`.** It refers to `docs/sample-data.md` and `docs/sample-splash.txt` and lists a bundled `docs/` folder. In this repo those are `design/sample-data.md`, `design/sample-splash.txt` and the real `docs/`.
- **Screenshots, not the spec, for icons.** In `02-this-week-mobile.png` the lucide icons render as blank squares (they didn't load at capture time). Use the boards for icons.

## Screen inventory (from handoff)

_Added 2026-10-07 when the Claude Code starter kit was adopted. One ID per logical screen; desktop and mobile files share an ID. Feature IDs are in [01-product.md › Feature index](01-product.md#feature-index-ids-priorities-outcomes). All design files are in `design/handoff/designs/` and all screenshots in `design/handoff/screenshots/` (default state, dark). Unless a row says otherwise, screens are drawn in dark mode only: light mode exists only for the This Week desktop slate (This Week board, frame 1f) and the design-system boards. No screen is drawn at the 768, 1280 or 1536 breakpoints._

| ID | Screen | Design files | Screenshots | States designed | States missing | Features |
|---|---|---|---|---|---|---|
| S-01 | This Week (Slate · Best lines) | `This Week Desktop.dc.html`, `This Week Mobile.dc.html`; board `This Week.dc.html`; off-season in `App States Desktop.dc.html` / `App States Mobile.dc.html`; skeleton in `Loading States.dc.html` | `01-this-week-desktop.png`, `02-this-week-mobile.png`, `20-offseason-empty-desktop.png`, `21-offseason-empty-mobile.png` | Slate; Best lines; Spread / Total / Both; All / Picks only / Starred; no starred games; weather tooltip (desktop) and tapped open (mobile); filter & sort sheet (mobile); compact and comfortable density; light mode (desktop); loading skeleton; off-season. Row states: upcoming pick, line moved since pick, live, final, no line (FCS), neutral site | Best lines with nothing above the threshold; a week whose lines aren't posted yet; light mode at 390 | F-01, F-02, F-06, F-07, F-08, F-10, F-11, F-14, F-32 |
| S-02 | Contest | `Contest Desktop.dc.html`, `Contest Mobile.dc.html`; board `Contest.dc.html`; skeleton in `Loading States.dc.html` | `03-contest-desktop.png`, `04-contest-mobile.png` | Empty (no slate); parsed preview with one unmatched row; ranked slate (Fri, one locked game, NFL "No model yet"); pick tray (side panel / bottom sheet); results & standing (Thu, and Sat check-in with a live pick); rules with Splash preset → Custom (desktop only, by design); loading skeleton | A paste that can't be parsed or matches nothing; pick save failure (only the generic error toast exists in Components); re-paste diff (lines moved since the last paste); every game locked; confidence-points variant | F-03, F-04, F-14, F-32, F-33 |
| S-03 | Game Detail | `Game Detail Desktop.dc.html`, `Game Detail Mobile.dc.html`; board `Game Detail.dc.html`; skeleton and failed panel in `Loading States.dc.html`, `Empty and Error States.dc.html` | `05-game-detail-desktop.png`, `06-game-detail-mobile.png` | Upcoming pick (Texas vs Oklahoma, 5h before kickoff); drivers as waterfall or bars; Plain English / Show the math; weather forecast, dome and no data (desktop); loading skeleton; one panel failed (Unit matchup); manual adjustment drawn disabled ("Coming later") | Live game; final game (result, final CLV); no line yet / FCS opponent; a game that isn't a pick; weather variants on mobile | F-05, F-06, F-08, F-10, F-13, F-14 |
| S-04 | Rankings › Power | `Rankings Desktop.dc.html`, `Rankings Mobile.dc.html` (`tab="power"`); board `Rankings.dc.html`; skeleton in `Loading States.dc.html` | `07-rankings-desktop.png`, `08-rankings-mobile.png` | Power table; time machine open (popover on desktop, sheet on mobile); stepping back to a past week (interactive in the file: banner + "Back to latest"); History tab disabled ("LATER"); loading skeleton | Conference filter with no teams; a season or week with no ratings (before 2014, or week 0 before any games); error; compact density (described in Foundations, not drawn) | F-17, F-19 |
| S-05 | Rankings › Season Outlook | `Rankings Desktop.dc.html`, `Rankings Mobile.dc.html` (`tab="outlook"`); board `Rankings.dc.html` | none | Outlook table: record, projected record, win-distribution histogram, P(conf title game), P(conf title) | Loading; empty (preseason, or no simulations yet); error; conference view (brief §8) | F-20, F-21 |
| S-06 | Team page | `Team Desktop.dc.html`, `Team Mobile.dc.html`; board `Rankings.dc.html` (1g, 1h); preseason in `App States Desktop.dc.html` / `App States Mobile.dc.html` (`frame="team"`) | `09-team-desktop.png`, `10-team-mobile.png` | Mid-season (Ohio State, live game in the header); preseason (only the trajectory chart empty) | Loading; error; the page before Phase 5 with "Path to the playoff" hidden, and before Phase 7 with CFP % hidden; FCS team (no rating); last-season overlay (brief §5) | F-18, F-20, F-21, F-22 |
| S-07 | Picks (Week · Best lines · Past weeks) | `Picks Desktop.dc.html`, `Picks Mobile.dc.html`; board `Picks - Performance.dc.html`; no-picks in `App States Desktop.dc.html` / `App States Mobile.dc.html` (`frame="nopicks"`) | `11-picks-desktop.png`, `12-picks-mobile.png` | Current week with working filters; Best lines (Splash + Market, Splash only); uncalibrated; past weeks (Week 5 expanded); filter sheet (mobile); no picks this week | Loading; error; Best lines empty; Past weeks empty (week 1 of a season) | F-02, F-04, F-07, F-09, F-10, F-32, F-37 |
| S-08 | Performance | `Performance Desktop.dc.html`, `Performance Mobile.dc.html`; board `Picks - Performance.dc.html`; skeleton in `Loading States.dc.html` | `13-performance-desktop.png`, `14-performance-mobile.png` | 2026 season (live); compare with v1.1 (candidate); version menu; chart hover; loading skeleton. Mobile: KPI tiles and units chart only | All-time scope (a prop in the file, on no board); no live picks yet (season start, or before paper trading begins); error; mobile edge buckets, calibration and breakdowns (decided: the link opens the desktop sections stacked) | F-09, F-10, F-36, F-37 |
| S-09 | Model Lab (Weights · Versions · Compare) | `Lab Desktop.dc.html`; board `Model Lab.dc.html` | `15-lab-desktop.png` | Weights (v1.0); Versions; Compare v1.0 vs v1.1. Desktop only, by design | Loading; error; no versions or runs yet; a backtest running, as seen from Versions | F-35, F-36 |
| S-10 | Model Lab › Builder and Promote (low fidelity) | `Lab Wireframes.dc.html`; board `Model Lab.dc.html` | `16-lab-builder-wireframe.png` | Builder with run states not started, queued, running, done and failed; Promote go/no-go checklist | Hi-fi design (planned before Phase 7) | F-38 |
| S-11 | Alerts panel | `This Week Desktop.dc.html` (`alertsOpen`), `Alerts Mobile.dc.html` (`screen="panel"`, `"empty"`); board `Watchlist - Alerts.dc.html` | `18-alerts-mobile.png` | One unread alert; no alerts; bell with and without an unread badge | Loading; error; many alerts across weeks | F-14 |
| S-12 | Settings › Alerts | `Settings Desktop.dc.html`, `Alerts Mobile.dc.html` (`screen="settings"`); board `Watchlist - Alerts.dc.html` | `17-settings-alerts-desktop.png` | Delivery email or push; both rules with scope menus and the half-point stepper; snapshot-lag note | Browser push permission denied; save failure | F-14 |
| S-13 | Settings › General | `App States Desktop.dc.html`, `App States Mobile.dc.html` (`frame="settings"`); board `Palette Login Settings.dc.html` | none | Theme, default contest, time zone with the device toggle on and off (live preview time) | Save failure; the Contests and Account sections named in the settings nav | F-45 |
| S-14 | Command palette (⌘K) | `Command Palette.dc.html`; board `Palette Login Settings.dc.html` (4a–4d) | `19-command-palette.png` | Open over This Week (recent teams + jump to); typed query; mobile full-screen sheet; typed query on mobile | No results (the copy exists in the file, but no frame shows it); first use with no recent teams | F-43 |
| S-15 | Login | `App States Desktop.dc.html`, `App States Mobile.dc.html` (`frame="login"`); board `Palette Login Settings.dc.html` | none | Default, wrong password, waking the database (drawn as a password form) | Needs a redraw for GitHub sign-in (see mismatch 9): "Sign in with GitHub" default, waking the database, and "this GitHub account isn't allowed" | F-42 |
| S-16 | App shell and global states | Every screen file (sidebar, top bar, mobile tab bar); `App States Desktop.dc.html` / `App States Mobile.dc.html` (`frame="apierror"`); wake-up note in `Loading States.dc.html` | `01-this-week-desktop.png`, `20-offseason-empty-desktop.png`, `21-offseason-empty-mobile.png` | Desktop sidebar with sport switcher and track-record card; top bar (week selector, ⌘K, updated time, bell); mobile top bar and bottom tabs; API unreachable (frame stays, auto-retry, Details); "Waking up the database…" note | Mobile "More" menu (Teams, Performance, Lab, Settings); 768 tablet layout; stale-data banner (described in `design/README.md` only); toasts drawn only as components | F-09, F-40, F-43 |
| S-17 | Teams index | Not designed | none | — | Every state. Decided 2026-10-07: it reuses the Rankings table components and grows from the walking skeleton's team list | F-44 |

Not screens, so no S-ID: the design-system boards (`CFB Design System.dc.html`, `Color Tokens.dc.html`, `Foundations.dc.html`, `Components.dc.html`, `Market Extras.dc.html`, `Charts.dc.html`, `Specimen.dc.html`, `Review Checks.dc.html`) and the superseded `This Week Wireframe.dc.html`.

### Mismatches between the handoff and the brief (resolved 2026-10-07)

The 13 rows under [Changes from the brief](#changes-from-the-brief) stand as recorded. These are the remaining mismatches, each resolved by the owner on 2026-10-07. Rows 2–5 also settle four of the [Open items found in the handoff](#open-items-found-in-the-handoff); that list is left as it was, so read it together with this table. Decision IDs are in [decisions.md](decisions.md).

| # | The brief (or another doc) says | The handoff does | Resolution |
|---|---|---|---|
| 1 | §12: alert when a **starred** game's edge crosses the pick threshold | Settings › Alerts applies the edge rule to **all games** by default, with a scope menu (All games / Starred games) | Design: all games by default, scope selectable (D-082) |
| 2 | §12: alert when a line moves by ≥ N points (N unset) | This Week board turn 1 says 0.5; the empty alerts panel and Settings say 1.0 | 1.0 pt by default, half-point stepper, starred games by default (D-082) |
| 3 | §1: weather icon for wind, rain/snow, extreme cold | This Week board and `design/README.md`: wind ≥ 15 mph or rain ≥ 50%. `Market Extras.dc.html` and `design/sample-data.md`: sustained wind ≥ 15 mph, rain or snow ≥ 60% likely, or ≤ 25°F | Market Extras thresholds (D-083) |
| 4 | Principle 3: "generous row height" | This Week desktop slate defaults to compact | Compact on the This Week desktop slate; comfortable is the default everywhere else, with compact as a per-table toggle on Rankings and Lab (D-084) |
| 5 | Color semantics: edge and outcomes as a colorblind-safe blue/orange pair | `--edge` is its own violet, which nearly matches `--pos` under deuteranopia; the alternative (ink-filled pill) was offered, not adopted | Keep violet as `tokens.css` ships it (D-085) |
| 6 | Navigation: "settings, account" | `App States` settings nav: General · Contests · Alerts · Account. `Settings Desktop.dc.html`: Account · Appearance · Contests · Alerts | General · Contests · Alerts · Account, from the later design pass; "Appearance" is General (D-086) |
| 7 | §8: P(CFP) "later" | Team page "Path to the playoff" shows "Make the CFP 89%" | CFP % stays hidden until F-22 (Phase 7). The module itself appears with F-20 (Phase 5) (D-081) |
| 8 | Navigation: "Teams: team pages (via search/rankings)" | A Teams nav item with no destination screen | A Teams index (S-17, F-44) built from the Rankings table components, starting as the walking skeleton's team list (D-080) |
| 9 | Changes from the brief: single-account login. 02 and D-012: GitHub OAuth via Auth.js | A password form with "4 tries left before a 15-minute pause" | GitHub sign-in stays. S-15 is redrawn as "Sign in with GitHub" plus the waking state; the wrong-password state is dropped (D-078) |
| 10 | §6: Performance (mobile unspecified) | Mobile shows only KPIs and the units chart, then links to "Edge buckets, calibration & breakdowns ›", which has no screen | The link opens the desktop sections stacked in one column, with tables collapsed to cards (D-087) |
| 11 | Navigation: ⌘K team search (coaches later) | ⌘K also finds this week's games and screens, with "G then a letter" shortcuts | Keep the design (D-088) |
| 12 | §2: Game Detail panels | Adds a number line under The Number, a Plain English / Show the math toggle and a 46 / 17 / 37 outcome bar | Keep the design (D-088) |
| 13 | 04 § 5: tune 2014–2021, validate 2022–2023 | Performance, Lab and sample data: "Validation 2016–2023", "Holdout 2024–2025" | Rolling-origin protocol in [04-model.md § 9](04-model.md#9-evaluation-protocol-fixed-2026-10-07), under which the design's labels are correct (D-076) |
| 14 | 04 § 5: edge buckets 0–1.5, 1.5–3, 3–5, 5+ | Performance buckets picks only: 2.5–3.5, 3.5–5.0, 5.0–7.0, 7.0+ | Both. 04's buckets cover every game and feed the go/no-go trend test; the design's buckets cover picks and are display only (D-077) |
| 15 | 01: CLV, calibration charts and the contest tracker are Next | All three appear on MVP screens (This Week, Picks, Performance, Contest) | All three are MVP (D-081) |

One more difference needs no decision: `design/README.md` states the tier thresholds (pick ≥ 2.5, C ≥ 2.5, B ≥ 3.5, A ≥ 5.0) as fixed numbers, while [04-model.md § 4](04-model.md) tunes them. The UI reads the thresholds from the active model version's spec (D-055), and the fixture's v1.0 spec uses those values.
