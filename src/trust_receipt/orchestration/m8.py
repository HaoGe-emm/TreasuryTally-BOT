"""Page-safe M8 commitment use cases."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from eth_account import Account

from trust_receipt.commitments import (
    create_task_commitment,
    verify_delivery_commitment,
    verify_task_commitment,
)
from trust_receipt.models import DeliveryCommitment, ServiceSubmission, TaskCommitment, TaskSpec
from trust_receipt.services import ReportService


class M8CommitmentWorkflow:
    def __init__(
        self,
        *,
        requester_private_key: str | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._requester_private_key = requester_private_key or Account.create().key.to_0x_hex()
        self._clock = clock

    def commit_task(self, task: TaskSpec, service_id: str) -> TaskCommitment:
        commitment = create_task_commitment(
            task,
            service_id=service_id,
            requester_private_key=self._requester_private_key,
            created_at=self._clock(),
        )
        if not verify_task_commitment(commitment, task):
            raise ValueError("generated task commitment failed EIP-712 verification")
        return commitment

    def commit_delivery(
        self,
        task_commitment: TaskCommitment,
        submission: ServiceSubmission,
        service: ReportService,
        *,
        accepted_at: datetime | None = None,
        acceptance_signature: str | None = None,
    ) -> DeliveryCommitment:
        accepted_at = accepted_at or self._clock()
        commitment = service.create_delivery_commitment(
            task_commitment,
            submission,
            accepted_at=accepted_at,
            submitted_at=max(accepted_at, submission.created_at),
            acceptance_signature=acceptance_signature,
        )
        if not verify_delivery_commitment(
            commitment,
            task_commitment,
            submission,
            expected_signer=service.signer_address,
        ):
            raise ValueError("generated delivery commitment failed EIP-712 verification")
        return commitment
