"""Lazy private downloads; renderer configuration belongs to deployment only."""

import os
from functools import partial

import streamlit as st

from app.report_download_cache import DownloadCache
from trust_receipt.hashing import content_hash
from trust_receipt.reporting import (
    EChartsRenderer,
    ExportUnavailable,
    export_docx,
    export_html,
    export_pdf,
    graph_png,
    graph_svg,
)

# M14 supplied measured-pressure candidates; final deployment gate is separate.
DOWNLOAD_CACHE_BYTES = 16 * 1024 * 1024
DOWNLOAD_FILE_BYTES = 8 * 1024 * 1024


@st.cache_resource
def application_download_cache():
    return DownloadCache(max_bytes=DOWNLOAD_CACHE_BYTES, max_file_bytes=DOWNLOAD_FILE_BYTES)


def reset_report_downloads(st):
    lease = st.session_state.pop("report-download-lease", None)
    if lease is not None:
        lease.close()
    st.session_state.pop("report-download-view", None)
    _prune_legacy_bytes(st)


def _prune_legacy_bytes(st):
    # Remove only the old implementation's reading-copy bytes, not widget
    # values, original JSON, executions, receipts or business history.
    for key in list(st.session_state):
        if key.startswith("report-export:") and isinstance(st.session_state[key], (bytes, str)):
            st.session_state.pop(key, None)


def sync_report_downloads(st, report):
    _prune_legacy_bytes(st)
    if "report-download-lease" not in st.session_state:
        reset_report_downloads(st)
        st.session_state["report-download-lease"] = application_download_cache().lease()
    view_hash = content_hash(report.model_dump_json().encode())
    owner = st.session_state["report-download-lease"].owner
    application_download_cache().activate(owner, view_hash)
    st.session_state["report-download-view"] = view_hash
    return owner, view_hash


def _media_manager():
    from streamlit import runtime

    return runtime.get_instance().media_file_mgr if runtime.exists() else None


def _session_id():
    from streamlit.runtime.scriptrunner import get_script_run_ctx

    context = get_script_run_ctx()
    return context.session_id if context is not None else None


def _download_coordinate(st):
    generator = getattr(st.download_button, "__self__", None)
    coordinate = getattr(generator, "_get_delta_path_str", None)
    if not callable(coordinate):
        raise ExportUnavailable("EXPORT_UNAVAILABLE: unsupported download widget")
    return coordinate()


def _export_slot():
    renderer = application_renderer()
    if not hasattr(renderer, "export_slot"):
        raise ExportUnavailable("EXPORT_UNAVAILABLE: missing lifecycle budget")
    return renderer.export_slot()


@st.cache_resource
def application_renderer():
    """One application instance, shared across sessions and all formats.

    Never discover a bare PATH Node: the deployment launcher owns isolation.
    Environment changes require an application restart.
    """
    return EChartsRenderer(
        node_path=os.environ.get("REPORT_RENDERER_NODE") or "/opt/trust-receipt-renderer/renderer-node",
        modules_path=os.environ.get("REPORT_RENDERER_MODULES") or "/opt/trust-receipt-renderer/node_modules",
    )


def document_exporters():
    renderer = application_renderer()
    return partial(export_docx, renderer=renderer), partial(export_pdf, renderer=renderer)


def render_export_download(st, report, *, label, suffix, mime, export):
    """No worker runs until requested; cache is bound to the entire frozen view."""
    owner, view_hash = sync_report_downloads(st, report)
    cache = application_download_cache()
    key = f"report-export:{view_hash}:{suffix}"
    if cache.get(owner, view_hash, suffix) is None:
        if st.button(f"生成{label}", key=key + ":create", use_container_width=True):
            try:
                with st.spinner(f"正在生成{label}…"), _export_slot():
                    cache.put(owner, view_hash, suffix, export(report))
                st.rerun()
            except (ValueError, OSError, RuntimeError, ImportError):
                st.error(f"{label}导出暂不可用（组件缺失、繁忙或生成失败）；原 JSON 回执仍可下载。")
    else:
        try:
            with _export_slot():
                filename = f"treasury-report-{report.current.attempt}.{suffix}"
                cache.publish(
                    owner, view_hash, suffix, media=_media_manager(), session_id=_session_id(),
                    coordinate=_download_coordinate(st), filename=filename, mime=mime,
                    download=lambda payload: st.download_button(
                        label, payload, filename, mime, key=key + ":download", use_container_width=True,
                    ),
                )
        except (ValueError, OSError, RuntimeError, ImportError):
            st.error(f"{label}下载暂不可用（繁忙、超限或缓存已过期）；原 JSON 回执仍可下载。")


def render_additional_exports(st, report):
    st.caption("以下文件属于最新业务报告的阅读副本；有两次交付时包含原核对历史，不是公开发布。")
    renderer = application_renderer()
    for label, suffix, mime, exporter in (
        ("离线 HTML 报告", "html", "text/html", export_html),
        ("资金流 PNG", "png", "image/png", graph_png),
        ("资金流 SVG", "svg", "image/svg+xml", graph_svg),
    ):
        render_export_download(
            st, report, label=label, suffix=suffix, mime=mime,
            export=partial(exporter, renderer=renderer),
        )
    st.caption("静态资金流仅展示最多前 4 条记录，拥挤并行线仅首条；完整事件见报告明细与原回执。")
