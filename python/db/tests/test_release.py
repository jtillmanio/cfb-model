"""The release workflow's logic (TASK-005, docs/02-architecture.md › Release & operations)."""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from db import release
from db.__main__ import main
from db.migrate import heads
from db.release import (
    CheckRun,
    Deployment,
    ReleaseRefused,
    current_heads,
    endpoint_id,
    pending_migrations,
    pick_deployment,
    render_pending_summary,
    render_plan_summary,
    require_ci_passed,
    script_directory,
    single_head,
    smoke_check,
    snapshot_name,
)

C1 = "1111111aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
C2 = "2222222bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
C3 = "3333333ccccccccccccccccccccccccccccccccc"
BRANCH = "4444444ddddddddddddddddddddddddddddddddd"
MAIN = [C3, C2, C1]  # newest first, as GitHub lists them


def build(commit: str, created: int, state: str = "READY", target: str | None = "production"):
    return Deployment(
        id=f"dpl_{commit[:4]}", url=f"cfb-{commit[:4]}.vercel.app", commit=commit,
        created=created, state=state, target=target,
    )


def run(status: str, conclusion: str | None, id: int = 10, name="verify"):
    return CheckRun(name=name, status=status, conclusion=conclusion, id=id)


# ─── AC-1: plan ───────────────────────────────────────────────────────────────────────────────


def test_picks_the_newest_ready_production_build_on_main():
    builds = [build(C1, 100), build(C2, 300), build(C3, 200)]
    assert pick_deployment(builds, MAIN).commit == C2


def test_skips_builds_that_are_not_ready_or_not_production():
    builds = [
        build(C1, 100),
        build(C3, 300, state="BUILDING"),
        build(C2, 200, state="ERROR"),
        build(C2, 250, target=None),
    ]
    assert pick_deployment(builds, MAIN).commit == C1


def test_skips_builds_whose_commit_is_not_on_main():
    builds = [build(C1, 100), build(BRANCH, 900)]
    assert pick_deployment(builds, MAIN).commit == C1


def test_picks_the_requested_commit_by_prefix():
    builds = [build(C1, 100), build(C2, 300)]
    assert pick_deployment(builds, MAIN, commit=C1[:7]).commit == C1


def test_refuses_when_no_ready_build_is_on_main():
    builds = [build(C3, 300, state="BUILDING"), build(BRANCH, 900)]
    with pytest.raises(ReleaseRefused, match=f"No ready production build.*{C3[:7]}"):
        pick_deployment(builds, MAIN)


def test_refuses_a_requested_commit_without_a_ready_build():
    builds = [build(C1, 100), build(C2, 300, state="BUILDING")]
    with pytest.raises(ReleaseRefused, match=f"No ready production build for {C2[:7]}"):
        pick_deployment(builds, MAIN, commit=C2[:7])


def test_refuses_a_requested_commit_shorter_than_seven_characters():
    with pytest.raises(ReleaseRefused, match="at least 7"):
        pick_deployment([build(C1, 100)], MAIN, commit=C1[:6])


def test_ci_passes_when_the_latest_verify_run_succeeded():
    runs = [
        run("completed", "failure", 1),
        run("completed", "success", 2),
        run("completed", "failure", 3, name="lighthouse"),
    ]
    assert require_ci_passed(C1, runs) == "success"


def test_ci_refuses_a_failed_verify_run_and_names_the_commit():
    runs = [
        run("completed", "success", 1),
        run("completed", "failure", 2),
    ]
    with pytest.raises(ReleaseRefused, match=f"{C1}.*failure"):
        require_ci_passed(C1, runs)


def test_ci_refuses_while_verify_is_still_running():
    with pytest.raises(ReleaseRefused, match=f"{C1}.*still running"):
        require_ci_passed(C1, [run("in_progress", None)])


def test_ci_refuses_while_a_newer_rerun_is_queued():
    # A queued run has no start time yet; it's still the newest, so CI hasn't settled.
    runs = [run("completed", "success", 1), run("queued", None, 2)]
    with pytest.raises(ReleaseRefused, match=f"{C1}.*still running"):
        require_ci_passed(C1, runs)


def test_ci_refuses_when_verify_never_ran():
    with pytest.raises(ReleaseRefused, match=f"{C1}"):
        require_ci_passed(C1, [run("completed", "success", name="lighthouse")])


def test_plan_command_exits_non_zero_and_names_the_commit_when_ci_failed(monkeypatch, capsys):
    # Under CI these point at the real job's files; the refusal must not write into them.
    monkeypatch.delenv("GITHUB_OUTPUT", raising=False)
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    monkeypatch.setattr(release, "fetch_deployments", lambda: [build(C2, 300)])
    monkeypatch.setattr(release, "fetch_main_commits", lambda branch: MAIN)
    monkeypatch.setattr(release, "fetch_check_runs", lambda sha: [run("completed", "failure")])
    with pytest.raises(SystemExit) as exc:
        main(["release", "plan"])
    assert exc.value.code not in (0, None)
    assert C2 in str(exc.value.code)


