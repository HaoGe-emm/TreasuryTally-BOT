"""Bounded anonymous reads from configured public receipt storage."""

from __future__ import annotations

import re
from urllib.parse import urlsplit

import httpx


class PublicArtifactReader:
    def __init__(
        self, *, https_base_urls: tuple[str, ...], ipfs_gateway: str,
        timeout_seconds: float = 10, max_bytes: int = 4_000_000,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._bases = tuple(base.rstrip("/") + "/" for base in https_base_urls)
        self._gateway = ipfs_gateway.rstrip("/")
        self._timeout = timeout_seconds
        self._max_bytes = max_bytes
        self._transport = transport

    def fetch(self, uri: str) -> bytes:
        if uri.startswith("ipfs://"):
            cid = uri.removeprefix("ipfs://")
            if re.fullmatch(r"[A-Za-z0-9]{32,128}", cid) is None:
                raise ValueError("invalid IPFS content identifier")
            url = f"{self._gateway}/{cid}"
        else:
            base = next((base for base in self._bases if uri.startswith(base)), None)
            if base is None or re.fullmatch(r"[A-Za-z0-9_-][A-Za-z0-9._-]*", uri[len(base):]) is None:
                raise ValueError("URI must be a file in the configured public receipt storage")
            url = uri
        parsed = urlsplit(url)
        if parsed.scheme != "https" or parsed.username is not None or parsed.password is not None:
            raise ValueError("public receipt storage must use credential-free HTTPS")
        try:
            with httpx.Client(
                timeout=self._timeout, follow_redirects=False, transport=self._transport,
            ) as client, client.stream("GET", url) as response:
                response.raise_for_status()
                payload = bytearray()
                for chunk in response.iter_bytes():
                    payload.extend(chunk)
                    if len(payload) > self._max_bytes:
                        raise ValueError("public artifact exceeds the size limit")
                return bytes(payload)
        except httpx.HTTPError as exc:
            raise OSError(f"public artifact download failed: {type(exc).__name__}") from exc
