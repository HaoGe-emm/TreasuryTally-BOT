"""Measured bytes and actual framework media lifetime, not renderer mocks."""

import gc
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from streamlit.runtime.media_file_manager import MediaFileManager
from streamlit.runtime.memory_media_file_storage import MemoryMediaFileStorage

from app.report_download_cache import DownloadCache
from trust_receipt.reporting import ExportUnavailable


def store():
    return DownloadCache(max_bytes=16, max_file_bytes=8)


def test_current_view_only_and_private_owner_isolation():
    cache = store()
    a, b = cache.lease(), cache.lease()
    cache.activate(a.owner, "first")
    cache.activate(b.owner, "first")
    cache.put(a.owner, "first", "docx", b"abcdef")
    assert cache.get(b.owner, "first", "docx") is None
    cache.put(b.owner, "first", "pdf", b"12345678")
    cache.activate(a.owner, "second")
    assert cache.get(a.owner, "first", "docx") is None
    assert cache.get(b.owner, "first", "pdf") == b"12345678"
    assert cache.stats()["bytes"] == 8
    with pytest.raises(ExportUnavailable, match="obsolete"):
        cache.put(a.owner, "first", "png", b"x")


def test_global_budget_file_limit_and_replacement_atomicity():
    cache = store()
    a, b = cache.lease(), cache.lease()
    for lease in (a, b):
        cache.activate(lease.owner, "view")
    cache.put(a.owner, "view", "docx", b"12345678")
    cache.put(b.owner, "view", "pdf", b"abcdefgh")
    for suffix, payload in (("svg", b"1"), ("docx", b"x" * 9)):
        with pytest.raises(ExportUnavailable, match="budget"):
            cache.put(a.owner, "view", suffix, payload)
        assert cache.stats() == {"bytes": 16, "files": 2, "owners": 2}
        assert cache.get(a.owner, "view", "docx") == b"12345678"
    cache.put(a.owner, "view", "docx", b"new")
    cache.put(a.owner, "view", "svg", "中")
    assert cache.stats()["bytes"] == 14


def test_only_five_formats_and_lease_lifetime():
    cache = DownloadCache(max_bytes=32, max_file_bytes=8)
    lease = cache.lease()
    cache.activate(lease.owner, "view")
    for suffix in ("docx", "pdf", "html", "png", "svg"):
        cache.put(lease.owner, "view", suffix, b"x")
    with pytest.raises(ExportUnavailable, match="invalid"):
        cache.put(lease.owner, "view", "json", b"original-must-not-enter")
    assert cache.stats()["files"] == 5
    del lease
    gc.collect()
    assert cache.stats() == {"bytes": 0, "files": 0, "owners": 0}


def publish(cache, lease, view, manager, payload):
    from streamlit.runtime.media_file_manager import _get_session_id

    cache.put(lease.owner, view, "pdf", payload)
    cache.publish(
        lease.owner, view, "pdf", media=manager, session_id=_get_session_id(), coordinate="report",
        filename="report.pdf", mime="application/pdf",
        download=lambda data: manager.add(data, "application/pdf", "report", "report.pdf",
                                          is_for_static_download=True),
    )


def test_real_media_multisession_multiview_keeps_no_obsolete_bytes(monkeypatch):
    current = ["session-a"]
    monkeypatch.setattr("streamlit.runtime.media_file_manager._get_session_id", lambda: current[0])
    media = MediaFileManager(MemoryMediaFileStorage("/media"))
    cache = DownloadCache(max_bytes=32, max_file_bytes=8)
    leases = [cache.lease() for _ in range(4)]
    originals = []
    for index in range(4):
        current[0] = f"session-{index}"
        originals.append(media.add(f"original-{index}".encode(), "application/json", "receipt",
                                   f"receipt-{index}.json", is_for_static_download=True))
    for view in range(30):
        for index, lease in enumerate(leases):
            current[0] = f"session-{index}"
            cache.activate(lease.owner, str(view))
            publish(cache, lease, str(view), media, f"{index}:{view}".encode())
        # Other sessions never clear their media refs or rerun on pruning.
        assert cache.stats()["files"] == 4
        assert len(media._storage._files_by_id) == 8
        assert sum(item.content_size for item in media._storage._files_by_id.values()
                   if item.mimetype == "application/pdf") == cache.stats()["bytes"]
        assert all(media._storage.get_file(url.rsplit("/", 1)[1].rsplit(".", 1)[0]).content
                   == f"original-{index}".encode() for index, url in enumerate(originals))
    for lease in leases:
        lease.close()
    assert cache.stats()["bytes"] == 0
    assert len(media._storage._files_by_id) == 4


def test_framework_dedup_is_canonical_and_refcounted(monkeypatch):
    current = ["a"]
    monkeypatch.setattr("streamlit.runtime.media_file_manager._get_session_id", lambda: current[0])
    media = MediaFileManager(MemoryMediaFileStorage("/media"))
    cache = store()
    a, b = cache.lease(), cache.lease()
    for lease in (a, b):
        current[0] = lease.owner
        cache.activate(lease.owner, "view")
        publish(cache, lease, "view", media, bytes(bytearray(b"same")))
    assert cache.get(a.owner, "view", "pdf") is cache.get(b.owner, "view", "pdf")
    assert len(media._storage._files_by_id) == 1
    a.close()
    assert len(media._storage._files_by_id) == 1
    assert cache.stats()["bytes"] == 4
    b.close()
    assert not media._storage._files_by_id


