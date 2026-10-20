"""Notebook #1: explore the data (docs/04-model.md § 8, TASK-021).

Home-field advantage by season, the margin distribution, and the closing line's error: the
benchmark every later model is measured against (04 § 9.6). It reads the local lake mirror's
`staging/` (built by `engine transform --rebuild`) and makes no API calls.

    uv run --group notebooks marimo edit notebooks/01-explore.py   # interactive
    uv run --group notebooks python notebooks/01-explore.py        # top to bottom, headless
"""

import marimo

__generated_with = "0.25.2"
app = marimo.App(width="medium")


@app.cell
def _():
    import io
    import os

    import duckdb
    import marimo as mo
    import matplotlib.pyplot as plt
    import pyarrow.parquet as pq

    from db.config import repo_root
    from engine.ingest.lake import open_lake
    from engine.transform.market import closing_lines

    return closing_lines, duckdb, io, mo, open_lake, os, plt, pq, repo_root


@app.cell
def _(io, open_lake, os, pq, repo_root):
    # The local mirror (`engine lake sync`), unless NOTEBOOK_LAKE_URI points elsewhere.
    lake = open_lake(os.environ.get("NOTEBOOK_LAKE_URI") or str(repo_root() / "data"))

    def staged(name):
        return pq.read_table(io.BytesIO(lake.read(f"staging/{name}.parquet")))

    games = staged("games")
    lines = staged("lines")
    return games, lines


@app.cell
def _(closing_lines, duckdb, games, lines):
    closing = closing_lines(games, lines)
    db = duckdb.connect()
    db.register("games", games)
    db.register("closing", closing)
    # Final FBS-vs-FBS games, 2014-2025: the games every metric in 04 § 9.3 is graded on.
    db.execute(
        """
        CREATE VIEW eligible AS
        SELECT g.*, g.home_points - g.away_points AS margin
        FROM games g
        WHERE g.status = 'final' AND g.season BETWEEN 2014 AND 2025
          AND g.home_classification = 'fbs' AND g.away_classification = 'fbs'
        """
    )
    return (db,)


@app.cell
def _(mo):
    mo.md(
        """
        ## Home-field advantage by season

        `margin = home_points − away_points`. On a neutral field there is no home team, so
        those games are left out. The mean margin of the rest is the raw home-field advantage:
        it mixes in that home teams are, on average, a little better (they schedule weaker
        visitors), so a rating model fits a smaller value once team strength is accounted for.
        """
    )
    return


@app.cell
def _(db):
    hfa = db.sql(
        """
        SELECT season, count(*) AS games, round(avg(margin), 2) AS mean_margin,
            round(avg((margin > 0)::INT), 3) AS home_win_rate
        FROM eligible WHERE NOT neutral_site
        GROUP BY season ORDER BY season
        """
    ).fetchall()
    hfa
    return (hfa,)


@app.cell
def _(hfa, plt):
    _fig, _ax = plt.subplots(figsize=(8, 3.5))
    _ax.plot([r[0] for r in hfa], [r[2] for r in hfa], marker="o")
    _ax.axhline(0, color="grey", linewidth=0.8)
    _ax.set(xlabel="Season", ylabel="Mean home margin (pts)", title="Home-field advantage")
    _fig.tight_layout()
    _fig
    return


@app.cell
def _(mo):
    mo.md(
        """
        ## The margin distribution

        Football scores move in 3s and 7s, so margins pile up on 3, 7, 10 and 14. That's why a
        spread of −3 and −3.5 are very different bets, and why the model will simulate a margin
        distribution instead of assuming a smooth bell curve (04 § 3).
        """
    )
    return


@app.cell
def _(db, plt):
    margins = [r[0] for r in db.sql("SELECT margin FROM eligible").fetchall()]
    _fig, _ax = plt.subplots(figsize=(8, 3.5))
    _ax.hist(margins, bins=range(-70, 72), color="#4a6fa5")
    _ax.set(xlabel="Home margin (pts)", ylabel="Games", title="Final FBS-vs-FBS margins, 2014-2025")
    _fig.tight_layout()
    _fig
    return (margins,)


@app.cell
def _(margins):
    _n = len(margins)
    key_numbers = {k: round(sum(abs(m) == k for m in margins) / _n, 3) for k in (1, 3, 7, 10, 14)}
    key_numbers  # share of games decided by exactly this many points
    return


@app.cell
def _(mo):
    mo.md(
        """
        ## The closing line's error: the benchmark

        The closing spread is the market's last prediction before kickoff. Its predicted home
        margin is `−spread_home`, so its error on a game is `|margin + spread_home|`. The mean of
        that over 2014-2025 is the number every model is compared with (04 § 9.6). The closing
        line is CFBD's close (each book's first pull after kickoff), else the last pull before
        it; the `consensus` book's spread when it quoted one, else the median across books
        (04 § 9.3, D-120).
        """
    )
    return


@app.cell
def _(db):
    by_season = db.sql(
        """
        SELECT e.season, count(*) AS eligible, count(c.spread_home) AS with_line,
            round(avg(abs(e.margin + c.spread_home)), 3) AS mae,
            count(*) FILTER (WHERE c.source = 'consensus') AS consensus,
            count(*) FILTER (WHERE c.source = 'median') AS median
        FROM eligible e LEFT JOIN closing c ON c.game_source_id = e.source_id
        GROUP BY e.season ORDER BY e.season
        """
    ).fetchall()
    by_season  # (season, eligible, with a closing spread, MAE, consensus, median)
    return


@app.cell
def _(db, mo):
    games_scored, pooled_mae = db.sql(
        """
        SELECT count(*), avg(abs(e.margin + c.spread_home))
        FROM eligible e JOIN closing c ON c.game_source_id = e.source_id
        WHERE c.spread_home IS NOT NULL
        """
    ).fetchone()
    _benchmark = f"Pooled closing-line MAE, 2014-2025: {pooled_mae:.3f} points"
    print(f"{_benchmark} over {games_scored:,} games.")  # the headless run's record
    mo.md(f"**{_benchmark}** over {games_scored:,} games.")
    return


if __name__ == "__main__":
    app.run()
