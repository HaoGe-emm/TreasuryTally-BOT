from __future__ import annotations

from datetime import UTC, datetime

import pytest

from trust_receipt.m9 import build_rework_package, verify_rework_package_hash


def test_fail_receipt_builds_deterministic_package_from_confirmed_errors_only(two_attempts) -> None:
    created_at = datetime(2026, 10, 7, 8, 0, tzinfo=UTC)
    first = build_rework_package(
        two_attempts.first_receipt,
        package_id="rework-1",
        created_at=created_at,
    )
    second = build_rework_package(
        two_attempts.first_receipt,
        package_id="rework-1",
        created_at=created_at,
    )

    assert first == second
    assert verify_rework_package_hash(first)
    assert first.items
    assert {item.finding_id for item in first.items} == {
        finding.finding_id
        for finding in two_attempts.first_receipt.verification_result.findings
        if finding.is_confirmed_error
    }
    assert all(item.evidence_refs for item in first.items)


def test_pass_receipt_cannot_create_rework_instructions(two_attempts) -> None:
    with pytest.raises(ValueError, match="FAIL"):
        build_rework_package(
            two_attempts.second_receipt,
            package_id="rework-pass",
            created_at=datetime(2026, 10, 7, 8, 0, tzinfo=UTC),
        )
