"""M8 commitment adapter for M9 receipt and comparison verification."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from trust_receipt.commitments import verify_delivery_commitment, verify_task_commitment
from trust_receipt.commitments.eip712 import task_commitment_hash
from trust_receipt.m9.models import CommitmentStatus, CommitmentVerification
from trust_receipt.models import DeliveryCommitment, ServiceSubmission, TaskCommitment
from trust_receipt.models.base import EvmAddress
from trust_receipt.models.receipts import Receipt


@dataclass(frozen=True)
class M8CommitmentBinding:
    """Private M8 snapshot bound to the public fields needed for verification."""

    task_commitment: TaskCommitment
    delivery_commitment: DeliveryCommitment
    submission: ServiceSubmission
    expected_signer: EvmAddress


class M8ReceiptCommitmentVerifier:
    """Verify actual M8 EIP-712 snapshots without treating them as chain anchors."""

    def __init__(self, bindings: Iterable[M8CommitmentBinding]) -> None:
        self._bindings: dict[tuple[str, str, int], M8CommitmentBinding] = {}
        for binding in bindings:
            key = (
                str(binding.submission.task_id),
                binding.submission.report_hash.lower(),
                binding.submission.attempt,
            )
            if key in self._bindings and self._bindings[key] != binding:
                raise ValueError("conflicting M8 commitment bindings for one submission")
            self._bindings[key] = binding

    def verify(self, receipt: Receipt, *, attempt: int) -> CommitmentVerification:
        key = (
            str(receipt.task_spec.task_id),
            receipt.submission_hash.lower(),
            attempt,
        )
        binding = self._bindings.get(key)
        if binding is None:
            return CommitmentVerification(
                status=CommitmentStatus.UNVERIFIED,
                evidence_refs=(),
                reason="No M8 commitment snapshot is available for this receipt attempt.",
            )
        task = binding.task_commitment
        delivery = binding.delivery_commitment
        submission = binding.submission
        evidence_refs = (
            f"m8-task-commitment:{task_commitment_hash(task)}",
            f"m8-delivery-report:{delivery.report_hash}",
            f"m8-anchor:{task.anchor.chain_id}:{task.anchor.status.value}",
        )
        links_match = (
            receipt.task_spec.task_id == submission.task_id
            and receipt.task_spec.spec_hash == task.spec_hash
            and receipt.service_identity.service_id == submission.service_id == task.service_id
            and receipt.verification_result.submission_id == submission.submission_id
            and receipt.submission_hash == submission.report_hash == delivery.report_hash
            and receipt.service_identity.identity_reference.lower() == binding.expected_signer.lower()
            and attempt == submission.attempt == delivery.attempt
        )
        signatures_valid = links_match and verify_task_commitment(task, receipt.task_spec)
        signatures_valid = signatures_valid and verify_delivery_commitment(
            delivery,
            task,
            submission,
            expected_signer=binding.expected_signer,
        )
        if not signatures_valid:
            return CommitmentVerification(
                status=CommitmentStatus.INVALID,
                evidence_refs=evidence_refs,
                reason="M8 task/delivery links or EIP-712 signatures do not match the receipt.",
            )
        return CommitmentVerification(
            status=CommitmentStatus.VERIFIED,
            evidence_refs=evidence_refs,
            reason=None,
        )
