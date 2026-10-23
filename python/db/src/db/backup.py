"""The backup workflow's logic (TASK-006, D-019, docs/02-architecture.md › Release & operations).

`.github/workflows/backup.yml` calls these as `python -m db backup dump|verify|upload`. `dump` reads
production through `BACKUP_DATABASE_URL` (a read-only role) and counts its rows in the same
snapshot `pg_dump` uses, so the counts match the dump exactly even if a job writes meanwhile.
`verify` runs against the restored copy in the job's local container: it re-applies the views,
queries each one, and compares row counts. Pure decisions first, then the database reads, then
the commands. docs/runbooks/restore.md is the manual restore.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from sqlalchemy import Connection, text

from db.migrate import VIEWS_DIR, apply_views
from db.release import _output, _summary  # the release workflow's job outputs and summary
from db.session import make_engine

BACKUP_URL_VAR = "BACKUP_DATABASE_URL"
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}

# Every ordinary and partitioned table outside the system schemas, as a quoted `schema.table`.
_TABLES = """
    SELECT format('%I.%I', n.nspname, c.relname)
    FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE c.relkind IN ('r', 'p')
      AND n.nspname <> 'information_schema' AND n.nspname NOT LIKE 'pg\\_%'
    ORDER BY 1
"""
_VIEWS = """
    SELECT format('%I.%I', schemaname, viewname) FROM pg_views
    WHERE schemaname <> 'information_schema' AND schemaname NOT LIKE 'pg\\_%'
    ORDER BY 1
"""


class BackupFailed(RuntimeError):
    """The backup can't be trusted. Nothing is uploaded; the message says why."""


# ─── Decisions ───────────────────────────────────────────────────────────────────────────────


def compare_counts(production: Mapping[str, int], restored: Mapping[str, int]) -> list[str]:
    """One line per table whose counts differ or that exists on one side only; empty if equal."""
    failures = []
    for table in sorted(production.keys() | restored.keys()):
        ours, theirs = production.get(table), restored.get(table)
        if ours != theirs:
            failures.append(
                f"{table}: production {_count(ours)}, restored {_count(theirs)}"
            )
    return failures


def check_dump(returncode: int, path: Path) -> int:
    """The dump's size in bytes; refuses a failed `pg_dump` or an empty (or missing) file."""
    if returncode != 0:
        raise BackupFailed(f"pg_dump exited {returncode}.")
    size = path.stat().st_size if path.is_file() else 0
    if size == 0:
        raise BackupFailed(f"The dump {path} is empty.")
    return size


def require_local(url: str) -> str:
    """`verify` writes views, so it runs only against the job's local restore container."""
    if (urlsplit(url).hostname or "").lower() not in LOCAL_HOSTS:
        raise BackupFailed("verify runs only against the local restore container (localhost).")
    return url


def run_date(now: datetime) -> date:
    """The run's UTC date, fixed once by `dump` so a run that crosses midnight writes one day."""
    return now.astimezone(UTC).date()


def object_keys(day: date) -> list[str]:
    """The keys one run writes (D-124): daily always, weekly on a Sunday, monthly on the 1st.

    Each prefix expires by the bucket's own lifecycle rule, never from here. A re-run that day
    replaces its keys with a newer verified dump; a missed Sunday or 1st isn't made up later."""
    keys = [f"backups/daily/{day:%Y-%m-%d}.dump"]
    if day.weekday() == 6:
        keys.append(f"backups/weekly/{day:%Y-%m-%d}.dump")
    if day.day == 1:
        keys.append(f"backups/monthly/{day:%Y-%m-%d}.dump")
    return keys


def render_summary(
    production: Mapping[str, int],
    restored: Mapping[str, int],
    *,
    dump_size: int,
    views: Mapping[str, int],
    failures: Sequence[str],
) -> str:
    lines = ["## Backup", "", "| Table | Production | Restored |", "|---|---|---|"]
    for table in sorted(production.keys() | restored.keys()):
        lines.append(
            f"| {table} | {_count(production.get(table))} | {_count(restored.get(table))} |"
        )
    lines += [
        "",
        f"Dump: {_size(dump_size)} ({dump_size:,} bytes)",
        "Views: "
        + (", ".join(f"{v} ({n} rows)" for v, n in views.items()) if views else "none"),
        "",
        f"**Row counts differ:** {'; '.join(failures)}" if failures else "Row counts match.",
    ]
    return "\n".join(lines) + "\n"


def _count(value: int | None) -> str:
    return "missing" if value is None else str(value)


def _size(n: int) -> str:
    return f"{n / 1024:.1f} KB" if n < 1024 * 1024 else f"{n / (1024 * 1024):.1f} MB"


# ─── Database reads ──────────────────────────────────────────────────────────────────────────


@contextmanager
def snapshot_transaction(url: str) -> Iterator[tuple[Connection, str]]:
    """A read-only REPEATABLE READ transaction and its exported snapshot ID. `pg_dump --snapshot`
    sees exactly what this transaction sees, for as long as it stays open; it's rolled back."""
    with make_engine(url).connect() as conn:
        conn = conn.execution_options(isolation_level="REPEATABLE READ", postgresql_readonly=True)
        snapshot = conn.execute(text("SELECT pg_export_snapshot()")).scalar_one()
        try:
            yield conn, snapshot
        finally:
            conn.rollback()


def count_rows(conn: Connection) -> dict[str, int]:
    """Exact row counts for every table, read in the connection's current transaction."""
    tables = conn.execute(text(_TABLES)).scalars().all()
    return {t: conn.execute(text(f"SELECT count(*) FROM {t}")).scalar_one() for t in tables}


