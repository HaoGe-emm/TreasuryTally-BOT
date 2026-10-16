"""Read-only ECharts controls over a saved business report, never new evidence."""

from trust_receipt.reporting.echarts_flow import echarts_component_html

PAGE_SIZE = 12


def render_report_graph(st, report, *, embed=None):
    if embed is None:
        from streamlit.components.v1 import html

        embed = html
    identity = report.current.receipt_hash
    attempt = "current"
    if report.previous is not None:
        attempt = st.selectbox(
            "查看哪次资金流", ("current", "previous"),
            format_func=lambda value: "修复后 · 第 2 次" if value == "current" else "修复前 · 第 1 次",
            key=f"report-graph-attempt:{identity}",
        )
    snapshot = report.current if attempt == "current" else report.previous
    if not snapshot.graph_available:
        st.info("这次历史未保存可重建的资金流；不补造转账，原回执结论仍保留。")
        return
    total = len(snapshot.flow_rows)
    if not total:
        st.info("已保存资金流中没有可展示的转账事件；这不改变原核验结论。")
        return
    page = 0
    if total > PAGE_SIZE:
        page = st.selectbox(
            "查看哪组转账", tuple(range((total + PAGE_SIZE - 1) // PAGE_SIZE)),
            format_func=lambda number: (
                f"第 {number * PAGE_SIZE + 1}–{min((number + 1) * PAGE_SIZE, total)} 条 / 共 {total} 条"
            ), key=f"report-graph-page:{identity}:{attempt}",
        )
    offset = page * PAGE_SIZE
    st.caption(f"展示第 {offset + 1}–{min(offset + PAGE_SIZE, total)} 条，共 {total} 条；分页不省略事件。")
    try:
        document = echarts_component_html(report, attempt=attempt, offset=offset, limit=PAGE_SIZE)
        embed(document, height=560, scrolling=True)
    except (ValueError, OSError):
        st.error("资金流组件暂时无法读取；原回执已保留，不会生成替代证据。")
    st.caption("拖动或缩放只改变视图。点击连线查看金额与来源；线宽不表示金额。")
    st.caption("图内可横向或纵向滚动；长标签的省略号只缩略展示，完整精确值仍在详情与事件表。")
    st.caption("图例：" + "；".join(f"{item.label} — {item.meaning}" for item in report.legend))
    st.caption("完整事件与引用可在「验证依据 / 技术详情 → 交易与差异依据」查看。")
