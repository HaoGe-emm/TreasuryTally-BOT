"""Deterministic findings, evidence descriptors, and three-state result."""

from __future__ import annotations

from pydantic import Field, JsonValue, StrictBool, model_validator

from trust_receipt.models.base import (
    DecimalIntegerString,
    DomainModel,
    Identifier,
    NonEmptyText,
    NonNegativeInt,
    UtcDatetime,
)
from trust_receipt.models.enums import (
    EvidenceSource,
    FindingSeverity,
    FindingStatus,
    FindingType,
    VerificationOutcome,
)


class SourceDescriptor(DomainModel):
    source: EvidenceSource
    source_id: Identifier
    retrieved_at: UtcDatetime
    complete: StrictBool
    details: dict[str, JsonValue]


class Finding(DomainModel):
    finding_id: Identifier
    finding_type: FindingType
    severity: FindingSeverity
    expected: dict[str, JsonValue] | None
    actual: dict[str, JsonValue] | None
    violated_rule: NonEmptyText
    evidence_refs: tuple[Identifier, ...] = Field(min_length=1)
    explanation: NonEmptyText
    status: FindingStatus

    @property
    def is_confirmed_error(self) -> bool:
        return self.status is FindingStatus.CONFIRMED and self.severity is FindingSeverity.ERROR


class VerificationResult(DomainModel):
    run_id: Identifier
    task_id: Identifier
    submission_id: Identifier
    verifier_version: Identifier
    reference_sources: tuple[SourceDescriptor, ...]
    reference_complete: StrictBool
    evidence_sufficient: StrictBool
    calculated_total_base_units: DecimalIntegerString | None
    calculated_count: NonNegativeInt | None
    findings: tuple[Finding, ...]
    outcome: VerificationOutcome
    inconclusive_reason: NonEmptyText | None
    started_at: UtcDatetime
    finished_at: UtcDatetime

    @model_validator(mode="after")
    def enforce_outcome_semantics(self) -> VerificationResult:
        if self.finished_at < self.started_at:
            raise ValueError("finished_at must not be earlier than started_at")
        if any(source.source is EvidenceSource.SERVICE for source in self.reference_sources):
            raise ValueError("reference_sources cannot use source=service")
        if self.reference_complete and any(not source.complete for source in self.reference_sources):
            raise ValueError("reference_complete=true requires every source descriptor to be complete")
        insufficient = not self.reference_complete or not self.evidence_sufficient
        confirmed_errors = any(finding.is_confirmed_error for finding in self.findings)
        if insufficient:
            if self.outcome is not VerificationOutcome.INCONCLUSIVE:
                raise ValueError("insufficient evidence requires outcome=INCONCLUSIVE")
            if self.inconclusive_reason is None:
                raise ValueError("INCONCLUSIVE requires inconclusive_reason")
            return self
        if self.outcome is VerificationOutcome.INCONCLUSIVE:
            raise ValueError("INCONCLUSIVE requires incomplete or insufficient evidence")
        if self.inconclusive_reason is not None:
            raise ValueError("conclusive outcomes cannot include inconclusive_reason")
        if self.calculated_total_base_units is None or self.calculated_count is None:
            raise ValueError("conclusive outcomes require calculated totals")
        expected_outcome = VerificationOutcome.FAIL if confirmed_errors else VerificationOutcome.PASS
        if self.outcome is not expected_outcome:
            raise ValueError(f"findings require outcome={expected_outcome.value}")
        return self
