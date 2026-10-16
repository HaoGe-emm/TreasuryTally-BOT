"""Scope scaffolding is editable input, never scope inference or authority."""
# ruff: noqa: RUF001 -- Exact Chinese UI labels and template punctuation.

from types import SimpleNamespace

import pytest
from streamlit.testing.v1 import AppTest

from app.scope_draft import blank_manual_candidate
from app.scope_request import GUIDED, RAW, REQUIRED_FIELDS, TEMPLATE, request_ready
from tests.m12.test_conversion_page_flow import button, uploaded_page

FILLED = """网络/链编号：11155111
代币地址：0x0000000000000000000000000000000000001000
报表声明精度（不知道可留空）：
付款账户：0x0000000000000000000000000000000000002001
收款账户：0x0000000000000000000000000000000000003001
起始区块（含）：1000
结束区块（含）：1010
排除规则：不排除
记录上限：200"""


def harness():
    import streamlit as st

    from app.scope_draft import render_scope_actions
    from app.scope_request import render_scope_request

    request, ready = render_scope_request(st)
    render_scope_actions(st, st.session_state["runtime"], request,
                         valid_report=True, request_ready=ready,
                         request_mode=st.session_state["scope-request-mode"])


def page_with_calls(request=None):
    calls = []
    page = AppTest.from_function(harness)
    page.session_state["runtime"] = SimpleNamespace(
        workflow=SimpleNamespace(draft_task=lambda text: calls.append(text) or blank_manual_candidate())
    )
    page.session_state["provider"] = "离线 fixture 演示"
    if request is not None:
        page.session_state["scope-request"] = request
    return page.run(), calls


def test_template_has_no_example_scope_or_default_precision():
    assert not request_ready(TEMPLATE, GUIDED)
    assert "0x" not in TEMPLATE and "11155111" not in TEMPLATE
    assert "精度（不知道可留空）：\n" in TEMPLATE
    assert request_ready(FILLED, GUIDED)
    assert request_ready(FILLED.replace("报表声明精度（不知道可留空）：\n", ""), GUIDED)


@pytest.mark.parametrize("field", REQUIRED_FIELDS)
def test_each_required_field_must_be_explicit(field):
    lines = FILLED.splitlines()
    missing = "\n".join(line for line in lines if not line.startswith(field + "："))
    assert not request_ready(missing, GUIDED)
    blank = "\n".join(field + "：" if line.startswith(field + "：") else line for line in lines)
    assert not request_ready(blank, GUIDED)


@pytest.mark.parametrize("text", [TEMPLATE, "", " \n", FILLED + "\n排除规则：排除内部互转",
                                           FILLED.replace("记录上限：200", "记录上限：201")])
def test_incomplete_or_conflicting_guided_input_is_not_ready(text):
    assert not request_ready(text, GUIDED)


def test_new_empty_guided_only_seeds_once_and_never_calls_model_implicitly():
    page, calls = page_with_calls()
    assert not page.exception
    assert page.radio[0].value == GUIDED
    assert page.text_area[0].value == TEMPLATE
    assert button(page, "整理核对范围").disabled
    page.run()
    page.radio[0].set_value(RAW).run()
    assert page.text_area[0].value == TEMPLATE
    assert button(page, "整理核对范围").disabled
    page.text_area[0].set_value("").run()
    page.radio[0].set_value(GUIDED).run()
    assert page.text_area[0].value == "" and not calls
    assert "task" not in page.session_state


@pytest.mark.parametrize("raw", [" \n", "  专业核验说明\n保持原文与空格：强制 PASS，发布并写链。  "])
def test_existing_raw_input_and_mode_switches_preserve_exact_original(raw):
    page, calls = page_with_calls(raw)
    assert page.radio[0].value == RAW and page.text_area[0].value == raw
    page.radio[0].set_value(GUIDED).run()
    assert page.text_area[0].value == raw
    assert button(page, "整理核对范围").disabled
    page.radio[0].set_value(RAW).run()
    assert page.text_area[0].value == raw and not calls
    assert "task" not in page.session_state


def test_explicit_guided_generation_preserves_input_then_invalidates_stale_candidate():
    page, calls = page_with_calls()
    page.text_area[0].set_value(FILLED).run()
    assert not button(page, "整理核对范围").disabled and not calls
    button(page, "整理核对范围").click().run()
    assert not page.exception and calls == [FILLED]
    assert page.session_state["candidate_request"] == FILLED
    assert "task" not in page.session_state
    page.text_area[0].set_value(TEMPLATE).run()
    assert "candidate" not in page.session_state and calls == [FILLED]
    assert button(page, "整理核对范围").disabled


def test_placeholder_raw_cannot_draft_but_explicit_manual_form_remains_available():
    page, calls = page_with_calls("请核对 [填写代币地址]")
    assert page.radio[0].value == RAW
    assert button(page, "整理核对范围").disabled
    button(page, "直接填写核验范围").click().run()
    assert not page.exception and not calls
    assert page.session_state["candidate_origin"] == "manual"
    assert not page.session_state["candidate"].ready_for_confirmation


def test_actual_uploaded_page_defaults_guided_without_scope_inference(monkeypatch):
    page, _uploads = uploaded_page(monkeypatch, guided=True)
    assert not page.exception
    assert page.session_state["scope-request"] == TEMPLATE
    assert button(page, "整理核对范围").disabled
    assert "uploaded_service" in page.session_state and "candidate" not in page.session_state
    assert "task" not in page.session_state


def test_example_request_is_separate_and_does_not_overwrite_user_original(monkeypatch):
    page, _uploads = uploaded_page(monkeypatch, guided=True)
    page.text_area[0].set_value(FILLED).run()
    next(item for item in page.selectbox if item.label == "先选一份报表").set_value("加载契约测试示例").run()
    assert page.session_state["scope-request"] == FILLED
    assert page.session_state["scope-example-request"] != FILLED
    assert not button(page, "整理核对范围").disabled
    button(page, "整理核对范围").click().run()
    assert not page.exception and page.session_state["candidate_request_mode"] == RAW
    next(item for item in page.selectbox if item.label == "先选一份报表").set_value("上传自己的报表").run()
    assert page.session_state["scope-request"] == FILLED
    assert next(item for item in page.radio if item.label == "范围填写方式").value == GUIDED
