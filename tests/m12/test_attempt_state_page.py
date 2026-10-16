"""Isolated AppTest workspaces reproduce durable requests, not user databases."""

from pathlib import Path

from streamlit.testing.v1 import AppTest

from trust_receipt.orchestration.m8_workspace import M8WorkspaceWorkflow
from trust_receipt.storage.models import TaskState
from trust_receipt.storage.sqlite import SQLiteRepository

ROOT = Path(__file__).parents[2]
APP = ROOT / "app" / "streamlit_app.py"


def button(page, label):
    return next(item for item in page.button if item.label == label)


def confirmed_page():
    page = AppTest.from_file(str(APP), default_timeout=30).run()
    next(item for item in page.selectbox if item.label == "先选一份报表").set_value("加载契约测试示例").run()
    button(page, "整理核对范围").click().run()
    page.checkbox[1].check()
    button(page, "确认范围，继续").click().run()  # noqa: RUF001
    assert not page.exception
    return page


def repository(page):
    return SQLiteRepository(ROOT / "data" / "m5" / f"{page.session_state['workspace_id']}.db")


def assert_no_request_buttons(page):
    assert not any(item.label in {"开始核对", "核对修正版（最后一次）"} for item in page.button)  # noqa: RUF001
    assert not page.exception


def test_durable_request_with_empty_session_blocks_initial_button_and_readonly_refresh():
    page = confirmed_page()
    repo = repository(page)
    task_id = page.session_state["task"].task_id
    assert repo.request_attempt(task_id) == 1
    page.run()
    assert_no_request_buttons(page)
    assert any("请求已保存" in item.value for item in page.warning)
    button(page, "只读刷新核对状态").click().run()
    assert_no_request_buttons(page)
    assert repo.get_task(task_id).state is TaskState.REQUESTED
    assert len(repo.list_attempts(task_id)) == 0


def test_execution_exception_after_request_rerenders_blocked_status_without_auto_retry(monkeypatch):
    page = confirmed_page()
    repo = repository(page)
    task = page.session_state["task"]
    calls = []

    def interrupt(_workflow, current_task, _service):
        calls.append(current_task.task_id)
        repo.request_attempt(current_task.task_id)
        raise RuntimeError("test interrupted after persisted request")

    monkeypatch.setattr(type(page.session_state["runtime"].m8_workflow), "run_attempt", interrupt)
    button(page, "开始核对").click().run()
    assert_no_request_buttons(page)
    assert any("上次核对操作没有完成" in item.value for item in page.error)
    assert any("test interrupted after persisted request" in item.value for item in page.markdown)
    page.run()
    assert calls == [task.task_id]
    assert repo.get_task(task.task_id).state is TaskState.REQUESTED


def test_missing_receipt_after_saved_result_is_blocked_not_first_attempt(monkeypatch):
    page = confirmed_page()

    def interrupted_receipt(*_args, **_kwargs):
        raise OSError("test interrupted receipt write")

    monkeypatch.setattr(type(page.session_state["runtime"].workflow), "_save_receipt", interrupted_receipt)
    button(page, "开始核对").click().run()
    assert_no_request_buttons(page)
    assert any("后台记录需要检查" in item.value for item in page.warning)
    assert repository(page).get_task(page.session_state["task"].task_id).state is TaskState.FAIL
    assert len(repository(page).list_attempts(page.session_state["task"].task_id)) == 1


def test_new_browser_session_restores_inflight_workspace_without_initial_button():
    first = confirmed_page()
    workspace_id = first.session_state["workspace_id"]
    task_id = first.session_state["task"].task_id
    repository(first).request_attempt(task_id)
    restarted = AppTest.from_file(str(APP), default_timeout=30).run()
    next(item for item in restarted.text_input if item.label == "工作区 ID").set_value(workspace_id).run()
    assert restarted.session_state["task"].task_id == task_id
    assert_no_request_buttons(restarted)


def test_stale_cache_restores_current_task_not_another_sessions_newest_task():
    page = confirmed_page()
    current_task = page.session_state["task"]
    button(page, "开始核对").click().run()
    runtime = page.session_state["runtime"]
    another = runtime.workflow.confirm_task(runtime.editable_seed)
    assert another.task_id != current_task.task_id
    page.session_state["executions"] = []
    page.run()
    assert page.session_state["task"].task_id == current_task.task_id
    assert len(page.session_state["executions"]) == 1
    assert button(page, "核对修正版（最后一次）").disabled  # noqa: RUF001
    assert not any(item.label == "开始核对" for item in page.button)
    assert not page.exception


def test_workspace_restore_conflict_is_readable_and_does_not_offer_new_execution(monkeypatch):
    def conflict(*_args):
        raise ValueError("test stored commitment conflict")

    monkeypatch.setattr(M8WorkspaceWorkflow, "restore_latest", conflict)
    page = AppTest.from_file(str(APP), default_timeout=30).run()
    assert_no_request_buttons(page)
    assert any("已有工作区记录无法安全恢复" in item.value for item in page.error)
    assert any("test stored commitment conflict" in item.value for item in page.markdown)
    assert not any(item.label == "整理核对范围" for item in page.button)
