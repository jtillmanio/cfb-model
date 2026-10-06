# 04 — Model Design (with a modeling primer)

This doc is both the model spec and a guide to the ideas behind it. Sections marked **Concept** explain a modeling idea the first time we need it.

## 1. What exactly are we predicting?

The core target is **game margin**: `home_points − away_points`. Everything else derives from it:

- **Model spread** = `−pred_margin` (if we think home wins by 6, our line is home −6)
- **Cover probability** for the home team at market spread `s`: `P(margin + s > 0)`
- **Win probability**: `P(margin > 0)`
- **Total** comes from a second model (pace × efficiency) later

**Concept: predicting a distribution, not a number.** A prediction of "home by 6" is really the center of a bell curve. CFB game margins scatter around a good prediction with a standard deviation (σ) of roughly 15–17 points; we'll measure it exactly. If we predict +6 and the line is home −3, then:

```
P(home covers) = P(margin > 3) = Φ((6 − 3) / σ) = Φ(3 / 16) ≈ 0.574
```

where Φ is the standard normal cumulative distribution. So a **3-point edge is worth about a 57% cover probability**. That's huge in betting terms, and it shows why edges have to be measured in points *and* probabilities. (Real margins have "key numbers" like 3, 7, 10 and 14 where games cluster, so we'll later refine the plain bell curve with an empirical distribution.)

**Concept: break-even and expected value.** At −110 you risk 110 to win 100. Break-even win rate = 110 / 210 = **52.38%**. Expected value per unit risked = `p × (100/110) − (1 − p)`. At p = 0.574 that's **+9.6%**, a strong bet in theory, *if the 57.4% is real*. The whole game is making sure the probability is real (it's *calibrated*).

## 2. The modeling ladder

We climb in rungs. Each rung must **beat the previous one in the backtest** to earn its complexity. You'll understand every step because we build them in order.

### Rung 0: Baselines (what we must beat)
| Baseline | Prediction | Why it matters |
|---|---|---|
| Home-field only | home by ~2.5 | The dumbest possible model; any model must crush it |
| Last season's final ratings | carry over | Shows how much in-season info adds |
| **Closing line** | market's number | The real benchmark. Accuracy close to it is the goal |
| SP+ / FPI (from CFBD) | their spreads | Public models; are we competitive? |

### Rung 1: Simple power ratings (margin-based, "Massey" style)

Give every team one number, its *rating*, so that for any game:

```
predicted_margin = rating_home − rating_away + HFA × (not neutral_site)
```

We find the ratings that best explain all game results so far, solving a least-squares regression where each game is one equation.

**Concept: regression as "solving lots of equations at once."** With 130 FBS teams and ~800 games, there are more equations than unknowns, so no ratings fit perfectly. Least squares picks the ratings that minimize total squared error. That's opponent adjustment for free: beating a strong team by 3 helps more than beating a weak team by 3, because the opponent's rating is in the equation.

Refinements we'll test:
- **Margin cap / diminishing returns:** a 63–0 blowout isn't 9× more informative than a 7-point win. Cap at about 28, or use a log transform.
- **Recency weighting:** week-10 games count more than week-1 games.
- **FCS opponents:** pool them into a few FCS tiers so they don't distort FBS ratings.

### Rung 2: Opponent-adjusted efficiency ratings (the core model, v1)

Scoring margin is noisy: turnovers, a bad bounce, garbage time. **Efficiency** (EPA/play, success rate) is more stable and more predictive, so we rate offenses and defenses on that.

For each efficiency stat (e.g. offensive EPA/play, excluding garbage time), fit:

```
stat(offense O vs defense D, game g) = μ + off_O − def_D + home_adj + ε
```

This gives every team an **offensive rating** and a **defensive rating** per stat, adjusted for the opponents they've faced.

**Concept: ridge regression (regularization).** In week 3 a team has played 2 games, and plain least squares will overreact to them. **Ridge regression** adds a penalty that pulls every rating toward zero (average) unless the data strongly says otherwise. A small sample gets heavily shrunk; a large sample barely at all. One knob (`alpha`) sets the strength, and we tune it in the backtest. This is one of the most useful ideas in all of sports modeling.

