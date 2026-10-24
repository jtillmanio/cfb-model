"""Deletes the Vercel deployments nothing needs any more (D-126, vercel-cleanup.yml).

Each deployment keeps its own copy of the functions, and the Hobby plan's Function Storage is
10 GB, so previews of closed PRs and old `main` builds pile up against it. `python -m db
vercel-cleanup --branch <b>` deletes one closed PR's previews; with no `--branch` it sweeps the
project. Never deleted: the deployment serving production, the newest `KEEP_MAIN` ready `main`
builds (release and rollback candidates), anything still building, a preview whose PR is open,
and anything not built from git. The decision is pure (`plan_cleanup`); the clients reuse
db.release's.
"""

from __future__ import annotations

import argparse
import time
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

from db.release import (
    GITHUB,
    VERCEL,
    ApiRefused,
    ReleaseRefused,
    _call,
    _need,
    _refusing,
    _summary,
    _vercel_scope,
)

KEEP_MAIN = 5
FRESH_MS = 24 * 60 * 60 * 1000  # a sweep leaves younger previews: their PR may not be open yet
FINISHED = {"READY", "ERROR", "CANCELED"}
MAIN = "main"


@dataclass(frozen=True)
class Build:
    id: str
    url: str
    branch: str
    created: int  # ms since the epoch
    state: str
    target: str | None

    @classmethod
    def from_vercel(cls, d: Mapping[str, Any]) -> Build:
        meta = d.get("meta") or {}
        return cls(
            id=d["uid"],
            url=d.get("url") or "",
            branch=meta.get("githubCommitRef") or "",
            created=int(d.get("created") or d.get("createdAt") or 0),
            state=d.get("readyState") or d.get("state") or "",
            target=d.get("target"),
        )

    @property
    def is_main(self) -> bool:
        return self.target == "production" or self.branch == MAIN


@dataclass(frozen=True)
class Verdict:
    build: Build
    delete: bool
    reason: str


# ─── Decision ────────────────────────────────────────────────────────────────────────────────


def plan_cleanup(
    builds: Iterable[Build],
    *,
    production: set[str],
    open_branches: set[str],
    now_ms: int,
    keep_main: int = KEEP_MAIN,
    branch: str | None = None,
) -> list[Verdict]:
    """What to delete and why, newest first. With `branch`, only that branch's previews."""
    if not production:
        raise ReleaseRefused("Couldn't tell which deployment serves production; nothing deleted.")
    if keep_main < 1:
        raise ReleaseRefused(f"--keep-main must be at least 1, not {keep_main}.")
    if branch is not None and (not branch or branch == MAIN):
        raise ReleaseRefused(f"--branch deletes a closed PR's previews; {branch!r} isn't one.")

    builds = sorted(builds, key=lambda b: b.created, reverse=True)
    if branch is not None:
        builds = [b for b in builds if b.branch == branch and not b.is_main]
    ready_main = [
        b.id for b in builds if b.is_main and b.state == "READY" and b.id not in production
    ]
    newest_main = set(ready_main[:keep_main])  # production is kept on top of these

    verdicts = []
    for b in builds:
        if b.id in production:
            verdicts.append(Verdict(b, False, "serving production"))
        elif b.state not in FINISHED:
            verdicts.append(Verdict(b, False, f"still {b.state.lower() or 'starting'}"))
        elif not b.branch:
            verdicts.append(Verdict(b, False, "not built from git"))
        elif b.is_main:
            if b.id in newest_main:
                verdicts.append(Verdict(b, False, f"one of the newest {keep_main} main builds"))
            elif b.state == "READY":
                verdicts.append(Verdict(b, True, f"older than the newest {keep_main} main builds"))
            else:
                verdicts.append(Verdict(b, True, f"main build {b.state.lower()}"))
        elif b.branch in open_branches:
            verdicts.append(Verdict(b, False, "its PR is open"))
        elif branch is None and now_ms - b.created < FRESH_MS:
            verdicts.append(Verdict(b, False, "under a day old"))
        else:
            verdicts.append(Verdict(b, True, "preview with no open PR"))
    return verdicts


