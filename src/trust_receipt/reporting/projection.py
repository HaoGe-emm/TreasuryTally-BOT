"""Receipt-bound read model; no event reaggregation, model calls, or writes."""
# ruff: noqa: RUF001

from __future__ import annotations

import re
from typing import Literal

from trust_receipt.hashing import verify_submission_hash
from trust_receipt.m9.models import ReceiptRevision
from trust_receipt.m9.revisions import validate_revision_pair, verify_receipt_revision_hash
from trust_receipt.models import FundFlowProjection, Receipt, ServiceSubmission
from trust_receipt.receipts.replay import replay_receipt
from trust_receipt.reporting.evidence_reasons import inconclusive_explanation
from trust_receipt.reporting.formatting import address_view, format_amount
from trust_receipt.reporting.models import (
    AttemptReport,
    BusinessReportView,
    FindingView,
    FlowRow,
    LegendItem,
    ReportAttemptInput,
    ScopeView,
    SourceView,
)
from trust_receipt.reporting.text import FINDING_TEXT, FLOW_TEXT, OUTCOME_LABELS


def _safe_refs(refs: tuple[str, ...]) -> tuple[str, ...]:
    # Never copy evidence URLs (possibly credentialed RPC), paths or free-form notes.
    return tuple(
        ref for ref in refs if re.fullmatch(r"(?:service|rpc|blockscout):[0-9]+:0x[0-9a-fA-F]{64}:[0-9]+", ref)
    )


