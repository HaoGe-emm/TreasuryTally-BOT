"""Offline scope recovery; no paid model, RPC, browser or automatic execution."""

from types import SimpleNamespace

import pytest
from streamlit.testing.v1 import AppTest

from app.scope_draft import ERROR_COPY, blank_manual_candidate
from tests.m12.test_conversion_page_flow import button, uploaded_page
from trust_receipt.agents import TaskField
from trust_receipt.agents.task_draft import TASK_DRAFT_DEADLINE_SECONDS, TaskDraftError


def scope_harness():
    import streamlit as st

    from app.scope_draft import render_scope_actions

    request = st.text_area("范围说明", key="scope-request")
    render_scope_actions(st, st.session_state["runtime"], request,
                         valid_report=st.session_state["valid"])


def scope_page(workflow, *, valid=True):
    page = AppTest.from_function(scope_harness)
    page.session_state["runtime"] = SimpleNamespace(workflow=workflow)
    page.session_state["valid"] = valid
    page.session_state["provider"] = "DeepSeek 真实模型"
    page.session_state["scope-request"] = "保留用户填写的链、账户与区块说明"
    return page.run()


@pytest.mark.parametrize("kind", tuple(ERROR_COPY))
def test_typed_error_has_distinct_safe_copy_and_preserves_request_without_retry(kind):
    calls = []

    def draft(request):
        calls.append(request)
        raise TaskDraftError(kind)

    page = scope_page(SimpleNamespace(draft_task=draft))
    request = page.session_state["scope-request"]
    button(page, "整理核对范围").click().run()
    assert not page.exception and len(calls) == 1
    assert page.error[0].value == ERROR_COPY[kind]
    assert page.session_state["draft_error"] == kind
    assert page.session_state["scope-request"] == request
    assert "candidate" not in page.session_state and "task" not in page.session_state
    page.run()
    assert len(calls) == 1
    assert not button(page, "重试整理核对范围").disabled
    assert any(str(TASK_DRAFT_DEADLINE_SECONDS) in item.value and "不自动重试" in item.value
               for item in page.caption)


def test_unknown_exception_is_not_stored_or_displayed():
    def draft(_):
        raise RuntimeError("https://private-rpc.invalid?api_key=secret-test-value")

    page = scope_page(SimpleNamespace(draft_task=draft))
    button(page, "整理核对范围").click().run()
    assert not page.exception
    assert page.error[0].value == ERROR_COPY["unavailable"]
    assert page.session_state["draft_error"] == "unavailable"
    assert "secret-test-value" not in str(page.session_state._state.filtered_state)
    assert not any("private-rpc" in item.value for item in page.error)


def test_raw_schema_failure_is_classified_without_echoing_model_payload():
    def draft(_):
        from trust_receipt.agents import TaskSpecCandidate

        return TaskSpecCandidate.model_validate({"candidate_id": "private-model-payload"})

    page = scope_page(SimpleNamespace(draft_task=draft))
    button(page, "整理核对范围").click().run()
    assert not page.exception
    assert page.error[0].value == ERROR_COPY["invalid_output"]
    assert "private-model-payload" not in str(page.session_state._state.filtered_state)


def test_blank_manual_candidate_has_no_report_or_fixture_scope():
    candidate = blank_manual_candidate()
    assert all(getattr(candidate, field.value) is None for field in TaskField)
    assert set(candidate.missing_fields) == set(TaskField)
    assert not candidate.ready_for_confirmation
    assert candidate.max_records == 200
    assert candidate.candidate_id != blank_manual_candidate().candidate_id


def test_invalid_report_disables_manual_and_model_paths():
    calls = []
    page = scope_page(SimpleNamespace(draft_task=lambda request: calls.append(request)), valid=False)
    assert button(page, "直接填写核验范围").disabled
    assert button(page, "整理核对范围").disabled
    assert not calls and "candidate" not in page.session_state


def test_explicit_retry_then_success_requires_later_confirmation():
    calls = []
    candidate = blank_manual_candidate()

    def draft(request):
        calls.append(request)
        if len(calls) == 1:
            raise TaskDraftError("timeout")
        return candidate

    page = scope_page(SimpleNamespace(draft_task=draft))
    button(page, "整理核对范围").click().run()
    button(page, "重试整理核对范围").click().run()
    assert not page.exception and len(calls) == 2
    assert page.session_state["candidate"] == candidate
    assert "draft_error" not in page.session_state and "task" not in page.session_state
    page.text_area[0].set_value("不同的范围请求").run()
    assert "candidate" not in page.session_state
    assert len(calls) == 2


