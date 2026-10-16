"""Input changes cannot inherit old recognized bytes or old failures."""

import pytest

from app.report_identification_state import (
    report_input_identity,
    reset_report_input,
    track_report_input,
)


@pytest.mark.parametrize("changed", ["original", "filename", "provider", "constants", "amount_unit"])
def test_every_input_dimension_changes_identity(changed):
    values = dict(original=b"csv", filename="report.csv", provider="live", constants={}, amount_unit=None)
    before = report_input_identity(**values)
    values[changed] = {
        "original": b"other", "filename": "other.csv", "provider": "other-model",
        "constants": {"chain_id": "1"}, "amount_unit": "token",
    }[changed]
    assert report_input_identity(**values) != before


def test_change_drops_ready_and_error_cache_not_task_history():
    state = {"task": "unchanged"}
    track_report_input(state, "first", "old")
    state["first:recognition:result"] = ("old", "ready-or-failure")
    state["first:recognition:retained"] = ("old", b"json")
    state["first:recognition:answer:old:chain_id"] = "1"
    track_report_input(state, "first", "new")
    assert "first:recognition:result" not in state
    assert "first:recognition:retained" not in state
    assert "first:recognition:answer:old:chain_id" not in state
    track_report_input(state, "first", "old")
    assert "first:recognition:retained" not in state
    assert state["task"] == "unchanged"


def test_namespaces_and_dictionary_order():
    assert report_input_identity(b"csv", "r", "live", {"a": "1", "b": "2"}, None) == (
        report_input_identity(b"csv", "r", "live", {"b": "2", "a": "1"}, None)
    )
    state = {"first:recognition:result": "first", "repair:recognition:result": "repair"}
    reset_report_input(state, "first")
    assert state == {"repair:recognition:result": "repair"}
