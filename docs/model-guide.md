# How the model works: a guide

A plain-language walkthrough of the college football model, from the data we pull to the pick that comes out, written for a software developer who hasn't done statistical modeling. It covers the math concepts, the actual files, and what each task in M2, M3 and M4 added.

**This is a guide, not the spec.** When it disagrees with the code, `docs/04-model.md` or `docs/decisions.md`, they win (CLAUDE.md › Which document wins), and this file should be fixed. Last brought up to date: 2026-10-31, after TASK-044 (D-145).

**Contents**
1. [The whole thing on one page](#1-the-whole-thing-on-one-page)
2. [The "engine": what it is and how you run it](#2-the-engine-what-it-is-and-how-you-run-it)
3. [Concepts primer](#3-concepts-primer)
4. [The rungs (the modeling ladder)](#4-the-rungs-the-modeling-ladder)
5. [The data (M2)](#5-the-data-m2)
6. [Rung 2, the v1 model, step by step](#6-rung-2-the-v1-model-step-by-step)
7. [From prediction to pick](#7-from-prediction-to-pick)
8. [The backtest](#8-the-backtest)
9. [Where results are stored](#9-where-results-are-stored)
10. [Task by task: M2, M3, M4](#10-task-by-task-m2-m3-m4)
11. [Where v1 stands and what's next](#11-where-v1-stands-and-whats-next)
12. [Glossary](#12-glossary)

---

## 1. The whole thing on one page

The model predicts one number per game: the **margin**, `home_points − away_points`. Everything else (the model's spread, cover probability, win probability, the pick) is derived from that number.

```
 CFBD API                      (games, advanced stats, betting lines, recruiting, ...)
    │  engine backfill / jobs   counted against a 5,000-call monthly budget
    ▼
 raw lake  (Parquet files, append-only, local ./data or Cloudflare R2)
    │  engine transform --rebuild   zero API calls
    ▼
 staging + feature tables  (DuckDB)   each week's rows stamped with as_of = "what we knew then"
    │
    ▼
 MODEL  (python/engine/src/engine/models/efficiency.py, configured by engine/specs/efficiency-v1.json)
    │   1. rate every team's offense & defense on 6 efficiency stats (ridge regression)
    │   2. blend with a preseason guess (the prior), which fades as games are played
    │   3. convert ratings to points (the margin model)
    │   4. predicted margin = home field + home rating − away rating
    ▼
 PROBABILITY  (core/probability.py)   margin ~ bell curve around the prediction, width σ
    ▼
 PICK  (core/picks.py)   compare to the line: edge = margin + spread; pick if edge is big enough
    ▼
 Postgres  (model_runs, team_ratings, predictions, picks)  insert-only
    ▼
 views grade the picks (pick_outcomes, model_record) → the web app shows them
```

Separately from that live path, the **backtest** replays 2014–2023 week by week through the exact same code to measure how good the model would have been. That's how every modeling decision gets made.

---

## 2. The "engine": what it is and how you run it

### What "engine" means here

`python/` is a **uv workspace** (uv is a Python package manager, like pnpm for Python) with three packages:

| Package | Folder | What it is |
|---|---|---|
| `cfb-db` | `python/db/` | Database models, Alembic migrations, backups, release helpers |
| `cfb-engine` | `python/engine/` | **The engine**: everything that pulls data, transforms it, fits models, backtests them and publishes results |
| `cfb-api` | `python/api/` | The FastAPI service the website calls (server-side only) |

The engine has two weights:

- **Light core** (`engine/core/`): pure math with only numpy, scipy and pydantic. It holds the spec, the probability formulas and the pick rules. The API imports *only* this, because the API runs as a Vercel function with a 250 MB size limit (CLAUDE.md hard rule 5).
- **Training stack** (the `train` extra: duckdb, pyarrow, numpy, boto3): ingest, transform, the models, the backtest. It runs on your machine or in GitHub Actions, never inside the API.

Inside `python/engine/src/engine/`:

| Folder | Job |
|---|---|
| `ingest/` | Call CFBD, count every call, save raw responses to the lake |
| `transform/` | Raw → staged tables → point-in-time feature tables, plus quality checks and closing lines |
| `sports/cfb/` | Everything specific to college football: FCS pooling, conference tiers, preseason sources. `core` never imports it, so NFL can plug in later |
| `core/` | The light core: spec, interfaces, probability, picks, contest rules, input registry |
| `models/` | The rating models: `power.py` (Rung 1), `efficiency.py` + `priors.py` (Rung 2) |
| `backtest/` | The walk-forward harness, baselines, metrics, report, bootstrap, pick-rule tuning |
| `publish/` | Write reference data, lines and model output to Postgres |
| `contests/` | The Splash paste parser |
| `cli.py` | The `engine` command |
| `specs/` (in `python/engine/`) | Model specs as JSON |

### Decoding `uv --directory python run engine …`

```
uv --directory python run engine backtest --spec engine/specs/efficiency-v1.json --seasons 2016-2023
│   │                  │   │      │
│   │                  │   │      └─ subcommand + its flags
│   │                  │   └─ the console script: python/engine/pyproject.toml maps `engine` → engine.cli:main
│   │                  └─ run a command inside the workspace's virtualenv (installing anything missing first)
│   └─ act as if we were in python/ (so relative paths like engine/specs/... start there)
└─ the uv tool
```

So it's equivalent to `cd python && .venv/Scripts/engine backtest …`. Each subcommand is a function in `engine/cli.py`.

### The commands

| Command | What it does | Touches |
|---|---|---|
| `engine ingest games --season Y` | Pull one season's `/games` into the dev DB (`pnpm ingest:games`) | CFBD (counted), dev DB |
| `engine backfill --from 2014 --to 2026 [--dry-run]` | Pull every endpoint the model uses for those seasons; skips files already final, so it resumes safely. `--dry-run` just counts the calls it would make | CFBD (counted), lake |
| `engine lake sync --from URI --to URI` | Copy raw files one lake has and the other lacks (R2 ↔ local `./data`) | lake |
| `engine transform --rebuild` | Rebuild every staged and feature table from raw files. **Zero API calls**, asserted | lake `staging/` |
| `engine check` | Run the data-quality checks on staging | read only |
| `engine publish --target dev\|test` | Upsert teams, games and line snapshots into Postgres | dev or test DB |
| `engine job results\|lines` | The scheduled jobs: refresh results and lines | CFBD, DB |
| `engine tiers --seasons 2014-2025` | Check every FBS team-season maps to Power 4 / G5 / FCS | read only |
| `engine backtest --spec F --seasons A-B [--report DIR] [--compare baselines] [--holdout --reason T]` | Replay history week by week and score the model | lake `backtests/` |
| `engine compare RUN_A RUN_B [--weeks 1-3]` | Is run A really better than run B? (paired week bootstrap, § 8) | read only |
| `engine rate --spec F --season Y --week N --target dev\|test [--choices run.json]` | Fit the model entering week N and insert the run, ratings and predictions | dev or test DB |
| `engine seed fixture` | Load the design's sample data into the test DB (`pnpm db:seed`) | test DB |

When a task's manual verification said "run `engine backtest …` and check the ledger is unchanged", it was checking two things: the backtest ran end to end on the real 12 seasons, and it didn't spend CFBD calls (the ledger is `data/cfbd_calls.json`).

---

## 3. Concepts primer

These are the ideas everything else rests on. Each links to the deeper treatment in `docs/04-model.md`.

### 3.1 A prediction is a bell curve, not a number

"Home by 6" is the center of a range. Real CFB margins scatter around a good prediction with a standard deviation **σ** of roughly 15–17 points. So the useful question is "how likely is the actual margin to land on the right side of the line?":

```
P(home covers home −3) = P(margin > 3) = Φ((6 − 3) / σ) = Φ(3 / 16) ≈ 0.574
```

Φ is the standard normal CDF: give it "how many σ above the threshold is the center" and it returns a probability. **A 3-point edge is worth about 57%.** (04 § 1; `NormalMargin` in `core/probability.py`.)

Sign conventions (CLAUDE.md): `spread_home` is negative when home is favored, and home covers when `margin + spread_home > 0`. So `edge = pred_margin + spread_home`: positive likes home, negative likes away.

### 3.2 Regression = solving more equations than you have unknowns

Give each team one number, its rating. Each game says "rating_home − rating_away ≈ margin". Three teams, neutral field:

| Game | Equation |
|---|---|
| A beat B by 10 | A − B = 10 |
| B beat C by 3 | B − C = 3 |
| A beat C by 7 | A − C = 7 |

No ratings satisfy all three (the first two imply A − C = 13, not 7). **Least squares** picks the ratings with the smallest total squared error. Adding "ratings average zero" to pin them down, the answer is A = +5.67, B = −2.33, C = −3.33. Those predict A by 8 over B, B by 1 over C and A by 9 over C: each game off by 2, total squared error 12, and no other ratings do better.

That's **opponent adjustment for free**: a win counts more against a team the equations say is strong. With 130+ teams and hundreds of games it's the same thing, solved by one `np.linalg.lstsq` call. You can step through one week of it in `python/notebooks/02-ratings-by-hand.py`.

### 3.3 Ridge regression = least squares that distrusts small samples

In week 3 a team has played 2 games, and plain least squares believes those 2 games completely. **Ridge** adds a penalty that pulls every rating toward average, with strength `alpha`. A rough feel, ignoring opponents: a rating behaves like `sum of observations / (games + alpha)`.

| Team | Games | Each game +0.30 EPA/play above average | Rating with alpha 2 |
|---|---|---|---|
| X | 2 | total 0.60 | 0.60 / 4 = **0.15** |
| Y | 10 | total 3.00 | 3.00 / 12 = **0.25** |

Same per-game performance, but the team with less evidence gets shrunk harder. In code this is literally extra rows appended to the equations, "this team's rating ≈ 0" weighted by √alpha (`efficiency.py`, `_solve`). We don't guess alpha; the backtest chooses it (§ 8). 04 § 2 Rung 2.

### 3.4 Priors and blending

Before week 1 there's no data at all, so we need a **prior**: a preseason guess, mostly last season's rating. Then

```
rating_week_N = w(N) · prior + (1 − w(N)) · in_season_rating
```

with `w` starting at 1 and fading as games are played. **Regression to the mean**: teams that were extreme last year drift back toward average (some of it was luck, and rosters turn over), so the prior is shrunk toward average too. 04 § 2 Preseason priors.

### 3.5 Three levels of "fitting"

This is the idea that makes the rest of the code readable. The model learns things at three speeds:

| Level | Examples | Fit from | How often |
|---|---|---|---|
| **Ratings** | Each team's offense and defense on each stat | This season's games so far | Every week |
| **Learned weights** | Margin-model coefficients, home field, σ, prior weights, decay `k` | Every *earlier* season's games | Once a season |
| **Settings** (hyperparameters) | `ridge_alpha`, recency half-life, pick thresholds, display shrinkage | Chosen by trying each candidate on *earlier* seasons in the backtest | Once a season |

Settings in the spec look like `{"tune": [1, 2, 3, 5, 8]}`: a list of candidates for the backtest to choose from. Learned weights never appear in the spec at all; they're in each run's `fitted_params`.

### 3.6 Overfitting and leakage

- **Overfitting**: a flexible model memorizes noise in the past and looks brilliant on games it has already seen, then fails on new ones. The defense is to only ever score a model on games it wasn't fit on.
- **Leakage**: any route by which information from *after* kickoff reaches a prediction (a season-total stat, a rating computed with the whole season, choosing alpha by looking at the season being scored). Backtests with leakage look amazing and live results look terrible. Much of the code exists to make leakage impossible, and tests prove it (04 § 9.2).

### 3.7 Measuring "good"

| Metric | Meaning | Good is |
|---|---|---|
| **MAE** (mean absolute error) | Average of \|predicted margin − actual margin\| | Lower. The closing line's MAE (~12.4) is the benchmark |
| **ATS win %** | Of the games picked, how often the pick covered (pushes left out) | Above 52.4%, break-even at −110 odds (risk 110 to win 100: 110/210) |
| **ROI** | Units won ÷ units risked at −110 | Positive |
| **Calibration** | When the model says 60%, does it happen 60% of the time? Checked in probability bins | Each bin within ±3 points |
| **Brier score** | Mean squared error of a probability (0 = perfect, 0.25 = always saying 50%) | Lower |
| **CLV** (closing line value) | Did the line move toward your pick after you made it? | Positive |

### 3.8 "Is A really better than B?": the bootstrap

Two models' MAEs differ by 0.1 points. Real, or luck? Score both on the same games, take the per-game difference in error, then **resample whole weeks with replacement** 10,000 times and recompute the average each time. If the middle 95% of those averages is entirely below zero, A beats B. Weeks, not games, because games in one week share news and weather, so treating them as independent overstates certainty. (04 § 9.5; `backtest/bootstrap.py`; `engine compare`.)

---

## 4. The rungs (the modeling ladder)

A **rung** is one level of model complexity. We climb one at a time, and **each rung must beat the one below it in the backtest** to earn its complexity. If a fancier model can't beat a simpler one out of sample, the simpler one wins. (04 § 2.)

| Rung | What it is | Status |
|---|---|---|
| **0: Baselines** | Dumb predictions to beat: home field only, last season's ratings frozen, the closing line, SP+/FPI | Built (TASK-032) |
| **1: Power ratings** | One number per team from game margins (least squares, § 3.2) | Built (TASK-033), beat Rung 0 |
| **2: Efficiency ratings** | Offense and defense ratings on efficiency stats (ridge), a fitted preseason prior, a margin model turning them into points | Built (TASK-036–038); this is **v1** |
| **3: ML layer** | LightGBM predicting what Rung 2 gets wrong (its residual) from matchup features | Not built (Phase 7) |
| **4: Situational** | Manual injury adjustments, rest, travel, altitude, weather | Not built (Phase 5) |

Rung 1 and 2 both end in the same formula, `margin = home field + home rating − away rating`, so everything downstream (probabilities, picks, the database, the app) doesn't care which rung made the prediction. That's what the `RatingModel` interface in `core/interfaces.py` guarantees: `fit(games, as_of) → Ratings`, then `predict(game, ratings, as_of) → Prediction`.

---

## 5. The data (M2)

### What we pull from CollegeFootballData (CFBD)

| Data | Used for |
|---|---|
| `/games` | Schedule, scores, neutral site, home/away |
| `/stats/game/advanced` | **The model's main input**: per team-game EPA/play and success rate, rushing and passing splits, garbage time excluded |
| `/lines` | Spreads from many books: opening and closing lines (the target to beat, never a model input) |
| `/player/returning`, `/talent`, `/recruiting/teams` | Preseason prior inputs |
| `/ratings/sp`, `/fpi`, `/elo` | Other people's ratings, for comparison only |
| `/plays`, `/drives`, `/games/teams`, `/teams`, `/venues`, `/calendar` | Box scores, reference data, later work |

**EPA (expected points added; CFBD calls it PPA).** Every down-distance-field position has an expected point value (1st-and-10 at the opponent's 25 is worth about 4). A play's EPA is how much it changed that. EPA per play measures efficiency with less noise than points: a turnover-fueled 35–31 game says less about team quality than the play-by-play efficiency does. **Success rate** is the share of plays that gain "enough" (e.g. half the needed yards on 1st down). (03 › Data sources.)

### How it flows

1. **Raw lake** (`ingest/lake.py`): every API response saved exactly as fetched, one Parquet file per pull, never overwritten. Lives in Cloudflare R2, mirrored to `./data`.
2. **Budget** (`ingest/cfbd.py`): 5,000 calls a month. Every call goes through `CallBudget`, which warns at 80%. A week whose games are all done is never fetched again.
3. **Staging** (`transform/staging.py`, `stats.py`): DuckDB reads the raw files and builds clean tables: latest version of each game, team names resolved to ids, advanced stats per team-game. Rebuilding from raw needs zero API calls.
4. **Quality checks** (`transform/quality.py`): e.g. every backtest game has a closing line; publishing refuses if a check fails.
5. **Point-in-time features** (`transform/features.py`): each week gets an `as_of` (its first kickoff); a game counts as finished 4 hours after kickoff (`GAME_HOURS`); a team's row for week N reads only games finished by `as_of`, and the build fails if any row didn't. This is the first line of defense against leakage.
6. **Closing lines** (`transform/market.py`): the consensus book's spread, else the median across books.

---

## 6. Rung 2, the v1 model, step by step

All of this is `engine/models/efficiency.py`, configured by `engine/specs/efficiency-v1.json`:

```json
"inputs": [epa_per_play, rush_epa_per_play, pass_epa_per_play,
           success_rate, rush_success_rate, pass_success_rate]   // each weight "fit"
"hyperparameters": { "ridge_alpha": {"tune": [1,2,3,5,8]}, "recency_half_life_weeks": {"tune": [8,16]} }
"home_field": "fit",  "shrink_toward": "tier",
"prior": { "components": [last_season, returning_production, talent, recruiting], "decay": {"type": "fitted"} },
"distribution": "normal",
"picks": { ... § 7 ... }
```

The spec is a `ModelSpec` (`core/spec.py`). Same spec + same data = same output, and each spec has a hash so a database row always knows exactly which spec made it.

### Step 1: per-stat ratings (every week)

For each of the 6 stats, every team-game offense is one equation:

```
stat = μ + off_O − def_D + h·s + tier_O − tier_D + error
```

- `μ`: the league average for this stat.
- `off_O`: how much better than average offense O is. `def_D`: how much less defense D allows than average (higher is better).
- `h·s`: home edge in the stat's own units; `s` = +1 home offense, −1 away, 0 neutral.
- `tier_*`: Power 4 / G5 / FCS levels (`sports/cfb/teams.py`). With `shrink_toward: tier`, ridge pulls a low-data team toward its *tier's* average instead of the overall average. A G5 team with two games is assumed G5-like, not average-FBS-like.

Solved with ridge (§ 3.3) on this season's games only, recent games weighted more (a game's weight halves every half-life weeks). All 6 stats share one design matrix, so one `lstsq` call solves them all. Ratings are shifted so FBS teams average zero. FCS teams are one pooled "team", since the lake only has their one or two games against FBS opponents.

Result: each team has 12 numbers (6 offense, 6 defense).

### Step 2: the preseason prior (fit once a season)

`engine/models/priors.py`. For each of the 12 ratings:

```
prior − anchor = a·(last season's final − anchor) + b·returning_production + c·talent + d·recruiting
```

- `anchor` is the team's tier level last season.
- `a, b, c, d` are learned by regression on earlier seasons: "given last year's rating and these roster signals, what did teams actually turn out to be?"
- Fitted for 2023: a team keeps about 30–55% of last season's distance from its tier (regression to the mean), going from 0% to 100% returning production is worth about 11.5 points, and talent adds nothing beyond recruiting.
- CFBD doesn't date these values, so each has an assumed publication date (`sports/cfb/preseason.py`, e.g. returning production July 1). The harness refuses any value assumed published after the season starts.

Blending: `w(N) = k / (k + N − 1)`, the prior counting as `k` weeks of games. `k` is learned (the candidate that makes the margin model fit best); it came out around 5:

| Week | 1 | 2 | 5 | 9 | 13 |
|---|---|---|---|---|---|
| Prior's weight | 1.00 | 0.83 | 0.56 | 0.38 | 0.29 |

So even in week 9 the preseason guess still carries about 38% of a rating, a slower fade than first guessed.

### Step 3: the margin model (fit once a season)

The ratings are in EPA and success-rate units. To get points:

```
pred_margin = HFA·(not neutral) + Σ b_off·(off_home − off_away) + Σ b_def·(def_home − def_away)
```

Ordinary least squares over every FBS-vs-FBS game of earlier seasons, using the ratings as they stood entering each game's week. The `b` coefficients answer "how many points is one unit of EPA/play worth?" σ is this model's typical miss (residual RMSE). They're stored in `fitted_params` as `b_off_<stat>`, `b_def_<stat>`, `home_field`, `margin_sd`.

Because the formula is symmetric, it collapses to **one points rating per team**, `Σ b·rating`, split into offense and defense in points. So `team_ratings` stores `rating = off_rating + def_rating` (TASK-038).

### Step 4: predict

```
pred_margin = home_field + rating_home − rating_away
```

Plus **drivers** (TASK-038): per stat, "home offense vs away defense" and "away offense vs home defense" contributions, which sum exactly to the predicted margin. That's what the app's "why" waterfall will show.

### Step 5: probability

`core/probability.py`. v1 uses the normal curve: `P(home covers) = Φ((pred_margin + spread_home) / σ)`.

TASK-038 also built `EmpiricalMargin`, which knows margins pile up on 3 and 7 (it found 3 happens 2.45× as often as a bell curve says). It didn't improve the Brier score, so v1 keeps `distribution: normal`; the code is ready for a later version.

---

## 7. From prediction to pick

`core/picks.py`. Worked example (numbers illustrative, σ taken as 16):

| Step | Formula | Example |
|---|---|---|
| Prediction | from § 6 | home by 10.5 |
| Line | from `line_snapshots` | home −7 |
| Edge | `pred_margin + spread_home` | 10.5 − 7 = **+3.5** (likes home) |
| Cover probability | `Φ(edge / σ)` | Φ(3.5/16) = **58.7%** |
| Pick? | `|edge| ≥ min_edge_pts` and prob ≥ `min_prob` (0.5) | yes if `min_edge_pts` ≤ 3.5 |
| Tier | highest of A ≥ 11, B ≥ 9, C ≥ 6 the edge reaches | none (3.5 < 6): a pick without a tier |
| Displayed probability | same formula on a margin shrunk toward the line by `display_shrinkage_k` | at k_d 0.15: margin 0.15·10.5 + 0.85·7 = 7.5, so Φ(0.5/16) ≈ **51%** |

Three ideas in that table need explaining.

**Market shrinkage** (`market_shrinkage_k`). When the model disagrees with the market by 10 points, the market is usually right: the model probably missed news. Blending `k·model + (1−k)·market` tempers that. TASK-039 tested it: it made the probabilities more honest but *lowered* ATS (53.7% vs 55.1% at k = 1). The rule says keep it only if ATS is at least as good, so v1 uses k = 1 (no shrinkage) for choosing picks.

**Display shrinkage** (`display_shrinkage_k`, TASK-042). The un-shrunk probabilities were badly overconfident: games shown at 65%+ covered 53%. Since *which* games get picked depends only on the edge, we can shrink the probability *shown* without changing a single pick. That's the 58.7% → 51% in the example: picks are identical, the number displayed is honest. The backtest chose k_d of 0.1–0.25 per season (heavy shrinkage), which says how much the market knows that the model doesn't.

**Pick thresholds are tuned, not guessed** (TASK-039, `backtest/pick_rules.py`). `min_edge_pts` is chosen from {2, …, 8} for the best ATS on earlier seasons, but only among choices with at least 200 picks (fewer is too noisy to trust). Tiers are the thirds of historical pick edges.

Other rules:
- **No FCS games** are ever picked (`pick_game` with `sports.cfb.teams.pickable`; D-047).
- **A pick is locked to its line.** If the line moves, a new pick row is written only if the side or tier changes, so "Picked at −2.5" stays true (D-140).
- **Contest mode** (`core/contest_rules.py`, `contests/splash.py`): Splash has no vig (break-even 50%) and a fixed number of picks, so the rule becomes "rank the slate by cover probability against the contest's line and take the top N", not "everything over a threshold". Wired up in M6.

---

## 8. The backtest

### What it is

A **backtest** answers "if we had run this exact model every week of 2016–2023, how would it have done?" It's the only honest way to evaluate a model before risking anything, and it's how every decision in this project gets made.

`backtest/harness.py` replays history in order:

```
for each season Y:
    choose settings (alpha, half-life, pick rules) using only seasons 2015 … Y−1
    for each week N of Y, in kickoff order:
        as_of = first kickoff of week N
        fit the model on every game that finished by as_of        ← asserted, not trusted
        predict every eligible game of week N (FBS vs FBS, final, has a closing line)
        record prediction, closing line, actual margin
```

This is **walk-forward** (always predicting the future from the past) and **rolling-origin** (the starting point for tuning rolls forward each season). Every 2016–2023 prediction is a true out-of-sample prediction.

### The seasons

| Seasons | Role |
|---|---|
| 2014 | Warm-up: ratings computed, nothing scored (the prior needs a last season) |
| 2015 | Tuning only |
| 2016–2023 | **Validation**: ~6,000 scored games, the "Validation 2016–2023" numbers in the app |
| 2024–2025 | **Holdout**: locked. Opened once per candidate, at promotion, with a written reason, and recorded. If it fails, you may not tweak the model to fix the holdout, or it becomes just another validation set |
| 2026 | Live paper trading |

### Leak-proofing

- The harness only hands a model inputs from `FIT_INPUTS` (games, team-game stats, preseason values), each through a method that asserts its timestamp (`finished_by(as_of)`, `for_season(Y)`).
- Market lines, SP+/FPI and hindsight ratings are **refused by name** if a model asks for them.
- Learned weights raise `PointInTimeError` if handed a game from the season being predicted.
- Tests change a game after week N and check week N's predictions don't move (`test_backtest_leakage.py`, `test_leakage.py`), and a golden test pins exact numbers on a two-season fixture (`test_backtest_golden.py`).

### What a run produces

Each run writes to the lake under `backtests/<timestamp>-<spec hash>/`:
- `predictions.parquet`: one row per game (prediction, line, actual, cover probability, …).
- `run.json`: the settings chosen for each season. `engine rate --choices run.json` reuses them, so the live model uses exactly the settings the backtest validated.
- With `--report DIR`, `report.md` and `report.html`: every metric and gate below, plus breakdowns by week, conference tier, spread size and favorite/underdog.

### The gates (04 § 9.4)

A model goes to `production` only if it passes all of these on pooled validation, then the holdout:

| Gate | Rule |
|---|---|
| MAE vs closing line | Model MAE − closing-line MAE ≤ +0.5 points |
| ATS | > 52.4%, with its 95% interval shown |
| Edge trend | Bigger edges cover more often (slope's interval above zero) |
| Consistency | ≤ 2 of 8 seasons below 50%, and still > 52.4% with the best season removed |
| Calibration | Every probability bin with ≥ 100 picks within ±3 points |
| Holdout | ATS > 50% and MAE gap ≤ +0.5 on 2024–2025 |

---

## 9. Where results are stored

Postgres, written by `engine rate` (`publish/models.py`):

| Table | One row per | Notes |
|---|---|---|
| `model_versions` | named model (e.g. efficiency v1.0) | `status`: `candidate` or `production`; spec + hash |
| `model_runs` | one fit entering one week | `fitted_params` (all learned weights), status, error |
| `team_ratings` | team × run | `rating`, `off_rating`, `def_rating`, `components` (per-stat points) |
| `predictions` | game × run | margin, σ, win probability, drivers |
| `picks` | each pick or pass | locked to a `line_snapshots` row; edge, displayed probability, tier, stake |

**Insert-only** (hard rule 2): database triggers reject UPDATE and DELETE. A re-run inserts new rows tied to a new `model_run`, so history is never rewritten and you can always see what the model said at the time.

**Derived numbers are views, never stored** (hard rule 1): `team_rankings` (rank and week-over-week change), `team_schedule_strength`, `current_picks` (the newest pick before kickoff), `pick_outcomes` (win/loss/push, units, CLV), `model_record` (W-L-P, ROI by week, tier and edge bucket). If a score is corrected, the record fixes itself on the next read: there's no grading job to rerun.

---

## 10. Task by task: M2, M3, M4

### M2: Data pipeline (Phase 1)

| Task | What it did | What it gave the model |
|---|---|---|
| **TASK-015** | CFBD client with call-budget tracking; raw Parquet lake (local or R2) | A safe, append-only place for all source data |
| **TASK-016** | Tables `seasons`, `team_aliases`, `sportsbooks`, `line_snapshots` | Somewhere to store every line a book offered, with its time |
| **TASK-017** | DuckDB staging, `transform --rebuild`, data-quality checks | Clean tables rebuilt from raw with zero API calls |
| **TASK-018** | Staged advanced stats, preseason inputs, benchmark ratings, plays and drives | The EPA/success-rate inputs and prior components |
| **TASK-019** | Point-in-time `team_week_features` and `game_features` | The `as_of` rule and its assertion: the base of leak-proofing |
| **TASK-020** | Publish teams, games and lines to Postgres; the `game_market` view | Opening, current and closing line per game for the app |
| **TASK-021** | Backfill 2014–2026; notebook #1 | All the history; **the benchmark: closing line MAE 12.38** over 9,085 games |
| **TASK-022** | Scheduled `results` and `lines` jobs | Fresh scores and lines without anyone running anything |
| **TASK-023** | Splash paste parser against `ContestRules` | Contest lines from a copy-paste (used in M6) |
| **TASK-028** | Stop a late fallback job run repeating the dispatched one | Ops fix (no model effect) |

### M3: Measuring stick (Phase 2)

The principle: **build the ruler before the thing you measure.** The backtest and baselines came before any serious model.

| Task | What it did | What it gave the model |
|---|---|---|
| **TASK-029** | `ModelSpec`, the `RatingModel` interface, probability math (edge, Φ, EV), pick rules from the spec, the input registry | The contract every model plugs into, and the light core the API can use |
| **TASK-030** | The walk-forward harness, tuning on earlier seasons, holdout lock, leakage assertions, golden test | The backtest itself (§ 8) |
| **TASK-031** | Metrics, gates, week bootstrap, markdown/HTML report | The scorecard and the "is it really better?" test |
| **TASK-032** | Baselines: home field only, last season frozen, closing line, SP+/FPI | Rung 0. SP+/FPI turned out to be season-final in CFBD, so they're labeled "hindsight benchmark" and can't count as beaten |
| **TASK-033** | **Rung 1** power ratings; notebooks #2–3 | First real model: **MAE 13.29**, beating home field only (16.51) and last season frozen (15.06). Closing line on the same games: 12.43 |
| **TASK-034** | `model_versions`, `model_runs`, `team_ratings`, `predictions`, insert-only triggers | Somewhere to keep every run immutably |
| **TASK-035** | `engine rate` publishes a week's run; `team_rankings` and `team_schedule_strength` views | Ratings and rankings the app can show |

### M4: Model v1 and paper trading (Phase 3)

| Task | What it did | What it gave the model |
|---|---|---|
| **TASK-036** | **Rung 2**: ridge efficiency ratings on 6 stats, conference tiers, the margin model, `engine compare` | Ratings built on efficiency instead of score; `shrink_toward: tier` beat `zero` (−0.19 MAE) |
| **TASK-037** | Fitted preseason prior (returning production, talent, recruiting) and fitted decay `k` | Better early-season ratings: MAE 13.03 vs 13.15. Most of the gain was the fitted fade, not the roster inputs |
| **TASK-038** | Ratings in points (offense + defense = rating), drivers, empirical margin distribution | Explainable predictions; key numbers measured but the normal curve kept |
| **TASK-039** | Tuning pick rules on earlier seasons (`backtest/pick_rules.py`); FCS games never picked | Pick thresholds and tiers chosen by data. Market shrinkage dropped for picks (ATS 53.7% vs 55.1%) |
| **TASK-040** | The `picks` table, insert-only, locked to a line snapshot; fixture picks seeded | Picks stored immutably, passes included |
| **TASK-041** | `current_picks`, `pick_outcomes`, `model_record` views | Grading, units, ROI and CLV computed on read |
| **TASK-042** | `display_shrinkage_k`: calibrate the shown probability separately | Honest probabilities with picks unchanged: calibration failed in 1 bin instead of 6 |
| **TASK-043** | Widened the alpha grid, ran full validation, opened the holdout once, recorded the go/no-go (D-144) | The verdict, below |
| **TASK-044** | Stage canceled games; `engine rate` predicts the harness's own week contexts | No permanent predictions for games that won't be played. Part of M4.8 |

Still open in M4.8: TASK-045 and TASK-046 (the weekly rate → predict → pick job and writing live picks).

---

## 11. Where v1 stands and what's next

**The verdict (D-144, 2026-10-31): v1 is not promoted. It's paper-traded as a `candidate` through 2026, and the app shows the "uncalibrated" label.**

| Check (validation 2016–2023, 5,954 games) | Result | |
|---|---|---|
| MAE vs closing line | 13.05 vs 12.43: gap **+0.63** (needs ≤ +0.5) | Fail |
| ATS | **54.4%** on 630-528-19, ROI +3.9% | Pass |
| Edge trend | Bigger edges cover more | Pass |
| Consistency | 2 of 8 seasons under 50% (2017, 2019) | Pass |
| Calibration | One bin: shown 55–57.5%, covered 46.5% | Fail |
| vs Rung 1 | 13.05 vs 13.29, a real win (−0.24) | Pass |
| **Holdout 2024–2025** | ATS **47.3%** (86-96-3); MAE gap +0.61; edge trend flat | Fail |

In plain terms: v1 is clearly better than Rung 1 and showed a profitable-looking ATS in validation, but it's still about 0.6 points less accurate than the closing line, and its validation edge didn't carry over to the two locked seasons. Promoting it anyway would call a model that failed its final exam "production". Paper trading 2026 gives new out-of-sample games for free.

**What the next variant goes after** (each its own candidate, with its own holdout run, never tuned on 2024–2025):
- The gap to the market is largest in **weeks 1–3** (+1.14) and the **postseason** (+0.88).
- **M19.1**: more inputs from 04 § 10 (explosiveness, havoc, finishing drives and others), each kept only if it wins on its own.
- **M19.2**: a per-game σ, so a mismatch and a toss-up don't get the same uncertainty.
- **Rung 3**: LightGBM on Rung 2's residuals.
- A noise-aware calibration tolerance (a 130-game bin's own standard error is ~4.4 points, wider than ±3), for later versions only.

**Updating this guide:** when a task changes the model, the spec, the pipeline or v1's status, update the section it touches and the "Last brought up to date" line at the top.

---

## 12. Glossary

| Term | Meaning |
|---|---|
| **as_of** | The moment a prediction is made "entering" a week: its first kickoff. Nothing after it may be read |
| **ATS** | Against the spread: did the pick cover the line |
| **Backtest** | Replaying past seasons week by week to measure the model (§ 8) |
| **Baseline** | A deliberately simple prediction a real model has to beat (Rung 0) |
| **Brier score** | Mean squared error of a probability; lower is better |
| **Calibration** | Whether stated probabilities match how often things happen |
| **CLV** | Closing line value: line you picked at vs the closing line |
| **Closing line** | The market's last spread before kickoff; the toughest benchmark |
| **Decay / w(N)** | How much of a rating is still the preseason prior in week N |
| **Drivers** | Per-stat contributions that add up to a predicted margin |
| **Edge** | `pred_margin + spread_home`; how much the model disagrees with the line |
| **EPA / PPA** | Expected points added per play; efficiency |
| **Fitted params** | Learned weights stored with a run (coefficients, HFA, σ, prior weights, k) |
| **Holdout** | 2024–2025, opened once per candidate as the final exam |
| **HFA** | Home-field advantage, in points |
| **Leakage** | Future information reaching a prediction |
| **MAE** | Mean absolute error of the margin, in points |
| **Margin model** | The regression turning efficiency ratings into points |
| **ModelSpec** | The JSON that fully defines a model version |
| **Point-in-time** | Using only data available before kickoff |
| **Prior** | The preseason guess a rating starts from |
| **Ridge (alpha)** | Least squares with a pull toward average; alpha is the strength |
| **Rung** | A level on the modeling ladder; each must beat the one below |
| **σ (margin_sd)** | How far real margins typically land from the prediction |
| **Spec hash** | Fingerprint of a spec, so stored rows know exactly which model made them |
| **Tier** | Power 4, G5 or FCS; what ridge shrinks a low-data team toward |
| **Tuning** | Choosing settings by trying candidates on earlier seasons |
| **Validation** | 2016–2023, scored out of sample with rolling-origin tuning |
| **Walk-forward** | Always predicting week N from data before week N |
