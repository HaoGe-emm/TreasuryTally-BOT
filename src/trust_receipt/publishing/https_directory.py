"""Content-addressed HTTPS publisher backed by a shared local directory."""

from __future__ import annotations

import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from trust_receipt.hashing import content_hash


class HttpsDirectoryPublisher:
    def __init__(
        self,
        directory: Path,
        base_url: str,
        *,
        timeout_seconds: float = 30,
    ) -> None:
        if not base_url.startswith("https://"):
            raise ValueError("public receipt base URL must use HTTPS")
        self._directory = directory.resolve()
        self._directory.mkdir(parents=True, exist_ok=True)
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds

    def publish(self, payload: bytes, *, name: str) -> str:
        safe_name = Path(name).name
        if not safe_name or safe_name != name or any(char in safe_name for char in ('"', "\r", "\n")):
            raise ValueError("invalid public receipt file name")
        digest = content_hash(payload).removeprefix("0x")
        filename = f"{digest}-{safe_name}"
        target = self._directory / filename
        try:
            with target.open("xb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
        except FileExistsError:
            if target.read_bytes() != payload:
                raise ValueError("content-addressed public receipt path contains different bytes") from None
        return f"{self._base_url}/{urllib.parse.quote(filename, safe='')}"

    def fetch(self, uri: str) -> bytes:
        expected_prefix = self._base_url + "/"
        if not uri.startswith(expected_prefix):
            raise ValueError("public receipt URI is outside the configured HTTPS base URL")
        try:
            with urllib.request.urlopen(uri, timeout=self._timeout_seconds) as response:
                return response.read()
        except (OSError, urllib.error.HTTPError) as exc:
            raise RuntimeError(f"public receipt download failed: {type(exc).__name__}") from exc
