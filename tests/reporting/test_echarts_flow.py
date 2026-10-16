"""Read-only ECharts option, source/precision preservation and script boundaries."""

import json
import re

import pytest

from trust_receipt.reporting import build_business_report
from trust_receipt.reporting.echarts_flow import (
    ECHARTS_VERSION,
    echarts_component_html,
    echarts_flow_option,
    echarts_javascript,
)


def view_for(item):
    return build_business_report(item.receipt, item.submission, fund_flow=item.fund_flow, source_mode="fixture")


def test_graph_preserves_facts_and_does_not_use_numeric_money(failing_input):
    view = view_for(failing_input)
    before = view.model_dump_json()
    option = echarts_flow_option(view)
    json.dumps(option, allow_nan=False)
    graph = option["series"][0]
    assert graph["type"] == "graph"
    assert graph["edgeSymbol"] == ["none", "arrow"]
    for row, edge in zip(view.current.flow_rows, graph["links"], strict=True):
        assert edge["event_ref"] == row.event_ref
        assert edge["amount_base_units"] == row.amount.base_units
        assert row.amount.display in edge["name"]
        assert row.amount.unit in edge["name"]
        assert row.source_label in edge["name"]
        assert edge["finding_ids"] == list(row.finding_ids)
        assert "value" not in edge
        assert edge["lineStyle"]["width"] == 2
    assert view.model_dump_json() == before


def test_all_200_edges_accessible_via_explicit_pages(failing_input):
    view = view_for(failing_input)
    row = view.current.flow_rows[0]
    rows = tuple(row.model_copy(update={"edge_id": f"edge-{i}"}) for i in range(200))
    view = view.model_copy(update={"current": view.current.model_copy(update={"flow_rows": rows})})
    seen = []
    for offset in range(0, 200, 12):
        option = echarts_flow_option(view, offset=offset)
        assert "/ 200" in option["title"]["subtext"]
        seen.extend(edge["edge_id"] for edge in option["series"][0]["links"])
    assert seen == [f"edge-{i}" for i in range(200)]


@pytest.mark.parametrize("kwargs", [{"offset": -1}, {"offset": True}, {"limit": 21}, {"limit": 0},
                                    {"attempt": "other"}, {"theme": "other"}, {"attempt": "previous"}])
def test_invalid_graph_selection_rejected(failing_input, kwargs):
    with pytest.raises(ValueError):
        echarts_flow_option(view_for(failing_input), **kwargs)


def test_no_graph_snapshot_does_not_fabricate_edges(failing_input):
    view = build_business_report(failing_input.receipt, failing_input.submission, source_mode="fixture")
    graph = echarts_flow_option(view)
    assert graph["series"][0]["links"] == []
    assert graph["series"][0]["data"] == []


def test_html_component_has_local_runtime_and_no_data_script_injection(failing_input):
    view = view_for(failing_input)
    payload = '</script><img src=x onerror="alert(1)">'
    row = view.current.flow_rows[0].model_copy(update={"source_label": payload})
    view = view.model_copy(update={"current": view.current.model_copy(update={"flow_rows": (row,)})})
    html = echarts_component_html(view)
    assert payload not in html
    assert "script src=" not in html
    assert "connect-src &#x27;none&#x27;" in html
    assert 'renderer:"svg"' in html
    assert 'treasuryTallyAttachCardEdges(chart)' in html
    assert 'chart.on("graphRoam",attach)' in html
    assert 'chart.resize();attach();' in html
    data = re.search(r'<script id="flow-data" type="application/json">(.*?)</script>', html).group(1)
    assert "<" not in data
    assert payload in json.loads(data)["series"][0]["links"][0]["name"]
    assert json.loads(data)["tooltip"]["renderMode"] == "richText"
    assert len(re.findall(r"<script\b", html)) == 3
    assert len(re.findall(r"</script>", html)) == 3


def test_pinned_component_available():
    assert ECHARTS_VERSION == "6.0.0"
    assert "Apache Software Foundation" in echarts_javascript()


def test_readable_cards_and_amount_labels_keep_complete_tooltips(failing_input):
    view = view_for(failing_input)
    option = echarts_flow_option(view)
    graph = option["series"][0]
    assert all(node["symbolSize"] == 176 and node["symbolKeepAspect"] for node in graph["data"])
    assert all(node["label"]["position"] == "inside" for node in graph["data"])
    for row, edge in zip(view.current.flow_rows, graph["links"], strict=True):
        assert row.amount.display in edge["label"]["formatter"]
        assert row.status_label in edge["label"]["formatter"]
        assert edge["lineStyle"]["color"] == "#b8b8bd"
    html = echarts_component_html(view)
    assert "min-width:720px" in html
    assert 'class="flow-scroll" tabindex="0"' in html


def test_long_amount_abbreviates_only_visual_label(failing_input):
    view = view_for(failing_input)
    row = view.current.flow_rows[0]
    amount = row.amount.model_copy(update={"display": "0." + "0" * 253 + "1"})
    row = row.model_copy(update={"amount": amount})
    view = view.model_copy(update={"current": view.current.model_copy(update={"flow_rows": (row,)})})
    edge = echarts_flow_option(view)["series"][0]["links"][0]
    assert "…" in edge["label"]["formatter"]
    assert amount.display in edge["name"]
    assert edge["amount_base_units"] == amount.base_units


def test_single_row_does_not_stretch_nodes_or_line_strokes(failing_input):
    view = view_for(failing_input)
    report = view.current.model_copy(update={"flow_rows": view.current.flow_rows[:1]})
    view = view.model_copy(update={"current": report})
    graph = echarts_flow_option(view)["series"][0]
    assert graph["height"] == 2
    assert len(graph["data"]) == 2


def test_lower_row_label_leaves_internal_transfer_lane_clear(failing_input):
    graph = echarts_flow_option(view_for(failing_input))["series"][0]
    positions = {node["id"]: node["y"] for node in graph["data"]}
    lower = [edge for edge in graph["links"]
             if positions[edge["source"]] > 0 and positions[edge["target"]] > 0]
    assert lower
    assert all(edge["label"]["position"] == "insideMiddleBottom" for edge in lower)