Stats to rate (all from CFBD advanced stats, garbage time excluded):
- EPA/play, overall + rushing + passing (offense and defense)
- Success rate
- Explosiveness
- Points per opportunity (finishing drives), field position, havoc
- Special teams (later)

Then a **margin model** turns efficiency matchups into points:

```
pred_margin = β₀·HFA + β₁·(off_epa_home − def_epa_away) − β₂·(off_epa_away − def_epa_home) + β₃·(…success rate…) + …
```

fit on historical games with plain linear regression (interpretable coefficients; you can see how many points each unit of EPA is worth).

### Preseason priors and blending (crucial for CFB)

In weeks 1–4 we barely know anything about this year's team. The **prior** is our best pre-season guess:

```
prior_rating = a·(last season's final rating, regressed toward the mean)
             + b·(returning production %)
             + c·(talent composite)
             + d·(recruiting, last 4 classes)
```

with weights fit on history. In-season data then gradually takes over:

```
rating_week_N = w(N)·prior + (1 − w(N))·in_season_rating
```

where `w(N)` decays from ~1.0 in week 1 toward ~0.1 by week 8–10. We fit the decay curve in the backtest rather than guessing it.

**Concept: regression to the mean.** Teams that were extreme last year (very good *or* very bad) tend to drift back toward average, partly because some of their extremeness was luck and partly from roster turnover. Every prior should be shrunk toward average, and returning production tells us how much.

**Concept: Bayesian thinking (informally).** Prior + evidence produces an updated belief, and the more evidence we have, the less the prior matters. Ridge regression and prior blending are both practical versions of this. We don't need full Bayesian machinery (PyMC) for v1, but it's a natural v3 upgrade that gives uncertainty for free.

### Rung 3: Machine-learning layer (test it, don't assume it)

Feed matchup features (rating differences, unit-vs-unit mismatches, rest days, travel distance, altitude, conference game, week of season) into a **gradient-boosted tree model** (LightGBM) that predicts the *residual* of the Rung 2 model.

**Concept: overfitting.** A flexible model can memorize noise in past games and look amazing in-sample while failing on new games. The defenses are walk-forward validation (below), few features, strong regularization, and the rule that **it ships only if it beats Rung 2 out of sample.** In sports, linear rating models often win, and that's fine.

### Rung 4: Situational adjustments
- **Manual overrides** (QB injuries, suspensions) via `manual_adjustments`: the market reacts to these and our stats don't know about them.
- **Rest/travel/timezone**, **altitude**, **weather** (totals).
- Each one is evaluated separately and kept only if it improves the backtest.

### Totals model (Next)
`pred_total = f(pace_home, pace_away, off/def efficiency, weather, dome)`, with the same ladder approach applied to points scored by each team.

## 3. Simulation: games and seasons

### Simulating a single game thousands of times
This is a reasonable idea, but whether it helps depends on *what* gets simulated.

**Concept: Monte Carlo.** You estimate a probability by randomly generating many possible outcomes and counting. Simulate 10,000 games, see the home team cover in 5,740, and the cover probability is ≈ 57.4%.

- **Simulating from our bell curve adds nothing.** If each simulated game just draws a margin from Normal(pred_margin, σ), 10,000 draws reproduce exactly what the formula `Φ(edge/σ)` gives instantly. Same answer, more compute.
- **Simulating the game's *structure* can add something.** A *possession/drive-level* simulator plays out a game: each team's drives end in TD, FG, punt or turnover with probabilities taken from its offense-vs-defense ratings, and pace sets the number of drives. Three things come out of that which a bell curve misses:
  1. **Key numbers**: margins cluster on 3, 7, 10 and 14 because scores come in 3s and 7s. That matters for half-point line decisions (−2.5 vs −3.5).
  2. **Margin and total together**: a fast, high-scoring game has wider margin swings. One simulation gives consistent spread, total and win probabilities.
  3. **Lopsided shapes**: big mismatches aren't symmetric bell curves.
