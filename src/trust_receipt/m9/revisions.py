"""Append-only receipt revision records and deterministic repair comparison."""

from __future__ import annotations

import os
from pathlib import Path

from trust_receipt.hashing import (
    canonical_json_bytes,
    hash_model,
    stable_hash,
    verify_receipt_hash,
    verify_submission_hash,
)
from trust_receipt.m9.models import (
    AttemptSnapshot,
    CommitmentStatus,
    ReceiptRevision,
    RepairComparison,
    RevisionResolution,
)
from trust_receipt.m9.ports import (
    ReceiptCommitmentVerifier,
    SubmissionSignatureVerifier,
    V1SubmissionSignatureVerifier,
)
from trust_receipt.models.enums import VerificationOutcome
from trust_receipt.models.receipts import Receipt
from trust_receipt.models.submissions import ServiceSubmission


def receipt_evidence_refs(receipt: Receipt) -> tuple[str, ...]:
    refs = {
        f"receipt:{receipt.receipt_hash}",
        f"task:{receipt.task_spec.spec_hash}",
        f"submission:{receipt.submission_hash}",
    }
    for descriptor in receipt.evidence_manifest:
        refs.add(f"evidence:{descriptor.evidence_id}:{descriptor.content_hash}")
        refs.update(f"event:{event_key}" for event_key in descriptor.event_keys)
        if descriptor.uri is not None:
            refs.add(descriptor.uri)
    if receipt.publication.uri is not None:
        refs.add(receipt.publication.uri)
    if receipt.publication.transaction_hash is not None:
        refs.add(f"feedback-transaction:{receipt.publication.transaction_hash}")
    return tuple(sorted(refs))


def receipt_revision_hash(revision: ReceiptRevision) -> str:
    return hash_model(revision, exclude=frozenset({"revision_hash"}))


def verify_receipt_revision_hash(revision: ReceiptRevision) -> bool:
    return revision.revision_hash == receipt_revision_hash(revision)


def build_receipt_revision(
    receipt: Receipt,
    *,
    attempt: int,
    parent: ReceiptRevision | None = None,
) -> ReceiptRevision:
    if not verify_receipt_hash(receipt):
        raise ValueError("receipt hash is invalid")
    if attempt == 1:
        if parent is not None:
            raise ValueError("attempt 1 cannot have a parent revision")
        resolution = RevisionResolution.ORIGINAL
        parent_hash = None
    elif attempt == 2:
        if parent is None or parent.attempt != 1:
            raise ValueError("attempt 2 requires the task's attempt 1 revision")
        if not verify_receipt_revision_hash(parent):
            raise ValueError("parent revision hash is invalid")
        if parent.task_id != receipt.task_spec.task_id:
            raise ValueError("parent revision must reference the same task")
        if parent.outcome is VerificationOutcome.PASS:
            raise ValueError("attempt 2 cannot supersede a PASS receipt")
        if parent.receipt_hash == receipt.receipt_hash:
            raise ValueError("attempt 2 receipt must differ from its parent")
        resolution = (
            RevisionResolution.FIXED
            if receipt.verification_result.outcome is VerificationOutcome.PASS
            else RevisionResolution.UNRESOLVED
        )
        parent_hash = parent.receipt_hash
    else:
        raise ValueError("M9 supports only attempts 1 and 2")
    draft = ReceiptRevision(
        revision_version="1.0",
        task_id=receipt.task_spec.task_id,
        service_id=receipt.service_identity.service_id,
        attempt=attempt,
        receipt_hash=receipt.receipt_hash,
        outcome=receipt.verification_result.outcome,
        resolution=resolution,
        parent_receipt_hash=parent_hash,
        supersedes_receipt_hash=parent_hash,
        evidence_refs=receipt_evidence_refs(receipt),
        created_at=receipt.created_at,
        revision_hash="0x" + "0" * 64,
    )
    return draft.model_copy(update={"revision_hash": receipt_revision_hash(draft)})


def validate_revision_pair(parent: ReceiptRevision, child: ReceiptRevision) -> None:
    if not verify_receipt_revision_hash(parent) or not verify_receipt_revision_hash(child):
        raise ValueError("revision hash does not match canonical revision content")
    if parent.attempt != 1 or child.attempt != 2:
        raise ValueError("revision pair must be ordered attempt 1 then attempt 2")
    if parent.task_id != child.task_id:
        raise ValueError("revision pair must reference the same task")
    if parent.outcome is VerificationOutcome.PASS:
        raise ValueError("attempt 2 cannot follow a PASS receipt")
    if parent.receipt_hash == child.receipt_hash:
        raise ValueError("revision pair must contain distinct receipts")
    if child.parent_receipt_hash != parent.receipt_hash:
        raise ValueError("child parent link does not match the first receipt")
    if child.supersedes_receipt_hash != parent.receipt_hash:
        raise ValueError("child supersedes link does not match the first receipt")


