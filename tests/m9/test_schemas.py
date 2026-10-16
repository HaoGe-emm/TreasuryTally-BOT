from __future__ import annotations

from datetime import UTC, datetime

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

from scripts.export_schemas import generate_schemas
from trust_receipt.hashing import canonical_json_bytes, content_hash
from trust_receipt.m9 import (
    PublicReceiptReference,
    PublicReferenceKind,
    ResolvedPublicReceipt,
    build_public_bundle,
    build_receipt_revision,
    build_repair_comparison,
    build_rework_package,
    verify_public_reference,
)
from trust_receipt.publishing import authorize_public_receipt


class StaticResolver:
    def __init__(self, resolved) -> None:
        self.resolved = resolved

    def resolve(self, reference):
        del reference
        return self.resolved


def test_m9_models_satisfy_their_generated_public_schemas(two_attempts) -> None:
    package = build_rework_package(
        two_attempts.first_receipt,
        package_id="schema-rework",
        created_at=datetime(2026, 10, 7, 8, 0, tzinfo=UTC),
    )
    first_revision = build_receipt_revision(two_attempts.first_receipt, attempt=1)
    second_revision = build_receipt_revision(two_attempts.second_receipt, attempt=2, parent=first_revision)
    comparison = build_repair_comparison(
        before_receipt=two_attempts.first_receipt,
        before_submission=two_attempts.first_submission,
        before_revision=first_revision,
        after_receipt=two_attempts.second_receipt,
        after_submission=two_attempts.second_submission,
        after_revision=second_revision,
    )
    public = authorize_public_receipt(two_attempts.first_receipt)
    payload = canonical_json_bytes(public) + b"\n"
    verification = verify_public_reference(
        PublicReceiptReference(PublicReferenceKind.RECEIPT_HASH, public.receipt_hash),
        StaticResolver(
            ResolvedPublicReceipt(
                payload=payload,
                attempt=1,
                expected_content_hash=content_hash(payload),
            )
        ),
    )
    schemas = generate_schemas()
    registry = Registry().with_resources(
        (schema["$id"], Resource.from_contents(schema)) for schema in schemas.values()
    )
    values = {
        "rework_package.schema.json": package,
        "receipt_revision.schema.json": second_revision,
        "repair_comparison.schema.json": comparison,
        "public_verification_result.schema.json": verification,
        "public_verification_bundle.schema.json": build_public_bundle(
            (two_attempts.first_receipt, two_attempts.second_receipt), authorized=True,
        ),
    }

    for filename, model in values.items():
        Draft202012Validator(
            schemas[filename],
            format_checker=FormatChecker(),
            registry=registry,
        ).validate(model.model_dump(mode="json"))
