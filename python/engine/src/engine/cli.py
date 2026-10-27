"""`engine` CLI. Commands land here as each phase adds them (ingest, transform, rate, …)."""

from __future__ import annotations

import argparse
import os
import sys
from typing import TYPE_CHECKING, NoReturn

from db.config import (
    MigrationTarget,
    UnsafeDatabaseError,
    direct_url,
    live_url,
    load_env,
    refuse_if_live,
)
from engine.ingest.endpoints import ENDPOINTS, SEASON_TYPES, query

if TYPE_CHECKING:
    from engine.jobs import Kind


def _extra_params(parser: argparse.ArgumentParser, pairs: list[str]) -> dict[str, str]:
    extra: dict[str, str] = {}
    for pair in pairs:
        name, sep, value = pair.partition("=")
        if not sep or not name:
            parser.error(f"--param takes NAME=VALUE, not {pair!r}")
        extra[name] = value
    return extra


def _refuse(message: str) -> NoReturn:
    """A refusal or a missing prerequisite: exit 2, so it isn't read as a failed check (1)."""
    print(f"error: {message}", file=sys.stderr)
    sys.exit(2)


def _quality() -> None:
    """Run the data-quality checks on staging/ and exit 1 if any fails."""
    from engine.ingest.lake import open_lake
    from engine.transform import quality

    try:
        report = quality.run(open_lake())
    except quality.StagingMissingError as e:
        _refuse(str(e))
    print(report.render())
    if not report.ok:
        sys.exit(1)


def _publish(target: MigrationTarget) -> None:
    """Check staging/, then publish it to the target in one transaction."""
    from db.session import make_engine
    from engine.ingest.lake import open_lake
    from engine.publish.staging import publish_lake
    from engine.transform import quality

    lake = open_lake()
    try:
        report = quality.run(lake)
    except quality.StagingMissingError as e:
        _refuse(str(e))
    if not report.ok:
        print(report.render())
        print("Nothing published: fix the failed checks first.")
        sys.exit(1)
    try:
        url = direct_url(target)
    except UnsafeDatabaseError as e:
        _refuse(str(e))
    with make_engine(url).begin() as conn:
        new = publish_lake(lake, conn, report=report)
    print(f"Published to {target}. New rows: " + ", ".join(f"{t} {n}" for t, n in new.items()))


def _backfill(first: int, last: int, dry_run: bool, max_calls: int | None) -> None:
    """Print the dry run, or pull what it lists; exit 3 when the budget or --max-calls stops it."""
    from engine.ingest import backfill
    from engine.ingest.cfbd import BudgetExceededError, CallBudget
    from engine.ingest.lake import open_lake

    lake = open_lake()
    if dry_run:
        print(backfill.render(backfill.plan(lake, first, last), first, last, CallBudget(lake)))
        return
    try:
        calls = backfill.run(lake, first, last, backfill.client_for(lake), max_calls)
    except (BudgetExceededError, backfill.Stopped) as e:
        by = "the CFBD budget" if isinstance(e, BudgetExceededError) else "--max-calls"
        left = len(backfill.plan(lake, first, last))
        print(e)
        print(f"Stopped by {by}. Left: {left} calls (engine backfill --dry-run lists them).")
        sys.exit(3)
    print(f"Backfill {first}-{last} done: {calls} CFBD calls.")


def _sync(src: str, dst: str) -> None:
    from engine.ingest.backfill import sync_raw
    from engine.ingest.lake import open_lake

    copied = sync_raw(open_lake(src), open_lake(dst))
    print(f"Copied {len(copied)} raw files from {src} to {dst}.")


def _job_url(target: str) -> str:
    """Production only under LIVE=true, and dev only without it, so a job never mixes them."""
    live = os.environ.get("LIVE", "").strip().lower() in {"1", "true", "yes"}
    try:
        if target == "dev":
            refuse_if_live("publish a job to dev")
            return direct_url("dev")
        if not live:
            _refuse("a job publishes to production only under LIVE=true.")
        return live_url(None)
    except UnsafeDatabaseError as e:
        _refuse(str(e))


