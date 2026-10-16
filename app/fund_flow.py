"""Streamlit rendering for the M8 fund-flow read model."""

from __future__ import annotations

from html import escape

import streamlit as st

from app.fund_flow_graph import graph_svg
from trust_receipt.models import FundFlowProjection, FundFlowVisualStatus

STATUS_LABELS = {
    FundFlowVisualStatus.MATCHED: ("✓", "已匹配"),
    FundFlowVisualStatus.MISSING_FROM_REPORT: ("!", "报表漏报"),
    FundFlowVisualStatus.NOT_FOUND_ON_CHAIN: ("!", "链上未找到对应记录"),
    FundFlowVisualStatus.INTERNAL_TRANSFER: ("↔", "内部互转（按规则排除）"),
    FundFlowVisualStatus.DUPLICATE: ("⧉", "重复记录"),
    FundFlowVisualStatus.INCONCLUSIVE: ("?", "证据不足"),
    FundFlowVisualStatus.MISMATCH: ("≠", "报表与链上字段不一致"),
    FundFlowVisualStatus.INVALID_SCOPE: ("!", "不在已确认范围内"),
}


def render_fund_flow(projection: FundFlowProjection | None, *, allow_explorer_links: bool = False) -> None:
    st.markdown("#### 资金流对账图")
    if projection is None:
        st.info("历史会话未保存完整转账证据，无法重建资金流图；确定性结论与回执仍可核验。")
        return
    if not projection.edges:
        st.info("已确认范围内没有可展示的资金流。")
        return
    node_lookup = {node.node_id: node for node in projection.nodes}
    st.markdown(graph_svg(projection), unsafe_allow_html=True)
    st.caption("窄屏可在图内横向查看；下方事件列表保留完整方向、状态、金额和证据。")
    legend = "".join(
        f'<span class="flow-legend flow-{status.value}">{icon} {escape(label)}</span>'
        for status, (icon, label) in STATUS_LABELS.items()
    )
    st.markdown(f'<div class="flow-legend-row">{legend}</div>', unsafe_allow_html=True)
    for edge in projection.edges:
        source = node_lookup[edge.from_node_id]
        destination = node_lookup[edge.to_node_id]
        icon, label = STATUS_LABELS[edge.status]
        chain_id, transaction_hash, log_index = edge.event_key
        st.markdown(
            f'<div class="flow-edge flow-{edge.status.value}" role="group" '
            f'aria-label="{escape(label)}">'
            f'<div class="flow-route"><span>{escape(source.label)}</span><b>→</b>'
            f'<span>{escape(destination.label)}</span></div>'
            f'<div class="flow-amount">{escape(edge.amount_base_units)} <small>最小单位</small></div>'
            f'<div class="flow-status">{icon} {escape(label)}</div>'
            f'<div class="flow-key">chain {chain_id} · {escape(transaction_hash)} · log {log_index}</div>'
            "</div>",
            unsafe_allow_html=True,
        )
        with st.expander(f"事件详情 · {transaction_hash[:10]}…{transaction_hash[-6:]} · log {log_index}"):
            st.write(f"完整事件键：`{chain_id} + {transaction_hash} + {log_index}`")
            st.write("服务声明引用：", list(edge.service_refs) or "无")
            st.write("参考证据引用：", list(edge.reference_refs) or "无")
            st.write("关联 Finding：", list(edge.finding_ids) or "无")
            st.json({
                "service": [record.model_dump(mode="json") for record in edge.service_records],
                "reference": [record.model_dump(mode="json") for record in edge.reference_records],
            })
            if allow_explorer_links and edge.reference_refs and chain_id == 11_155_111:
                st.link_button("查看 Sepolia 参考交易", f"https://sepolia.etherscan.io/tx/{transaction_hash}")
