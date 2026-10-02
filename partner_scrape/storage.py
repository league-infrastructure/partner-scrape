"""Keyed byte storage over a local directory or an S3-compatible bucket.

Leaf module: it knows nothing about cache or data layout and never reads
config or the environment. `config.py` builds Stores and injects the boto3
client into `S3Store`.

Keys are `/`-separated relative strings (`"hosts/example.com.json"`). A
missing key reads as `None` rather than raising, so callers treat "absent"
as an ordinary cache miss.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import urlparse


class Store(Protocol):
    """Minimal keyed blob store."""

    def read_bytes(self, key: str) -> bytes | None: ...

    def write_bytes(
        self, key: str, data: bytes, content_type: str | None = None
    ) -> None: ...

    def read_text(self, key: str) -> str | None: ...

    def write_text(
        self, key: str, text: str, content_type: str | None = None
    ) -> None: ...

    def read_json(self, key: str) -> Any | None: ...

    def write_json(self, key: str, obj: Any) -> None: ...

    def exists(self, key: str) -> bool: ...

    def list(self, prefix: str = "") -> list[str]: ...


class _TextJsonMixin:
    """Text/JSON helpers shared by every backend, built on bytes I/O."""

    def read_text(self, key: str) -> str | None:
        data = self.read_bytes(key)  # type: ignore[attr-defined]
        return None if data is None else data.decode("utf-8")

    def write_text(
        self, key: str, text: str, content_type: str | None = None
    ) -> None:
        self.write_bytes(  # type: ignore[attr-defined]
            key, text.encode("utf-8"), content_type or "text/plain; charset=utf-8"
        )

    def read_json(self, key: str) -> Any | None:
        text = self.read_text(key)
        return None if text is None else json.loads(text)

    def write_json(self, key: str, obj: Any) -> None:
        self.write_text(
            key,
            json.dumps(obj, indent=2, ensure_ascii=False),
            "application/json",
        )

    def exists(self, key: str) -> bool:
        return self.read_bytes(key) is not None  # type: ignore[attr-defined]


class LocalStore(_TextJsonMixin):
    """Store rooted at a local directory; writes are atomic."""

    def __init__(self, root: Path):
        self.root = Path(root)

    def _path(self, key: str) -> Path:
        return self.root / key

    def read_bytes(self, key: str) -> bytes | None:
        try:
            return self._path(key).read_bytes()
        except (FileNotFoundError, NotADirectoryError, IsADirectoryError):
            return None

    def write_bytes(
        self, key: str, data: bytes, content_type: str | None = None
    ) -> None:
        """Write `data` so a crash mid-write can never leave a half-written
        file: the content lands in a sibling temp file first, fsynced, and
        is then atomically swapped over the target via `os.replace` (atomic
        on POSIX and Windows within one filesystem). Raises `RuntimeError`
        on any `OSError` -- loud failure for an unwritable target rather
        than silently skipping the write. `content_type` is ignored.
        """
        path = self._path(key)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp_name = tempfile.mkstemp(
                dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp"
            )
            try:
                with os.fdopen(fd, "wb") as f:
                    f.write(data)
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(tmp_name, path)
            except BaseException:
                if os.path.exists(tmp_name):
                    os.remove(tmp_name)
                raise
        except OSError as exc:
            raise RuntimeError(
                f"Cannot write partner log / storage entry to {path}: {exc}. "
                f"Check that its parent directory is writable."
            ) from exc

    def list(self, prefix: str = "") -> list[str]:
        """Sorted keys under `prefix` (a string prefix, as in S3)."""
        if not self.root.is_dir():
            return []
        keys = [
            p.relative_to(self.root).as_posix()
            for p in self.root.rglob("*")
            if p.is_file() and not p.name.endswith(".tmp")
        ]
        return sorted(k for k in keys if k.startswith(prefix))


class S3Store(_TextJsonMixin):
    """Store over an S3-compatible bucket, with every key under `prefix`."""

    def __init__(self, bucket: str, prefix: str, client: Any):
        self.bucket = bucket
        self.prefix = prefix.strip("/")
        self.client = client

    def _key(self, key: str) -> str:
        return f"{self.prefix}/{key}" if self.prefix else key

    def read_bytes(self, key: str) -> bytes | None:
        from botocore.exceptions import ClientError

        try:
            resp = self.client.get_object(Bucket=self.bucket, Key=self._key(key))
        except ClientError as exc:
            code = str(exc.response.get("Error", {}).get("Code", ""))
            if code in ("NoSuchKey", "404", "NotFound"):
                return None
            raise
        return resp["Body"].read()

    def write_bytes(
        self, key: str, data: bytes, content_type: str | None = None
    ) -> None:
        kwargs: dict[str, Any] = {}
        if content_type:
            kwargs["ContentType"] = content_type
        self.client.put_object(
            Bucket=self.bucket, Key=self._key(key), Body=data, **kwargs
        )

    def list(self, prefix: str = "") -> list[str]:
        """Sorted keys (relative to this store's prefix) starting with `prefix`."""
        strip = f"{self.prefix}/" if self.prefix else ""
        keys: list[str] = []
        paginator = self.client.get_paginator("list_objects_v2")
        for page in paginator.paginate(
            Bucket=self.bucket, Prefix=self._key(prefix)
        ):
            for obj in page.get("Contents", []):
                keys.append(obj["Key"][len(strip):])
        return sorted(keys)


def store_from_location(location: str | Path, client: Any = None) -> Store:
    """`s3://bucket/prefix` -> `S3Store` (using `client`); anything else ->
    `LocalStore`. The client is injected by the caller (config), never built
    here.
    """
    if isinstance(location, str) and location.startswith("s3://"):
        parsed = urlparse(location)
        return S3Store(parsed.netloc, parsed.path.strip("/"), client)
    return LocalStore(Path(location))
