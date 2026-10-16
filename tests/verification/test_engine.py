from __future__ import annotations

from datetime import UTC, datetime

import pytest

from trust_receipt.models import (
    EvidenceSource,
    FindingSeverity,
    FindingStatus,
    FindingType,
    ServiceSubmission,
    SourceDescriptor,
    TaskSpec,
    TransferRecord,
    VerificationOutcome,
)
from trust_receipt.verification import ReferenceEvidence, ReferencePage, ReferenceStream, verify_submission

TOKEN = "0x" + "a" * 40
OTHER_TOKEN = "0x" + "d" * 40
TREASURY_A = "0x" + "1" * 40
TREASURY_B = "0x" + "2" * 40
RECIPIENT = "0x" + "3" * 40
OUTSIDER = "0x" + "4" * 40
BLOCK_HASH = "0x" + "b" * 64
STARTED = datetime(2026, 10, 6, tzinfo=UTC)
FINISHED = datetime(2026, 10, 6, 0, 0, 1, tzinfo=UTC)


def task() -> TaskSpec:
    return TaskSpec.model_validate(
        {
            "schema_version": "1.0",
            "task_id": "task-m2",
            "chain_id": 11_155_111,
            "token_address": TOKEN,
            "treasury_addresses": [TREASURY_A, TREASURY_B],
            "recipient_addresses": [RECIPIENT],
            "start_block": 100,
            "end_block": 110,
            "exclusion_rules": [
                {
                    "rule_id": "internal",
                    "rule_type": "EXCLUDE_TREASURY_INTERNAL",
                    "reason": "Exclude movements between treasuries.",
                }
            ],
            "max_records": 200,
            "confirmed_at": STARTED,
            "spec_hash": "0x" + "e" * 64,
        }
    )


def transfer(
    number: int,
    amount: str,
    *,
    source: EvidenceSource = EvidenceSource.RPC,
    log_index: int = 0,
    block: int = 105,
    from_address: str = TREASURY_A,
    to_address: str = RECIPIENT,
    token_address: str = TOKEN,
    decimals: int = 6,
) -> TransferRecord:
    return TransferRecord.model_validate(
        {
            "chain_id": 11_155_111,
            "token_address": token_address,
            "transaction_hash": "0x" + f"{number:064x}",
            "log_index": log_index,
            "block_number": block,
            "block_hash": BLOCK_HASH,
            "from_address": from_address,
            "to_address": to_address,
            "amount_base_units": amount,
            "token_decimals": decimals,
            "source": source,
        }
    )


def reported(record: TransferRecord, **changes: object) -> TransferRecord:
    data = record.model_dump(mode="json")
    data.update({"source": "service", **changes})
    return TransferRecord.model_validate(data)


def submission(records: tuple[TransferRecord, ...], claimed_total: str, claimed_count: int) -> ServiceSubmission:
    return ServiceSubmission.model_validate(
        {
            "schema_version": "1.0",
            "submission_id": "submission-m2",
            "task_id": "task-m2",
            "service_id": "demo-a",
            "service_version": "1.0.0",
            "attempt": 1,
            "claimed_total_base_units": claimed_total,
            "claimed_count": claimed_count,
            "transfers": records,
            "report_text": "Synthetic test report.",
            "created_at": STARTED,
            "report_hash": "0x" + "f" * 64,
            "signature": None,
        }
    )


def evidence(
    records: tuple[TransferRecord, ...],
    *,
    source: EvidenceSource = EvidenceSource.RPC,
    source_complete: bool = True,
    next_cursor: str | None = None,
    sufficient: bool = True,
    reason: str | None = None,
) -> ReferenceEvidence:
    descriptor = SourceDescriptor.model_validate(
        {
            "source": source,
            "source_id": f"{source.value}-test",
            "retrieved_at": STARTED,
            "complete": source_complete,
            "details": {"test_data": True},
        }
    )
    return ReferenceEvidence(
        streams=(
            ReferenceStream(
                source=descriptor,
                pages=(ReferencePage(cursor=None, next_cursor=next_cursor, transfers=records),),
            ),
        ),
        evidence_sufficient=sufficient,
        insufficiency_reason=reason,
    )


def verify(report: ServiceSubmission, reference: ReferenceEvidence):
    return verify_submission(
        task(),
        report,
        reference,
        run_id="run-m2",
        started_at=STARTED,
        finished_at=FINISHED,
    )