- **The catch:** a drive simulator has many more moving parts to get wrong. In published work it rarely beats a well-calibrated ratings model on spread accuracy. Its edge is in the *shape* of the distribution.

**Recommendation:** for v1, get key numbers cheaply by replacing the plain bell curve with an **empirical margin distribution** (how real CFB margins scatter around a prediction, measured from history). Then try a drive-level simulator as a Phase 7 research experiment, which ships only if it improves calibration around key numbers or the totals model.

### Simulating seasons (definitely worth it)
Monte Carlo really earns its place here, because season outcomes are **path-dependent**: who makes a conference title game depends on the results of dozens of other games and on tiebreakers. There's no clean formula, but simulation handles it easily:

```
repeat 10,000 times:
    for each remaining game: draw a result using its win probability
    apply conference tiebreakers → title game participants → simulate title game
    record each team's final record, conference champion, (later) CFP field
aggregate → expected wins, P(8+ wins), P(conference title), …
```

- **Projected final records and conference title odds** (Next): straightforward once ratings exist.
- **CFP odds** (Later): needs a model of the 12-team selection (5 highest-ranked conference champions + 7 at-large by committee ranking). We'd approximate the committee from our ratings plus résumé features (record, strength of record from §7), validated against past rankings. Fun, but the committee is the noisiest part.
- **Concept: rating uncertainty within a season.** A team's true strength is uncertain too. Good simulations draw each team's rating once per simulated season (rating ± its uncertainty) before simulating games. Otherwise the odds come out overconfident: a team that's secretly overrated fails *all* its games together, not independently.

## 4. From predictions to picks

```
edge_pts   = pred_margin + spread_home          # >0 → like home, <0 → like away
model_prob = Φ(|edge_pts| / σ)                  # prob our side covers
EV         = model_prob × payout − (1 − model_prob)
```

Pick rules (tuned in backtest, not guessed):
- Recommend when `|edge_pts| ≥ threshold` (likely 2.5–4 points) **and** `model_prob ≥ min_prob`.
- **Tiers:** A / B / C by edge bucket, where each tier's historical hit rate is shown in the UI.
- Skip early-season games where the prior still dominates, if the backtest says those picks don't perform.
- Re-evaluate when the line moves. A pick is locked to the line it was made at (`line_snapshot_id`), and a new line creates a new pick that supersedes the old one.

### Contest mode (generic pick'em; Splash is the default preset)
Pick logic reads the contest's `ContestRules` (see [03-data-model.md](03-data-model.md)), so nothing below is Splash-specific. For your league (4 picks/week from CFB + NFL, per-game kickoff lock, 1 point per win), it works out as follows:

- **No vig:** break-even is 50%, not 52.4%. Every pick only has to beat a coin flip.
- **Fixed number of picks:** instead of "everything above a threshold," we **rank the eligible slate by cover probability against the contest's line** and recommend the top N (4). The full ranking stays visible, so you can see how close #5 was.
- **Contest line vs market:** when the contest's line differs from current consensus (contest −3, market −5.5), the market's number is strong information by itself. The ranking combines the model's view with the contest-vs-market gap. This is the one edge that also works for games the model doesn't cover, like NFL before Phase 8.
- **Per-game locks:** each game locks at its own kickoff, so a Thursday pick can't be revisited Saturday. Lines can still move until kickoff, so the Contest screen shows when the line you'd get now differs from when you last looked.
- **Mixed sports:** until the NFL model exists, NFL games are ranked only on the contest-vs-market gap and labeled "no model."

**Concept: the winner's curse in top-N picks.** If you rank 75 games by model edge and take the top 4, those 4 are disproportionately games where the model *overestimated* its edge: big errors float to the top. This is why picking a few games from a big slate needs **shrinking toward the market** (below) even more than threshold betting does. The backtest will measure it: we'll check the "top 4 per week" strategy's real hit rate against the hit rate its probabilities predicted.

### When you pick: end of week
You pick late in the week, near the closing line, which is the hardest line to beat. Since Splash's lines stay live until kickoff, they probably track the market closely too. So the **primary evaluation line is the closing line** (or the contest line, in contest mode), not the opener. Early-week edges that vanish by Friday don't help you. The backtest also reports results against opening lines, for anyone who bets early.

