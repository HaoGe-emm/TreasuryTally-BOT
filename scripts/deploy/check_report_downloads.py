"""Actual AppTest export requests against the Linux runtime; no browser or RPC."""

import io
import json
import sys
from pathlib import Path
from zipfile import ZipFile

from streamlit.testing.v1 import AppTest


def harness():
    import streamlit as st

    from app.business_report import render_business_report
    from app.report_exports import document_exporters, render_additional_exports
    from app.report_graph import render_report_graph

    render_business_report(
        st, st.session_state["report"], graph=render_report_graph,
        exports=document_exporters(), receipt_json=st.session_state["receipt"],
    )
    render_additional_exports(st, st.session_state["report"])


def main():
    from app.report_exports import application_download_cache, application_renderer
    from trust_receipt.hashing import content_hash
    from trust_receipt.reporting import BusinessReportView

    view = BusinessReportView.model_validate_json(Path(sys.argv[1]).read_bytes())
    original = Path(sys.argv[2]).read_bytes()
    page = AppTest.from_function(harness, default_timeout=30)
    page.session_state["report"] = view
    page.session_state["receipt"] = original
    page.run()
    assert not page.exception and len(page.get("download_button")) == 1
    prefix = "report-export:" + content_hash(view.model_dump_json().encode()) + ":"
    assert all(prefix + suffix not in page.session_state for suffix in ("docx", "pdf", "html", "png", "svg"))
    cache = application_download_cache()
    owner = page.session_state["report-download-lease"].owner
    view_hash = page.session_state["report-download-view"]
    assert cache.stats()["bytes"] == 0 and cache.stats()["files"] == 0
    renderer = application_renderer()
    assert renderer._node == "/opt/trust-receipt-renderer/renderer-node"
    assert renderer._modules == "/opt/trust-receipt-renderer/node_modules"
    sizes = {}
    for label, suffix in (("Word 报告", "docx"), ("PDF 报告", "pdf"),
                          ("离线 HTML 报告", "html"), ("资金流 PNG", "png"), ("资金流 SVG", "svg")):
        next(button for button in page.button if button.label == "生成" + label).click().run()
        assert not page.exception and not page.error
        payload = cache.get(owner, view_hash, suffix)
        assert isinstance(payload, bytes)
        if suffix == "docx":
            with ZipFile(io.BytesIO(payload)) as doc:
                assert "word/document.xml" in doc.namelist()
        elif suffix == "pdf":
            assert payload.startswith(b"%PDF-")
        elif suffix == "png":
            assert payload.startswith(b"\x89PNG\r\n\x1a\n")
        elif suffix == "html":
            assert b"<svg" in payload and b"Content-Security-Policy" in payload
        else:
            assert b"<svg" in payload
        page.run()
        assert not page.exception
        assert payload == cache.get(owner, view_hash, suffix)
        sizes[suffix] = len(payload)
    assert cache.stats()["bytes"] == sum(sizes.values()) and cache.stats()["files"] == 5
    assert len(page.get("download_button")) == 6
    assert page.session_state["receipt"] == original
    assert page.session_state["report"].model_dump_json() == view.model_dump_json()
    print(json.dumps({"actual_app_test_exports": sizes, "downloads": 6, "original_json_unchanged": True,
                      "view_unchanged": True, "renderer_shared": application_renderer() is renderer,
                      "scope": "synthetic view only; no browser, HTTP download, RPC or production"}))


if __name__ == "__main__":
    main()
