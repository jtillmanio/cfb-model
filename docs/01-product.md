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
