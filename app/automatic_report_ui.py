"""Automatic intake presentation, injected use cases own model and persistence."""

from __future__ import annotations

from pathlib import Path

from app.report_identification_state import report_input_identity, track_report_input

COMMON_FIELDS = {
    "chain_id": "报表使用的链编号",
    "token_address": "报表使用的代币合约地址",
    "token_decimals": "报表金额的代币精度",
}
FIELD_LABELS = {
    **COMMON_FIELDS,
    "transaction_hash": "交易哈希", "log_index": "日志序号",
    "block_number": "区块号", "from_address": "付款地址", "to_address": "收款地址",
    "amount_base_units_or_amount": "金额与明确单位", "amount_unit": "金额单位",
}


def render_automatic_report(
    st, uploaded, *, directory: Path, namespace: str, provider: str,
    recognizer, recognize, retain, on_change=None,
) -> bytes | None:
    """A ready, privately retained report is input, never scope or verification consent."""
    original = uploaded.getvalue()
    filename = uploaded.name
    source = report_input_identity(original, filename, provider, {}, None)
    track_report_input(st.session_state, namespace, source)
    prefix = f"{namespace}:recognition:"
    requested = st.session_state.get(prefix + "problem_fields", ())
    constants = {
        field: st.session_state.get(f"{prefix}answer:{source}:{field}", "").strip()
        for field in requested if field in COMMON_FIELDS
    }
    constants = {key: value for key, value in constants.items() if value}
    unit = st.session_state.get(f"{prefix}answer:{source}:amount_unit") or None
    identity = report_input_identity(original, filename, provider, constants, unit)
    cache = st.session_state.get(prefix + "result")
    if cache is None or cache[0] != identity:
        st.session_state.pop(prefix + "retained", None)
        if on_change is not None:
            on_change()
        with st.spinner("正在读取报表并识别字段…"):
            result = recognize(
                original, filename, recognizer, constants=constants, amount_unit=unit,
                previous=cache[1] if cache is not None else None,
            )
        st.session_state[prefix + "result"] = (identity, result)
    else:
        result = cache[1]

    st.write(f"文件：{filename}")
    requested = tuple(dict.fromkeys((*requested, *(
        field for field in result.missing_fields if field in COMMON_FIELDS
    ))))
    if "amount_unit" in result.clarifications and "amount_unit" not in requested:
        requested = (*requested, "amount_unit")
    st.session_state[prefix + "problem_fields"] = requested
    if requested:
        st.caption("只需补充以下未明确的条件；数值请以原报表为准，不会替你猜填。")
        for field in requested:
            key = f"{prefix}answer:{source}:{field}"
            if field == "amount_unit":
                st.selectbox(
                    "这列金额使用哪种单位？", ("", "base", "token"), key=key,
                    format_func=lambda value: {"": "请选择原表的金额单位", "base": "最小单位整数",
                                              "token": "代币单位十进制"}[value],
                )
            else:
                st.text_input(COMMON_FIELDS[field], key=key)
    for issue in result.issues:
        st.error(issue)
    for clarification in result.clarifications:
        if clarification != "amount_unit":
            st.warning(clarification)
    unfillable = tuple(field for field in result.missing_fields if field not in requested)
    if unfillable:
        st.warning("请在原文件补齐：" + "、".join(FIELD_LABELS.get(field, field) for field in unfillable))
    for warning in result.warnings:
        st.caption(warning)
    if not result.ready:
        st.info("报表尚未识别完整，不能继续确认范围或核对；不会使用旧报表或样例替代。")
        if st.button("重新识别这份报表", key=prefix + "retry", use_container_width=True):
            st.session_state.pop(prefix + "result", None)
            st.session_state.pop(prefix + "retained", None)
            st.rerun()
        return None

    retained = st.session_state.get(prefix + "retained")
    if retained is None or retained[0] != identity:
        try:
            payload = retain(original, result, directory)
        except (ValueError, OSError):
            st.error("报表私有留档失败，尚不能继续。请保留原文件并联系维护者。")
            return None
        st.session_state[prefix + "retained"] = (identity, payload)
    else:
        payload = retained[1]
    report = result.report
    derived = result.conversion.derived_fields if result.conversion else ()
    st.write(f"已读取 {len(report.transfers)} 条明细")
    total_source = "明细派生，非原作者声明" if "claimed_total_base_units" in derived else "原报表声明"
    count_source = "明细派生，非原作者声明" if "claimed_count" in derived else "原报表声明"
    st.write(f"总额（最小单位）：{report.claimed_total_base_units} · {total_source}")
    st.write(f"声明笔数：{report.claimed_count} · {count_source}")
    st.caption("读取与识别不代表链上核验通过，也不认证报表作者；接下来仍需确认范围。")
    with st.expander("查看报表明细与读取来源"):
        st.json(report.model_dump(mode="json"))
        st.code(result.original_hash, language=None)
        st.caption(f"读取方式：{result.recognition_mode} · 原文件和识别来源仅私有留档")
        if result.conversion:
            st.json({"字段来源": result.conversion.field_mapping,
                     "用户补充": result.conversion.constants, "派生汇总字段": derived})
    return payload
