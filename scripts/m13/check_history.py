"""Verify existing M9 public history bytes in a fresh process, without publishing."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    parser.add_argument("--expected-content-hash", required=True)
    parser.add_argument("--kind", choices=("URI", "RECEIPT_HASH", "TASK_HASH"), default="URI")
    parser.add_argument("--value")
    parser.add_argument("--expected-outcome", choices=("PASS", "FAIL", "INCONCLUSIVE"), default="PASS")
    args = parser.parse_args()
    try:
        from trust_receipt.m9 import (
            PublicBundleResolver,
            PublicReceiptReference,
            PublicReferenceKind,
            verify_public_reference,
        )
    except ImportError:
        print(json.dumps({"status": "INCONCLUSIVE", "reason": "M9 committed dependency is unavailable"}))
        return 2
    if args.kind != "URI" and not args.value:
        parser.error("--value is required for a hash reference")
    location = str(args.bundle.resolve())
    try:
        with args.bundle.open("rb") as stream:
            payload = stream.read(4_000_001)
        if len(payload) > 4_000_000:
            raise ValueError("bundle exceeds 4 MB")
        result = verify_public_reference(
            PublicReceiptReference(PublicReferenceKind(args.kind), args.value or location),
            PublicBundleResolver(payload, location=location, expected_content_hash=args.expected_content_hash),
        )
    except (OSError, ValueError) as error:
        print(json.dumps({"status": "INCONCLUSIVE", "reason": type(error).__name__}))
        return 2
    print(json.dumps(result.model_dump(mode="json"), ensure_ascii=False, sort_keys=True))
    if result.status.value == "INCONCLUSIVE":
        return 2
    if result.status.value != "VERIFIED" or result.outcome.value != args.expected_outcome:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
