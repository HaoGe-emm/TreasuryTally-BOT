from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

from trust_receipt.hashing import canonical_json_bytes, content_hash
from trust_receipt.m9 import (
    CommitmentStatus,
    CommitmentVerification,
    PublicReceiptReference,
    PublicReferenceKind,
    PublicVerificationStatus,
    ResolvedPublicReceipt,
    build_receipt_revision,
    verify_public_reference,
)
from trust_receipt.publishing import authorize_public_receipt


@dataclass
class StaticResolver:
    resolved: ResolvedPublicReceipt

    def resolve(self, reference):
        del reference
        return self.resolved


class VerifiedCommitments:
    def verify(self, receipt, *, attempt):
        return CommitmentVerification(
            status=CommitmentStatus.VERIFIED,
            evidence_refs=(f"commitment:{receipt.task_spec.spec_hash}:{attempt}",),
            reason=None,
        )


def _public(receipt):
    public = authorize_public_receipt(receipt)
    payload = canonical_json_bytes(public) + b"\n"
    return public, payload


@pytest.mark.parametrize(
    "kind",
    [
        PublicReferenceKind.URI,
        PublicReferenceKind.RECEIPT_HASH,
        PublicReferenceKind.TASK_HASH,
        PublicReferenceKind.FEEDBACK_TRANSACTION,
    ],
)
def test_all_public_entry_kinds_resolve_to_the_same_verified_relationship(two_attempts, kind) -> None:
    receipt, payload = _public(two_attempts.first_receipt)
    revision = build_receipt_revision(receipt, attempt=1)
    transaction_hash = "0x" + "ab" * 32
    value = {
        PublicReferenceKind.URI: "https://example.test/receipt.json",
        PublicReferenceKind.RECEIPT_HASH: receipt.receipt_hash,
        PublicReferenceKind.TASK_HASH: receipt.task_spec.spec_hash,
        PublicReferenceKind.FEEDBACK_TRANSACTION: transaction_hash,
    }[kind]
    resolver = StaticResolver(
        ResolvedPublicReceipt(
            payload=payload,
            attempt=1,
            expected_content_hash=content_hash(payload),
            feedback_transaction_hash=transaction_hash,
            feedback_binding_verified=True,
            revision=revision,
            evidence_refs=("public-index:fixture",),
        )
    )

    result = verify_public_reference(
        PublicReceiptReference(kind=kind, value=value),
        resolver,
        commitment_verifier=VerifiedCommitments(),
    )

    assert result.status is PublicVerificationStatus.VERIFIED
    assert result.task_id == receipt.task_spec.task_id
    assert result.service_id == receipt.service_identity.service_id
    assert result.attempt == 1
    assert result.receipt_hash == receipt.receipt_hash
    assert result.outcome == receipt.verification_result.outcome
    assert result.commitment_status is CommitmentStatus.VERIFIED


def test_missing_commitment_port_is_explicitly_unverified_but_v1_replay_stays_valid(two_attempts) -> None:
    receipt, payload = _public(two_attempts.first_receipt)
    result = verify_public_reference(
        PublicReceiptReference(PublicReferenceKind.RECEIPT_HASH, receipt.receipt_hash),
        StaticResolver(
            ResolvedPublicReceipt(
                payload=payload,
                attempt=1,
                expected_content_hash=content_hash(payload),
            )
        ),
    )

    assert result.status is PublicVerificationStatus.VERIFIED
    assert result.commitment_status is CommitmentStatus.UNVERIFIED
    assert any(check.check_id == "m8-commitment" for check in result.checks)


def test_attempt_two_without_parent_revision_is_inconclusive(two_attempts) -> None:
    first, _ = _public(two_attempts.first_receipt)
    second, payload = _public(two_attempts.second_receipt)
    first_revision = build_receipt_revision(first, attempt=1)
    second_revision = build_receipt_revision(second, attempt=2, parent=first_revision)
    result = verify_public_reference(
        PublicReceiptReference(PublicReferenceKind.RECEIPT_HASH, second.receipt_hash),
        StaticResolver(
            ResolvedPublicReceipt(
                payload=payload,
                attempt=2,
                expected_content_hash=content_hash(payload),
                revision=second_revision,
                parent_revision=None,
            )
        ),
    )

    assert result.status is PublicVerificationStatus.INCONCLUSIVE
    assert "revision" in (result.reason or "").lower()


def test_tampered_public_receipt_is_invalid(two_attempts) -> None:
    receipt, payload = _public(two_attempts.first_receipt)
    tampered = payload.replace(receipt.receipt_id.encode(), b"tampered-receipt", 1)
    result = verify_public_reference(
        PublicReceiptReference(PublicReferenceKind.RECEIPT_HASH, receipt.receipt_hash),
        StaticResolver(
            ResolvedPublicReceipt(
                payload=tampered,
                attempt=1,
                expected_content_hash=content_hash(payload),
            )
        ),
    )

    assert result.status is PublicVerificationStatus.INVALID


def test_caller_supplied_feedback_text_is_not_independent_chain_evidence(two_attempts) -> None:
    _, payload = _public(two_attempts.first_receipt)
    tx = "0x" + "ab" * 32
    result = verify_public_reference(
        PublicReceiptReference(PublicReferenceKind.FEEDBACK_TRANSACTION, tx),
        StaticResolver(ResolvedPublicReceipt(
            payload=payload, attempt=1, feedback_transaction_hash=tx,
            expected_content_hash=content_hash(payload),
        )),
    )
    assert result.status is PublicVerificationStatus.INCONCLUSIVE


def test_float_in_finding_does_not_crash_public_verification(two_attempts) -> None:
    receipt, _ = _public(two_attempts.first_receipt)
    raw = receipt.model_dump(mode="json")
    raw["verification_result"]["findings"][0]["expected"] = {"amount": 1.5}
    result = verify_public_reference(
        PublicReceiptReference(PublicReferenceKind.RECEIPT_HASH, receipt.receipt_hash),
        StaticResolver(ResolvedPublicReceipt(payload=json.dumps(raw).encode(), attempt=1)),
    )
    assert result.status is PublicVerificationStatus.INVALID


def test_standalone_cli_replays_public_receipt_without_database(tmp_path, two_attempts) -> None:
    receipt, payload = _public(two_attempts.first_receipt)
    path = tmp_path / "public-receipt.json"
    path.write_bytes(payload)
    project_root = Path(__file__).resolve().parents[2]
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(project_root / "src")

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "trust_receipt.m9.cli",
            str(path),
            "--kind",
            PublicReferenceKind.RECEIPT_HASH.value,
            "--value",
            receipt.receipt_hash,
            "--attempt",
            "1",
            "--expected-content-hash",
            content_hash(payload),
        ],
        cwd=project_root,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    result = json.loads(completed.stdout)
    assert result["status"] == "VERIFIED"
    assert result["commitment_status"] == "UNVERIFIED"
