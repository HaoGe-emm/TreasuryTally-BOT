"""Portable public receipt histories, independent of private workspace storage."""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Literal

from pydantic import Field, ValidationError

from trust_receipt.hashing import canonical_json_bytes, content_hash, hash_model
from trust_receipt.m9.models import PublicReferenceKind, ReceiptRevision
from trust_receipt.m9.ports import PublicReceiptReference, ResolvedPublicReceipt
from trust_receipt.m9.revisions import build_receipt_revision
from trust_receipt.models.base import DomainModel, Hex32
from trust_receipt.models.receipts import Receipt
from trust_receipt.publishing import authorize_public_receipt
from trust_receipt.receipts import replay_receipt


class InvalidPublicEvidence(ValueError):
    """Public bytes contradict their declared content or object relationships."""


def read_public_json(payload: bytes):
    if len(payload) > 4_000_000:
        raise InvalidPublicEvidence("Public artifact exceeds the size limit.")

    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise InvalidPublicEvidence("Public artifact contains duplicate JSON keys.")
            result[key] = value
        return result

    def reject_number(value):
        raise InvalidPublicEvidence("Public artifacts cannot contain float or nonfinite values.")

    try:
        return json.loads(
            payload.decode("utf-8"), object_pairs_hook=unique_object,
            parse_float=reject_number, parse_constant=reject_number,
        )
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise InvalidPublicEvidence("Public artifact is not unambiguous UTF-8 JSON.") from exc


class PublicVerificationBundle(DomainModel):
    bundle_version: Literal["1.0"]
    receipts: tuple[Receipt, ...] = Field(min_length=1, max_length=2)
    revisions: tuple[ReceiptRevision, ...] = Field(min_length=1, max_length=2)
    bundle_hash: Hex32


def validate_public_bundle(bundle: PublicVerificationBundle) -> None:
    try:
        digest = hash_model(bundle, exclude=frozenset({"bundle_hash"}))
    except (ValueError, TypeError) as exc:
        raise InvalidPublicEvidence("Public history contains noncanonical values.") from exc
    if bundle.bundle_hash != digest:
        raise InvalidPublicEvidence("Public verification bundle hash mismatch.")
    if len(bundle.receipts) != len(bundle.revisions):
        raise InvalidPublicEvidence("Each public receipt requires its revision record.")
    spec_hash = bundle.receipts[0].task_spec.spec_hash
    for index, (receipt, revision) in enumerate(zip(bundle.receipts, bundle.revisions, strict=True)):
        try:
            valid = replay_receipt(receipt).valid
        except (ValueError, TypeError) as exc:
            raise InvalidPublicEvidence("Public receipt contains noncanonical values.") from exc
        if not receipt.publication.authorized or not valid:
            raise InvalidPublicEvidence("Public receipt authorization or replay failed.")
        if receipt.task_spec.spec_hash != spec_hash:
            raise InvalidPublicEvidence("Public history changes the immutable task spec.")
        parent = bundle.revisions[index - 1] if index else None
        try:
            expected = build_receipt_revision(receipt, attempt=index + 1, parent=parent)
        except ValueError as exc:
            raise InvalidPublicEvidence(str(exc)) from exc
        if revision != expected:
            raise InvalidPublicEvidence("Public revision does not bind its receipt and parent.")


def build_public_bundle(receipts: Sequence[Receipt], *, authorized: bool) -> PublicVerificationBundle:
    if not authorized:
        raise ValueError("explicit authorization to share the complete receipt history is required")
    public_receipts = tuple(authorize_public_receipt(receipt) for receipt in receipts)
    revisions: list[ReceiptRevision] = []
    for index, receipt in enumerate(public_receipts):
        revisions.append(build_receipt_revision(
            receipt, attempt=index + 1, parent=revisions[-1] if revisions else None,
        ))
    draft = PublicVerificationBundle(
        bundle_version="1.0", receipts=public_receipts,
        revisions=tuple(revisions), bundle_hash="0x" + "0" * 64,
    )
    bundle = draft.model_copy(update={
        "bundle_hash": hash_model(draft, exclude=frozenset({"bundle_hash"})),
    })
    validate_public_bundle(bundle)
    return bundle


class PublicBundleResolver:
    """Use only supplied public bytes; never look up private tasks or reports."""

    def __init__(
        self, payload: bytes, *, location: str,
        expected_content_hash: str | None = None, attempt: int | None = None,
    ) -> None:
        self._payload = payload
        self._location = location
        self._expected_content_hash = expected_content_hash
        self._attempt = attempt

    def resolve(self, reference: PublicReceiptReference) -> ResolvedPublicReceipt:
        if self._expected_content_hash is not None and (
            content_hash(self._payload).lower() != self._expected_content_hash.lower()
        ):
            raise InvalidPublicEvidence("Downloaded bundle bytes do not match the expected content hash.")
        try:
            bundle = PublicVerificationBundle.model_validate(read_public_json(self._payload))
        except ValidationError as exc:
            raise InvalidPublicEvidence("Invalid public verification bundle schema.") from exc
        validate_public_bundle(bundle)
        if reference.kind is PublicReferenceKind.FEEDBACK_TRANSACTION:
            raise LookupError("A bundle alone does not prove an ERC-8004 feedback transaction.")
        candidates = list(range(len(bundle.receipts)))
        if self._attempt is not None:
            candidates = [i for i in candidates if i + 1 == self._attempt]
        if reference.kind is PublicReferenceKind.URI:
            if reference.value != self._location:
                raise InvalidPublicEvidence("Requested URI does not match the downloaded bundle location.")
        elif reference.kind is PublicReferenceKind.RECEIPT_HASH:
            candidates = [i for i in candidates if bundle.receipts[i].receipt_hash.lower() == reference.value.lower()]
        elif reference.kind is PublicReferenceKind.TASK_HASH:
            candidates = [
                i for i in candidates
                if bundle.receipts[i].task_spec.spec_hash.lower() == reference.value.lower()
            ]
        if not candidates:
            raise LookupError("Requested public receipt or task is not in this bundle.")
        index = candidates[-1]
        receipt = bundle.receipts[index]
        return ResolvedPublicReceipt(
            payload=canonical_json_bytes(receipt) + b"\n", attempt=index + 1,
            revision=bundle.revisions[index],
            parent_revision=bundle.revisions[index - 1] if index else None,
            parent_receipt=bundle.receipts[index - 1] if index else None,
            evidence_refs=(
                self._location, f"bundle:{bundle.bundle_hash}",
                f"bundle-content:{content_hash(self._payload)}",
            ),
        )
