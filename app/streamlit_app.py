"""Responsive Streamlit product page for the M5 vertical demonstration."""

from __future__ import annotations

import json
import os
import sys
from dataclasses import replace
from html import escape
from pathlib import Path
from uuid import uuid4

import streamlit as st
from pydantic import ValidationError

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from app.attempt_state import attempt_view, refresh_task_view, render_attempt_state
from app.branding import LOGO_PATH, logo_display_url
from app.business_report import render_business_report
from app.case_intake import load_real_case
from app.m9_components import (
    render_public_verification,
)
from app.m9_public import render_public_explorer
from app.onboarding import render_onboarding
from app.report_evidence import render_report_evidence
from app.report_experience import (
    contract_example_bytes,
    strict_template_bytes,
)
from app.report_exports import document_exporters, reset_report_downloads
from app.report_graph import render_report_graph
from app.report_intake import render_report_intake
from app.runtime import AppRuntime, ConfigurationBlocked, create_runtime
from app.scope_draft import clear_scope_candidate, render_scope_actions
from app.scope_request import RAW, preserve_scope_inputs, render_scope_request, request_ready
from app.service_history import render_workspace_history
from app.styles import APP_CSS
from trust_receipt.agents import TaskSpecCandidate
from trust_receipt.hashing import content_hash
from trust_receipt.m9 import PublicReceiptReference, PublicReferenceKind, verify_public_reference
from trust_receipt.models import (
    ExclusionRule,
    ExclusionRuleType,
    PublicationChainStatus,
    VerificationOutcome,
)
from trust_receipt.orchestration.m9 import PublisherReceiptResolver, build_m9_artifacts
from trust_receipt.reporting import ReportAttemptInput, build_business_report
from trust_receipt.services.upload import UploadedReport, UploadedReportService

PROVIDERS = ("离线 fixture 演示", "OpenAI 真实模型", "DeepSeek 真实模型")
EVIDENCE_MODES = ("完整 fixture 证据", "模拟证据不可用", "真实 Sepolia RPC")


def _live_only() -> bool:
    return os.environ.get("APP_REQUIRE_LIVE", "").strip().lower() in {"1", "true", "yes"}


def _section(title: str, subtitle: str) -> None:
    st.markdown(
        '<div class="section-head"><div>'
        f'<h2>{escape(title)}</h2></div>'
        f'<p>{escape(subtitle)}</p></div>',
        unsafe_allow_html=True,
    )


def _product_header() -> None:
    logo_url = escape(logo_display_url(st.get_option("server.baseUrlPath")), quote=True)
    environment = "样例演示 · 非真实链上证据"
    if _live_only() or st.session_state.get("evidence_label") == "真实 Sepolia RPC":
        environment = "Sepolia · 真实只读核验"
    st.html(
        '<div class="product-bar"><div class="brand">'
        f'<img class="brand-logo" src="{logo_url}" alt="TreasuryTally Logo" width="52" height="52" '
        'loading="eager" decoding="async">'
        '<span>TreasuryTally</span></div><span class="env-chip"><i class="env-dot"></i>'
        f'{escape(environment)}</span></div>'
        '<section class="hero-main"><div class="hero-copy"><div class="eyebrow">链上报表验收工具</div>'
        '<h1>核对服务商报表与链上资金流</h1>'
        '<p>生成可复现的验收回执。金额与结论由确定性程序计算，技术依据按需展开。</p></div>'
        '<div class="hero-emblem" aria-hidden="true">'
        f'<img src="{logo_url}" alt="" width="144" height="144" loading="eager" decoding="async"></div></section>'
        '<nav class="workflow-steps" aria-label="验收流程">'
        '<span><b>1</b> 上传报表</span><i>→</i><span><b>2</b> 确认范围</span><i>→</i>'
        '<span><b>3</b> 链上核验</span></nav>',
    )


