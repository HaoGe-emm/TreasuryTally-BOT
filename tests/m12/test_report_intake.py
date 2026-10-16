"""Automatic intake integration; model double is explicit, never real API evidence."""

import csv
import io
import json
from dataclasses import dataclass
from pathlib import Path

from streamlit.testing.v1 import AppTest

from app.report_experience import strict_template_bytes
from trust_receipt.services.header_recognition import ColumnRole, HeaderRecognizer
from trust_receipt.services.report_conversion import ALIASES, _header_key

CSV = Path(__file__).parents[2] / "fixtures/m14/conversion/correct-token-units.csv"


@dataclass
class Upload:
    name: str
    payload: bytes

    def getvalue(self):
        return self.payload


class TestModel:
    __test__ = False

    def __init__(self):
        self.calls = []

    def generate(self, *, schema, system_prompt, payload):
        self.calls.append(payload)
        roles = []
        for column in payload["columns"]:
            field = next((name for name, aliases in ALIASES.items()
                          if _header_key(column["label"]) in {_header_key(alias) for alias in aliases}), "ignore")
            roles.append(ColumnRole(column_index=column["index"], field=field, ambiguous=False))
        return schema(schema_version="1.0", columns=tuple(roles))


def make_recognizer():
    return HeaderRecognizer(TestModel(), mode="offline-test", model_id="explicit-ui-test")


def harness():
    from pathlib import Path

    import streamlit as st

    from app.report_intake import render_report_intake

    st.session_state["payload"] = render_report_intake(
        st, st.session_state.get("upload"), directory=Path(st.session_state["directory"]),
        namespace="workspace:first", recognizer=st.session_state.get("recognizer"), provider="explicit-ui-test",
    )
    st.button("继续", disabled=st.session_state["payload"] is None)


def page_for(tmp_path, upload, recognizer=None):
    page = AppTest.from_function(harness, default_timeout=20)
    page.session_state["directory"] = str(tmp_path)
    page.session_state["upload"] = upload
    page.session_state["recognizer"] = recognizer
    return page.run()


def test_csv_automatically_retains_original_and_exact_report_without_adoption(tmp_path):
    model = make_recognizer()
    page = page_for(tmp_path, Upload(CSV.name, CSV.read_bytes()), model)
    assert not page.exception and not page.checkbox and not page.selectbox
    normalized = json.loads(page.session_state["payload"])
    assert normalized["claimed_total_base_units"] == "180674489737"
    assert normalized["claimed_count"] == 1
    assert len(list(tmp_path.rglob("*.*"))) == 3
    assert len(model.port.calls) == 1
    page.run()
    assert len(model.port.calls) == 1


def test_json_keeps_exact_bytes_without_model_and_rejects_invalid_json(tmp_path):
    model = make_recognizer()
    raw = strict_template_bytes()
    page = page_for(tmp_path, Upload("strict.json", raw), model)
    assert not page.exception and page.session_state["payload"] == raw
    assert not model.port.calls
    page.session_state["upload"] = Upload("bad.json", b"{}")
    page.run()
    assert not page.exception and page.session_state["payload"] is None
    assert page.button[-1].disabled


def test_xlsx_uses_same_automatic_entry_and_formula_replacement_revokes_ready_input(tmp_path):
    from tests.test_report_conversion import xlsx

    rows = list(csv.reader(io.StringIO(CSV.read_text(encoding="utf-8"))))
    model = make_recognizer()
    page = page_for(tmp_path, Upload("synthetic.xlsx", xlsx(rows)), model)
    assert not page.exception and not page.checkbox and not page.selectbox
    assert json.loads(page.session_state["payload"])["claimed_total_base_units"] == "180674489737"
    assert len(model.port.calls) == 1
    page.session_state["upload"] = Upload("formula.xlsx", xlsx(rows, formula="<f>SUM(A1)</f>"))
    page.run()
    assert not page.exception and page.session_state["payload"] is None
    assert page.button[-1].disabled
    assert len(model.port.calls) == 1


def test_no_model_blocks_table_without_fixture_fallback(tmp_path):
    page = page_for(tmp_path, Upload(CSV.name, CSV.read_bytes()))
    assert not page.exception and page.session_state["payload"] is None
    assert any("真实模型" in item.value for item in page.error)
    assert not page.checkbox and not page.text_input
    assert not list(tmp_path.iterdir())


def test_only_missing_chain_is_asked_and_user_condition_never_reaches_model(tmp_path):
    raw = CSV.read_bytes().replace("链ID".encode(), b"ignore_network")
    model = make_recognizer()
    page = page_for(tmp_path, Upload("missing-chain.csv", raw), model)
    assert not page.exception and page.session_state["payload"] is None
    assert len(page.text_input) == 1 and not page.checkbox
    page.text_input[0].set_value("11155111").run()
    assert not page.exception and page.session_state["payload"] is not None
    assert len(model.port.calls) == 1
    assert "11155111" not in json.dumps(model.port.calls)
    page.text_input[0].set_value("").run()
    assert page.session_state["payload"] is None


def test_changed_or_removed_input_clears_old_service_and_scope_candidate(tmp_path):
    page = page_for(tmp_path, Upload(CSV.name, CSV.read_bytes()), make_recognizer())
    for key in ("uploaded_service", "uploaded_report_hash", "candidate"):
        page.session_state[key] = "stale"
    page.session_state["upload"] = Upload("invalid.csv", b"bad")
    page.run()
    assert not page.exception and page.session_state["payload"] is None
    assert all(key not in page.session_state for key in ("uploaded_service", "uploaded_report_hash", "candidate"))
    page.session_state["upload"] = None
    page.run()
    assert not page.exception and page.session_state["payload"] is None


def test_duplicate_rows_and_original_summary_are_not_repaired(tmp_path):
    lines = CSV.read_bytes().splitlines()
    page = page_for(tmp_path, Upload("duplicate.csv", b"\n".join([*lines, lines[1]])), make_recognizer())
    report = json.loads(page.session_state["payload"])
    assert report["claimed_total_base_units"] == "180674489737" and report["claimed_count"] == 1
    assert len(report["transfers"]) == 2 and report["transfers"][0] == report["transfers"][1]


def test_retention_failure_blocks_without_showing_private_exception(tmp_path, monkeypatch):
    def fail(*_args):
        raise OSError("PRIVATE STORAGE PATH")

    monkeypatch.setattr("app.report_intake.persist_recognized_report", fail)
    page = page_for(tmp_path, Upload(CSV.name, CSV.read_bytes()), make_recognizer())
    assert not page.exception and page.session_state["payload"] is None
    assert not any("PRIVATE STORAGE PATH" in item.value for item in page.error)
