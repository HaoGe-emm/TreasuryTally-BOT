from __future__ import annotations

import pytest

from trust_receipt.hashing import verify_receipt_hash
from trust_receipt.m9 import (
    CommitmentStatus,
    LocalRevisionStore,
    RevisionResolution,
    build_receipt_revision,
    build_repair_comparison,
)


def test_revisions_are_external_append_only_and_do_not_change_v1_hashes(tmp_path, two_attempts) -> None:
    first_hash = two_attempts.first_receipt.receipt_hash
    second_hash = two_attempts.second_receipt.receipt_hash
    first = build_receipt_revision(two_attempts.first_receipt, attempt=1)
    second = build_receipt_revision(two_attempts.second_receipt, attempt=2, parent=first)
    store = LocalRevisionStore(tmp_path / "revisions")

    store.append(first)
    store.append(second)

    assert two_attempts.first_receipt.receipt_hash == first_hash
    assert two_attempts.second_receipt.receipt_hash == second_hash
    assert verify_receipt_hash(two_attempts.first_receipt)
    assert verify_receipt_hash(two_attempts.second_receipt)
    assert second.parent_receipt_hash == first.receipt_hash
    assert second.supersedes_receipt_hash == first.receipt_hash
    assert second.resolution is RevisionResolution.FIXED
    assert store.list(first.task_id) == (first, second)
    with pytest.raises(ValueError, match="consecutive"):
        store.append(second)


def test_comparison_preserves_both_attempts_and_marks_commitments_unverified(two_attempts) -> None:
    first_revision = build_receipt_revision(two_attempts.first_receipt, attempt=1)
    second_revision = build_receipt_revision(
        two_attempts.second_receipt,
        attempt=2,
        parent=first_revision,
    )
    comparison = build_repair_comparison(
        before_receipt=two_attempts.first_receipt,
        before_submission=two_attempts.first_submission,
        before_revision=first_revision,
        after_receipt=two_attempts.second_receipt,
        after_submission=two_attempts.second_submission,
        after_revision=second_revision,
    )

    assert comparison.before.outcome.value == "FAIL"
    assert comparison.after.outcome.value == "PASS"
    assert comparison.before.receipt_hash != comparison.after.receipt_hash
    assert comparison.before.commitment_status is CommitmentStatus.UNVERIFIED
    assert comparison.after.commitment_status is CommitmentStatus.UNVERIFIED
    assert comparison.resolution is RevisionResolution.FIXED
    assert comparison.resolved_finding_ids
    assert comparison.remaining_finding_ids == ()
    assert comparison.before.evidence_refs
    assert comparison.after.evidence_refs


def test_comparison_reuses_v1_signature_verification(two_attempts) -> None:
    first_revision = build_receipt_revision(two_attempts.first_receipt, attempt=1)
    second_revision = build_receipt_revision(
        two_attempts.second_receipt,
        attempt=2,
        parent=first_revision,
    )
    invalid_submission = two_attempts.second_submission.model_copy(update={"signature": "0x00"})

    with pytest.raises(ValueError, match="signature"):
        build_repair_comparison(
            before_receipt=two_attempts.first_receipt,
            before_submission=two_attempts.first_submission,
            before_revision=first_revision,
            after_receipt=two_attempts.second_receipt,
            after_submission=invalid_submission,
            after_revision=second_revision,
        )
