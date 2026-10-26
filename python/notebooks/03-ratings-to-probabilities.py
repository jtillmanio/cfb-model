"""Notebook #3: from ratings to probabilities (docs/04-model.md § 1, § 4 and § 8, TASK-033).

A rating gap becomes a predicted margin, the margin a cover probability against the closing
spread, and the probability an expected value at −110, with `engine.core`'s functions (TASK-029).
Then a first calibration plot from the latest Rung 1 backtest in the lake. It reads the local
lake mirror and makes no API calls.

    uv run --group notebooks marimo edit notebooks/03-ratings-to-probabilities.py   # interactive
    uv run --group notebooks python notebooks/03-ratings-to-probabilities.py        # headless

The calibration plot needs a Rung 1 run in the lake first:
`uv run engine backtest --spec engine/specs/power-v1.json --seasons 2016-2023`.
"""

import marimo

__generated_with = "0.25.2"
app = marimo.App(width="medium")


@app.cell
def _():
    import io
    import json
    import os
    from pathlib import Path
    from statistics import NormalDist

    import marimo as mo
    import matplotlib.pyplot as plt
    import pyarrow.parquet as pq

    from db.config import repo_root
    from engine.backtest import harness
    from engine.backtest.metrics import grade
    from engine.core.probability import (
        NormalMargin,
        break_even,
        cover_probability,
        expected_value,
        win_probability,
    )
    from engine.core.spec import ModelSpec
    from engine.ingest.lake import open_lake
    from engine.models.power import PowerRatings
    from engine.sports.cfb.teams import RULES
    from engine.transform.market import closing_lines

    return (
        ModelSpec,
        NormalDist,
        NormalMargin,
        Path,
        PowerRatings,
        RULES,
        break_even,
        closing_lines,
        cover_probability,
        expected_value,
        grade,
        harness,
        io,
        json,
        mo,
        open_lake,
        os,
        plt,
        pq,
        repo_root,
        win_probability,
    )


@app.cell
def _(io, open_lake, os, pq, repo_root):
    lake = open_lake(os.environ.get("NOTEBOOK_LAKE_URI") or str(repo_root() / "data"))

    def staged(name):
        return pq.read_table(io.BytesIO(lake.read(f"staging/{name}.parquet")))

    games = staged("games")
    lines = staged("lines")
    names = {int(t["source_id"]): t["school"] for t in staged("teams").to_pylist()}
    return games, lake, lines, names


@app.cell
def _(mo):
    mo.md(
        """
        ## One game: LSU at Alabama, 9 November 2019

        Rung 1's ratings entering that week, with the settings the backtest chose for 2019
        (margin cap 38, recency half-life 16 weeks, prior regression 0.1, prior gone by week 12).
        """
    )
    return


@app.cell
def _(ModelSpec, PowerRatings, RULES, harness, lake, names):
    spec = ModelSpec.model_validate(
        {
            "base": "power",
            "hyperparameters": {"margin_cap": 38, "recency_half_life_weeks": 16},
            "prior": {
                "components": ["last_season"],
                "regression": 0.1,
                "decay": {"type": "linear", "zero_at_week": 12},
            },
            "picks": {"min_edge_pts": 3, "min_prob": 0.55, "tiers": {"A": 5, "B": 3.5, "C": 2.5}},
        }
    )
    model = PowerRatings(spec, RULES)
    history = harness.load(lake)
    ids = {school: team for team, school in names.items()}
    (week, game) = [
        (w, e)
        for w in history.weeks
        if w.season == 2019
        for e in w.games
        if (e.context.home_team, e.context.away_team) == (ids["Alabama"], ids["LSU"])
    ][0]
    ratings = model.fit(harness.fit_games(history, week.as_of), week.as_of)
    home = ratings.teams[game.context.home_team]
    away = ratings.teams[game.context.away_team]
    hfa = ratings.params["home_field"]
    sigma = ratings.params["margin_sd"]
    pred_margin = home - away + (0.0 if game.context.neutral_site else hfa)
    print(
        f"Alabama {home:+.1f}, LSU {away:+.1f}, home field {hfa:+.1f}: "
        f"Alabama by {pred_margin:.1f} (sigma {sigma:.1f})"
    )
    return game, pred_margin, sigma


@app.cell
def _(mo):
    mo.md(
        """
        ## From a margin to a probability

        The predicted margin is our best single guess, but games are noisy: the final margin
        lands around it roughly on a bell curve whose width **σ** is the model's typical miss.
        Rung 1 measures σ out of sample, as the root-mean-square error of its own week-by-week
        predictions last season. With a normal curve centred on the prediction:

        - **P(home wins)** is the area above 0.
        - **P(home covers)** against `spread_home` (negative when home is favoured) is the area
          above `−spread_home`: the home team must win by more than the spread.
        - **Edge** is `pred_margin + spread_home`: positive likes the home side.

        A bet at −110 risks 1.1 to win 1, so it breaks even at 110/210 = 52.4%, and its expected
        value per unit risked is `p × (100/110) − (1 − p)`.
        """
    )
    return