def _runtime() -> AppRuntime | None:
    live_only = _live_only()
    providers = ("DeepSeek 真实模型",) if live_only else PROVIDERS
    evidence_modes = ("真实 Sepolia RPC",) if live_only else EVIDENCE_MODES
    with st.expander("高级设置 · 模型、证据来源与历史恢复", expanded=False):
        provider_col, evidence_col, workspace_col = st.columns((1, 1.25, 1))
        with provider_col:
            provider = st.selectbox("AI 路径", providers, key="provider", disabled=len(providers) == 1)
        if "workspace_id" not in st.session_state:
            st.session_state.workspace_id = f"workspace-{uuid4().hex[:8]}"
        with evidence_col:
            evidence_label = st.radio(
                "独立证据", evidence_modes, key="evidence_label", horizontal=True,
                disabled=len(evidence_modes) == 1,
            )
        with workspace_col:
            workspace_id = st.text_input(
                "工作区 ID",
                key="workspace_id",
                help="保存此编号，下次填入即可恢复已保存的核对记录。更换编号会切换工作区。",
            )
        if live_only:
            st.caption("生产环境已锁定真实 DeepSeek 与真实 Sepolia RPC；不会回退为离线 fixture。")
    config = (provider, evidence_label, workspace_id)
    if st.session_state.get("runtime_config") != config:
        reset_report_downloads(st)
        clear_scope_candidate(st.session_state)
        for key in (
            "runtime",
            "candidate",
            "task",
            "executions",
            "draft_error",
            "commitment_pairs",
            "uploaded_service",
            "uploaded_report_hash",
            "m10-next-service",
            "report-service",
            "report_snapshot_modes",
        ):
            st.session_state.pop(key, None)
        st.session_state.runtime_config = config
    if "runtime" not in st.session_state:
        restoring = False
        try:
            st.session_state.runtime = create_runtime(
                project_root=PROJECT_ROOT,
                session_id=workspace_id,
                provider=provider,
                evidence_mode=evidence_label,
            )
            restoring = True
            restored = st.session_state.runtime.m8_workflow.restore_latest()
            if restored is not None:
                st.session_state.task, st.session_state.executions, snapshots = restored
                st.session_state.commitment_pairs = [
                    (snapshot.task_commitment, snapshot.delivery_commitment, snapshot.expected_signer)
                    if snapshot is not None else None
                    for snapshot in snapshots
                ]
                st.session_state.restore_notice = True
        except (ConfigurationBlocked, ValueError, OSError) as error:
            st.session_state.pop("runtime", None)
            if restoring:
                st.error("已有工作区记录无法安全恢复，核对入口已阻塞。请保留工作区编号与历史，交由维护者检查。")
                with st.expander("查看工作区恢复的实际错误"):
                    st.write(str(error))
                st.caption("更换工作区只会开始独立新任务，不会修复或清除旧请求。这里不会自动重跑或删除记录。")
            else:
                st.error(str(error))
                if not live_only:
                    st.info("可明确选择离线演示进行练习；不会把演示当作真实证据。")
            return None
    return st.session_state.runtime


