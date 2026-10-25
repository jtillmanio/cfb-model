"""Whether a `schedule` run of results.yml or lines.yml is a late fallback with nothing to do
(TASK-028, D-129). The dispatcher starts each job on time; the workflow's cron is only a fallback.
GitHub starts scheduled runs 5-8 hours late, so the check is anchored to the cron's own slot, not
to when the run happened to start: skip when a dispatched run of the same workflow succeeded at or
after SLOT - 3 hours. Standard library only: the guard runs before the job's dependencies."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

# Every dispatcher time is 1-2 h before its fallback cron (ET to UTC), so 3 h always reaches it.
LOOKBACK = timedelta(hours=3)

Runner = Callable[[list[str]], subprocess.CompletedProcess[str]]


@dataclass(frozen=True)
class Decision:
    skip: bool
    summary: str


def _weekdays(field: str) -> set[int]:
    """Cron weekdays (0 = Sunday) from `*` or a comma list."""
    if field == "*":
        return set(range(7))
    return {int(d) % 7 for d in field.split(",")}


def slot(cron: str, now: datetime) -> datetime:
    """The latest UTC firing of `cron` at or before `now`. Reads `M H * * D` only (minute, hour,
    `*` or a comma list of weekdays), which is all the workflows use."""
    parts = cron.split()
    try:
        if len(parts) != 5 or parts[2] != "*" or parts[3] != "*":
            raise ValueError
        minute, hour, days = int(parts[0]), int(parts[1]), _weekdays(parts[4])
    except ValueError:
        raise ValueError(
            f"cron {cron!r} is not 'M H * * D' with a number minute and hour"
        ) from None
    for back in range(8):
        day = (now - timedelta(days=back)).date()
        fired = datetime(day.year, day.month, day.day, hour, minute, tzinfo=UTC)
        if (fired.weekday() + 1) % 7 in days and fired <= now:
            return fired
    raise ValueError(f"cron {cron!r} never fires")


def _stamp(moment: datetime) -> str:
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def decide(
    event: str, cron: str | None, now: datetime, dispatched_at: Sequence[datetime]
) -> Decision:
    """Skip a fallback run when a dispatched run succeeded in [slot - 3 h, now]. A dispatch with
    no cron, or a schedule run whose cron is unknown, runs: doubt means run."""
    if not cron:
        return Decision(False, "Running: not a scheduled fallback.")
    since = slot(cron, now) - LOOKBACK
    recent = sorted(d for d in dispatched_at if since <= d <= now)
    if recent:
        return Decision(
            True,
            f"Skipped: the dispatcher's run succeeded at {_stamp(recent[-1])}, since "
            f"{_stamp(since)} (3 hours before this run's {cron} slot).",
        )
    return Decision(
        False,
        f"No dispatched run succeeded since {_stamp(since)} (3 hours before this run's "
        f"{cron} slot): running as the fallback.",
    )


def _gh(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, capture_output=True, text=True, check=False)


def main(
    argv: list[str] | None = None,
    now: datetime | None = None,
    run: Runner = _gh,
) -> int:
    parser = argparse.ArgumentParser(prog="engine fallback")
    parser.add_argument("--event", required=True)
    parser.add_argument("--schedule", default="", help="The cron that fired, or a test cron")
    parser.add_argument("--workflow", required=True, help="Workflow file name, e.g. results.yml")
    parser.add_argument("--summary", help="Append the decision as markdown ($GITHUB_STEP_SUMMARY)")
    args = parser.parse_args(argv)
    now = now or datetime.now(UTC)

    cron = args.schedule or None
    dispatched: list[datetime] = []
    if cron:
        done = run(
            [
                "gh",
                "run",
                "list",
                "--repo",
                os.environ.get("GITHUB_REPOSITORY", ""),
                "--workflow",
                args.workflow,
                "--event",
                "workflow_dispatch",
                "--status",
                "success",
                "--limit",
                "50",
                "--json",
                "createdAt",
            ]
        )
        if done.returncode != 0:
            print(f"gh run list failed: {done.stderr.strip()}", file=sys.stderr)
            raise SystemExit(1)
        dispatched = [
            datetime.fromisoformat(r["createdAt"].replace("Z", "+00:00"))
            for r in json.loads(done.stdout)
        ]
    decision = decide(args.event, cron, now, dispatched)
    print(decision.summary)
    if args.summary:
        with open(args.summary, "a", encoding="utf-8") as f:
            f.write(f"`{args.workflow}`: {decision.summary}\n")
    with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as f:
        f.write(f"skip={'true' if decision.skip else 'false'}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
