"""Immutable business reading copy; never part of the signed receipt schema."""
# ruff: noqa: RUF001

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from pydantic import StrictBool, StrictInt

from trust_receipt.models import FundFlowProjection, Receipt, ServiceSubmission, VerificationOutcome
from trust_receipt.models.base import DomainModel, UtcDatetime


class AddressView(DomainModel):
    full: str
    short: str


class AmountView(DomainModel):
    base_units: str
    display: str
    unit: str
    decimals: StrictInt | None


class ScopeView(DomainModel):
    chain_id: StrictInt
    token: AddressView
    treasuries: tuple[AddressView, ...]
    recipients: tuple[AddressView, ...]
    start_block: StrictInt
    end_block: StrictInt
    exclusions: tuple[str, ...]
    summary: str


class SourceView(DomainModel):
    source: str
    label: str
    complete: StrictBool
    retrieved_at: UtcDatetime


class FindingView(DomainModel):
    finding_id: str
    finding_type: str
    title: str
    description: str
    recommendation: str
    confirmed: StrictBool
    severity: str
    evidence_refs: tuple[str, ...]


class FlowRow(DomainModel):
    edge_id: str
    sender: AddressView
    recipient: AddressView
    amount: AmountView
    status: str
    status_label: str
    event_ref: str
    source_label: str
    finding_ids: tuple[str, ...]


class LegendItem(DomainModel):
    status: str
    label: str
    meaning: str


class AttemptReport(DomainModel):
    attempt: StrictInt
    outcome: VerificationOutcome
    outcome_label: str
    service_id: str
    identity_label: str
    receipt_hash: str
    claimed: AmountView
    calculated: AmountView | None
    difference: AmountView | None
    difference_reason: str | None
    claimed_count: StrictInt
    calculated_count: StrictInt | None
    findings: tuple[FindingView, ...]
    uncertainties: tuple[str, ...]
    sources: tuple[SourceView, ...]
    evidence_as_of: UtcDatetime | None
    flow_rows: tuple[FlowRow, ...]
    graph_available: StrictBool


class BusinessReportView(DomainModel):
    view_version: Literal["1.0"] = "1.0"
    title: str = "TreasuryTally 链上报表核验报告"
    task_id: str
    spec_hash: str
    conclusion: str
    outcome: VerificationOutcome
    next_step: str
    scope: ScopeView
    source_mode: Literal["recorded", "fixture", "live_rpc"]
    source_mode_label: str
    current: AttemptReport
    previous: AttemptReport | None
    repair_label: str | None
    repair_verified: StrictBool
    legend: tuple[LegendItem, ...]
    limitations: tuple[str, ...]
    notice: str = (
        "本报告是原验收结果的业务阅读副本，不是新的签名回执；复核请使用原 JSON 回执。下载不代表公开发布或写链授权。"
    )


@dataclass(frozen=True)
class ReportAttemptInput:
    receipt: Receipt
    submission: ServiceSubmission
    fund_flow: FundFlowProjection | None = None