def _candidate_editor(runtime: AppRuntime) -> None:
    candidate = st.session_state.candidate
    manual = st.session_state.get("candidate_origin") == "manual"
    if manual:
        st.caption("手工范围尚未确认：请逐项填写，表单没有采纳报表中的观察范围，也没有调用模型。")
    if candidate.missing_fields and not manual:
        st.warning("缺失字段：" + "、".join(field.value for field in candidate.missing_fields))
    for issue in candidate.ambiguities:
        st.warning(f"歧义 · {issue.target.value}：{issue.description}")
    for question in candidate.clarification_questions:
        st.caption(f"待确认：{question}")

    with st.container(border=True, key="panel-scope"):
        st.info("待你确认：下面是整理后的核对条件，可直接修改。确认后才会锁定，不会自动开始核对。")
        with st.form("task_editor"):
            left, right = st.columns(2)
            with left:
                st.markdown("**链与资产**")
                chain_id = st.number_input(
                    "核对哪条链（链编号）", min_value=1, value=candidate.chain_id or 11_155_111,
                    help="Sepolia 测试链编号是 11155111；请确认与报表使用的链一致。",
                )
                token = st.text_input("核对哪种代币（合约地址）", value=candidate.token_address or "")
                start_block = st.number_input("起始区块（含）", min_value=0, value=candidate.start_block or 0)
                end_block = st.number_input("结束区块（含）", min_value=0, value=candidate.end_block or 0)
            with right:
                st.markdown("**参与账户与规则**")
                treasuries = st.text_area(
                    "资金账户（每行一个，最多两个）", value="\n".join(candidate.treasury_addresses or ())
                )
                recipients = st.text_area(
                    "资助对象（每行一个）", value="\n".join(candidate.recipient_addresses or ())
                )
                exclude_internal = st.checkbox(
                    "排除资金账户之间的内部互转", value=bool(candidate.exclusion_rules)
                )
                st.caption("本次最多核对 200 条相关记录；不会截断超限报表后当作完整结果。")
            st.divider()
            confirmed = st.checkbox("我已核对以上链、代币、账户、区块与排除规则，确认锁定此范围")
            submitted = st.form_submit_button("确认范围，继续", type="primary", use_container_width=True)

    if not submitted:
        return
    if st.session_state.get("candidate_origin") == "model" and not request_ready(
        st.session_state.get("candidate_request", ""), st.session_state.get("candidate_request_mode", RAW),
    ):
        st.error("任务未确认：请先补齐范围说明，不能锁定未填写的占位内容。")
        return
    if not confirmed:
        st.error("任务未确认：请先勾选任务边界确认框。")
        return
    payload = {
        "schema_version": "1.0",
        "candidate_id": candidate.candidate_id,
        "chain_id": int(chain_id),
        "token_address": token.strip() or None,
        "treasury_addresses": _lines(treasuries) or None,
        "recipient_addresses": _lines(recipients) or None,
        "start_block": int(start_block),
        "end_block": int(end_block),
        "exclusion_rules": (
            [
                ExclusionRule(
                    rule_id="exclude-treasury-internal",
                    rule_type=ExclusionRuleType.EXCLUDE_TREASURY_INTERNAL,
                    reason="Transfers between confirmed treasury accounts are not grants.",
                ).model_dump(mode="json")
            ]
            if exclude_internal
            else []
        ),
        "max_records": 200,
        "ambiguities": [],
        "missing_fields": [],
        "clarification_questions": [],
    }
    try:
        edited = TaskSpecCandidate.model_validate(payload)
        st.session_state.candidate = edited
        st.session_state.task = runtime.workflow.confirm_task(edited)
        st.session_state.executions = []
        st.rerun()
    except (ValidationError, ValueError) as error:
        st.error(f"任务未确认：{error}")
        st.info("请检查以上字段。范围通过校验后才会锁定；现在仍可修改。")


def _lines(value: str) -> list[str]:
    return [line.strip() for line in value.splitlines() if line.strip()]


def _task_summary() -> None:
    task = st.session_state.task
    st.markdown(
        '<div class="task-summary">'
        f'<div class="summary-cell"><small>任务编号</small><strong>{escape(str(task.task_id))}</strong></div>'
        f'<div class="summary-cell"><small>核对的链</small><strong>链编号 {task.chain_id}</strong></div>'
        '<div class="summary-cell"><small>区块范围（含边界）</small>'
        f'<strong>{task.start_block} — {task.end_block}</strong></div>'
        '</div>',
        unsafe_allow_html=True,
    )
    with st.expander("查看不可变任务指纹与完整边界"):
        st.code(task.spec_hash, language=None)
        st.json(task.model_dump(mode="json"))


