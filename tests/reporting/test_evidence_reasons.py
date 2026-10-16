"""Saved-receipt cause projection; never diagnose from free text or precision."""
# ruff: noqa: RUF001

import pytest

from tests.reporting.conftest import report_input
from trust_receipt.hashing import receipt_hash
from trust_receipt.models import EvidenceSource
from trust_receipt.reporting import build_business_report
from trust_receipt.reporting.evidence_reasons import inconclusive_explanation
from trust_receipt.reporting.layout import report_sections

SECRET = "API_KEY=never-export https://user:password@rpc.invalid/private?token=secret"


def saved_incomplete(code, *, source="rpc", complete=False):
    item = report_input("insufficient-evidence-page")
    descriptor = item.receipt.verification_result.reference_sources[0].model_copy(update={
        "source": EvidenceSource(source), "complete": complete,
        "source_id": "private-source-id", "details": {"error_code": code, "error": SECRET, "uri": SECRET},
    })
    result = item.receipt.verification_result.model_copy(update={
        "reference_complete": False, "evidence_sufficient": False,
        "reference_sources": (descriptor,), "inconclusive_reason": SECRET,
    })
    draft = item.receipt.model_copy(update={"verification_result": result})
    receipt = draft.model_copy(update={"receipt_hash": receipt_hash(draft)})
    return item, receipt


@pytest.mark.parametrize(("code", "phrase"), [
    ("HISTORICAL_DATA_UNAVAILABLE", "无法提供所选区块的历史转账证据"),
    ("TIMEOUT", "读取超时"), ("UNAVAILABLE", "数据源暂不可用"),
    ("WRONG_NETWORK", "网络与已确认任务不一致"), ("UNCONFIRMED_RANGE", "尚未达到要求的确认数"),
    ("INVALID_RESPONSE", "事件格式无法验证"), ("INVALID_OR_UNAVAILABLE", "读取失败或返回内容无法使用"),
])
def test_defined_code_projects_same_safe_note_with_or_without_snapshot(code, phrase):
    item, receipt = saved_incomplete(code)
    original = receipt.model_dump_json()
    for flow in (item.fund_flow, None):
        view = build_business_report(receipt, item.submission, fund_flow=flow)
        assert phrase in view.current.uncertainties[0]
        assert "服务失败" in view.current.uncertainties[0]
        if flow is None:
            assert "没有唯一可信的代币精度" in view.current.uncertainties[1]
        assert view.current.receipt_hash == receipt.receipt_hash
        assert view.outcome.value == "INCONCLUSIVE"
        assert view.current.calculated is None and view.current.difference is None
        notes = next(s for s in report_sections(view) if s.title == "明确不可确定项")
        assert notes.paragraphs == view.current.uncertainties
        assert SECRET not in view.model_dump_json()
        assert "rpc.invalid" not in view.model_dump_json()
        assert "private-source-id" not in view.model_dump_json()
    assert receipt.model_dump_json() == original


@pytest.mark.parametrize("code", [None, "NEW_CODE", "timeout", SECRET, "TIMEOUT " + SECRET, 1, True, [], {}])
def test_unknown_or_untrusted_code_never_guesses_a_cause(code):
    item, receipt = saved_incomplete(code)
    view = build_business_report(receipt, item.submission)
    note = view.current.uncertainties[0]
    assert "证据来源未完成，需查看诊断" in note
    assert "读取超时" not in note and "数据源暂不可用" not in note
    assert "API_KEY" not in view.model_dump_json() and "rpc.invalid" not in view.model_dump_json()


@pytest.mark.parametrize(("source", "complete"), [("blockscout", False), ("rpc", True)])
def test_supplementary_or_complete_source_cannot_claim_primary_rpc_error(source, complete):
    item, receipt = saved_incomplete("TIMEOUT", source=source, complete=complete)
    view = build_business_report(receipt, item.submission)
    assert "读取超时" not in view.current.uncertainties[0]
    assert "需查看诊断" in view.current.uncertainties[0]


def test_multiple_saved_causes_are_deduplicated_in_one_primary_note():
    _, receipt = saved_incomplete("UNAVAILABLE")
    result = receipt.verification_result
    source = result.reference_sources[0]
    timeout = source.model_copy(update={"details": {"error_code": "TIMEOUT", "error": SECRET}})
    result = result.model_copy(update={"reference_sources": (source, source, timeout)})
    note = inconclusive_explanation(result)
    assert note.count("数据源暂不可用") == 1 and note.count("读取超时") == 1
    assert SECRET not in note


def test_missing_saved_sources_uses_unknown_not_freeform_reason():
    item, receipt = saved_incomplete("TIMEOUT")
    result = receipt.verification_result.model_copy(update={"reference_sources": ()})
    draft = receipt.model_copy(update={"verification_result": result})
    receipt = draft.model_copy(update={"receipt_hash": receipt_hash(draft)})
    view = build_business_report(receipt, item.submission)
    assert "需查看诊断" in view.current.uncertainties[0] and SECRET not in view.model_dump_json()


@pytest.mark.parametrize("case", ["correct-basic", "missing-transfer-vertical-slice"])
def test_complete_verdicts_ignore_stale_supplementary_diagnostics(case):
    item = report_input(case)
    result = item.receipt.verification_result
    sources = tuple(s.model_copy(update={"details": {
        "error_code": "TIMEOUT", "supplementary_status": "DEGRADED", "error": SECRET,
    }}) for s in result.reference_sources)
    result = result.model_copy(update={"reference_sources": sources})
    assert inconclusive_explanation(result) is None
    draft = item.receipt.model_copy(update={"verification_result": result})
    receipt = draft.model_copy(update={"receipt_hash": receipt_hash(draft)})
    view = build_business_report(receipt, item.submission, fund_flow=item.fund_flow)
    assert view.outcome == item.receipt.verification_result.outcome
    assert not any("需查看诊断" in note or "读取超时" in note for note in view.current.uncertainties)


def test_complete_empty_terminal_page_remains_pass_not_rpc_unavailable():
    def empty(fixture):
        return fixture.model_copy(update={
            "reference": fixture.reference.model_copy(update={"transfers": ()}),
            "submission": fixture.submission.model_copy(update={
                "transfers": (), "claimed_count": 0, "claimed_total_base_units": "0",
            }),
        })

    item = report_input("correct-basic", transform=empty)
    view = build_business_report(item.receipt, item.submission, fund_flow=item.fund_flow)
    assert view.outcome.value == "PASS"
    assert view.current.calculated.base_units == "0" and view.current.calculated_count == 0
    assert not any("数据源暂不可用" in note or "需查看诊断" in note for note in view.current.uncertainties)