def test_matching_report_passes_with_exact_base_units() -> None:
    amount = "900719925474099312345678901"
    reference = transfer(1, amount)
    result = verify(submission((reported(reference),), amount, 1), evidence((reference,)))

    assert result.outcome is VerificationOutcome.PASS
    assert result.calculated_total_base_units == amount
    assert result.calculated_count == 1
    assert result.findings == ()


def test_first_vertical_slice_reports_internal_transfer_and_missing_grant() -> None:
    included = transfer(1, "90000")
    internal = transfer(2, "30000", to_address=TREASURY_B)
    missing = transfer(3, "20000")
    report = submission((reported(included), reported(internal)), "120000", 2)

    result = verify(report, evidence((included, internal, missing)))

    assert result.outcome is VerificationOutcome.FAIL
    assert result.calculated_total_base_units == "110000"
    assert result.calculated_count == 2
    assert {finding.finding_type for finding in result.findings} == {
        FindingType.EXCLUDED_INTERNAL_TRANSFER,
        FindingType.MISSING_TRANSFER,
    }
    assert len(result.findings) == 2
    assert all(finding.status is FindingStatus.CONFIRMED for finding in result.findings)


def test_same_transaction_with_distinct_log_indexes_is_not_deduplicated() -> None:
    first = transfer(1, "20", log_index=0)
    second = transfer(1, "30", log_index=1)
    result = verify(submission((reported(first), reported(second)), "50", 2), evidence((first, second)))

    assert result.outcome is VerificationOutcome.PASS
    assert result.calculated_total_base_units == "50"
    assert result.calculated_count == 2


def test_address_and_hash_comparison_ignores_hex_letter_case() -> None:
    reference = transfer(10, "25")
    actual = reported(
        reference,
        transaction_hash=reference.transaction_hash.upper().replace("0X", "0x"),
        token_address=TOKEN.upper().replace("0X", "0x"),
    )
    result = verify(submission((actual,), "25", 1), evidence((reference,)))

    assert result.outcome is VerificationOutcome.PASS


def test_all_contiguous_reference_pages_are_included() -> None:
    first = transfer(1, "10")
    second = transfer(2, "20")
    descriptor = evidence((first,)).streams[0].source
    reference = ReferenceEvidence(
        streams=(
            ReferenceStream(
                source=descriptor,
                pages=(
                    ReferencePage(cursor=None, next_cursor="page-2", transfers=(first,)),
                    ReferencePage(cursor="page-2", next_cursor=None, transfers=(second,)),
                ),
            ),
        ),
        evidence_sufficient=True,
        insufficiency_reason=None,
    )
    result = verify(submission((reported(first), reported(second)), "30", 2), reference)

    assert result.outcome is VerificationOutcome.PASS
    assert result.calculated_total_base_units == "30"
    assert result.calculated_count == 2


def test_repeated_service_event_is_a_confirmed_duplicate() -> None:
    reference = transfer(1, "20")
    duplicate = reported(reference)
    result = verify(submission((duplicate, duplicate), "40", 2), evidence((reference,)))

    assert result.outcome is VerificationOutcome.FAIL
    assert result.calculated_total_base_units == "20"
    assert [finding.finding_type for finding in result.findings] == [FindingType.DUPLICATE_TRANSFER]
    assert "submission:submission-m2:0" in result.findings[0].evidence_refs
    assert "submission:submission-m2:1" in result.findings[0].evidence_refs


@pytest.mark.parametrize("block", [100, 110])
def test_block_range_includes_both_endpoints(block: int) -> None:
    reference = transfer(1, "7", block=block)
    result = verify(submission((reported(reference),), "7", 1), evidence((reference,)))
    assert result.outcome is VerificationOutcome.PASS


@pytest.mark.parametrize(
    ("changes", "finding_type"),
    [
        ({"block_number": 111}, FindingType.OUT_OF_RANGE),
        ({"token_address": OTHER_TOKEN}, FindingType.WRONG_TOKEN),
        ({"from_address": OUTSIDER}, FindingType.WRONG_DIRECTION),
    ],
)
def test_service_scope_violations_are_reproducible(changes: dict[str, object], finding_type: FindingType) -> None:
    reference = transfer(1, "20")
    result = verify(submission((reported(reference, **changes),), "20", 1), evidence((reference,)))

    assert result.outcome is VerificationOutcome.FAIL
    assert {finding.finding_type for finding in result.findings} == {finding_type, FindingType.MISSING_TRANSFER}
    assert all(finding.evidence_refs for finding in result.findings)


