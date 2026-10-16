"""Portable receipt and explicit publication lifecycle models."""

from typing import Literal

from pydantic import StrictBool, model_validator

from trust_receipt.models.base import (
    DomainModel,
    EvmAddress,
    Hex32,
    Identifier,
    NonEmptyText,
    NonNegativeInt,
    PositiveInt,
    UtcDatetime,
)
from trust_receipt.models.enums import EvidenceSource, PublicationChainStatus
from trust_receipt.models.plans import VerificationPlan
from trust_receipt.models.tasks import TaskSpec
from trust_receipt.models.verification import VerificationResult


class ServiceIdentity(DomainModel):
    service_id: Identifier
    name: NonEmptyText
    identity_scheme: Identifier
    identity_reference: NonEmptyText


class EvidenceDescriptor(DomainModel):
    evidence_id: Identifier
    source: EvidenceSource
    content_hash: Hex32
    uri: NonEmptyText | None
    event_keys: tuple[str, ...]


class Publication(DomainModel):
    authorized: StrictBool
    uri: NonEmptyText | None
    content_hash: Hex32 | None
    transaction_hash: Hex32 | None
    chain_status: PublicationChainStatus
    chain_id: PositiveInt | None = None
    reviewer_address: EvmAddress | None = None
    transaction_nonce: NonNegativeInt | None = None
    feedback_index: PositiveInt | None = None
    block_number: NonNegativeInt | None = None
    error_code: Identifier | None = None
    error_message: NonEmptyText | None = None

    @model_validator(mode="after")
    def enforce_publication_state(self) -> "Publication":
        if not self.authorized:
            public_values = (
                self.uri,
                self.content_hash,
                self.transaction_hash,
                self.chain_id,
                self.reviewer_address,
                self.transaction_nonce,
                self.feedback_index,
                self.block_number,
                self.error_code,
                self.error_message,
            )
            if any(value is not None for value in public_values):
                raise ValueError("unauthorized publication cannot contain public references")
            if self.chain_status is not PublicationChainStatus.NOT_SUBMITTED:
                raise ValueError("unauthorized publication must be NOT_SUBMITTED")
        if self.chain_status in {PublicationChainStatus.SUBMITTED, PublicationChainStatus.CONFIRMED} and (
            not self.authorized
            or self.uri is None
            or self.content_hash is None
            or self.chain_id is None
            or self.reviewer_address is None
            or self.transaction_nonce is None
        ):
            raise ValueError(
                "submitted publication requires authorization, public content, chain, reviewer, and nonce"
            )
        if self.chain_status is PublicationChainStatus.CONFIRMED and (
            self.transaction_hash is None or self.feedback_index is None or self.block_number is None
        ):
            raise ValueError("confirmed publication requires transaction, feedback index, and block")
        if self.chain_status is PublicationChainStatus.FAILED and self.error_code is None:
            raise ValueError("failed publication requires an error code")
        return self


class Receipt(DomainModel):
    receipt_version: Literal["1.0"]
    receipt_id: Identifier
    task_spec: TaskSpec
    service_identity: ServiceIdentity
    submission_hash: Hex32
    verification_plan: VerificationPlan
    verification_result: VerificationResult
    evidence_manifest: tuple[EvidenceDescriptor, ...]
    created_at: UtcDatetime
    receipt_hash: Hex32
    publication: Publication

    @model_validator(mode="after")
    def enforce_receipt_links(self) -> "Receipt":
        task_id = self.task_spec.task_id
        if self.verification_plan.task_id != task_id or self.verification_result.task_id != task_id:
            raise ValueError("receipt task references must match task_spec.task_id")
        return self
