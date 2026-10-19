"""The lake: `raw/`, every API response saved exactly as fetched and append-only (D-027, D-112),
and `staging/`, derived from raw and overwritten by `engine transform --rebuild` (D-116).

`LAKE_URI` picks where it lives: unset or a path is a local folder (default ./data at the repo
root); `s3://<bucket>[/<prefix>]` is the Cloudflare R2 bucket, through R2's S3 API. Keys are
POSIX paths relative to the lake root, e.g. `raw/cfbd/games/season=2025/week=01/…`.

A raw file is one Parquet file per pull with one row per top-level record: `row` (its position),
`record` (the record as JSON text), `params` (the query sent, as JSON text) and `fetched_at`
(UTC). pyarrow and boto3 are the engine's `train` extra (D-004), so they're imported only where
they're used.
"""

from __future__ import annotations

import io
import json
import os
import posixpath
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from db.config import repo_root

LEDGER_KEY = "cfbd_calls.json"
_FETCHED_AT = "%Y-%m-%dT%H%M%SZ"


class Lake(Protocol):
    def write_new(self, key: str, data: bytes) -> None:
        """Write a file that must not exist yet. Raises FileExistsError if it does."""
        ...

    def read(self, key: str) -> bytes: ...

    def list(self, folder: str) -> list[str]:
        """Keys of the files directly inside `folder`, sorted."""
        ...

    def read_text(self, key: str) -> str | None: ...

    def write_text(self, key: str, text: str) -> None:
        """Overwrite a small text object. Only the call ledger uses it."""
        ...

    def walk(self, prefix: str) -> list[str]:
        """Keys of every file below `prefix`, at any depth, sorted."""
        ...

    def replace(self, key: str, data: bytes) -> None:
        """Overwrite a derived file in one step. Refuses `raw/` keys."""
        ...


def _never_overwritten(key: str) -> FileExistsError:
    return FileExistsError(f"Raw files are never overwritten: {key}")


def _refuse_raw(key: str) -> None:
    """Refuse a key that resolves to raw (`./raw/…`, `staging/../raw/…`), climbs out of the
    lake, or holds a backslash (Windows would read it as a separator)."""
    normal = posixpath.normpath(key.replace("\\", "/")).lstrip("/")
    if "\\" in key or normal == "raw" or normal.startswith(("raw/", "../")):
        raise _never_overwritten(key)


class LocalLake:
    def __init__(self, root: Path) -> None:
        self.root = root

    def _temp(self, path: Path, data: bytes) -> Path:
        """Write beside the target first, so a crash never leaves a torn file under its name."""
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
        temp.write_bytes(data)
        return temp

    def write_new(self, key: str, data: bytes) -> None:
        path = self.root / key
        if path.exists():
            raise _never_overwritten(key)
        temp = self._temp(path, data)
        try:
            os.link(temp, path)  # fails if the file exists: never overwrites
        except FileExistsError:
            raise _never_overwritten(key) from None
        finally:
            temp.unlink()

    def read(self, key: str) -> bytes:
        return (self.root / key).read_bytes()

    def list(self, folder: str) -> list[str]:
        path = self.root / folder
        if not path.is_dir():
            return []
        return sorted(f"{folder}/{p.name}" for p in path.iterdir() if p.is_file())

    def read_text(self, key: str) -> str | None:
        path = self.root / key
        return path.read_text(encoding="utf-8") if path.is_file() else None

    def write_text(self, key: str, text: str) -> None:
        path = self.root / key
        os.replace(self._temp(path, text.encode("utf-8")), path)

    def walk(self, prefix: str) -> list[str]:
        path = self.root / prefix
        if not path.is_dir():
            return []
        return sorted(
            p.relative_to(self.root).as_posix()
            for p in path.rglob("*")
            if p.is_file() and not p.name.startswith(".")  # skip a crashed write's temp file
        )

    def replace(self, key: str, data: bytes) -> None:
        _refuse_raw(key)
        path = self.root / key
        os.replace(self._temp(path, data), path)


