"""The Vercel cleanup's decisions and client (D-126, db.deployments)."""

import argparse
from collections.abc import Collection

import pytest

from db import deployments
from db.__main__ import main
from db.deployments import Build, delete_build, fetch_builds, plan_cleanup, render_summary
from db.release import ApiRefused, ReleaseRefused

DAY = 24 * 60 * 60 * 1000
NOW = 100 * DAY
PROD = "dpl_prod"


def build(id: str, *, branch: str = "feat/x", age_days: float = 3, state: str = "READY",
          target: str | None = None) -> Build:
    return Build(id=id, url=f"{id}.vercel.app", branch=branch, created=int(NOW - age_days * DAY),
                 state=state, target=target)


def main_build(id: str, age_days: float, state: str = "READY") -> Build:
    return build(id, branch="main", age_days=age_days, state=state, target="production")


def plan(builds, *, production: Collection[str] = (PROD,), open_branches: Collection[str] = (),
         **kwargs):
    verdicts = plan_cleanup(builds, production=set(production), open_branches=set(open_branches),
                            now_ms=NOW, **kwargs)
    return {v.build.id: (v.delete, v.reason) for v in verdicts}


# ─── Sweep ───────────────────────────────────────────────────────────────────────────────────


def test_keeps_the_newest_five_ready_main_builds_and_deletes_the_rest():
    builds = [main_build(f"dpl_m{i}", age_days=i) for i in range(1, 9)]
    got = plan(builds)
    kept = [id for id, (delete, _) in got.items() if not delete]
    assert kept == ["dpl_m1", "dpl_m2", "dpl_m3", "dpl_m4", "dpl_m5"]
    assert got["dpl_m6"] == (True, "older than the newest 5 main builds")


def test_never_deletes_production_even_when_it_is_the_oldest_main_build():
    builds = [main_build(f"dpl_m{i}", age_days=i) for i in range(1, 8)] + [main_build(PROD, 30)]
    got = plan(builds)
    assert got[PROD] == (False, "serving production")
    # Production doesn't take one of the five places: the five newest stay too.
    assert [id for id, (delete, _) in got.items() if not delete][:5] == [
        "dpl_m1", "dpl_m2", "dpl_m3", "dpl_m4", "dpl_m5"
    ]


def test_failed_and_skipped_main_builds_are_deleted_and_do_not_count_toward_the_five():
    builds = [main_build("dpl_err", 1, state="ERROR"), main_build("dpl_skip", 2, state="CANCELED")]
    builds += [main_build(f"dpl_m{i}", age_days=2 + i) for i in range(1, 6)]
    got = plan(builds)
    assert got["dpl_err"] == (True, "main build error")
    assert got["dpl_skip"] == (True, "main build canceled")
    assert all(not got[f"dpl_m{i}"][0] for i in range(1, 6))


def test_never_deletes_a_build_still_in_progress():
    got = plan([main_build("dpl_b", 40, state="BUILDING"), build("dpl_q", state="QUEUED")])
    assert got == {"dpl_q": (False, "still queued"), "dpl_b": (False, "still building")}


def test_deletes_previews_with_no_open_pr_and_keeps_open_ones():
    got = plan([build("dpl_open", branch="feat/open"), build("dpl_closed", branch="fix/done")],
               open_branches={"feat/open"})
    assert got["dpl_open"] == (False, "its PR is open")
    assert got["dpl_closed"] == (True, "preview with no open PR")


def test_a_sweep_leaves_a_preview_under_a_day_old_its_pr_may_not_be_open_yet():
    got = plan([build("dpl_new", age_days=0.5), build("dpl_old", age_days=1.5)])
    assert got["dpl_new"] == (False, "under a day old")
    assert got["dpl_old"][0] is True


def test_keeps_deployments_not_built_from_git():
    assert plan([build("dpl_cli", branch="", age_days=50)]) == {
        "dpl_cli": (False, "not built from git")
    }


def test_a_main_preview_counts_as_a_main_build_not_a_preview():
    # A redeploy of main without the production target is still main's, never "no open PR".
    got = plan([build(f"dpl_m{i}", branch="main", age_days=i) for i in range(1, 7)])
    assert got["dpl_m1"] == (False, "one of the newest 5 main builds")
    assert got["dpl_m6"] == (True, "older than the newest 5 main builds")


# ─── One closed PR ───────────────────────────────────────────────────────────────────────────


def test_branch_mode_deletes_only_that_branchs_previews_however_new():
    builds = [
        build("dpl_mine", branch="feat/x", age_days=0.1),
        build("dpl_other", branch="feat/y", age_days=9),
        main_build("dpl_m9", 90),
    ]
    assert plan(builds, branch="feat/x") == {"dpl_mine": (True, "preview with no open PR")}


def test_branch_mode_keeps_a_branch_whose_pr_was_reopened():
    got = plan([build("dpl_mine", branch="feat/x")], branch="feat/x", open_branches={"feat/x"})
    assert got == {"dpl_mine": (False, "its PR is open")}


@pytest.mark.parametrize("branch", ["main", ""])
def test_branch_mode_refuses_main_and_an_empty_branch(branch):
    with pytest.raises(ReleaseRefused, match="--branch"):
        plan([main_build("dpl_m1", 1)], branch=branch)


