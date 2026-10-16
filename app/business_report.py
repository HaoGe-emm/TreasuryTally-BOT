"""A single business reading surface; all facts and amounts come from reporting."""

from html import escape

from app.report_exports import render_export_download, sync_report_downloads


def render_business_report(st, report, *, graph=None, exports=None, receipt_json: str):
    sync_report_downloads(st, report)
    current = report.current
    st.html(
        f'<section class="attempt-card outcome-{escape(report.outcome.value)}">'
        f'<div><small>第 {current.attempt} 次核对 · {escape(report.source_mode_label)}</small>'
        f'<h2 class="attempt-title">{escape(report.conclusion)}</h2></div></section>'
    )
    network = "Sepolia" if report.scope.chain_id == 11_155_111 else f"链 {report.scope.chain_id}"
    st.caption(
        f"核对范围：{network} · {report.scope.token.short} · "
        f"区块 {report.scope.start_block:,} 至 {report.scope.end_block:,}"
    )
    amounts = (current.claimed, current.calculated, current.difference)
    units = {amount.unit for amount in amounts if amount is not None}
    columns = st.columns(3)
    for column, label, amount in zip(
        columns, ("报表金额", "链上有效金额", "差额（报表 − 链上）"),
        amounts, strict=True,
    ):
        with column:
            st.metric(
                label, amount.display if amount is not None else "无法确定",
                help=(f"{amount.unit}；精确最小单位：{amount.base_units}" if amount else current.difference_reason),
            )
            if len(units) > 1 and amount is not None:
                st.caption(amount.unit)
    if len(units) == 1:
        st.caption(current.claimed.unit)
    inconclusive = report.outcome.value == "INCONCLUSIVE"
    uncertainties = current.uncertainties
    if inconclusive:
        st.markdown("#### 为什么暂不能判断")
        st.warning(uncertainties[0] if uncertainties else "已保存证据不足，暂时不能判断报表是否符合范围。")
    elif current.difference_reason:
        st.warning(current.difference_reason)

    if current.findings:
        st.markdown("#### 需要处理的差异")
        grouped = {}
        for finding in current.findings:
            grouped.setdefault((finding.finding_type, finding.confirmed), []).append(finding)
        for number, items in enumerate(grouped.values(), 1):
            finding = items[0]
            st.html(
                '<div class="finding-card">'
                f'<strong>{number}. {escape(finding.title)}</strong>'
                f'<p>{escape(finding.description)}</p>'
                f'<p>{escape(finding.recommendation)}</p>'
                f'<small>{len(items)} 条{"已确认差异" if finding.confirmed else "待核实线索"}</small></div>'
            )
    if report.previous is not None:
        st.markdown("#### 修复前后")
        st.caption(report.repair_label)
        st.dataframe([
            {"核对": f"第 {item.attempt} 次", "结论": item.outcome_label,
             "报表金额": f"{item.claimed.display} {item.claimed.unit}",
             "有效金额": f"{item.calculated.display} {item.calculated.unit}" if item.calculated else "无法确定",
             "差额": f"{item.difference.display} {item.difference.unit}" if item.difference else "无法确定",
             "差异数": len(item.findings)} for item in (report.previous, current)
        ], hide_index=True, width="stretch")

    st.markdown("#### 资金流与差异")
    if graph is not None:
        graph(st, report)
    elif not current.graph_available:
        st.info("没有可重建的已保存资金流图，原回执结论仍保留。")
    else:
        st.caption("资金流图组件尚未接入，不能把技术准备版本作为完整报告交付。")
    if inconclusive:
        st.info("下一步：" + report.next_step)
    else:
        st.write(report.next_step)
    st.markdown("#### 保存报告")
    buttons = st.columns(3)
    with buttons[0]:
        st.download_button(
            "原 JSON 回执", receipt_json, f"attempt-{current.attempt}-receipt.json",
            "application/json", key=f"report-json-{current.receipt_hash}", use_container_width=True,
        )
    if exports is not None:
        for column, label, suffix, mime, export in (
            (buttons[1], "Word 报告", "docx",
             "application/vnd.openxmlformats-officedocument.wordprocessingml.document", exports[0]),
            (buttons[2], "PDF 报告", "pdf", "application/pdf", exports[1]),
        ):
            with column:
                render_export_download(st, report, label=label, suffix=suffix, mime=mime, export=export)