class S3Lake:
    """An R2 bucket. A raw key is checked with HEAD before the PUT; there's one writer at a time
    (the scheduled jobs share a concurrency group), and R2's conditional PUT is unverified."""

    def __init__(self, client: Any, bucket: str, prefix: str = "") -> None:
        self.client = client
        self.bucket = bucket
        self.prefix = prefix.strip("/")

    def _key(self, key: str) -> str:
        return f"{self.prefix}/{key}" if self.prefix else key

    def _exists(self, key: str) -> bool:
        from botocore.exceptions import ClientError

        try:
            self.client.head_object(Bucket=self.bucket, Key=self._key(key))
        except ClientError as e:
            if e.response.get("Error", {}).get("Code") in ("404", "NoSuchKey", "NotFound"):
                return False
            raise
        return True

    def write_new(self, key: str, data: bytes) -> None:
        if self._exists(key):
            raise _never_overwritten(key)
        self.client.put_object(Bucket=self.bucket, Key=self._key(key), Body=data)

    def read(self, key: str) -> bytes:
        return self.client.get_object(Bucket=self.bucket, Key=self._key(key))["Body"].read()

    def list(self, folder: str) -> list[str]:
        keys: list[str] = []
        pages = self.client.get_paginator("list_objects_v2").paginate(
            Bucket=self.bucket, Prefix=f"{self._key(folder)}/", Delimiter="/"
        )
        for page in pages:
            keys += [obj["Key"] for obj in page.get("Contents", [])]
        strip = len(self.prefix) + 1 if self.prefix else 0
        return sorted(k[strip:] for k in keys)

    def read_text(self, key: str) -> str | None:
        return self.read(key).decode("utf-8") if self._exists(key) else None

    def write_text(self, key: str, text: str) -> None:
        self.client.put_object(Bucket=self.bucket, Key=self._key(key), Body=text.encode("utf-8"))

    def walk(self, prefix: str) -> list[str]:
        keys: list[str] = []
        pages = self.client.get_paginator("list_objects_v2").paginate(
            Bucket=self.bucket, Prefix=f"{self._key(prefix)}/"
        )
        for page in pages:
            keys += [obj["Key"] for obj in page.get("Contents", [])]
        strip = len(self.prefix) + 1 if self.prefix else 0
        return sorted(k[strip:] for k in keys)

    def replace(self, key: str, data: bytes) -> None:
        _refuse_raw(key)  # an object PUT replaces the whole object, so it's one step
        self.client.put_object(Bucket=self.bucket, Key=self._key(key), Body=data)


def _required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is not set; an s3:// LAKE_URI needs it.")
    return value


def r2_client() -> Any:
    import boto3
    from botocore.config import Config

    account = _required_env("R2_ACCOUNT_ID")
    return boto3.client(
        "s3",
        endpoint_url=f"https://{account}.r2.cloudflarestorage.com",
        region_name="auto",
        aws_access_key_id=_required_env("R2_DATA_LAKE_ACCESS_KEY_ID"),
        aws_secret_access_key=_required_env("R2_DATA_LAKE_SECRET_ACCESS_KEY"),
        # R2 rejects the SDK's default checksum headers (as in backup.yml).
        config=Config(
            request_checksum_calculation="when_required",
            response_checksum_validation="when_required",
        ),
    )


def open_lake() -> Lake:
    uri = os.environ.get("LAKE_URI", "").strip()
    if uri.startswith("s3://"):
        bucket, _, prefix = uri.removeprefix("s3://").partition("/")
        return S3Lake(r2_client(), bucket, prefix)
    return LocalLake(Path(uri) if uri else repo_root() / "data")


def raw_folder(
    endpoint: str, season: int, week: int | None = None, season_type: str = "regular"
) -> str:
    """`raw/cfbd/<endpoint>/season=Y[/season_type=postseason][/week=NN]`. The regular season
    adds no level, so a postseason week 1 never shares a folder with regular week 1."""
    folder = f"raw/cfbd/{endpoint}/season={season}"
    if season_type != "regular":
        folder += f"/season_type={season_type}"
    if week is not None:
        folder += f"/week={week:02d}"
    return folder


def raw_key(folder: str, fetched_at: datetime) -> str:
    return f"{folder}/fetched_at={fetched_at.astimezone(UTC).strftime(_FETCHED_AT)}.parquet"


def fetched_at_of(key: str) -> datetime:
    stamp = key.rsplit("fetched_at=", 1)[1].removesuffix(".parquet")
    return datetime.strptime(stamp, _FETCHED_AT).replace(tzinfo=UTC)


def latest_raw(lake: Lake, folder: str) -> str | None:
    """The newest Parquet raw file in `folder` (the timestamp format sorts as text)."""
    files = [k for k in lake.list(folder) if k.endswith(".parquet") and "fetched_at=" in k]
    return files[-1] if files else None


def encode_raw(payload: Any, params: dict[str, Any], fetched_at: datetime) -> bytes:
    import pyarrow as pa
    import pyarrow.parquet as pq

    records = payload if isinstance(payload, list) else [payload]
    n = len(records)
    table = pa.table(
        {
            "row": pa.array(range(n), pa.int32()),
            "record": pa.array([json.dumps(r, ensure_ascii=False) for r in records], pa.string()),
            "params": pa.array([json.dumps(params, sort_keys=True)] * n, pa.string()),
            "fetched_at": pa.array([fetched_at.astimezone(UTC)] * n, pa.timestamp("us", "UTC")),
        }
    )
    buffer = io.BytesIO()
    pq.write_table(table, buffer)
    return buffer.getvalue()


def decode_raw(data: bytes) -> list[Any]:
    """The response's records in order. A non-list response comes back as a one-item list."""
    import pyarrow.parquet as pq

    table = pq.read_table(io.BytesIO(data), columns=["row", "record"]).sort_by("row")
    return [json.loads(text) for text in table.column("record").to_pylist()]
