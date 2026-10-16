from itertools import permutations

from trust_receipt.models import EvidenceSource, VerificationOutcome
from trust_receipt.verification import ReferenceEvidence, ReferencePage, ReferenceStream

from .test_engine import evidence, reported, submission, transfer, verify


def test_event_order_does_not_change_the_result() -> None:
    records = (transfer(1, "9007199254740993"), transfer(2, "7"), transfer(3, "0"))
    for reference_order in permutations(records):
        for report_order in permutations(records):
            result = verify(
                submission(tuple(reported(record) for record in report_order), "9007199254741000", 3),
                evidence(reference_order),
            )
            assert result.outcome is VerificationOutcome.PASS
            assert result.calculated_total_base_units == "9007199254741000"
            assert result.calculated_count == 3
            assert result.findings == ()


def test_complete_sources_with_different_event_sets_cannot_be_unionized_into_pass() -> None:
    rpc = transfer(1, "10")
    blockscout = transfer(2, "20", source=EvidenceSource.BLOCKSCOUT)
    streams = (evidence((rpc,)).streams[0], evidence((blockscout,), source=EvidenceSource.BLOCKSCOUT).streams[0])
    for order in permutations(streams):
        reference = ReferenceEvidence(streams=order, evidence_sufficient=True, insufficiency_reason=None)
        result = verify(submission((reported(rpc), reported(blockscout)), "30", 2), reference)
        assert result.outcome is VerificationOutcome.INCONCLUSIVE
        assert result.calculated_total_base_units is None


def test_different_events_in_one_block_cannot_have_conflicting_block_hashes() -> None:
    first = transfer(1, "10")
    second = transfer(2, "20").model_copy(update={"block_hash": "0x" + "c" * 64})
    for order in permutations((first, second)):
        result = verify(submission((reported(first), reported(second)), "30", 2), evidence(order))
        assert result.outcome is VerificationOutcome.INCONCLUSIVE


def test_reordering_pages_is_not_treated_as_complete() -> None:
    first, second = transfer(1, "10"), transfer(2, "20")
    pages = (
        ReferencePage(cursor="next", next_cursor=None, transfers=(second,)),
        ReferencePage(cursor=None, next_cursor="next", transfers=(first,)),
    )
    reference = ReferenceEvidence(
        streams=(ReferenceStream(source=evidence(()).streams[0].source, pages=pages),),
        evidence_sufficient=True,
        insufficiency_reason=None,
    )
    result = verify(submission((reported(first), reported(second)), "30", 2), reference)
    assert result.outcome is VerificationOutcome.INCONCLUSIVE
    assert not result.reference_complete


def test_count_only_claim_error_cannot_pass() -> None:
    record = transfer(1, "10")
    result = verify(submission((reported(record),), "10", 2), evidence((record,)))
    assert result.outcome is VerificationOutcome.FAIL
    assert result.findings[0].expected["count"] == 1
    assert result.findings[0].actual["count"] == 2
