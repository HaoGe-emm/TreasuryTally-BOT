"""Task-scoped, receipt-backed service history projections."""

from trust_receipt.history.models import (
    HistoryCategory,
    ManualServiceSelection,
    ReceiptRevisionLink,
    ReceiptSourceRef,
    RevisionResolution,
    ServiceComparison,
    ServiceHistoryProjection,
    ServiceTaskFact,
)
from trust_receipt.history.ports import NoReceiptRevisions, ReceiptRevisionPort
from trust_receipt.history.projection import (
    ReceiptHistoryInput,
    compare_services,
    project_service_histories,
    record_manual_selection,
)

__all__ = [
    "HistoryCategory",
    "ManualServiceSelection",
    "NoReceiptRevisions",
    "ReceiptHistoryInput",
    "ReceiptRevisionLink",
    "ReceiptRevisionPort",
    "ReceiptSourceRef",
    "RevisionResolution",
    "ServiceComparison",
    "ServiceHistoryProjection",
    "ServiceTaskFact",
    "compare_services",
    "project_service_histories",
    "record_manual_selection",
]
