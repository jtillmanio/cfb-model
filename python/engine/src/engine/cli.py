"""`engine` CLI. Commands land here as each phase adds them (ingest, transform, rate, …)."""

from __future__ import annotations

import argparse

from db.config import direct_url, load_env
from engine.ingest.endpoints import ENDPOINTS, SEASON_TYPES, query


def _extra_params(parser: argparse.ArgumentParser, pairs: list[str]) -> dict[str, str]:
    extra: dict[str, str] = {}
    for pair in pairs:
        name, sep, value = pair.partition("=")
        if not sep or not name:
            parser.error(f"--param takes NAME=VALUE, not {pair!r}")
        extra[name] = value
    return extra


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
    elif args.command == "seed":
        load_env()
        from engine.fixture import seed_fixture

        seed_fixture()

if __name__ == "__main__":
    main()
