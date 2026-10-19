"""The raw lake: Parquet round trips, never overwriting, and R2 through its S3 API (D-112).

No test opens a socket: CFBD is an httpx.MockTransport and R2 is moto's in-process S3, which
intercepts the R2 endpoint through MOTO_S3_CUSTOM_ENDPOINTS.
"""

import json
import re
from pathlib import Path

import httpx
import pyarrow.parquet as pq
import pytest
from moto import mock_aws

from engine.ingest.cfbd import CallBudget, CfbdClient
from engine.ingest.endpoints import pull
from engine.ingest.lake import LocalLake, S3Lake, decode_raw, open_lake

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def fixed_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("FIXTURE_NOW", "2025-09-02T12:00:00Z")


@pytest.mark.parametrize(
    ("endpoint", "fixture"),
    [("games", "cfbd_games_sample.json"), ("lines", "cfbd_lines_sample.json")],
)
def test_raw_round_trip(endpoint: str, fixture: str, tmp_path: Path) -> None:
    response = json.loads((FIXTURES / fixture).read_text(encoding="utf-8"))
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=response)

    lake = LocalLake(tmp_path)
    http = httpx.Client(base_url="https://cfbd.test", transport=httpx.MockTransport(handler))
    pull(lake, endpoint, 2025, week=1, client=CfbdClient("key", CallBudget(lake), http))

    files = [p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob("*.parquet")]
    assert len(files) == 1
    assert re.fullmatch(
        rf"raw/cfbd/{endpoint}/season=2025/week=01/fetched_at=2025-09-02T120000Z\.parquet",
        files[0],
    )
    table = pq.read_table(tmp_path / files[0])
    assert table.column_names == ["row", "record", "params", "fetched_at"]
    assert decode_raw((tmp_path / files[0]).read_bytes()) == response
    assert len(requests) == 1
    assert requests[0].url.params["year"] == "2025"
    assert requests[0].url.params["week"] == "1"
    assert requests[0].url.params["seasonType"] == "regular"


def test_an_empty_response_is_a_zero_row_file(tmp_path: Path) -> None:
    lake = LocalLake(tmp_path)
    http = httpx.Client(
        base_url="https://cfbd.test",
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=[])),
    )
    key = pull(lake, "lines", 2025, week=1, client=CfbdClient("key", CallBudget(lake), http))
    assert pq.read_table(tmp_path / key).num_rows == 0
    assert decode_raw(lake.read(key)) == []


def test_writing_an_existing_key_raises_and_keeps_the_file(tmp_path: Path) -> None:
    lake = LocalLake(tmp_path)
    key = "raw/cfbd/games/season=2025/week=01/fetched_at=2025-09-02T120000Z.parquet"
    lake.write_new(key, b"first")
    with pytest.raises(FileExistsError, match="never overwritten"):
        lake.write_new(key, b"second")
    assert (tmp_path / key).read_bytes() == b"first"


def test_s3_lake_round_trip_and_refuses_overwrite(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LAKE_URI", "s3://cfb-lake-test")
    monkeypatch.setenv("R2_ACCOUNT_ID", "acct")
    monkeypatch.setenv("R2_DATA_LAKE_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("R2_DATA_LAKE_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("MOTO_S3_CUSTOM_ENDPOINTS", "https://acct.r2.cloudflarestorage.com")
    with mock_aws():
        lake = open_lake()
        assert isinstance(lake, S3Lake)
        assert lake.client.meta.endpoint_url == "https://acct.r2.cloudflarestorage.com"
        lake.client.create_bucket(
            Bucket="cfb-lake-test", CreateBucketConfiguration={"LocationConstraint": "auto"}
        )

        key = "raw/cfbd/calendar/season=2025/fetched_at=2025-09-02T120000Z.parquet"
        lake.write_new(key, b"first")
        assert lake.read(key) == b"first"
        assert lake.list("raw/cfbd/calendar/season=2025") == [key]
        with pytest.raises(FileExistsError, match="never overwritten"):
            lake.write_new(key, b"second")
        assert lake.read(key) == b"first"

        # The call ledger lives in the bucket too (D-112): the one object that is overwritten.
        assert lake.read_text("cfbd_calls.json") is None
        lake.write_text("cfbd_calls.json", '{"2025-09": 1}')
        lake.write_text("cfbd_calls.json", '{"2025-09": 2}')
        assert lake.read_text("cfbd_calls.json") == '{"2025-09": 2}'


def _walk_and_replace(lake: LocalLake | S3Lake) -> None:
    lake.write_new("raw/cfbd/games/season=2025/week=01/fetched_at=2025-09-02T120000Z.parquet", b"r")
    lake.write_new("raw/cfbd/games/season=2025/fetched_at=2025-09-02T120000Z.parquet", b"r")
    lake.write_new("raw/cfbd/gamesx/season=2025/fetched_at=2025-09-02T120000Z.parquet", b"r")
    assert lake.walk("raw/cfbd/games") == [
        "raw/cfbd/games/season=2025/fetched_at=2025-09-02T120000Z.parquet",
        "raw/cfbd/games/season=2025/week=01/fetched_at=2025-09-02T120000Z.parquet",
    ]
    assert lake.walk("staging") == []

    # Staging is derived (D-116): replace overwrites it, but never a raw file.
    lake.replace("staging/games.parquet", b"first")
    lake.replace("staging/games.parquet", b"second")
    assert lake.read("staging/games.parquet") == b"second"
    assert lake.walk("staging") == ["staging/games.parquet"]
    raw = "raw/cfbd/games/season=2025/fetched_at=2025-09-02T120000Z.parquet"
    with pytest.raises(FileExistsError, match="never overwritten"):
        lake.replace(raw, b"changed")
    assert lake.read(raw) == b"r"


def test_local_lake_walk_and_replace(tmp_path: Path) -> None:
    _walk_and_replace(LocalLake(tmp_path))


def test_s3_lake_walk_and_replace(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MOTO_S3_CUSTOM_ENDPOINTS", "https://acct.r2.cloudflarestorage.com")
    with mock_aws():
        import boto3

        client = boto3.client(
            "s3",
            endpoint_url="https://acct.r2.cloudflarestorage.com",
            region_name="auto",
            aws_access_key_id="testing",
            aws_secret_access_key="testing",
        )
        client.create_bucket(
            Bucket="cfb-lake-test", CreateBucketConfiguration={"LocationConstraint": "auto"}
        )
        _walk_and_replace(S3Lake(client, "cfb-lake-test", "dev"))