def manual_page(monkeypatch):
    page, _uploads = uploaded_page(monkeypatch)
    calls = []

    def draft(request):
        calls.append(request)
        raise TaskDraftError("timeout")

    monkeypatch.setattr(page.session_state["runtime"].workflow, "draft_task", draft)
    return page, calls


def fill_manual(page, *, chain=11_155_111, start=1000, end=1010, duplicate=False):
    next(item for item in page.number_input if item.label.startswith("核对哪条链")).set_value(chain)
    next(item for item in page.text_input if item.label.startswith("核对哪种代币")).set_value("0x" + "0" * 36 + "1000")
    next(item for item in page.number_input if item.label.startswith("起始区块")).set_value(start)
    next(item for item in page.number_input if item.label.startswith("结束区块")).set_value(end)
    treasury = "0x" + "0" * 36 + "2001"
    next(item for item in page.text_area if item.label.startswith("资金账户")).set_value(
        treasury + "\n" + (treasury if duplicate else "0x" + "0" * 36 + "2002")
    )
    next(item for item in page.text_area if item.label.startswith("资助对象")).set_value(
        "0x" + "0" * 36 + "3001" + "\n" + "0x" + "0" * 36 + "3002"
    )
    next(item for item in page.checkbox if item.label.startswith("排除资金账户")).check()


def test_fullpage_timeout_retains_report_then_manual_is_strict_and_never_calls_model(monkeypatch):
    page, calls = manual_page(monkeypatch)
    request = "手工输入下一步要确认的范围并保持上传报表。"
    next(item for item in page.text_area if item.label == "说明要核对的范围").set_value(request).run()
    original = page.session_state["uploaded_service"]
    original_hash = page.session_state["uploaded_report_hash"]
    button(page, "整理核对范围").click().run()
    assert len(calls) == 1 and page.session_state["scope-request"] == request
    button(page, "直接填写核验范围").click().run()
    assert not page.exception and len(calls) == 1
    assert page.session_state["uploaded_service"] is original
    assert page.session_state["uploaded_report_hash"] == original_hash
    assert page.session_state["candidate"].token_address is None
    assert page.session_state["candidate"].treasury_addresses is None
    assert page.session_state["candidate"].start_block is None
    assert "task" not in page.session_state
    fill_manual(page)
    button(page, "确认范围，继续").click().run()  # noqa: RUF001
    assert "task" not in page.session_state  # Explicit checkbox still required.
    next(item for item in page.checkbox if item.label.startswith("我已核对以上")).check()
    button(page, "确认范围，继续").click().run()  # noqa: RUF001
    assert not page.exception and len(calls) == 1
    assert page.session_state["task"].start_block == 1000
    assert not page.session_state["executions"]
    assert not button(page, "开始核对").disabled  # Not clicked: no model/RPC/attempt execution.


@pytest.mark.parametrize("changes", [
    {"chain": 1}, {"start": 1011, "end": 1000}, {"duplicate": True},
])
def test_invalid_manual_scope_never_creates_task_or_calls_model(monkeypatch, changes):
    page, calls = manual_page(monkeypatch)
    button(page, "直接填写核验范围").click().run()
    fill_manual(page, **changes)
    next(item for item in page.checkbox if item.label.startswith("我已核对以上")).check()
    button(page, "确认范围，继续").click().run()  # noqa: RUF001
    assert not page.exception and not calls
    assert "task" not in page.session_state
    assert any("任务未确认" in item.value for item in page.error)


def test_blank_manual_form_still_rejects_missing_fields_even_if_checkbox_is_checked(monkeypatch):
    page, calls = manual_page(monkeypatch)
    button(page, "直接填写核验范围").click().run()
    next(item for item in page.checkbox if item.label.startswith("我已核对以上")).check()
    button(page, "确认范围，继续").click().run()  # noqa: RUF001
    assert not page.exception and not calls
    assert "task" not in page.session_state
    assert page.session_state["candidate"].treasury_addresses is None


def test_report_change_clears_failed_candidate_not_user_text(monkeypatch):
    page, uploads = uploaded_page(monkeypatch)

    def draft(_):
        raise TaskDraftError("timeout")

    monkeypatch.setattr(page.session_state["runtime"].workflow, "draft_task", draft)
    request = "明确填写并在下一步确认原核验范围。"
    next(item for item in page.text_area if item.label == "说明要核对的范围").set_value(request).run()
    button(page, "整理核对范围").click().run()
    uploads["first"].payload = b"not-a-valid-report"
    page.run()
    assert not page.exception
    assert "candidate" not in page.session_state and "draft_error" not in page.session_state
    assert page.session_state["scope-request"] == request
    assert button(page, "直接填写核验范围").disabled