def _attempt(receipt: Receipt, submission: ServiceSubmission, flow: FundFlowProjection | None) -> AttemptReport:
    if not replay_receipt(receipt).valid or not verify_submission_hash(submission):
        raise ValueError("business report requires valid receipt and submission integrity")
    result = receipt.verification_result
    token_short = address_view(receipt.task_spec.token_address).short

    def amount(value: str, decimals: int | None, *, signed: bool = False, token: str | None = None):
        formatted = format_amount(value, decimals, signed=signed)
        short = address_view(token).short if token else token_short
        unit = f"{short} 代币" if decimals is not None else f"{short} 最小单位"
        return formatted.model_copy(update={"unit": unit})

    if (
        submission.report_hash != receipt.submission_hash
        or submission.submission_id != result.submission_id
        or submission.task_id != receipt.task_spec.task_id
        or submission.service_id != receipt.service_identity.service_id
    ):
        raise ValueError("submission is not bound to this receipt")
    if flow is not None and (
        flow.task_id != submission.task_id
        or flow.attempt != submission.attempt
        or flow.outcome != result.outcome
        or flow.claimed_total_base_units != submission.claimed_total_base_units
        or flow.calculated_total_base_units != result.calculated_total_base_units
    ):
        raise ValueError("fund flow is not bound to this receipt result")
    reference_decimals = {
        record.token_decimals
        for edge in (flow.edges if flow else ())
        for record in edge.reference_records
        if record.token_address.lower() == receipt.task_spec.token_address.lower()
    }
    claimed_decimals = {record.token_decimals for record in submission.transfers}
    verified_decimals = next(iter(reference_decimals)) if len(reference_decimals) == 1 else None
    declared_tokens = {record.token_address.lower() for record in submission.transfers}
    wrong_asset = bool(declared_tokens - {receipt.task_spec.token_address.lower()})
    wrong_precision = any(f.finding_type.value == "DECIMAL_ERROR" for f in result.findings if f.is_confirmed_error)
    precision_confirmed = (
        verified_decimals is not None and claimed_decimals <= {verified_decimals} and not wrong_precision
    )
    claimed = amount(submission.claimed_total_base_units, verified_decimals if precision_confirmed else None)
    if wrong_asset:
        claimed = format_amount(submission.claimed_total_base_units, None).model_copy(
            update={
                "unit": "报表声明最小单位 资产未确认" + (" 混合代币" if len(declared_tokens) > 1 else " 含其他代币")
            }
        )
    elif not precision_confirmed:
        claimed = claimed.model_copy(update={"unit": "报表声明最小单位 精度未确认"})
    comparable = (
        result.reference_complete
        and result.evidence_sufficient
        and result.calculated_total_base_units is not None
        and not wrong_asset
        and len(claimed_decimals) <= 1
        and len(reference_decimals) <= 1
        and (not claimed_decimals or not reference_decimals or claimed_decimals == reference_decimals)
        and not any(
            f.finding_type.value in {"DECIMAL_ERROR", "WRONG_TOKEN"} for f in result.findings if f.is_confirmed_error
        )
    )
    reason = (
        None
        if comparable
        else (
            "参考不完整或证据不足，金额不能作为最终可比值。"
            if not result.reference_complete or not result.evidence_sufficient
            else "币种或代币精度不一致，差额不可直接比较。"
        )
    )
    findings = []
    for finding in result.findings:
        title, description, advice = FINDING_TEXT[finding.finding_type.value]
        if finding.expected and finding.actual:
            fields = (
                ("total_base_units", "总额最小单位"),
                ("amount_base_units", "事件金额最小单位"),
                ("count", "记录数"),
                ("token_decimals", "代币精度"),
            )
            facts = []
            for key, label in fields:
                expected, actual = finding.expected.get(key), finding.actual.get(key)
                if (
                    type(expected) in {int, str}
                    and type(actual) in {int, str}
                    and re.fullmatch(r"[0-9]+", str(expected))
                    and re.fullmatch(r"[0-9]+", str(actual))
                ):
                    if key in {"total_base_units", "amount_base_units"} and precision_confirmed and not wrong_asset:
                        expected_amount = amount(str(int(expected)), verified_decimals)
                        actual_amount = amount(str(int(actual)), verified_decimals)
                        label = "总额" if key == "total_base_units" else "事件金额"
                        facts.append(
                            f"{label}：核验 {expected_amount.display} {expected_amount.unit}，"
                            f"报表 {actual_amount.display} {actual_amount.unit}。"
                        )
                    else:
                        facts.append(f"{label}：核验 {expected}，报表 {actual}。")
            description += "".join(facts)
        confirmed = finding.status.value == "confirmed"
        findings.append(
            FindingView(
                finding_id=finding.finding_id,
                finding_type=finding.finding_type.value,
                title=title,
                description=description if confirmed else "该项仅是待核实线索，尚未确认为错误。",
                recommendation=advice if confirmed else "补充证据或人工确认，不据此要求确定性返工。",
                confirmed=confirmed,
                severity=finding.severity.value,
                evidence_refs=_safe_refs(finding.evidence_refs),
            )
        )
    rows = []
    nodes = {node.node_id: node for node in flow.nodes} if flow else {}
    for edge in flow.edges if flow else ():
        label, _ = FLOW_TEXT[edge.status.value]
        if edge.from_node_id not in nodes or edge.to_node_id not in nodes:
            raise ValueError("fund flow contains an unresolved account")
        records = edge.reference_records or edge.service_records
        record = records[0] if records else None
        row_token = record.token_address if record else receipt.task_spec.token_address
        row_precision = (
            verified_decimals
            if row_token.lower() == receipt.task_spec.token_address.lower()
            and edge.token_decimals == verified_decimals
            else None
        )
        row_amount = amount(edge.amount_base_units, row_precision, token=row_token)
        if row_precision is None:
            row_amount = row_amount.model_copy(update={"unit": row_amount.unit + " 精度未确认"})
        rows.append(
            FlowRow(
                edge_id=edge.edge_id,
                sender=address_view(nodes[edge.from_node_id].address),
                recipient=address_view(nodes[edge.to_node_id].address),
                amount=row_amount,
                status=edge.status.value,
                status_label=label,
                event_ref=f"{edge.event_key[0]}:{edge.event_key[1]}:{edge.event_key[2]}",
                source_label="报表声明与参考"
                if edge.service_records and edge.reference_records
                else ("仅参考事件" if edge.reference_records else "仅报表声明"),
                finding_ids=edge.finding_ids,
            )
        )
    sources = tuple(
        SourceView(
            source=source.source.value,
            label="RPC 参考" if source.source.value == "rpc" else "Blockscout 参考",
            complete=source.complete,
            retrieved_at=source.retrieved_at,
        )
        for source in result.reference_sources
    )
    uncertainties = []
    if explanation := inconclusive_explanation(result):
        uncertainties.append(explanation)
    if verified_decimals is None:
        uncertainties.append("没有唯一可信的代币精度，核验金额以最小单位显示。")
    if flow is None:
        uncertainties.append("本次未提供已保存的资金流投影，未重取链上数据或构造历史图。")
    if any(not f.confirmed for f in findings):
        uncertainties.append("待核实线索与已确认差异分开，不作为确定性错误。")
    return AttemptReport(
        attempt=submission.attempt,
        outcome=result.outcome,
        outcome_label=OUTCOME_LABELS[result.outcome.value],
        service_id=submission.service_id,
        identity_label="本地接收封装 不认证原作者"
        if receipt.service_identity.identity_scheme == "local-upload-intake"
        else "回执记录的服务身份",
        receipt_hash=receipt.receipt_hash,
        claimed=claimed,
        calculated=amount(result.calculated_total_base_units, verified_decimals)
        if result.calculated_total_base_units is not None
        else None,
        difference=amount(
            str(int(submission.claimed_total_base_units) - int(result.calculated_total_base_units)),
            verified_decimals,
            signed=True,
        )
        if comparable
        else None,
        difference_reason=reason,
        claimed_count=submission.claimed_count,
        calculated_count=result.calculated_count,
        findings=tuple(findings),
        uncertainties=tuple(uncertainties),
        sources=sources,
        evidence_as_of=max((s.retrieved_at for s in sources), default=None),
        flow_rows=tuple(rows),
        graph_available=flow is not None,
    )