def render_summary(verdicts: Sequence[Verdict], *, dry_run: bool, failed: Sequence[str]) -> str:
    deleted = [v for v in verdicts if v.delete and v.build.id not in failed]
    title = "## Vercel cleanup (dry run: nothing deleted)" if dry_run else "## Vercel cleanup"
    counts: dict[tuple[bool, str], int] = {}
    for v in verdicts:
        counts[(v.delete, v.reason)] = counts.get((v.delete, v.reason), 0) + 1
    lines = [title, "", "| | Reason | Deployments |", "|---|---|---|"]
    for (delete, reason), n in sorted(counts.items(), key=lambda kv: (not kv[0][0], kv[0][1])):
        action = ("would delete" if dry_run else "deleted") if delete else "kept"
        lines.append(f"| {action} | {reason} | {n} |")
    if failed:
        lines += ["", f"**Failed to delete {len(failed)}:** {', '.join(failed)}"]
    if deleted:
        lines += ["", "<details><summary>Deployments</summary>", ""]
        lines += [f"- `{v.build.id}` {v.build.branch} ({v.reason})" for v in deleted]
        lines += ["", "</details>"]
    return "\n".join(lines) + "\n"


# ─── Clients ─────────────────────────────────────────────────────────────────────────────────


def fetch_builds() -> list[Build]:
    """Every deployment of the project, newest first, following Vercel's `until` pagination."""
    builds: list[Build] = []
    until: int | None = None
    while True:
        params: dict[str, Any] = {"projectId": _need("VERCEL_PROJECT_ID"), "limit": 100,
                                  **_vercel_scope()}
        if until:
            params["until"] = until
        data = _call("GET", f"{VERCEL}/v6/deployments", _need("VERCEL_TOKEN"), params=params)
        builds += [Build.from_vercel(d) for d in data["deployments"]]
        until = (data.get("pagination") or {}).get("next")
        if not until:
            return builds


def fetch_production(production_url: str) -> set[str]:
    """The deployment the production domain points at, and the project's production target."""
    token, found = _need("VERCEL_TOKEN"), set()
    host = urlsplit(production_url).hostname or production_url
    alias = _call("GET", f"{VERCEL}/v4/aliases/{host}", token, params=_vercel_scope())
    if alias.get("deploymentId"):
        found.add(alias["deploymentId"])
    project = _call("GET", f"{VERCEL}/v9/projects/{_need('VERCEL_PROJECT_ID')}", token,
                    params=_vercel_scope())
    if target := ((project.get("targets") or {}).get("production") or {}).get("id"):
        found.add(target)
    return found


def fetch_open_branches() -> set[str]:
    repo = _need("GITHUB_REPOSITORY")
    data = _call("GET", f"{GITHUB}/repos/{repo}/pulls", _need("GITHUB_TOKEN"),
                 params={"state": "open", "per_page": 100})
    return {p["head"]["ref"] for p in data}


def delete_build(deployment_id: str, *, attempts: int = 4, wait: float = 30.0) -> None:
    """Deletes one deployment; one already gone passes, and a rate limit waits and retries."""
    for attempt in range(1, attempts + 1):
        try:
            _call("DELETE", f"{VERCEL}/v13/deployments/{deployment_id}", _need("VERCEL_TOKEN"),
                  params=_vercel_scope())
            return
        except ApiRefused as e:
            if e.status == 404:
                return
            if e.status != 429 or attempt == attempts:
                raise
            print(f"Rate limited deleting {deployment_id}; waiting {wait:.0f} s")
            time.sleep(wait)


# ─── Command ─────────────────────────────────────────────────────────────────────────────────


@_refusing
def cleanup(args: argparse.Namespace) -> None:
    verdicts = plan_cleanup(
        fetch_builds(),
        production=fetch_production(_need("PRODUCTION_URL")),
        open_branches=fetch_open_branches(),
        now_ms=int(time.time() * 1000),
        keep_main=args.keep_main,
        branch=args.branch,
    )
    failed: list[str] = []
    if not args.dry_run:
        for v in verdicts:
            if not v.delete:
                continue
            try:
                delete_build(v.build.id)
                print(f"Deleted {v.build.id} ({v.build.branch}: {v.reason})")
            except ReleaseRefused as e:
                print(f"Couldn't delete {v.build.id}: {e}")
                failed.append(v.build.id)
            time.sleep(args.pause)
    _summary(render_summary(verdicts, dry_run=args.dry_run, failed=failed))
    if failed:
        raise ReleaseRefused(f"{len(failed)} deployment(s) couldn't be deleted; re-run to retry.")


def add_command(subparsers: Any) -> None:
    p = subparsers.add_parser(
        "vercel-cleanup", help="Delete Vercel deployments of closed PRs and old main builds"
    )
    p.add_argument("--branch", help="Only this closed PR's previews (default: sweep the project)")
    p.add_argument("--keep-main", type=int, default=KEEP_MAIN)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--pause", type=float, default=0.5, help="Seconds between deletes")
    p.set_defaults(func=cleanup)