class LocalRevisionStore:
    """One immutable file per revision; append never edits an earlier record."""

    def __init__(self, directory: str | Path) -> None:
        self._directory = Path(directory)

    def _task_directory(self, task_id: str) -> Path:
        return self._directory / stable_hash({"task_id": task_id}).removeprefix("0x")

    def list(self, task_id: str) -> tuple[ReceiptRevision, ...]:
        directory = self._task_directory(task_id)
        if not directory.is_dir():
            return ()
        revisions = tuple(
            ReceiptRevision.model_validate_json(path.read_bytes())
            for path in sorted(directory.glob("attempt-*.json"))
        )
        if any(not verify_receipt_revision_hash(revision) for revision in revisions):
            raise ValueError("revision hash does not match canonical revision content")
        if any(revision.task_id != task_id for revision in revisions):
            raise ValueError("revision store contains records for a different task")
        if len(revisions) > 2:
            raise ValueError("revision store contains more than two attempts")
        if revisions and revisions[0].attempt != 1:
            raise ValueError("revision store is missing attempt 1")
        if len(revisions) == 2:
            validate_revision_pair(revisions[0], revisions[1])
        return revisions

    def append(self, revision: ReceiptRevision) -> Path:
        if not verify_receipt_revision_hash(revision):
            raise ValueError("revision hash does not match canonical revision content")
        existing = self.list(revision.task_id)
        if revision.attempt != len(existing) + 1:
            raise ValueError("receipt revisions must be appended in consecutive attempt order")
        if existing:
            validate_revision_pair(existing[0], revision)
        directory = self._task_directory(revision.task_id)
        directory.mkdir(parents=True, exist_ok=True)
        target = directory / f"attempt-{revision.attempt}-{revision.receipt_hash.removeprefix('0x')}.json"
        payload = canonical_json_bytes(revision) + b"\n"
        with target.open("xb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        return target


def _finding_key(finding) -> tuple[object, ...]:
    return (
        finding.finding_type,
        finding.violated_rule,
        tuple(sorted(finding.evidence_refs)),
    )


def _commitment_status(
    receipt: Receipt,
    attempt: int,
    verifier: ReceiptCommitmentVerifier | None,
) -> CommitmentStatus:
    if verifier is None:
        return CommitmentStatus.UNVERIFIED
    try:
        return verifier.verify(receipt, attempt=attempt).status
    except (KeyError, LookupError, OSError, TimeoutError, ValueError):
        return CommitmentStatus.UNVERIFIED


def _snapshot(
    receipt: Receipt,
    submission: ServiceSubmission,
    revision: ReceiptRevision,
    commitment_verifier: ReceiptCommitmentVerifier | None,
    signature_verifier: SubmissionSignatureVerifier,
) -> AttemptSnapshot:
    if not verify_receipt_hash(receipt) or not verify_submission_hash(submission):
        raise ValueError("comparison requires valid receipt and submission hashes")
    if submission.report_hash != receipt.submission_hash:
        raise ValueError("submission hash does not match its receipt")
    if submission.submission_id != receipt.verification_result.submission_id:
        raise ValueError("submission ID does not match its verification result")
    if not signature_verifier.verify(submission, receipt.service_identity):
        raise ValueError("submission signature does not match the receipt service identity")
    if submission.attempt != revision.attempt:
        raise ValueError("submission attempt does not match its revision")
    expected = (
        receipt.task_spec.task_id,
        receipt.service_identity.service_id,
        receipt.receipt_hash,
        receipt.verification_result.outcome,
    )
    actual = (revision.task_id, revision.service_id, revision.receipt_hash, revision.outcome)
    if actual != expected:
        raise ValueError("revision fields do not match the referenced receipt")
    return AttemptSnapshot(
        task_id=revision.task_id,
        service_id=revision.service_id,
        submission_id=submission.submission_id,
        attempt=revision.attempt,
        receipt_hash=revision.receipt_hash,
        outcome=revision.outcome,
        resolution=revision.resolution,
        claimed_total_base_units=submission.claimed_total_base_units,
        calculated_total_base_units=receipt.verification_result.calculated_total_base_units,
        finding_ids=tuple(finding.finding_id for finding in receipt.verification_result.findings),
        evidence_refs=revision.evidence_refs,
        commitment_status=_commitment_status(receipt, revision.attempt, commitment_verifier),
    )


def build_repair_comparison(
    *,
    before_receipt: Receipt,
    before_submission: ServiceSubmission,
    before_revision: ReceiptRevision,
    after_receipt: Receipt,
    after_submission: ServiceSubmission,
    after_revision: ReceiptRevision,
    commitment_verifier: ReceiptCommitmentVerifier | None = None,
    signature_verifier: SubmissionSignatureVerifier | None = None,
) -> RepairComparison:
    validate_revision_pair(before_revision, after_revision)
    if before_receipt.task_spec.spec_hash != after_receipt.task_spec.spec_hash:
        raise ValueError("repair comparison requires the same immutable task spec")
    signatures = signature_verifier or V1SubmissionSignatureVerifier()
    before = _snapshot(
        before_receipt,
        before_submission,
        before_revision,
        commitment_verifier,
        signatures,
    )
    after = _snapshot(
        after_receipt,
        after_submission,
        after_revision,
        commitment_verifier,
        signatures,
    )
    before_findings = {
        _finding_key(finding): finding.finding_id
        for finding in before_receipt.verification_result.findings
        if finding.is_confirmed_error
    }
    after_keys = {
        _finding_key(finding)
        for finding in after_receipt.verification_result.findings
        if finding.is_confirmed_error
    }
    resolved = tuple(sorted(finding_id for key, finding_id in before_findings.items() if key not in after_keys))
    remaining = tuple(
        sorted(
            finding.finding_id
            for finding in after_receipt.verification_result.findings
            if finding.is_confirmed_error
        )
    )
    return RepairComparison(
        comparison_version="1.0",
        task_id=before.task_id,
        before=before,
        after=after,
        resolved_finding_ids=resolved,
        remaining_finding_ids=remaining,
        resolution=after.resolution,
    )
