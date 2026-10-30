"""The backtest report (TASK-031): every § 9.4 row a run supports, each gate marked pass, fail or
n/a, written as `report.md` and `report.html` from one structure (`build`), so the two can't
disagree (docs/04-model.md § 9.4). The Performance and Lab screens draw the same numbers later
(M7); this is the engine's own read-out.
"""

from __future__ import annotations

import html
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from engine.backtest import metrics as m
from engine.backtest.pick_rules import FLOOR
from engine.core.spec import ModelSpec, fixed

if TYPE_CHECKING:
    from engine.backtest.compare import Versus

FILES = ("report.md", "report.html")
DASH = "—"


@dataclass(frozen=True, slots=True)
class Table:
    header: tuple[str, ...]
    rows: tuple[tuple[str, ...], ...]


@dataclass(frozen=True, slots=True)
class Section:
    title: str
    lines: tuple[str, ...] = ()  # sentences shown above the tables
    tables: tuple[Table, ...] = ()


@dataclass(frozen=True, slots=True)
class Document:
    title: str
    facts: tuple[tuple[str, str], ...]  # what was run
    sections: tuple[Section, ...] = field(default_factory=tuple)


def pct(x: float | None, digits: int = 1) -> str:
    return DASH if x is None else f"{x * 100:.{digits}f}%"


def pts(x: float | None, signed: bool = False) -> str:
    if x is None:
        return DASH
    return f"{x:+.2f}" if signed else f"{x:.2f}"


def mark(gate: m.Gate) -> str:
    return {"pass": "PASS", "fail": "FAIL", "n/a": "n/a"}[gate.status]


def record_cells(r: m.Record) -> tuple[str, str, str, str]:
    """Record, win % (pushes left out), units at −110, ROI."""
    roi = DASH if r.roi is None else f"{r.roi * 100:+.1f}%"
    return str(r), pct(r.win_pct), f"{r.units:+.1f}u", roi


def interval_text(bounds: tuple[float, float] | None) -> str:
    return DASH if bounds is None else f"{pct(bounds[0])} to {pct(bounds[1])}"


def _gates(metrics: m.Metrics) -> Section:
    rows = tuple((name, mark(g), g.detail) for name, g in metrics.gates)
    return Section(
        "Gates",
        ("The go/no-go targets of docs/04-model.md § 9.4 (D-077). n/a: the run can't decide it.",),
        (Table(("Gate", "Result", "Detail"), rows),),
    )


def _accuracy(a: m.Accuracy, title: str = "Margin accuracy vs the closing line") -> Section:
    gap = a.gap_interval
    spread = DASH if gap is None else f"{gap.low:+.2f} to {gap.high:+.2f}"
    rows = (
        ("Games", str(a.games)),
        ("Model MAE", pts(a.mae)),
        ("Closing-line MAE", pts(a.closing_mae)),
        ("MAE gap (model − closing)", pts(a.gap, signed=True)),
        ("MAE gap, 95% week bootstrap", spread),
        ("Model RMSE", pts(a.rmse)),
        ("Closing-line RMSE", pts(a.closing_rmse)),
    )
    return Section(
        title,
        (f"Gate: {mark(a.gate)}. {a.gate.detail}.",),
        (Table(("Metric", "Points"), rows),),
    )


def _ats(metrics: m.Metrics) -> Section:
    record, win, units, roi = record_cells(metrics.picks)
    rows = (
        ("Record (W-L-P)", record),
        ("Win % (pushes excluded)", win),
        ("Win %, 95% interval", interval_text(metrics.picks.interval)),
        ("Units at −110", units),
        ("ROI", roi),
    )
    gate = metrics.ats_gate
    return Section(
        "ATS vs the closing line",
        (
            f"Gate: {mark(gate)}. {gate.detail}.",
            "Qualifying picks under each season's pick rules. A win is +1.0u and a loss −1.1u; "
            "a push is refunded, so ROI is units over the 1.1u risked on each win or loss.",
        ),
        (Table(("Metric", "Value"), rows),),
    )


