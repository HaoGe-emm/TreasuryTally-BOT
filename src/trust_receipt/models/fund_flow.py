"""Read-only fund-flow projection contract for page adapters."""

from __future__ import annotations

from pydantic import Field, StrictInt

from trust_receipt.models.base import (
    DecimalIntegerString,
    DomainModel,
    EventKey,
    EvmAddress,
    Identifier,
)
from trust_receipt.models.enums import FundFlowNodeRole, FundFlowVisualStatus, VerificationOutcome
from trust_receipt.models.transfers import TransferRecord


class FundFlowNode(DomainModel):
    node_id: Identifier
    address: EvmAddress
    role: FundFlowNodeRole
    label: Identifier


class FundFlowEdge(DomainModel):
    edge_id: Identifier
    from_node_id: Identifier
    to_node_id: Identifier
    event_key: EventKey
    amount_base_units: DecimalIntegerString
    token_decimals: StrictInt = Field(ge=0, le=255)
    status: FundFlowVisualStatus
    service_refs: tuple[Identifier, ...]
    reference_refs: tuple[Identifier, ...]
    finding_ids: tuple[Identifier, ...]
    service_records: tuple[TransferRecord, ...] = ()
    reference_records: tuple[TransferRecord, ...] = ()


class FundFlowProjection(DomainModel):
    task_id: Identifier
    attempt: StrictInt = Field(ge=1, le=2)
    claimed_total_base_units: DecimalIntegerString
    calculated_total_base_units: DecimalIntegerString | None
    outcome: VerificationOutcome
    nodes: tuple[FundFlowNode, ...]
    edges: tuple[FundFlowEdge, ...]
