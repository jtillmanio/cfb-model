"""The backup workflow's logic (TASK-006, D-019, docs/02-architecture.md › Release & operations)."""

import re
import subprocess
from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from db.__main__ import main
from db.backup import (
    BackupFailed,
    check_dump,
    compare_counts,
    count_rows,
    object_keys,
    query_views,
    render_summary,
    require_local,
    run_date,
    snapshot_transaction,
)
from db.config import repo_root

WORKFLOWS = repo_root() / ".github" / "workflows"
START_POSTGRES = repo_root() / ".github" / "actions" / "start-postgres" / "action.yml"


# ─── AC-1: row counts ────────────────────────────────────────────────────────────────────────


def test_counts_that_match_pass():
    counts = {"public.teams": 134, "public.alembic_version": 1}
    assert compare_counts(counts, dict(counts)) == []


def test_a_mismatch_names_the_table_and_both_counts():
    failures = compare_counts(
        {"public.teams": 134, "public.alembic_version": 1},
        {"public.teams": 133, "public.alembic_version": 1},
    )
    assert failures == ["public.teams: production 134, restored 133"]


def test_a_table_missing_from_the_restore_is_named():
    failures = compare_counts({"public.teams": 134, "public.venues": 0}, {"public.teams": 134})
    assert failures == ["public.venues: production 0, restored missing"]


def test_a_table_only_in_the_restore_is_named():
    failures = compare_counts({"public.teams": 134}, {"public.teams": 134, "public.extra": 2})
    assert failures == ["public.extra: production missing, restored 2"]


def test_every_difference_is_named_not_only_the_first():
    failures = compare_counts({"public.a": 1, "public.b": 2}, {"public.a": 9, "public.c": 3})
    assert [f.split(":")[0] for f in failures] == ["public.a", "public.b", "public.c"]


def test_count_rows_covers_every_table_of_the_migrated_database(db_conn):
    counts = count_rows(db_conn)
    assert counts["public.alembic_version"] == 1
    assert "public.teams" in counts
    assert not any(name.startswith(("pg_", "information_schema.")) for name in counts)


def test_count_rows_counts_exactly(db_conn):
    before = count_rows(db_conn)["public.alembic_version"]
    db_conn.execute(text("INSERT INTO alembic_version VALUES ('zz_test_only')"))
    assert count_rows(db_conn)["public.alembic_version"] == before + 1


def test_verify_exits_non_zero_and_names_the_table_when_counts_differ(
    monkeypatch, tmp_path, test_db_url
):
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    monkeypatch.setattr("db.backup.require_local", lambda url: url)  # the test DB may be Neon
    counts = tmp_path / "counts.json"
    counts.write_text('{"public.alembic_version": 99}', encoding="utf-8")
    dump = tmp_path / "backup.dump"
    dump.write_bytes(b"x" * 10)
    with pytest.raises(SystemExit) as exc:
        main(["backup", "verify", "--restored-url", test_db_url, "--counts", str(counts),
              "--dump", str(dump)])
    assert "public.alembic_version: production 99, restored 1" in str(exc.value.code)


# ─── AC-3: dump, restore target, views ───────────────────────────────────────────────────────


def test_verify_refuses_a_views_directory_that_does_not_exist(monkeypatch, tmp_path, test_db_url):
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    monkeypatch.setattr("db.backup.require_local", lambda url: url)
    counts = tmp_path / "counts.json"
    counts.write_text("{}", encoding="utf-8")
    dump = tmp_path / "backup.dump"
    dump.write_bytes(b"x")
    with pytest.raises(SystemExit) as exc:
        main(["backup", "verify", "--restored-url", test_db_url, "--counts", str(counts),
              "--dump", str(dump), "--views", str(tmp_path / "no-such-dir")])
    assert "no-such-dir" in str(exc.value.code)


def test_the_dump_refuses_neons_pooled_host(monkeypatch, tmp_path):
    # A snapshot can't be shared through PgBouncer's transaction mode.
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    monkeypatch.setenv("BACKUP_DATABASE_URL", "postgresql://u:p@ep-x-pooler.aws.neon.tech/db")
    with pytest.raises(SystemExit) as exc:
        main(["backup", "dump", "--out", str(tmp_path / "d"), "--counts", str(tmp_path / "c")])
    assert "pooled" in str(exc.value.code)


