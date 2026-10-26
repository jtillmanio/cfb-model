"""Notebook #2: build Rung 1 by hand (docs/04-model.md § 2 Rung 1 and § 8, TASK-033).

One week's power ratings solved from the least-squares equations written out, then checked
against the engine's `PowerRatings` for the same week (they must agree within 0.01 points). It
reads the local lake mirror's `staging/` and `features/` and makes no API calls.

    uv run --group notebooks marimo edit notebooks/02-ratings-by-hand.py   # interactive
    uv run --group notebooks python notebooks/02-ratings-by-hand.py        # top to bottom
"""

import marimo

__generated_with = "0.25.2"
app = marimo.App(width="medium")


@app.cell
def _():
    import io
    import os
    from datetime import timedelta

    import marimo as mo
    import matplotlib.pyplot as plt
    import numpy as np
    import pyarrow.parquet as pq

    from db.config import repo_root
    from engine.backtest import harness
    from engine.core.spec import ModelSpec
    from engine.ingest.lake import open_lake
    from engine.models.power import PowerRatings
    from engine.sports.cfb.teams import RULES

    return (
        ModelSpec,
        PowerRatings,
        RULES,
        harness,
        io,
        mo,
        np,
        open_lake,
        os,
        plt,
        pq,
        repo_root,
        timedelta,
    )


@app.cell
def _(io, open_lake, os, pq, repo_root):
    # The local mirror (`engine lake sync`), unless NOTEBOOK_LAKE_URI points elsewhere.
    lake = open_lake(os.environ.get("NOTEBOOK_LAKE_URI") or str(repo_root() / "data"))
    teams = pq.read_table(io.BytesIO(lake.read("staging/teams.parquet"))).to_pylist()
    names = {int(t["source_id"]): t["school"] for t in teams}
    return lake, names


@app.cell
def _(mo):
    mo.md(
        """
        ## The idea: one equation per game

        Give every team one number, its rating, so that for any game

        `predicted_margin = rating_home − rating_away + HFA × (not neutral_site)`

        Each finished game is one equation. With ~130 FBS teams and a few hundred games by
        mid-season there are more equations than unknowns, so no ratings fit every game.
        **Least squares** picks the ratings with the smallest total squared error, and that
        adjusts for opponents for free: beating a strong team by 3 says more than beating a weak
        one by 3, because the opponent's rating is in the equation.

        We solve 2019's ratings **entering week 5** with the settings the backtest chose for
        2019, the way the engine does, then check the engine gets the same numbers.
        """
    )
    return


@app.cell
def _(ModelSpec, PowerRatings, RULES):
    SEASON, WEEK = 2019, 5
    # What the backtest tuned for 2019 (engine/specs/power-v1.json, tuned on 2015-2018).
    CAP, HALF_LIFE, REGRESSION, ZERO_AT_WEEK = 38.0, 16.0, 0.1, 12.0
    spec = ModelSpec.model_validate(
        {
            "base": "power",
            "hyperparameters": {"margin_cap": CAP, "recency_half_life_weeks": HALF_LIFE},
            "prior": {
                "components": ["last_season"],
                "regression": REGRESSION,
                "decay": {"type": "linear", "zero_at_week": ZERO_AT_WEEK},
            },
            "picks": {"min_edge_pts": 3, "min_prob": 0.55, "tiers": {"A": 5, "B": 3.5, "C": 2.5}},
        }
    )
    engine_model = PowerRatings(spec, RULES)
    return CAP, HALF_LIFE, REGRESSION, SEASON, WEEK, ZERO_AT_WEEK, engine_model