**Concept: shrinking toward the market.** When our model disagrees with the market by 10 points, the market is usually right: we've probably missed news. Many sharp bettors blend `final = k·model + (1−k)·market` and bet only when the *blended* number still clears the threshold. We'll test whether this improves pick ROI; it often does, by filtering out the model's wildest (and wrongest) takes.

**Concept: Kelly staking (Later).** Kelly sizes a bet proportional to edge: `stake = (p·(b+1) − 1) / b`. Full Kelly is far too aggressive given model uncertainty, so if we use it at all it'll be ¼ Kelly with a cap. Until the model proves itself, flat 1-unit picks.

## 5. Validation: how we know it works

**Concept: walk-forward backtesting and leakage.** To simulate reality, we "replay" history week by week: to predict week N of 2019, the model sees *only* data from before week N of 2019. Then it predicts, we score it, and we move to week N+1. **Leakage** is any way future information sneaks in, e.g. using season-total stats, a rating computed with the full season, or tuning hyperparameters on the test years. It makes backtests look amazing and live results look terrible. Our defenses:

- `as_of` timestamps on every feature row, and assertions that no input postdates the game.
- The harness drives everything by `(season, week)` and calls the same code path as production.
- **Split by seasons:** tune on 2014–2021, validate on 2022–2023, hold out 2024–2025 as a final exam that's looked at rarely. The **2026 season (in progress) becomes live paper trading.**

### Metrics we report for every model version
| Metric | What it tells us |
|---|---|
| MAE / RMSE of margin | Raw accuracy (compare to closing line on the same games) |
| ATS win % vs opening and vs closing lines | Would picks have made money? |
| ATS win % by edge bucket (0–1.5, 1.5–3, 3–5, 5+) | Do bigger edges win more often? If not, the edge isn't real |
| Units / ROI at −110 | Profit view |
| **Calibration**: predicted cover prob vs actual hit rate | Are our probabilities honest? |
| Avg **CLV** of picks | Are we beating the closing number? |
| Breakdown by week-of-season, conference tier, spread size | Where the model is strong or weak |

**Concept: why opening vs closing lines both matter.** The **closing line** (right before kickoff) is the most accurate number, since it has absorbed all the news and sharp money. Beating closing lines in a backtest is the gold standard. But in real life you bet *earlier*, closer to the **opening/early-week line**, which is softer. So we evaluate against both: closing tells us if the model is truly smart, and opening tells us if it's practically profitable. Since you pick late in the week, closing (and contest lines) are what we optimize for.

### Go / no-go to "production"
A model version becomes `production` only if, on the validation seasons:
1. Margin MAE is within ~0.5 pt of the closing line (or better),
2. ATS win % on qualifying picks is > 52.4% vs **closing** lines with a monotonic edge-bucket trend,
3. Calibration error is small (predicted 58% ≈ actual 55–61%),
4. Results are consistent across seasons, not driven by one lucky year.

(For contest-only use, 50%+ would technically be enough, but we hold the stricter sportsbook bar so a "production" model means something.)

## 6. Config-driven models & the model lab

### Every model is a spec
To make "create and customize a model in the UI" possible, and to make versions reproducible, **a model is fully described by a declarative `ModelSpec`** (a pydantic model, stored as `model_versions.spec`). The code is a generic engine that reads the spec. A sketch:

```yaml
name: efficiency-v1-pass-heavy
base: efficiency            # rating family: power | efficiency | (later) ml-residual
inputs:                     # which opponent-adjusted stats to rate
  - {stat: epa_per_play, split: pass, weight: fit}
  - {stat: epa_per_play, split: rush, weight: fit}
  - {stat: success_rate, weight: fit}
  - {stat: explosiveness, weight: 0.0}       # excluded
hyperparameters:
  ridge_alpha: 150
  recency_half_life_weeks: 6
  margin_cap: 28
home_field: fit             # or a fixed number, e.g. 2.0
prior:
  components: [last_season, returning_production, talent, recruiting]
  weights: fit
  decay: {type: fitted}     # or {type: linear, zero_at_week: 8}
distribution: empirical     # or normal
picks:
  min_edge_pts: 3.0
  market_shrinkage_k: 0.7
  tiers: {A: 5.0, B: 3.5, C: 2.5}
```

