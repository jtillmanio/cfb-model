# 01 — Product Vision & Features

## What we're building

A personal sports-analytics app. It starts with college football (CFB) and has four jobs:

1. **Predict games.** Give every FBS game a projected margin, total and win probability.
2. **Find edges against the line.** Compare our numbers to point spreads (the market's, and your pick'em contest's) and recommend picks where we disagree enough to matter.
3. **Rank teams and project seasons.** Publish our own power ratings (overall, offense, defense) every week, with history back to ~2014, plus projected final records and playoff odds. Later, rank whole seasons, programs and coaches across history.
4. **Keep score honestly.** Track every pick the model makes at the line it was made against, so we always know whether the model is actually good.

Later the same engine extends to other sports, NFL first since its data and market structure are the closest match.

## Who it's for

For now there's one user: you. You play a weekly against-the-spread pick'em in a Splash Sports work league (4 picks a week from that week's college *and* NFL games, each line locking at its game's kickoff, 1 point per correct pick). You make your picks late in the week and don't currently bet at a sportsbook. The app is private, behind a login, and cheap to run. Design choices like the `sport_id` column, the model-version registry and the users table keep the door open to more users later, but we won't build for that until there's a reason to.

## Guiding principles

- **Built general, defaulted to how you play today.** The Splash league is the default, not the design center. Contests are a generic concept (any platform, any rule set, with Splash as the first preset), and the model and market features stand on their own for sportsbook-style use. Priorities reflect current usage, but the data model never assumes it.
- **Point-in-time honesty.** A prediction for a game may only use information that was available before kickoff. This holds in backtests as well as live. It's the most common way sports models fool their builders, and the architecture enforces it.
- **The market is the benchmark.** The closing line is the toughest opponent there is. A model that can't get close to "just use the closing line" on accuracy should be trusted only where it selectively disagrees, and only once we've proven that disagreement wins.
- **Explainable over clever.** You're learning modeling, so every model step should be inspectable, down to its weights: why does the model like Team A by 6? We start simple and add complexity only when a backtest shows it pays.
- **Version everything.** Models, ratings and predictions are immutable and tagged with a model version, so we can compare v1 against v2 (or your own custom model) on exactly the same games.

## Feature set

Priorities: **MVP** is the first usable app (end of Phase 4). **Next** follows soon after. **Later** is the long-term direction.

### Predictions & picks
| Feature | Priority | Notes |
|---|---|---|
| Weekly slate: every game with model spread vs market spread, edge, cover probability | MVP | The home screen |
| Pick recommendations: games where the edge clears a threshold, with confidence tiers | MVP | Thresholds are tuned in the backtest, not guessed |
| **Contest mode (pick'em):** load a contest's slate and lines, and the model ranks the games against the *contest's* lines and recommends your picks under that contest's rules | MVP | Generic contest rules (picks per week, sports, lock rule, scoring) with a **Splash preset** as the default. Slates load by pasting the contest page's text |
| Contest vs market line comparison | MVP | Flags where the contest's line differs from consensus, even for games the model doesn't cover yet (e.g. NFL before Phase 8) |
| Game detail: matchup breakdown (unit vs unit), prediction drivers, line history | MVP | "Why does the model like this?" |
| **Line movement:** opening → current line with a small trend sparkline on every slate row, full history on game detail | MVP | Built from our own `line_snapshots`, so the trend is only as fine-grained as the `lines` job (a few points a week). Past seasons have open and close only |
| **Best lines board:** every upcoming game ranked by the model's cover probability against the best line available to you, one row per game | MVP | Picks the better of the market and contest lines and tags which one it is. Shows games below the pick threshold too, under a cutoff line. Cover % is labeled *uncalibrated* until the backtest shows predicted % matches actual hit rates ([04-model.md §5](04-model.md)) |
| **Weather flag** on outdoor games: wind, rain/snow, extreme cold | Next | Open-Meteo forecasts by venue; domes never flagged. Information only until the totals model uses it |
| Model track record: ATS record, ROI, by season / edge bucket / conference | MVP | Every pick graded automatically |
| Closing line value (CLV) on every pick | Next | The best early signal of whether a model is sharp |
| Totals (over/under) model and picks | Next | Pace × efficiency, plus weather |
| Moneyline / win probability edges | Later | Less useful without a sportsbook |
| Manual adjustments: e.g. "starting QB out, −4 pts" | Next | Applied as an override layer, with an audit trail |
| **Watchlist & alerts:** star a game; get notified when its edge crosses the pick threshold or its line moves | Next | Email or web push. Checked by the `lines` job, so alerts arrive hours after a move, not minutes |
| Multi-book odds (which sportsbook has the best number) | Later | Lower value since you don't use a sportsbook; CFBD consensus lines cover us |
| Game simulation (simulating each game thousands of times) | Later (research) | See [04-model.md §3](04-model.md): it adds value only if it simulates game structure (drives), not just a bell curve |

### Rankings, teams & season outlook
| Feature | Priority | Notes |
|---|---|---|
| Power rankings: overall, offense, defense ratings and rank movement | MVP | Our model's view |
| Team page: rating trajectory over the season, schedule with predictions, unit profile | MVP | |
| Historical rankings: browse any season and week since ~2014 | MVP | Falls out of the backtest |
| **Projected final records:** expected wins and the full win distribution | Next | Monte Carlo over the remaining schedule, cheap once ratings exist |
| **Conference title odds:** who makes the title game, and who wins it | Next | Same simulation, plus conference tiebreakers |
| **CFP odds:** making the 12-team field, seeding, winning the title | Later | Needs a model of how the committee selects, which is the hard part |
| Compare against SP+, FPI and Elo (CFBD provides these) | Next | A sanity check and a fun view |
| Hypothetical matchup tool: any two teams at any site | Next | "Who wins, 2026 Ohio State vs 2019 LSU?" |
| Win totals vs market season win totals | Later | Preseason feature |

### History: seasons, programs & coaches
Built after the betting model (Phase 6). See [04-model.md §7](04-model.md).
| Feature | Priority | Notes |
|---|---|---|
| **Season final rankings** for any past season: best team (hindsight rating) and best résumé (strength of record), side by side | Later | Hindsight ratings use the whole season, so they're a separate kind that predictions can never read |
| **Program rankings** over any span of seasons: average rating, peak, worst, top-10 finishes | Later | Aggregates of season-final ratings |
| **Coach rankings:** value over expectation (how much better their teams played than the preseason prior predicted), with and without crediting recruiting | Later | Needs coach tenures, including mid-season changes and interim coaches |
| Coach page: career by stop, season-by-season value added, ATS and close-game records | Later | |
| Cross-era scale: within-season percentile next to the raw rating | Later | Scoring environments change, so raw points don't compare cleanly across decades |
| Deeper history before ~2014 (start year to be decided) | Later | Efficiency stats only exist from about the mid-2000s; earlier seasons use a scores-only rating, labeled as such |

### Tracking
| Feature | Priority | Notes |
|---|---|---|
| **This week's record:** a strip showing picks graded as games finish (e.g. "3-1 so far, 2 live"), for the model's picks and your contest entries | MVP | Grading is already a view; this needs a Saturday score refresh. Near-live (GitHub cron can start 10–30 min late). Contest records count points, not units |
| Contest tracker: your actual Splash picks, weekly results, league standing | Next | Kept separate from model picks: compare "you" vs "the model" |
| Bet tracker for sportsbook bets | Later | Only if you start betting |

### Model lab (for you as the builder)
| Feature | Priority | Notes |
|---|---|---|
| **View model weights:** the fitted coefficients and settings behind the production model and any version (e.g. "1 point of EPA/play = X points", home field = 2.3, how fast the preseason prior fades) | Next | Read-only, with plain-English labels |
| Model versions and backtest reports, comparable side by side | Next | Starts as CLI and notebook output and moves into the UI |
| Calibration charts: do 60% picks hit about 60%? | Next | |
| **Model builder:** clone a model, choose its inputs, set or fix weights and hyperparameters, run a backtest from the UI, compare it with production, and promote it if it passes the gates | Later | Models are config-driven from day one so this is possible (see [04-model.md §6](04-model.md)) |
| Plain-English pick write-ups from Claude | Later | Claude API summarizes the drivers |

### Multi-sport
| Feature | Priority | Notes |
|---|---|---|
| NFL | Later | nflverse data; same rating framework |
| College basketball | Later | CBBD (same author as CFBD) |

## What "good" looks like

Sports lines are very efficient, so we need to know up front what success means.

- **Pick'em contest (your main use):** there's no vig, so anything above **50%** against the spread is beating a coin flip. Winning the league means beating your coworkers' records, and 55%+ over a season is a very good year. With only 4 picks a week (~60 a season), luck dominates any single season, so judge the model on its full slate of recommendations, not just your 4.
- **Sportsbook break-even (for reference):** at −110 you must win **52.38%** to break even. Above ~54–55% over hundreds of bets is genuinely good. Anyone claiming 60%+ long-term is mostly showing variance.
- **Accuracy:** the closing line's mean absolute error (MAE) on CFB margins is roughly 12–13 points (we'll measure the exact figure in Phase 2). Matching it would be excellent. We don't need to beat it everywhere; we need to be right *when we disagree*.
- **CLV:** if our picks consistently beat the closing number (we take −3 and the game closes −4.5), the model is probably finding real signal, even before win/loss results stabilize.
- **Sample size:** a CFB season gives maybe 60–150 qualifying picks. One season can't prove anything, which is why the multi-season backtest matters so much.

## Non-goals (for now)

- Live/in-game betting and props
- Automated bet placement
- Public or multi-user features, payments, social features
- Real-time play-by-play (CFBD's paid GraphQL tier has it; we don't need it)
- Injury data: there's no free structured CFB injury feed. You track injuries yourself and, once manual adjustments exist, enter the ones that matter as an adjustment ("QB out, −4 pts")

## Responsible-use note

This is an analytics tool, not a guarantee. The design keeps model picks and your real picks separate and puts honest performance tracking first-class, so the app tells you the truth about whether the model is working.

## Feature index (IDs, priorities, outcomes)

_Added 2026-10-07 when the Claude Code starter kit was adopted. The tables above stay as written. This index gives each feature a stable ID (F-01…) for task files, and it wins where the two differ: CLV (F-10), the contest tracker (F-33) and calibration charts (F-37) moved from Next to MVP, and four app-level features from the design handoff were added (F-42 to F-45). Screen IDs (S-01…) are defined in [05-ui-design-brief.md › Screen inventory (from handoff)](05-ui-design-brief.md#screen-inventory-from-handoff). Phase numbers refer to [06-roadmap.md](06-roadmap.md)._

Outcomes use the 2026 Week 6 fixture (`design/sample-data.md`, seeded as described in [02-architecture.md › Testing strategy](02-architecture.md#testing-strategy)), so each value matches what the reference screenshots show. "Now" is fixed per screen: the slate, Picks and Game Detail at Sat 10/10 2:15 PM ET, Contest and Best lines at Thu 10/8 10:00 PM ET unless stated.

| ID | Feature | Priority | Phase | Screens |
|---|---|---|---|---|
| F-01 | Weekly slate | MVP | 4 | S-01 |
| F-02 | Pick recommendations with confidence tiers | MVP | 3 (logic) · 4 (UI) | S-01, S-07 |
| F-03 | Contest mode (pick'em, Splash preset) | MVP | 4 | S-02 |
| F-04 | Contest vs market line comparison | MVP | 4 | S-02, S-07 |
| F-05 | Game detail: The Number, drivers, unit matchup, distribution | MVP | 4 | S-03 |
| F-06 | Line movement | MVP | 4 | S-01, S-03 |
| F-07 | Best lines board | MVP | 4 | S-01, S-07 |
| F-08 | Weather flag | Next | 5 | S-01, S-03 |
| F-09 | Model track record | MVP | 3 (views) · 4 (UI) | S-07, S-08, S-16 |
| F-10 | Closing line value (CLV) on every pick | **MVP** (was Next) | 3 (view) · 4 (UI) | S-01, S-07, S-08 |
| F-11 | Totals model and picks | Next | 7 | S-01 (Spread / Total / Both) |
| F-12 | Moneyline / win-probability edges | Later | — | — |
| F-13 | Manual adjustments | Next | 5 | S-03 (drawn disabled, "Coming later") |
| F-14 | Watchlist & alerts | Next | 5 | S-01, S-02, S-03, S-11, S-12 |
| F-15 | Multi-book odds | Later | 7 (optional) | — |
| F-16 | Game simulation (drive-level) | Later (research) | 7 | — |
| F-17 | Power rankings | MVP | 4 | S-04 |
| F-18 | Team page | MVP | 4 | S-06 |
| F-19 | Historical rankings (any season and week since 2014) | MVP | 4 | S-04 |
| F-20 | Projected final records | Next | 5 | S-05, S-06 |
| F-21 | Conference title odds | Next | 5 | S-05, S-06 |
| F-22 | CFP odds | Later | 7 | S-06 (CFP % hidden until Phase 7) |
| F-23 | Compare against SP+, FPI and Elo | Next | 5 | not designed |
| F-24 | Hypothetical matchup tool | Next | 7 | not designed |
| F-25 | Win totals vs market season win totals | Later | — | — |
| F-26 | Season final rankings (hindsight and résumé) | Later | 6 | not designed |
| F-27 | Program rankings | Later | 6 | not designed |
| F-28 | Coach rankings | Later | 6 | not designed |
| F-29 | Coach page | Later | 6 | not designed |
| F-30 | Cross-era scale | Later | 6 | not designed |
| F-31 | Deeper history before ~2014 | Later | 6 | not designed |
| F-32 | This week's record strip | MVP | 4 | S-01, S-02, S-07 |
| F-33 | Contest tracker: your entries, results, league standing | **MVP** (was Next) | 4 | S-02 |
| F-34 | Bet tracker | Later | — | — |
| F-35 | View model weights | Next | 5 | S-09 |
| F-36 | Model versions and backtest reports side by side | Next | 5 | S-08 (version compare), S-09 |
| F-37 | Calibration charts | **MVP** (was Next) | 2 (data) · 4 (UI) | S-07, S-08 |
| F-38 | Model builder | Later | 7 | S-10 |
| F-39 | Plain-English pick write-ups from Claude | Later | 7 | — |
| F-40 | NFL | Later | 8 | S-16 (sport switcher) |
| F-41 | College basketball | Later | — | — |
| F-42 | Sign-in (single user, GitHub) | MVP (added) | 0 | S-15 |
| F-43 | ⌘K command palette: teams, this week's games, screens | MVP (added) | 4 | S-14 |
| F-44 | Teams index (destination of the Teams nav item) | MVP (added) | 0 (skeleton) · 4 | S-17 |
| F-45 | Settings › General: theme, default contest, time zone | MVP (added) | 4 | S-13 |

### Observable outcomes for MVP features

**F-01 Weekly slate**
1. This Week shows the header "This Week · 2026 · Week 6 · 54 games · 9 picks" and groups rows under day/time windows ("FRI NIGHT", "SAT NOON", "SAT AFTERNOON", "SAT NIGHT"). Clicking a row opens that game's Game Detail.
2. Each row reads Market → Model → Edge left to right. Purdue @ Ohio State shows "OSU −27.5", "OSU −31.2", a filled "+3.7 OSU" pill, "59%", tier "B" and "OSU 99%". Kansas State @ Utah shows "+0.6 UTAH" as plain muted text with no tier.
3. Row states render as designed: final ("Final", scores 24 / 31, "✓ No pick · UNLV covered"), live ("Q3 9:12" with a live dot and mono scores), no line (Furman @ Clemson: "No line", "FCS · no lines yet") and neutral site ("N · Dallas"). At 390 px each game is a card showing Market, Model and Edge without expanding, with no horizontal scroll.

**F-02 Pick recommendations**
1. A game is a pick only when its edge and cover probability clear the active model version's pick rules. v1.0's spec gives min edge 2.5, min cover 55% and tiers A ≥ 5.0 · B ≥ 3.5 · C ≥ 2.5. The UI reads these from the spec, never from constants. Texas vs Oklahoma is tier A, Ole Miss @ LSU is B, Notre Dame @ Stanford is C, and the week has 9 picks.
2. Picks › "Week 6 · 9" lists picks sorted by tier, then edge. Each row shows Picked at, Now, CLV, Edge now and Cover. For example: "MISS +2.5 · Picked at +2.5, Sun 6:10 AM · Now ↔ +3.5 moved · CLV +1.0 so far · +4.9 MISS, at pick +3.9 MISS · 62%, was 60%".
3. Picks are immutable. When a line moves, the original pick keeps its "Picked at" line, and any re-evaluation is stored as a new pick row.

**F-03 Contest mode**
1. With no slate loaded, the Contest page's hero is the "Paste from Splash" area. Pasting the Week 6 page text shows the raw text beside the parsed rows with "9 rows match · 1 unmatched". Confirm stays disabled until "Hou Texans" @ "Jax" is mapped to Houston Texans @ Jacksonville, and that mapping is saved as a team alias.
2. The ranked slate orders games by cover % against the contest line and draws a "MODEL'S TOP 4" cutoff under #4: Texas vs Oklahoma 64% (OU +7), Ole Miss @ LSU 61%, Purdue @ Ohio State 60%, Colorado @ BYU 59%. Beside the cutoff it reads "Next best #5 ND −17.5 · 55%".
3. One tap on a side button adds a pick, and the tray reads "Your picks 2 of 4". Each pick shows when its line was locked in: "Locked in at OU +7 · Thu 9:14 PM" and "BUF −3 · Thu 9:20 PM". After kickoff, UNLV @ Boise State shows "Picks closed", and the API rejects a new or changed entry for that game.

**F-04 Contest vs market line comparison**
1. When the contest line differs from consensus, the market line sits under it with a ≠ chip: "TEX −7 / mkt −6.5 ≠ OU +0.5" (blue: better for the ranked side) and "LSU −3 / mkt −3.5 ≠ LSU +0.5" (orange: worse).
2. NFL games show "No model yet" and are ranked on the gap alone: Buffalo @ NY Jets reads "1.5 pts off mkt → BUF" and "~54% mkt-implied".
3. The "Line ≠ market" filter chip counts the differing rows ("Line ≠ market 7") and filters to them.

**F-05 Game detail**
1. The Number panel sits above the fold at 1440 and 390 and shows Market "TEX −6.5" (opened TEX −7, with a sparkline), Model "TEX −1.3", Edge "+5.2 OU" with tier A, Cover "63%", Win "TEX 54% · OU 46%" and "Picked at OU +6.5 · now OU +6.5 · CLV 0.0".
2. The prediction-drivers waterfall carries a running total and lands on the model margin: +3.8, −2.4, −1.6, +0.9, +0.4, +0.2, 0.0 → "Model margin +1.3 TEX".
3. Projected margin shows a curve with σ 13.8, the caption "Oklahoma covers in 63% of outcomes" and a 46% / 17% / 37% split bar. Unit matchup shows percentile bars, e.g. "TEX offense 96th" against "OU defense 58th" for passing.

**F-06 Line movement**
1. The slate's Market cell shows the opening line and a sparkline, muted, before the current line ("−28 ⟍ OSU −27.5"). An unchanged line shows a flat line ("−9 — MICH −9"). A game with no line shows no opener.
2. Game Detail's Line movement card is a step chart through every snapshot (Sun −7 → Tue −6.5 → Thu −6 → Sat −6.5) with a kickoff marker. A past season's game shows only two dots, open and close, joined by a dashed line and labeled as such, not as an error.

**F-07 Best lines board**
1. Best lines lists upcoming CFB games, one row per game, ranked by cover %, each written as the bet. #1 is "OU +7", tagged Splash, 64%, with "Market OU +6.5 (63%)" alongside. #2 is "MISS +3.5", tagged Market, 62%.
2. A dashed "Pick threshold · edge ≥ 2.5" line separates #6 Iowa from #7 Kentucky. Choosing the "Splash only" chip drops Iowa, Kentucky, Northwestern and Utah, and #2 falls back to "MISS +3" (61%).
3. Until the calibration check in [04-model.md § 9](04-model.md#9-evaluation-protocol-fixed-2026-10-07) passes, every cover % carries the "UNCALIBRATED" badge and a dotted underline, and a banner quotes the backtest ("62.5% predicted, 58.9% hit").

**F-09 Model track record**
1. The Picks record strip and the Performance KPI tiles show the live 2026 record: "31-24-1", "56.4%" with a break-even tick at 52.4% and "95% range 43–70%", "+4.6u", "+7.6%" ROI, "+0.9 pts" avg CLV, and "56" picks.
2. Backtest numbers appear only inside a dashed "BACKTEST" frame ("Validation 2016–2023 · 54.1% · 1,184 picks"; "Holdout 2024–2025 · 53.2% · 263 picks") and are never added into live totals.
3. Breakdown tables show tier, week, conference and favorite/underdog. For example, tier C reads "12-12 · 50.0% · −1.2u". Results come from the `pick_outcomes` and `model_record` views; there is no grading job.

**F-10 Closing line value**
1. Every pick shows CLV in points against the line it was picked at. Ole Miss reads "Picked at −2.5 → now −3.5 · CLV +1.0 · moved our way". Before kickoff it's labeled "so far"; after kickoff it's final, against the closing line.
2. Performance shows "Avg CLV +0.9 pts · vs the closing line", and the sidebar card shows "CLV +0.9".

**F-17 Power rankings**
1. Rankings › Power shows Rk, Δ, Team, Conf, Record, Rating, Trend, Off · rk, Def · rk, SOS and Next game. Row 1 reads "1 ▲1 Ohio State · Big Ten · 5-0 · +27.4 · +14.1 3 · +13.3 1 · 34 · vs Purdue, Model OSU −31.2, +3.7 OSU, B". Ratings are ink, never colored.
2. "FBS only" is on by default. The "SEC" chip shows Texas, Oklahoma, Georgia, Ole Miss and LSU from the fixture's top 10, and column headers sort.
3. Rank and Δ come from the `team_rankings` view and are never stored.

**F-18 Team page**
1. The Ohio State header has a 3px team-color accent bar and reads "1 Ohio State · Big Ten · 5-0 · ATS 3-2", Rating "+27.4 ▲1 · now 1st", Offense "+14.1 3rd", Defense "+13.3 1st", Schedule "34th SOS rank".
2. The schedule table lists every game with Market, Model, Edge, Result and ATS. Week 2 reads "vs Ohio · OSU −32.5 · OSU −30.8 · W 38-13 · ✗ Not covered".
3. The rating trajectory chart shows overall, offense and defense with a dashed "Prior +24.0" line. Preseason vs now shows "Change +3.4", "Returning prod. 58%" and "Talent rank 2nd". "Path to the playoff" appears only once F-20 ships (Phase 5), and its CFP % only once F-22 ships (Phase 7).

**F-19 Historical rankings**
1. "Ratings as of" steps back one week, or opens a season × week picker back to 2014. A past week shows a banner and a "Back to latest" button.
2. A past week shows the ratings stored at the time ("entering Week N"), never ratings recomputed with later games, and it's labeled "no hindsight".

**F-32 This week's record strip**
1. Under the This Week header: "This week 1-0 · 2 live (IOWA covering, OSU not yet) · 6 to play · +1.0u", one segment per pick. Clicking it toggles the Picks-only filter.
2. A live pick that's behind shows as live, never as lost, until the game is final. Scores refresh during game windows on the `scores` job's cadence (about every 30 min, plus the scheduler's 10–30 min delay).
3. Contest › Results "this week so far" counts points, not units. At Thu 10:00 PM both you and the model read "0 pts".

**F-33 Contest tracker**
1. Results & standing shows the season ("You 12-8", "Model top 4 11-9", "3rd of 14") and week-by-week rows (W1 3-1 / 2-2 … W5 3-1 / 2-2).
2. League standing is entered by hand through Edit and is still there after a reload.
3. Your entries (`contest_entries`) stay separate from model picks. Both are graded against the contest line with that contest's push rule (Splash preset: push = 0).

**F-37 Calibration charts**
1. Performance's calibration chart plots predicted cover % against actual hit rate, with a dotted "Perfect" diagonal, overconfidence gaps in `--neg` and the table "52.5% → 52.0% … 65+% → 59.6%, gap −5.4".
2. The "UNCALIBRATED" label shows on every cover % in the app until the calibration check in [04-model.md § 9](04-model.md#9-evaluation-protocol-fixed-2026-10-07) passes, then disappears everywhere at once.

**F-42 Sign-in**
1. Signed out, any page redirects to `/login`, which has a single "Sign in with GitHub" button and the note "Stays signed in on this device for 90 days". The allowlisted account lands on This Week. Any other GitHub account comes back to `/login` with "This GitHub account isn't allowed" and a "Use a different account" link.
2. A stale or badly signed session redirects to `/login`, never a 500.
3. On a cold database the sign-in button reads "Waking up the database…" with a one-line reason, instead of spinning with no explanation.

**F-43 ⌘K command palette**
1. ⌘K (desktop) or the search icon (mobile) opens the palette. Before you type, it shows Recent teams (e.g. "Oklahoma · 4 · SEC · 4-1 · +24.4") and Jump-to screens with "G then a letter" shortcuts ("G W" This Week, "⌘ ," Settings).
2. Typing "ohio" lists Ohio State and Ohio under Teams, and Enter opens the team page. A query with no hits shows "Nothing matches "<query>"".
3. On mobile the palette is a full-screen sheet.

**F-44 Teams index**
1. The Teams nav item (More › Teams on mobile) opens "Teams · Every FBS team · 136 · ratings entering Week 6". It's sorted by rating, with columns Team, Conf, Record, Rating (rank) and Next game · model line. Row 1 reads "Ohio State · Big Ten · 5-0 · +27.4 (1) · vs Purdue, Model OSU −31.2, +3.7 OSU, B". A row click opens the team page.
2. The "Filter by team name" box filters as you type and highlights the match, and the conference chips are single-select. The two stack: "ohio" with the MAC chip shows only Ohio. A search with no match shows its own empty state with "Clear filters"; before the first data sync the page reads "No teams yet".
3. It grows from the walking skeleton's team list ([02-architecture.md › Walking skeleton](02-architecture.md#walking-skeleton)), which shows only team chip, school and conference.

**F-45 Settings › General**
1. Settings (General · Contests · Alerts · Account) opens on General, which holds theme (Dark default, Light, Match system), default contest ("Splash work league · You 12-8 · 3rd of 14") and time zone, with "Use this device's time zone" on by default. Turning that off shows a zone picker with a live preview time.
2. Kickoff times everywhere render in the chosen zone. With ET selected, the fixture shows "Sat 3:30 PM ET".