# ─── Guards ──────────────────────────────────────────────────────────────────────────────────


def test_refuses_when_production_is_unknown():
    with pytest.raises(ReleaseRefused, match="serves production"):
        plan([main_build("dpl_m1", 1)], production=set())


def test_refuses_keeping_fewer_than_one_main_build():
    with pytest.raises(ReleaseRefused, match="at least 1"):
        plan([main_build("dpl_m1", 1)], keep_main=0)


# ─── Summary ─────────────────────────────────────────────────────────────────────────────────


def test_dry_run_summary_says_nothing_was_deleted_and_counts_by_reason():
    verdicts = plan_cleanup(
        [main_build(PROD, 9), build("dpl_a"), build("dpl_b")],
        production={PROD}, open_branches=set(), now_ms=NOW,
    )
    text = render_summary(verdicts, dry_run=True, failed=[])
    assert "dry run: nothing deleted" in text
    assert "| would delete | preview with no open PR | 2 |" in text
    assert "| kept | serving production | 1 |" in text


def test_summary_names_failed_deletes_and_leaves_them_out_of_the_list():
    verdicts = plan_cleanup([build("dpl_a"), build("dpl_b")], production={PROD},
                            open_branches=set(), now_ms=NOW)
    text = render_summary(verdicts, dry_run=False, failed=["dpl_b"])
    assert "**Failed to delete 1:** dpl_b" in text
    assert "- `dpl_a`" in text and "- `dpl_b`" not in text


# ─── Client ──────────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def vercel_env(monkeypatch):
    monkeypatch.setenv("VERCEL_TOKEN", "t")
    monkeypatch.setenv("VERCEL_PROJECT_ID", "prj_1")
    monkeypatch.setenv("VERCEL_ORG_ID", "team_1")


def test_fetch_builds_follows_pagination(monkeypatch, vercel_env):
    pages = {
        None: {"deployments": [{"uid": "dpl_1", "created": 3, "meta": {"githubCommitRef": "a"}}],
               "pagination": {"next": 2}},
        2: {"deployments": [{"uid": "dpl_2", "created": 1, "readyState": "READY",
                             "target": "production"}], "pagination": {"next": None}},
    }
    seen = []

    def fake_call(method, url, token, *, params=None, body=None):
        assert params is not None
        seen.append(params)
        return pages[params.get("until")]

    monkeypatch.setattr(deployments, "_call", fake_call)
    builds = fetch_builds()
    assert [b.id for b in builds] == ["dpl_1", "dpl_2"]
    assert builds[0].branch == "a" and builds[1].target == "production"
    assert all(p["teamId"] == "team_1" and p["projectId"] == "prj_1" for p in seen)


def test_delete_treats_404_as_gone_and_retries_a_rate_limit(monkeypatch, vercel_env):
    answers = [ApiRefused("slow down", 429), None]

    def fake_call(method, url, token, *, params=None, body=None):
        assert method == "DELETE" and url.endswith("/v13/deployments/dpl_1")
        answer = answers.pop(0)
        if answer:
            raise answer

    monkeypatch.setattr(deployments, "_call", fake_call)
    delete_build("dpl_1", wait=0)
    assert answers == []

    def gone(*args, **kwargs):
        raise ApiRefused("not found", 404)

    monkeypatch.setattr(deployments, "_call", gone)
    delete_build("dpl_1", wait=0)


def test_delete_raises_other_errors(monkeypatch, vercel_env):
    def forbidden(*args, **kwargs):
        raise ApiRefused("forbidden", 403)

    monkeypatch.setattr(deployments, "_call", forbidden)
    with pytest.raises(ApiRefused):
        delete_build("dpl_1", wait=0)


def test_a_dry_run_deletes_nothing(monkeypatch, capsys):
    monkeypatch.setattr(deployments, "fetch_builds", lambda: [build("dpl_a")])
    monkeypatch.setattr(deployments, "fetch_production", lambda url: {PROD})
    monkeypatch.setattr(deployments, "fetch_open_branches", lambda: set())
    monkeypatch.setattr(deployments, "delete_build", lambda id: pytest.fail("deleted in a dry run"))
    monkeypatch.setenv("PRODUCTION_URL", "https://cfb.example.com")
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    main(["vercel-cleanup", "--dry-run"])
    assert "| would delete | preview with no open PR | 1 |" in capsys.readouterr().out


def test_a_failed_delete_fails_the_run_after_trying_the_rest(monkeypatch):
    tried = []

    def delete(id):
        tried.append(id)
        if id == "dpl_a":
            raise ApiRefused("forbidden", 403)

    monkeypatch.setattr(deployments, "fetch_builds", lambda: [build("dpl_a"), build("dpl_b")])
    monkeypatch.setattr(deployments, "fetch_production", lambda url: {PROD})
    monkeypatch.setattr(deployments, "fetch_open_branches", lambda: set())
    monkeypatch.setattr(deployments, "delete_build", delete)
    monkeypatch.setenv("PRODUCTION_URL", "https://cfb.example.com")
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    with pytest.raises(SystemExit, match="1 deployment"):
        deployments.cleanup(argparse.Namespace(
            branch=None, keep_main=5, dry_run=False, pause=0
        ))
    assert sorted(tried) == ["dpl_a", "dpl_b"]