def _job(kind: Kind, target: str, summary_path: str | None) -> None:
    """Run one scheduled job; exit 1 if a check fails (nothing published), 2 on a refusal, 3 when
    the CFBD budget stops it. The summary is appended to `summary_path` whatever happens."""
    from engine import clock, jobs
    from engine.ingest.backfill import client_for
    from engine.ingest.cfbd import BudgetExceededError
    from engine.ingest.lake import open_lake

    url = _job_url(target)
    lake = open_lake()
    summary = jobs.Summary(kind, jobs.current_season(clock.now()), target)
    code = 0
    try:
        jobs.run(kind, lake, url, target=target, client=client_for(lake), summary=summary)
    except jobs.JobFailed:
        code = 1
    except BudgetExceededError as e:
        print(e)
        code = 3
    finally:
        text = summary.render()
        print(text)
        if summary_path:
            with open(summary_path, "a", encoding="utf-8") as f:
                f.write(text + "\n")
    if code:
        sys.exit(code)


def _season_range(parser: argparse.ArgumentParser, text: str) -> list[int]:
    first, sep, last = text.partition("-")
    try:
        seasons = list(range(int(first), int(last if sep else first) + 1))
    except ValueError:
        parser.error(f"--seasons takes SEASON or FIRST-LAST, not {text!r}")
    if not seasons:
        parser.error(f"--seasons {text}: the first season is after the last")
    return seasons


def _backtest(args: argparse.Namespace, seasons: list[int]) -> None:
    """Walk the seasons forward and write the results; exit 1 if the point-in-time check fails,
    2 on a refusal (a locked holdout season, a refused input, nothing to tune on)."""
    from pathlib import Path

    from pydantic import ValidationError

    from engine import backtest, clock
    from engine.backtest import compare, harness, holdout
    from engine.core.spec import ModelSpec
    from engine.ingest.lake import open_lake
    from engine.transform.features import PointInTimeError

    try:
        spec = ModelSpec.model_validate_json(Path(args.spec).read_text("utf-8"))
    except (OSError, ValidationError) as e:
        _refuse(f"--spec {args.spec}: {e}")
    try:
        opened = holdout.guard(seasons, args.holdout, args.reason)
    except holdout.HoldoutRefusedError as e:
        _refuse(str(e))
    if args.compare and (args.model or opened):
        _refuse("--compare baselines compares the spec's own model on validation seasons only")
    name = args.model or spec.base
    factory = backtest.MODELS.get(name)
    if factory is None:
        known = ", ".join(sorted(backtest.MODELS))
        _refuse(f"no model is registered as {name!r} (registered: {known})")
    lake = open_lake()
    try:
        history = harness.load(lake)
        harness.prepare(spec, factory, history, seasons, args.tune_from)
        at = clock.now()
        if opened:
            holdout.record(lake, at, harness.spec_hash(spec), seasons, args.reason, name)
        result = harness.run(spec, factory, history, seasons, args.tune_from)
        others = (
            compare.run_baselines(spec, history, seasons, args.tune_from, result.choices)
            if args.compare
            else {}
        )
        versus = compare.compare(result.rows, others)  # before anything is written
    except harness.RefusedError as e:
        _refuse(str(e))
    except PointInTimeError as e:
        print(f"FAIL {e}")
        sys.exit(1)
    folder = harness.write(
        lake, result, spec=spec, model=name, tune_from=args.tune_from, holdout=opened, at=at
    )
    for other, run in others.items():
        written = harness.write(
            lake, run, spec=spec, model=other, tune_from=args.tune_from, holdout=False, at=at
        )
        print(f"Wrote {written}/predictions.parquet ({other})")
    print(f"Backtest {seasons[0]}-{seasons[-1]} ({name}): {len(result.rows)} games predicted.")
    for season, choices in result.choices.items():
        if choices:
            tuning = result.tuned_on[season]
            settings = ", ".join(f"{path} = {value:g}" for path, value in choices.items())
            print(f"  {season}: {settings} (tuned on {tuning[0]}-{tuning[-1]})")
    print(f"Wrote {folder}/predictions.parquet and run.json")
    if opened:
        print(f"Holdout runs so far: {holdout.count(lake)}")
    for v in versus:  # ASCII only: a cp1252 console can't print the minus sign
        d = v.difference
        if d is None or v.mae is None or v.model_mae is None:
            dropped = ", ".join(f"{n} {c}" for n, c in v.dropped.items())
            print(f"  {v.name}: no game to compare ({dropped} left out)")
            continue
        verdict = ("BEATS" if v.beats else "DOES NOT BEAT") if v.bar else "reported"
        print(
            f"  {v.name}: {v.games} games, MAE {v.mae:.2f} vs {name} {v.model_mae:.2f}, "
            f"difference {d.estimate:+.2f} [{d.low:+.2f}, {d.high:+.2f}] {verdict}"
        )
    if args.report:
        from engine.backtest import metrics, report

        scored = metrics.compute(result.rows, spec, result.choices, holdout=opened)
        run = {"model": name, "spec_hash": harness.spec_hash(spec), "tune_from": args.tune_from}
        md, page = report.write(Path(args.report), scored, {**run, "folder": folder}, versus)
        for gate_name, gate in scored.gates:  # the details hold − and ≤, which cp1252 lacks
            print(f"  {gate.status.upper():4} {gate_name}")
        print(f"Wrote {md} and {page}")


