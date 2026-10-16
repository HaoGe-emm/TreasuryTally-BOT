"""Deterministic conversion of confirmed receipt findings into rework instructions."""

from __future__ import annotations

from datetime import datetime

from trust_receipt.hashing import hash_model, verify_receipt_hash
from trust_receipt.m9.models import ReworkAction, ReworkItem, ReworkPackage
from trust_receipt.models.enums import FindingType, VerificationOutcome
from trust_receipt.models.receipts import Receipt

_ACTION_BY_FINDING: dict[FindingType, ReworkAction] = {
    FindingType.MISSING_TRANSFER: ReworkAction.ADD_MISSING_TRANSFER,
    FindingType.EXTRA_TRANSFER: ReworkAction.REMOVE_EXTRA_TRANSFER,
    FindingType.DUPLICATE_TRANSFER: ReworkAction.REMOVE_DUPLICATE_TRANSFER,
    FindingType.EXCLUDED_INTERNAL_TRANSFER: ReworkAction.REMOVE_EXCLUDED_INTERNAL_TRANSFER,
    FindingType.OUT_OF_RANGE: ReworkAction.CORRECT_SCOPE,
    FindingType.WRONG_TOKEN: ReworkAction.CORRECT_TOKEN,
    FindingType.WRONG_DIRECTION: ReworkAction.CORRECT_DIRECTION,
    FindingType.AMOUNT_MISMATCH: ReworkAction.CORRECT_AMOUNT,
    FindingType.DECIMAL_ERROR: ReworkAction.CORRECT_DECIMALS,
}


def rework_package_hash(package: ReworkPackage) -> str:
    return hash_model(package, exclude=frozenset({"package_hash"}))


def verify_rework_package_hash(package: ReworkPackage) -> bool:
    return package.package_hash == rework_package_hash(package)


def build_rework_package(
    receipt: Receipt,
    *,
    package_id: str,
    created_at: datetime,
) -> ReworkPackage:
    """Build instructions from confirmed errors only; AI text never enters the package."""
    if not verify_receipt_hash(receipt):
        raise ValueError("source receipt hash is invalid")
    result = receipt.verification_result
    if result.outcome is not VerificationOutcome.FAIL:
        raise ValueError("rework package requires a FAIL receipt")
    items = tuple(
        ReworkItem(
            finding_id=finding.finding_id,
            finding_type=finding.finding_type,
            violated_rule=finding.violated_rule,
            expected=finding.expected,
            actual=finding.actual,
            evidence_refs=finding.evidence_refs,
            required_action=_ACTION_BY_FINDING[finding.finding_type],
        )
        for finding in result.findings
        if finding.is_confirmed_error and finding.finding_type in _ACTION_BY_FINDING
    )
    if not items:
        raise ValueError("FAIL receipt has no actionable confirmed error findings")
    draft = ReworkPackage(
        package_version="1.0",
        package_id=package_id,
        task_id=receipt.task_spec.task_id,
        source_submission_id=result.submission_id,
        source_receipt_hash=receipt.receipt_hash,
        created_at=created_at,
        items=items,
        package_hash="0x" + "0" * 64,
    )
    return draft.model_copy(update={"package_hash": rework_package_hash(draft)})
