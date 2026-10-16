"""Stable optional ports used by M9 without depending on M8 adapters."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from trust_receipt.m9.models import (
    CommitmentVerification,
    PublicReferenceKind,
    ReceiptRevision,
)
from trust_receipt.models.receipts import Receipt, ServiceIdentity
from trust_receipt.models.submissions import ServiceSubmission
from trust_receipt.services.signatures import verify_submission_signature


@dataclass(frozen=True)
class PublicReceiptReference:
    kind: PublicReferenceKind
    value: str


@dataclass(frozen=True)
class ResolvedPublicReceipt:
    """Public bytes plus resolver-supplied bindings, never private workspace data."""

    payload: bytes
    attempt: int
    expected_content_hash: str | None = None
    feedback_transaction_hash: str | None = None
    feedback_binding_verified: bool = False
    revision: ReceiptRevision | None = None
    parent_revision: ReceiptRevision | None = None
    parent_receipt: Receipt | None = None
    evidence_refs: tuple[str, ...] = ()


class PublicReceiptResolver(Protocol):
    def resolve(self, reference: PublicReceiptReference) -> ResolvedPublicReceipt: ...


class ReceiptCommitmentVerifier(Protocol):
    def verify(self, receipt: Receipt, *, attempt: int) -> CommitmentVerification: ...


class SubmissionSignatureVerifier(Protocol):
    def verify(self, submission: ServiceSubmission, identity: ServiceIdentity) -> bool: ...


class V1SubmissionSignatureVerifier:
    """Reuse the M3 EVM personal-sign verifier for existing v1 submissions."""

    def verify(self, submission: ServiceSubmission, identity: ServiceIdentity) -> bool:
        try:
            return verify_submission_signature(submission, identity.identity_reference)
        except Exception:
            return False
