from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from trust_receipt.chain.models import TransferRecord as ChainTransferRecord
from trust_receipt.models import (
    EvidenceSource,
    ExclusionRule,
    Finding,
    FindingSeverity,
    FindingStatus,
    FindingType,
    FixtureCase,
    FixtureManifest,
    Receipt,
    ServiceSubmission,
    SourceDescriptor,
    TaskSpec,
    TransferRecord,
    VerificationOutcome,
    VerificationPlan,
    VerificationResult,
)

ADDRESS_A = "0x1111111111111111111111111111111111111111"
ADDRESS_B = "0x2222222222222222222222222222222222222222"
ADDRESS_C = "0x3333333333333333333333333333333333333333"
HASH_A = "0x" + "aa" * 32
HASH_B = "0x" + "bb" * 32
NOW = "2026-10-06T00:00:00Z"


def transfer_data(*, source: str = "service", amount: object = "120000") -> dict[str, object]:
    return {
        "chain_id": 11_155_111,
        "token_address": ADDRESS_A,
        "transaction_hash": HASH_A,
        "log_index": 2,
        "block_number": 9_000_000,
        "block_hash": HASH_B,
        "from_address": ADDRESS_B,
        "to_address": ADDRESS_C,
        "amount_base_units": amount,
        "token_decimals": 6,
        "source": source,
    }


def task_data() -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "task_id": "task-1",
        "chain_id": 11_155_111,
        "token_address": ADDRESS_A,
        "treasury_addresses": [ADDRESS_B],
        "recipient_addresses": [ADDRESS_C],
        "start_block": 8_999_000,
        "end_block": 9_001_000,
        "exclusion_rules": [
            {
                "rule_id": "exclude-internal",
                "rule_type": "EXCLUDE_TREASURY_INTERNAL",
                "reason": "Do not count movement between confirmed treasury accounts.",
            }
        ],
        "max_records": 200,
        "confirmed_at": NOW,
        "spec_hash": HASH_A,
    }


def submission_data() -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "submission_id": "submission-1",
        "task_id": "task-1",
        "service_id": "service-a",
        "service_version": "1.0.0",
        "attempt": 1,
        "claimed_total_base_units": "120000",
        "claimed_count": 1,
        "transfers": [transfer_data()],
        "report_text": "One reported transfer.",
        "created_at": NOW,
        "report_hash": HASH_B,
        "signature": None,
    }


def source_descriptor() -> SourceDescriptor:
    return SourceDescriptor.model_validate(
        {
            "source": "rpc",
            "source_id": "sepolia-rpc",
            "retrieved_at": NOW,
            "complete": True,
            "details": {"page_count": 1},
        }
    )


def finding() -> Finding:
    return Finding.model_validate(
        {
            "finding_id": "finding-1",
            "finding_type": "MISSING_TRANSFER",
            "severity": "error",
            "expected": {"event_key": [11_155_111, HASH_A, 2]},
            "actual": None,
            "violated_rule": "Every eligible reference transfer must be reported.",
            "evidence_refs": ["rpc-log-1"],
            "explanation": "The eligible reference event was not present in the submission.",
            "status": "confirmed",
        }
    )


def result_data() -> dict[str, object]:
    return {
        "run_id": "run-1",
        "task_id": "task-1",
        "submission_id": "submission-1",
        "verifier_version": "1.0.0",
        "reference_sources": [source_descriptor().model_dump(mode="json")],
        "reference_complete": True,
        "evidence_sufficient": True,
        "calculated_total_base_units": "110000",
        "calculated_count": 2,
        "findings": [finding().model_dump(mode="json")],
        "outcome": "FAIL",
        "inconclusive_reason": None,
        "started_at": NOW,
        "finished_at": "2026-10-06T00:00:01Z",
    }


def test_transfer_record_preserves_exact_amount_and_full_event_key() -> None:
    transfer = TransferRecord.model_validate(transfer_data())

    assert transfer.amount_base_units == "120000"
    assert transfer.event_key == (11_155_111, HASH_A, 2)
    assert transfer.source is EvidenceSource.SERVICE
    assert ChainTransferRecord is TransferRecord


@pytest.mark.parametrize("amount", [120000, 120000.0, "0120000", "-1", "1.5"])
def test_transfer_record_rejects_noncanonical_amounts(amount: object) -> None:
    with pytest.raises(ValidationError):
        TransferRecord.model_validate(transfer_data(amount=amount))


@pytest.mark.parametrize("missing", ["chain_id", "transaction_hash", "log_index"])
def test_event_identity_fields_are_required(missing: str) -> None:
    data = transfer_data()
    del data[missing]

    with pytest.raises(ValidationError):
        TransferRecord.model_validate(data)


def test_models_reject_extra_fields_and_are_frozen() -> None:
    data = transfer_data()
    data["provider_note"] = "unexpected"
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        TransferRecord.model_validate(data)

    transfer = TransferRecord.model_validate(transfer_data())
    with pytest.raises(ValidationError, match="Instance is frozen"):
        transfer.amount_base_units = "1"  # type: ignore[misc]


