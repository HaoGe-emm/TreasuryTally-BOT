from __future__ import annotations

import pytest

from trust_receipt.publishing import HttpsDirectoryPublisher


class _Response:
    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self) -> bytes:
        return self._payload


def test_https_directory_publisher_writes_content_addressed_file_and_fetches(monkeypatch, tmp_path):
    payload = b'{"public":true}\n'
    captured = {}

    def fake_urlopen(uri, timeout):
        captured.update(uri=uri, timeout=timeout)
        return _Response(payload)

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    publisher = HttpsDirectoryPublisher(
        tmp_path,
        "https://creatoros.top/trust-receipt/public/",
        timeout_seconds=9,
    )

    uri = publisher.publish(payload, name="receipt.json")

    assert uri.startswith("https://creatoros.top/trust-receipt/public/")
    assert uri.endswith("-receipt.json")
    assert next(tmp_path.glob("*.json")).read_bytes() == payload
    assert publisher.fetch(uri) == payload
    assert captured == {"uri": uri, "timeout": 9}


def test_https_directory_publisher_rejects_non_https_and_unsafe_names(tmp_path):
    with pytest.raises(ValueError, match="must use HTTPS"):
        HttpsDirectoryPublisher(tmp_path, "http://example.test/public")

    publisher = HttpsDirectoryPublisher(tmp_path, "https://example.test/public")
    with pytest.raises(ValueError, match="invalid public receipt file name"):
        publisher.publish(b"{}", name="../private.json")
