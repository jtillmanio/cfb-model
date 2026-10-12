"""The release workflow's logic (TASK-005, D-018, docs/02-architecture.md › Release & operations).

`.github/workflows/release.yml` calls these as `python -m db release plan|pending|snapshot|promote|
smoke`. Pure decisions come first (which build, did CI pass, what's pending, is production
healthy), then the thin Vercel, GitHub and Neon clients, then the commands that join them and
write the job outputs and summary. HTTP is stdlib `urllib`: the workflow is the only caller.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import text

from db.config import live_url
from db.migrate import DB_DIR
from db.session import make_engine

CI_CHECK = "verify"  # the CI job a release requires (workflow.ciJobName)
MIN_PREFIX = 7


class ReleaseRefused(RuntimeError):
    """The release can't go ahead. The message names the commit or check that stopped it."""


@dataclass(frozen=True)
class Deployment:
    id: str
    url: str
    commit: str
    created: int  # ms since the epoch
    state: str
    target: str | None

    @classmethod
    def from_vercel(cls, d: Mapping[str, Any]) -> Deployment:
        meta = d.get("meta") or {}
        return cls(
            id=d["uid"],
            url=d.get("url") or "",
            commit=meta.get("githubCommitSha") or "",
            created=int(d.get("created") or d.get("createdAt") or 0),
            state=d.get("readyState") or d.get("state") or "",
            target=d.get("target"),
        )


@dataclass(frozen=True)
class CheckRun:
    name: str
    status: str  # queued | in_progress | completed
    conclusion: str | None  # success | failure | cancelled | … once completed
    id: int  # GitHub assigns ids in creation order, so the highest is the newest run

    @classmethod
    def from_github(cls, r: Mapping[str, Any]) -> CheckRun:
        return cls(r["name"], r["status"], r.get("conclusion"), int(r["id"]))


# ─── Decisions ───────────────────────────────────────────────────────────────────────────────


def pick_deployment(
    deployments: Sequence[Deployment], main_commits: Sequence[str], commit: str | None = None
) -> Deployment:
    """The newest ready production build whose commit is on main (or the requested commit's)."""
    on_main = set(main_commits)
    ready = [
        d for d in deployments
        if d.state == "READY" and d.target == "production" and d.commit in on_main
    ]
    if commit:
        if len(commit) < MIN_PREFIX:
            raise ReleaseRefused(f"Name the commit with at least {MIN_PREFIX} characters: {commit}")
        ready = [d for d in ready if d.commit.startswith(commit)]
        if not ready:
            raise ReleaseRefused(
                f"No ready production build for {commit} on main. Check the commit is on main "
                "and its Vercel build finished."
            )
    if not ready:
        newest = main_commits[0][:MIN_PREFIX] if main_commits else "none"
        raise ReleaseRefused(
            f"No ready production build for any recent commit on main (newest: {newest})."
        )
    return max(ready, key=lambda d: d.created)


def require_ci_passed(commit: str, runs: Sequence[CheckRun], name: str = CI_CHECK) -> str:
    """CI's latest `verify` run on exactly this commit must have completed with success."""
    runs = [r for r in runs if r.name == name]
    if not runs:
        raise ReleaseRefused(f"CI's {name} never ran on {commit}.")
    latest = max(runs, key=lambda r: r.id)
    if latest.status != "completed":
        raise ReleaseRefused(f"CI's {name} on {commit} is still running ({latest.status}).")
    if latest.conclusion != "success":
        raise ReleaseRefused(f"CI's {name} on {commit} didn't pass ({latest.conclusion}).")
    return latest.conclusion


def script_directory(migrations_dir: Path | None = None) -> ScriptDirectory:
    """The Alembic scripts in a checkout (default: this one's python/db/migrations)."""
    return ScriptDirectory(str(migrations_dir or DB_DIR / "migrations"))


def single_head(script: ScriptDirectory) -> str:
    found = list(script.get_heads())
    if len(found) != 1:
        raise ReleaseRefused(f"Expected one Alembic head, found {len(found)} heads: {found}")
    return found[0]


