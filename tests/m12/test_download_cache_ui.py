"""Actual AppTest media registration and shared lifecycle contention."""

from threading import Event, Thread
from types import SimpleNamespace

import pytest

from app import report_exports
from app.report_download_cache import DownloadCache
from tests.m12.test_business_report import page_for
from tests.m12.test_report_exports import view
from tests.reporting.conftest import report_input
from trust_receipt.reporting import build_business_report


@pytest.fixture
def cache(monkeypatch):
    cache = DownloadCache(max_bytes=64, max_file_bytes=32)
    monkeypatch.setattr(report_exports, "application_download_cache", lambda: cache)
    return cache


def create_word(page):
    next(button for button in page.button if button.label == "生成Word 报告").click().run()
    assert not page.exception


def test_actual_apptest_30_views_prunes_media_and_session_bytes(cache):
    report = view()
    page = page_for(report, exports=(lambda _: b"derived-copy", lambda _: b"pdf-copy"))
    page.session_state["executions"] = ["original-history"]
    page.session_state["report-export:old:docx"] = b"legacy-copy"
    for index in range(30):
        page.session_state["report"] = report.model_copy(update={"notice": str(index)})
        page.run()
        create_word(page)
        owner = page.session_state["report-download-lease"].owner
        view_hash = page.session_state["report-download-view"]
        assert cache.get(owner, view_hash, "docx") == b"derived-copy"
        assert cache.stats() == {"bytes": 12, "files": 1, "owners": 1}
        assert len(page.get("download_button")) == 2
        assert page.session_state["executions"] == ["original-history"]
        assert not any(key.startswith("report-export:") and isinstance(value, (bytes, str))
                       for key, value in page.session_state._state.filtered_state.items())
        entry = next(iter(cache._entries.values()))
        assert entry.file_ids and entry.references
        assert len(entry.media._storage._files_by_id) == 2  # original JSON + current Word
    page.session_state["report-download-lease"].close()
    assert cache.stats()["bytes"] == 0
    assert page.session_state["executions"] == ["original-history"]
    assert len(entry.media._storage._files_by_id) == 1


def test_oversized_ui_rejects_without_cached_download_or_verdict_change(cache):
    report = view()
    before = report.model_dump_json()
    page = page_for(report, exports=(lambda _: b"x" * 33, lambda _: b"valid-pdf"))
    create_word(page)
    assert len(page.get("download_button")) == 1
    assert "原 JSON 回执仍可下载" in page.error[0].value
    assert cache.stats()["bytes"] == 0
    assert page.session_state["report"].model_dump_json() == before
    next(button for button in page.button if button.label == "生成PDF 报告").click().run()
    assert len(page.get("download_button")) == 2
    assert cache.stats()["bytes"] == 9


def test_original_receipt_media_bytes_survive_reading_copy_retirement(cache):
    item = report_input("insufficient-evidence-page")
    report = build_business_report(item.receipt, item.submission, fund_flow=item.fund_flow)
    original = item.receipt.model_dump_json()
    page = page_for(report, receipt_json=original, exports=(lambda _: b"reading-copy", lambda _: b"pdf"))
    create_word(page)
    entry = next(iter(cache._entries.values()))
    manager = entry.media
    url = next(element.proto.url for element in page.get("download_button")
               if element.proto.label == "原 JSON 回执")
    file_id = url.rsplit("/", 1)[1].rsplit(".", 1)[0]
    page.session_state["report"] = report.model_copy(update={"notice": "new reading view"})
    page.run()
    assert not page.exception and cache.stats()["bytes"] == 0
    assert manager._storage.get_file(file_id).content == original.encode("utf-8")
    assert len(page.get("download_button")) == 1
    assert page.session_state["report"].current.receipt_hash == item.receipt.receipt_hash


def test_reset_only_removes_reading_copy_data_and_metadata(cache):
    lease = cache.lease()
    cache.activate(lease.owner, "view")
    cache.put(lease.owner, "view", "pdf", b"copy")
    state = {
        "report-download-lease": lease, "report-download-view": "view",
        "report-export:legacy:docx": b"old-copy", "report-export:view:pdf:create": False,
        "receipt": b"original-json", "executions": ["original-history"], "task": "original-task",
    }
    report_exports.reset_report_downloads(SimpleNamespace(session_state=state))
    assert cache.stats()["bytes"] == 0
    assert state == {
        "report-export:view:pdf:create": False, "receipt": b"original-json",
        "executions": ["original-history"], "task": "original-task",
    }


@pytest.mark.parametrize("cached", [False, True])
def test_busy_lifecycle_rejects_generation_or_registration_without_queue(cache, cached):
    calls = []

    def exporter(_):
        calls.append(True)
        return b"copy"

    page = page_for(view(), exports=(exporter, exporter))
    if cached:
        create_word(page)
    entered, release = Event(), Event()

    def hold_slot():
        with report_exports.application_renderer().export_slot():
            entered.set()
            assert release.wait(15)

    thread = Thread(target=hold_slot)
    thread.start()
    assert entered.wait(5)
    try:
        if cached:
            page.run()
        else:
            create_word(page)
        assert not page.exception
        assert len(page.get("download_button")) == 1
        assert "原 JSON 回执仍可下载" in page.error[0].value
        assert len(calls) == int(cached)
        assert cache.stats()["bytes"] == (4 if cached else 0)
    finally:
        release.set()
        thread.join(5)
    if not cached:
        create_word(page)
    else:
        page.run()
    assert len(page.get("download_button")) == 2
    assert len(calls) == 1
