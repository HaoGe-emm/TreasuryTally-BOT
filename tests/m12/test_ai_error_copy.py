"""Untrusted AI failures must not be echoed through the real evidence renderer."""
# ruff: noqa: RUF001 -- Exact Chinese UI copy is the security regression contract.

from types import SimpleNamespace

import pytest
from pydantic import BaseModel, ValidationError
from streamlit.testing.v1 import AppTest

SECRET = "SYNTHETIC_ONLY_ERROR_INPUT_NOT_A_REAL_SECRET"
FALLBACK = "AI 说明暂不可用，核对结果与原回执不受影响。"
SAFE_COPY = {
    "RESULT_EXPLANATION_UNAVAILABLE": "AI 结果说明暂不可用，核对结果与原回执不受影响。",
    "FOLLOW_UP_ADVICE_UNAVAILABLE": "AI 处理建议暂不可用，核对结果与原回执不受影响。",
    "Restored locally; AI text was not regenerated.": "已恢复核对记录，AI 说明未重新生成。",
}


def evidence_harness():
    import streamlit as st

    from app.report_evidence import render_report_evidence

    render_report_evidence(st, None, st.session_state["executions"], None,
                           allow_actions=False, publish=None)


def error_page(*errors):
    page = AppTest.from_function(evidence_harness)
    page.session_state["report-evidence-section"] = "AI 说明"
    page.session_state["executions"] = [SimpleNamespace(
        explanation=None, follow_up=None, ai_errors=(error,),
    ) for error in errors]
    return page.run()


def visible_text(page):
    return "\n".join(str(item.value) for kind in
                     ("warning", "error", "info", "caption", "markdown", "code", "json")
                     for item in page.get(kind))


def validation_failure_text():
    class IntegerOutput(BaseModel):
        value: int

    try:
        IntegerOutput.model_validate({"value": SECRET})
    except ValidationError as error:
        return f"Follow-up advice rejected: {error}"
    raise AssertionError("synthetic invalid output unexpectedly accepted")


@pytest.mark.parametrize("error", [
    validation_failure_text(),
    f"Result explanation rejected: provider https://private.invalid/?api_key={SECRET}",
    f"RESULT_EXPLANATION_UNAVAILABLE\n{SECRET}",
    f"FOLLOW_UP_ADVICE_UNAVAILABLE: {SECRET}",
    "Unrecognized legacy failure", "", None, [], {"unexpected": SECRET},
    " RESULT_EXPLANATION_UNAVAILABLE", "FOLLOW_UP_ADVICE_UNAVAILABLE ",
])
def test_unknown_and_validation_input_never_reach_actual_ui(error):
    page = error_page(error)
    assert not page.exception
    assert [item.value for item in page.warning] == [FALLBACK]
    assert SECRET not in visible_text(page)
    assert "private.invalid" not in visible_text(page)
    assert "input_value" not in visible_text(page)
    assert page.session_state["executions"][0].ai_errors == (error,)  # Read-only projection.


@pytest.mark.parametrize("code,copy", SAFE_COPY.items())
def test_exact_safe_contract_and_restore_notice_remain_visible(code, copy):
    page = error_page(code)
    assert not page.exception
    assert [item.value for item in page.warning] == [copy]


def test_history_selector_applies_same_boundary_to_both_attempts():
    page = error_page(validation_failure_text(), "FOLLOW_UP_ADVICE_UNAVAILABLE")
    assert [item.value for item in page.warning] == [SAFE_COPY["FOLLOW_UP_ADVICE_UNAVAILABLE"]]
    page.selectbox[0].set_value(1).run()
    assert not page.exception
    assert [item.value for item in page.warning] == [FALLBACK]
    assert SECRET not in visible_text(page)
    assert len(page.session_state["executions"]) == 2


def test_valid_explanation_and_advice_are_not_hidden_by_error_projection():
    page = AppTest.from_function(evidence_harness)
    page.session_state["report-evidence-section"] = "AI 说明"
    advice = {"outcome": "INCONCLUSIVE", "suggestions": []}
    page.session_state["executions"] = [SimpleNamespace(
        explanation=SimpleNamespace(summary="请先核查独立证据来源。"),
        follow_up=SimpleNamespace(model_dump=lambda **_kwargs: advice), ai_errors=(),
    )]
    page.run()
    assert not page.exception and not page.warning
    assert "请先核查独立证据来源。" in visible_text(page)
    assert any("INCONCLUSIVE" in str(item.value) for item in page.json)