def _run_attempt(runtime: AppRuntime, status) -> None:
    task = st.session_state.task
    executions = st.session_state.get("executions", [])
    view = attempt_view(status)
    can_run = view.next_attempt is not None
    repair_blocked = False
    if not can_run:
        st.caption("本任务已结束。核对记录已保留，不会被后续操作覆盖。")
        return
    with st.container(border=True, key="panel-execution"):
        left, right = st.columns((1.25, 1))
        with left:
            choices = tuple(runtime.services)
            uploaded_service = st.session_state.get("uploaded_service")
            restoring_upload = bool(executions and executions[0].submission.service_id == "uploaded-report-intake")
            if uploaded_service is not None or restoring_upload:
                choices = ("已上传报表 · 作者签名未验证",)
            if "report-service" not in st.session_state and st.session_state.get("m10-next-service"):
                selected_id = st.session_state["m10-next-service"]
                selected_label = next(
                    (label for label, service in runtime.services.items() if service.service_id == selected_id), None,
                )
                if selected_label in choices:
                    st.session_state["report-service"] = selected_label
            if st.session_state.get("report-service") not in choices:
                st.session_state.pop("report-service", None)
            if uploaded_service is not None or restoring_upload:
                service_label = choices[0]
                st.caption("将核对你已上传的报表。作者身份未经外部签名验证。")
            else:
                service_label = st.radio("选择要核对的报表", choices, horizontal=True, key="report-service")
            if executions:
                repaired = st.file_uploader(
                    "上传修正版报表（JSON / CSV / XLSX，最后一次）",
                    type=("json", "csv", "xlsx"), max_upload_size=1, key="repair-upload",
                )
                if repaired is not None:
                    repair_payload = render_report_intake(
                        st, repaired, directory=runtime.upload_directory,
                        namespace=f"{st.session_state.workspace_id}:repair:{task.task_id}",
                        recognizer=runtime.report_recognizer, provider=st.session_state.provider,
                    )
                    # A selected but unreadable repair must not fall back to the original.
                    uploaded_service = None
                    can_run = repair_payload is not None
                    repair_blocked = not can_run
                    if repair_payload is not None:
                        try:
                            uploaded_service = UploadedReportService(
                                repair_payload, private_directory=runtime.upload_directory,
                            )
                            st.caption("本次将验收上传的修复报表；本地接收签名不证明原作者身份。")
                        except (ValueError, OSError):
                            st.error("修复报表未通过严格 JSON 校验或私有留档；请检查字段、金额整数与记录上限。")
                            can_run = False
                            repair_blocked = True
                else:
                    render_report_intake(
                        st, None, directory=runtime.upload_directory,
                        namespace=f"{st.session_state.workspace_id}:repair:{task.task_id}",
                    )
                if restoring_upload and uploaded_service is None and repaired is None:
                    st.info("原上传任务已恢复。请上传修复报表后再提交；不会替换成演示服务报表。")
                    can_run = False
                if (
                    restoring_upload and repaired is None
                    and executions[-1].result.outcome is VerificationOutcome.FAIL
                    and getattr(uploaded_service, "service_id", None) == "uploaded-report-intake"
                ):
                    st.caption("请先上传修正版；不会直接拿原报表消耗最后一次补交机会。")
                    can_run = False
            st.caption("服务提交的是待验报告；最终金额与结论仍由独立证据和确定性引擎产生。")
        with right:
            button_label = "开始核对" if view.next_attempt == 1 else "核对修正版（最后一次）"
            if st.button(
                button_label, type="secondary" if repair_blocked else "primary",
                disabled=not can_run, use_container_width=True,
            ):
                try:
                    fresh = runtime.m8_workflow.get_attempt_status(task.task_id)
                    if fresh.next_attempt != view.next_attempt:
                        raise ValueError("后台核对状态已变化，本次没有重复发起。请查看刷新后的状态。")
                    with st.spinner("正在读取独立链上证据并核对报表，随后生成回执与差异说明…"):
                        service = uploaded_service or runtime.services[service_label]
                        execution, snapshot = runtime.m8_workflow.run_attempt(task, service)
                    st.session_state.executions = [*executions, execution]
                    modes = dict(st.session_state.get("report_snapshot_modes", {}))
                    modes[execution.receipt.receipt_hash] = (
                        "live_rpc" if runtime.evidence_label.startswith("真实 Sepolia RPC") else "fixture"
                    )
                    st.session_state.report_snapshot_modes = modes
                    pairs = st.session_state.get("commitment_pairs", [])
                    st.session_state.commitment_pairs = [
                        *pairs,
                        (snapshot.task_commitment, snapshot.delivery_commitment, snapshot.expected_signer),
                    ]
                    st.session_state.pop("attempt_error", None)
                    st.rerun()
                except Exception as error:
                    st.session_state.attempt_error = (task.task_id, str(error))
                    # Rerender from persisted state; this never retries execution.
                    st.rerun()


