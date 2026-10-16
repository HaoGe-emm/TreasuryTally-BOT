from pathlib import Path

from streamlit.testing.v1 import AppTest


def button(page, label):
    return next(item for item in page.button if item.label == label)


def test_page_history_drilldown_and_next_manual_choice():
    page = AppTest.from_file(str(Path(__file__).parents[2] / "app" / "streamlit_app.py"), default_timeout=20).run()
    next(item for item in page.selectbox if item.label == "先选一份报表").set_value("加载契约测试示例").run()
    button(page, "整理核对范围").click().run()
    # Existing scope confirmation uses two explicit acknowledgements.
    page.checkbox[1].check()
    button(page, "确认范围，继续").click().run()  # noqa: RUF001
    page.session_state["uploaded_service"] = page.session_state["runtime"].services["服务 A · 首次故意漏项"]
    button(page, "开始核对").click().run()
    page.session_state["uploaded_service"] = page.session_state["runtime"].services["服务 B · 完整交付"]
    page.run()
    button(page, "核对修正版（最后一次）").click().run()  # noqa: RUF001
    page.toggle[0].set_value(True).run()
    assert not page.exception
    assert any(metric.label == "修复后通过" and metric.value == "1" for metric in page.metric)
    assert any(metric.label == "未通过" and metric.value == "1" for metric in page.metric)
    assert len(next(item for item in page.selectbox if item.label == "来源回执").options) == 2
    choice = next(item for item in page.radio if item.label == "人工选择服务")
    choice.set_value(choice.options[1]).run()
    button(page, "确认选择").click().run()
    assert not page.exception
    button(page, "开始下一次报表验收").click().run()
    next(item for item in page.selectbox if item.label == "先选一份报表").set_value("加载契约测试示例").run()
    button(page, "整理核对范围").click().run()
    page.checkbox[1].check()
    button(page, "确认范围，继续").click().run()  # noqa: RUF001
    # An explicit new upload must not be silently replaced by a historical service choice.
    assert "uploaded_service" in page.session_state
    assert not any(item.label == "选择要核对的报表" for item in page.radio)
    assert not page.exception
