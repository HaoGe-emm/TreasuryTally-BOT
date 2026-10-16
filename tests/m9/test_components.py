from __future__ import annotations

from datetime import UTC, datetime

from app.m9_components import (
    render_public_verification,
    render_repair_comparison,
    render_rework_package,
)
from trust_receipt.hashing import canonical_json_bytes, content_hash
from trust_receipt.m9 import (
    PublicReceiptReference,
    PublicReferenceKind,
    ResolvedPublicReceipt,
    build_receipt_revision,
    build_repair_comparison,
    build_rework_package,
    verify_public_reference,
)
from trust_receipt.publishing import authorize_public_receipt


class FakeUi:
    def __init__(self) -> None:
        self.calls: list[tuple[str, object]] = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def __getattr__(self, name):
        def call(value=None, *args, **kwargs):
            self.calls.append((name, value))
            if name == "columns":
                return (self, self)
            if name in {"container", "expander"}:
                return self
            return None

        return call


class StaticResolver:
    def __init__(self, resolved) -> None:
        self.resolved = resolved

    def resolve(self, reference):
        del reference
        return self.resolved


def test_m9_components_render_only_supplied_models(two_attempts) -> None:
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
    package = build_rework_package(
        two_attempts.first_receipt,
        package_id="component-rework",
        created_at=datetime(2026, 10, 7, 8, 0, tzinfo=UTC),
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
    ui = FakeUi()

    render_rework_package(ui, package)
    render_repair_comparison(ui, comparison)
    render_public_verification(ui, verification)

    names = [name for name, _ in ui.calls]
    assert names.count("subheader") == 3
    assert "success" in names
    assert "json" in names