def _pick_rules(run: Mapping[str, Any]) -> Section | None:
    """Each season's pick rules and the tuning-season picks behind them (TASK-039), for a spec
    that tunes its pick rules: none otherwise, so a fixed spec's report is unchanged."""
    tuning = run.get("pick_tuning")
    if not tuning:
        return None

    spec = ModelSpec.model_validate(run["spec"])
    rows = []
    for season, choices in sorted(run["choices"].items(), key=lambda sc: int(sc[0])):
        rules = spec.resolve(choices).picks
        tuned_on = run.get("tuned_on", {}).get(season, [])
        picked = tuning.get(season)
        rows.append(
            (
                str(season),
                f"{tuned_on[0]}–{tuned_on[-1]}" if tuned_on else DASH,
                f"{fixed(rules.market_shrinkage_k, 'k'):g}",
                f"{fixed(rules.display_shrinkage_k, 'display k'):g}",
                f"{fixed(rules.min_edge_pts, 'min_edge_pts'):g}",
                pct(fixed(rules.min_prob, "min_prob")),
                " / ".join(
                    f"{fixed(t, 'tier'):g}" for t in (rules.tiers.A, rules.tiers.B, rules.tiers.C)
                ),
                DASH if picked is None else str(picked["picks"]),
                DASH if picked is None else ("yes" if picked["floor_met"] else "no"),
            )
        )
    return Section(
        "Pick rules by season",
        (
            "Each season's pick rules, chosen on its tuning seasons only (04 § 9.1): "
            "market shrinkage k by the lowest cover Brier score, then the thresholds by ATS win % "
            f"among choices with at least {FLOOR} graded picks there; with none, the choice with "
            "the most picks (TASK-039). Edges and tiers are on the blended margin. Display k "
            "shrinks only the cover probability shown, chosen last by the lowest cover Brier: it "
            "never changes a pick (TASK-042).",
        ),
        (
            Table(
                (
                    "Season",
                    "Tuned on",
                    "Shrinkage k",
                    "Display k",
                    "Min edge (pts)",
                    "Min cover",
                    "Tiers A / B / C (pts)",
                    "Tuning-season picks",
                    f"{FLOOR}+",
                ),
                tuple(rows),
            ),
        ),
    )


def _bucket_table(buckets: Sequence[m.Bucket], first: str) -> Table:
    rows = tuple((b.label, *record_cells(b.record)[:2]) for b in buckets)
    return Table((first, "Record", "Win %"), rows)


def _edge_trend(t: m.EdgeTrend) -> Section:
    gate = t.gate
    return Section(
        "Edge trend",
        (
            f"Gate: {mark(gate)}. {gate.detail}.",
            f"Every eligible game ({t.games} graded): does the side the edge likes cover, "
            "regressed on the edge size (logistic). One bucket may dip.",
        ),
        (_bucket_table(t.buckets, "Edge (pts)"),),
    )


def _consistency(c: m.Consistency) -> Section:
    gate = c.gate
    rows = tuple((str(s), *record_cells(r)[:2]) for s, r in c.seasons)
    return Section(
        "Consistency",
        (f"Gate: {mark(gate)}. {gate.detail}.",),
        (Table(("Season", "Record", "Win %"), rows),),
    )


def _calibration(c: m.Calibration) -> Section:
    gate = c.gate
    rows = tuple(
        (
            b.label,
            str(b.count),
            pct(b.mean_prob),
            pct(b.hit_rate),
            DASH if b.off is None else f"{b.off:+.1f}",
        )
        for b in c.bins
    )
    return Section(
        "Calibration",
        (
            f"Gate: {mark(gate)}. {gate.detail}.",
            "The cover probability the app displays for the side the model likes, after market "
            "and display shrinkage, on every eligible game. "
            f"Bins of {m.CALIBRATION_MIN_PICKS}+ must be within ±{m.CALIBRATION_TOLERANCE:g} "
            "points; above zero is overconfident.",
        ),
        (Table(("Predicted", "Games", "Mean predicted", "Actual", "Off (pts)"), rows),),
    )


def _opening(o: m.OpeningLine, games: int) -> Section:
    record, win, units, roi = record_cells(o.picks)
    warning = " Warning: average CLV is at or below zero." if o.warning else ""
    if not o.games:
        warning = " No game in this run has an opening line, so there's no CLV to measure."
    rows = (
        ("Games with an opening line", f"{o.games} of {games}"),
        ("Picks at the opener (W-L-P)", record),
        ("Win % at the opener", win),
        ("Units at −110", units),
        ("ROI", roi),
        ("Average CLV (pts)", pts(o.clv, signed=True)),
    )
    return Section(
        "Opening line and CLV",
        (
            "Picks made at the opening line, graded at it; CLV is how many points that line beat "
            "the same books' close by (04 § 9.3, D-132). Target: average CLV above zero."
            f"{warning}",
        ),
        (Table(("Metric", "Value"), rows),),
    )


def _pick_buckets(buckets: Sequence[m.Bucket]) -> Section:
    return Section(
        "Win % by pick bucket",
        ("Picks only, by edge size. Display only: the edge-trend gate uses every game.",),
        (_bucket_table(buckets, "Edge (pts)"),),
    )


