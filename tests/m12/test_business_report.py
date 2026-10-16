"""Business-only presentation; test exports below are explicit byte doubles."""
# ruff: noqa: RUF001

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from tests.reporting.conftest import report_input
from tests.reporting.test_evidence_reasons import SECRET, saved_incomplete
from trust_receipt.reporting import build_business_report

ROOT = Path(__file__).parents[2]


def harness():
    import streamlit as st

    from app.business_report import render_business_report

    render_business_report(
        st, st.session_state["report"], graph=st.session_state.get("graph"),
        exports=st.session_state.get("exports"),
        receipt_json=st.session_state.get("receipt_json", "original-json-test-bytes"),
    )


def page_for(report, **kwargs):
    page = AppTest.from_function(harness, default_timeout=15)
    page.session_state["report"] = report
    for key, value in kwargs.items():
        page.session_state[key] = value
    return page.run()


@pytest.mark.parametrize("case", sorted(path.stem for path in (ROOT / "fixtures/m1/cases").glob("*.json")))
def test_each_verdict_preserves_exact_business_amounts_without_technical_directory(case):
    item = report_input(case)
    view = build_business_report(item.receipt, item.submission, fund_flow=item.fund_flow, source_mode="fixture")
    page = page_for(view)
    assert not page.exception
    assert [metric.value for metric in page.metric] == [
        view.current.claimed.display,
        view.current.calculated.display if view.current.calculated else "无法确定",
        view.current.difference.display if view.current.difference else "无法确定",
    ]
    assert not page.expander and not page.json
    assert len(page.get("download_button")) == 1
    assert not any("Offline explanation" in item.value for item in page.markdown)


def test_pass_does_not_render_empty_problem_cards():
    item = report_input("correct-basic")
    view = build_business_report(item.receipt, item.submission, fund_flow=item.fund_flow)
    assert view.outcome.value == "PASS"
    page = page_for(view)
    assert not page.exception
    assert not any(item.value == "#### 需要处理的差异" for item in page.markdown)


def test_inconclusive_reason_is_visible_and_separate_from_precision_notice():
    item = report_input("insufficient-evidence-page")
    view = build_business_report(item.receipt, item.submission, fund_flow=item.fund_flow)
    # Explicit view double isolates UI hierarchy; this is not live RPC evidence.
    reason = "已保存的 RPC 诊断表明请求超时，未取得完整参考数据；不能认定报表有错。"
    precision = "没有唯一可信的代币精度，核验金额以最小单位显示。"
    current = view.current.model_copy(update={"uncertainties": (reason, precision)})
    view = view.model_copy(update={"current": current, "next_step": "检查节点可用性后，再主动决定是否核对。"})
    before = view.model_dump_json()
    page = page_for(view)
    assert not page.exception and not page.expander
    assert any(element.value == "#### 为什么暂不能判断" for element in page.markdown)
    assert page.warning[0].value == reason
    assert not any(element.value == precision for element in page.caption)
    assert any(element.value == "下一步：" + view.next_step for element in page.info)
    assert len(page.get("download_button")) == 1
    assert view.model_dump_json() == before


def test_business_surface_omits_implementation_notes_but_keeps_scope_and_units():
    item = report_input("correct-basic")
    view = build_business_report(item.receipt, item.submission, fund_flow=item.fund_flow)
    page = page_for(view)
    captions = [element.value for element in page.caption]
    assert any(value.startswith("核对范围：Sepolia") and view.scope.token.short in value
               and f"区块 {view.scope.start_block:,} 至 {view.scope.end_block:,}" in value for value in captions)
    assert view.current.claimed.unit in captions
    assert view.notice not in captions
    assert not any(value in captions for value in view.limitations)
    assert not any(value.startswith(("资金账户：", "资助对象：", "核验资产：")) for value in captions)


def test_inconclusive_missing_safe_reason_uses_fixed_fallback_not_amount_hint():
    item = report_input("insufficient-evidence-page")
    view = build_business_report(item.receipt, item.submission, fund_flow=item.fund_flow)
    current = view.current.model_copy(update={
        "uncertainties": (), "difference_reason": "private-url-or-raw-provider-error",
    })
    page = page_for(view.model_copy(update={"current": current}))
    assert not page.exception
    assert page.warning[0].value == "已保存证据不足，暂时不能判断报表是否符合范围。"
    assert not any("private-url" in element.value for element in page.warning)


@pytest.mark.parametrize("code", ["UNAVAILABLE", "HISTORICAL_DATA_UNAVAILABLE", None])
def test_saved_safe_mapper_reason_is_primary_even_without_recovered_flow(code):
    item, receipt = saved_incomplete(code)
    view = build_business_report(receipt, item.submission)
    page = page_for(view)
    assert not page.exception
    assert page.warning[0].value == view.current.uncertainties[0]
    assert [metric.value for metric in page.metric][1:] == ["无法确定", "无法确定"]
    assert view.outcome.value == "INCONCLUSIVE" and view.current.receipt_hash == receipt.receipt_hash
    assert not any(SECRET in element.value for element in (*page.warning, *page.caption, *page.info))
    assert not any("精度" in element.value for element in page.warning)


def test_many_same_kind_findings_are_summarized_without_mutating_report():
    item = report_input()
    view = build_business_report(item.receipt, item.submission, fund_flow=item.fund_flow)
    repeated = view.current.model_copy(update={"findings": (view.current.findings[0],) * 200})
    view = view.model_copy(update={"current": repeated})
    page = page_for(view)
    assert not page.exception
    assert len(view.current.findings) == 200
    bodies = [element.proto.body for element in page.get("html")]
    assert sum("finding-card" in body for body in bodies) == 1
    assert any("200 条" in body for body in bodies)


def test_export_is_lazy_and_cached_without_new_verification():
    item = report_input()
    view = build_business_report(item.receipt, item.submission, fund_flow=item.fund_flow)
    calls = []

    def export(_view):
        calls.append(_view.current.receipt_hash)
        return b"explicit-test-output-not-a-real-docx"

    page = page_for(view, exports=(export, export))
    assert not calls
    next(item for item in page.button if item.label == "生成Word 报告").click().run()
    assert not page.exception and len(calls) == 1
    page.run()
    assert len(calls) == 1
    assert len(page.get("download_button")) == 2
