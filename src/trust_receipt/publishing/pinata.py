"""Pinata/IPFS adapter with bounded HTTP calls and no credential logging."""

from __future__ import annotations

import json
import secrets
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from pydantic import SecretStr


class PinataPublisher:
    def __init__(
        self,
        jwt: SecretStr,
        *,
        api_url: str = "https://uploads.pinata.cloud/v3/files",
        gateway_url: str = "https://gateway.pinata.cloud/ipfs",
        timeout_seconds: float = 30,
    ) -> None:
        self._jwt = jwt
        self._api_url = api_url
        self._gateway_url = gateway_url.rstrip("/")
        self._timeout_seconds = timeout_seconds

    def publish(self, payload: bytes, *, name: str) -> str:
        name = Path(name).name
        if not name or "\r" in name or "\n" in name or '"' in name:
            raise ValueError("invalid Pinata file name")
        boundary = f"----trustreceipt{secrets.token_hex(16)}"
        disposition = f'form-data; name="file"; filename="{name}"'
        body = (
            f'--{boundary}\r\nContent-Disposition: form-data; name="network"\r\n\r\n'
            f"public\r\n--{boundary}\r\nContent-Disposition: {disposition}\r\n"
            "Content-Type: application/json\r\n\r\n"
        ).encode() + payload + (
            f'\r\n--{boundary}\r\nContent-Disposition: form-data; name="name"\r\n\r\n'
            f"{name}\r\n--{boundary}--\r\n"
        ).encode()
        request = urllib.request.Request(
            self._api_url,
            data=body,
            method="POST",
            headers={
                "Authorization": f"Bearer {self._jwt.get_secret_value()}",
                "Content-Type": f"multipart/form-data; boundary={boundary}",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=self._timeout_seconds) as response:
                result = json.loads(response.read())
        except (OSError, urllib.error.HTTPError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"Pinata upload failed: {type(exc).__name__}") from exc
        cid = result.get("data", {}).get("cid") or result.get("IpfsHash")
        if not isinstance(cid, str) or not cid:
            raise RuntimeError("Pinata upload returned no CID")
        return f"ipfs://{cid}"

    def fetch(self, uri: str) -> bytes:
        if not uri.startswith("ipfs://"):
            raise ValueError("Pinata publisher accepts only ipfs:// URIs")
        cid = uri.removeprefix("ipfs://")
        url = f"{self._gateway_url}/{urllib.parse.quote(cid, safe='')}"
        try:
            with urllib.request.urlopen(url, timeout=self._timeout_seconds) as response:
                return response.read()
        except (OSError, urllib.error.HTTPError) as exc:
            raise RuntimeError(f"Pinata gateway verification failed: {type(exc).__name__}") from exc
