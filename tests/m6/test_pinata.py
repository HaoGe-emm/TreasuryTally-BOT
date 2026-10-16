from __future__ import annotations

import json

from pydantic import SecretStr

from trust_receipt.publishing import PinataPublisher


class _Response:
    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self) -> bytes:
        return self._payload


def test_pinata_upload_uses_public_network_and_bearer_without_logging_secret(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout):
        captured["request"] = request
        captured["timeout"] = timeout
        return _Response(json.dumps({"data": {"cid": "bafy-public-receipt"}}).encode())

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    publisher = PinataPublisher(SecretStr("top-secret-jwt"), timeout_seconds=7)

    uri = publisher.publish(b'{"receipt":true}', name="receipt.json")

    request = captured["request"]
    assert uri == "ipfs://bafy-public-receipt"
    assert request.get_header("Authorization") == "Bearer top-secret-jwt"
    assert b'name="network"' in request.data
    assert b"public" in request.data
    assert b'name="file"; filename="receipt.json"' in request.data
    assert b'name="name"' in request.data
    assert captured["timeout"] == 7
