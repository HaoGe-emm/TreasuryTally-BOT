"""Complete export budget, separate from the shorter-lived Node permit."""

import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

from trust_receipt.reporting import (
    build_business_report,
    export_docx,
    export_html,
    export_pdf,
    graph_png,
    graph_svg,
)
from trust_receipt.reporting.renderer import EChartsRenderer, ExportUnavailable, RenderedDiagram

BUILDERS = [
    (export_docx, "trust_receipt.reporting.docx_export._export_docx"),
    (export_pdf, "trust_receipt.reporting.pdf_export._export_pdf"),
    (export_html, "trust_receipt.reporting.html_export._export_html"),
]


def view_for(item):
    return build_business_report(item.receipt, item.submission, fund_flow=item.fund_flow, source_mode="fixture")


def probe_slot(renderer):
    with renderer.export_slot():
        return "available"


def test_export_slot_is_nonblocking_and_same_thread_reentrant():
    renderer = EChartsRenderer()
    with ThreadPoolExecutor(max_workers=1) as pool:
        with renderer.export_slot(), renderer.export_slot():
            assert probe_slot(renderer) == "available"
            with pytest.raises(ExportUnavailable, match="export busy"):
                pool.submit(probe_slot, renderer).result(timeout=1)
        assert pool.submit(probe_slot, renderer).result(timeout=1) == "available"


def test_budget_is_instance_owned_not_global():
    renderer = EChartsRenderer()
    other = EChartsRenderer()
    with renderer.export_slot(), ThreadPoolExecutor(max_workers=1) as pool:
        assert pool.submit(probe_slot, other).result(timeout=1) == "available"


@pytest.mark.parametrize("builder", [export_docx, export_pdf, export_html, graph_png, graph_svg])
def test_all_export_entries_reject_busy_before_work(failing_input, builder):
    renderer = EChartsRenderer(node_path="missing-node")
    view = view_for(failing_input)
    receipt_before = failing_input.receipt.model_dump_json()
    view_before = view.model_dump_json()
    with (
        renderer.export_slot(),
        ThreadPoolExecutor(max_workers=1) as pool,
        pytest.raises(ExportUnavailable, match="export busy"),
    ):
        pool.submit(builder, view, renderer=renderer).result(timeout=1)
    assert view.model_dump_json() == view_before
    assert failing_input.receipt.model_dump_json() == receipt_before


@pytest.mark.parametrize(("builder", "body_path"), BUILDERS)
def test_document_budget_outlives_node_and_covers_final_bytes(failing_input, monkeypatch, builder, body_path):
    renderer = EChartsRenderer(node_path=__file__)
    view = view_for(failing_input)
    after_node, finish = threading.Event(), threading.Event()
    monkeypatch.setattr(renderer, "_run", lambda data, binding, view_hash, option_hash:
                        RenderedDiagram(view_hash, option_hash, b"png", "<svg/>"))

    def body(report, *, renderer):
        # A real render entry consumes and releases its independent Node slot.
        assert graph_png(report, renderer=renderer) == b"png"
        assert renderer._slots.acquire(blocking=False)
        renderer._slots.release()
        after_node.set()
        assert finish.wait(timeout=5)
        # Represents later font/layout/ZIP and byte assembly, still protected.
        return b"complete export bytes"

    monkeypatch.setattr(body_path, body)
    with ThreadPoolExecutor(max_workers=2) as pool:
        export = pool.submit(builder, view, renderer=renderer)
        try:
            assert after_node.wait(timeout=3)
            with pytest.raises(ExportUnavailable, match="export busy"):
                pool.submit(graph_svg, view, renderer=renderer).result(timeout=1)
        finally:
            finish.set()
        assert export.result(timeout=3) == b"complete export bytes"
        assert pool.submit(probe_slot, renderer).result(timeout=1) == "available"


@pytest.mark.parametrize(("builder", "body_path"), BUILDERS)
@pytest.mark.parametrize("error_type", [OSError, ExportUnavailable])
def test_late_export_exception_releases_budget(failing_input, monkeypatch, builder, body_path, error_type):
    renderer = EChartsRenderer(node_path=__file__)
    monkeypatch.setattr(renderer, "_run", lambda data, binding, view_hash, option_hash:
                        RenderedDiagram(view_hash, option_hash, b"png", "<svg/>"))

    def body(report, *, renderer):
        graph_png(report, renderer=renderer)
        raise error_type("late layout or packaging failure")

    monkeypatch.setattr(body_path, body)
    with pytest.raises(error_type, match="late layout"):
        builder(view_for(failing_input), renderer=renderer)
    with ThreadPoolExecutor(max_workers=1) as pool:
        assert pool.submit(probe_slot, renderer).result(timeout=1) == "available"
    assert renderer._slots.acquire(blocking=False)
    renderer._slots.release()


def test_outer_application_slot_can_cover_cache_and_media_registration(failing_input, monkeypatch):
    renderer = EChartsRenderer(node_path=__file__)
    monkeypatch.setattr(renderer, "_run", lambda data, binding, view_hash, option_hash:
                        RenderedDiagram(view_hash, option_hash, b"png", "<svg/>"))
    with renderer.export_slot(), ThreadPoolExecutor(max_workers=1) as pool:
        assert graph_svg(view_for(failing_input), renderer=renderer) == "<svg/>"
        # Application cache/media registration can retain the same outer budget.
        with pytest.raises(ExportUnavailable, match="export busy"):
            pool.submit(probe_slot, renderer).result(timeout=1)
    with ThreadPoolExecutor(max_workers=1) as pool:
        assert pool.submit(probe_slot, renderer).result(timeout=1) == "available"