def query_views(conn: Connection) -> dict[str, int]:
    """Every view answers a full SELECT (all columns, all rows); names the first that doesn't.

    A production restore can't match the fixture values the view tests assert (02 › Testing
    strategy), so this proves each view still runs against the real data (D-109)."""
    rows = {}
    for view in conn.execute(text(_VIEWS)).scalars().all():
        try:
            rows[view] = len(conn.execute(text(f"SELECT * FROM {view}")).fetchall())
        except Exception as e:
            raise BackupFailed(f"View {view} failed: {e}") from None
    return rows


# ─── Commands ────────────────────────────────────────────────────────────────────────────────


def _failing(step: Callable[[argparse.Namespace], None]) -> Callable[[argparse.Namespace], None]:
    """A failure ends the step non-zero and says why in the job summary."""

    def run(args: argparse.Namespace) -> None:
        try:
            step(args)
        except BackupFailed as e:
            _summary(f"**Backup failed:** {e}")
            raise SystemExit(f"Backup failed: {e}") from None

    return run


@_failing
def dump(args: argparse.Namespace) -> None:
    url = os.environ.get(BACKUP_URL_VAR, "").strip()
    if not url:
        raise BackupFailed(f"{BACKUP_URL_VAR} is not set.")
    if (urlsplit(url).hostname or "").partition(".")[0].endswith("-pooler"):
        # A snapshot can't be shared through PgBouncer's transaction mode (D-016).
        raise BackupFailed(f"{BACKUP_URL_VAR} is Neon's pooled host; the dump needs the direct.")
    out: Path = args.out
    with snapshot_transaction(url) as (conn, snapshot):
        # Count first: the snapshot is already fixed, and the session then sits idle while
        # pg_dump runs, so a dropped idle session can't fail a good dump at the count.
        counts = count_rows(conn)
        result = subprocess.run(
            ["pg_dump", "--format=custom", f"--snapshot={snapshot}", f"--file={out}",
             f"--dbname={url}"],
            check=False,
        )
        size = check_dump(result.returncode, out)
    args.counts.write_text(json.dumps(counts, indent=2, sort_keys=True), encoding="utf-8")
    print(f"Dumped {len(counts)} tables, {_size(size)}.")
    _output(size=str(size), date=run_date(datetime.now(UTC)).isoformat())


@_failing
def verify(args: argparse.Namespace) -> None:
    url = require_local(args.restored_url)
    production: dict[str, int] = json.loads(args.counts.read_text(encoding="utf-8"))
    size = check_dump(0, args.dump)
    views_dir: Path = args.views or VIEWS_DIR
    if not views_dir.is_dir():
        # A wrong path would apply zero views and still pass.
        raise BackupFailed(f"The views directory {views_dir} doesn't exist.")
    apply_views(url, views_dir)
    with make_engine(url).connect() as conn:
        views = query_views(conn)
        restored = count_rows(conn)
    failures = compare_counts(production, restored)
    _summary(
        render_summary(production, restored, dump_size=size, views=views, failures=failures)
    )
    if failures:
        raise BackupFailed("Row counts differ: " + "; ".join(failures))


@_failing
def upload(args: argparse.Namespace) -> None:
    """`aws s3 cp` the verified dump to each of the day's keys (D-124). A failed key doesn't stop
    the rest; the summary says which were written, and any failure fails the step."""
    bucket = os.environ.get("R2_BUCKET", "").strip()
    account = os.environ.get("R2_ACCOUNT_ID", "").strip()
    if not bucket or not account:
        raise BackupFailed("R2_BUCKET and R2_ACCOUNT_ID must both be set.")
    endpoint = f"https://{account}.r2.cloudflarestorage.com"
    written, failed = [], []
    for key in object_keys(args.date):
        result = subprocess.run(
            ["aws", "s3", "cp", str(args.dump), f"s3://{bucket}/{key}", "--no-progress",
             "--endpoint-url", endpoint],
            check=False,
        )
        (written if result.returncode == 0 else failed).append(key)
    commit = os.environ.get("PROD_COMMIT", "").strip()
    lines = [f"Uploaded to `{bucket}`" + (f" (production at `{commit}`):" if commit else ":"), ""]
    lines += [f"- Written: `{key}`" for key in written]
    lines += [f"- **Not written:** `{key}`" for key in failed]
    _summary("\n".join(lines))
    if failed:
        raise BackupFailed("Not written: " + ", ".join(failed))


def add_commands(subparsers: Any) -> None:
    backup = subparsers.add_parser("backup", help="Steps of the backup workflow")
    steps = backup.add_subparsers(dest="step", required=True)

    p = steps.add_parser("dump", help=f"pg_dump {BACKUP_URL_VAR} and count its rows")
    p.add_argument("--out", type=Path, required=True, help="The dump file (custom format)")
    p.add_argument("--counts", type=Path, required=True, help="Where to write the row counts")
    p.set_defaults(func=dump)

    p = steps.add_parser("verify", help="Check the restored copy: views and row counts")
    p.add_argument("--restored-url", required=True, help="The local restore container")
    p.add_argument("--counts", type=Path, required=True, help="Production's counts from dump")
    p.add_argument("--dump", type=Path, required=True, help="The dump file, for its size")
    p.add_argument("--views", type=Path, help="The views to apply (default: this checkout's)")
    p.set_defaults(func=verify)

    p = steps.add_parser("upload", help="Write the verified dump to each of the day's R2 keys")
    p.add_argument("--dump", type=Path, required=True, help="The verified dump file")
    p.add_argument("--date", type=date.fromisoformat, required=True,
                   help="The run's UTC date (dump's `date` output)")
    p.set_defaults(func=upload)
