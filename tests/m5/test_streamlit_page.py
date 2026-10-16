from pathlib import Path

from streamlit.testing.v1 import AppTest

from app.styles import APP_CSS


def practice(page):
    next(item for item in page.selectbox if item.label == "先选一份报表").set_value("加载契约测试示例").run()
    return page


def button(page, label):
    return next(item for item in page.button if item.label == label)


def test_responsive_css_forces_narrow_layout_to_single_column() -> None:
    assert "@media (max-width:760px)" in APP_CSS
    assert 'div[data-testid="stHorizontalBlock"] { flex-direction:column !important' in APP_CSS
    assert 'div[data-testid="column"] { width:100% !important' in APP_CSS
    assert "overflow-wrap:anywhere" in APP_CSS
    assert "padding:12px 24px 64px" in APP_CSS
    assert "--tr-gold-primary:#D4AF37" in APP_CSS
    assert "border-radius:12px" in APP_CSS


def test_page_starts_without_execution_controls_before_confirmation() -> None:
    app_path = Path(__file__).parents[2] / "app" / "streamlit_app.py"
    page = AppTest.from_file(str(app_path), default_timeout=20).run()

    assert not page.exception
    assert button(page, "整理核对范围").disabled
    assert not any("Attempt" in button.label for button in page.button)
    assert not any('class="signal-grid"' in markdown.value for markdown in page.markdown)


def test_page_walks_fail_to_pass_without_overwriting_attempt_one() -> None:
    app_path = Path(__file__).parents[2] / "app" / "streamlit_app.py"
    page = AppTest.from_file(str(app_path), default_timeout=20).run()
    practice(page)
    button(page, "整理核对范围").click().run(timeout=20)

    button(page, "确认范围，继续").click().run(timeout=20)  # noqa: RUF001
    assert not any("Attempt" in button.label for button in page.button)

    page.checkbox[1].check()
    button(page, "确认范围，继续").click().run(timeout=20)  # noqa: RUF001
    assert not page.exception
    assert any(item.label == "开始核对" for item in page.button)

    button(page, "开始核对").click().run(timeout=20)
    assert [metric.value for metric in page.metric] == ["0.12", "0.11", "0.01"]
    assert page.session_state["executions"][0].submission.claimed_total_base_units == "120000"
    assert page.session_state["executions"][0].result.calculated_total_base_units == "110000"

    # AppTest cannot set file uploads; inject the corrected delivery adapter.
    page.session_state["uploaded_service"] = page.session_state["runtime"].services["服务 B · 完整交付"]
    page.run()
    button(page, "核对修正版（最后一次）").click().run(timeout=20)  # noqa: RUF001
    assert [metric.value for metric in page.metric] == ["0.11", "0.11", "0"]
    assert [item.result.outcome.value for item in page.session_state["executions"]] == ["FAIL", "PASS"]
    assert page.session_state["executions"][0].submission.claimed_total_base_units == "120000"
    assert page.session_state["executions"][1].submission.claimed_total_base_units == "110000"
    assert not page.exception


def test_page_renders_inconclusive_as_evidence_shortfall() -> None:
    app_path = Path(__file__).parents[2] / "app" / "streamlit_app.py"
    page = AppTest.from_file(str(app_path), default_timeout=20).run()
    practice(page)
    next(radio for radio in page.radio if radio.label == "独立证据").set_value("模拟证据不可用").run(timeout=20)
    button(page, "整理核对范围").click().run(timeout=20)
    page.checkbox[1].check()
    button(page, "确认范围，继续").click().run(timeout=20)  # noqa: RUF001
    button(page, "开始核对").click().run(timeout=20)

    assert page.session_state["executions"][0].result.outcome.value == "INCONCLUSIVE"
    assert any(element.value == "#### 为什么暂不能判断" for element in page.markdown)
    assert any(
        "通过或服务失败" in warning.value
        and ("不能认定" in warning.value or "暂不能判断" in warning.value)
        for warning in page.warning
    )
    assert [metric.value for metric in page.metric] == ["0.12", "无法确定", "无法确定"]


def test_live_mode_is_selectable_with_configured_rpc(monkeypatch) -> None:
    monkeypatch.setenv("ETH_RPC_URL", "https://unused.invalid")
    app_path = Path(__file__).parents[2] / "app" / "streamlit_app.py"
    page = AppTest.from_file(str(app_path), default_timeout=20).run()
    next(radio for radio in page.radio if radio.label == "独立证据").set_value("真实 Sepolia RPC").run(timeout=20)

    assert not page.exception
    assert not page.error
    assert next(radio for radio in page.radio if radio.label == "独立证据").value == "真实 Sepolia RPC"


def test_production_mode_is_locked_to_real_deepseek_and_rpc(monkeypatch) -> None:
    monkeypatch.setenv("APP_REQUIRE_LIVE", "true")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-only")
    monkeypatch.setenv("DEEPSEEK_MODEL", "deepseek-test")
    monkeypatch.setenv("ETH_RPC_URL", "https://unused.invalid")
    app_path = Path(__file__).parents[2] / "app" / "streamlit_app.py"
    page = AppTest.from_file(str(app_path), default_timeout=20).run()

    assert not page.exception
    assert page.selectbox[0].value == "DeepSeek 真实模型"
    assert list(page.selectbox[0].options) == ["DeepSeek 真实模型"]
    assert page.radio[0].value == "真实 Sepolia RPC"
