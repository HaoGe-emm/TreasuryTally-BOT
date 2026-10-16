"""Moved reading notes stay reachable through the existing evidence entry."""

from types import SimpleNamespace

from streamlit.testing.v1 import AppTest

from tests.reporting.conftest import report_input
from trust_receipt.reporting import build_business_report


def evidence_harness():
    import streamlit as st

    from app.report_evidence import render_report_evidence

    render_report_evidence(
        st, st.session_state["runtime"], st.session_state["executions"], None,
        allow_actions=False, publish=None, report=st.session_state["report"],
    )


def test_existing_scope_evidence_entry_keeps_full_scope_and_reading_limits():
    item = report_input("insufficient-evidence-page")
    view = build_business_report(item.receipt, item.submission, fund_flow=item.fund_flow)
    page = AppTest.from_function(evidence_harness)
    page.session_state["runtime"] = SimpleNamespace(mode_label="offline-test", evidence_label="saved-test")
    page.session_state["task"] = item.receipt.task_spec
    page.session_state["executions"] = [SimpleNamespace(
        result=item.receipt.verification_result, evidence_diagnostics=(),
    )]
    page.session_state["report"] = view
    page.run()
    assert not page.exception
    assert len(page.expander) == 1 and page.expander[0].label == "验证依据 / 技术详情"
    captions = [element.value for element in page.caption]
    assert all(detail in captions for detail in (*view.limitations, view.notice, *view.current.uncertainties))
    assert any(view.scope.token.full in detail for detail in captions)
    assert all(any(account.full in detail for detail in captions) for account in view.scope.treasuries)
    assert all(any(account.full in detail for detail in captions) for account in view.scope.recipients)
