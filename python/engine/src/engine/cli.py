"""`engine` CLI. Commands land here as each phase adds them (ingest, transform, rate, …)."""

from __future__ import annotations

import argparse
import sys
from typing import NoReturn

from db.config import MigrationTarget, UnsafeDatabaseError, direct_url, load_env
from engine.ingest.endpoints import ENDPOINTS, SEASON_TYPES, query


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
        help="Rebuild staging/ from raw/ with no API calls, then run the data-quality checks",
        description="Recreates every staged table in LAKE_URI from its raw files alone, then runs "
        "the checks. Exits 1 if a check fails, 2 if it refuses (LIVE=true).",
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

    seed = commands.add_parser("seed", help="Load seed data into the test DB")
    seed.add_argument("what", choices=["fixture"])

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

        try:
            rebuild(open_lake())
        except UnsafeDatabaseError as e:
            _refuse(str(e))
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
    elif args.command == "seed":
        load_env()
        from engine.fixture import seed_fixture

        seed_fixture()


if __name__ == "__main__":
    main()
