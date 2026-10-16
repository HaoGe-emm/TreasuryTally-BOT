"""Unconfirmed scope recovery; no report inference or automatic verification."""

from uuid import uuid4

from pydantic import ValidationError

from app.scope_request import RAW, has_placeholders
from trust_receipt.agents import TaskField, TaskSpecCandidate
from trust_receipt.agents.task_draft import TASK_DRAFT_DEADLINE_SECONDS, TaskDraftError

ERROR_COPY = {
    "timeout": "整理核对范围超时。本次本地等待已停止，没有取得可用候选。",
    "connection": "暂时无法连接模型服务，没有取得核验范围候选。",
    "rate_limit": "模型服务限流，暂未取得核验范围候选。",
    "provider": "模型服务暂时不可用，没有取得核验范围候选。",
    "invalid_output": "模型返回的范围未通过结构校验，未采纳该候选。",
    "unavailable": "暂时无法整理核验范围，没有取得可用候选。",
}


def blank_manual_candidate():
    return TaskSpecCandidate.model_validate({
        "schema_version": "1.0", "candidate_id": f"manual-{uuid4().hex}",
        **{field.value: None for field in TaskField},
        "max_records": 200, "ambiguities": [], "missing_fields": list(TaskField),
        "clarification_questions": ["请填写并确认链、代币、账户、区块和排除规则。"],
    })


def clear_scope_candidate(state):
    for key in ("candidate", "candidate_origin", "candidate_request", "candidate_request_mode", "draft_error"):
        state.pop(key, None)


def error_kind(error):
    if isinstance(error, TaskDraftError):
        return error.kind if error.kind in ERROR_COPY else "unavailable"
    return "invalid_output" if isinstance(error, ValidationError) else "unavailable"


def render_scope_actions(st, runtime, request, *, valid_report, example=None,
                         request_ready=True, request_mode=RAW):
    request_ready = request_ready and not has_placeholders(request)
    if (st.session_state.get("candidate_origin") == "model"
            and (st.session_state.get("candidate_request") != request or not request_ready)):
        clear_scope_candidate(st.session_state)
    if st.session_state.get("provider") != "离线 fixture 演示" and example is None:
        st.caption(
            f"候选生成使用单次 {TASK_DRAFT_DEADLINE_SECONDS} 秒本地等待预算，不自动重试。"
            "停止本地等待不代表供应商已取消处理；也不代表已确认范围或链上核验。"
        )
    failed = "draft_error" in st.session_state
    if failed:
        st.error(ERROR_COPY.get(st.session_state.draft_error, ERROR_COPY["unavailable"]))
        st.info("上传报表和范围说明已保留。可显式重试，或直接手工填写核验范围；仍需校验和确认，不会自动核验。")
    if st.button(
        "重试整理核对范围" if failed else "整理核对范围",
        type="secondary" if "candidate" in st.session_state or not valid_report else "primary",
        disabled=not valid_report or (example is None and (not request.strip() or not request_ready)),
        use_container_width=True,
    ):
        clear_scope_candidate(st.session_state)
        try:
            with st.spinner("正在整理你要核对的条件…"):
                candidate = example if example is not None else runtime.workflow.draft_task(request)
                st.session_state.candidate = TaskSpecCandidate.model_validate(candidate)
            st.session_state.candidate_origin = "example" if example is not None else "model"
            st.session_state.candidate_request = request
            st.session_state.candidate_request_mode = request_mode
        except (TaskDraftError, ValidationError) as error:
            st.session_state.draft_error = error_kind(error)
        except Exception:
            st.session_state.draft_error = "unavailable"
        st.rerun()
    if st.button("直接填写核验范围", disabled=not valid_report, use_container_width=True):
        clear_scope_candidate(st.session_state)
        st.session_state.candidate = blank_manual_candidate()
        st.session_state.candidate_origin = "manual"
        st.rerun()
