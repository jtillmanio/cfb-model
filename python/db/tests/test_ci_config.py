"""Repo config TASK-009 adds (D-020, D-021): the merged-migration step in CI, Dependabot's
ecosystems and reasoned ignores, and the protected path the CI check replaces."""

import json
import re

from db.config import repo_root

CI = (repo_root() / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
DEPENDABOT = repo_root() / ".github" / "dependabot.yml"
KIT = repo_root() / ".claude" / "kit.json"


def step_index(name: str) -> int:
    index = CI.find(f"- name: {name}")
    assert index >= 0, f"no step named {name!r} in ci.yml"
    return index


# ─── AC-2: CI runs the check on every PR and push to main, before the migration steps ────────


def test_ci_runs_on_every_pr_and_on_pushes_to_main():
    assert re.search(r"^on:\n  pull_request:\n  push:\n    branches: \[main\]$", CI, re.M)


def test_ci_checks_merged_migrations_before_migrating():
    check = step_index("Merged migrations unchanged")
    assert check < step_index("Migrate the test DB")
    assert check < step_index("Migration checks (one head, models match migrations)")


def test_the_check_diffs_against_the_merge_base_or_the_previous_main():
    step = CI[step_index("Merged migrations unchanged"):step_index("Migrate the test DB")]
    assert "python -m db merged-migrations --base" in step
    assert "format('origin/{0}', github.base_ref)" in step
    assert "github.event.before" in step


def test_checkout_fetches_enough_history_for_the_merge_base():
    checkout = CI[CI.index("uses: actions/checkout@"):step_index("Task files parse cleanly")]
    assert "fetch-depth: 0" in checkout


# ─── AC-4: Dependabot's ecosystems and its reasoned ignores ──────────────────────────────────


def updates() -> list[str]:
    """Each `updates:` entry of dependabot.yml as text."""
    text = DEPENDABOT.read_text(encoding="utf-8")
    return ["- package-ecosystem:" + block for block in text.split("- package-ecosystem:")[1:]]


def entry(ecosystem: str, directory: str) -> str:
    for block in updates():
        if re.match(rf"- package-ecosystem: {ecosystem}\n", block) and (
            re.search(rf'^    directory: "{re.escape(directory)}"$', block, re.M)
            or re.search(rf'^    directories: \[.*"{re.escape(directory)}".*\]$', block, re.M)
        ):
            return block
    raise AssertionError(f"no {ecosystem} entry covers {directory}")


def ignore(block: str, dependency: str) -> str:
    """The ignore rule for one dependency, with the comment line above it."""
    match = re.search(
        rf"^( *#[^\n]*)\n *- dependency-name: {re.escape(dependency)}\n( +[a-z-]+: [^\n]*\n)?",
        block, re.M,
    )
    assert match, f"no ignore for {dependency} with a reason comment above it"
    return match.group(0)


def test_dependabot_covers_every_ecosystem():
    entry("npm", "/")
    entry("npm", "/web")
    entry("npm", "/scripts/perf")
    entry("uv", "/python")
    entry("github-actions", "/")


def test_next_majors_are_ignored_with_a_reason():
    web = entry("npm", "/web")
    for dependency in ("next", "eslint-config-next"):
        rule = ignore(web, dependency)
        assert 'update-types: ["version-update:semver-major"]' in rule
        assert "hand upgrade" in rule


def test_typescript_7_and_later_is_ignored_with_a_reason():
    rule = ignore(entry("npm", "/web"), "typescript")
    assert 'versions: [">=7"]' in rule
    assert "no JS API" in rule


def test_only_majors_and_typescript_7_are_ignored_for_the_app():
    # Every other web dependency still gets its updates.
    web = entry("npm", "/web")
    assert re.findall(r"- dependency-name: (\S+)", web) == [
        "next", "eslint-config-next", "typescript"
    ]


def test_perf_auth_core_moves_with_next_auth_not_alone():
    rule = ignore(entry("npm", "/scripts/perf"), '"@auth/core"')
    assert "next-auth" in rule


# ─── AC-5: the CI check replaces the 0001 protected path ─────────────────────────────────────


def test_no_migration_is_a_protected_path_any_more():
    patterns = [p["pattern"] for p in json.loads(KIT.read_text(encoding="utf-8"))["protectedPaths"]]
    assert not [p for p in patterns if "migrations/versions" in p]
    # Every other entry is unchanged.
    assert patterns == [
        ".env", ".env.local", ".env.*.local", ".env.live", "design/*", "data/*", "data",
        "web/app/tokens.css", "pnpm-lock.yaml", "python/uv.lock", "*.pem", "*.key",
        "docs/tasks/INDEX.md",
    ]
