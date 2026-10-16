"""Provider-neutral ERC-20 transfer evidence."""

from pydantic import Field

from trust_receipt.models.base import (
    DecimalIntegerString,
    DomainModel,
    EventKey,
    EvmAddress,
    Hex32,
    NonNegativeInt,
    PositiveInt,
)
from trust_receipt.models.enums import EvidenceSource


class TransferRecord(DomainModel):
    chain_id: PositiveInt
    token_address: EvmAddress
    transaction_hash: Hex32
    log_index: NonNegativeInt
    block_number: NonNegativeInt
    block_hash: Hex32 | None
    from_address: EvmAddress
    to_address: EvmAddress
    amount_base_units: DecimalIntegerString
    token_decimals: NonNegativeInt = Field(le=255)
    source: EvidenceSource

    @property
    def event_key(self) -> EventKey:
        return (self.chain_id, self.transaction_hash, self.log_index)