Each weight is either **`fit`** (learned from data by the backtest) or **fixed** at a number you choose. The spec's JSON Schema generates the model-builder form in the UI, so the form can never offer an option the engine doesn't support.

### Two kinds of numbers: settings vs learned weights
**Concept: hyperparameters vs parameters.** *Parameters* (weights) are what the model **learns** from data: "1.0 EPA/play is worth 28 points," "home field = 2.3." *Hyperparameters* are settings **you choose** that control how learning happens: the ridge `alpha`, the recency half-life, the margin cap. The backtest tunes hyperparameters by trying values and keeping the best on the validation seasons.

- The spec holds your choices (hyperparameters and any fixed weights).
- `model_runs.fitted_params` holds what the model learned. The **"View weights" screen** shows both, side by side, with plain-English labels.

### The lab workflow
1. **Clone** the production model (or any version) into a new `dev` version.
2. **Edit** the spec in the form: drop a stat, fix home field at 2.0, change the prior decay.
3. **Run backtest**: the API queues a run and triggers the GitHub Actions `backtest` workflow. A few minutes later the report appears.
4. **Compare** it against production on the same games: metrics, calibration, record by edge bucket.
5. **Promote** it to `candidate`, then `production`, only if it passes the go/no-go gates (the UI shows a checklist).

**Concept: backtest overfitting.** This is the main danger of a model lab. Try 50 variants and keep the best, and you've partly found the variant that got luckiest on those seasons, not the best model. Statisticians call it "multiple comparisons," or the garden of forking paths. Our protections:
- **Holdout seasons stay locked.** Day-to-day comparisons use validation seasons only. A holdout evaluation happens only at promotion, and the lab records each time it's used.
- **The lab shows how many variants have been tried** since the last production model, as a reminder to be skeptical of small improvements.
- **Prefer simple wins.** A variant that improves by 0.05 points of MAE after 30 tries is noise. We'll eventually put a rough significance check on comparisons.
- **Hand-set weights are for learning.** Fixing a weight by gut usually underperforms fitting it, and the backtest will show you that. That's a feature: it's one of the fastest ways to build intuition.

### Engineering contract
Every model implements the same interface, so backtests, production runs, the lab and the API treat them identically:

```python
class RatingModel(Protocol):
    def fit(self, games: GameHistory, as_of: datetime) -> Ratings: ...

class GamePredictor(Protocol):
    def predict(self, game: GameContext, ratings: Ratings, as_of: datetime) -> Prediction:
        """Returns pred_margin, margin_sd, home_win_prob, drivers."""
```

- `drivers` is a list of `(label, points)` contributions, such as "Home pass offense vs away pass defense: +3.1". The UI renders it as "why this pick."
- Models are pure functions of their inputs + `spec`. Same inputs + same spec give the same output, which is what makes versioning meaningful.
- The light "rating → prediction" math and `ModelSpec` validation live in `engine.core`, so the API can run hypothetical matchups and validate lab specs without the training stack.

## 7. Rankings beyond the betting model: seasons, programs, coaches

Built in Phase 6, after the betting model. Everything here reuses the rating machinery above; what changes is the question being asked.

### Two questions a ranking can answer
- **Predictive:** "who wins on a neutral field next week?" These are the weekly power ratings from §2. They weight recent games more and use only data from before kickoff.
- **Retrospective:** "who had the best season?" This has two versions:
  - **Best team (hindsight rating):** one rating fit on the whole season at once, every game weighted equally, no preseason prior blending. Because it looks back from the end, a September game is judged with the opponent's *final* strength, not the guess at the time.
  - **Best résumé (strength of record):** given a team's schedule, how likely is it that a benchmark team (the 25th-best that season) would have done at least as well? A 15-0 run against a hard schedule might be a 0.3% feat; 11-2 against a soft one might be 21%. Rank by that probability, lowest first. This is roughly what the CFP committee rewards, so the CFP odds model (§3) reuses it.

