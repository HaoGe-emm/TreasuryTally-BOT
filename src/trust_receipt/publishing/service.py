"""Deterministic redaction, publication, and post-upload verification."""

from __future__ import annotations

from trust_receipt.hashing import canonical_json_bytes, content_hash, receipt_hash, verify_receipt_hash
from trust_receipt.models.enums import PublicationChainStatus
from trust_receipt.models.receipts import Publication, Receipt
from trust_receipt.publishing.models import PublishedArtifact
from trust_receipt.publishing.ports import ContentPublisher


class PublicationIntegrityError(ValueError):
    pass


_FORBIDDEN_PUBLIC_KEYS = frozenset(
    {
        "api_key",
        "authorization",
        "jwt",
        "mnemonic",
        "private_key",
        "report_text",
        "secret",
        "signature",
    }
)


def _reject_private_keys(value: object, *, path: str = "$") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = key.lower().replace("-", "_")
            if normalized in _FORBIDDEN_PUBLIC_KEYS:
                raise PublicationIntegrityError(f"private field is forbidden in public receipt: {path}.{key}")
            _reject_private_keys(child, path=f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _reject_private_keys(child, path=f"{path}[{index}]")


def authorize_public_receipt(receipt: Receipt) -> Receipt:
    """Create the immutable JSON that may be uploaded after explicit approval."""
    if not verify_receipt_hash(receipt):
        raise PublicationIntegrityError("source receipt hash is invalid")
    publication = Publication(
        authorized=True,
        uri=None,
        content_hash=None,
        transaction_hash=None,
        chain_status=PublicationChainStatus.NOT_SUBMITTED,
    )
    draft = receipt.model_copy(
        update={"publication": publication, "receipt_hash": "0x" + "0" * 64}
    )
    public_receipt = draft.model_copy(update={"receipt_hash": receipt_hash(draft)})
    _reject_private_keys(public_receipt.model_dump(mode="json"))
    return public_receipt


def verify_public_receipt(payload: bytes, expected_hash: str) -> Receipt:
    if content_hash(payload) != expected_hash:
        raise PublicationIntegrityError("published content hash does not match uploaded bytes")
    receipt = Receipt.model_validate_json(payload)
    if not receipt.publication.authorized or not verify_receipt_hash(receipt):
        raise PublicationIntegrityError("published receipt is unauthorized or internally inconsistent")
    return receipt


def publish_receipt(
    receipt: Receipt,
    publisher: ContentPublisher,
) -> tuple[Receipt, PublishedArtifact]:
    """Upload once, fetch once, and bind the verified URI/hash to local state."""
    public_receipt = authorize_public_receipt(receipt)
    payload = canonical_json_bytes(public_receipt) + b"\n"
    expected_hash = content_hash(payload)
    uri = publisher.publish(payload, name=f"{receipt.receipt_id}.json")
    downloaded = publisher.fetch(uri)
    verify_public_receipt(downloaded, expected_hash)
    artifact = PublishedArtifact(uri=uri, content_hash=expected_hash, byte_length=len(payload))
    publication = public_receipt.publication.model_copy(
        update={"uri": uri, "content_hash": expected_hash}
    )
    final_draft = public_receipt.model_copy(
        update={"publication": publication, "receipt_hash": "0x" + "0" * 64}
    )
    final_receipt = final_draft.model_copy(update={"receipt_hash": receipt_hash(final_draft)})
    return final_receipt, artifact
