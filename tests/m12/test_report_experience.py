import json
from pathlib import Path

from streamlit.testing.v1 import AppTest

from app.case_intake import load_real_case
from app.report_experience import (
    amount_summary,
    contract_example_bytes,
    finding_copy,
    format_token_amount,
    reference_decimals,
    strict_template_bytes,
)
from trust_receipt.models import FindingType
from trust_receipt.orchestration import evidence_from_fixture, load_vertical_demo_fixture
from trust_receipt.services.upload import parse_report

PROJECT_ROOT = Path(__file__).parents[2]


def test_downloaded_template_is_a_valid_strict_uploaded_report():
    payload = strict_template_bytes()
    assert parse_report(payload).model_dump(mode="json") == json.loads(payload)
    assert json.loads(payload)["claimed_total_base_units"] == "0"


def test_contract_example_loads_existing_synthetic_fixture_without_relabelling_it_real():
    payload = contract_example_bytes(PROJECT_ROOT)
    report = parse_report(payload)
    assert report.claimed_total_base_units == "120000"
    assert report.claimed_count == 2
    assert all(record.source.value == "service" for record in report.transfers)


def test_amount_summary_keeps_exact_integer_direction_and_token_formatting():
    summary = amount_summary("120000", "110000", decimals=6)
    assert summary.difference == "10000"
    assert summary.direction == "报表比链上有效金额多计 10000 个最小单位。"
    assert format_token_amount(summary.claimed, summary.decimals) == (
        "0.12 代币单位 (120000 最小单位, decimals=6)"
    )
    assert amount_summary("90000", "110000", decimals=6).difference == "-20000"


def test_unknown_verified_amount_is_not_rendered_as_zero_or_failure():
    summary = amount_summary("120000", None, decimals=6)
    assert summary.verified == "无法确定"
    assert summary.difference == "无法确定"
    assert "证据不足" in summary.direction


def test_incompatible_units_do_not_produce_a_misleading_difference():
    summary = amount_summary("120000", "110000", decimals=6, units_comparable=False)
    assert summary.difference == "无法确定"
    assert "金额单位" in summary.direction


def test_every_finding_type_has_business_copy_and_next_action():
    for finding_type in FindingType:
        title, action = finding_copy(finding_type)
        assert title
        assert action.endswith("。")


def test_page_exposes_example_template_and_evidence_drilldown():
    source = (PROJECT_ROOT / "app" / "streamlit_app.py").read_text(encoding="utf-8")
    assert '"上传自己的报表", "加载真实 Sepolia 案例", "加载契约测试示例"' in source
    assert "上传自己的 JSON" not in source
    assert "JSON 报表必填字段" in source
    assert '"真实 Sepolia RPC"' in source
    assert "加载契约测试示例" in source
    assert "团队构造报表" in source
    assert "下载严格 JSON 空白模板" in source
    evidence = (PROJECT_ROOT / "app" / "report_evidence.py").read_text(encoding="utf-8")
    assert "render_report_evidence(" in source
    assert 'st.expander("验证依据 / 技术详情"' in evidence
    assert 'section == "交易与差异依据"' in evidence
    assert "execution.result.findings" in evidence
    assert "execution.fund_flow.model_dump" in evidence


def test_real_case_input_preserves_reports_and_requires_new_confirmation():
    case = load_real_case(PROJECT_ROOT)
    assert case.candidate.ready_for_confirmation
    assert case.candidate.start_block == case.candidate.end_block == 11855664
    assert parse_report(case.error_report).claimed_total_base_units == "0"
    assert parse_report(case.corrected_report).claimed_total_base_units == "180674489737"
    assert "confirmed_at" not in case.candidate.model_dump()
    assert "spec_hash" not in case.candidate.model_dump()


def test_summary_precision_comes_from_reference_not_service():
    fixture = load_vertical_demo_fixture(PROJECT_ROOT)
    assert reference_decimals(evidence_from_fixture(fixture), fixture.task_spec.token_address) == 6
    assert reference_decimals(None, fixture.task_spec.token_address) is None
    assert reference_decimals(evidence_from_fixture(fixture), "0x" + "f" * 40) is None


def test_real_case_does_not_execute_with_fixture_and_prefills_editable_scope(monkeypatch):
    monkeypatch.setenv("ETH_RPC_URL", "https://unused.invalid")
    page = AppTest.from_file(str(PROJECT_ROOT / "app" / "streamlit_app.py"), default_timeout=20).run()
    next(widget for widget in page.selectbox if widget.label == "先选一份报表").set_value(
        "加载真实 Sepolia 案例"
    ).run()
    assert next(button for button in page.button if button.label == "整理核对范围").disabled
    next(widget for widget in page.radio if widget.label == "独立证据").set_value("真实 Sepolia RPC").run()
    next(button for button in page.button if button.label == "整理核对范围").click().run()
    assert not page.exception
    assert next(widget for widget in page.number_input if widget.label.startswith("起始区块")).value == 11855664
    assert "task" not in page.session_state
    assert not any("Attempt 1" in button.label for button in page.button)