def test_task_scope_rejects_invalid_range_and_duplicate_addresses() -> None:
    reversed_range = task_data()
    reversed_range["start_block"] = 10
    reversed_range["end_block"] = 9
    with pytest.raises(ValidationError, match="start_block"):
        TaskSpec.model_validate(reversed_range)

    duplicate_treasury = task_data()
    duplicate_treasury["treasury_addresses"] = [ADDRESS_B, ADDRESS_B.upper().replace("0X", "0x")]
    with pytest.raises(ValidationError, match="unique ignoring case"):
        TaskSpec.model_validate(duplicate_treasury)


def test_task_datetime_must_be_utc() -> None:
    data = task_data()
    data["confirmed_at"] = "2026-10-06T08:00:00+08:00"
    with pytest.raises(ValidationError, match="timezone-aware UTC"):
        TaskSpec.model_validate(data)

    task = TaskSpec.model_validate(task_data())
    assert task.confirmed_at == datetime(2026, 10, 6, tzinfo=UTC)
    assert isinstance(task.exclusion_rules[0], ExclusionRule)


def test_submission_requires_service_sources_and_attempt_limit() -> None:
    rpc_submission = submission_data()
    rpc_submission["transfers"] = [transfer_data(source="rpc")]
    with pytest.raises(ValidationError, match="source=service"):
        ServiceSubmission.model_validate(rpc_submission)

    third_attempt = submission_data()
    third_attempt["attempt"] = 3
    with pytest.raises(ValidationError):
        ServiceSubmission.model_validate(third_attempt)


def test_verification_result_derives_fail_from_confirmed_error() -> None:
    result = VerificationResult.model_validate(result_data())
    assert result.outcome is VerificationOutcome.FAIL
    assert result.findings[0].finding_type is FindingType.MISSING_TRANSFER
    assert result.findings[0].severity is FindingSeverity.ERROR
    assert result.findings[0].status is FindingStatus.CONFIRMED

    wrong_outcome = result_data()
    wrong_outcome["outcome"] = "PASS"
    with pytest.raises(ValidationError, match="findings require outcome=FAIL"):
        VerificationResult.model_validate(wrong_outcome)


def test_insufficient_evidence_can_only_be_inconclusive() -> None:
    data = deepcopy(result_data())
    data.update(
        {
            "reference_complete": False,
            "evidence_sufficient": False,
            "calculated_total_base_units": None,
            "calculated_count": None,
            "findings": [],
            "outcome": "INCONCLUSIVE",
            "inconclusive_reason": "RPC pagination state is unknown.",
        }
    )
    result = VerificationResult.model_validate(data)
    assert result.outcome is VerificationOutcome.INCONCLUSIVE

    data["outcome"] = "FAIL"
    with pytest.raises(ValidationError, match="requires outcome=INCONCLUSIVE"):
        VerificationResult.model_validate(data)


def test_public_schema_titles_and_required_event_identity_are_stable() -> None:
    schema = TransferRecord.model_json_schema()
    assert schema["title"] == "TransferRecord"
    assert {"chain_id", "transaction_hash", "log_index"}.issubset(schema["required"])


def test_every_frozen_top_level_schema_can_be_generated() -> None:
    models = (
        TaskSpec,
        TransferRecord,
        ServiceSubmission,
        VerificationPlan,
        VerificationResult,
        Receipt,
        FixtureCase,
        FixtureManifest,
    )
    assert [model.model_json_schema()["title"] for model in models] == [model.__name__ for model in models]


def test_fixture_expected_outcome_matches_evidence_and_findings() -> None:
    data = {
        "fixture_version": "1.0",
        "fixture_id": "correct-report-01",
        "title": "Correct single transfer",
        "tags": ["correct"],
        "task_spec": task_data(),
        "submission": submission_data(),
        "reference": {
            "sources": [source_descriptor().model_dump(mode="json")],
            "reference_complete": True,
            "evidence_sufficient": True,
            "transfers": [transfer_data(source="rpc")],
            "insufficiency_reason": None,
        },
        "expected": {
            "outcome": "PASS",
            "calculated_total_base_units": "120000",
            "calculated_count": 1,
            "findings": [],
        },
        "human_review": {
            "summary": "The report and reference contain the same event.",
            "calculation": "120000 = 120000",
            "reviewer": "M1 contract owner",
            "verified_at": NOW,
        },
    }
    fixture = FixtureCase.model_validate(data)
    assert fixture.expected.outcome is VerificationOutcome.PASS

    data["expected"] = {
        "outcome": "FAIL",
        "calculated_total_base_units": "120000",
        "calculated_count": 1,
        "findings": [],
    }
    with pytest.raises(ValidationError, match="expected findings require outcome=PASS"):
        FixtureCase.model_validate(data)


def test_reference_sources_cannot_be_service_claims() -> None:
    data = result_data()
    service_source = source_descriptor().model_copy(update={"source": EvidenceSource.SERVICE})
    data["reference_sources"] = [service_source.model_dump(mode="json")]

    with pytest.raises(ValidationError, match="cannot use source=service"):
        VerificationResult.model_validate(data)