def _replace_execution_receipt(index: int, receipt) -> None:
    executions = list(st.session_state.executions)
    modes = dict(st.session_state.get("report_snapshot_modes", {}))
    old_hash = executions[index].receipt.receipt_hash
    if old_hash in modes:
        modes[receipt.receipt_hash] = modes[old_hash]
        st.session_state.report_snapshot_modes = modes
    executions[index] = replace(executions[index], receipt=receipt)
    st.session_state.executions = executions


def _render_publication(runtime: AppRuntime, execution, index: int, m9_artifacts) -> None:
    control_key = f"{index}:{execution.receipt.receipt_hash}"
    publication = execution.receipt.publication
    st.caption(runtime.publication_status)
    if publication.uri:
        st.code(publication.uri, language=None)
        st.caption(f"公开内容 SHA-256：{publication.content_hash}")
        verification_key = f"public-verification-{index}-{execution.receipt.receipt_hash}"
        if st.button(
            "独立重放公开回执",
            key=f"verify-public-{control_key}",
            disabled=runtime.publisher is None,
            use_container_width=True,
        ):
            reference = PublicReceiptReference(PublicReferenceKind.URI, publication.uri)
            resolver = PublisherReceiptResolver(runtime.publisher, execution.receipt, attempt=index + 1)
            st.session_state[verification_key] = verify_public_reference(
                reference,
                resolver,
            )
        if runtime.publisher is None:
            st.info("当前运行配置没有对应公共存储读取器，无法重新下载公开字节。")
        if verification_key in st.session_state:
            render_public_verification(st, st.session_state[verification_key])
    if publication.chain_status is PublicationChainStatus.FAILED:
        st.error(f"发布/链上状态 FAILED：{publication.error_code} · {publication.error_message or ''}")
        authorized = st.checkbox("我已核对失败原因并授权重新准备", key=f"recover-{control_key}")
        if st.button(
            "恢复为 NOT_SUBMITTED",
            key=f"recover-button-{control_key}",
            disabled=not authorized,
            use_container_width=True,
        ):
            try:
                recovered = runtime.publication_workflow.recover_failed(
                    execution.receipt, authorized=authorized
                )
                _replace_execution_receipt(index, recovered)
                st.rerun()
            except Exception as error:
                st.error(f"失败状态不能恢复：{error}")
        return
    if publication.uri is None:
        authorized = st.checkbox(
            "我授权公开这份脱敏 JSON 回执",
            key=f"publish-authorized-{control_key}",
        )
        if st.button(
            "发布公开 JSON 回执",
            key=f"publish-{control_key}",
            disabled=runtime.publisher is None or not authorized,
            use_container_width=True,
        ):
            try:
                published, _ = runtime.publication_workflow.publish(
                    execution.receipt,
                    runtime.publisher,
                    authorized=authorized,
                )
                _replace_execution_receipt(index, published)
                st.rerun()
            except Exception as error:
                st.error(f"公共发布失败：{error}")
        return
    st.caption(runtime.feedback_status)
    if publication.chain_status is PublicationChainStatus.NOT_SUBMITTED:
        authorized = st.checkbox(
            "我授权向 Sepolia ERC-8004 提交此 URI 与内容哈希",
            key=f"chain-authorized-{control_key}",
        )
        if st.button(
            "提交 ERC-8004 反馈",
            key=f"chain-submit-{control_key}",
            disabled=runtime.feedback_adapter is None or not authorized,
            use_container_width=True,
        ):
            try:
                submitted = runtime.publication_workflow.submit_feedback(
                    execution.receipt,
                    runtime.feedback_adapter,
                    authorized=authorized,
                )
                _replace_execution_receipt(index, submitted)
                st.rerun()
            except Exception as error:
                st.error(f"链上提交被安全边界拒绝：{error}")
    elif publication.chain_status is PublicationChainStatus.SUBMITTED:
        st.warning("交易已提交或广播结果未知；系统不会自动重发。请只执行读回核验。")
        if publication.transaction_hash:
            st.code(publication.transaction_hash, language=None)
        if st.button(
            "从链上读回并核验",
            key=f"chain-reconcile-{control_key}",
            disabled=runtime.feedback_adapter is None,
            use_container_width=True,
        ):
            try:
                reconciled = runtime.publication_workflow.reconcile_feedback(
                    execution.receipt, runtime.feedback_adapter
                )
                _replace_execution_receipt(index, reconciled)
                st.rerun()
            except Exception as error:
                st.error(f"链上读回失败：{error}")
    elif publication.chain_status is PublicationChainStatus.CONFIRMED:
        st.success(
            f"ERC-8004 已确认并读回一致 · block {publication.block_number} · "
            f"feedback #{publication.feedback_index}"
        )


