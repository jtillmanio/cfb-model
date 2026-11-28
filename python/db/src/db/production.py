"""`python -m db production-commit` (TASK-076): the commit production serves.

The scheduled jobs run production's code, not `main`'s: `main` can hold a migration production
hasn't had yet, and its code would fail against production's older schema until a release
(schema first, code second; docs/02-architecture.md › Release & operations). The backup
re-applies production's views for the same reason (D-109). Production names its commit at
`PRODUCTION_URL/api/py/health`, the one route outside the auth gate, so this reads it there.

Only a full 40-hex SHA will do: a build without one says `unknown`. Anything else fails the
step (exit 1) before the job does anything, and the summary names the URL and what came back.
Called by `.github/actions/production-commit`; HTTP is the standard library's.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import time
from http.client import HTTPException
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from db.release import _output, _summary  # the workflow's step outputs and summary

HEALTH_PATH = "/api/py/health"
SHA = re.compile(r"[0-9a-f]{40}")
ATTEMPTS = 6  # one try and 5 retries, as the backup's curl step had
TIMEOUT = 20  # seconds a try may take
BYPASS_VAR = "VERCEL_AUTOMATION_BYPASS_SECRET"

_sleep = time.sleep  # replaced in tests


class LookupFailed(RuntimeError):
    """Production didn't name a commit. The message says what came back instead."""


def health_url(base: str) -> str:
    return f"{base.rstrip('/')}{HEALTH_PATH}"


def commit_from(body: bytes) -> str:
    """The full SHA in a health body; `LookupFailed` saying what it held otherwise."""
    try:
        health = json.loads(body)
    except ValueError:
        raise LookupFailed(f"an answer that isn't JSON ({body[:80]!r})") from None
    commit = health.get("commit") if isinstance(health, dict) else None
    if commit is None:
        raise LookupFailed("no commit")
    if not isinstance(commit, str) or not SHA.fullmatch(commit):
        raise LookupFailed(f"commit {commit!r}, not a full SHA")
    return commit


def _get(url: str, bypass: str) -> bytes:
    # The bypass header gets past Deployment Protection should it ever cover production
    # (02 › Auth); production's own domain doesn't need it today.
    request = Request(url, headers={"x-vercel-protection-bypass": bypass} if bypass else {})
    with urlopen(request, timeout=TIMEOUT) as response:
        return response.read()


def lookup(base: str, bypass: str) -> str:
    """Production's commit. A failed request is tried again, up to `ATTEMPTS` in all, with
    waits of 1, 2, 4… seconds; an answer that names no commit isn't, since it won't change."""
    url = health_url(base)
    error = ""
    for attempt in range(ATTEMPTS):
        if attempt:
            _sleep(2 ** (attempt - 1))
        try:
            body = _get(url, bypass)
        except HTTPError as e:
            error = f"HTTP {e.code}"
            continue
        except OSError as e:
            error = f"no answer ({e})"
            continue
        except HTTPException as e:  # a broken answer, e.g. cut short: IncompleteRead
            error = f"a broken answer ({type(e).__name__}: {e})"
            continue
        return commit_from(body)
    raise LookupFailed(f"{error} after {ATTEMPTS} attempts")


def summary_line(commit: str, *, code_ref: str, uses: str) -> str:
    if uses == "views":
        return f"Re-applying the views of production's commit `{commit}`."
    if code_ref:
        return (
            f"Running `{code_ref}`, not production's commit `{commit}`: a hand-run test of "
            "code that isn't released."
        )
    return f"Running production's commit `{commit}`."


def production_commit(args: argparse.Namespace) -> None:
    base = (args.url or "").strip()
    try:
        if not base:
            raise LookupFailed("nothing: PRODUCTION_URL is unset")
        commit = lookup(base, os.environ.get(BYPASS_VAR, ""))
    except LookupFailed as e:
        where = health_url(base) if base else "PRODUCTION_URL"
        _summary(
            f"**{args.workflow} failed:** {where} didn't name the commit production serves; it "
            f"gave {e}. Nothing was run. Check `PRODUCTION_URL` is the production domain and "
            "that a release has run (README › Jobs › Read a failed run)."
        )
        raise SystemExit(1) from None
    code_ref = (args.code_ref or "").strip()
    _output(commit=commit, ref=code_ref or commit)
    _summary(summary_line(commit, code_ref=code_ref, uses=args.uses))


def add_command(subparsers: Any) -> None:
    p = subparsers.add_parser(
        "production-commit", help="The commit production serves, from its /api/py/health"
    )
    p.add_argument("--url", default=os.environ.get("PRODUCTION_URL", ""),
                   help="Production's base URL (default: $PRODUCTION_URL)")
    p.add_argument("--code-ref", default="",
                   help="Check out this ref instead (a hand-run test); empty: production's commit")
    p.add_argument("--uses", choices=["code", "views"], default="code",
                   help="What the caller takes from the commit, for the summary line")
    p.add_argument("--workflow", default="Job", help="The workflow's name, for a failure")
    p.set_defaults(func=production_commit)
