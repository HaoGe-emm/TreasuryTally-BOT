"""Validate M9 revisions against their actual immutable receipts before projection."""

from collections.abc import Iterable

from trust_receipt.history.models import ReceiptRevisionLink, RevisionResolution
from trust_receipt.m9.models import ReceiptRevision
from trust_receipt.m9.revisions import build_receipt_revision, validate_revision_pair
from trust_receipt.models import Receipt
from trust_receipt.receipts import replay_receipt


class VerifiedM9RevisionAdapter:
    def __init__(self, receipts: Iterable[Receipt], revisions: Iterable[ReceiptRevision]) -> None:
        by_hash = {receipt.receipt_hash: receipt for receipt in receipts}
        by_revision = {revision.receipt_hash: revision for revision in revisions}
        self._links: dict[str, ReceiptRevisionLink] = {}
        for revision in by_revision.values():
            receipt = by_hash.get(revision.receipt_hash)
            if receipt is None or not replay_receipt(receipt).valid:
                raise ValueError("revision requires an independently verified receipt")
            parent = by_revision.get(revision.parent_receipt_hash)
            if revision.attempt == 2:
                if parent is None:
                    raise ValueError("revision chain is missing its parent")
                parent_receipt = by_hash.get(parent.receipt_hash)
                if parent_receipt is None or not replay_receipt(parent_receipt).valid:
                    raise ValueError("revision chain is missing its verified parent receipt")
                validate_revision_pair(parent, revision)
                if parent_receipt.task_spec != receipt.task_spec:
                    raise ValueError("revision chain must bind the same immutable task spec")
                if parent_receipt.created_at > receipt.created_at:
                    raise ValueError("revision child cannot precede its parent")
                if build_receipt_revision(parent_receipt, attempt=1) != parent:
                    raise ValueError("parent revision does not match the actual receipt")
            expected = build_receipt_revision(receipt, attempt=revision.attempt, parent=parent)
            if expected != revision:
                raise ValueError("revision does not match the actual receipt")
            self._links[receipt.receipt_hash] = ReceiptRevisionLink(
                receipt_hash=receipt.receipt_hash,
                parent_receipt_hash=revision.parent_receipt_hash,
                supersedes_receipt_hash=revision.supersedes_receipt_hash,
                resolution=RevisionResolution(revision.resolution.value),
            )

    def get_revision(self, receipt_hash: str) -> ReceiptRevisionLink | None:
        return self._links.get(receipt_hash)