def _render_attempts(runtime: AppRuntime, status) -> None:
    executions = st.session_state.get("executions", [])
    if not executions:
        return
    state = attempt_view(status)
    allow_actions = state.next_attempt is not None or state.can_start_next_task
    try:
        artifacts = build_m9_artifacts(
            executions, st.session_state.get("commitment_pairs", []), runtime.revision_store,
        )
        current = executions[-1]
        before = executions[0] if len(executions) == 2 else None
        report = build_business_report(
            current.receipt, current.submission, fund_flow=current.fund_flow,
            previous=ReportAttemptInput(before.receipt, before.submission, before.fund_flow) if before else None,
            revisions=artifacts.revisions if before else (),
            source_mode=st.session_state.get("report_snapshot_modes", {}).get(current.receipt.receipt_hash, "recorded"),
        )
    except ValueError:
        reset_report_downloads(st)
        st.error("报告与原回执的绑定未通过校验。请保留历史并联系维护者，不会生成新的核验结论。")
        return
    render_business_report(
        st, report, graph=render_report_graph, exports=document_exporters(),
        receipt_json=json.dumps(current.receipt.model_dump(mode="json"), ensure_ascii=False, indent=2),
    )
    if (
        allow_actions and report.outcome is VerificationOutcome.PASS and current.receipt.publication.uri is None
        and st.button(
            "预览回执与分享选项", type="primary", key=f"preview-publication-{len(executions)}",
            use_container_width=True,
        )
    ):
        st.session_state["report-evidence-section"] = "分享与公开验证"
        st.session_state["show-report-evidence"] = True
        st.rerun()
    render_report_evidence(
        st, runtime, executions, artifacts, allow_actions=allow_actions, publish=_render_publication, report=report,
    )