def _contest(c: m.Contest) -> Section:
    record, win, _, _ = record_cells(c.record)
    warning = (
        f" Warning: the gap is over {m.CONTEST_GAP:g} points, the winner's curse (04 § 4)."
        if c.warning
        else ""
    )
    rows = (
        ("Weeks", str(c.weeks)),
        ("Record (W-L-P)", record),
        ("Hit rate", win),
        ("Average predicted cover", pct(c.mean_prob)),
        ("Predicted − actual (pts)", DASH if c.gap is None else f"{c.gap:+.1f}"),
    )
    return Section(
        f"Contest top {m.CONTEST_PICKS}",
        (
            f"Each week's top {m.CONTEST_PICKS} by cover probability against the close, pooled. "
            f"Target: hit rate above 50% and predicted − actual at most {m.CONTEST_GAP:g} points."
            f"{warning}",
        ),
        (Table(("Metric", "Value"), rows),),
    )


def _win_probability(w: m.WinProbability) -> Section:
    rows = (
        ("Games", str(w.games)),
        ("Brier score, model", f"{w.brier:.4f}"),
        ("Brier score, market-implied", f"{w.market_brier:.4f}"),
        ("Difference (model − market)", f"{w.brier - w.market_brier:+.4f}"),
    )
    return Section(
        "Win probability",
        (
            "The Brier score of `home_win_prob` (lower is better), beside the closing line's "
            "implied probability on each game's own distribution.",
        ),
        (Table(("Metric", "Value"), rows),),
    )


def _breakdowns(breakdowns: Sequence[m.Breakdown]) -> Section:
    tables = []
    for b in breakdowns:
        rows = tuple(
            (
                g.label,
                str(g.games),
                pts(g.mae),
                pts(g.closing_mae),
                pts(g.mae - g.closing_mae, signed=True),
                *record_cells(g.picks)[:2],
            )
            for g in b.groups
        )
        header = (b.name, "Games", "Model MAE", "Closing MAE", "Gap", "Picks", "Win %")
        tables.append(Table(header, rows))
    return Section("Breakdowns", ("Reported, not gated.",), tuple(tables))


LABELS = {
    "home_field": "Home field only",
    "last_season": "Last season carried over",
    "closing_line": "Closing line",
    "sp": "SP+",
    "fpi": "FPI",
}


def _comparison(versus: Sequence[Versus], model: str) -> Section:
    """The model against each Rung 0 baseline on the same games (04 § 9.5-9.6)."""
    rows = []
    for v in versus:
        d = v.difference
        verdict = ("beats it" if v.beats else "doesn't beat it") if v.bar else "reported only"
        if d is None:
            verdict = "no game to compare"
        notes = [f"{n} dropped: {count}" for n, count in v.dropped.items()]
        if v.unseen:
            notes.append(f"unseen team kept: {v.unseen}")
        rows.append(
            (
                LABELS.get(v.name, v.name),
                str(v.games),
                pts(v.mae),
                pts(v.model_mae),
                DASH if d is None else f"{d.estimate:+.2f} ({d.low:+.2f} to {d.high:+.2f})",
                verdict,
                "; ".join(notes) or DASH,
            )
        )
    bars = [v for v in versus if v.bar]
    passed = bool(bars) and all(v.beats for v in bars)
    return Section(
        "Comparison with the baselines",
        (
            f"Bar (04 § 9.6): {'PASS' if passed else 'FAIL'}. {model} must have a lower MAE than "
            "home field only and last season carried over: the 95% interval of a week-level "
            "paired bootstrap of its absolute error minus theirs entirely below zero (§ 9.5). "
            "The closing line and SP+/FPI are reported alongside.",
            "Each baseline ran with the settings this run chose for each season. Hindsight "
            "benchmarks and games with an unrated team are left out of that baseline's row "
            "(and of the model's MAE beside it); unseen-team games are kept.",
        ),
        (
            Table(
                (
                    "Baseline",
                    "Games",
                    "Baseline MAE",
                    f"{model} MAE",
                    "Difference (95% interval)",
                    f"{model}",
                    "Notes",
                ),
                tuple(rows),
            ),
        ),
    )


def _postseason(s: m.Summary) -> Section:
    acc = _accuracy(s.accuracy, "Postseason on its own")
    record, win, units, roi = record_cells(s.picks)
    rows = (
        ("Picks (W-L-P)", record),
        ("Win %", win),
        ("Units at −110", units),
        ("ROI", roi),
        ("Brier score, model", f"{s.win_probability.brier:.4f}"),
        ("Brier score, market-implied", f"{s.win_probability.market_brier:.4f}"),
    )
    return Section(
        acc.title,
        ("Bowls and the CFP, also counted in every pooled row above. Reported, not gated.",),
        (*acc.tables, Table(("Metric", "Value"), rows)),
    )


COVER_CURVES = {
    "normal": "normal margin with each game's σ (margin_sd)",
    "empirical": (
        "empirical margin: each game's σ (margin_sd) and its season's key-number weights "
        "(margin_weights), pushes left out"
    ),
}


