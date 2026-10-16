"""Read-only verification of public v1 receipts and M9 revision relationships."""

from __future__ import annotations

from pydantic import ValidationError

from trust_receipt.hashing import content_hash
from trust_receipt.m9.bundles import InvalidPublicEvidence, read_public_json
from trust_receipt.m9.models import (
    CommitmentStatus,
    PublicReferenceKind,
    PublicVerificationResult,
    PublicVerificationStatus,
    RevisionResolution,
    VerificationCheck,
    VerificationCheckState,
)
from trust_receipt.m9.ports import (
    PublicReceiptReference,
    PublicReceiptResolver,
    ReceiptCommitmentVerifier,
)
from trust_receipt.m9.revisions import (
    build_receipt_revision,
    receipt_evidence_refs,
    validate_revision_pair,
    verify_receipt_revision_hash,
)
from trust_receipt.models.receipts import Receipt
from trust_receipt.receipts import replay_receipt


def _terminal_result(
    reference: PublicReceiptReference,
    *,
    status: PublicVerificationStatus,
    check_id: str,
    detail: str,
) -> PublicVerificationResult:
    state = (
        VerificationCheckState.FAILED
        if status is PublicVerificationStatus.INVALID
        else VerificationCheckState.UNVERIFIED
    )
    return PublicVerificationResult(
        verification_version="1.0",
        reference_kind=reference.kind,
        reference_value=reference.value,
        status=status,
        task_id=None,
        service_id=None,
        attempt=None,
        receipt_hash=None,
        outcome=None,
        resolution=None,
        evidence_refs=(),
        commitment_status=CommitmentStatus.UNVERIFIED,
        checks=(VerificationCheck(check_id=check_id, state=state, detail=detail),),
        reason=detail,
    )


def _reference_check(reference: PublicReceiptReference, resolved, receipt: Receipt) -> VerificationCheck:
    if reference.kind is PublicReferenceKind.URI:
        return VerificationCheck(
            check_id="reference-binding",
            state=VerificationCheckState.PASSED,
            detail="The supplied public artifact is resolved under the requested URI; origin is not authenticated.",
        )
    if reference.kind is PublicReferenceKind.RECEIPT_HASH:
        valid = receipt.receipt_hash.lower() == reference.value.lower()
        detail = "Receipt hash matches the requested hash." if valid else "Receipt hash does not match the request."
    elif reference.kind is PublicReferenceKind.TASK_HASH:
        valid = receipt.task_spec.spec_hash.lower() == reference.value.lower()
        detail = "Task hash matches the requested hash." if valid else "Task hash does not match the request."
    else:
        observed = resolved.feedback_transaction_hash
        valid = observed is not None and observed.lower() == reference.value.lower()
        detail = (
            "Feedback transaction resolves to this public receipt."
            if valid
            else "Feedback transaction is missing or resolves to a different receipt."
        )
    return VerificationCheck(
        check_id="reference-binding",
        state=VerificationCheckState.PASSED if valid else VerificationCheckState.FAILED,
        detail=detail,
    )