**Concept: retrodiction vs prediction.** Using the whole season to rate a team is fine when the question is about the past. It's leakage the moment a prediction uses it (§5). So hindsight ratings are their own *kind* of rating, stored separately, and the backtest harness and production predictions are tested to refuse them. The next season's preseason prior keeps using the predictive end-of-season rating, so the betting model's code path never touches hindsight ratings.

**Concept: Poisson binomial.** The chance of winning at least *k* of *n* games, where each game has its own win probability, has an exact answer. You build it up one game at a time (a small dynamic program), so strength of record needs no simulation.

### Comparing across seasons and eras
A rating means "points better than the average FBS team *that season*." Two things make +25 in 2008 and +25 in 2024 not quite equal: scoring environments change (2010s offenses widened margins), and the "average FBS team" changes as FBS grows. So history shows two scales:
- **Raw rating** (points), for comparisons within an era.
- **Within-season z-score / percentile**: `(rating − season mean) / season SD`, for comparisons across eras. A +2.8 z-score is "about as dominant relative to its season" whatever the year.

### Programs over a period
A program ranking summarizes its season-final hindsight ratings over a chosen span (e.g. 2014–2025, a decade, a conference era): average rating (the default sort), peak season, worst season, and top-10 finishes. These are aggregates of stored ratings, so they're views.

### Coaches
- **Raw ratings credit the coach for the program.** Alabama's baseline is not Vanderbilt's, so a coach's average team rating mostly measures where they work.
- **Value over expectation** is the default measure. For each season, `hindsight rating − preseason prior` (the §2 prior: last season regressed toward the mean, returning production, talent, recruiting). Average it over the coach's seasons. A positive number means their teams kept playing better than the roster and history predicted.
- **Why not compare before and after the hire?** Regression to the mean. A coach who inherits a fluke bad year looks like a turnaround artist for free. The prior already expects that rebound, so it doesn't give credit for it.
- **Shrink short tenures.** Four great seasons is weaker evidence than seventeen good ones. Pull each coach's average toward zero by an amount based on seasons coached, the same idea as ridge regression (§2).
- **The recruiting judgment call.** The prior includes talent and recruiting, but recruiting is partly the coach's own work, so controlling for it removes credit they earned. Show both: *controlling for recruiting* (coaching only) and *crediting recruiting* (a prior without talent or recruiting, so roster-building counts).
- **Partial seasons.** Mid-season firings and interim coaches need games attributed to the coach who coached them. Partial seasons count by the share of games coached, and tiny interim stints are shown but flagged as too small to judge.
- **Cheap extras for the coach page:** record against the spread, and record in close games (one score or less), which is mostly luck and worth showing as such.

### How far back
Scores go back to the 1800s; the play-level stats behind the efficiency model only go back to about the mid-2000s (exact year confirmed in Phase 1). Seasons before that use a **scores-only** hindsight rating (Rung 1 from §2, which works unchanged), and the UI labels which kind each season uses. Games and coach data are season-level API calls, so going back to the 1970s costs roughly 50–100 calls.

## 8. Learning path (you'll build these alongside the phases)

1. **Notebook: explore the data.** Margin distributions, home-field advantage over time, closing-line accuracy.
2. **Notebook: build Rung 1 by hand.** Least-squares ratings for one season, then see the ratings and residuals.
3. **Notebook: from ratings to probabilities.** σ, the normal CDF, and a first calibration plot.
4. **Backtest harness**: Rung 1 walk-forward over 2014–2023, then read the report.
5. **Rung 2**: ridge, priors, blending, and comparing reports.
6. **Pick logic + thresholds**: edge buckets, market shrinkage.

Recommended reading as we go: *The Logic of Sports Betting* (Miller & Davidow); Bill Connelly's SP+ methodology write-ups; CFBD blog tutorials (their opponent-adjusted stats and ridge regression posts follow this approach closely).
