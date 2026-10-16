import httpx
import pytest

from trust_receipt.m9.public_reader import PublicArtifactReader


def _reader(handler, **kwargs):
    return PublicArtifactReader(
        https_base_urls=("https://public.test/receipts",), ipfs_gateway="https://gateway.test/ipfs",
        transport=httpx.MockTransport(handler), **kwargs,
    )


@pytest.mark.parametrize("uri", [
    "http://public.test/receipts/file.json", "http://127.0.0.1/private", "file:///private.json",
    "https://public.test/receipts/../private", "https://public.test/receipts/file.json?secret=1",
    "https://public.test.evil/receipts/file.json", "ipfs://../../private",
])
def test_public_reader_rejects_unconfigured_locations_without_requests(uri):
    def reject(request):
        raise AssertionError("must not fetch an unconfigured location")

    with pytest.raises(ValueError):
        _reader(reject).fetch(uri)


def test_public_reader_bounds_download_and_does_not_follow_redirects():
    with pytest.raises(ValueError, match="size limit"):
        _reader(lambda request: httpx.Response(200, content=b"x" * 11), max_bytes=10).fetch(
            "https://public.test/receipts/file.json",
        )
    with pytest.raises(OSError):
        _reader(lambda request: httpx.Response(302, headers={"location": "http://127.0.0.1/private"})).fetch(
            "https://public.test/receipts/file.json",
        )


def test_public_reader_fetches_public_https_or_ipfs_anonymously():
    def respond(request):
        assert "authorization" not in request.headers
        return httpx.Response(200, content=b"public")

    reader = _reader(respond)
    assert reader.fetch("https://public.test/receipts/file.json") == b"public"
    assert reader.fetch("ipfs://" + "a" * 46) == b"public"