def test_plan_command_writes_the_outputs_and_summary(monkeypatch, tmp_path):
    out, summary = tmp_path / "out", tmp_path / "summary"
    monkeypatch.setenv("GITHUB_OUTPUT", str(out))
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    monkeypatch.setattr(release, "fetch_deployments", lambda: [build(C2, 300)])
    monkeypatch.setattr(release, "fetch_main_commits", lambda branch: MAIN)
    monkeypatch.setattr(release, "fetch_check_runs", lambda sha: [run("completed", "success")])
    main(["release", "plan"])
    assert f"commit={C2}" in out.read_text().splitlines()
    assert "deployment_id=dpl_2222" in out.read_text().splitlines()
    assert C2 in summary.read_text()


# ─── AC-2: smoke ──────────────────────────────────────────────────────────────────────────────


def healthy(**overrides):
    return {"commit": C2, "db_reachable": True, "migration_head": "0001", **overrides}


def test_smoke_passes_for_the_right_commit_head_and_a_guarded_api():
    assert smoke_check(healthy(), commit=C2, head="0001", unsigned_status=401) == []


def test_smoke_fails_on_a_different_commit():
    failures = smoke_check(healthy(commit=C1), commit=C2, head="0001", unsigned_status=401)
    assert len(failures) == 1
    assert failures[0].startswith("commit")


def test_smoke_fails_when_the_database_is_unreachable():
    failures = smoke_check(
        healthy(db_reachable=False, migration_head=None), commit=C2, head="0001",
        unsigned_status=401,
    )
    assert failures[0].startswith("db_reachable")


def test_smoke_fails_on_a_different_migration_head():
    failures = smoke_check(healthy(migration_head="0000"), commit=C2, head="0001",
                           unsigned_status=401)
    assert len(failures) == 1
    assert failures[0].startswith("migration_head")


def test_smoke_fails_when_the_api_answers_without_a_token():
    failures = smoke_check(healthy(), commit=C2, head="0001", unsigned_status=200)
    assert len(failures) == 1
    assert failures[0].startswith("unsigned GET /api/py/teams")


def test_the_expected_head_is_the_repos_single_alembic_head():
    assert [single_head(script_directory())] == heads()


def test_current_heads_reads_the_migrated_databases_head(test_db_url):
    # The same read the plan job makes of production, here on the migrated test DB.
    assert current_heads(test_db_url) == tuple(heads())


# ─── Pending migrations and the snapshot ──────────────────────────────────────────────────────


def write_chain(root: Path, *revisions: tuple[str, str | None]) -> Path:
    versions = root / "versions"
    versions.mkdir(parents=True)
    for rev, down in revisions:
        (versions / f"{rev}_m.py").write_text(
            f"revision = {rev!r}\ndown_revision = {down!r}\nbranch_labels = None\n"
            "depends_on = None\n\ndef upgrade():\n    pass\n",
            encoding="utf-8",
        )
    return root


@pytest.fixture
def chain(tmp_path):
    revisions = (("0001", None), ("0002", "0001"), ("0003", "0002"))
    return script_directory(write_chain(tmp_path, *revisions))


def test_every_migration_is_pending_on_an_empty_database(chain):
    assert pending_migrations(chain, ()) == ["0001", "0002", "0003"]


def test_only_newer_migrations_are_pending(chain):
    assert pending_migrations(chain, ("0001",)) == ["0002", "0003"]


def test_nothing_is_pending_at_head(chain):
    assert pending_migrations(chain, ("0003",)) == []


def test_refuses_when_production_is_at_a_revision_the_commit_does_not_know(chain):
    with pytest.raises(ReleaseRefused, match="9999"):
        pending_migrations(chain, ("9999",))


def test_refuses_a_commit_with_two_heads(tmp_path):
    two = script_directory(write_chain(tmp_path, ("000a", None), ("000b", None)))
    with pytest.raises(ReleaseRefused, match="2 heads"):
        single_head(two)


def test_snapshot_name_carries_the_time_and_short_commit():
    when = datetime(2026, 10, 12, 18, 5, tzinfo=UTC)
    assert snapshot_name(C2, when) == "release/20261012-1805-2222222"


def test_endpoint_id_comes_from_the_host_with_the_pooler_suffix_folded():
    assert endpoint_id("postgresql://u:p@ep-cool-9-pooler.c-6.us-east-2.aws.neon.tech/db") == (
        "ep-cool-9"
    )
    assert endpoint_id("postgresql://u:p@ep-cool-9.c-6.us-east-2.aws.neon.tech/db") == "ep-cool-9"


# ─── AC-5: the job summary ────────────────────────────────────────────────────────────────────


def test_plan_summary_names_the_commit_build_and_ci():
    text = render_plan_summary(build(C2, 300), "success", main_head=C3)
    assert C2 in text
    assert "dpl_2222" in text
    assert "success" in text
    assert C3[:7] in text  # main's newer commit, which has no ready build yet


def test_dry_run_summary_lists_pending_and_says_nothing_changed():
    text = render_pending_summary(["0002"], head="0002", current=("0001",), dry_run=True)
    assert "0002" in text
    assert "no snapshot was made, no migration ran and nothing was promoted" in text


def test_summary_says_none_when_nothing_is_pending():
    text = render_pending_summary([], head="0001", current=("0001",), dry_run=True)
    assert "Pending migrations | none" in text
    # A table of its own (header + separator), or GitHub shows the rows as plain text.
    assert text.splitlines()[1] == "|---|---|"
