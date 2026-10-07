# Handoff: CFB Model — design system + app screens

## Overview
A private college-football analytics app for one user. A statistical model predicts every FBS game, compares its numbers to sportsbook and pick'em-contest spreads, recommends picks where it disagrees, ranks teams, projects seasons, and tracks its own record honestly. The user researches at a desk on weekday evenings, makes Splash pick'em picks Thu/Fri, and follows results on a phone on Saturday.

This bundle covers: the design system (tokens, type, spacing, number formats, components, charts) and hi-fi screens for This Week, Contest, Game Detail, Rankings + Season Outlook, Team, Teams index, Picks, Performance, Model Lab, Watchlist/Alerts, ⌘K palette, Login, Settings, plus loading / empty / error states. Desktop (1440) and mobile (390) for each, a 768 tablet This Week, dark default with a light frame per screen.

**Updated 2026-10-07.** Decisions made after the 2026-10-06 handoff, the missing states and the light frames are on the `Pass … .dc.html` boards (A Decisions · B New screens · C1–C3 States · D Light mode · Audit). Where a Pass board disagrees with an older board, the Pass board wins. `Pass Audit.dc.html` lists every added or changed frame by screen ID (S-01…S-17).

Product context lives in the repo's `docs/` (01-product, 04-model, 05-ui-design-brief) — not bundled here. All mock numbers come from `design/sample-data.md` (internally consistent — use it for fixtures/tests); the sample Splash paste is `design/sample-splash.txt`.

## About the design files
Files in `designs/` are **design references built in HTML** — prototypes showing intended look and behavior, not production code. Recreate them in the target codebase: **Next.js App Router + Tailwind + shadcn/ui + Recharts (or visx) + lucide icons** in `web/` (per the brief). Don't port the HTML/inline styles; use them to read exact values.

**Viewing:** open a board file (e.g. `designs/This Week.dc.html`) in a browser via a local static server (`npx serve designs`) — `support.js`, sibling `.dc.html` imports and `*-data.js` must load from the same folder. Boards set the token CSS variables on wrapper divs; per-screen files (`This Week Desktop.dc.html` etc.) expect those variables from the parent, so view them through a board. Each screen file declares its states as props (listed below); boards render every state side-by-side with numbered notes (1a, 1b…) explaining decisions — **read the board notes, they are the spec.**

## Fidelity
**High-fidelity** for everything except `Lab Wireframes.dc.html` (Model builder + Promote) and `This Week Wireframe.dc.html` (superseded early wireframe — ignore). Recreate colors, type, spacing and behavior pixel-accurately with shadcn primitives restyled by the tokens. Builder/Promote are low-fi: follow structure and behavior, style with the system.

---

## Design tokens

### Color — `tokens/tokens.css` (drop-in)
CSS variables, shadcn naming, oklch with hex comments. `:root`/`.dark` = dark (default), `.light` = light. `tokens/tokens.json` has per-token notes and WCAG contrast checks (all pass 4.5:1 for text pairs).

Key semantic tokens beyond shadcn defaults:

| Token | Dark | Light | Meaning |
|---|---|---|---|
| `--edge` / `-foreground` | #b699eb / #0c0f12 | #6d41a9 / #fcfcfc | "Model disagrees with market." Edge pill fill. Deliberately NOT `--pos` |
| `--pos` | #68b5f5 | #0465af | Good signed outcome: covered, +units, +CLV, ▲rank, line moved our way |
| `--neg` | #f19a4b | #a64b00 | Bad signed outcome: not covered, −units, ▼rank, moved against us |
| `--push` | #a7abb1 | #5f6469 | Push / no change |
| `--tier-a/b/c` (+fg) | #bd9ff2 · #8a70b8 · #392a51 (fg #0c0f12 · #0c0f12 · #d7c9f3) | #6d41a9 · #987aca · #e2d9f5 (fg #fcfcfc · #13161b · #5a358c) | Pick tiers: one violet, three lightness steps. C gets 1px outline |
| `--live` | #52cd86 | #0b7643 | Live game dot/clock only |
| `--locked` | #91969b | #62666c | Locked (kickoff passed) |
| `--breakeven` | #c9ced4 | #373b40 | Break-even reference lines (52.4%, contest 50%) |
| `--chart-1…5` | #4fa6e9 #e38d3d #aa8dde #39bab4 #87909c | #037ac0 #c9690c #7f5bb6 #018d87 #78818c | Series identity, in order |

