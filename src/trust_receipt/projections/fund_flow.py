"""Project source-labelled transfers and Findings without recomputing the result."""

from __future__ import annotations

from collections import defaultdict

from trust_receipt.models import (
    FindingType,
    FundFlowEdge,
    FundFlowNode,
    FundFlowNodeRole,
    FundFlowProjection,
    FundFlowVisualStatus,
    ServiceSubmission,
    TaskSpec,
    VerificationOutcome,
    VerificationResult,
)
from trust_receipt.models.transfers import TransferRecord
from trust_receipt.verification import ReferenceEvidence
from trust_receipt.verification.evidence import collect_reference
from trust_receipt.verification.normalization import address_key, event_key, event_ref
from trust_receipt.verification.scope import scope_violation


def _node_role(task: TaskSpec, address: str) -> FundFlowNodeRole:
    key = address_key(address)
    if key in {address_key(item) for item in task.treasury_addresses}:
        return FundFlowNodeRole.TREASURY
    if key in {address_key(item) for item in task.recipient_addresses}:
        return FundFlowNodeRole.RECIPIENT
    return FundFlowNodeRole.EXTERNAL


def _record_ref(record: TransferRecord) -> str:
    return event_ref(record)


def _finding_index(result: VerificationResult) -> dict[tuple[int, str, int], list]:
    indexed: dict[tuple[int, str, int], list] = defaultdict(list)
    for finding in result.findings:
        for reference in finding.evidence_refs:
            parts = reference.split(":")
            if len(parts) < 4 or parts[0] not in {"service", "rpc", "blockscout"}:
                continue
            try:
                key = (int(parts[-3]), parts[-2].lower(), int(parts[-1]))
            except ValueError:
                continue
            indexed[key].append(finding)
    return indexed


def _status(
    *,
    task: TaskSpec,
    record: TransferRecord,
    in_service: bool,
    in_reference: bool,
    occurrence: int,
    result: VerificationResult,
    findings: list,
) -> FundFlowVisualStatus:
    if result.outcome is VerificationOutcome.INCONCLUSIVE:
        return FundFlowVisualStatus.INCONCLUSIVE
    if occurrence > 0:
        return FundFlowVisualStatus.DUPLICATE
    if scope_violation(task, record) is FindingType.EXCLUDED_INTERNAL_TRANSFER:
        return FundFlowVisualStatus.INTERNAL_TRANSFER
    finding_types = {finding.finding_type for finding in findings}
    if finding_types & {FindingType.WRONG_TOKEN, FindingType.OUT_OF_RANGE} or any(
        finding.violated_rule == "submitted transfers must satisfy the confirmed task scope"
        for finding in findings
    ):
        return FundFlowVisualStatus.INVALID_SCOPE
    if any(finding.violated_rule == "complete_event_set" for finding in findings) and not in_reference:
        return FundFlowVisualStatus.NOT_FOUND_ON_CHAIN
    if not in_service and in_reference:
        return FundFlowVisualStatus.MISSING_FROM_REPORT
    if in_service and not in_reference:
        return FundFlowVisualStatus.INCONCLUSIVE
    if finding_types & {
        FindingType.EXTRA_TRANSFER,
        FindingType.WRONG_DIRECTION,
        FindingType.AMOUNT_MISMATCH,
        FindingType.DECIMAL_ERROR,
        FindingType.WRONG_TOKEN,
        FindingType.OUT_OF_RANGE,
    }:
        return FundFlowVisualStatus.MISMATCH
    return FundFlowVisualStatus.MATCHED


def project_fund_flow(
    task: TaskSpec,
    submission: ServiceSubmission,
    result: VerificationResult,
    evidence: ReferenceEvidence | None,
) -> FundFlowProjection:
    """Create a stable visual read model while preserving source provenance."""
    if (
        submission.task_id != task.task_id or result.task_id != task.task_id
        or result.submission_id != submission.submission_id
    ):
        raise ValueError("task, submission, and result must describe the same attempt")
    reference_records = collect_reference(evidence).transfers if evidence is not None else ()
    service_by_key: dict[tuple[int, str, int], list[TransferRecord]] = defaultdict(list)
    reference_by_key: dict[tuple[int, str, int], list[TransferRecord]] = defaultdict(list)
    for record in submission.transfers:
        service_by_key[event_key(record)].append(record)
    for record in reference_records:
        # RPC inventories may contain unrelated transfers from the same block.
        # Keep submitted events' original evidence even when the report violates
        # scope; reference-only edges must be eligible or explained exclusions.
        if event_key(record) not in service_by_key and scope_violation(task, record) not in {
            None, FindingType.EXCLUDED_INTERNAL_TRANSFER,
        }:
            continue
        reference_by_key[event_key(record)].append(record)
    finding_by_key = _finding_index(result)
    nodes_by_address: dict[str, FundFlowNode] = {}
    edges: list[FundFlowEdge] = []
    keys = sorted(set(service_by_key) | set(reference_by_key))
    for key in keys:
        service_records = service_by_key[key]
        reference_matches = reference_by_key[key]
        occurrences = max(len(service_records), 1)
        for occurrence in range(occurrences):
            record = reference_matches[0] if reference_matches else service_records[occurrence]
            for address in (record.from_address, record.to_address):
                normalized = address_key(address)
                if normalized not in nodes_by_address:
                    role = _node_role(task, address)
                    nodes_by_address[normalized] = FundFlowNode(
                        node_id=f"account:{normalized}",
                        address=address,
                        role=role,
                        label=f"{role.value.lower()} · {address[:8]}…{address[-6:]}",
                    )
            findings = finding_by_key.get(key, [])
            status = _status(
                task=task,
                record=record,
                in_service=bool(service_records),
                in_reference=bool(reference_matches),
                occurrence=occurrence,
                result=result,
                findings=findings,
            )
            edges.append(
                FundFlowEdge(
                    edge_id=f"flow:{key[0]}:{key[1]}:{key[2]}:{occurrence}",
                    from_node_id=f"account:{address_key(record.from_address)}",
                    to_node_id=f"account:{address_key(record.to_address)}",
                    event_key=key,
                    amount_base_units=record.amount_base_units,
                    token_decimals=record.token_decimals,
                    status=status,
                    service_refs=tuple(
                        f"submission:{submission.submission_id}:{index}"
                        for index, item in enumerate(submission.transfers) if event_key(item) == key
                    ),
                    reference_refs=tuple(_record_ref(item) for item in reference_matches),
                    finding_ids=tuple(dict.fromkeys(finding.finding_id for finding in findings)),
                    service_records=tuple(service_records),
                    reference_records=tuple(reference_matches),
                )
            )
    return FundFlowProjection(
        task_id=task.task_id,
        attempt=submission.attempt,
        claimed_total_base_units=submission.claimed_total_base_units,
        calculated_total_base_units=result.calculated_total_base_units,
        outcome=result.outcome,
        nodes=tuple(sorted(nodes_by_address.values(), key=lambda node: node.node_id)),
        edges=tuple(edges),
    )