@app.cell
def _(SEASON, WEEK, harness, lake, timedelta):
    history = harness.load(lake)
    (week,) = [
        w
        for w in history.weeks
        if (w.season, w.season_type, w.week) == (SEASON, "regular", WEEK)
    ]
    as_of = week.as_of
    # What a fit entering the week may see: every game that finished (kickoff + 4 h) by as_of.
    seen = harness.fit_games(history, as_of)
    this_season = [g for g in seen if g.season == SEASON]
    last_season = [g for g in history.results if g.season == SEASON - 1]
    last_end = max(g.kickoff for g in last_season) + timedelta(hours=4)
    print(f"Entering {SEASON} week {WEEK} ({as_of:%Y-%m-%d %H:%M} UTC): {len(this_season)} games")
    return as_of, last_end, last_season, seen, this_season


@app.cell
def _(mo):
    mo.md(
        """
        ## Writing the equations down

        Number the things we rate: every FBS team on its own, plus **one pooled rating for all
        FCS teams** (an FCS team plays one or two FBS teams a season, too few games to rate it
        alone), plus home-field advantage. Each game is a row of a matrix **X**: +1 in the home
        team's column, −1 in the away team's, 1 in the HFA column unless the site is neutral.
        **y** holds the margins, capped at ±38 (a 63–0 rout isn't nine times as informative as
        a 7-point win). **W** weights each game, halving every 16 weeks back, so recent games
        count more.

        Least squares minimises `Σ w·(y − X·r)²`. Setting its derivative to zero gives the
        **normal equations**

        `XᵀWX · r = XᵀW · y`

        but ratings have no natural zero: add 5 to every team and no prediction changes, so
        `XᵀWX` is singular. We add one more equation, **the FBS ratings average zero**, with a
        Lagrange multiplier λ:

        ```
        [ XᵀWX  c ] [ r ]   [ XᵀWy ]
        [ cᵀ    0 ] [ λ ] = [  0   ]
        ```

        where `c` is 1 for each FBS team and 0 for the FCS pool and HFA. Now there's one
        answer, and a rating means "points better than the average FBS team".
        """
    )
    return


@app.cell
def _(CAP, HALF_LIFE, RULES, np):
    def unit(team, classification):
        """A team id, or the pool it's rated in."""
        return RULES.pool(classification) or team

    def solve_by_hand(games, as_of):
        """The in-season ratings and HFA, from the bordered normal equations."""
        units = sorted(
            {unit(g.home_team, g.home_classification) for g in games}
            | {unit(g.away_team, g.away_classification) for g in games},
            key=lambda u: (isinstance(u, str), str(u)),
        )
        col = {u: i for i, u in enumerate(units)}
        k = len(units)
        X = np.zeros((len(games), k + 1))
        y = np.zeros(len(games))
        w = np.zeros(len(games))
        for i, g in enumerate(games):
            X[i, col[unit(g.home_team, g.home_classification)]] = 1
            X[i, col[unit(g.away_team, g.away_classification)]] = -1
            X[i, k] = 0 if g.neutral_site else 1
            y[i] = max(-CAP, min(CAP, g.margin))
            weeks_ago = (as_of - g.kickoff).total_seconds() / (7 * 24 * 3600)
            w[i] = 0.5 ** (weeks_ago / HALF_LIFE)
        XtWX = X.T @ (w[:, None] * X)
        XtWy = X.T @ (w * y)
        c = np.array([0.0 if isinstance(u, str) else 1.0 for u in units] + [0.0])
        bordered = np.block([[XtWX, c[:, None]], [c[None, :], np.zeros((1, 1))]])
        solution = np.linalg.solve(bordered, np.append(XtWy, 0.0))
        ratings = dict(zip(units, solution[:k], strict=True))
        return ratings, float(solution[k]), X, y, w

    return solve_by_hand, unit


