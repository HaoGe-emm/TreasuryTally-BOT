from pathlib import Path

from streamlit.testing.v1 import AppTest

from app.user_guidance import chain_state_copy, explanation_preview, next_step, outcome_copy, short_explanation
from trust_receipt.models import PublicationChainStatus, VerificationOutcome

APP = Path(__file__).parents[2] / "app" / "streamlit_app.py"


def button(page, label):
    return next(item for item in page.button if item.label == label)


def practice(page):
    next(item for item in page.selectbox if item.label == "先选一份报表").set_value("加载契约测试示例").run()
    button(page, "整理核对范围").click().run()
    return page


def test_plain_outcomes_and_next_step_do_not_recast_unknown_as_failure():
    assert outcome_copy(VerificationOutcome.INCONCLUSIVE) == "暂时无法下结论"
    assert "证据" in next_step(VerificationOutcome.INCONCLUSIVE, 1)
    assert "修正报表" in next_step(VerificationOutcome.FAIL, 1)
    assert "不能再次补交" in next_step(VerificationOutcome.FAIL, 2)
    assert "另行授权发布" in next_step(VerificationOutcome.PASS, 1)


def test_ai_copy_is_brief_and_does_not_recompute_amounts():
    assert short_explanation("\n 金额 10000   保持原值\n") == "金额 10000 保持原值"
    assert len(short_explanation("解释" * 200)) == 181
    assert "原文不是中文" in explanation_preview("Differences require correction.")
    assert explanation_preview("报表少记一笔转账。") == "报表少记一笔转账。"


def test_submitted_is_not_presented_as_confirmed_or_publication_success():
    assert chain_state_copy(PublicationChainStatus.NOT_SUBMITTED) == "未提交"
    assert "待读回确认" in chain_state_copy(PublicationChainStatus.SUBMITTED)
    assert "读回一致" in chain_state_copy(PublicationChainStatus.CONFIRMED)
    assert "失败" in chain_state_copy(PublicationChainStatus.FAILED)


def test_first_screen_requires_an_actual_report_and_hides_technical_settings():
    page = AppTest.from_file(str(APP), default_timeout=20).run()
    assert not page.exception
    assert button(page, "整理核对范围").disabled
    assert not any(item.label == "开始核对" for item in page.button)
    assert all(item.proto.expanded is False for item in page.expander)
    assert any(item.label.startswith("高级设置") for item in page.expander)
    assert not any("TaskSpec" in item.label or "Attempt" in item.label for item in page.button)


def test_scope_remains_visible_and_requires_explicit_confirmation():
    page = practice(AppTest.from_file(str(APP), default_timeout=20).run())
    assert len(page.number_input) == 3
    assert any(item.label.startswith("核对哪种代币") for item in page.text_input)
    assert any(item.label.startswith("资金账户") for item in page.text_area)
    assert any(item.label.startswith("资助对象") for item in page.text_area)
    button(page, "确认范围，继续").click().run()  # noqa: RUF001
    assert "task" not in page.session_state
    assert any("任务未确认" in item.value for item in page.error)


def test_failed_drafting_does_not_silently_substitute_a_sample_scope(monkeypatch):
    page = AppTest.from_file(str(APP), default_timeout=20).run()
    next(item for item in page.selectbox if item.label == "先选一份报表").set_value("加载契约测试示例").run()

    def fail(*_args, **_kwargs):
        raise ValueError("test: model unavailable")

    monkeypatch.setattr(type(page.session_state["runtime"].workflow), "draft_task", fail)
    button(page, "整理核对范围").click().run()
    assert "candidate" not in page.session_state
    assert "task" not in page.session_state
    assert any("暂时无法整理核验范围" in item.value for item in page.error)
    assert not any("test: model unavailable" in item.value for item in page.error)


def test_latest_result_puts_next_step_before_evidence_and_keeps_one_main_action():
    page = practice(AppTest.from_file(str(APP), default_timeout=20).run())
    page.checkbox[1].check()
    button(page, "确认范围，继续").click().run()  # noqa: RUF001
    button(page, "开始核对").click().run()
    assert not page.exception
    assert any("按已确认差异修正报表" in item.value for item in page.markdown)
    assert any(item.label == "验证依据 / 技术详情" and not item.proto.expanded for item in page.expander)
    assert not any(item.label in {"查看完整 AI 说明", "查看资金流、完整事件与证据"} for item in page.expander)
    assert [item.label for item in page.button if item.proto.type == "primary"] == ["核对修正版（最后一次）"]  # noqa: RUF001
    assert button(page, "核对修正版（最后一次）").disabled  # noqa: RUF001


def test_ai_original_and_receipt_are_only_in_selected_technical_category():
    page = practice(AppTest.from_file(str(APP), default_timeout=20).run())
    page.checkbox[1].check()
    button(page, "确认范围，继续").click().run()  # noqa: RUF001
    button(page, "开始核对").click().run()
    execution = page.session_state["executions"][0]
    original = execution.explanation.summary
    assert not any(item.value == original for item in page.markdown)
    category = next(item for item in page.selectbox if item.label == "查看依据类别")
    category.set_value("AI 说明").run()
    assert not page.exception
    assert any(item.value == original for item in page.markdown)
    category = next(item for item in page.selectbox if item.label == "查看依据类别")
    category.set_value("回执与修复历史").run()
    assert not page.exception
    assert not any(item.value == original for item in page.markdown)
    assert len(page.session_state["executions"]) == 1
    assert page.session_state["executions"][0].receipt == execution.receipt
    assert any(execution.receipt.receipt_hash in item.value for item in page.json)