def _rate(args: argparse.Namespace) -> None:
    """Fit the spec entering the week and publish the run; exit 1 if the fit failed (recorded as
    a failed run) or the point-in-time check fails, 2 on a refusal (nothing written)."""
    import json
    from pathlib import Path

    from pydantic import ValidationError

    from engine.backtest import harness
    from engine.core.spec import ModelSpec
    from engine.ingest.lake import open_lake
    from engine.publish import models
    from engine.transform.features import PointInTimeError

    try:
        refuse_if_live(f"rate to {args.target}")
    except UnsafeDatabaseError as e:
        _refuse(str(e))
    try:
        spec = ModelSpec.model_validate_json(Path(args.spec).read_text("utf-8"))
    except (OSError, ValidationError) as e:
        _refuse(f"--spec {args.spec}: {e}")
    run = None
    if args.choices:
        try:
            run = json.loads(Path(args.choices).read_text("utf-8"))
        except (OSError, ValueError) as e:
            _refuse(f"--choices {args.choices}: {e}")
    name = args.name or spec.base
    try:
        choices = models.settings(spec, run, args.season)
        url = direct_url(args.target)
    except (models.RateRefused, UnsafeDatabaseError, RuntimeError) as e:
        _refuse(str(e))  # RuntimeError: the dev URL isn't set
    try:
        summary = models.publish(
            open_lake(),
            url,
            spec,
            choices,
            season=args.season,
            week=args.week,
            name=name,
            version=args.version,
        )
    except (models.RateRefused, harness.RefusedError) as e:
        _refuse(str(e))
    except PointInTimeError as e:  # the lake's check as it's loaded, or the fit's (nothing written)
        print(f"FAIL {e}")
        sys.exit(1)
    print(
        f"Run {summary.run_id} of {name} {args.version} entering {args.season} week {args.week} "
        f"{summary.status} on {args.target}: {summary.ratings} ratings, "
        f"{summary.predictions} predictions."
    )
    if summary.error:
        print(f"FAIL {summary.error}")
        sys.exit(1)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="engine")
    commands = parser.add_subparsers(dest="command", required=True)

    ingest = commands.add_parser(
        "ingest",
        help="Pull one CFBD endpoint into the raw lake (games also publishes to the dev DB)",
        description="One counted CFBD call, saved as Parquet under raw/cfbd/<endpoint>/ in "
        "LAKE_URI. A week saved after all its games completed is reused, never re-fetched.",
    )
    ingest.add_argument("endpoint", choices=list(ENDPOINTS), help="%(choices)s")
    ingest.add_argument("--season", type=int, required=True)
    ingest.add_argument("--week", type=int)
    ingest.add_argument("--season-type", default="regular", choices=SEASON_TYPES)
    ingest.add_argument(
        "--param",
        action="append",
        default=[],
        metavar="NAME=VALUE",
        help="Another CFBD query param, e.g. --param down=1 for ppa_predicted",
    )

    transform = commands.add_parser(
        "transform",
        help="Rebuild staging/ and features/ from raw/ with no API calls, then run the "
        "data-quality checks",
        description="Recreates every staged table in LAKE_URI from its raw files alone, then the "
        "point-in-time feature tables from those, then runs the checks. Exits 1 if a check fails "
        "(a feature row that reads a later game included), 2 if it refuses (LIVE=true).",
    )
    transform.add_argument(
        "--rebuild", action="store_true", required=True, help="Rebuild every staged table"
    )

    commands.add_parser(
        "check",
        help="Run the data-quality checks on staging/",
        description="Exits 1 if a check fails, 2 if staging/ hasn't been built.",
    )

    publish = commands.add_parser(
        "publish",
        help="Publish staged teams, venues, seasons, games and lines to Postgres",
        description="Runs the data-quality checks, then upserts every staged reference row and "
        "inserts new line snapshots in one transaction on the target's direct URL. Exits 1 "
        "before connecting if a check fails, 2 if staging/ hasn't been built.",
    )
    publish.add_argument("--target", required=True, choices=["dev", "test"])

    backfill = commands.add_parser(
        "backfill",
        help="Pull every CFBD endpoint the model uses for a range of seasons into the raw lake",
        description="Season by season: /games, the calendar, each completed week's box scores, "
        "plays and drives, then the season-level lines, stats, teams, preseason inputs and "
        "benchmark ratings. A pull whose saved file is final is skipped, so a stopped run "
        "resumes where it left off. Exits 3 when the month's CFBD budget or --max-calls stops it.",
    )
    backfill.add_argument("--from", dest="first", type=int, required=True, metavar="SEASON")
    backfill.add_argument("--to", dest="last", type=int, required=True, metavar="SEASON")
    backfill.add_argument(
        "--dry-run", action="store_true", help="Count the calls per endpoint; make none"
    )
    backfill.add_argument("--max-calls", type=int, help="Stop before call N + 1")

    lake = commands.add_parser("lake", help="Copy raw files between lakes")
    lake_commands = lake.add_subparsers(dest="lake_command", required=True)
    sync = lake_commands.add_parser(
        "sync",
        help="Copy every raw/cfbd/ file the source has and the target lacks",
        description="No CFBD calls, and no file in the target is overwritten. Each side is a "
        "LAKE_URI: a folder, or s3://<bucket>[/<prefix>] for R2.",
    )
    sync.add_argument("--from", dest="src", required=True, metavar="URI")
    sync.add_argument("--to", dest="dst", required=True, metavar="URI")

    job = commands.add_parser(
        "job",
        help="Run a scheduled job: pull the week, stage the season, check it, publish it",
        description="results: every week with a game in the last 14 days (scores, box scores, "
        "advanced stats, plays, drives, closing lines); lines: the next week's games and lines. "
        "The season is staged in a scratch lake, checked, and published in one transaction. "
        "Exits 1 if a check fails (nothing published), 2 on a refusal, 3 when the CFBD budget "
        "stops it.",
    )
    job.add_argument("kind", choices=["results", "lines"])
    job.add_argument(
        "--target",
        required=True,
        choices=["dev", "live"],
        help="live needs LIVE=true and PRODUCTION_DATABASE_URL_UNPOOLED (the workflows set both)",
    )
    job.add_argument(
        "--summary",
        metavar="PATH",
        help="Append the run's summary as markdown ($GITHUB_STEP_SUMMARY)",
    )

    commands.add_parser(
        "fallback",
        add_help=False,
        help="Say whether a scheduled run is a late fallback to skip (the workflow guard, D-129)",
        description="Arguments are forwarded to engine.fallback: --event, --schedule, "
        "--workflow, --summary. Writes skip=true|false to $GITHUB_OUTPUT.",
    )

    bt = commands.add_parser(
        "backtest",
        help="Replay seasons week by week for a model spec (walk-forward, rolling-origin)",
        description="Predicts every FBS-vs-FBS game with a closing line in the seasons, each "
        "week fit only on games finished before it, each season's tuned settings chosen on "
        "earlier seasons (docs/04-model.md § 9). Reads staging/ and features/ in LAKE_URI and "
        "writes backtests/<run>/predictions.parquet and run.json; --report also writes the "
        "metrics and gates (04 § 9.4) as report.md and report.html. Exits 1 if the point-in-time "
        "check fails, 2 on a refusal.",
    )
    bt.add_argument("--spec", required=True, metavar="FILE", help="A ModelSpec as JSON")
    bt.add_argument("--seasons", required=True, metavar="FIRST-LAST", help="e.g. 2016-2023")
    bt.add_argument(
        "--tune-from",
        type=int,
        default=2015,
        metavar="SEASON",
        help="The first tuning season (default %(default)s; 2014 is warm-up only)",
    )
    bt.add_argument("--model", help="A registered model to run instead of the spec's base")
    bt.add_argument(
        "--holdout",
        action="store_true",
        help="Open the locked holdout seasons (2024-2025); needs --reason, and is recorded",
    )
    bt.add_argument("--reason", help="Why the holdout is being opened")
    bt.add_argument(
        "--report", metavar="DIR", help="Write the metrics and gates to DIR/report.md and .html"
    )
    bt.add_argument(
        "--compare",
        choices=["baselines"],
        help="Also run the Rung 0 baselines with this run's settings and compare them on the "
        "same games (04 § 9.5-9.6); the report gains the comparison",
    )

    rate = commands.add_parser(
        "rate",
        help="Fit a model entering one week and publish the run, ratings and predictions",
        description="Fits the spec on every game finished before the regular-season week's first "
        "kickoff, as the backtest does, predicts each of the week's staged games, and inserts a "
        "new model run with its ratings and predictions in one transaction on the target's "
        "direct URL (re-running inserts another run). A failed fit is recorded as a failed run "
        "(exit 1); a refusal writes nothing (exit 2). Refused under LIVE=true.",
    )
    rate.add_argument("--spec", required=True, metavar="FILE", help="A ModelSpec as JSON")
    rate.add_argument("--season", type=int, required=True)
    rate.add_argument("--week", type=int, required=True, help="Rate entering this regular week")
    rate.add_argument("--target", required=True, choices=["dev", "test"])
    rate.add_argument(
        "--choices",
        metavar="RUN_JSON",
        help="A backtest's run.json: the settings it chose for the season (a tuned spec needs it)",
    )
    rate.add_argument("--name", help="The model version's name (default: the spec's base)")
    rate.add_argument(
        "--version",
        default="v1.0",
        help="The model version, created as dev if it doesn't exist (default %(default)s)",
    )

    seed = commands.add_parser("seed", help="Load seed data into the test DB")
    seed.add_argument("what", choices=["fixture"])

    if (argv if argv is not None else sys.argv[1:])[:1] == ["fallback"]:
        from engine import fallback

        sys.exit(fallback.main((argv if argv is not None else sys.argv[1:])[1:]))
    args = parser.parse_args(argv)

    if args.command == "ingest":
        extra = _extra_params(ingest, args.param)
        try:
            query(args.endpoint, args.season, args.week, args.season_type, extra)
        except ValueError as e:
            ingest.error(str(e))
        load_env()
        if args.endpoint == "games":
            from engine.ingest import games

            games.ingest_games(args.season, args.week, args.season_type, direct_url("dev"))
        else:
            from engine.ingest import endpoints
            from engine.ingest.lake import open_lake

            endpoints.pull(
                open_lake(), args.endpoint, args.season, args.week, args.season_type, extra
            )
    elif args.command == "transform":
        load_env()  # before the LIVE check, so a LIVE in .env.local counts
        from engine.ingest.lake import open_lake
        from engine.transform import rebuild
        from engine.transform.features import PointInTimeError

        try:
            rebuild(open_lake())
        except UnsafeDatabaseError as e:
            _refuse(str(e))
        except PointInTimeError as e:  # a failed check: no feature or `TABLES` file replaced
            print(f"FAIL {e}")
            sys.exit(1)
        _quality()
    elif args.command == "check":
        load_env()
        _quality()
    elif args.command == "publish":
        load_env()
        _publish(args.target)
    elif args.command == "backfill":
        if args.first > args.last:
            backfill.error("--from must not be after --to.")
        load_env()
        _backfill(args.first, args.last, args.dry_run, args.max_calls)
    elif args.command == "lake":
        load_env()
        _sync(args.src, args.dst)
    elif args.command == "job":
        load_env()
        _job(args.kind, args.target, args.summary)
    elif args.command == "backtest":
        seasons = _season_range(bt, args.seasons)
        load_env()
        _backtest(args, seasons)
    elif args.command == "rate":
        load_env()  # before the LIVE check, so a LIVE in .env.local counts
        _rate(args)
    elif args.command == "seed":
        load_env()
        from engine.fixture import seed_fixture

        seed_fixture()


if __name__ == "__main__":
    main()
