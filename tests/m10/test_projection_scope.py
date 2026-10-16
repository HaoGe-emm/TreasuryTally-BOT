"""Reference inventory is broader than the confirmed report scope."""

from datetime import UTC, datetime

import pytest

from tests.contracts.samples import submission_data, task_data, transfer_data
from trust_receipt.models import (
    EvidenceSource,
    FundFlowVisualStatus,
    ServiceSubmission,
    SourceDescriptor,
    TaskSpec,
    TransferRecord,
)
from trust_receipt.projections import project_fund_flow
from trust_receipt.verification import ReferenceEvidence, ReferencePage, ReferenceStream, verify_submission

NOW = datetime(2026, 10, 7, tzinfo=UTC)
EXTERNAL = "0x9999999999999999999999999999999999999999"


def project(task, records, submitted=()):
    evidence = ReferenceEvidence(
        streams=(ReferenceStream(
            source=SourceDescriptor(
                source=EvidenceSource.RPC, source_id="scope-rpc", retrieved_at=NOW,
                complete=True, details={},
            ),
            pages=(ReferencePage(cursor=None, next_cursor=None, transfers=tuple(records)),),
        ),),
        evidence_sufficient=True, insufficiency_reason=None,
    )
    raw = submission_data()
    raw.update(task_id=task.task_id, transfers=[item.model_dump(mode="json") for item in submitted],
               claimed_total_base_units="0", claimed_count=0)
    submission = ServiceSubmission.model_validate(raw)
    result = verify_submission(task, submission, evidence, run_id="scope-test", started_at=NOW, finished_at=NOW)
    return result, project_fund_flow(task, submission, result, evidence)


def test_six_raw_events_only_one_eligible_transfer_is_report_missing():
    task = TaskSpec.model_validate(task_data())
    eligible = TransferRecord.model_validate(transfer_data(source="rpc", amount="180674489737"))
    unrelated = tuple(eligible.model_copy(update={
        "log_index": index + 10, "from_address": EXTERNAL, "to_address": EXTERNAL,
    }) for index in range(5))
    result, projection = project(task, (eligible, *unrelated))
    assert result.calculated_total_base_units == "180674489737"
    assert result.calculated_count == 1
    assert len(result.findings) == 1
    assert len(projection.edges) == 1
    assert projection.edges[0].status is FundFlowVisualStatus.MISSING_FROM_REPORT
    assert projection.edges[0].finding_ids == (result.findings[0].finding_id,)
    assert projection.calculated_total_base_units == result.calculated_total_base_units
    assert projection.outcome == result.outcome


@pytest.mark.parametrize("updates", [
    {"from_address": EXTERNAL},
    {"to_address": EXTERNAL},
    {"block_number": 8_998_999},
    {"block_number": 9_001_001},
    {"token_address": EXTERNAL},
    {"chain_id": 1},
])
def test_reference_only_outside_scope_cannot_invent_missing_report_event(updates):
    task = TaskSpec.model_validate(task_data())
    record = TransferRecord.model_validate(transfer_data(source="rpc")).model_copy(update=updates)
    result, projection = project(task, (record,))
    assert projection.edges == ()
    assert projection.nodes == ()
    assert projection.outcome == result.outcome
    assert projection.calculated_total_base_units == result.calculated_total_base_units


@pytest.mark.parametrize("updates", [
    {"from_address": EXTERNAL}, {"to_address": EXTERNAL},
    {"block_number": 9_001_001}, {"token_address": EXTERNAL},
])
def test_submitted_outside_scope_keeps_both_original_sources(updates):
    task = TaskSpec.model_validate(task_data())
    reference = TransferRecord.model_validate(transfer_data(source="rpc")).model_copy(update=updates)
    submitted = reference.model_copy(update={"source": EvidenceSource.SERVICE})
    result, projection = project(task, (reference,), (submitted,))
    assert len(projection.edges) == 1
    edge = projection.edges[0]
    assert edge.status is FundFlowVisualStatus.INVALID_SCOPE
    assert edge.service_records == (submitted,)
    assert edge.reference_records == (reference,)
    assert edge.finding_ids
    assert projection.outcome == result.outcome


def test_internal_reference_is_explained_only_in_confirmed_chain_token_block_scope():
    task = TaskSpec.model_validate(task_data())
    internal = TransferRecord.model_validate(transfer_data(source="rpc")).model_copy(update={
        "to_address": task.treasury_addresses[0],
    })
    _, projection = project(task, (internal,))
    assert len(projection.edges) == 1
    assert projection.edges[0].status is FundFlowVisualStatus.INTERNAL_TRANSFER
    for updates in ({"chain_id": 1}, {"token_address": EXTERNAL}, {"block_number": 9_001_001}):
        _, outside = project(task, (internal.model_copy(update=updates),))
        assert outside.edges == ()