Base dark: background #0c0f12, card #13161a, popover #1b1e23, foreground #eef0f3, muted #1d2125, muted-foreground #9fa5ad, accent (row hover/selected) #262a30, secondary #23272b, border #2a2e33, input #5f646a, ring #67aaed, primary #e5e8ec (ink, not a hue), destructive #ef6661. Light values in tokens.css.

Rules: blue/orange (not green/red) for colorblind safety; color never the only signal (glyph, sign, shape, text always present). Ratings (+27.4) take **no** color — "+" means above average, not good news. Team brand colors only as the 20px logo dot and 3px accent bar; never backgrounds, never under text; locked games drop team color.

Tailwind v4: map with `@theme inline { --color-edge: var(--edge); --color-pos: var(--pos); … }` alongside the standard shadcn mappings; toggle theme via `.light` class on `<html>` (dark is default, no class needed).

### Typography
- `--font-sans: "IBM Plex Sans"` (400/500/600/700), `--font-mono: "IBM Plex Mono"` (400/500/600). Load via `next/font/google`.
- **`font-variant-numeric: tabular-nums lining-nums` on body — required everywhere.** Never proportional figures in data.
- Mono **only** for scores and clocks (they tick; must not jitter) and raw paste text.

| Role | Desktop size/line · weight · tracking | Mobile 390 |
|---|---|---|
| KPI number | 32/40 · 600 · −0.01em | 28/36 |
| Page title | 24/32 · 600 · −0.005em | 20/28 |
| Board/section h2 | 20/28 · 600 | |
| Section / panel title | 16/24 · 600 | |
| Table body / body | 14/20 · 400 (emphasis 600) | |
| Label (buttons, chips, tabs, pills) | 13/16 · 500 | |
| Table header | 12/16 · 500 · muted-foreground, sentence case ("Cover %") | |
| Caption / meta | 12/16 · 400 · muted-foreground — **floor size, nothing smaller** | |
| Score/clock | Plex Mono 14/20 · 500; detail 20/28 · 600 | |

Minus sign is always U+2212 (−), same width as +. Records keep the hyphen (31-24-1).

### Spacing (4px base)
space-1 4 · 2 8 · 3 12 · 4 16 · 5 20 · 6 24 · 8 32 · 10 40 · 12 48 · 16 64.
Cell padding 12px horizontal · card padding 16 · section gap 24 · page gutter 16 / 24 / 32 at 390 / 768 / 1280.

### Radius
sm 4 (tier badge, result marker) · md 6 = `--radius` (buttons, inputs, nav items) · lg 8 (cards, popovers) · xl 12 (mobile sheets) · full (edge pill, chips).

### Borders
1px `--border` dividers/card edges · 1px `--input` control outlines · focus: 2px `--ring` outline, 2px offset · active tab / sorted column: 2px `--foreground` · team accent: 3px team color.

### Elevation
0 canvas (`--background`) · 1 card (`--card` + 1px border, **no shadow**) · 2 popover/tooltip (`--popover`, `0 8px 24px -8px rgba(0,0,0,.35)`) · 3 dialog/⌘K (`0 24px 64px -12px rgba(0,0,0,.5)`). Shadows only on things that float above data.

### Table density
Comfortable (default): header 40, row 48. Compact (per-table toggle on Rankings, Lab, This Week desktop slate): header 32, row 36. Numbers right-aligned. Sticky header `top: 56px` with 1px rule.

### Breakpoints
390 base: game cards, bottom tab bar, chip rows scroll sideways, gutter 16, all targets ≥ 44px.
768 md: table with priority columns (drops Win %, TV, totals), top bar, gutter 24.
1280 xl: full tables, full sidebar nav, gutter 32, content max 1216.
1536 2xl: table + 360px game-detail rail, max 1472.
(Screens are drawn at 1440 desktop and 390 mobile.)