@app.cell
def _(mo):
    mo.md(
        """
        ## The prior: last season, regressed

        In week 2 a team has played one game, and least squares would rate it on that game
        alone. So each rating starts from a **prior**, last season's final rating pulled toward
        the average (**regression to the mean**: some of last year's extremeness was luck, some
        of the roster left), and this season's games take over week by week:

        `rating = w·prior + (1 − w)·in_season`, with `w = (Z − N)/(Z − 1)`, clamped to [0, 1]

        N is 1 + the weeks played so far and Z (here 12) is the week the prior's weight reaches
        zero. Last season's final rating is the same least-squares fit on all of last season's
        games (by its end, w is 0, so the 2017 prior has no say). A team with no rating last
        season starts from the FCS pool's prior: every team that joined FBS since 2014 moved up
        from FCS.
        """
    )
    return


@app.cell
def _(
    REGRESSION,
    ZERO_AT_WEEK,
    last_end,
    last_season,
    solve_by_hand,
    this_season,
    as_of,
):
    final, final_hfa, _, _, _ = solve_by_hand(last_season, last_end)
    prior = {u: (1 - REGRESSION) * r for u, r in final.items()}
    newcomer = prior["fcs"]
    in_season, in_season_hfa, X, y, w_games = solve_by_hand(this_season, as_of)
    weeks_played = len({(g.season_type, g.week) for g in this_season})
    w = min(1.0, max(0.0, (ZERO_AT_WEEK - (weeks_played + 1)) / (ZERO_AT_WEEK - 1)))
    by_hand = {u: w * prior.get(u, newcomer) + (1 - w) * r for u, r in in_season.items()}
    hfa = w * final_hfa + (1 - w) * in_season_hfa
    print(f"Weeks played {weeks_played}, so w = {w:.3f}; HFA {hfa:.2f} points")
    return X, by_hand, hfa, in_season, in_season_hfa, prior, y


@app.cell
def _(as_of, by_hand, engine_model, hfa, seen):
    engine_ratings = engine_model.fit(seen, as_of)
    gaps = [abs(engine_ratings.teams[t] - r) for t, r in by_hand.items() if isinstance(t, int)]
    gaps.append(abs(engine_ratings.params["pool_fcs"] - by_hand["fcs"]))
    gaps.append(abs(engine_ratings.params["home_field"] - hfa))
    biggest = max(gaps)
    assert biggest < 0.01, f"the hand solve is {biggest:.4f} points off the engine"
    print(f"By hand vs the engine: largest gap {biggest:.2e} points over {len(gaps)} numbers")
    return (engine_ratings,)


@app.cell
def _(mo):
    mo.md(
        """
        ## Spot check: 2019's top 10 entering week 5

        Does it pass the smell test? 2019 was LSU's and Ohio State's year, with Clemson,
        Alabama and Oklahoma close behind.
        """
    )
    return


@app.cell
def _(by_hand, names, prior):
    ranked = sorted(((r, t) for t, r in by_hand.items() if isinstance(t, int)), reverse=True)
    top10 = [
        (i + 1, names.get(t, t), round(r, 1), round(prior.get(t, float("nan")), 1))
        for i, (r, t) in enumerate(ranked[:10])
    ]
    for _row in top10:
        print("{:>2}. {:<20} {:>6} (prior {})".format(*_row))
    top10  # (rank, team, rating, its prior)
    return


@app.cell
def _(mo):
    mo.md(
        """
        ## Residuals

        What least squares couldn't explain: each game's capped margin minus the in-season fit's
        prediction. Their spread is roughly the noise in a single game's result; the model will
        never get below it.
        """
    )
    return


@app.cell
def _(X, in_season, in_season_hfa, np, plt, y):
    residuals = y - X @ np.array([*in_season.values(), in_season_hfa])
    _fig, _ax = plt.subplots(figsize=(8, 3.5))
    _ax.hist(residuals, bins=30, color="#4a6fa5")
    _ax.set(xlabel="Residual (pts)", ylabel="Games", title="In-season residuals, 2019 weeks 1-4")
    _fig.tight_layout()
    print(f"Residual standard deviation: {residuals.std(ddof=1):.1f} points")
    _fig
    return


if __name__ == "__main__":
    app.run()