def pending_migrations(script: ScriptDirectory, current: Sequence[str]) -> list[str]:
    """Revisions between production's current head(s) and the script's head, oldest first."""
    head = single_head(script)
    known = {s.revision for s in script.walk_revisions()}
    unknown = [rev for rev in current if rev not in known]
    if unknown:
        raise ReleaseRefused(
            f"Production is at {', '.join(unknown)}, which this commit's migrations don't know. "
            "Is production ahead of this commit?"
        )
    if len(current) > 1:
        raise ReleaseRefused(f"Production has {len(current)} migration heads: {list(current)}")
    lower = current[0] if current else "base"
    return [s.revision for s in reversed(list(script.iterate_revisions(head, lower)))]


def smoke_check(
    health: Mapping[str, Any], *, commit: str, head: str, unsigned_status: int
) -> list[str]:
    """What's wrong with production, one line per failed check; empty when it's healthy."""
    failures = []
    if health.get("commit") != commit:
        failures.append(f"commit is {health.get('commit')}, expected {commit}")
    if health.get("db_reachable") is not True:
        failures.append(f"db_reachable is {health.get('db_reachable')}, expected true")
    if health.get("migration_head") != head:
        failures.append(f"migration_head is {health.get('migration_head')}, expected {head}")
    if unsigned_status != 401:
        # Every route but health needs the JWT (D-107); a build without the guard must not pass.
        failures.append(f"unsigned GET /api/py/teams answered {unsigned_status}, expected 401")
    return failures


def snapshot_name(commit: str, now: datetime) -> str:
    return f"release/{now:%Y%m%d-%H%M}-{commit[:MIN_PREFIX]}"


def endpoint_id(url: str) -> str:
    """Neon's endpoint ID is the host's first label (`ep-…`), pooled or direct."""
    return (urlsplit(url).hostname or "").partition(".")[0].removesuffix("-pooler")


def render_plan_summary(deployment: Deployment, ci: str, main_head: str | None) -> str:
    lines = [
        "## Release plan",
        "",
        "| | |",
        "|---|---|",
        f"| Commit | `{deployment.commit}` |",
        f"| Build | `{deployment.id}` (https://{deployment.url}) |",
        f"| CI `{CI_CHECK}` | {ci} |",
    ]
    if main_head and main_head != deployment.commit:
        lines.append(f"| Newest on main | `{main_head[:MIN_PREFIX]}`, no ready build yet |")
    return "\n".join(lines) + "\n"


def render_pending_summary(
    pending: Sequence[str], *, head: str, current: Sequence[str], dry_run: bool
) -> str:
    lines = [
        "| Migrations | |",  # its own table: the plan summary above ends with a blank line
        "|---|---|",
        f"| Production's migration head | {', '.join(current) or 'none (empty database)'} |",
        f"| Commit's migration head | {head} |",
        f"| Pending migrations | {', '.join(pending) or 'none'} |",
        "",
    ]
    if dry_run:
        lines.append(
            "**Dry run:** no snapshot was made, no migration ran and nothing was promoted."
        )
    elif pending:
        lines.append("Next: snapshot production, migrate, promote, smoke test.")
    else:
        lines.append("Next: no snapshot (nothing pending); re-apply views, promote, smoke test.")
    return "\n".join(lines) + "\n"


# ─── Clients ─────────────────────────────────────────────────────────────────────────────────


def _need(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise ReleaseRefused(f"{name} is not set.")
    return value


def _call(
    method: str, url: str, token: str, *, body: Any = None, params: Mapping[str, Any] | None = None
) -> Any:
    full = f"{url}?{urlencode(params)}" if params else url
    request = Request(
        full,
        data=None if body is None else json.dumps(body).encode(),
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "cfb-model-release",
        },
    )
    try:
        with urlopen(request, timeout=30) as response:
            raw = response.read()
    except HTTPError as e:
        detail = e.read().decode(errors="replace")[:300]
        raise ReleaseRefused(f"{method} {url} answered {e.code}: {detail}") from None
    return json.loads(raw) if raw else None


