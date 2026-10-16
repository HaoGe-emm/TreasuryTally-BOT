"""M6 use case for explicit publication and ERC-8004 lifecycle transitions."""

from __future__ import annotations

from trust_receipt.hashing import receipt_hash
from trust_receipt.models.enums import PublicationChainStatus
from trust_receipt.models.receipts import Receipt
from trust_receipt.publishing import ContentPublisher, PublishedArtifact, publish_receipt
from trust_receipt.reputation import ERC8004ReceiptFeedback


class M6Workflow:
    def __init__(self, repository) -> None:
        self._repository = repository

    def publish(
        self,
        receipt: Receipt,
        publisher: ContentPublisher,
        *,
        authorized: bool,
    ) -> tuple[Receipt, PublishedArtifact]:
        if not authorized:
            raise ValueError("explicit public-receipt authorization is required")
        published, artifact = publish_receipt(receipt, publisher)
        self._repository.append_publication(published)
        return published, artifact

    def submit_feedback(
        self,
        receipt: Receipt,
        adapter: ERC8004ReceiptFeedback,
        *,
        authorized: bool,
    ) -> Receipt:
        if not authorized:
            raise ValueError("explicit ERC-8004 write authorization is required")
        submitted = adapter.submit_once(receipt)
        self._repository.append_publication(submitted)
        return submitted

    def reconcile_feedback(self, receipt: Receipt, adapter: ERC8004ReceiptFeedback) -> Receipt:
        reconciled = adapter.reconcile(receipt)
        if reconciled.receipt_hash != receipt.receipt_hash:
            self._repository.append_publication(reconciled)
        return reconciled

    def recover_failed(self, receipt: Receipt, *, authorized: bool) -> Receipt:
        """Explicitly return a terminal failure to NOT_SUBMITTED; never used for unknown writes."""
        if not authorized:
            raise ValueError("explicit failed-write recovery authorization is required")
        if receipt.publication.chain_status is not PublicationChainStatus.FAILED:
            raise ValueError("only FAILED publication can be recovered")
        if receipt.publication.error_code == "TRANSACTION_UNKNOWN":
            raise ValueError("unknown write status must be reconciled and cannot be reset")
        publication = receipt.publication.model_copy(
            update={
                "chain_status": PublicationChainStatus.NOT_SUBMITTED,
                "transaction_hash": None,
                "chain_id": None,
                "reviewer_address": None,
                "transaction_nonce": None,
                "feedback_index": None,
                "block_number": None,
                "error_code": None,
                "error_message": None,
            }
        )
        draft = receipt.model_copy(
            update={"publication": publication, "receipt_hash": "0x" + "0" * 64}
        )
        recovered = draft.model_copy(update={"receipt_hash": receipt_hash(draft)})
        self._repository.append_publication(recovered)
        return recovered

    def latest(self, receipt: Receipt) -> Receipt:
        events = self._repository.list_publications(receipt.receipt_id)
        return events[-1].receipt if events else receipt