@app.cell
def _(
    NormalMargin,
    break_even,
    closing_lines,
    cover_probability,
    expected_value,
    game,
    games,
    lines,
    pred_margin,
    sigma,
    win_probability,
):
    closing = {r["game_source_id"]: r for r in closing_lines(games, lines).to_pylist()}
    spread_home = closing[game.source_id]["spread_home"]
    dist = NormalMargin(sigma)
    cover = cover_probability(pred_margin, spread_home, dist)
    ev = expected_value(cover.prob)
    print(f"Closing spread (home): {spread_home:+.1f}; edge {cover.edge:+.1f} for {cover.side}")
    print(f"P(Alabama wins) {win_probability(pred_margin, dist):.1%}")
    print(
        f"P({cover.side} covers) {cover.prob:.1%} vs break-even {break_even():.1%}: "
        f"EV {ev:+.3f} units per unit risked"
    )
    print(f"Final: Alabama {game.home_points}, LSU {game.away_points}")
    return dist, spread_home


@app.cell
def _(NormalDist, dist, plt, pred_margin, sigma, spread_home):
    _curve = NormalDist(pred_margin, sigma)
    _xs = [pred_margin + sigma * (i / 50 - 4) for i in range(401)]
    _line = -spread_home
    _covers = [x for x in _xs if x > _line]
    _fig, _ax = plt.subplots(figsize=(8, 3.5))
    _ax.plot(_xs, [_curve.pdf(x) for x in _xs], color="#4a6fa5")
    _ax.fill_between(_covers, [_curve.pdf(x) for x in _covers], alpha=0.3)
    _ax.axvline(_line, color="grey", linewidth=0.8)
    _ax.set(
        xlabel="Home margin (pts)",
        ylabel="Density",
        title=f"Shaded: home covers ({dist.prob_above(pred_margin, _line):.0%})",
    )
    _fig.tight_layout()
    _fig
    return


@app.cell
def _(mo):
    mo.md(
        """
        ## A first calibration plot

        If the model says 60%, does that side cover 60% of the time? Take every game of the
        latest Rung 1 backtest, compute the cover probability for the side the model likes,
        bin it, and compare with how often that side actually covered (pushes left out). Points
        under the diagonal are **overconfident**: the model disagrees with the market more than
        it should. That's the winner's curse of § 4, and the reason picks shrink toward the
        market (`market_shrinkage_k`) before trusting a probability.
        """
    )
    return


@app.cell
def _(ModelSpec, Path, harness, io, json, lake, pq, repo_root):
    _spec = ModelSpec.model_validate_json(
        (Path(repo_root()) / "python/engine/specs/power-v1.json").read_text("utf-8")
    )
    _hash = harness.spec_hash(_spec)
    _metas = {
        key.removesuffix("/run.json"): json.loads(lake.read(key))
        for key in lake.walk("backtests")
        if key.endswith("/run.json")
    }
    _runs = sorted(
        folder
        for folder, meta in _metas.items()
        if meta["spec_hash"] == _hash and meta["model"] == "power"
    )
    run_rows = (
        pq.read_table(io.BytesIO(lake.read(f"{_runs[-1]}/predictions.parquet"))).to_pylist()
        if _runs
        else []
    )
    print(f"Latest power-v1 run: {_runs[-1] if _runs else 'none in the lake yet'}")
    return (run_rows,)


@app.cell
def _(NormalMargin, cover_probability, grade, plt, run_rows):
    _bins = [0.5, 0.525, 0.55, 0.575, 0.6, 0.625, 0.65, 1.0]
    _points = []
    for _lo, _hi in zip(_bins, _bins[1:], strict=False):
        _graded = []
        for _r in run_rows:
            _dist = NormalMargin(_r["margin_sd"])
            _c = cover_probability(_r["pred_margin"], _r["spread_home"], _dist)
            if _lo <= _c.prob < _hi:
                _result = grade(_c.side, _r["margin"], _r["spread_home"])
                if _result != "P":
                    _graded.append((_c.prob, _result == "W"))
        if _graded:
            _points.append(
                (
                    sum(p for p, _ in _graded) / len(_graded),
                    sum(w for _, w in _graded) / len(_graded),
                    len(_graded),
                )
            )
    for _pred, _hit, _n in _points:
        print(f"predicted {_pred:.1%}  actual {_hit:.1%}  ({_n} games)")
    _fig, _ax = plt.subplots(figsize=(5, 5))
    _ax.plot([0.5, 0.8], [0.5, 0.8], color="grey", linewidth=0.8)
    _ax.scatter([p[0] for p in _points], [p[1] for p in _points], s=[p[2] / 10 for p in _points])
    _ax.set(xlabel="Predicted cover %", ylabel="Actual cover %", title="Rung 1 calibration")
    _fig.tight_layout()
    _fig
    return


if __name__ == "__main__":
    app.run()
