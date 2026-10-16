"""Stable port for a future commitment anchor implementation."""

from typing import Protocol

from trust_receipt.models import CommitmentAnchor, DeliveryCommitment, TaskCommitment


class CommitmentAnchorPort(Protocol):
    def read_task_anchor(self, commitment: TaskCommitment, *, task, expected_signer: str) -> CommitmentAnchor: ...

    def read_delivery_anchor(
        self, commitment: DeliveryCommitment, *, task_commitment: TaskCommitment,
        submission, expected_signer: str, anchor: CommitmentAnchor,
    ) -> CommitmentAnchor: ...
