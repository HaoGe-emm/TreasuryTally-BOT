"""Independent receipt integrity and deterministic-outcome replay."""

from __future__ import annotations

from dataclasses import dataclass

from trust_receipt.hashing import verify_receipt_hash, verify_task_spec_hash
from trust_receipt.models.enums import VerificationOutcome
from trust_receipt.models.receipts import Receipt


@dataclass(frozen=True)
class ReceiptReplay:
    receipt_hash_valid: bool
    task_hash_valid: bool
    links_valid: bool
    recorded_outcome: VerificationOutcome
    recomputed_outcome: VerificationOutcome

    @property
    def valid(self) -> bool:
        return (
            self.receipt_hash_valid
            and self.task_hash_valid
            and self.links_valid
            and self.recorded_outcome is self.recomputed_outcome
        )


def _recompute_outcome(receipt: Receipt) -> VerificationOutcome:
    result = receipt.verification_result
    if not result.reference_complete or not result.evidence_sufficient:
        return VerificationOutcome.INCONCLUSIVE
    if any(finding.is_confirmed_error for finding in result.findings):
        return VerificationOutcome.FAIL
    return VerificationOutcome.PASS


def replay_receipt(receipt: Receipt) -> ReceiptReplay:
    task_id = receipt.task_spec.task_id
    links_valid = (
        receipt.verification_plan.task_id == task_id
        and receipt.verification_result.task_id == task_id
        and receipt.submission_hash.startswith("0x")
    )
    return ReceiptReplay(
        receipt_hash_valid=verify_receipt_hash(receipt),
        task_hash_valid=verify_task_spec_hash(receipt.task_spec),
        links_valid=links_valid,
        recorded_outcome=receipt.verification_result.outcome,
        recomputed_outcome=_recompute_outcome(receipt),
    )

