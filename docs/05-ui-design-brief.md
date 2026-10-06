# 05 — UI Design Brief (for Claude Design)

> **How to use this doc:** attach it to Claude Design along with `01-product.md` and `design/sample-data.md`, then follow the prompts in [07-claude-design-playbook.md](07-claude-design-playbook.md), which also covers what to do with the output. When designs are done, hand off to Claude Code to implement in `web/` (Next.js + Tailwind + shadcn/ui).

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
