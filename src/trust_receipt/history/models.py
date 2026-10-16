"""Immutable read models for traceable, task-scoped service history."""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field, model_validator

from trust_receipt.models.base import DomainModel, Hex32, Identifier, NonEmptyText, NonNegativeInt, UtcDatetime
from trust_receipt.models.enums import VerificationOutcome


class HistoryCategory(StrEnum):
    FIRST_PASS = "FIRST_PASS"
    FIXED_PASS = "FIXED_PASS"
    FAIL = "FAIL"
    INCONCLUSIVE = "INCONCLUSIVE"


class RevisionResolution(StrEnum):
    ORIGINAL = "ORIGINAL"
    RESUBMITTED = "RESUBMITTED"
    FIXED = "FIXED"
    UNRESOLVED = "UNRESOLVED"


class ReceiptRevisionLink(DomainModel):
    receipt_hash: Hex32
    parent_receipt_hash: Hex32 | None = None
    supersedes_receipt_hash: Hex32 | None = None
    resolution: RevisionResolution


class ReceiptSourceRef(DomainModel):
    receipt_hash: Hex32
    receipt_id: Identifier
    task_id: Identifier
    service_id: Identifier
    task_type: Identifier
    outcome: VerificationOutcome
    delivery_at: UtcDatetime
    verified_at: UtcDatetime
    source_ref: NonEmptyText
    public_uri: NonEmptyText | None = None
    feedback_transaction_hash: Hex32 | None = None
    revision: ReceiptRevisionLink | None = None


class ServiceTaskFact(DomainModel):
    task_id: Identifier
    service_id: Identifier
    task_type: Identifier
    category: HistoryCategory
    latest_delivery_at: UtcDatetime
    primary_receipt_hash: Hex32
    receipt_refs: tuple[ReceiptSourceRef, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def enforce_fact_links(self) -> ServiceTaskFact:
        if any(
            ref.task_id != self.task_id
            or ref.service_id != self.service_id
            or ref.task_type != self.task_type
            for ref in self.receipt_refs
        ):
            raise ValueError("task fact receipt refs must share task, service, and task type")
        if self.primary_receipt_hash not in {ref.receipt_hash for ref in self.receipt_refs}:
            raise ValueError("primary receipt must be included in receipt_refs")
        return self


class ServiceHistoryProjection(DomainModel):
    service_id: Identifier
    service_name: NonEmptyText
    task_type: Identifier
    verified_task_count: NonNegativeInt
    first_pass_count: NonNegativeInt
    fixed_pass_count: NonNegativeInt
    fail_count: NonNegativeInt
    inconclusive_count: NonNegativeInt
    verifiable_receipt_count: NonNegativeInt
    latest_delivery_at: UtcDatetime | None
    latest_verified_at: UtcDatetime | None
    receipt_refs: tuple[ReceiptSourceRef, ...]
    task_facts: tuple[ServiceTaskFact, ...]

    @model_validator(mode="after")
    def enforce_recomputable_counts(self) -> ServiceHistoryProjection:
        facts = self.task_facts
        expected = {
            HistoryCategory.FIRST_PASS: self.first_pass_count,
            HistoryCategory.FIXED_PASS: self.fixed_pass_count,
            HistoryCategory.FAIL: self.fail_count,
            HistoryCategory.INCONCLUSIVE: self.inconclusive_count,
        }
        if self.verified_task_count != len(facts):
            raise ValueError("verified_task_count must equal the number of task facts")
        if any(sum(fact.category is category for fact in facts) != count for category, count in expected.items()):
            raise ValueError("history counts must be exactly recomputable from task_facts")
        hashes = {ref.receipt_hash for ref in self.receipt_refs}
        if self.verifiable_receipt_count != len(hashes) or len(hashes) != len(self.receipt_refs):
            raise ValueError("verifiable_receipt_count must equal unique receipt refs")
        fact_hashes = {ref.receipt_hash for fact in facts for ref in fact.receipt_refs}
        if hashes != fact_hashes:
            raise ValueError("projection receipt refs must exactly cover task fact sources")
        return self

    def sources_for(self, category: HistoryCategory) -> tuple[ReceiptSourceRef, ...]:
        hashes = {
            ref.receipt_hash
            for fact in self.task_facts
            if fact.category is category
            for ref in fact.receipt_refs
        }
        return tuple(ref for ref in self.receipt_refs if ref.receipt_hash in hashes)


class ServiceComparison(DomainModel):
    task_type: Identifier
    services: tuple[ServiceHistoryProjection, ServiceHistoryProjection]

    @model_validator(mode="after")
    def enforce_two_distinct_services(self) -> ServiceComparison:
        if any(service.task_type != self.task_type for service in self.services):
            raise ValueError("comparison services must share the selected task type")
        if self.services[0].service_id == self.services[1].service_id:
            raise ValueError("comparison requires two distinct services")
        return self


class ManualServiceSelection(DomainModel):
    task_type: Identifier
    selected_service_id: Identifier
    considered_service_ids: tuple[Identifier, Identifier]
    selected_at: UtcDatetime
    rationale: NonEmptyText | None = None