### Number formats (every number on every screen is one of these — build a `format.ts`)
- **Spread:** favorite abbr + − + number. `OSU −27.5`, `BSU −10` (whole numbers bare), `PK` for even. No line → "No line" muted.
- **Price:** American, always signed, `−110`; muted 12px beside a spread.
- **Model line:** like spread but **always one decimal** (`CLEM −34.0`) so model never looks like market.
- **Edge:** always `+`, one decimal, side after: `+3.7 OSU`. Filled `--edge` pill only when ≥ 2.5 (a pick); otherwise plain muted text.
- **Cover %:** integer for the edge side `59%`; `~54%` prefix = market-implied (no model, e.g. NFL).
- **Win %:** model favorite abbr + integer `TEX 54%`. Record win rates one decimal `56.4%`.
- **Rating:** signed, one decimal, ink color `+27.4`.
- **Rank move:** `▲3` (pos) `▼1` (neg) `—` (push).
- **Record:** `31-24-1`; push count only if non-zero (`5-0`).
- **Units:** `+4.6u` / `−1.1u`, pos/neg color.
- **CLV:** `+0.9 pts`, positive = beat the close.
- **Kickoff:** `Sat 3:30 PM ET` + network muted; drop "ET" inside tables whose header says ET.
- **Lock countdown:** two largest units (`Locks in 1d 14h`, `3h 20m`, `12m`) → "Locked" + lucide `lock` in `--locked`.
- **Live score:** mono, away first `PUR 3 · OSU 24` + live dot + `Q3 9:12` (never dot alone). Final: `Final · UNLV 24, BSU 31`.
- **Pick thresholds:** read from the active model version's spec, never hard-coded. v1.0: pick = edge ≥ 2.5 · Tier C ≥ 2.5 · B ≥ 3.5 · A ≥ 5.0. Legends and empty states print whatever the active spec says.

### Motion
Skeleton pulse: opacity 1 → 0.5 → 1 over 1.6s, all bars in sync; static fill under `prefers-reduced-motion: reduce`. Tooltips open after 300ms on hover/focus. Toasts 5s, pause on hover, bottom-right desktop / above tab bar mobile.

---

## Components (see `Components.dc.html`, `Market Extras.dc.html`, `Charts.dc.html` — every state drawn: default, hover, focus, disabled/locked, loading)

**Numbers & badges**
- *SpreadDisplay* — favorite/whole/PK/with price/no line; "moved since pick" and "contest ≠ market" put history on a **second line** (`picked −2.5`, `market −4.5`) so the current number never shifts columns.
- *EdgePill* — h24, px8, radius full, 13px/600. Variants: pick (filled `--edge`), below threshold (muted text), no line (—), large (The Number panel), locked, loading. No hover/focus of its own; the row is the hit target.
- *TierBadge* — A/B/C, radius 4; "—" for no pick; optional "Tier A" label.
- *ProbabilityBar* — 0–100 scale with 50% tick (59% should look modest). Hatched = market-implied. Win-split variant (TEX 54% | OU 46%).
- *ResultMarker* — glyph first (✓ ✗ P), color second; covered/not/push/pending; compact squares for "last 5 ATS"; straight-up W/L/P.
- *RankMove* — ▲▼—.

**Team & game**
- *TeamChip* — 20px max logo slot (team-color dot until real logos), model rank small+muted before name with no "#", abbreviation or full name; FCS tag; neutral marker "N"; locked drops color.
- *TeamRow* — upcoming / live (mono scores) / final (winner bold, loser muted).
- *TeamHeader* — 3px accent bar; `Ohio State 1 · 5-0 (ATS 3-2) · Rating +27.4`.
- *GameRow* (desktop ≥1280) / *GameCard* (mobile) — states: upcoming pick, line moved since pick (`Picked −2.5 · CLV +1.0 pts`), live, final, no line / FCS.
- *LineMovementCell* — opening line + sparkline muted *before* the current line inside the Market column (market → model → edge still reads left to right). Flat line when unchanged; past seasons = two dots open/close, dashed join.
- *LineHistoryChart* — step line through each snapshot, labelled where value changed, kickoff marker.
- *StarToggle* — 24px desktop / 44px mobile target; shape (outline vs filled star) carries state.
- *WeatherFlag* — outdoor games only; icon next to network only when sustained wind ≥ 15 mph, rain or snow ≥ 60% likely, or ≤ 25°F at kickoff. Hover (desktop) / tap (mobile) for forecast + which threshold tripped. Wind, rain, snow and cold tooltips drawn in `Market Extras.dc.html`; dome and no-data never show an icon. Info only, not a model input.
- *LiveRecordStrip* — "This week 1-0 · 2 live (IOWA covering, OSU not yet) · 6 to play · +1.0u", one segment per pick (won/lost/live/to play); click toggles Picks-only filter.

