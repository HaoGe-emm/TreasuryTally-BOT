"""Standalone read-only verification for a public Receipt 1.0 artifact."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.parse import urlparse

import httpx

from trust_receipt.integrations.config import M0Settings
from trust_receipt.m9 import (
    PublicBundleResolver,
    PublicReceiptReference,
    PublicReferenceKind,
    PublicVerificationStatus,
    ReceiptRevision,
    ResolvedPublicReceipt,
    verify_public_reference,
)
from trust_receipt.m9.feedback import ERC8004PublicResolver
from trust_receipt.m9.public_reader import PublicArtifactReader
from trust_receipt.models.receipts import Receipt
from trust_receipt.publishing import M6Settings


class _SingleArtifactResolver:
    def __init__(self, resolved: ResolvedPublicReceipt) -> None:
        self._resolved = resolved

    def resolve(self, reference: PublicReceiptReference) -> ResolvedPublicReceipt:
        del reference
        return self._resolved


def _read_public_bytes(location: str, timeout_seconds: float) -> bytes:
    local_path = Path(location)
    if local_path.is_file():
        with local_path.open("rb") as handle:
            payload = handle.read(4_000_001)
        if len(payload) > 4_000_000:
            raise ValueError("public artifact exceeds the size limit")
        return payload
    parsed = urlparse(location)
    if parsed.scheme in {"http", "https"}:
        if parsed.username is not None or parsed.password is not None:
            raise ValueError("public URI cannot contain credentials")
        with httpx.stream("GET", location, timeout=timeout_seconds, follow_redirects=False) as response:
            response.raise_for_status()
            payload = bytearray()
            for chunk in response.iter_bytes():
                payload.extend(chunk)
                if len(payload) > 4_000_000:
                    raise ValueError("public artifact exceeds the size limit")
            return bytes(payload)
    if parsed.scheme:
        raise ValueError("receipt location must be a local path or an HTTP(S) URI")
    return local_path.read_bytes()


def _load_revision(path: Path | None) -> ReceiptRevision | None:
    return ReceiptRevision.model_validate_json(path.read_bytes()) if path is not None else None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("receipt", nargs="?", help="local public JSON path or HTTP(S) URI")
    parser.add_argument("--kind", choices=[kind.value for kind in PublicReferenceKind], required=True)
    parser.add_argument("--value", help="reference value; defaults to receipt location for URI")
    parser.add_argument("--attempt", type=int, choices=(1, 2))
    parser.add_argument("--bundle", action="store_true", help="verify a complete public history bundle")
    parser.add_argument("--public-history", type=Path, help="complete public bundle for feedback attempt 2")
    parser.add_argument("--expected-content-hash")
    parser.add_argument("--feedback-transaction-hash")
    parser.add_argument("--revision", type=Path)
    parser.add_argument("--parent-revision", type=Path)
    parser.add_argument("--parent-receipt", type=Path)
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    args = parser.parse_args()

    kind = PublicReferenceKind(args.kind)
    value = args.value or (args.receipt if kind is PublicReferenceKind.URI else None)
    if value is None:
        parser.error("--value is required unless --kind URI is used")
    if not args.bundle and args.attempt is None:
        parser.error("--attempt is required for a single Receipt")
    if kind is not PublicReferenceKind.FEEDBACK_TRANSACTION and args.receipt is None:
        parser.error("receipt location is required")
    try:
        if kind is PublicReferenceKind.FEEDBACK_TRANSACTION:
            chain = M0Settings.load()
            storage = M6Settings.load()
            if chain.rpc_url is None or chain.reputation_registry_address is None:
                print(json.dumps({
                    "status": "INCONCLUSIVE", "reason": "RPC or Reputation Registry configuration missing",
                }))
                return 2
            reader = PublicArtifactReader(
                https_base_urls=tuple(filter(None, (
                    storage.public_receipt_base_url, "https://creatoros.top/trust-receipt/public",
                ))),
                ipfs_gateway=storage.pinata_gateway_url,
            )
            resolver = ERC8004PublicResolver(
                rpc_url=chain.rpc_url_value(), chain_id=chain.chain_id,
                reputation_registry=chain.reputation_registry_address,
                reader=reader, attempt=args.attempt or 1,
                bundle_payload=args.public_history.read_bytes() if args.public_history else None,
            )
            result = verify_public_reference(PublicReceiptReference(kind, value), resolver)
            print(json.dumps(result.model_dump(mode="json"), ensure_ascii=False, sort_keys=True))
            return 0 if result.status is PublicVerificationStatus.VERIFIED else (
                2 if result.status is PublicVerificationStatus.INCONCLUSIVE else 1
            )
        payload = _read_public_bytes(args.receipt, args.timeout_seconds)
        if args.bundle:
            result = verify_public_reference(
                PublicReceiptReference(kind=kind, value=value),
                PublicBundleResolver(
                    payload, location=args.receipt,
                    expected_content_hash=args.expected_content_hash, attempt=args.attempt,
                ),
            )
            print(json.dumps(result.model_dump(mode="json"), ensure_ascii=False, sort_keys=True))
            return 0 if result.status is PublicVerificationStatus.VERIFIED else (
                2 if result.status is PublicVerificationStatus.INCONCLUSIVE else 1
            )
        resolved = ResolvedPublicReceipt(
            payload=payload,
            attempt=args.attempt,
            expected_content_hash=args.expected_content_hash,
            feedback_transaction_hash=args.feedback_transaction_hash,
            revision=_load_revision(args.revision),
            parent_revision=_load_revision(args.parent_revision),
            parent_receipt=(
                Receipt.model_validate_json(args.parent_receipt.read_bytes())
                if args.parent_receipt is not None else None
            ),
            evidence_refs=(args.receipt,),
        )
        result = verify_public_reference(
            PublicReceiptReference(kind=kind, value=value),
            _SingleArtifactResolver(resolved),
        )
    except (httpx.HTTPError, OSError, ValueError) as exc:
        print(json.dumps({"status": "INCONCLUSIVE", "reason": type(exc).__name__}, sort_keys=True))
        return 2
    print(json.dumps(result.model_dump(mode="json"), ensure_ascii=False, sort_keys=True))
    if result.status is PublicVerificationStatus.VERIFIED:
        return 0
    return 2 if result.status is PublicVerificationStatus.INCONCLUSIVE else 1


if __name__ == "__main__":
    raise SystemExit(main())
