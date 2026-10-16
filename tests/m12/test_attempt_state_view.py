from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.attempt_state import attempt_view, refresh_task_view


def status(**changes):
    fields = {
        "state": "CONFIRMED",
        "in_flight_attempt": None,
        "next_attempt": 1,
        "blocking_reason": None,
        "persisted_attempts": 0,
        "completed_attempts": 0,
    }
    return SimpleNamespace(**(fields | changes))


@pytest.mark.parametrize("state", ["REQUESTED", "RETRY_REQUESTED", "SUBMITTED", "VERIFYING"])
def test_active_persisted_request_never_shows_initial_or_retry_action(state):
    view = attempt_view(status(state=state, in_flight_attempt=1, next_attempt=None))
    assert view.next_attempt is None
    assert not view.can_start_next_task
    assert "自动重试" in view.message


@pytest.mark.parametrize("state", ["PASS", "FAIL", "INCONCLUSIVE"])
def test_missing_receipt_terminal_state_is_not_recast_as_first_request(state):
    view = attempt_view(status(
        state=state, next_attempt=None, blocking_reason="MISSING_RECEIPT", persisted_attempts=1, completed_attempts=1,
    ))
    assert view.next_attempt is None
    assert not view.can_start_next_task


def test_allowed_attempt_number_comes_from_port_not_session_execution_list():
    assert attempt_view(status()).next_attempt == 1
    retry = attempt_view(status(state="FAIL", next_attempt=2, persisted_attempts=1, completed_attempts=1))
    assert retry.next_attempt == 2
    terminal = attempt_view(status(
        state="PASS", next_attempt=None, persisted_attempts=1, completed_attempts=1, blocking_reason="PASSED",
    ))
    assert terminal.can_start_next_task
    assert terminal.next_attempt is None
    assert attempt_view(status(next_attempt=3)).next_attempt is None


class State(dict):
    __setattr__ = dict.__setitem__


def test_stale_empty_cache_restores_only_current_task_without_execution():
    task = SimpleNamespace(task_id="current-task")
    execution = object()
    persisted = status(state="FAIL", persisted_attempts=1, completed_attempts=1, next_attempt=2)
    workflow = Mock()
    workflow.get_attempt_status.return_value = persisted
    workflow.restore_task.return_value = (task, (execution,), (None,))
    ui = SimpleNamespace(session_state=State(executions=[]))
    assert refresh_task_view(ui, SimpleNamespace(m8_workflow=workflow), task) is persisted
    workflow.restore_task.assert_called_once_with("current-task")
    workflow.restore_latest.assert_not_called()
    workflow.run_attempt.assert_not_called()
    assert ui.session_state["executions"] == [execution]
    assert ui.session_state["commitment_pairs"] == [None]


def test_read_errors_propagate_instead_of_guessing_initial_state():
    workflow = Mock()
    workflow.get_attempt_status.side_effect = ValueError("state unreadable")
    with pytest.raises(ValueError, match="state unreadable"):
        refresh_task_view(
            SimpleNamespace(session_state=State(executions=[])),
            SimpleNamespace(m8_workflow=workflow),
            SimpleNamespace(task_id="current-task"),
        )
    workflow.restore_task.assert_not_called()
    workflow.run_attempt.assert_not_called()