**Tables & lists**
- *DataTable* — sortable (sorted = 2px ink rule + arrow; hover shows sort hint), sticky header, row hover `--accent`, keyboard focus ring. Collapses to cards < 768: rank, team, sorted column stay prominent; rest becomes a caption line; sort moves into a sheet.
- *SlateEntryRow* (paste parser) — sport, away, home, contest line, kickoff, match status (Matched / N names unmatched).
- *WinHistogram* mini, *OddsCell* (`37%` with 24%-opacity `--chart-1` fill behind ink text, length only).

**Forms & controls** (shadcn restyled; desktop controls h32, mobile pads to 44)
- Buttons: primary / secondary / outline / ghost / destructive; disabled 50% opacity + no pointer events; loading keeps width, icon → spinner. No "Lock" verbs — users "Add to picks"; picks lock at kickoff automatically.
- Input states incl. error ("No team matches. Pick one or save an alias."). Line inputs accept `-7`, `−7`, `+7`, `pk`, always render true minus.
- PasteArea — Plex Mono, footer "9 rows match · 1 unmatched", actions "Add game manually" / "Review matches".
- Segmented control, filter chips (selected = ink fill + check), Fit/Fixed toggle field, run-status pill (queued/running/done/failed), pass/fail checklist item.

**Navigation**
- Desktop: 224px left sidebar (`--card`, right border): logo mark (24px ink square "CF") + "CFB Model"; sport switcher (live dot, "College football", chevrons; NFL marked Later); nav items h34 radius 6, 13px, 16px lucide icons — This Week `calendar-days`, Picks `target` (count badge 9), Contest `trophy`, Rankings `list-ordered`, Teams `shield`, Performance `activity`, Lab `flask-conical`; active = `--accent` fill + 600; hover = `--muted`. Bottom: track-record card ("Model · 2026 live · 31-24-1 56.4% · +4.6u · CLV +0.9 · Track record ›") → Performance; then settings/account.
- Top bar: week selector "2026 · Week 6" (arrows step a week; label opens season/week list back to 2014), "Search teams ⌘K", "Updated Thu 9:02 PM ET", alerts bell (unread count badge; none when all read).
- Mobile: top bar (sport · week → sheet · search), bottom tab bar with 5 tabs: This Week, Picks, Contest, Rankings, More (Teams, Performance, Lab, Settings). Active = filled pill behind icon + weight.
- Command palette (⌘K): before typing — recent teams + screen jumps; typing — Teams / This week's games / Screens; arrow keys + enter; desktop dialog 560 wide, mobile full-screen sheet.

**Feedback**
- Skeletons drawn at the exact loaded size: nav, titles, tabs, chips, column headers stay real; every DB value becomes a bar. Chart areas become one solid block. After 1.5s with no data, show "Waking up the database…" note (not an error).
- Empty: dashed frame, no illustrations, says which rule produced emptiness + what's next.
- Error: say what failed, what you're seeing instead, when it retries; stale data = neutral banner ("Lines last updated Thu 9:02 PM ET · Refresh"). Single failed panel keeps its title and size ("Couldn't load unit stats … try 1 of 3 · Retry · Details").
- Toast ("Pick saved · OU +7 · Locks at kickoff, Sat 7:30 PM ET · Undo"), error toast, tooltip.

**Charts** (Recharts) — axes 12/16 muted, signed tabular ticks; only zero baseline drawn (`--input`); horizontal gridlines 1px `--border`, no vertical grid; dashed crosshair on hover. Reference lines 1.5px `--breakeven`, dash `6 3`, labelled at right end in ink ("Break-even 52.4%"). **Live = 2px solid + filled markers; Backtest = 2px dash `6 4` + hollow markers + "Backtest" label, never summed into live numbers.** Series colors `--chart-1…5` in order; `--pos/--neg` only for signed outcomes; `--edge` only for edge side. Direct end labels instead of legends (≤3 series). Tooltip = elevation 2, 12/16, title 600, 12px from cursor, flips at edges, also on focus. Charts: cumulative units, calibration (dotted perfect diagonal, overconfidence gaps), win % by edge bucket (y-axis starts at 50%, stated), you vs model, distribution curve with shaded cover area, waterfall drivers, percentile bars, sparklines, prior-decay curve, importance bars.