def build_business_report(
    receipt: Receipt,
    submission: ServiceSubmission,
    *,
    fund_flow: FundFlowProjection | None = None,
    previous: ReportAttemptInput | None = None,
    revisions: tuple[ReceiptRevision, ...] = (),
    source_mode: Literal["recorded", "fixture", "live_rpc"] = "recorded",
) -> BusinessReportView:
    current = _attempt(receipt, submission, fund_flow)
    before = _attempt(previous.receipt, previous.submission, previous.fund_flow) if previous else None
    repair_verified = False
    repair_label = None
    if previous:
        if (
            previous.receipt.task_spec.spec_hash != receipt.task_spec.spec_hash
            or before.attempt != 1
            or current.attempt != 2
            or before.outcome.value == "PASS"
        ):
            raise ValueError("comparison requires the same task and eligible consecutive attempts")
        repair_label = "两次交付已保留 修复关系未核实"
        if revisions:
            if len(revisions) != 2:
                raise ValueError("comparison requires both receipt revisions")
            validate_revision_pair(*revisions)
            for revision, attempt in zip(revisions, (before, current), strict=True):
                if not verify_receipt_revision_hash(revision) or (
                    revision.receipt_hash != attempt.receipt_hash
                    or revision.outcome != attempt.outcome
                    or revision.service_id != attempt.service_id
                    or revision.task_id != receipt.task_spec.task_id
                ):
                    raise ValueError("revision does not bind the displayed attempt")
            repair_verified = True
            repair_label = (
                "修复后符合范围 原始结果保留" if current.outcome.value == "PASS" else "补交后仍未通过 原始结果保留"
            )
    elif revisions:
        raise ValueError("revision comparison requires the previous receipt")
    task = receipt.task_spec
    scope = ScopeView(
        chain_id=task.chain_id,
        token=address_view(task.token_address),
        treasuries=tuple(address_view(a) for a in task.treasury_addresses),
        recipients=tuple(address_view(a) for a in task.recipient_addresses),
        start_block=task.start_block,
        end_block=task.end_block,
        exclusions=tuple("排除资金账户之间的内部互转" for _ in task.exclusion_rules),
        summary=(
            f"链 {task.chain_id}，区块 {task.start_block:,} 至 {task.end_block:,}（含两端）。仅核对已确认代币与账户。"
        ),
    )
    next_step = {
        "PASS": "保存报告与原 JSON 回执，按原回执引用独立复核。",
        "FAIL": "按已确认差异修正报表，补交次数以下方可用操作为准。",
        "INCONCLUSIVE": "先检查证据来源与范围完整性，再决定是否主动重新核对。",
    }[current.outcome.value]
    if current.attempt == 2 and current.outcome.value != "PASS":
        next_step = "本任务两次交付已用完；保留报告并人工复核，不再发起第三次验收。"
    return BusinessReportView(
        task_id=task.task_id,
        spec_hash=task.spec_hash,
        conclusion=OUTCOME_LABELS[current.outcome.value],
        outcome=current.outcome,
        next_step=next_step,
        scope=scope,
        source_mode=source_mode,
        source_mode_label={
            "recorded": "已记录证据快照 未重新取链上数据",
            "fixture": "离线构造样例 非真实链上验收",
            "live_rpc": "真实 RPC 核验的已保存快照",
        }[source_mode],
        current=current,
        previous=before,
        repair_label=repair_label,
        repair_verified=repair_verified,
        legend=tuple(
            LegendItem(status=status, label=label, meaning=meaning) for status, (label, meaning) in FLOW_TEXT.items()
        ),
        limitations=("结论仅适用于已确认范围和原证据时点，不代表全面审计、合规认证或付款授权。",),
    )
