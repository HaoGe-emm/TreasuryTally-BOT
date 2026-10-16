"""Stable EVM comparison keys without changing evidence presentation."""

from __future__ import annotations

from trust_receipt.models.transfers import TransferRecord

type EventKey = tuple[int, str, int]


def address_key(address: str) -> str:
    return address.lower()


def event_key(record: TransferRecord) -> EventKey:
    return (record.chain_id, record.transaction_hash.lower(), record.log_index)


def event_ref(record: TransferRecord) -> str:
    chain_id, transaction_hash, log_index = event_key(record)
    return f"{record.source.value}:{chain_id}:{transaction_hash}:{log_index}"


def equivalent_reference(left: TransferRecord, right: TransferRecord) -> bool:
    """Allow a missing block hash, but reject conflicting known facts."""
    return (
        event_key(left) == event_key(right)
        and address_key(left.token_address) == address_key(right.token_address)
        and left.block_number == right.block_number
        and (left.block_hash is None or right.block_hash is None or left.block_hash.lower() == right.block_hash.lower())
        and address_key(left.from_address) == address_key(right.from_address)
        and address_key(left.to_address) == address_key(right.to_address)
        and left.amount_base_units == right.amount_base_units
        and left.token_decimals == right.token_decimals
    )
