"""Download composition gates; byte doubles do not claim visual/format QA."""

from contextlib import nullcontext
from types import SimpleNamespace

import pytest
from streamlit.testing.v1 import AppTest

from app import report_exports
from tests.m12.test_business_report import page_for
from tests.reporting.conftest import report_input
from trust_receipt.reporting import ExportUnavailable, build_business_report


def view():
    item = report_input()
    return build_business_report(item.receipt, item.submission, fund_flow=item.fund_flow)


def additional_harness():
    import streamlit as st

    from app.report_exports import render_additional_exports

    render_additional_exports(st, st.session_state["report"])


def test_application_instance_shared_by_formats_and_sessions(monkeypatch):
    report_exports.application_renderer.clear()
    monkeypatch.setenv("REPORT_RENDERER_NODE", "/trusted/isolated-renderer")
    monkeypatch.setenv("REPORT_RENDERER_MODULES", "/trusted/modules")
    try:
        renderer = report_exports.application_renderer()
        assert renderer is report_exports.application_renderer()
        word, pdf = report_exports.document_exporters()
        assert word.keywords["renderer"] is pdf.keywords["renderer"] is renderer
        assert renderer._node == "/trusted/isolated-renderer"
        assert renderer._modules == "/trusted/modules"
        monkeypatch.setenv("REPORT_RENDERER_NODE", "/changed/needs-restart")
        assert report_exports.application_renderer() is renderer
    finally:
        report_exports.application_renderer.clear()


@pytest.mark.parametrize("configured", [None, ""])
def test_no_path_node_fallback_when_missing_or_empty(monkeypatch, configured):
    report_exports.application_renderer.clear()
    if configured is None:
        monkeypatch.delenv("REPORT_RENDERER_NODE", raising=False)
    else:
        monkeypatch.setenv("REPORT_RENDERER_NODE", configured)
    try:
        renderer = report_exports.application_renderer()
        assert renderer._node == "/opt/trust-receipt-renderer/renderer-node"
    finally:
        report_exports.application_renderer.clear()


def test_unavailable_download_preserves_original_and_verdict():
    report = view()
    before = report.model_dump_json()

    def unavailable(_):
        raise ExportUnavailable("private/path/secret must not be displayed")

    page = page_for(report, exports=(unavailable, unavailable))
    for label in ("生成Word 报告", "生成PDF 报告"):
        next(button for button in page.button if button.label == label).click().run()
        assert not page.exception
        assert len(page.get("download_button")) == 1
        assert "原 JSON 回执仍可下载" in page.error[0].value
        assert "private" not in page.error[0].value
    assert report.model_dump_json() == before


def test_full_view_binding_invalidates_previous_download():
    calls = []

    def exporter(report):
        calls.append(report.model_dump_json())
        return b"explicit-unit-double"

    report = view()
    page = page_for(report, exports=(exporter, exporter))
    next(button for button in page.button if button.label == "生成Word 报告").click().run()
    assert len(calls) == 1
    page.session_state["report"] = report.model_copy(update={"notice": "不同完整业务视图"})
    page.run()
    assert len(page.get("download_button")) == 1
    next(button for button in page.button if button.label == "生成Word 报告").click().run()
    assert len(calls) == 2


@pytest.mark.parametrize("label,suffix", [
    ("离线 HTML 报告", "html"), ("资金流 PNG", "png"), ("资金流 SVG", "svg"),
])
def test_additional_downloads_lazy_cached_and_format_bound(monkeypatch, label, suffix):
    calls = []
    renderer = SimpleNamespace(export_slot=nullcontext)
    monkeypatch.setattr(report_exports, "application_renderer", lambda: renderer)

    def exporter(report, *, renderer):
        calls.append((report.current.receipt_hash, renderer))
        return b"explicit-unit-double"

    for name in ("export_html", "graph_png", "graph_svg"):
        monkeypatch.setattr(report_exports, name, exporter)
    page = AppTest.from_function(additional_harness)
    page.session_state["report"] = view()
    page.run()
    assert not page.exception and not calls and len(page.button) == 3
    next(button for button in page.button if button.label == "生成" + label).click().run()
    page.run()
    assert not page.exception and len(calls) == 1 and calls[0][1] is renderer
    download = page.get("download_button")[0]
    assert download.proto.label == label
    assert len(page.button) == 2
