"""The merged-migration check (TASK-009, D-020): CI fails a change that edits, renames or deletes a
migration already on `main`."""

import subprocess
from pathlib import Path

import pytest

from db.__main__ import main
from db.merged_migrations import violations

V = "python/db/migrations/versions"


# ─── AC-1: the pure check over `git diff --name-status` lines ────────────────────────────────


def test_a_modified_migration_fails_and_is_named():
    assert violations([f"M\t{V}/0001_reference_tables.py"]) == [
        f"modified: {V}/0001_reference_tables.py"
    ]


def test_a_renamed_migration_fails_and_names_both_paths():
    assert violations([f"R100\t{V}/0001_reference_tables.py\t{V}/0001_renamed.py"]) == [
        f"renamed: {V}/0001_reference_tables.py -> {V}/0001_renamed.py"
    ]


def test_a_migration_moved_out_of_the_folder_fails():
    assert violations([f"R097\t{V}/0001_reference_tables.py\tpython/db/old/0001.py"]) == [
        f"renamed: {V}/0001_reference_tables.py -> python/db/old/0001.py"
    ]


def test_a_deleted_migration_fails_and_is_named():
    assert violations([f"D\t{V}/0001_reference_tables.py"]) == [
        f"deleted: {V}/0001_reference_tables.py"
    ]


def test_a_type_change_counts_as_an_edit():
    assert violations([f"T\t{V}/0001_reference_tables.py"]) == [
        f"modified: {V}/0001_reference_tables.py"
    ]


def test_every_offending_file_is_named():
    lines = [f"M\t{V}/0001_a.py", f"A\t{V}/0003_c.py", f"D\t{V}/0002_b.py"]
    assert violations(lines) == [f"modified: {V}/0001_a.py", f"deleted: {V}/0002_b.py"]


def test_an_added_migration_passes():
    assert violations([f"A\t{V}/0002_next.py"]) == []


def test_a_copy_leaves_its_source_untouched_and_passes():
    assert violations([f"C075\t{V}/0001_reference_tables.py\t{V}/0002_next.py"]) == []


def test_changes_outside_the_folder_pass():
    lines = [
        "M\tpython/db/src/db/models.py",
        "D\tpython/db/migrations/env.py",
        "M\tpython/db/migrations/versions_notes.md",
        "R100\tdocs/a.md\tdocs/b.md",
        "",
    ]
    assert violations(lines) == []


# ─── AC-1/AC-3: the CLI against a real git history ───────────────────────────────────────────


def git(repo: Path, *args: str) -> str:
    done = subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.com", *args],
        cwd=repo, check=True, capture_output=True, text=True,
    )
    return done.stdout.strip()


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, str]:
    """A repo with one merged migration; returns it and the base commit."""
    git(tmp_path, "init", "-q")
    (tmp_path / V).mkdir(parents=True)
    (tmp_path / V / "0001_reference_tables.py").write_text("revision = '0001'\n")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-q", "-m", "base")
    monkeypatch.chdir(tmp_path)
    return tmp_path, git(tmp_path, "rev-parse", "HEAD")


def test_cli_fails_naming_an_edited_merged_migration(repo, capsys):
    path, base = repo
    (path / V / "0001_reference_tables.py").write_text("revision = '0001'  # edited\n")
    git(path, "commit", "-q", "-am", "edit")

    with pytest.raises(SystemExit) as exit_:
        main(["merged-migrations", "--base", base])

    assert exit_.value.code != 0
    assert f"modified: {V}/0001_reference_tables.py" in capsys.readouterr().out


def test_cli_passes_when_the_branch_only_adds_a_migration(repo, capsys):
    path, base = repo
    (path / V / "0002_next.py").write_text("revision = '0002'\n")
    git(path, "add", ".")
    git(path, "commit", "-q", "-m", "add")

    main(["merged-migrations", "--base", base])

    assert "No migration on the base was edited" in capsys.readouterr().out


def test_cli_passes_after_an_edit_is_reverted(repo):
    path, base = repo
    (path / V / "0001_reference_tables.py").write_text("revision = '0001'  # edited\n")
    git(path, "commit", "-q", "-am", "edit")
    git(path, "revert", "--no-edit", "HEAD")

    main(["merged-migrations", "--base", base])


def test_cli_reports_a_bad_base_instead_of_passing(repo):
    with pytest.raises(SystemExit) as exit_:
        main(["merged-migrations", "--base", "no-such-ref"])
    assert exit_.value.code != 0
