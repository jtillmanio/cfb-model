"""`python -m db migrate|check --target dev|test|preview`.

Root scripts: db:migrate (dev), db:migrate:test, db:check (test). The preview target is the
Vercel preview build's step; outside a preview build it does nothing.
"""

from __future__ import annotations

import argparse
from typing import cast

from db.config import MigrationTarget, direct_url, load_env, preview_migration_url
from db.migrate import check, upgrade


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m db")
    parser.add_argument("command", choices=["migrate", "check"])
    parser.add_argument("--target", choices=["dev", "test", "preview"], default="dev")
    args = parser.parse_args(argv)

    if args.target == "preview":
        if args.command != "migrate":
            parser.error("--target preview only supports migrate")
        url = preview_migration_url()
        if url is None:
            print("Not a preview build: skipping the preview migration.")
            return
    else:
        load_env()
        url = direct_url(cast(MigrationTarget, args.target))

    print(f"Target: {args.target}")
    if args.command == "migrate":
        upgrade(url)
    else:
        check(url)


if __name__ == "__main__":
    main()
