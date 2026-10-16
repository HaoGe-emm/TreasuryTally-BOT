"""Append-only local JSON receipt storage."""

from __future__ import annotations

import os
from pathlib import Path

from trust_receipt.hashing import canonical_json_bytes, verify_receipt_hash
from trust_receipt.models.receipts import Receipt


class ReceiptIntegrityError(ValueError):
    pass


def save_receipt(receipt: Receipt, path: str | Path) -> Path:
    """Create a receipt file once; existing evidence is never overwritten."""
    if not verify_receipt_hash(receipt):
        raise ReceiptIntegrityError("receipt_hash does not match canonical receipt content")
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = canonical_json_bytes(receipt) + b"\n"
    with target.open("xb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    return target


def load_receipt(path: str | Path) -> Receipt:
    receipt = Receipt.model_validate_json(Path(path).read_bytes())
    if not verify_receipt_hash(receipt):
        raise ReceiptIntegrityError("receipt_hash does not match canonical receipt content")
    return receipt
