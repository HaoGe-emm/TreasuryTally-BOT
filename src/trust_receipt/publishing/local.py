"""Deterministic offline publisher used for tests and local demonstrations."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import unquote, urlparse
from urllib.request import url2pathname

from trust_receipt.hashing import content_hash


class LocalDirectoryPublisher:
    def __init__(self, directory: Path) -> None:
        self._directory = directory.resolve()
        self._directory.mkdir(parents=True, exist_ok=True)

    def publish(self, payload: bytes, *, name: str) -> str:
        digest = content_hash(payload).removeprefix("0x")
        target = self._directory / f"{digest}-{Path(name).name}"
        with target.open("xb") as handle:
            handle.write(payload)
        return target.as_uri()

    def fetch(self, uri: str) -> bytes:
        parsed = urlparse(uri)
        if parsed.scheme != "file":
            raise ValueError("local publisher accepts only file:// URIs")
        path = Path(url2pathname(unquote(parsed.path))).resolve()
        if path.parent != self._directory:
            raise ValueError("local publication URI escapes the configured directory")
        return path.read_bytes()