def test_the_dump_refuses_without_backup_database_url(monkeypatch, tmp_path):
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    monkeypatch.delenv("BACKUP_DATABASE_URL", raising=False)
    with pytest.raises(SystemExit) as exc:
        main(["backup", "dump", "--out", str(tmp_path / "d"), "--counts", str(tmp_path / "c")])
    assert "BACKUP_DATABASE_URL is not set" in str(exc.value.code)


def test_a_dump_with_a_non_zero_exit_is_refused(tmp_path):
    dump = tmp_path / "backup.dump"
    dump.write_bytes(b"partial")
    with pytest.raises(BackupFailed, match="pg_dump exited 1"):
        check_dump(1, dump)


def test_an_empty_dump_is_refused(tmp_path):
    dump = tmp_path / "backup.dump"
    dump.write_bytes(b"")
    with pytest.raises(BackupFailed, match="empty"):
        check_dump(0, dump)


def test_a_missing_dump_is_refused(tmp_path):
    with pytest.raises(BackupFailed, match="empty"):
        check_dump(0, tmp_path / "never-written.dump")


def test_the_dump_reads_in_a_read_only_repeatable_read_snapshot(test_db_url):
    # Production's counts must come from the snapshot pg_dump uses, and nothing may write.
    with snapshot_transaction(test_db_url) as (conn, snapshot):
        assert snapshot
        assert conn.execute(text("SHOW transaction_isolation")).scalar_one() == "repeatable read"
        assert conn.execute(text("SHOW transaction_read_only")).scalar_one() == "on"
        assert count_rows(conn)["public.alembic_version"] == 1


def test_a_good_dump_reports_its_size(tmp_path):
    dump = tmp_path / "backup.dump"
    dump.write_bytes(b"x" * 2048)
    assert check_dump(0, dump) == 2048


@pytest.mark.parametrize(
    "url",
    [
        "postgresql://ci:ci@localhost:5432/restore",
        "postgresql://ci:ci@127.0.0.1:5432/restore",
    ],
)
def test_the_restore_target_may_be_the_local_container(url):
    assert require_local(url) == url


@pytest.mark.parametrize(
    "url",
    [
        "postgresql://u:p@ep-cool-name.us-east-2.aws.neon.tech/neondb",
        "postgresql://u:p@ep-cool-name-pooler.us-east-2.aws.neon.tech/neondb",
        "postgresql://u:p@localhost.evil.example/restore",
        "",
    ],
)
def test_the_restore_target_refuses_anything_but_the_local_container(url):
    with pytest.raises(BackupFailed, match="local"):
        require_local(url)


def test_each_view_answers_a_select(db_conn):
    db_conn.execute(text("CREATE VIEW zz_backup_test_v AS SELECT 1 AS x UNION ALL SELECT 2"))
    assert query_views(db_conn)["public.zz_backup_test_v"] == 2


def test_a_view_that_errors_is_named(db_conn):
    db_conn.execute(text("CREATE VIEW zz_backup_broken_v AS SELECT 1 / 0 AS x"))
    with pytest.raises(BackupFailed, match="public.zz_backup_broken_v"):
        query_views(db_conn)


def test_zero_views_pass(db_conn):
    assert all(name.startswith("public.") for name in query_views(db_conn))


# ─── TASK-024: tiered keys and the upload ────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("day", "keys"),
    [
        (date(2026, 10, 16), ["backups/daily/2026-10-16.dump"]),  # a Friday
        (
            date(2026, 10, 18),  # a Sunday
            ["backups/daily/2026-10-18.dump", "backups/weekly/2026-10-18.dump"],
        ),
        (
            date(2026, 12, 1),  # a Tuesday, the 1st
            ["backups/daily/2026-12-01.dump", "backups/monthly/2026-12-01.dump"],
        ),
        (
            date(2026, 11, 1),  # a Sunday and the 1st
            [
                "backups/daily/2026-11-01.dump",
                "backups/weekly/2026-11-01.dump",
                "backups/monthly/2026-11-01.dump",
            ],
        ),
    ],
)
def test_object_keys_for_a_run_date(day, keys):
    assert object_keys(day) == keys


def test_the_run_date_is_the_utc_date():
    # 23:30 ET on the 17th is already the 18th in UTC.
    assert run_date(datetime(2026, 10, 17, 23, 30, tzinfo=timezone(timedelta(hours=-4)))) == date(
        2026, 10, 18
    )