def _draft_task(runtime: AppRuntime) -> bool:
    preserve_scope_inputs(st.session_state)
    _section("上传报表", "上传 CSV、Excel .xlsx 或 JSON，系统自动读取并识别报表。")
    panel = (
        st.expander("已读取的报表与原范围说明", expanded=False)
        if "candidate" in st.session_state else st.container(border=True, key="panel-input")
    )
    with panel:
        with st.expander("没有报表？使用案例或模板", expanded=False):
            input_mode = st.selectbox(
                "先选一份报表",
                ("上传自己的报表", "加载真实 Sepolia 案例", "加载契约测试示例"),
                key="intake-mode",
                format_func=lambda mode: {
                    "上传自己的报表": "使用我上传的报表",
                    "加载真实 Sepolia 案例": "用真实交易案例试一遍",
                    "加载契约测试示例": "离线练习（模拟数据）",
                }[mode],
                help="这里选择案例来源，不是文件格式。上传文件无需选择此项。",
            )
            st.download_button(
                "下载严格 JSON 空白模板", data=strict_template_bytes(),
                file_name="uploaded-report-template.json", mime="application/json",
                use_container_width=True,
            )
        real_case = load_real_case(PROJECT_ROOT)
        with st.expander("下载示例报表与核验范围"):
            st.caption("团队为演示构造报表，引用真实公开 Sepolia 交易；账户角色为演示设定。")
            for report_label, report_data, filename in (
                ("下载真实案例错误版 JSON", real_case.error_report, "error-missing-transfer.json"),
                ("下载真实案例修正版 JSON", real_case.corrected_report, "corrected-complete.json"),
            ):
                st.download_button(report_label, report_data, filename, "application/json")
            st.json(real_case.candidate.model_dump(mode="json"))
        uploaded = st.file_uploader(
            "服务商报表",
            type=("json", "csv", "xlsx"),
            accept_multiple_files=False,
            max_upload_size=1,
            disabled=input_mode != "上传自己的报表",
        )
        upload_valid = True
        with st.expander("查看上传格式与身份说明"):
            st.caption("表格限制：1 MB、200 行、64 列；XLSX 仅单工作表，金额为文本，不支持公式、宏或外部链接。")
            st.caption("合并单元格也不支持；请把表头和明细整理为逐行逐列的原始值。")
            st.caption("支持 CSV、Excel .xlsx、JSON；旧 .xls 不支持。自动识别不认证作者，也不代表链上通过。")
            st.caption("JSON 报表必填字段：schema_version、claimed_total_base_units、claimed_count、transfers。")
            st.json(UploadedReport.model_json_schema())
            st.caption("无签名报表使用本地接收身份留档；不表示外部作者或 ERC-8004 服务 owner 已签名。")
        payload = None
        report_name = None
        if input_mode == "加载真实 Sepolia 案例":
            payload = real_case.error_report
            report_name = "真实 Sepolia 案例错误版（团队构造报表）"
            st.caption("下一步预填案例范围供你修改和确认；实时参考证据只从 Sepolia RPC 获取。")
            if not runtime.evidence_label.startswith("真实 Sepolia RPC"):
                upload_valid = False
                st.info("此案例需要真实链上证据。请展开高级设置，将独立证据切换为“真实 Sepolia RPC”。")
        elif input_mode == "加载契约测试示例":
            payload = contract_example_bytes(PROJECT_ROOT)
            report_name = "契约测试示例（人工标注合成数据，非 M11 真实案例）"
        elif uploaded is not None:
            payload = render_report_intake(
                st, uploaded, directory=runtime.upload_directory,
                namespace=f"{st.session_state.workspace_id}:first",
                recognizer=runtime.report_recognizer, provider=st.session_state.provider,
            )
            report_name = uploaded.name
        else:
            render_report_intake(
                st, None, directory=runtime.upload_directory,
                namespace=f"{st.session_state.workspace_id}:first",
            )
        candidate_source = (input_mode, content_hash(payload) if payload else None)
        if st.session_state.get("candidate_source") != candidate_source:
            clear_scope_candidate(st.session_state)
            st.session_state.candidate_source = candidate_source
        if payload is not None:
            try:
                digest = content_hash(payload)
                if (
                    st.session_state.get("uploaded_report_hash") != digest
                    or "uploaded_service" not in st.session_state
                ):
                    st.session_state.uploaded_service = UploadedReportService(
                        payload, private_directory=runtime.upload_directory,
                    )
                    st.session_state.uploaded_report_hash = digest
                if uploaded is None:
                    st.write(f"已读取：{report_name}")
                with st.expander("查看报表留档指纹"):
                    st.code(digest, language=None)
                st.caption("原报表和读取来源已私有留档；下一步确认核验范围，不会自动开始核对。")
            except (ValueError, OSError):
                upload_valid = False
                st.session_state.pop("uploaded_service", None)
                st.session_state.pop("uploaded_report_hash", None)
                st.error(
                    "报表未通过严格 JSON 校验或私有留档：请检查完整字段、整数金额、service 来源与最多 200 条记录。"
                )
        else:
            st.session_state.pop("uploaded_service", None)
            st.session_state.pop("uploaded_report_hash", None)
            if input_mode == "上传自己的报表":
                upload_valid = False
                st.caption("请选择报表；读取失败或必要条件未明确时不能继续，不会用样例替代。")
        default_request = (
            "" if input_mode == "上传自己的报表" else (
            f"核对 Sepolia 案例在区块 {real_case.candidate.start_block} 的转账；下一步可修改所有范围字段。"
            if input_mode == "加载真实 Sepolia 案例" else
            "核对 Sepolia 上两个资金账户在区块 1000–1010 对两个资助对象的代币拨款，排除内部互转。"
            )
        )
        if input_mode == "上传自己的报表":
            request, ready = render_scope_request(st)
        else:
            if not st.session_state.get("scope-example-request"):
                st.session_state["scope-example-request"] = default_request
            request = st.text_area(
                "说明要核对的范围", value=None,
                placeholder="说明链、代币、付款与收款账户、起止区块，以及是否排除内部互转。",
                height=130, key="scope-example-request", disabled=input_mode == "加载真实 Sepolia 案例",
                help="这里不会直接触发链上操作；系统先生成一份可修改候选。",
            ) or ""
            ready = True
        render_scope_actions(
            st, runtime, request, valid_report=upload_valid,
            example=real_case.candidate if input_mode == "加载真实 Sepolia 案例" else None,
            request_ready=ready,
            request_mode=st.session_state["scope-request-mode"] if input_mode == "上传自己的报表" else RAW,
        )
    return upload_valid


