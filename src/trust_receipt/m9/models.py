"""Strict M9 contracts kept outside the frozen Receipt 1.0 payload."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import Field, JsonValue, model_validator

from trust_receipt.models.base import (
    DecimalIntegerString,
    DomainModel,
    Hex32,
    Identifier,
    NonEmptyText,
    UtcDatetime,
)
from trust_receipt.models.enums import FindingType, VerificationOutcome


class ReworkAction(StrEnum):
    ADD_MISSING_TRANSFER = "ADD_MISSING_TRANSFER"
    REMOVE_EXTRA_TRANSFER = "REMOVE_EXTRA_TRANSFER"
    REMOVE_DUPLICATE_TRANSFER = "REMOVE_DUPLICATE_TRANSFER"
    REMOVE_EXCLUDED_INTERNAL_TRANSFER = "REMOVE_EXCLUDED_INTERNAL_TRANSFER"
    CORRECT_SCOPE = "CORRECT_SCOPE"
    CORRECT_TOKEN = "CORRECT_TOKEN"
    CORRECT_DIRECTION = "CORRECT_DIRECTION"
    CORRECT_AMOUNT = "CORRECT_AMOUNT"
    CORRECT_DECIMALS = "CORRECT_DECIMALS"


class RevisionResolution(StrEnum):
    ORIGINAL = "ORIGINAL"
    RESUBMITTED = "RESUBMITTED"
    FIXED = "FIXED"
    UNRESOLVED = "UNRESOLVED"


class CommitmentStatus(StrEnum):
    VERIFIED = "VERIFIED"
    UNVERIFIED = "UNVERIFIED"
    INVALID = "INVALID"


class PublicReferenceKind(StrEnum):
    URI = "URI"
    RECEIPT_HASH = "RECEIPT_HASH"
    TASK_HASH = "TASK_HASH"
    FEEDBACK_TRANSACTION = "FEEDBACK_TRANSACTION"


class PublicVerificationStatus(StrEnum):
    VERIFIED = "VERIFIED"
    INCONCLUSIVE = "INCONCLUSIVE"
    INVALID = "INVALID"


class VerificationCheckState(StrEnum):
    PASSED = "PASSED"
    FAILED = "FAILED"
    UNVERIFIED = "UNVERIFIED"


class ReworkItem(DomainModel):
    finding_id: Identifier
    finding_type: FindingType
    violated_rule: NonEmptyText
    expected: dict[str, JsonValue] | None
    actual: dict[str, JsonValue] | None
    evidence_refs: tuple[Identifier, ...] = Field(min_length=1)
    required_action: ReworkAction


class ReworkPackage(DomainModel):
    package_version: Literal["1.0"]
    package_id: Identifier
    task_id: Identifier
    source_submission_id: Identifier
    source_receipt_hash: Hex32
    created_at: UtcDatetime
    items: tuple[ReworkItem, ...] = Field(min_length=1)
    package_hash: Hex32

    @model_validator(mode="after")
    def enforce_unique_findings(self) -> ReworkPackage:
        finding_ids = [item.finding_id for item in self.items]
        if len(finding_ids) != len(set(finding_ids)):
            raise ValueError("rework package finding IDs must be unique")
        return self


class ReceiptRevision(DomainModel):
    revision_version: Literal["1.0"]
    task_id: Identifier
    service_id: Identifier
    attempt: Literal[1, 2]
    receipt_hash: Hex32
    outcome: VerificationOutcome
    resolution: RevisionResolution
    parent_receipt_hash: Hex32 | None
    supersedes_receipt_hash: Hex32 | None
    evidence_refs: tuple[NonEmptyText, ...] = Field(min_length=1)
    created_at: UtcDatetime
    revision_hash: Hex32

    @model_validator(mode="after")
    def enforce_revision_shape(self) -> ReceiptRevision:
        if self.attempt == 1:
            if self.resolution is not RevisionResolution.ORIGINAL:
                raise ValueError("attempt 1 revision must be ORIGINAL")
            if self.parent_receipt_hash is not None or self.supersedes_receipt_hash is not None:
                raise ValueError("attempt 1 revision cannot have parent or supersedes links")
            return self
        if self.parent_receipt_hash is None or self.supersedes_receipt_hash is None:
            raise ValueError("attempt 2 revision requires parent and supersedes links")
        if self.parent_receipt_hash != self.supersedes_receipt_hash:
            raise ValueError("attempt 2 parent and supersedes must identify the same prior receipt")
        expected = (
            RevisionResolution.FIXED
            if self.outcome is VerificationOutcome.PASS
            else RevisionResolution.UNRESOLVED
        )
        if self.resolution is not expected:
            raise ValueError(f"attempt 2 outcome requires resolution={expected.value}")
        return self


class AttemptSnapshot(DomainModel):
    task_id: Identifier
    service_id: Identifier
    submission_id: Identifier
    attempt: Literal[1, 2]
    receipt_hash: Hex32
    outcome: VerificationOutcome
    resolution: RevisionResolution
    claimed_total_base_units: DecimalIntegerString
    calculated_total_base_units: DecimalIntegerString | None
    finding_ids: tuple[Identifier, ...]
    evidence_refs: tuple[NonEmptyText, ...] = Field(min_length=1)
    commitment_status: CommitmentStatus


class RepairComparison(DomainModel):
    comparison_version: Literal["1.0"]
    task_id: Identifier
    before: AttemptSnapshot
    after: AttemptSnapshot
    resolved_finding_ids: tuple[Identifier, ...]
    remaining_finding_ids: tuple[Identifier, ...]
    resolution: RevisionResolution

    @model_validator(mode="after")
    def enforce_pair(self) -> RepairComparison:
        if self.before.task_id != self.task_id or self.after.task_id != self.task_id:
            raise ValueError("comparison snapshots must reference the same task")
        if self.before.attempt != 1 or self.after.attempt != 2:
            raise ValueError("comparison requires attempt 1 before attempt 2")
        if self.before.receipt_hash == self.after.receipt_hash:
            raise ValueError("comparison receipts must be distinct")
        if self.after.resolution is not self.resolution:
            raise ValueError("comparison resolution must match the second revision")
        if set(self.resolved_finding_ids) & set(self.remaining_finding_ids):
            raise ValueError("resolved and remaining findings must be disjoint")
        return self


class CommitmentVerification(DomainModel):
    status: CommitmentStatus
    evidence_refs: tuple[NonEmptyText, ...]
    reason: NonEmptyText | None

    @model_validator(mode="after")
    def require_reason_when_not_verified(self) -> CommitmentVerification:
        if self.status is CommitmentStatus.VERIFIED and self.reason is not None:
            raise ValueError("verified commitment cannot include a failure reason")
        if self.status is not CommitmentStatus.VERIFIED and self.reason is None:
            raise ValueError("unverified or invalid commitment requires a reason")
        return self


class VerificationCheck(DomainModel):
    check_id: Identifier
    state: VerificationCheckState
    detail: NonEmptyText


class PublicVerificationResult(DomainModel):
    verification_version: Literal["1.0"]
    reference_kind: PublicReferenceKind
    reference_value: NonEmptyText
    status: PublicVerificationStatus
    task_id: Identifier | None
    service_id: Identifier | None
    attempt: Literal[1, 2] | None
    receipt_hash: Hex32 | None
    outcome: VerificationOutcome | None
    resolution: RevisionResolution | None
    evidence_refs: tuple[NonEmptyText, ...]
    commitment_status: CommitmentStatus
    checks: tuple[VerificationCheck, ...] = Field(min_length=1)
    reason: NonEmptyText | None

    @model_validator(mode="after")
    def enforce_result_shape(self) -> PublicVerificationResult:
        identity = (self.task_id, self.service_id, self.attempt, self.receipt_hash, self.outcome)
        if self.status is PublicVerificationStatus.VERIFIED and any(value is None for value in identity):
            raise ValueError("verified result requires task, service, attempt, receipt, and outcome")
        if self.status is PublicVerificationStatus.VERIFIED and self.reason is not None:
            raise ValueError("verified result cannot include an inconclusive or invalid reason")
        if self.status is not PublicVerificationStatus.VERIFIED and self.reason is None:
            raise ValueError("inconclusive or invalid result requires a reason")
        return self
