"""Lake fixtures: a local lake in `tmp_path` with the CLI pointed at it, empty or holding
`fixtures/lake.json`. No test downloads nflverse's file: a pull without its own client gets the
recorded slice in `fixtures/nflverse/games.csv` (TASK-069)."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest
from lake_fixture import write_fixture

from engine import cli
from engine.ingest import nflverse
from engine.ingest.lake import LocalLake

NFLVERSE_CSV = Path(__file__).parent / "fixtures" / "nflverse" / "games.csv"


@pytest.fixture(autouse=True)
def recorded_nflverse(monkeypatch: pytest.MonkeyPatch) -> None:
    text = NFLVERSE_CSV.read_text("utf-8")
    transport = httpx.MockTransport(lambda _request: httpx.Response(200, text=text))
    monkeypatch.setattr(nflverse, "_client", lambda: httpx.Client(transport=transport))


@pytest.fixture
def empty_lake(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> LocalLake:
    monkeypatch.setenv("LAKE_URI", str(tmp_path))
    monkeypatch.delenv("LIVE", raising=False)
    monkeypatch.setattr(cli, "load_env", lambda: None)
    return LocalLake(tmp_path)


@pytest.fixture
def lake(empty_lake: LocalLake) -> LocalLake:
    write_fixture(empty_lake)
    return empty_lake