def main() -> None:
    st.set_page_config(
        page_title="TreasuryTally · 链上验收工作台",
        page_icon=str(LOGO_PATH),
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    render_onboarding(st)
    # Pure CSS/HTML must not wait for the Markdown component's parsing dependency.
    st.html(APP_CSS)
    _product_header()
    if st.query_params.get("verify") == "1":
        render_public_explorer(st, PROJECT_ROOT)
        return
    runtime = _runtime()
    if runtime is None:
        return
    if st.session_state.pop("restore_notice", False):
        st.info("已恢复上次的范围与核对记录；历史 AI 说明没有重新生成。")
    with st.expander("历史记录与独立验证", expanded=False):
        st.link_button("打开独立公开验证页", "?verify=1")
        render_workspace_history(st, runtime)

    if "task" not in st.session_state:
        input_valid = _draft_task(runtime)
        if input_valid and "candidate" in st.session_state:
            _section("确认要核对的范围", "请逐项检查下面的条件。确认后才进入核对步骤。")
            _candidate_editor(runtime)
        return

    if not st.session_state.get("executions"):
        _section("核验范围已确认", "链、资产、账户与区块范围已经锁定。")
        _task_summary()
    try:
        status = refresh_task_view(st, runtime, st.session_state.task)
    except Exception as error:
        st.error("无法安全读取或恢复后台记录，核对入口已阻塞。现有历史不会被删除，也不会自动重试。")
        with st.expander("查看状态读取或恢复错误"):
            st.write(str(error))
        return
    view = render_attempt_state(st, status)
    attempt_error = st.session_state.get("attempt_error")
    if attempt_error and attempt_error[0] == st.session_state.task.task_id:
        st.error("上次核对操作没有完成；页面已重新读取后台状态。请按当前状态处理，不会自动重试。")
        with st.expander("查看上次操作的实际错误", expanded=False):
            st.write(attempt_error[1])
    executions = st.session_state.get("executions", [])
    if view.next_attempt == 1:
        _section("开始核对", "范围已锁定。点击后才会读取证据、核对报表并生成回执。")
        _run_attempt(runtime, status)
    else:
        if executions:
            _render_attempts(runtime, status)
        if view.next_attempt == 2:
            _section("核对修正版", "请先看清差异或证据问题，再使用唯一一次补交机会。")
            _run_attempt(runtime, status)
    if (
        view.can_start_next_task
        and st.button("开始下一次报表验收", key="m10-next-task")
    ):
        reset_report_downloads(st)
        clear_scope_candidate(st.session_state)
        for key in (
            "task", "candidate", "executions", "commitment_pairs", "uploaded_service", "uploaded_report_hash",
            "attempt_error",
        ):
            st.session_state.pop(key, None)
        st.rerun()


if __name__ == "__main__":
    main()
