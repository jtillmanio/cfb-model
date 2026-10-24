"""`python -m db migrate|check --target dev|test|preview|live`, `python -m db release <step>` and
`python -m db backup dump|verify`, `python -m db merged-migrations --base <ref>` (CI) and
`python -m db vercel-cleanup [--branch <b>]` (db.deployments).

Root scripts: db:migrate (dev), db:migrate:test, db:check (test). The preview target is the
Vercel preview build's step; outside a preview build it does nothing. The live target is
production, migrated only by the release workflow or with an explicit `--env-file .env.live`
(D-015); the release steps are in db.release.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import cast

from db import backup, deployments, merged_migrations, release
from db.config import MigrationTarget, direct_url, live_url, load_env, preview_migration_url
from db.migrate import check, upgrade


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m db")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("migrate", "check"):
        p = commands.add_parser(name)
        p.add_argument("--target", choices=["dev", "test", "preview", "live"], default="dev")
        p.add_argument("--env-file", type=Path, help="Only with --target live: e.g. .env.live")
    release.add_commands(commands)
    backup.add_commands(commands)
    merged_migrations.add_command(commands)
    deployments.add_command(commands)
    args = parser.parse_args(argv)

    if args.command in ("release", "backup", "merged-migrations", "vercel-cleanup"):
        args.func(args)
        return

    if args.env_file is not None and args.target != "live":
        parser.error("--env-file is only for --target live")
    if args.target in ("preview", "live") and args.command != "migrate":
        parser.error(f"--target {args.target} only supports migrate")

    if args.target == "preview":
        url = preview_migration_url()
        if url is None:
            print("Not a preview build: skipping the preview migration.")
            return
    elif args.target == "live":
        url = live_url(args.env_file)
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
