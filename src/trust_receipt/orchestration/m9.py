"""M9 use cases over immutable M5/M8 outputs and stable storage ports."""

from __future__ import annotations

from dataclasses import dataclass

from trust_receipt.m9 import (
    LocalRevisionStore,
    PublicReceiptReference,
    ReceiptRevision,
    RepairComparison,
    ResolvedPublicReceipt,
    ReworkPackage,
    build_receipt_revision,
    build_repair_comparison,
    build_rework_package,
)
from trust_receipt.m9.commitments import M8CommitmentBinding, M8ReceiptCommitmentVerifier
from trust_receipt.models import Receipt, VerificationOutcome
from trust_receipt.receipts import load_receipt


@dataclass(frozen=True)
class M9Artifacts:
    rework_package: ReworkPackage | None
    revisions: tuple[ReceiptRevision, ...]
    comparison: RepairComparison | None
    commitment_verifier: M8ReceiptCommitmentVerifier
    receipts: tuple[Receipt, ...]


def _immutable_receipt(execution) -> Receipt:
    path = execution.receipt_path
    return load_receipt(path) if path is not None and path.is_file() else execution.receipt


def _ensure_revision(store: LocalRevisionStore, revision: ReceiptRevision) -> None:
    existing = store.list(revision.task_id)
    if revision.attempt <= len(existing):
        if existing[revision.attempt - 1] != revision:
            raise ValueError("stored M9 revision conflicts with the immutable attempt receipt")
        return
    store.append(revision)


def _commitment_verifier(executions, commitment_pairs) -> M8ReceiptCommitmentVerifier:
    bindings = []
    for execution, pair in zip(executions, commitment_pairs, strict=False):
        if pair is None:
            continue
        task_commitment, delivery_commitment, expected_signer = pair
        bindings.append(
            M8CommitmentBinding(
                task_commitment=task_commitment,
                delivery_commitment=delivery_commitment,
                submission=execution.submission,
                expected_signer=expected_signer,
            )
        )
    return M8ReceiptCommitmentVerifier(bindings)


def build_m9_artifacts(executions, commitment_pairs, store: LocalRevisionStore) -> M9Artifacts:
    verifier = _commitment_verifier(executions, commitment_pairs)
    if not executions:
        return M9Artifacts(None, (), None, verifier, ())
    receipts = tuple(_immutable_receipt(execution) for execution in executions)
    first_revision = build_receipt_revision(receipts[0], attempt=1)
    _ensure_revision(store, first_revision)
    revisions = [first_revision]
    package = None
    if receipts[0].verification_result.outcome is VerificationOutcome.FAIL:
        package = build_rework_package(
            receipts[0],
            package_id=f"rework-{receipts[0].receipt_hash[2:18]}",
            created_at=receipts[0].created_at,
        )
    comparison = None
    if len(executions) == 2:
        second_revision = build_receipt_revision(receipts[1], attempt=2, parent=first_revision)
        _ensure_revision(store, second_revision)
        revisions.append(second_revision)
        comparison = build_repair_comparison(
            before_receipt=receipts[0],
            before_submission=executions[0].submission,
            before_revision=first_revision,
            after_receipt=receipts[1],
            after_submission=executions[1].submission,
            after_revision=second_revision,
            commitment_verifier=verifier,
        )
    return M9Artifacts(package, tuple(revisions), comparison, verifier, receipts)


class PublisherReceiptResolver:
    """Resolve only the explicitly published URI and its independent byte hash."""

    def __init__(self, publisher, receipt: Receipt, *, attempt: int) -> None:
        self._publisher = publisher
        self._receipt = receipt
        self._attempt = attempt

    def resolve(self, reference: PublicReceiptReference) -> ResolvedPublicReceipt:
        publication = self._receipt.publication
        if publication.uri is None or publication.content_hash is None:
            raise LookupError("receipt has no public artifact")
        if reference.value != publication.uri:
            raise ValueError("reference is not the selected receipt URI")
        payload = self._publisher.fetch(publication.uri)
        return ResolvedPublicReceipt(
            payload=payload,
            attempt=self._attempt,
            expected_content_hash=publication.content_hash,
            feedback_transaction_hash=publication.transaction_hash,
            evidence_refs=(publication.uri,),
        )
