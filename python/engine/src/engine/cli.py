"""`engine` CLI. Commands land here as each phase adds them (ingest, transform, rate, …)."""

from __future__ import annotations

import argparse

from db.config import direct_url, load_env


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="engine")
    commands = parser.add_subparsers(dest="command", required=True)

    ingest = commands.add_parser("ingest", help="Fetch from a source and publish to the dev DB")
    ingest_what = ingest.add_subparsers(dest="what", required=True)
    games = ingest_what.add_parser("games", help="One week of CFBD games (one API call)")
    games.add_argument("--season", type=int, required=True)
    games.add_argument("--week", type=int, required=True)
    games.add_argument("--season-type", default="regular", choices=["regular", "postseason"])
    games.add_argument("--classification", default="fbs", choices=["fbs", "fcs", "ii", "iii"])

    seed = commands.add_parser("seed", help="Load seed data into the test DB")
    seed.add_argument("what", choices=["fixture"])

    args = parser.parse_args(argv)
    load_env()

    if args.command == "ingest":
        from engine.ingest.games import ingest_games

        ingest_games(
            args.season, args.week, args.season_type, args.classification, direct_url("dev")
        )
    elif args.command == "seed":
        from engine.fixture import seed_fixture

        seed_fixture()


if __name__ == "__main__":
    main()
