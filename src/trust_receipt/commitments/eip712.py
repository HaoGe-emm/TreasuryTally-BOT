"""EIP-712 commitments that never imply an on-chain submission."""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from eth_account import Account
from eth_account.messages import encode_typed_data

from trust_receipt.hashing import stable_hash, verify_submission_hash, verify_task_spec_hash
from trust_receipt.models import (
    CommitmentAnchor,
    CommitmentAnchorStatus,
    DeliveryCommitment,
    ServiceSubmission,
    TaskCommitment,
    TaskSpec,
)

DOMAIN_NAME = "TrustReceipt"
DOMAIN_VERSION = "1"
EMPTY_SIGNATURE = "0x" + "00" * 65


def _timestamp(value: datetime) -> str:
    return value.isoformat()


def _domain(chain_id: int) -> dict[str, object]:
    return {"name": DOMAIN_NAME, "version": DOMAIN_VERSION, "chainId": chain_id}


def _sign(private_key: str, *, chain_id: int, primary_type: str, fields: list[dict], message: dict) -> str:
    typed = {
        "types": {
            "EIP712Domain": [
                {"name": "name", "type": "string"},
                {"name": "version", "type": "string"},
                {"name": "chainId", "type": "uint256"},
            ],
            primary_type: fields,
        },
        "primaryType": primary_type,
        "domain": _domain(chain_id),
        "message": message,
    }
    return Account.sign_message(encode_typed_data(full_message=typed), private_key=private_key).signature.to_0x_hex()


def _recover(signature: str, *, chain_id: int, primary_type: str, fields: list[dict], message: dict) -> str | None:
    try:
        typed = {
            "types": {
                "EIP712Domain": [
                    {"name": "name", "type": "string"},
                    {"name": "version", "type": "string"},
                    {"name": "chainId", "type": "uint256"},
                ],
                primary_type: fields,
            },
            "primaryType": primary_type,
            "domain": _domain(chain_id),
            "message": message,
        }
        return Account.recover_message(encode_typed_data(full_message=typed), signature=signature)
    except (TypeError, ValueError):
        return None


TASK_FIELDS = [
    {"name": "commitmentId", "type": "string"},
    {"name": "taskId", "type": "string"},
    {"name": "specHash", "type": "bytes32"},
    {"name": "requester", "type": "address"},
    {"name": "serviceId", "type": "string"},
    {"name": "createdAt", "type": "string"},
    {"name": "expiresAt", "type": "string"},
]

ACCEPTANCE_FIELDS = [
    {"name": "taskCommitmentId", "type": "string"},
    {"name": "taskCommitmentHash", "type": "bytes32"},
    {"name": "specHash", "type": "bytes32"},
    {"name": "serviceId", "type": "string"},
    {"name": "attempt", "type": "uint256"},
    {"name": "acceptedAt", "type": "string"},
]

DELIVERY_FIELDS = [
    *ACCEPTANCE_FIELDS,
    {"name": "submissionId", "type": "string"},
    {"name": "reportHash", "type": "bytes32"},
    {"name": "submittedAt", "type": "string"},
]


def _task_message(commitment: TaskCommitment) -> dict[str, object]:
    return {
        "commitmentId": commitment.commitment_id,
        "taskId": commitment.task_id,
        "specHash": commitment.spec_hash,
        "requester": commitment.requester_address,
        "serviceId": commitment.service_id,
        "createdAt": _timestamp(commitment.created_at),
        "expiresAt": _timestamp(commitment.expires_at) if commitment.expires_at else "",
    }


def _acceptance_message(commitment: DeliveryCommitment) -> dict[str, object]:
    return {
        "taskCommitmentId": commitment.task_commitment_id,
        "taskCommitmentHash": commitment.task_commitment_hash,
        "specHash": commitment.spec_hash,
        "serviceId": commitment.service_id,
        "attempt": commitment.attempt,
        "acceptedAt": _timestamp(commitment.accepted_at),
    }


def _delivery_message(commitment: DeliveryCommitment) -> dict[str, object]:
    return {
        **_acceptance_message(commitment),
        "submissionId": commitment.submission_id,
        "reportHash": commitment.report_hash,
        "submittedAt": _timestamp(commitment.submitted_at),
    }


def create_task_commitment(
    task: TaskSpec,
    *,
    service_id: str,
    requester_private_key: str,
    created_at: datetime,
    expires_at: datetime | None = None,
    commitment_id: str | None = None,
) -> TaskCommitment:
    if not verify_task_spec_hash(task):
        raise ValueError("TaskSpec hash does not match its canonical content")
    requester = Account.from_key(requester_private_key).address
    unsigned = TaskCommitment(
        commitment_version="1.0",
        commitment_id=commitment_id or f"task-commitment-{uuid4()}",
        task_id=task.task_id,
        spec_hash=task.spec_hash,
        requester_address=requester,
        service_id=service_id,
        created_at=created_at,
        expires_at=expires_at,
        signature_scheme="EIP712",
        signature=EMPTY_SIGNATURE,
        anchor=CommitmentAnchor(chain_id=task.chain_id, status=CommitmentAnchorStatus.NOT_SUBMITTED),
    )
    signature = _sign(
        requester_private_key,
        chain_id=task.chain_id,
        primary_type="TaskCommitment",
        fields=TASK_FIELDS,
        message=_task_message(unsigned),
    )
    return unsigned.model_copy(update={"signature": signature})


