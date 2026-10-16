"""EIP-712 task acceptance and report-delivery commitments."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, StrictInt, StrictStr, model_validator

from trust_receipt.models.base import DomainModel, EvmAddress, Hex32, Identifier, UtcDatetime
from trust_receipt.models.enums import CommitmentAnchorStatus

Eip712Signature = Annotated[StrictStr, Field(pattern=r"^0x[0-9a-fA-F]{130}$")]


class CommitmentAnchor(DomainModel):
    chain_id: StrictInt = Field(gt=0)
    status: CommitmentAnchorStatus
    transaction_hash: Hex32 | None = None
    block_number: StrictInt | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def enforce_state(self) -> CommitmentAnchor:
        if self.status is CommitmentAnchorStatus.CONFIRMED:
            if self.transaction_hash is None or self.block_number is None:
                raise ValueError("CONFIRMED anchor requires transaction_hash and block_number")
        elif self.status is CommitmentAnchorStatus.NOT_SUBMITTED and (
            self.transaction_hash is not None or self.block_number is not None
        ):
            raise ValueError("NOT_SUBMITTED anchor cannot contain transaction details")
        return self


class TaskCommitment(DomainModel):
    commitment_version: Literal["1.0"]
    commitment_id: Identifier
    task_id: Identifier
    spec_hash: Hex32
    requester_address: EvmAddress
    service_id: Identifier
    created_at: UtcDatetime
    expires_at: UtcDatetime | None
    signature_scheme: Literal["EIP712"]
    signature: Eip712Signature
    anchor: CommitmentAnchor

    @model_validator(mode="after")
    def validate_expiry(self) -> TaskCommitment:
        if self.expires_at is not None and self.expires_at <= self.created_at:
            raise ValueError("expires_at must be later than created_at")
        return self


class DeliveryCommitment(DomainModel):
    commitment_version: Literal["1.0"]
    task_commitment_id: Identifier
    task_commitment_hash: Hex32
    spec_hash: Hex32
    submission_id: Identifier
    service_id: Identifier
    attempt: StrictInt = Field(ge=1, le=2)
    report_hash: Hex32
    accepted_at: UtcDatetime
    submitted_at: UtcDatetime
    signer_address: EvmAddress
    signature_scheme: Literal["EIP712"]
    acceptance_signature: Eip712Signature
    signature: Eip712Signature

    @model_validator(mode="after")
    def validate_times(self) -> DeliveryCommitment:
        if self.submitted_at < self.accepted_at:
            raise ValueError("submitted_at must not be earlier than accepted_at")
        return self