VERCEL = "https://api.vercel.com"
GITHUB = "https://api.github.com"
NEON = "https://console.neon.tech/api/v2"


def _vercel_scope() -> dict[str, str]:
    org = _need("VERCEL_ORG_ID")  # a team ID scopes the call; a personal account's needs none
    return {"teamId": org} if org.startswith("team_") else {}


def fetch_deployments() -> list[Deployment]:
    data = _call(
        "GET", f"{VERCEL}/v6/deployments", _need("VERCEL_TOKEN"),
        params={"projectId": _need("VERCEL_PROJECT_ID"), "target": "production", "state": "READY",
                "limit": 50, **_vercel_scope()},
    )
    return [Deployment.from_vercel(d) for d in data["deployments"]]


def fetch_main_commits(branch: str) -> list[str]:
    repo = _need("GITHUB_REPOSITORY")
    data = _call("GET", f"{GITHUB}/repos/{repo}/commits", _need("GITHUB_TOKEN"),
                 params={"sha": branch, "per_page": 100})
    return [c["sha"] for c in data]


def fetch_check_runs(sha: str) -> list[CheckRun]:
    repo = _need("GITHUB_REPOSITORY")
    data = _call("GET", f"{GITHUB}/repos/{repo}/commits/{sha}/check-runs", _need("GITHUB_TOKEN"),
                 params={"check_name": CI_CHECK, "filter": "all", "per_page": 100})
    return [CheckRun.from_github(r) for r in data["check_runs"]]


def promote_deployment(deployment_id: str) -> None:
    project = _need("VERCEL_PROJECT_ID")
    _call("POST", f"{VERCEL}/v10/projects/{project}/promote/{deployment_id}",
          _need("VERCEL_TOKEN"), params=_vercel_scope())


def create_snapshot(name: str, database_url: str) -> dict[str, str]:
    """Branch the Neon branch production's endpoint serves. No compute: it's a restore point."""
    project, key = _need("NEON_PROJECT_ID"), _need("NEON_API_KEY")
    endpoint = _call("GET", f"{NEON}/projects/{project}/endpoints/{endpoint_id(database_url)}", key)
    parent = endpoint["endpoint"]["branch_id"]
    made = _call("POST", f"{NEON}/projects/{project}/branches", key,
                 body={"branch": {"name": name, "parent_id": parent}})
    return {"id": made["branch"]["id"], "name": made["branch"]["name"], "parent": parent}


def current_heads(url: str) -> tuple[str, ...]:
    """Production's Alembic head(s), read in a read-only transaction. Empty on a new database."""
    with make_engine(url).connect() as conn:
        conn.execute(text("SET TRANSACTION READ ONLY"))
        heads = MigrationContext.configure(conn).get_current_heads()
        conn.rollback()
    return tuple(heads)


def fetch_health(base_url: str) -> tuple[dict[str, Any], int]:
    """Production's health, and the status an unsigned data call gets."""
    base = base_url.rstrip("/")
    try:
        with urlopen(Request(f"{base}/api/py/health"), timeout=10) as response:
            health = json.loads(response.read())
    except (HTTPError, OSError, ValueError) as e:
        health = {"commit": None, "db_reachable": None, "migration_head": None, "error": str(e)}
    try:
        with urlopen(Request(f"{base}/api/py/teams"), timeout=10) as response:
            status = response.status
    except HTTPError as e:
        status = e.code
    except OSError:
        status = 0
    return health, status


# ─── Commands ────────────────────────────────────────────────────────────────────────────────