def test_wrong_amount_and_decimals_are_reported_without_float_arithmetic() -> None:
    reference = transfer(1, "1000000", decimals=6)
    actual = reported(reference, amount_base_units="1", token_decimals=0)
    result = verify(submission((actual,), "1", 1), evidence((reference,)))

    assert result.calculated_total_base_units == "1000000"
    assert {finding.finding_type for finding in result.findings} == {
        FindingType.AMOUNT_MISMATCH,
        FindingType.DECIMAL_ERROR,
    }


def test_incorrect_aggregate_claim_is_detected_without_line_errors() -> None:
    reference = transfer(1, "100")
    result = verify(submission((reported(reference),), "101", 1), evidence((reference,)))

    assert result.outcome is VerificationOutcome.FAIL
    assert len(result.findings) == 1
    assert result.findings[0].finding_type is FindingType.AMOUNT_MISMATCH
    assert result.findings[0].expected == {"total_base_units": "100", "count": 1}


def test_unknown_pagination_is_inconclusive_and_not_a_service_failure() -> None:
    reference = transfer(1, "100")
    result = verify(submission((reported(reference),), "100", 1), evidence((reference,), next_cursor="page-2"))

    assert result.outcome is VerificationOutcome.INCONCLUSIVE
    assert result.reference_complete is False
    assert result.calculated_total_base_units is None
    assert result.findings[0].finding_type is FindingType.INSUFFICIENT_EVIDENCE
    assert result.findings[0].severity is FindingSeverity.WARNING
    assert result.findings[0].status is FindingStatus.HYPOTHESIS


def test_incomplete_source_or_known_shortfall_is_inconclusive() -> None:
    reference = transfer(1, "100")
    report = submission((reported(reference),), "100", 1)
    incomplete = verify(report, evidence((reference,), source_complete=False))
    shortfall = verify(report, evidence((reference,), sufficient=False, reason="RPC metadata missing"))

    assert incomplete.outcome is VerificationOutcome.INCONCLUSIVE
    assert incomplete.reference_complete is False
    assert shortfall.outcome is VerificationOutcome.INCONCLUSIVE
    assert shortfall.reference_complete is True
    assert shortfall.inconclusive_reason == "RPC metadata missing"


def test_conflicting_reference_sources_are_inconclusive() -> None:
    rpc = transfer(1, "100")
    blockscout = transfer(1, "101", source=EvidenceSource.BLOCKSCOUT)
    first = evidence((rpc,)).streams[0]
    second = evidence((blockscout,), source=EvidenceSource.BLOCKSCOUT).streams[0]
    reference = ReferenceEvidence(streams=(first, second), evidence_sufficient=True, insufficiency_reason=None)
    result = verify(submission((reported(rpc),), "100", 1), reference)

    assert result.outcome is VerificationOutcome.INCONCLUSIVE
    assert "disagree" in result.inconclusive_reason


def test_matching_sources_count_each_event_once() -> None:
    rpc = transfer(1, "100")
    blockscout = transfer(1, "100", source=EvidenceSource.BLOCKSCOUT)
    reference = ReferenceEvidence(
        streams=(
            evidence((rpc,)).streams[0],
            evidence((blockscout,), source=EvidenceSource.BLOCKSCOUT).streams[0],
        ),
        evidence_sufficient=True,
        insufficiency_reason=None,
    )
    result = verify(submission((reported(rpc),), "100", 1), reference)

    assert result.outcome is VerificationOutcome.PASS
    assert result.calculated_count == 1
    assert result.calculated_total_base_units == "100"


def test_more_than_200_relevant_events_requires_segmentation() -> None:
    records = tuple(transfer(1, "1", log_index=index) for index in range(201))
    result = verify(submission((), "0", 0), evidence(records))

    assert result.outcome is VerificationOutcome.INCONCLUSIVE
    assert "split the task" in result.inconclusive_reason
    assert result.calculated_total_base_units is None


def test_complete_empty_reference_can_pass_an_empty_report() -> None:
    result = verify(submission((), "0", 0), evidence(()))

    assert result.outcome is VerificationOutcome.PASS
    assert result.calculated_total_base_units == "0"
    assert result.calculated_count == 0