class FakeAws:
    """Records each `aws` call; fails the ones whose destination contains `fail`."""

    def __init__(self, fail: str | None = None):
        self.fail, self.calls = fail, []

    def __call__(self, cmd, **kwargs):
        self.calls.append(cmd)
        dest = cmd[4]
        return subprocess.CompletedProcess(cmd, 1 if self.fail and self.fail in dest else 0)


def _upload(monkeypatch, tmp_path, fake, day="2026-10-18"):
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    monkeypatch.setenv("R2_BUCKET", "cfb-backups")
    monkeypatch.setenv("R2_ACCOUNT_ID", "acct")
    monkeypatch.setattr("db.backup.subprocess.run", fake)
    dump = tmp_path / "backup.dump"
    dump.write_bytes(b"x" * 10)
    main(["backup", "upload", "--dump", str(dump), "--date", day])
    return summary


def test_upload_writes_every_key_to_r2(monkeypatch, tmp_path):
    fake = FakeAws()
    summary = _upload(monkeypatch, tmp_path, fake)
    dests = [cmd[4] for cmd in fake.calls]
    assert dests == [
        "s3://cfb-backups/backups/daily/2026-10-18.dump",
        "s3://cfb-backups/backups/weekly/2026-10-18.dump",
    ]
    for cmd in fake.calls:
        assert cmd[:3] == ["aws", "s3", "cp"]
        assert cmd[3] == str(tmp_path / "backup.dump")
        assert "https://acct.r2.cloudflarestorage.com" in cmd
    text_ = summary.read_text(encoding="utf-8")
    assert "Written: `backups/daily/2026-10-18.dump`" in text_
    assert "Written: `backups/weekly/2026-10-18.dump`" in text_


def test_upload_writes_every_key_and_names_each_unwritten_one(monkeypatch, tmp_path):
    fake = FakeAws(fail="weekly")
    with pytest.raises(SystemExit) as exc:
        _upload(monkeypatch, tmp_path, fake, day="2026-11-01")
    # A failed key doesn't stop the ones after it.
    assert len(fake.calls) == 3
    assert "backups/weekly/2026-11-01.dump" in str(exc.value.code)
    text_ = (tmp_path / "summary.md").read_text(encoding="utf-8")
    assert "Written: `backups/daily/2026-11-01.dump`" in text_
    assert "**Not written:** `backups/weekly/2026-11-01.dump`" in text_
    assert "Written: `backups/monthly/2026-11-01.dump`" in text_


def test_upload_refuses_without_the_bucket(monkeypatch, tmp_path):
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    monkeypatch.delenv("R2_BUCKET", raising=False)
    monkeypatch.setenv("R2_ACCOUNT_ID", "acct")
    dump = tmp_path / "backup.dump"
    dump.write_bytes(b"x")
    with pytest.raises(SystemExit) as exc:
        main(["backup", "upload", "--dump", str(dump), "--date", "2026-10-16"])
    assert "R2_BUCKET" in str(exc.value.code)


def test_the_upload_step_passes_the_dump_steps_date():
    code = re.sub(r"#.*", "", (WORKFLOWS / "backup.yml").read_text(encoding="utf-8"))
    step = re.split(r"^      - ", code, flags=re.M)[-1]
    assert "db backup upload" in step
    assert '--date "${{ steps.dump.outputs.date }}"' in step
    assert "steps.dump.outputs.key" not in code


# ─── AC-5: the job summary ───────────────────────────────────────────────────────────────────


def test_the_summary_lists_each_tables_counts_on_both_sides_and_the_dump_size():
    summary = render_summary(
        {"public.teams": 134, "public.alembic_version": 1},
        {"public.teams": 134, "public.alembic_version": 1},
        dump_size=2_621_440,
        views={},
        failures=[],
    )
    assert "| public.teams | 134 | 134 |" in summary
    assert "| public.alembic_version | 1 | 1 |" in summary
    assert "2.5 MB" in summary
    assert "Views: none" in summary


# ─── AC-2 and AC-4: the workflows ────────────────────────────────────────────────────────────


