"""Stable, source-linked descriptions of confirmed verification differences."""

from __future__ import annotations

from pydantic import JsonValue

from trust_receipt.models.enums import FindingSeverity, FindingStatus, FindingType
from trust_receipt.models.transfers import TransferRecord
from trust_receipt.models.verification import Finding
from trust_receipt.verification.normalization import event_ref


def transfer_summary(record: TransferRecord) -> dict[str, JsonValue]:
    return {
        "chain_id": record.chain_id,
        "transaction_hash": record.transaction_hash,
        "log_index": record.log_index,
        "token_address": record.token_address,
        "block_number": record.block_number,
        "from_address": record.from_address,
        "to_address": record.to_address,
        "amount_base_units": record.amount_base_units,
        "token_decimals": record.token_decimals,
        "source": record.source.value,
    }


def confirmed_finding(
    *,
    run_id: str,
    number: int,
    finding_type: FindingType,
    rule: str,
    explanation: str,
    expected: dict[str, JsonValue] | None,
    actual: dict[str, JsonValue] | None,
    records: tuple[TransferRecord, ...],
    additional_refs: tuple[str, ...] = (),
) -> Finding:
    return Finding(
        finding_id=f"{run_id}:{number}",
        finding_type=finding_type,
        severity=FindingSeverity.ERROR,
        expected=expected,
        actual=actual,
        violated_rule=rule,
        evidence_refs=tuple(event_ref(record) for record in records) + additional_refs or (f"run:{run_id}",),
        explanation=explanation,
        status=FindingStatus.CONFIRMED,
    )


def insufficient_evidence_finding(
    run_id: str,
    reason: str,
    records: tuple[TransferRecord, ...] = (),
) -> Finding:
    return Finding(
        finding_id=f"{run_id}:evidence",
        finding_type=FindingType.INSUFFICIENT_EVIDENCE,
        severity=FindingSeverity.WARNING,
        expected=None,
        actual=None,
        violated_rule="all reference pages must be proven complete",
        evidence_refs=tuple(event_ref(record) for record in records) or (f"run:{run_id}",),
        explanation=reason,
        status=FindingStatus.HYPOTHESIS,
    )
