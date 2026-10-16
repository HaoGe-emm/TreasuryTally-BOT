"""Frozen shape for the twelve human-reviewed M1 fixture cases."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, StrictBool, model_validator

from trust_receipt.models.base import (
    DecimalIntegerString,
    DomainModel,
    EventKey,
    Identifier,
    NonEmptyText,
    NonNegativeInt,
    UtcDatetime,
)
from trust_receipt.models.enums import EvidenceSource, FindingSeverity, FindingStatus, FindingType, VerificationOutcome
from trust_receipt.models.submissions import ServiceSubmission
from trust_receipt.models.tasks import TaskSpec
from trust_receipt.models.transfers import TransferRecord
from trust_receipt.models.verification import SourceDescriptor


class FixtureReference(DomainModel):
    sources: tuple[SourceDescriptor, ...]
    reference_complete: StrictBool
    evidence_sufficient: StrictBool
    transfers: tuple[TransferRecord, ...] = Field(max_length=200)
    insufficiency_reason: NonEmptyText | None

    @model_validator(mode="after")
    def enforce_reference_semantics(self) -> FixtureReference:
        if any(source.source is EvidenceSource.SERVICE for source in self.sources):
            raise ValueError("reference sources cannot use source=service")
        if any(transfer.source is EvidenceSource.SERVICE for transfer in self.transfers):
            raise ValueError("reference transfers cannot use source=service")
        insufficient = not self.reference_complete or not self.evidence_sufficient
        if insufficient != (self.insufficiency_reason is not None):
            raise ValueError("insufficiency_reason must be present exactly when reference evidence is insufficient")
        return self


class ExpectedFinding(DomainModel):
    finding_type: FindingType
    severity: FindingSeverity
    status: FindingStatus
    violated_rule: NonEmptyText
    event_keys: tuple[EventKey, ...]


class FixtureExpectedResult(DomainModel):
    outcome: VerificationOutcome
    calculated_total_base_units: DecimalIntegerString | None
    calculated_count: NonNegativeInt | None
    findings: tuple[ExpectedFinding, ...]


class HumanReview(DomainModel):
    summary: NonEmptyText
    calculation: NonEmptyText
    reviewer: NonEmptyText
    verified_at: UtcDatetime


class FixtureCase(DomainModel):
    fixture_version: Literal["1.0"]
    fixture_id: Identifier = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    title: NonEmptyText
    tags: tuple[Identifier, ...] = Field(min_length=1)
    task_spec: TaskSpec
    submission: ServiceSubmission
    reference: FixtureReference
    expected: FixtureExpectedResult
    human_review: HumanReview

    @model_validator(mode="after")
    def enforce_case_links(self) -> FixtureCase:
        if self.submission.task_id != self.task_spec.task_id:
            raise ValueError("submission task_id must match task_spec task_id")
        insufficient = not self.reference.reference_complete or not self.reference.evidence_sufficient
        if insufficient != (self.expected.outcome is VerificationOutcome.INCONCLUSIVE):
            raise ValueError("expected outcome must preserve inconclusive evidence semantics")
        if not insufficient and (
            self.expected.calculated_total_base_units is None or self.expected.calculated_count is None
        ):
            raise ValueError("conclusive fixture expectations require calculated totals")
        confirmed_errors = any(
            finding.status is FindingStatus.CONFIRMED and finding.severity is FindingSeverity.ERROR
            for finding in self.expected.findings
        )
        if not insufficient:
            expected_outcome = VerificationOutcome.FAIL if confirmed_errors else VerificationOutcome.PASS
            if self.expected.outcome is not expected_outcome:
                raise ValueError(f"expected findings require outcome={expected_outcome.value}")
        return self


class FixtureManifestEntry(DomainModel):
    fixture_id: Identifier = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    file: NonEmptyText = Field(pattern=r"^cases/[a-z0-9]+(?:-[a-z0-9]+)*\.json$")
    title: NonEmptyText
    tags: tuple[Identifier, ...] = Field(min_length=1)
    expected_outcome: VerificationOutcome


class FixtureManifest(DomainModel):
    fixture_version: Literal["1.0"]
    fixtures: tuple[FixtureManifestEntry, ...] = Field(min_length=12, max_length=12)

    @model_validator(mode="after")
    def require_unique_entries(self) -> FixtureManifest:
        ids = [entry.fixture_id for entry in self.fixtures]
        files = [entry.file for entry in self.fixtures]
        if len(ids) != len(set(ids)) or len(files) != len(set(files)):
            raise ValueError("fixture manifest IDs and files must be unique")
        if any(entry.file != f"cases/{entry.fixture_id}.json" for entry in self.fixtures):
            raise ValueError("fixture file must match fixture_id")
        return self