def verify_public_reference(
    reference: PublicReceiptReference,
    resolver: PublicReceiptResolver,
    *,
    commitment_verifier: ReceiptCommitmentVerifier | None = None,
) -> PublicVerificationResult:
    """Resolve public evidence and replay it without database, UI, or model access."""
    try:
        resolved = resolver.resolve(reference)
    except InvalidPublicEvidence as exc:
        return _terminal_result(
            reference, status=PublicVerificationStatus.INVALID,
            check_id="public-integrity", detail=str(exc),
        )
    except (KeyError, LookupError, OSError, TimeoutError, ValueError, RuntimeError) as exc:
        return _terminal_result(
            reference,
            status=PublicVerificationStatus.INCONCLUSIVE,
            check_id="public-resolution",
            detail=f"Public receipt could not be resolved: {type(exc).__name__}",
        )
    if resolved.attempt not in (1, 2):
        return _terminal_result(
            reference,
            status=PublicVerificationStatus.INVALID,
            check_id="attempt-binding",
            detail="Resolved receipt attempt must be 1 or 2.",
        )
    try:
        receipt = Receipt.model_validate(read_public_json(resolved.payload))
        replay = replay_receipt(receipt)
    except (ValidationError, InvalidPublicEvidence, ValueError, TypeError):
        return _terminal_result(
            reference,
            status=PublicVerificationStatus.INVALID,
            check_id="receipt-schema",
            detail="Public bytes are not a valid Receipt 1.0 object.",
        )

    checks: list[VerificationCheck] = [
        VerificationCheck(
            check_id="receipt-replay",
            state=VerificationCheckState.PASSED if replay.valid else VerificationCheckState.FAILED,
            detail=(
                "Receipt hash, task hash, object links, and deterministic outcome replay are valid."
                if replay.valid
                else "Receipt integrity, object links, or deterministic outcome replay failed."
            ),
        ),
        _reference_check(reference, resolved, receipt),
        VerificationCheck(
            check_id="public-authorization",
            state=(
                VerificationCheckState.PASSED
                if receipt.publication.authorized
                else VerificationCheckState.FAILED
            ),
            detail=(
                "Receipt is an explicitly authorized public snapshot."
                if receipt.publication.authorized
                else "Receipt was not authorized for public verification."
            ),
        ),
    ]

    if resolved.expected_content_hash is None:
        checks.append(
            VerificationCheck(
                check_id="published-content-hash",
                state=VerificationCheckState.UNVERIFIED,
                detail="No independent published-byte hash was supplied by the resolver.",
            )
        )
    else:
        matches = content_hash(resolved.payload).lower() == resolved.expected_content_hash.lower()
        checks.append(
            VerificationCheck(
                check_id="published-content-hash",
                state=VerificationCheckState.PASSED if matches else VerificationCheckState.FAILED,
                detail=(
                    "Public bytes match the independently supplied content hash."
                    if matches
                    else "Public bytes do not match the independently supplied content hash."
                ),
            )
        )

    resolution: RevisionResolution | None = None
    revision_incomplete = False
    revision = resolved.revision
    if revision is None:
        resolution = RevisionResolution.ORIGINAL if resolved.attempt == 1 else None
        revision_incomplete = resolved.attempt == 2
        checks.append(
            VerificationCheck(
                check_id="revision-chain",
                state=VerificationCheckState.UNVERIFIED,
                detail=(
                    "Legacy attempt 1 receipt has no external revision record."
                    if resolved.attempt == 1
                    else "Attempt 2 is missing its required parent and supersedes revision evidence."
                ),
            )
        )
    else:
        try:
            expected = (
                receipt.task_spec.task_id,
                receipt.service_identity.service_id,
                resolved.attempt,
                receipt.receipt_hash,
                receipt.verification_result.outcome,
            )
            actual = (
                revision.task_id,
                revision.service_id,
                revision.attempt,
                revision.receipt_hash,
                revision.outcome,
            )
            if not verify_receipt_revision_hash(revision):
                raise ValueError("revision hash does not match canonical revision content")
            if expected != actual:
                raise ValueError("revision fields do not match the public receipt")
            if revision.attempt == 1 and resolved.parent_revision is not None:
                raise ValueError("attempt 1 cannot include a parent revision")
            if revision.attempt == 2:
                if resolved.parent_revision is None:
                    revision_incomplete = True
                    raise LookupError("attempt 2 parent revision is unavailable")
                validate_revision_pair(resolved.parent_revision, revision)
                parent_receipt = resolved.parent_receipt
                if parent_receipt is None:
                    revision_incomplete = True
                    raise LookupError("attempt 2 parent public receipt is unavailable")
                if not parent_receipt.publication.authorized or not replay_receipt(parent_receipt).valid:
                    raise ValueError("parent public receipt authorization or replay failed")
                if parent_receipt.task_spec.spec_hash != receipt.task_spec.spec_hash:
                    raise ValueError("parent public receipt changes the immutable task spec")
                if build_receipt_revision(parent_receipt, attempt=1) != resolved.parent_revision:
                    raise ValueError("parent revision does not bind the parent public receipt")
            resolution = revision.resolution
            checks.append(
                VerificationCheck(
                    check_id="revision-chain",
                    state=VerificationCheckState.PASSED,
                    detail="Receipt revision and parent/supersedes relationships are consistent.",
                )
            )
        except LookupError as exc:
            checks.append(
                VerificationCheck(
                    check_id="revision-chain",
                    state=VerificationCheckState.UNVERIFIED,
                    detail=str(exc),
                )
            )
        except ValueError as exc:
            checks.append(
                VerificationCheck(
                    check_id="revision-chain",
                    state=VerificationCheckState.FAILED,
                    detail=str(exc),
                )
            )

    if commitment_verifier is None:
        commitment_status = CommitmentStatus.UNVERIFIED
        checks.append(
            VerificationCheck(
                check_id="m8-commitment",
                state=VerificationCheckState.UNVERIFIED,
                detail="No M8 commitment verification port was provided.",
            )
        )
        commitment_refs: tuple[str, ...] = ()
    else:
        try:
            commitment = commitment_verifier.verify(receipt, attempt=resolved.attempt)
        except (KeyError, LookupError, OSError, TimeoutError, ValueError) as exc:
            commitment = None
            commitment_status = CommitmentStatus.UNVERIFIED
            commitment_refs = ()
            checks.append(
                VerificationCheck(
                    check_id="m8-commitment",
                    state=VerificationCheckState.UNVERIFIED,
                    detail=f"Commitment evidence is unavailable: {type(exc).__name__}",
                )
            )
        if commitment is None:
            pass
        else:
            commitment_status = commitment.status
            commitment_refs = commitment.evidence_refs
            state = {
                CommitmentStatus.VERIFIED: VerificationCheckState.PASSED,
                CommitmentStatus.UNVERIFIED: VerificationCheckState.UNVERIFIED,
                CommitmentStatus.INVALID: VerificationCheckState.FAILED,
            }[commitment.status]
            checks.append(
                VerificationCheck(
                    check_id="m8-commitment",
                    state=state,
                    detail=commitment.reason or "Task and delivery commitments are verified.",
                )
            )

    failures = [check for check in checks if check.state is VerificationCheckState.FAILED]
    feedback_incomplete = (
        reference.kind is PublicReferenceKind.FEEDBACK_TRANSACTION
        and (resolved.expected_content_hash is None or not resolved.feedback_binding_verified)
    )
    if failures:
        status = PublicVerificationStatus.INVALID
        reason = failures[0].detail
    elif revision_incomplete or feedback_incomplete:
        status = PublicVerificationStatus.INCONCLUSIVE
        reason = (
            "Necessary revision evidence is incomplete."
            if revision_incomplete
            else "Feedback verification requires an independently read chain event and content hash."
        )
    else:
        status = PublicVerificationStatus.VERIFIED
        reason = None

    evidence_refs = set(receipt_evidence_refs(receipt))
    evidence_refs.update(resolved.evidence_refs)
    evidence_refs.update(commitment_refs)
    if resolved.revision is not None:
        evidence_refs.update(resolved.revision.evidence_refs)
        evidence_refs.add(f"revision:{resolved.revision.revision_hash}")
    if resolved.parent_revision is not None:
        evidence_refs.update(resolved.parent_revision.evidence_refs)
        evidence_refs.add(f"revision:{resolved.parent_revision.revision_hash}")
    if resolved.expected_content_hash is not None:
        evidence_refs.add(f"content:{resolved.expected_content_hash}")
    if resolved.feedback_transaction_hash is not None:
        evidence_refs.add(f"feedback-transaction:{resolved.feedback_transaction_hash}")
    return PublicVerificationResult(
        verification_version="1.0",
        reference_kind=reference.kind,
        reference_value=reference.value,
        status=status,
        task_id=receipt.task_spec.task_id,
        service_id=receipt.service_identity.service_id,
        attempt=resolved.attempt,
        receipt_hash=receipt.receipt_hash,
        outcome=receipt.verification_result.outcome,
        resolution=resolution,
        evidence_refs=tuple(sorted(evidence_refs)),
        commitment_status=commitment_status,
        checks=tuple(checks),
        reason=reason,
    )