def _distribution(run: Mapping[str, Any]) -> str:
    spec = run.get("spec")
    return str(spec.get("distribution", "normal")) if isinstance(spec, Mapping) else "normal"


def build(
    metrics: m.Metrics, run: Mapping[str, Any], comparison: Sequence[Versus] = ()
) -> Document:
    """The report for one run: `run` is its `run.json` fields plus the lake `folder`, and
    `comparison` the baselines it was compared with, if any."""
    first, last = metrics.seasons[0], metrics.seasons[-1]
    facts = (
        ("Model", str(run.get("model", DASH))),
        ("Spec hash", str(run.get("spec_hash", DASH))[:12]),
        ("Seasons", str(first) if first == last else f"{first}–{last}"),
        ("Tuned from", str(run.get("tune_from", DASH))),
        ("Games", str(metrics.games)),
        ("Holdout opened", "yes" if metrics.holdout else "no"),
        ("Results", f"{run['folder']}/predictions.parquet" if "folder" in run else DASH),
        ("Cover probabilities", COVER_CURVES[_distribution(run)]),
    )
    pick_rules = _pick_rules(run)
    sections = [
        *([_comparison(comparison, str(run.get("model", "Model")))] if comparison else []),
        _gates(metrics),
        _accuracy(metrics.accuracy),
        _ats(metrics),
        *([pick_rules] if pick_rules else []),
        _edge_trend(metrics.edge_trend),
        _consistency(metrics.consistency),
        _calibration(metrics.calibration),
        _opening(metrics.opening, metrics.games),
        _pick_buckets(metrics.pick_buckets),
        _contest(metrics.contest),
        _win_probability(metrics.win_probability),
        _breakdowns(metrics.breakdowns),
    ]
    if metrics.postseason is not None:
        sections.append(_postseason(metrics.postseason))
    return Document("Backtest report", facts, tuple(sections))


def _cell(text: str) -> str:
    return text.replace("|", "\\|")


def markdown(doc: Document) -> str:
    out = [f"# {doc.title}", ""]
    out += [f"- **{k}:** {v}" for k, v in doc.facts]
    for s in doc.sections:
        out += ["", f"## {s.title}"]
        for line in s.lines:
            out += ["", line]
        for t in s.tables:
            out += ["", "| " + " | ".join(map(_cell, t.header)) + " |"]
            out.append("|" + "|".join("---" for _ in t.header) + "|")
            out += ["| " + " | ".join(map(_cell, row)) + " |" for row in t.rows]
    return "\n".join(out) + "\n"


_STYLE = """
body { font: 15px/1.5 system-ui, sans-serif; margin: 2rem auto; max-width: 60rem;
  padding: 0 1rem; background: Canvas; color: CanvasText; }
table { border-collapse: collapse; margin: 0.5rem 0 1.25rem; }
th, td { border: 1px solid GrayText; padding: 0.25rem 0.6rem; text-align: left; }
td.PASS { font-weight: 600; } td.FAIL { font-weight: 600; text-decoration: underline; }
"""


def html_page(doc: Document) -> str:
    e = html.escape
    out = [
        "<!doctype html>",
        '<html lang="en"><head><meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        '<meta name="color-scheme" content="light dark">',
        f"<title>{e(doc.title)}</title><style>{_STYLE}</style></head><body>",
        f"<h1>{e(doc.title)}</h1><ul>",
    ]
    out += [f"<li><strong>{e(k)}:</strong> {e(v)}</li>" for k, v in doc.facts]
    out.append("</ul>")
    for s in doc.sections:
        out.append(f"<h2>{e(s.title)}</h2>")
        out += [f"<p>{e(line)}</p>" for line in s.lines]
        for t in s.tables:
            out.append("<table><thead><tr>")
            out += [f"<th>{e(h)}</th>" for h in t.header]
            out.append("</tr></thead><tbody>")
            for row in t.rows:
                cells = (f'<td class="{e(c)}">{e(c)}</td>' if c in ("PASS", "FAIL") else
                         f"<td>{e(c)}</td>" for c in row)
                out.append("<tr>" + "".join(cells) + "</tr>")
            out.append("</tbody></table>")
    out.append("</body></html>")
    return "\n".join(out) + "\n"


def write(
    folder: Path, metrics: m.Metrics, run: Mapping[str, Any], comparison: Sequence[Versus] = ()
) -> tuple[Path, Path]:
    """Write `report.md` and `report.html` into `folder` (created if missing)."""
    doc = build(metrics, run, comparison)
    folder.mkdir(parents=True, exist_ok=True)
    md, page = (folder / name for name in FILES)
    md.write_text(markdown(doc), "utf-8", newline="\n")
    page.write_text(html_page(doc), "utf-8", newline="\n")
    return md, page