def test_pg_major_is_set_once_in_the_start_postgres_action():
    action = START_POSTGRES.read_text(encoding="utf-8")
    assert re.search(r"PG_MAJOR=\d+", action), "the action sets PG_MAJOR"
    for name in ("ci.yml", "backup.yml"):
        workflow = (WORKFLOWS / name).read_text(encoding="utf-8")
        assert "uses: ./.github/actions/start-postgres" in workflow, name
        assert not re.search(r"PG_MAJOR\s*[:=]\s*\"?\d", workflow), f"{name} sets PG_MAJOR"
        assert not re.search(r"postgres(ql)?(-client)?[:-]\d", workflow), f"{name} names a major"


def test_the_backup_installs_the_client_for_pg_major_from_pgdg():
    workflow = (WORKFLOWS / "backup.yml").read_text(encoding="utf-8")
    assert "apt.postgresql.org" in workflow
    assert "postgresql-client-${PG_MAJOR}" in workflow
    assert "/usr/lib/postgresql/${PG_MAJOR}/bin" in workflow


BACKUP_SECRETS = ("R2_BACKUPS_ACCESS_KEY_ID", "R2_BACKUPS_SECRET_ACCESS_KEY", "BACKUP_DATABASE_URL")
BYPASS = "VERCEL_AUTOMATION_BYPASS_SECRET"  # shared with the Lighthouse job; not a backup secret


def test_backup_secrets_appear_only_in_the_backup_workflow():
    for path in WORKFLOWS.glob("*.yml"):
        if path.name == "backup.yml":
            continue
        workflow = path.read_text(encoding="utf-8")
        assert not any(secret in workflow for secret in BACKUP_SECRETS), path.name


def test_secrets_reach_backup_steps_only_through_env():
    lines = (WORKFLOWS / "backup.yml").read_text(encoding="utf-8").splitlines()
    uses = [line for line in lines if "secrets." in line]
    assert {s for s in BACKUP_SECRETS if any(f"secrets.{s}" in line for line in uses)} == set(
        BACKUP_SECRETS
    )
    for line in uses:
        # Only `VAR: ${{ secrets.NAME }}`, which sits under a step's env:, never inline in `run:`.
        assert re.fullmatch(r"\s+[A-Z0-9_]+: \$\{\{ secrets\.[A-Z0-9_]+ \}\}", line), line


def test_the_backup_steps_run_in_order_and_the_upload_comes_last():
    code = re.sub(r"#.*", "", (WORKFLOWS / "backup.yml").read_text(encoding="utf-8"))
    order = [
        code.index("db backup dump"),
        code.index("pg_restore --no-owner"),
        code.index("db backup verify"),
        code.index("db backup upload"),
    ]
    assert order == sorted(order)
    steps = re.split(r"^      - ", code, flags=re.M)
    assert "db backup upload" in steps[-1], "the upload is the job's last step"
    # A failed step must end the job before the upload: nothing may carry on past a failure.
    assert "continue-on-error" not in code
    assert not re.search(r"\b(always|failure|cancelled)\(\)", code)


def test_the_backup_reads_production_only_through_backup_database_url():
    code = re.sub(r"#.*", "", (WORKFLOWS / "backup.yml").read_text(encoding="utf-8"))
    assert set(re.findall(r"secrets\.([A-Z0-9_]+)", code)) == {*BACKUP_SECRETS, BYPASS}
    assert "DATABASE_URL" not in code.replace("BACKUP_DATABASE_URL", "")
    restore_url = re.search(r"RESTORE_URL: (\S+)", code)
    assert restore_url and require_local(restore_url.group(1))


def test_the_health_call_gets_past_vercels_deployment_protection():
    # Should Deployment Protection cover production, health without it is a login page.
    code = re.sub(r"#.*", "", (WORKFLOWS / "backup.yml").read_text(encoding="utf-8"))
    step = next(s for s in re.split(r"^      - ", code, flags=re.M) if "/api/py/health" in s)
    assert f"{BYPASS}: ${{{{ secrets.{BYPASS} }}}}" in step
    assert f'-H "x-vercel-protection-bypass: ${BYPASS}"' in step


def test_the_backup_workflow_runs_nightly_and_on_demand_with_read_only_permissions():
    code = re.sub(r"#.*", "", (WORKFLOWS / "backup.yml").read_text(encoding="utf-8"))
    assert re.search(r"^  schedule:\s*\n\s*- cron:", code, re.M)
    assert re.search(r"^  workflow_dispatch:", code, re.M)
    assert re.search(r"^permissions:\s*\n\s+contents: read\s*$", code, re.M)
    assert "write" not in code
