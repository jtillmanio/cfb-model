"""`engine` CLI. Commands land here as each phase adds them (ingest, transform, rate, …)."""

from __future__ import annotations

import argparse
import sys
from typing import NoReturn

from db.config import UnsafeDatabaseError, direct_url, load_env
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
    elif args.command == "seed":
        load_env()
        from engine.fixture import seed_fixture

        seed_fixture()

if __name__ == "__main__":
    main()
