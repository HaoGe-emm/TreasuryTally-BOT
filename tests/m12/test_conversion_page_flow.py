"""Automatic full-page input and repair gates with explicit model/upload doubles."""

import csv
import io
import json
from dataclasses import dataclass, replace
from pathlib import Path

import streamlit as st
from streamlit.testing.v1 import AppTest
from test_report_intake import make_recognizer

import app.runtime as runtime_module
from app.report_experience import contract_example_bytes
from trust_receipt.models import EvidenceSource
from trust_receipt.orchestration import eligible_records, load_vertical_demo_fixture

ROOT = Path(__file__).parents[2]
APP = ROOT / "app" / "streamlit_app.py"


@dataclass
class Upload:
    name: str
    payload: bytes

    def getvalue(self):
        return self.payload


def report_csv(report):
    """Serialize synthetic test input as text, without amount inference or floats."""
    headers = [*report["transfers"][0], "claimed_total_base_units", "claimed_count"]
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=headers)
    writer.writeheader()
    for record in report["transfers"]:
        writer.writerow({
            **record,
            "claimed_total_base_units": report["claimed_total_base_units"],
            "claimed_count": report["claimed_count"],
        })
    return output.getvalue().encode("utf-8")


def button(page, label):
    return next(item for item in page.button if item.label == label)


def uploaded_page(monkeypatch, *, guided=False):
    uploads = {"first": Upload("synthetic-error.csv", report_csv(json.loads(contract_example_bytes(ROOT))))}

    def uploader(label, *_args, **_kwargs):
        return uploads.get("first" if label == "服务商报表" else "repair")

    monkeypatch.setattr(st, "file_uploader", uploader)
    original_runtime = runtime_module.create_runtime

    def test_runtime(**kwargs):
        return replace(original_runtime(**kwargs), report_recognizer=make_recognizer())

    monkeypatch.setattr(runtime_module, "create_runtime", test_runtime)
    page = AppTest.from_file(str(APP), default_timeout=30).run()
    if not guided:
        next(item for item in page.radio if item.label == "范围填写方式").set_value("直接写说明").run()
    return page, uploads


def first_failure(page):
    next(item for item in page.text_area if item.label == "说明要核对的范围").set_value(
        "核对离线人工样例并在下一步逐项确认范围。"
    ).run()
    button(page, "整理核对范围").click().run()
    next(item for item in page.checkbox if item.label.startswith("我已核对以上")).check()
    button(page, "确认范围，继续").click().run()  # noqa: RUF001
    button(page, "开始核对").click().run()
    assert not page.exception
    assert len(page.session_state["executions"]) == 1
    assert page.session_state["executions"][0].result.outcome.value == "FAIL"


def test_first_csv_is_read_automatically_but_still_needs_scope_confirmation(monkeypatch):
    page, _uploads = uploaded_page(monkeypatch)
    assert not page.exception
    assert button(page, "整理核对范围").disabled
    assert "uploaded_service" in page.session_state
    assert "task" not in page.session_state
    assert not page.checkbox
    assert not any(item.label == "确认采用转换 JSON" for item in page.button)
    assert button(page, "整理核对范围").disabled  # No scope description yet.


def test_invalid_json_or_table_repair_cannot_fall_back_to_original(monkeypatch):
    page, uploads = uploaded_page(monkeypatch)
    first_failure(page)
    assert button(page, "核对修正版（最后一次）").disabled  # noqa: RUF001
    uploads["repair"] = Upload("invalid.json", b"{}")
    page.run()
    assert not page.exception
    assert button(page, "核对修正版（最后一次）").disabled  # noqa: RUF001
    assert len(page.session_state["executions"]) == 1
    uploads["repair"] = Upload("invalid.csv", b"not-a-report")
    page.run()
    assert not page.exception
    assert button(page, "核对修正版（最后一次）").disabled  # noqa: RUF001
    assert len(page.session_state["executions"]) == 1


def test_automatic_csv_repair_uses_last_attempt_and_preserves_original_failure(monkeypatch):
    page, uploads = uploaded_page(monkeypatch)
    first_failure(page)
    fixture = load_vertical_demo_fixture(ROOT)
    corrected = {
        "claimed_total_base_units": "110000", "claimed_count": 2,
        "transfers": [item.model_copy(update={"source": EvidenceSource.SERVICE}).model_dump(mode="json")
                      for item in eligible_records(fixture)],
    }
    uploads["repair"] = Upload("synthetic-corrected.csv", report_csv(corrected))
    page.run()
    assert not button(page, "核对修正版（最后一次）").disabled  # noqa: RUF001
    button(page, "核对修正版（最后一次）").click().run()  # noqa: RUF001
    assert not page.exception
    assert [item.result.outcome.value for item in page.session_state["executions"]] == ["FAIL", "PASS"]
    assert page.session_state["executions"][0].submission.claimed_total_base_units == "120000"
    assert page.session_state["executions"][1].submission.claimed_total_base_units == "110000"
    assert not any(item.label in {"开始核对", "核对修正版（最后一次）"} for item in page.button)  # noqa: RUF001
