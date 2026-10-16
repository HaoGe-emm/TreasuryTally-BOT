"""Provider-independent public artifact metadata."""

from pydantic import StrictInt

from trust_receipt.models.base import DomainModel, Hex32, NonEmptyText, PositiveInt, UtcDatetime
from trust_receipt.models.receipts import Receipt


class PublishedArtifact(DomainModel):
    uri: NonEmptyText
    content_hash: Hex32
    byte_length: StrictInt


class PublicationEvent(DomainModel):
    receipt_id: NonEmptyText
    sequence: PositiveInt
    recorded_at: UtcDatetime
    receipt: Receipt
