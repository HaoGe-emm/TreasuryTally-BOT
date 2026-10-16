"""Independent Streamlit component for receipt-backed service comparison."""

from __future__ import annotations

from typing import Any

from trust_receipt.history import HistoryCategory, ReceiptSourceRef, ServiceComparison, ServiceHistoryProjection

_METRICS = (
    ("首次通过", "first_pass_count", HistoryCategory.FIRST_PASS),
    ("修复后通过", "fixed_pass_count", HistoryCategory.FIXED_PASS),
    ("未通过", "fail_count", HistoryCategory.FAIL),
    ("无法判断", "inconclusive_count", HistoryCategory.INCONCLUSIVE),
)


def _render_source(st: Any, source: ReceiptSourceRef) -> None:
    label = f"{source.task_id} · {source.outcome.value} · {source.receipt_hash[:12]}…"
    st.text(label)
    st.code(source.receipt_hash, language=None)
    st.caption(f"回执来源：{source.source_ref}")
    if source.public_uri:
        st.link_button("查看公开回执", source.public_uri)
    if source.revision and source.revision.parent_receipt_hash:
        st.caption("已核验的父回执（可能属于另一服务；不会把其结果计入本服务）：")
        st.code(source.revision.parent_receipt_hash, language=None)


def _render_sources(st: Any, history: ServiceHistoryProjection, category: HistoryCategory) -> None:
    sources = history.sources_for(category)
    if not sources:
        st.caption("没有对应的已核验任务。")
        return
    for source in sources:
        _render_source(st, source)


def _render_service(st: Any, history: ServiceHistoryProjection) -> None:
    st.subheader(history.service_name)
    st.caption(f"服务 ID：{history.service_id} · 任务类型：{history.task_type}")
    top = st.columns(2)
    top[0].metric("已核验任务", history.verified_task_count)
    top[1].metric("可验证回执", history.verifiable_receipt_count)
    with st.expander(f"全部可验证回执（{history.verifiable_receipt_count}）"):
        for source in history.receipt_refs:
            _render_source(st, source)
    for label, field, category in _METRICS:
        count = getattr(history, field)
        st.metric(label, count)
        with st.expander(f"{label}来源（{count}）"):
            _render_sources(st, history, category)
    latest = history.latest_delivery_at.isoformat() if history.latest_delivery_at else "暂无"
    st.caption(f"最近交付：{latest}")
    if history.receipt_refs:
        with st.expander("最近交付来源"):
            _render_source(st, history.receipt_refs[-1])


def render_service_history(
    comparison: ServiceComparison,
    *,
    streamlit_api: Any | None = None,
    key: str = "m10-service-history",
) -> str | None:
    """Render two histories without ranking them; return only an explicit user choice."""
    if streamlit_api is None:
        import streamlit as streamlit_api

    st = streamlit_api
    st.subheader("服务历史对比")
    st.caption("以下事实仅来自已核验回执；无法判断不计为未通过，系统不会生成综合评分。")
    columns = st.columns(2)
    for column, history in zip(columns, comparison.services, strict=True):
        with column:
            if not history.receipt_refs:
                st.caption("暂无已核验历史；零条记录不代表服务已通过或已失败。")
            _render_service(st, history)

    labels = {service.service_id: service.service_name for service in comparison.services}
    selected = st.radio(
        "人工选择服务",
        options=tuple(labels),
        index=None,
        format_func=lambda service_id: f"{labels[service_id]} · {service_id}",
        key=f"{key}-choice",
        help="选择由您确认，不代表系统推荐。",
    )
    if st.button("确认选择", disabled=selected is None, key=f"{key}-confirm"):
        return selected
    return None


__all__ = ["render_service_history"]


def render_workspace_history(st: Any, runtime: Any) -> None:
    from trust_receipt.history import compare_services
    from trust_receipt.orchestration.m10 import TASK_TYPE

    with st.expander("服务历史与下次选择", expanded=False):
        if not st.toggle("查看当前工作区服务历史", key="m10-show-history"):
            st.caption("按 ERC-20 拨款报表任务聚合，只读取当前工作区的已核验交付。")
            return
        snapshot = runtime.history_workflow.read_history()
        for issue in snapshot.issues:
            st.warning(issue)
        comparison = compare_services(
            snapshot.histories, task_type=TASK_TYPE, service_ids=("service-a", "service-b"),
            service_names={"service-a": "服务 A · 团队演示", "service-b": "服务 B · 团队演示"},
        )
        st.caption("样例故障是团队控制的模拟行为；这些本地统计不代表第三方公开信誉或链上反馈已确认。")
        chosen = render_service_history(comparison, streamlit_api=st)
        if chosen is not None:
            st.session_state["m10-next-service"] = chosen
            st.session_state["report-service"] = next(
                label for label, service in runtime.services.items() if service.service_id == chosen
            )
            st.success("已记录人工选择，将用于下一次服务交付。")
        with st.expander("查看来源回执与父版本内容"):
            if snapshot.receipts:
                by_hash = {receipt.receipt_hash: receipt for receipt in snapshot.receipts}
                selected = st.selectbox("来源回执", tuple(by_hash), key="m10-source-receipt")
                receipt = by_hash[selected]
                st.json(receipt.model_dump(mode="json"))
                revisions = {
                    ref.receipt_hash: ref.revision
                    for history in snapshot.histories for ref in history.receipt_refs
                }
                revision = revisions[selected]
                if revision and revision.parent_receipt_hash in by_hash:
                    st.caption("父回执保留原服务身份与结论")
                    st.json(by_hash[revision.parent_receipt_hash].model_dump(mode="json"))
            else:
                st.caption("当前没有可下钻的已核验回执。")