def _output(**values: str) -> None:
    """Step outputs for later jobs (`$GITHUB_OUTPUT`); printed too, for local runs."""
    lines = [f"{k}={v}" for k, v in values.items()]
    print("\n".join(lines))
    if path := os.environ.get("GITHUB_OUTPUT"):
        with open(path, "a", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")


def _summary(markdown: str) -> None:
    print(markdown)
    if path := os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(path, "a", encoding="utf-8") as f:
            f.write(markdown + "\n")


def _refusing(step: Callable[[argparse.Namespace], None]) -> Callable[[argparse.Namespace], None]:
    """A refusal ends the step non-zero and says why in the job summary."""

    def run(args: argparse.Namespace) -> None:
        try:
            step(args)
        except ReleaseRefused as e:
            _summary(f"**Refused:** {e}")
            raise SystemExit(f"Refused: {e}") from None

    return run


@_refusing
def plan(args: argparse.Namespace) -> None:
    main_commits = fetch_main_commits(args.branch)
    deployment = pick_deployment(fetch_deployments(), main_commits, args.commit or None)
    ci = require_ci_passed(deployment.commit, fetch_check_runs(deployment.commit))
    _summary(render_plan_summary(deployment, ci, main_commits[0] if main_commits else None))
    _output(commit=deployment.commit, deployment_id=deployment.id, deployment_url=deployment.url)


@_refusing
def pending(args: argparse.Namespace) -> None:
    script = script_directory(args.migrations)
    head = single_head(script)
    current = current_heads(live_url(None))
    todo = pending_migrations(script, current)
    _summary(render_pending_summary(todo, head=head, current=current, dry_run=args.dry_run))
    _output(head=head, pending=" ".join(todo))


@_refusing
def snapshot(args: argparse.Namespace) -> None:
    made = create_snapshot(snapshot_name(args.commit, datetime.now(UTC)), live_url(None))
    _summary(f"Snapshot: Neon branch `{made['name']}` ({made['id']}) of {made['parent']}.")


@_refusing
def promote(args: argparse.Namespace) -> None:
    promote_deployment(args.deployment_id)
    _summary(f"Promoted `{args.deployment_id}` to production.")


@_refusing
def smoke(args: argparse.Namespace) -> None:
    """Retry until production serves the release (promotion takes a moment to reach the domain)."""
    failures: list[str] = []
    for attempt in range(1, args.attempts + 1):
        health, status = fetch_health(args.url)
        failures = smoke_check(health, commit=args.commit, head=args.head, unsigned_status=status)
        if not failures:
            _summary(f"Smoke test passed: {args.url} serves `{args.commit}` at {args.head}.")
            return
        print(f"Attempt {attempt}/{args.attempts}: " + "; ".join(failures))
        if attempt < args.attempts:
            time.sleep(args.interval)
    raise ReleaseRefused("Smoke test failed: " + "; ".join(failures))


def add_commands(subparsers: Any) -> None:
    release = subparsers.add_parser("release", help="Steps of the release workflow")
    steps = release.add_subparsers(dest="step", required=True)

    p = steps.add_parser("plan", help="Pick the build to release and check CI passed on it")
    p.add_argument("--commit", default="", help="A commit on main (default: the newest ready)")
    p.add_argument("--branch", default="main")
    p.set_defaults(func=plan)

    p = steps.add_parser("pending", help="List the migrations production still needs")
    p.add_argument("--migrations", type=Path, help="The planned commit's python/db/migrations")
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(func=pending)

    p = steps.add_parser("snapshot", help="Branch production in Neon before migrating")
    p.add_argument("--commit", required=True)
    p.set_defaults(func=snapshot)

    p = steps.add_parser("promote", help="Point production's domains at the planned build")
    p.add_argument("--deployment-id", required=True)
    p.set_defaults(func=promote)

    p = steps.add_parser("smoke", help="Check production's health and the API guard")
    p.add_argument("--url", required=True)
    p.add_argument("--commit", required=True)
    p.add_argument("--head", required=True)
    p.add_argument("--attempts", type=int, default=16)  # ~5 min, ≤ 9 min if every call times out
    p.add_argument("--interval", type=float, default=15.0)
    p.set_defaults(func=smoke)