def verify_task_commitment(commitment: TaskCommitment, task: TaskSpec) -> bool:
    if commitment.task_id != task.task_id or commitment.spec_hash != task.spec_hash:
        return False
    if commitment.anchor.chain_id != task.chain_id or not verify_task_spec_hash(task):
        return False
    recovered = _recover(
        commitment.signature,
        chain_id=commitment.anchor.chain_id,
        primary_type="TaskCommitment",
        fields=TASK_FIELDS,
        message=_task_message(commitment),
    )
    return recovered is not None and recovered.lower() == commitment.requester_address.lower()


def create_delivery_commitment(
    task_commitment: TaskCommitment,
    submission: ServiceSubmission,
    *,
    service_private_key: str,
    accepted_at: datetime,
    submitted_at: datetime,
    acceptance_signature: str | None = None,
) -> DeliveryCommitment:
    if submission.task_id != task_commitment.task_id or submission.service_id != task_commitment.service_id:
        raise ValueError("submission does not match the task commitment")
    if not verify_submission_hash(submission):
        raise ValueError("ServiceSubmission hash does not match its canonical content")
    signer = Account.from_key(service_private_key).address
    unsigned = DeliveryCommitment(
        commitment_version="1.0",
        task_commitment_id=task_commitment.commitment_id,
        task_commitment_hash=task_commitment_hash(task_commitment),
        spec_hash=task_commitment.spec_hash,
        submission_id=submission.submission_id,
        service_id=submission.service_id,
        attempt=submission.attempt,
        report_hash=submission.report_hash,
        accepted_at=accepted_at,
        submitted_at=submitted_at,
        signer_address=signer,
        signature_scheme="EIP712",
        acceptance_signature=EMPTY_SIGNATURE,
        signature=EMPTY_SIGNATURE,
    )
    acceptance = acceptance_signature or create_acceptance_signature(
        task_commitment, attempt=submission.attempt,
        service_private_key=service_private_key, accepted_at=accepted_at,
    )
    delivery = _sign(
        service_private_key,
        chain_id=task_commitment.anchor.chain_id,
        primary_type="DeliveryCommitment",
        fields=DELIVERY_FIELDS,
        message=_delivery_message(unsigned),
    )
    return unsigned.model_copy(update={"acceptance_signature": acceptance, "signature": delivery})


def verify_delivery_commitment(
    commitment: DeliveryCommitment,
    task_commitment: TaskCommitment,
    submission: ServiceSubmission,
    *,
    expected_signer: str,
) -> bool:
    if (
        commitment.task_commitment_id != task_commitment.commitment_id
        or commitment.task_commitment_hash != task_commitment_hash(task_commitment)
        or commitment.spec_hash != task_commitment.spec_hash
        or submission.task_id != task_commitment.task_id
        or submission.service_id != task_commitment.service_id
        or commitment.submission_id != submission.submission_id
        or commitment.service_id != submission.service_id
        or commitment.attempt != submission.attempt
        or commitment.report_hash != submission.report_hash
        or commitment.signer_address.lower() != expected_signer.lower()
        or commitment.accepted_at < task_commitment.created_at
        or commitment.submitted_at < commitment.accepted_at
        or (task_commitment.expires_at is not None and commitment.accepted_at >= task_commitment.expires_at)
        or not verify_submission_hash(submission)
    ):
        return False
    requester = _recover(
        task_commitment.signature, chain_id=task_commitment.anchor.chain_id,
        primary_type="TaskCommitment", fields=TASK_FIELDS, message=_task_message(task_commitment),
    )
    if requester is None or requester.lower() != task_commitment.requester_address.lower():
        return False
    acceptance = _recover(
        commitment.acceptance_signature,
        chain_id=task_commitment.anchor.chain_id,
        primary_type="DeliveryAcceptance",
        fields=ACCEPTANCE_FIELDS,
        message=_acceptance_message(commitment),
    )
    delivery = _recover(
        commitment.signature,
        chain_id=task_commitment.anchor.chain_id,
        primary_type="DeliveryCommitment",
        fields=DELIVERY_FIELDS,
        message=_delivery_message(commitment),
    )
    return all(
        recovered is not None and recovered.lower() == expected_signer.lower()
        for recovered in (acceptance, delivery)
    )


def task_commitment_hash(commitment: TaskCommitment) -> str:
    return stable_hash({
        "message": _task_message(commitment),
        "chain_id": commitment.anchor.chain_id,
        "signature": commitment.signature,
    })


def create_acceptance_signature(
    task_commitment: TaskCommitment, *, attempt: int, service_private_key: str, accepted_at: datetime,
) -> str:
    """Sign the full task binding before acquiring or generating a report."""
    if attempt not in (1, 2) or accepted_at < task_commitment.created_at:
        raise ValueError("invalid task acceptance attempt or time")
    if task_commitment.expires_at is not None and accepted_at >= task_commitment.expires_at:
        raise ValueError("task commitment has expired")
    return _sign(
        service_private_key, chain_id=task_commitment.anchor.chain_id,
        primary_type="DeliveryAcceptance", fields=ACCEPTANCE_FIELDS,
        message={
            "taskCommitmentId": task_commitment.commitment_id,
            "taskCommitmentHash": task_commitment_hash(task_commitment),
            "specHash": task_commitment.spec_hash,
            "serviceId": task_commitment.service_id,
            "attempt": attempt,
            "acceptedAt": _timestamp(accepted_at),
        },
    )
