"""Read-only presentation of the workflow's persisted attempt-status port."""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AttemptView:
    title: str
    message: str
    next_attempt: int | None
    can_start_next_task: bool


def attempt_view(status: Any) -> AttemptView:
    """Never infer an allowed request from the browser's execution count."""
    state = str(status.state)
    if status.next_attempt not in {None, 1, 2}:
        return AttemptView("核对状态异常", "后台返回了不允许的次数。入口已阻塞，不会发起第三次核对。", None, False)
    if status.in_flight_attempt is not None:
        title = {
            "REQUESTED": "核对请求已保存",
            "RETRY_REQUESTED": "最后一次核对请求已保存",
            "SUBMITTED": "报表已接收，结果尚未完成",
            "VERIFYING": "核对已开始，结果尚未完成",
        }.get(state, "已有未完成的核对请求")
        return AttemptView(
            title,
            f"后台已记录第 {status.in_flight_attempt} 次请求，可能仍在处理或曾中断。"
            "不会再次发起或自动重试。请只读刷新状态；若持续不变，请保留工作区编号并交由维护者检查。",
            None,
            False,
        )
    if status.blocking_reason and str(status.blocking_reason) not in {"PASSED", "ATTEMPTS_EXHAUSTED"}:
        return AttemptView(
            "后台记录需要检查，暂不能继续",
            "已有请求或核对记录尚不能完整恢复。不会因页面没有结果而当作首次请求；"
            "请保留工作区编号与现有记录，查看原因或只读刷新状态。",
            None,
            False,
        )
    if status.next_attempt is not None:
        return AttemptView(
            "等待开始核对" if status.next_attempt == 1 else "可使用最后一次核对",
            "点击后才会开始；不会自动提交。" if status.next_attempt == 1
            else "后台允许第 2 次核对。请先处理差异或证据问题；本任务不会提供第三次机会。",
            status.next_attempt,
            False,
        )
    return AttemptView(
        "本任务核对已结束",
        "后台不再允许发起本任务。结果与回执保持留档，可以查看记录或明确开始新任务。",
        None,
        state in {"PASS", "FAIL", "INCONCLUSIVE"},
    )


def render_attempt_state(ui: Any, status: Any) -> AttemptView:
    view = attempt_view(status)
    if not view.can_start_next_task and view.next_attempt is None:
        ui.warning(f"{view.title}：{view.message}")
        with ui.expander("查看后台核对状态与恢复说明", expanded=False):
            ui.write({
                "状态": str(status.state),
                "已保存交付数": status.persisted_attempts,
                "已保存结果数": status.completed_attempts,
                "未完成请求序号": status.in_flight_attempt,
                "阻塞原因": status.blocking_reason,
            })
            ui.caption("这里只读取记录，不撤销请求、不删除历史，也不重新执行。新工作区须由你明确选择。")
        if ui.button("只读刷新核对状态", key="refresh-attempt-status"):
            ui.rerun()
    return view


def refresh_task_view(ui: Any, runtime: Any, task: Any) -> Any:
    """Read the active task only; do not replace it with another session's latest."""
    status = runtime.m8_workflow.get_attempt_status(task.task_id)
    cached = ui.session_state.get("executions", [])
    if len(cached) != status.completed_attempts or any(
        execution.submission.task_id != task.task_id for execution in cached
    ):
        restored_task, executions, snapshots = runtime.m8_workflow.restore_task(task.task_id)
        if restored_task != task:
            raise ValueError("restored task differs from the confirmed active task")
        ui.session_state.executions = list(executions)
        ui.session_state.commitment_pairs = [
            (snapshot.task_commitment, snapshot.delivery_commitment, snapshot.expected_signer)
            if snapshot is not None else None
            for snapshot in snapshots
        ]
    return status
