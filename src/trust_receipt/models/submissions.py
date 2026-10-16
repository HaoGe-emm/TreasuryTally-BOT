"""Versioned service claims retained independently for each attempt."""

from typing import Literal

from pydantic import Field, StrictInt, StrictStr, model_validator

from trust_receipt.models.base import (
    DecimalIntegerString,
    DomainModel,
    Hex32,
    Identifier,
    NonNegativeInt,
    UtcDatetime,
)
from trust_receipt.models.enums import EvidenceSource
from trust_receipt.models.transfers import TransferRecord


class ServiceSubmission(DomainModel):
    schema_version: Literal["1.0"]
    submission_id: Identifier
    task_id: Identifier
    service_id: Identifier
    service_version: Identifier
    attempt: StrictInt = Field(ge=1, le=2)
    claimed_total_base_units: DecimalIntegerString
    claimed_count: NonNegativeInt
    transfers: tuple[TransferRecord, ...] = Field(max_length=200)
    report_text: StrictStr
    created_at: UtcDatetime
    report_hash: Hex32
    signature: StrictStr | None

    @model_validator(mode="after")
    def require_service_sources(self) -> "ServiceSubmission":
        if any(transfer.source is not EvidenceSource.SERVICE for transfer in self.transfers):
            raise ValueError("submission transfers must use source=service")
        return self
