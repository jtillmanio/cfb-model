"""The late-fallback guard for results.yml and lines.yml (TASK-028, D-129): a `schedule` run skips
when a dispatched run succeeded at or after 3 hours before the cron's own slot, however late the
run started. No network: `gh` is faked."""

from __future__ import annotations

import json
import re
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from db.config import repo_root
from engine import fallback

RESULTS = "0 12 * * 0,1"
LINES_DAILY = "0 14 * * *"
LINES_EVENING = "0 1 * * 5,6"


def utc(text: str) -> datetime:
    return datetime.fromisoformat(text).replace(tzinfo=UTC)


# slot


def test_slot_is_the_latest_firing_at_or_before_now() -> None:
    sunday = utc("2026-10-25T20:00:00")  # a Sunday, 8 hours after the 12:00 slot
    assert fallback.slot(RESULTS, sunday) == utc("2026-10-25T12:00:00")
    assert fallback.slot(RESULTS, utc("2026-10-25T12:00:00")) == utc("2026-10-25T12:00:00")
    assert fallback.slot(RESULTS, utc("2026-10-25T11:59:00")) == utc("2026-10-19T12:00:00")
    assert fallback.slot(RESULTS, utc("2026-10-28T09:00:00")) == utc("2026-10-26T12:00:00")  # Wed


def test_slot_honors_the_weekday_list() -> None:
    friday_morning = utc("2026-10-23T09:00:00")  # 8 hours after Friday 01:00
    assert fallback.slot(LINES_EVENING, friday_morning) == utc("2026-10-23T01:00:00")
    assert fallback.slot(LINES_EVENING, utc("2026-10-27T00:00:00")) == utc("2026-10-24T01:00:00")


def test_slot_of_a_start_over_a_day_late_is_a_later_slot() -> None:
    assert fallback.slot(LINES_DAILY, utc("2026-10-24T15:00:00")) == utc("2026-10-24T14:00:00")


def test_slot_rejects_a_cron_it_does_not_read() -> None:
    with pytest.raises(ValueError, match="cron"):
        fallback.slot("*/5 * * * *", utc("2026-10-25T12:00:00"))


# AC-1: a late fallback after a dispatched success


def test_ac1_results_fallback_8_hours_late_skips() -> None:
    now = utc("2026-10-25T20:00:00")
    d = fallback.decide("schedule", RESULTS, now, [utc("2026-10-25T10:00:00")])
    assert d.skip is True
    assert "skipped" in d.summary.lower()
    assert "2026-10-25T10:00:00" in d.summary


def test_ac1_lines_evening_fallback_8_hours_late_skips() -> None:
    now = utc("2026-10-23T09:00:00")  # Friday 01:00 slot, started 8 hours late
    d = fallback.decide("schedule", LINES_EVENING, now, [utc("2026-10-22T23:00:00")])
    assert d.skip is True


def test_ac1_lines_daily_fallback_8_hours_late_skips() -> None:
    d = fallback.decide(
        "schedule", LINES_DAILY, utc("2026-10-24T22:00:00"), [utc("2026-10-24T12:00:00")]
    )
    assert d.skip is True


# AC-2: no dispatched success in the window runs as before


def test_ac2_no_dispatched_run_runs() -> None:
    d = fallback.decide("schedule", RESULTS, utc("2026-10-25T13:00:00"), [])
    assert d.skip is False
    assert "fallback" in d.summary.lower()


def test_ac2_success_just_before_the_window_runs() -> None:
    slot_minus_3h = utc("2026-10-25T09:00:00")
    just_before = slot_minus_3h - timedelta(minutes=1)
    now = utc("2026-10-25T13:00:00")
    assert fallback.decide("schedule", RESULTS, now, [just_before]).skip is False
    assert fallback.decide("schedule", RESULTS, now, [slot_minus_3h]).skip is True


def test_ac2_thursday_morning_run_does_not_cover_the_evening_fallback() -> None:
    thursday_morning = utc("2026-10-22T12:00:00")  # the 08:00 ET dispatch
    d = fallback.decide("schedule", LINES_EVENING, utc("2026-10-23T09:00:00"), [thursday_morning])
    assert d.skip is False