def test_unsupported_framework_rejects_before_download():
    cache = store()
    lease = cache.lease()
    cache.activate(lease.owner, "view")
    cache.put(lease.owner, "view", "pdf", b"safe")
    calls = []
    with pytest.raises(ExportUnavailable, match="unsupported"):
        cache.publish(
            lease.owner, "view", "pdf", media=object(), session_id="test", coordinate="report",
            filename="report.pdf", mime="application/pdf", download=lambda _: calls.append(True),
        )
    assert not calls


def test_foreign_widget_shared_file_survives_and_stays_budgeted(monkeypatch):
    current = ["owned"]
    monkeypatch.setattr("streamlit.runtime.media_file_manager._get_session_id", lambda: current[0])
    media = MediaFileManager(MemoryMediaFileStorage("/media"))
    cache = store()
    lease = cache.lease()
    cache.activate(lease.owner, "first")
    publish(cache, lease, "first", media, b"12345678")
    current[0] = "foreign"
    media.add(b"12345678", "application/pdf", "foreign-widget", "report.pdf", is_for_static_download=True)
    cache.activate(lease.owner, "second")
    assert len(media._storage._files_by_id) == 1
    assert cache.stats()["bytes"] == 8
    assert media._files_by_session_and_coord["foreign"]
    cache.put(lease.owner, "second", "docx", b"abcdefgh")
    with pytest.raises(ExportUnavailable, match="budget"):
        cache.put(lease.owner, "second", "html", b"x")
    media.clear_session_refs("foreign")
    assert cache.stats()["bytes"] == 8
    assert not media._storage._files_by_id


def test_concurrent_sessions_cannot_exceed_total_budget():
    cache = DownloadCache(max_bytes=32, max_file_bytes=8)
    leases = [cache.lease() for _ in range(8)]
    barrier = Barrier(8)

    def request(lease):
        cache.activate(lease.owner, "view")
        barrier.wait(timeout=5)
        try:
            cache.put(lease.owner, "view", "docx", b"12345678")
            return True
        except ExportUnavailable:
            return False

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(request, leases))
    assert sum(results) == 4
    assert cache.stats()["bytes"] == 32


def test_published_replacement_cannot_hide_foreign_retained_bytes(monkeypatch):
    current = ["owned"]
    monkeypatch.setattr("streamlit.runtime.media_file_manager._get_session_id", lambda: current[0])
    media = MediaFileManager(MemoryMediaFileStorage("/media"))
    cache = store()
    lease = cache.lease()
    cache.activate(lease.owner, "view")
    publish(cache, lease, "view", media, b"12345678")
    current[0] = "foreign"
    media.add(b"12345678", "application/pdf", "other", "report.pdf", is_for_static_download=True)
    cache.put(lease.owner, "view", "pdf", b"new")
    assert cache.stats()["bytes"] == 11
    assert len(media._storage._files_by_id) == 1
    with pytest.raises(ExportUnavailable, match="budget"):
        cache.put(lease.owner, "view", "docx", b"12345678")
    assert cache.get(lease.owner, "view", "pdf") == b"new"


def test_widget_failure_after_registration_still_releases_exact_file(monkeypatch):
    monkeypatch.setattr("streamlit.runtime.media_file_manager._get_session_id", lambda: "owned")
    media = MediaFileManager(MemoryMediaFileStorage("/media"))
    cache = store()
    lease = cache.lease()
    cache.activate(lease.owner, "view")
    cache.put(lease.owner, "view", "pdf", b"safe")

    def widget(data):
        media.add(data, "application/pdf", "report", "report.pdf", is_for_static_download=True)
        raise ValueError("enqueue failed")

    with pytest.raises(ValueError, match="enqueue"):
        cache.publish(
            lease.owner, "view", "pdf", media=media, session_id="owned", coordinate="report",
            filename="report.pdf", mime="application/pdf", download=widget,
        )
    assert len(media._storage._files_by_id) == 1
    lease.close()
    assert not media._storage._files_by_id


def test_same_session_foreign_widget_reference_is_not_appropriated(monkeypatch):
    monkeypatch.setattr("streamlit.runtime.media_file_manager._get_session_id", lambda: "same-session")
    media = MediaFileManager(MemoryMediaFileStorage("/media"))
    media.add(b"same", "application/pdf", "foreign-widget", "report.pdf", is_for_static_download=True)
    cache = store()
    lease = cache.lease()
    cache.activate(lease.owner, "view")
    publish(cache, lease, "view", media, b"same")
    lease.close()
    assert media._files_by_session_and_coord["same-session"] == {
        "foreign-widget": next(iter(media._storage._files_by_id)),
    }
    assert cache.stats()["bytes"] == 4
