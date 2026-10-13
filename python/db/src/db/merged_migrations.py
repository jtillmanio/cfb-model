"""`python -m db merged-migrations --base <ref>`: fail when a migration already on the base was
edited, renamed or deleted (D-020; .claude/rules/database.md › Migrations).

CI passes the base: on a PR, `origin/<base branch>`, so the three-dot diff starts at the merge
base and only the branch's own changes count; on a push to `main`, the previous tip of `main`.
Adding a migration is the only change allowed in the folder.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from collections.abc import Iterable
from typing import Any

VERSIONS = "python/db/migrations/versions/"

_KIND = {"M": "modified", "T": "modified", "D": "deleted", "R": "renamed"}


def violations(name_status: Iterable[str]) -> list[str]:
    """Each change to an existing migration in `git diff --name-status` output, named.

    A rename or copy line is `R100<TAB>old<TAB>new`. A rename counts when its old path is a
    migration; a copy leaves its source untouched, so it counts as an add, as `A` does.
    """
    found: list[str] = []
    for line in name_status:
        if not line.strip():
            continue
        status, *paths = line.split("\t")
        kind = _KIND.get(status[:1])
        if kind is None or not paths[0].startswith(VERSIONS):
            continue
        found.append(f"{kind}: {' -> '.join(paths)}")
    return found


def diff(base: str) -> list[str]:
    done = subprocess.run(
        ["git", "diff", "--name-status", "--find-renames", f"{base}...HEAD"],
        capture_output=True, text=True,
    )
    if done.returncode != 0:
        sys.exit(f"git diff against {base!r} failed: {done.stderr.strip()}")
    return done.stdout.splitlines()


def run(args: argparse.Namespace) -> None:
    found = violations(diff(args.base))
    if found:
        print(f"Migrations already on {args.base} changed (forward-only: add a new one instead):")
        for item in found:
            print(f"  {item}")
        sys.exit(1)
    print(f"No migration on the base was edited, renamed or deleted (base {args.base}).")


def add_command(subparsers: Any) -> None:
    p = subparsers.add_parser("merged-migrations", help="Fail if a merged migration changed")
    p.add_argument("--base", required=True, help="The ref to diff against (three-dot)")
    p.set_defaults(func=run)