def test_ac2_a_dispatched_event_always_runs() -> None:
    now = utc("2026-10-25T13:00:00")
    assert fallback.decide("workflow_dispatch", None, now, [now]).skip is False
    assert fallback.decide("schedule", None, now, [now]).skip is False  # no cron: doubt means run


def test_a_dispatch_with_a_fallback_cron_takes_the_fallback_path() -> None:
    now = utc("2026-10-25T13:00:00")
    assert fallback.decide("workflow_dispatch", RESULTS, now, [utc("2026-10-25T10:00:00")]).skip


# main: gh, GITHUB_OUTPUT and the summary


def fake_gh(created: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess([], 0, json.dumps([{"createdAt": c} for c in created]), "")


def test_main_writes_skip_and_summary(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    out, summary = tmp_path / "out", tmp_path / "summary"
    monkeypatch.setenv("GITHUB_OUTPUT", str(out))
    called: list[list[str]] = []

    def run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
        called.append(cmd)
        return fake_gh(["2026-10-25T10:00:00Z"])

    code = fallback.main(
        [
            "--event",
            "schedule",
            "--schedule",
            RESULTS,
            "--workflow",
            "results.yml",
            "--summary",
            str(summary),
        ],
        now=utc("2026-10-25T20:00:00"),
        run=run,
    )
    assert code == 0
    assert out.read_text() == "skip=true\n"
    assert "results.yml" in summary.read_text()
    assert called and "workflow_dispatch" in called[0] and "results.yml" in called[0]


def test_main_does_not_call_gh_for_a_dispatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = tmp_path / "out"
    monkeypatch.setenv("GITHUB_OUTPUT", str(out))

    def run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
        raise AssertionError("gh called")

    fallback.main(
        ["--event", "workflow_dispatch", "--schedule", "", "--workflow", "results.yml"],
        now=utc("2026-10-25T20:00:00"),
        run=run,
    )
    assert out.read_text() == "skip=false\n"


def test_main_fails_when_gh_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_OUTPUT", str(tmp_path / "out"))
    bad = subprocess.CompletedProcess([], 1, "", "no auth")
    with pytest.raises(SystemExit) as e:
        fallback.main(
            ["--event", "schedule", "--schedule", RESULTS, "--workflow", "results.yml"],
            now=utc("2026-10-25T20:00:00"),
            run=lambda cmd: bad,
        )
    assert e.value.code == 1


# the files that wire it


def test_action_runs_the_engine_not_a_six_hour_window() -> None:
    action = (repo_root() / ".github/actions/skip-if-dispatched/action.yml").read_text("utf-8")
    assert "engine fallback" in action
    assert "6 hours ago" not in action


@pytest.mark.parametrize("name", ["results.yml", "lines.yml"])
def test_workflows_set_up_uv_before_the_guard_and_take_a_test_cron(name: str) -> None:
    text = (repo_root() / ".github/workflows" / name).read_text("utf-8")
    assert text.index("astral-sh/setup-uv") < text.index(
        "uses: ./.github/actions/skip-if-dispatched"
    )
    assert re.search(r"^\s+fallback_cron:\n", text, re.M)


@pytest.mark.parametrize("name", ["results.yml", "lines.yml"])
def test_the_job_step_is_gated_on_the_guard_output(name: str) -> None:
    text = (repo_root() / ".github/workflows" / name).read_text("utf-8")
    assert "id: guard" in text
    steps = text.split("      - name: ")[2:]  # after the guard step
    job = [s for s in steps if "engine job" in s]
    assert len(job) == 1
    assert "if: ${{ steps.guard.outputs.skip != 'true' }}" in job[0]


def test_the_engine_cli_forwards_to_the_guard(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from engine import cli

    out = tmp_path / "out"
    monkeypatch.setenv("GITHUB_OUTPUT", str(out))
    with pytest.raises(SystemExit) as e:
        cli.main(["fallback", "--event", "workflow_dispatch", "--workflow", "results.yml"])
    assert e.value.code == 0
    assert out.read_text() == "skip=false\n"
