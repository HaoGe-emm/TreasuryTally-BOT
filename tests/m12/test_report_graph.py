"""ECharts UI wiring tests; AppTest does not execute JavaScript or prove legibility."""

import json
import re

from streamlit.testing.v1 import AppTest

from tests.reporting.conftest import report_input
from trust_receipt.reporting import build_business_report


def view():
    item = report_input()
    return build_business_report(item.receipt, item.submission, fund_flow=item.fund_flow, source_mode="fixture")


def harness():
    import streamlit as st

    from app.report_graph import render_report_graph

    render_report_graph(st, st.session_state["report"], embed=st.session_state["embed"])


def page_for(report):
    options = []

    def capture(document, *, height, scrolling):
        data = re.search(r'<script id="flow-data" type="application/json">(.*?)</script>', document).group(1)
        options.append(json.loads(data))
        assert height == 560 and scrolling
        assert "script src=" not in document
        assert "connect-src &#x27;none&#x27;" in document

    page = AppTest.from_function(harness, default_timeout=15)
    page.session_state["report"] = report
    page.session_state["embed"] = capture
    return page.run(), options


def test_saved_graph_is_default_with_text_legend_and_no_business_mutation():
    report = view()
    original = report.model_dump_json()
    page, options = page_for(report)
    assert not page.exception and len(options) == 1
    assert not page.selectbox
    assert len(options[0]["series"][0]["links"]) == len(report.current.flow_rows)
    assert any("图例：" in item.value for item in page.caption)  # noqa: RUF001
    assert any("拖动或缩放只改变视图" in item.value for item in page.caption)
    assert report.model_dump_json() == original


def test_all_200_events_reachable_through_ui_page_selection():
    report = view()
    row = report.current.flow_rows[0]
    rows = tuple(row.model_copy(update={"edge_id": f"edge-{number}"}) for number in range(200))
    report = report.model_copy(update={"current": report.current.model_copy(update={"flow_rows": rows})})
    page, options = page_for(report)
    seen = [edge["edge_id"] for edge in options[-1]["series"][0]["links"]]
    for number in range(1, 17):
        next(item for item in page.selectbox if item.label == "查看哪组转账").set_value(number).run()
        assert not page.exception
        seen.extend(edge["edge_id"] for edge in options[-1]["series"][0]["links"])
    assert seen == [f"edge-{number}" for number in range(200)]
    assert any("193–200" in item.value and "共 200" in item.value for item in page.caption)  # noqa: RUF001


def test_graph_attempt_switch_preserves_original_failure():
    report = view()
    current = report.current.model_copy(update={"attempt": 2, "flow_rows": report.current.flow_rows[:1]})
    report = report.model_copy(update={"current": current, "previous": report.current})
    page, options = page_for(report)
    assert "第 2 次" in options[-1]["title"]["text"]
    next(item for item in page.selectbox if item.label == "查看哪次资金流").set_value("previous").run()
    assert not page.exception
    assert "第 1 次" in options[-1]["title"]["text"]
    assert len(options[-1]["series"][0]["links"]) == len(report.previous.flow_rows)
    assert report.previous.outcome.value == "FAIL"


def test_missing_snapshot_never_fabricates_a_graph():
    item = report_input()
    report = build_business_report(item.receipt, item.submission, source_mode="recorded")
    page, options = page_for(report)
    assert not page.exception and not options
    assert any("不补造转账" in item.value for item in page.info)


def test_unknown_precision_stays_explicit_in_visible_graph_label():
    def transform(fixture):
        records = tuple(record.model_copy(update={
            "token_address": "0x" + "f" * 40, "transaction_hash": "0x" + "d" * 64,
        }) for record in fixture.submission.transfers)
        return fixture.model_copy(update={"submission": fixture.submission.model_copy(update={"transfers": records})})

    item = report_input("correct-basic", transform=transform)
    report = build_business_report(item.receipt, item.submission, fund_flow=item.fund_flow)
    page, options = page_for(report)
    assert not page.exception
    rows = {row.edge_id: row for row in report.current.flow_rows}
    unknown = [edge for edge in options[-1]["series"][0]["links"] if rows[edge["edge_id"]].amount.decimals is None]
    assert unknown
    for edge in unknown:
        assert "最小单位（精度未确认）" in edge["label"]["formatter"]  # noqa: RUF001
        assert edge["amount_base_units"] == rows[edge["edge_id"]].amount.base_units
        assert rows[edge["edge_id"]].amount.unit in edge["name"]
