"""Ports that keep M9 revision storage outside the M10 read model."""

from __future__ import annotations

from typing import Protocol

from trust_receipt.history.models import ReceiptRevisionLink


class ReceiptRevisionPort(Protocol):
    def get_revision(self, receipt_hash: str) -> ReceiptRevisionLink | None: ...


class NoReceiptRevisions:
    """Fallback until an M9 revision adapter is configured."""

    def get_revision(self, receipt_hash: str) -> ReceiptRevisionLink | None:
        return None
