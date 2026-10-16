"""Injected use-case presentation tests, not real model or browser evidence."""

from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

from streamlit.testing.v1 import AppTest

from trust_receipt.services.report_conversion import convert_report_table, read_report_table

CSV = Path(__file__).parents[2] / "fixtures/m14/conversion/correct-token-units.csv"


@dataclass
class Upload:
    name: str
    payload: bytes

    def getvalue(self):
        return self.payload


def harness():
    from pathlib import Path

    import streamlit as st

    from app.automatic_report_ui import render_automatic_report

    st.session_state["payload"] = render_automatic_report(
        st, st.session_state["upload"], directory=Path(st.session_state["directory"]),
        namespace="workspace:first", provider="explicit-test", recognizer=None,
        recognize=st.session_state["recognize"], retain=st.session_state["retain"],
    )
    st.button("继续", disabled=st.session_state["payload"] is None)


def outcome(*, missing=(), issues=(), clarifications=()):
    candidate = convert_report_table(read_report_table(CSV.read_bytes(), CSV.name))
    return SimpleNamespace(
        ready=not missing and not issues and not clarifications,
        missing_fields=missing, issues=issues, clarifications=clarifications, warnings=(),
        conversion=candidate, report=candidate.report, original_hash=candidate.original_hash,
        recognition_mode="offline-test",
    )


def page_for(tmp_path, recognize, retain=None):
    page = AppTest.from_function(harness, default_timeout=15)
    for key, value in {
        "upload": Upload(CSV.name, CSV.read_bytes()), "directory": str(tmp_path),
        "recognize": recognize, "retain": retain or (lambda *_args: b"strict-json"),
    }.items():
        page.session_state[key] = value
    return page.run()


def test_ready_report_is_automatic_and_normal_rerun_does_not_call_again(tmp_path):
    calls = []

    def recognize(*args, **kwargs):
        calls.append((args, kwargs))
        return outcome()

    page = page_for(tmp_path, recognize)
    assert not page.exception
    assert page.session_state["payload"] == b"strict-json"
    assert not page.checkbox and not page.selectbox and not page.text_input
    assert [item.label for item in page.button] == ["继续"]
    assert any("180674489737" in item.value for item in page.markdown)
    page.run()
    assert len(calls) == 1


def test_model_failure_is_cached_and_only_explicit_retry_calls_again(tmp_path):
    calls = []

    def recognize(*_args, **_kwargs):
        calls.append(1)
        return outcome(issues=("模型不可用, 请检查配置",))

    page = page_for(tmp_path, recognize)
    assert not page.exception
    assert page.session_state["payload"] is None
    page.run()
    assert len(calls) == 1
    next(item for item in page.button if item.label == "重新识别这份报表").click().run()
    assert len(calls) == 2
    assert page.session_state["payload"] is None


def test_only_missing_common_condition_is_asked_and_reuses_bound_previous(tmp_path):
    calls = []

    def recognize(*_args, **kwargs):
        calls.append(kwargs)
        return outcome() if kwargs["constants"].get("chain_id") else outcome(missing=("chain_id",))

    page = page_for(tmp_path, recognize)
    assert len(page.text_input) == 1 and not page.selectbox
    assert page.session_state["payload"] is None
    page.text_input[0].set_value("11155111").run()
    assert not page.exception
    assert page.session_state["payload"] == b"strict-json"
    assert calls[1]["previous"] is not None
    page.text_input[0].set_value("").run()
    assert page.session_state["payload"] is None


def test_unit_question_is_machine_driven_and_event_identity_cannot_be_filled(tmp_path):
    page = page_for(tmp_path, lambda *_args, **_kwargs: outcome(clarifications=("amount_unit",)))
    assert not page.exception
    assert len(page.selectbox) == 1 and not page.text_input
    assert page.session_state["payload"] is None
    assert not any(item.value == "amount_unit" for item in page.warning)
    page = page_for(tmp_path, lambda *_args, **_kwargs: outcome(missing=("transaction_hash",)))
    assert not page.exception
    assert not page.text_input and not page.selectbox
    assert any("交易哈希" in item.value for item in page.warning)


def test_new_file_failure_never_returns_old_retained_bytes(tmp_path):
    def recognize(payload, *_args, **_kwargs):
        return outcome() if payload == CSV.read_bytes() else outcome(issues=("新文件无效",))

    page = page_for(tmp_path, recognize)
    assert page.session_state["payload"] == b"strict-json"
    page.session_state["upload"] = Upload("new.csv", b"invalid")
    page.run()
    assert not page.exception
    assert page.session_state["payload"] is None
    assert page.button[-1].disabled


def test_private_retention_failure_blocks_without_adoption_control(tmp_path):
    def fail(*_args):
        raise OSError("private detail must not be shown")

    page = page_for(tmp_path, lambda *_args, **_kwargs: outcome(), fail)
    assert not page.exception
    assert page.session_state["payload"] is None
    assert not page.checkbox
    assert not any("private detail" in item.value for item in page.error)
