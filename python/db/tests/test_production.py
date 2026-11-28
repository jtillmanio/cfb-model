"""`python -m db production-commit` (TASK-076): the commit production serves, which the job
workflows check out and run, and whose views the backup re-applies."""

from __future__ import annotations

import json
import socket
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

from db import production
from db.__main__ import main

SHA = "0123456789abcdef0123456789abcdef01234567"


class Production:
    """A local stand-in for production's `/api/py/health`: each request takes the next answer
    (status, body); the last one repeats. It records the bypass header it was sent."""

    def __init__(self, *answers: tuple[int, bytes], truncate: bool = False) -> None:
        self.answers = list(answers)
        self.requests: list[tuple[str, str | None]] = []
        self.truncate = truncate  # promise more bytes than are sent, then hang up

    def next(self) -> tuple[int, bytes]:
        return self.answers.pop(0) if len(self.answers) > 1 else self.answers[0]


def serve(fake: Production) -> Iterator[str]:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            fake.requests.append((self.path, self.headers.get("x-vercel-protection-bypass")))
            status, body = fake.next()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            if fake.truncate:
                self.send_header("Content-Length", str(len(body) + 100))
                self.close_connection = True
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: object) -> None:  # noqa: A002
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/"
    finally:
        server.shutdown()
        server.server_close()


@pytest.fixture
def gha(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    """The step's `$GITHUB_OUTPUT` and `$GITHUB_STEP_SUMMARY`, and no real waiting."""
    output, summary = tmp_path / "output", tmp_path / "summary"
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    monkeypatch.setenv("VERCEL_AUTOMATION_BYPASS_SECRET", "bypass-123")
    monkeypatch.delenv("PRODUCTION_URL", raising=False)
    monkeypatch.setattr(production, "_sleep", lambda _seconds: None)
    return output, summary


def run(*args: str) -> int:
    try:
        main(["production-commit", *args])
    except SystemExit as e:
        return int(e.code or 0)
    return 0


def read(path: Path) -> str:
    return path.read_text("utf-8") if path.exists() else ""


def health(commit: object) -> bytes:
    return json.dumps({"commit": commit, "db_reachable": True, "migration_head": "0009"}).encode()


# AC-1: a full SHA is the commit to run


def test_a_full_sha_is_written_with_the_ref_to_check_out(gha: tuple[Path, Path]) -> None:
    output, summary = gha
    fake = Production((200, health(SHA)))
    for url in serve(fake):
        assert run("--url", url) == 0
    assert read(output).splitlines() == [f"commit={SHA}", f"ref={SHA}"]
    assert f"Running production's commit `{SHA}`" in read(summary)
    assert fake.requests == [("/api/py/health", "bypass-123")]


def test_the_url_comes_from_production_url(
    gha: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    output, _ = gha
    for url in serve(Production((200, health(SHA)))):
        monkeypatch.setenv("PRODUCTION_URL", url.rstrip("/"))
        assert run() == 0
    assert f"commit={SHA}" in read(output)


def test_a_code_ref_is_checked_out_instead_and_the_summary_says_so(
    gha: tuple[Path, Path],
) -> None:
    output, summary = gha
    for url in serve(Production((200, health(SHA)))):
        assert run("--url", url, "--code-ref", "fix/077-cfbd-retry") == 0
    assert read(output).splitlines() == [f"commit={SHA}", "ref=fix/077-cfbd-retry"]
    text = read(summary)
    assert f"Running `fix/077-cfbd-retry`, not production's commit `{SHA}`" in text
    assert "Running production's commit" not in text


def test_the_backup_says_whose_views_it_uses(gha: tuple[Path, Path]) -> None:
    _, summary = gha
    for url in serve(Production((200, health(SHA)))):
        assert run("--url", url, "--uses", "views") == 0
    assert f"Re-applying the views of production's commit `{SHA}`" in read(summary)


def test_a_failed_answer_is_retried(gha: tuple[Path, Path]) -> None:
    output, _ = gha
    fake = Production((503, b"busy"), (200, health(SHA)))
    for url in serve(fake):
        assert run("--url", url) == 0
    assert len(fake.requests) == 2
    assert f"commit={SHA}" in read(output)


# AC-2: no full SHA means the run stops, naming the URL and what came back


@pytest.mark.parametrize(
    ("answer", "shown"),
    [
        ((500, b"oops"), "HTTP 500"),
        ((200, health("unknown")), "'unknown'"),
        ((200, health(None)), "no commit"),
        ((200, health("0123abc")), "'0123abc'"),
        ((200, b"<html>Vercel login</html>"), "isn't JSON"),
    ],
)
def test_no_full_sha_fails_and_writes_no_output(
    gha: tuple[Path, Path], workflow: str, answer: tuple[int, bytes], shown: str
) -> None:
    output, summary = gha
    url = ""
    for url in serve(Production(answer)):
        assert run("--url", url, "--workflow", workflow) == 1
    assert read(output) == ""
    text = read(summary)
    assert f"**{workflow} failed:**" in text
    assert f"{url.rstrip('/')}/api/py/health" in text
    assert shown in text


@pytest.fixture(params=["Lines", "Backup"])
def workflow(request: pytest.FixtureRequest) -> str:
    return str(request.param)


def test_an_unreachable_production_fails_after_every_attempt(
    gha: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    output, summary = gha
    with socket.socket() as s:  # a port nothing listens on
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    calls: list[float] = []
    monkeypatch.setattr(production, "_sleep", calls.append)
    assert run("--url", f"http://127.0.0.1:{port}", "--workflow", "Results") == 1
    assert len(calls) == production.ATTEMPTS - 1
    assert read(output) == ""
    text = read(summary)
    assert "**Results failed:**" in text
    assert f"http://127.0.0.1:{port}/api/py/health" in text
    assert f"after {production.ATTEMPTS} attempts" in text


def test_an_answer_cut_short_fails_with_the_summary_line(gha: tuple[Path, Path]) -> None:
    output, summary = gha
    fake = Production((200, health(SHA)), truncate=True)
    url = ""
    for url in serve(fake):
        assert run("--url", url, "--workflow", "Scores") == 1
    assert len(fake.requests) == production.ATTEMPTS  # a broken answer is tried again
    assert read(output) == ""
    text = read(summary)
    assert "**Scores failed:**" in text
    assert f"{url.rstrip('/')}/api/py/health" in text
    assert "IncompleteRead" in text


def test_an_unset_production_url_fails(gha: tuple[Path, Path]) -> None:
    output, summary = gha
    assert run("--workflow", "Lines") == 1
    assert read(output) == ""
    assert "PRODUCTION_URL is unset" in read(summary)