---

## Screens
All desktop screens: 1440 wide, grid `224px minmax(0,1fr)` (sidebar + main). Main column = top bar, then page title row, then content. Column grids below are copied from the files (verify mapping in the file).

### 1. This Week (home) — `This Week.dc.html` → `This Week Desktop` / `This Week Mobile`
Props/states: `view` slate|best · `markets` spread|total|both · `filter` all|picks|starred · `noStars` · `alertsEmpty` · `wxTip` · `density` compact|comfortable · `alertsOpen` (mobile: `wxOpen`, `sheet`).
- Header: "This Week" + "2026 · Week 6 · 54 games · 9 picks"; LiveRecordStrip under it.
- Tabs: Slate | Best lines (count). Filter chips: All / Picks only / FBS vs FBS / Starred (count) / Conference / Window / Ranked. Markets segmented: Spread / Total / Both. Sort menu (kickoff, edge, confidence).
- Slate table grid: `24px 100px minmax(0,1fr) 388px 92px 32px 76px 160px 16px` → star · Kickoff ET · Matchup · number band (open→ Market | Model | Edge — light grey band) · Cover % · Tier · Win % · Pick·result · chevron. Rows grouped by day/time window. Row click → Game Detail.
- Footer legend: "Edge pill = clears 2.5 pts · Tier A ≥ 5.0 · B ≥ 3.5 · C ≥ 2.5 · Market = opening line, its moves, then now".
- Best lines view: every spread/total clearing 2.5, ranked by cover %, written as the bet ("MISS +3.5"); grid `28px 160px minmax(0,1fr) 112px 168px 64px 100px 112px 28px 24px` (# · Bet · Matchup · Kickoff · Market·Model · Move · Edge · Cover % · Tier · chevron). Started games drop to "Already kicked off" section. Ties broken by edge. Note: cover % is vs current market line.
- Starred empty: "No starred games this week — Star a game from its row, Game Detail or Contest…" + "Show all 54 games".
- Alerts popover from bell (see §10).
- Mobile: game cards, chips scroll sideways, filters & sort in bottom sheet, weather tap-to-open.

### 2. Contest (pick'em) — `Contest.dc.html` → `Contest Desktop` / `Contest Mobile`
Props: `frame` empty|parse|slate|tray|results|settings · `now` thu|fri. Default rules = Splash preset: 4 picks/week, CFB+NFL, each game locks at kickoff, 1 pt per correct, push 0.
- **Empty:** large "Paste from Splash" textarea is the hero; "Add game manually" secondary.
- **Parse preview:** raw paste (mono) beside parsed rows; skipped lines dimmed; clicking a row jumps to its source lines; unmatched rows highlighted first with team picker ("Hou Texans" @ "Jax" → pick Houston Texans) — Confirm disabled until resolved. Splash text format: one value per line (day headers, team names / NFL nicknames, "Preview / Sun 1:00pm", records, each side's spread, O/U) — see `design/sample-splash.txt` and `contest-data.js`.
- **Ranked slate:** sorted by cover % vs the **contest's** line; visible cutoff line under #4. Row: sport tag (CFB/NFL), matchup, contest line, market line beneath with ≠ chip when different (blue if contest gives ranked side a better number, orange if worse), model line, edge, cover %, kickoff + lock countdown, two side buttons ("TEX −7" / "OU +7") — tap to pick, tap again to clear, tap other to switch; purple dot marks model's side. NFL: "No model yet", ranked on contest-vs-market gap with ~market-implied %. Locked rows greyed with hatched "Picks closed" block.
- **Pick tray:** desktop persistent right panel (~380px); mobile bottom bar → bottom sheet. "Your picks: 2 of 4"; each pick shows line locked at + when; matches to model rank noted; open slots offer the model's next pick; "Use the model's top 4" fills all.
- **Results & standing:** scoreboard you vs model's top 4 (pts), season + by week, league standing entered by hand (Edit).
- **Rules (desktop only):** sports, picks/week, lock rule, scoring, push rule; Splash preset — editing any rule switches to "Custom".
- Target flow: paste → 4 picks in 7 taps (or 4 with "Use the model's top 4").

### 3. Game Detail — `Game Detail.dc.html` → `Game Detail Desktop` / `Mobile`
Props: `showMath` · `drivers` waterfall|bars · `weather` forecast|dome|none. Sample: #2 Texas vs #4 Oklahoma, neutral (Dallas), Sat 2:15 PM, 5h before kickoff.
- Header: teams, ranks, records, kickoff, venue, weather line (84°F · wind 7 mph · rain 5%; dome / no-data states), star button, "Show the math" toggle.
- **The Number** panel above the fold: market (open → current + sparkline), model, edge (large pill), cover %, win %, tier, "picked at". Number line below showing edge as a literal gap between model and market margins.
- **Prediction drivers** waterfall: each bar starts where the previous ended, running total, lands on model margin (+3.8 −2.4 −1.6 … = +1.3). "Helps OU / Helps TEX" side chips, team chip per row, bars neutral color. Alt "Bars" view.
- **Unit matchup:** each offense vs the defense it faces, FBS percentile bars.
- **Projected margin distribution:** bell curve, market line marked, cover area shaded+hatched, then a 46/17/37 stacked bar (OU wins / TEX wins but doesn't cover / TEX covers).
- Line movement card (step chart), recent form (last 5 ATS), head-to-head.
- Every chart has a plain-English caption; Show the math adds formulas (Σ drivers, Φ(edge/σ), calibration note).
- Desktop grid `minmax(0,1fr) 380px` (main + right column).

### 4. Rankings + Season Outlook — `Rankings.dc.html` → `Rankings Desktop` / `Mobile`
Props: `tab` power|outlook · `machineOpen` (mobile `sheet`). Tabs: Power · Season Outlook · History (disabled, "LATER").
- Power table (same row grammar as slate, grey number band): Rk · Δ · Team (chip, conference, record) · Rating · trend sparkline · Off (rk) · Def (rk) · SOS · Next game with model spread (edge pill + tier if a pick). Conference chips; FBS default. Sortable headers.
- Time machine "Ratings as of": step weeks or open season × week picker back to 2014; labelled "no hindsight"; past week shows banner + "Back to latest".
- Outlook: current record, projected record, win-distribution histogram (shared scale, labelled), P(conf title game), P(conf title) as odds cells (no color meaning).

### 5. Team page — `Team Desktop` / `Team Mobile` (in Rankings board)
Ohio State sample. 3px accent bar + logo dot only. Header record SU + ATS, rank, rating. Rating trajectory chart (overall/off/def, hover by week). Schedule table with market, model, result, ATS ✓/✗. Unit profile percentile bars. Preseason vs now. "Path to the playoff": win distribution + two swing games. Preseason empty state (only trajectory empty) in Empty & Error board.

### 6. Picks — `Picks - Performance.dc.html` → `Picks Desktop` / `Mobile`
Props: `tab` current|best|past · `source` both|splash · `calibration` uncalibrated|calibrated (mobile `sheet`).
- Record strip: season ATS W-L-P, win % vs 52.4% break-even (dashed tick / ± bar), units, ROI, avg CLV.
- Current: picks sorted by tier/edge; each shows picked-at line + time, line now, CLV so far (final after kickoff), status; edge/cover note how they moved. Filters: tier, conference, fav/dog, home/away.
- Best lines: one row per game using whichever source (Splash/market) gives higher cover %; other source alongside; dashed threshold line; source chips Splash + Market / Splash only.
- Uncalibrated state: header badge, dotted underline on every cover %, banner quoting backtest (62.5% predicted, 58.9% hit).
- Past weeks: one row per week, expandable (Week 5 expanded).

### 7. Performance — `Performance Desktop` / `Mobile`
Props: `scope` season|all · `compare` · `versionOpen` · `hover`.
KPI tiles (win % with 95% range, units, ROI, CLV, #picks) — live; backtest in dashed outline with BACKTEST tag + hatched fill, never mixed. Cumulative units chart (live solid, backtest dashed). Win % by edge bucket (7.0+ dip stays visible). Calibration with red overconfidence gap lines + table. Breakdowns by tier, week, conference, fav/dog with ± bars centred on 52.4%. Model version selector; compare vs v1.1 (candidate).

### 8. Model Lab — `Model Lab.dc.html` → `Lab Desktop` (hi-fi) / `Lab Wireframes` (lo-fi). Desktop only.
Props: `view` weights|versions|compare; wireframe `screen` builder|promote, `run` idle|queued|running|done|failed.
- "7 variants tried" overfitting counter in the Lab header on every tab (hero on Versions, "this run will be #8" in Builder, acknowledgement checkbox in Promote).
- Weights: each setting/weight = name, spec key (mono), value, plain-English meaning ("+0.1 EPA/play ≈ +3.1 pts"); labelled Tuned vs Set by hand; prior-decay curve + input importance bars share grey for "preseason guess".
- Versions: status (dev/candidate/production/retired), parent, created, headline metrics.
- Compare: one-line verdict first ("better on every metric and proves nothing"), delta cards with noise range; v1.0 grey circles, v1.1 blue squares in every chart; games they disagree on most.
- Builder (lo-fi): sections Inputs, Hyperparameters, Home field, Prior, Distribution, Pick rules; each weight a Fit-from-data / Fixed [value] toggle; Run backtest → queued → running → done/failed.
- Promote (lo-fi): go/no-go checklist (MAE vs closing, ATS vs closing, calibration, consistency across seasons) pass/fail.

### 9. Watchlist & Alerts — `Watchlist - Alerts.dc.html` → `This Week Desktop` (alertsOpen), `Settings Desktop`, `Alerts Mobile`
Bell with unread badge. Panel newest first: game, time, what changed, new edge + tier, delivery channel; item opens game; footer repeats snapshot-lag note + settings link. Settings → Alerts: delivery email|push; rules "edge crosses pick threshold" (all games default, scope menu All / Starred) and "line moves ≥ N pts" (default **1.0 pt**, half-point stepper, starred games). State plainly that alerts follow the line-snapshot schedule and can lag hours.

### 10. ⌘K, Login, Settings — `Palette Login Settings.dc.html` → `Command Palette`, `App States Desktop/Mobile`
Login: GitHub OAuth only, one allowlisted account (no password, sign-up or reset). States: default ("Sign in with GitHub"), waking the database (button reads "Waking up the database…"), and "This GitHub account isn't allowed" with "Use a different account". Settings nav on every frame: General · Contests · Alerts · Account. General: theme, default contest, time zone ("Use this device's time zone" toggle; off → picker with live preview time). Contests: your contests with platform + rules summary, default marker, link to each contest's Rules. Account: GitHub username + avatar, Sign out. Boards: `Pass A - Decisions.dc.html`.

### 11. Loading / Empty / Error — `Loading States.dc.html`, `Empty and Error States.dc.html`
Skeletons for This Week, Contest, Game Detail, Rankings, Performance (tweaks `showLoaded` overlay to check fit, `reducedMotion`). Empty: off-season (filters hidden, sidebar shows final record), no picks this week (record stays, 3 games nearest threshold listed as not picks), contest no slate, team preseason. Error: API unreachable (frame stays, filters dimmed, auto-retry with backoff, Details), one panel failed (Game Detail unit matchup).

---

## Interactions & behavior (summary)
- Row/card is the single hit target (pills/badges have no own hover). Row hover `--accent`; focus 2px ring.
- Clicking LiveRecordStrip toggles Picks-only; stars feed Starred filter + alerts.
- Contest side buttons: toggle/switch; locked games unpickable at kickoff; lock countdown live.
- Tooltips 300ms delay, also on focus. Toasts 5s, pause on hover, Undo on pick saves.
- Week selector arrows step; label opens list. Time machine steps/picker.
- Skeleton → data with zero layout shift; wake-up note after 1.5s.
- Mobile: sheets (radius 12) for filters/sort, week picker, time machine, pick tray, ⌘K.

## State / data
Per screen (server components + client islands): season/week (URL), filters/sort/view (URL search params), starred game ids (persisted), contest slate + parsed rows + user picks (persisted, picks store line + timestamp at pick time), alert rules + read state, theme + time zone, model version selection. Data shapes: see `designs/*-data.js` (`window.TW`, `window.CT`, etc.) — these mirror `design/sample-data.md` and are good fixture seeds. Expect slow first query (DB cold start) — every data view needs its skeleton.

## Assets
- Icons: lucide (loaded from unpkg in mocks → use `lucide-react`): calendar-days, target, trophy, list-ordered, shield, activity, flask-conical, chevrons-up-down, chevron-right, lock, star, bell, search, cloud/wind/rain weather icons.
- Fonts: IBM Plex Sans / Mono (Google Fonts).
- Team logos: not supplied — mocks use a team-color dot (max 20px). Team colors live in the data files. Real logos (e.g. from CFBD) drop into the same slot.
- No other imagery.

### 12. Teams index (S-17) — `Teams Desktop` / `Teams Mobile` (Pass B)
Props: `state` default|conf|search|empty · `query`. Every FBS team in the Rankings row grammar: Team · Conf · Record · Rating (rank) · Next game · model line (edge pill + tier only for picks). Search filters by name as you type with a match highlight; conference chips single-select; both stack. Row opens the team page. Loading = skeleton; empty = "No teams yet" (before the first data sync); no-match empty with Clear filters. Mobile reached from More › Teams.

### Props added 2026-10-07 (states on the Pass C boards)
- `This Week Desktop/Mobile`: `week` live|noLines|bestEmpty · `stale` · (desktop) `alertsState` one|many|loading|error. `This Week Tablet` (768): priority columns.
- `Contest Desktop`: `pasteError` none|unparsed|nomatch · `repaste` · `now` thu|fri|sun (sun = every game locked).
- `Game Detail States`: `layout` desktop|mobile · `game` texou|furclem|minw · `status` upcoming|live|final (header + The Number).
- `Rankings Desktop/Mobile`: `conf`. `Team Desktop/Mobile`: `phase` none|sims|cfp.
- `Picks Desktop/Mobile`: `empty`. `Performance Desktop/Mobile`: `noLive`; mobile `screen` summary|detail.
- `Lab Desktop`: `noVersions`. `Alerts Mobile`: `screen` adds history|loading|error. `Command Palette`: `firstUse`.
- `App States Desktop/Mobile`: `loginState` default|waking|denied · `section` general|contests|account · `saveError`; mobile `frame` adds more.

## Files
- `screenshots/` — 2x PNGs of every screen's default state, dark mode. 01–21 from the original handoff; 01, 03, 05, 07, 09, 11, 13, 15, 17 and 19 re-captured 2026-10-07 (Settings nav, ⌘K data, 12px keycaps). New: 22 Login desktop, 23 Login mobile (GitHub only), 24 Settings › General desktop, 25 Teams desktop, 26 Teams mobile, 27 More mobile, 28 This Week tablet 768. Mobile shots are full scroll length without the tab bar. Other states live in the boards.
- `tokens/tokens.css` — production-ready CSS variables (light/dark). `tokens/tokens.json` — token notes + contrast checks.
- `designs/CFB Design System.dc.html` — design-system board (Color Tokens, Foundations, Components, Market Extras, Charts, Specimen, Review Checks; dark + light side-by-side).
- `designs/This Week.dc.html`, `Contest.dc.html`, `Game Detail.dc.html`, `Rankings.dc.html`, `Picks - Performance.dc.html`, `Model Lab.dc.html`, `Watchlist - Alerts.dc.html`, `Loading States.dc.html`, `Empty and Error States.dc.html`, `Palette Login Settings.dc.html` — screen boards with annotated states.
- `designs/* Desktop.dc.html`, `* Mobile.dc.html`, `Command Palette`, `Settings Desktop`, `Alerts Mobile`, `App States *` — individual screens. Each carries a `<style id="dc-token-fallback">` with the dark token set on `:root` so it renders standalone; inside a board, the board's wrapper vars (dark or light) take precedence. Mock-only — in the app, load `tokens/tokens.css` once.
- `designs/Review Checks.dc.html` — accessibility/consistency audit board.
- `designs/*-data.js` — sample data; `support.js` — runtime needed only to view the mocks.
- `designs/This Week Wireframe.dc.html` — superseded, reference only.
- `designs/Pass A - Decisions.dc.html` — frames changed or added after the 2026-10-06 handoff (Login, Settings, Team phases, More menu, Teams index, missing states, light frames). Where it disagrees with an older board, it wins.
- `sample-data.md`, `sample-splash.txt` — at the bundle root, i.e. `design/sample-data.md` and `design/sample-splash.txt` in the repo.
- New screen files: `Teams Desktop`, `Teams Mobile`, `This Week Tablet`, `Game Detail States`.
