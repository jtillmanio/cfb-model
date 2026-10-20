"""Lake fixtures: a local lake in `tmp_path` with the CLI pointed at it, empty or holding
`fixtures/lake.json`."""

from __future__ import annotations

from pathlib import Path

import pytest
from lake_fixture import write_fixture

from engine import cli
from engine.ingest.lake import LocalLake


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
