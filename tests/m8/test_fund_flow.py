from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.fund_flow_graph import graph_svg
from trust_receipt.models import FixtureCase, FundFlowVisualStatus, VerificationOutcome
from trust_receipt.orchestration import evidence_from_fixture
from trust_receipt.projections import project_fund_flow
from trust_receipt.verification import verify_submission

CASES = tuple((Path(__file__).parents[2] / "fixtures" / "m1" / "cases").glob("*.json"))


@pytest.mark.parametrize("path", CASES, ids=lambda path: path.stem)
def test_all_frozen_cases_preserve_verdict_and_provenance(path):
    fixture = FixtureCase.model_validate_json(path.read_text(encoding="utf-8"))
    evidence = evidence_from_fixture(fixture, sufficient=fixture.reference.evidence_sufficient)
    now = datetime(2026, 10, 7, tzinfo=UTC)
    result = verify_submission(
        fixture.task_spec, fixture.submission, evidence,
        run_id="projection-matrix", started_at=now, finished_at=now,
    )
    projection = project_fund_flow(fixture.task_spec, fixture.submission, result, evidence)
    assert projection.outcome == result.outcome == fixture.expected.outcome
    assert projection.calculated_total_base_units == result.calculated_total_base_units
    for edge in projection.edges:
        assert all(record.source.value == "service" for record in edge.service_records)
        assert all(record.source.value != "service" for record in edge.reference_records)
        if result.outcome is VerificationOutcome.INCONCLUSIVE:
            assert edge.status is FundFlowVisualStatus.INCONCLUSIVE
        if edge.status is FundFlowVisualStatus.NOT_FOUND_ON_CHAIN:
            assert not edge.reference_records
            assert edge.finding_ids
    if path.stem == "decimal-unit-error":
        assert FundFlowVisualStatus.MISMATCH in {edge.status for edge in projection.edges}
    if path.stem == "out-of-range-event":
        assert FundFlowVisualStatus.INVALID_SCOPE in {edge.status for edge in projection.edges}
    assert "role=\"img\"" in graph_svg(projection)
    assert "stroke=\"none\"" in graph_svg(projection)


def test_finding_driven_projection_keeps_sources_event_keys_and_internal_transfer(m5_components) -> None:
    _, candidate, _, workflow, service = m5_components
    task = workflow.confirm_task(candidate)
    execution = workflow.run_attempt(task.task_id, service)
    projection = execution.fund_flow

    assert projection is not None
    assert projection.outcome is VerificationOutcome.FAIL
    statuses = {edge.status for edge in projection.edges}
    assert FundFlowVisualStatus.MATCHED in statuses
    assert FundFlowVisualStatus.MISSING_FROM_REPORT in statuses
    assert FundFlowVisualStatus.INTERNAL_TRANSFER in statuses
    missing = next(edge for edge in projection.edges if edge.status is FundFlowVisualStatus.MISSING_FROM_REPORT)
    assert missing.reference_refs
    assert not missing.service_refs
    assert missing.finding_ids
    assert len(missing.event_key) == 3


def test_insufficient_evidence_never_projects_a_negative_chain_fact(tmp_path, m5_components) -> None:
    from trust_receipt.agents import OfflineDemoStructuredOutputAdapter, RestrictedAIService
    from trust_receipt.orchestration import M5Workflow, StaticEvidenceProvider, evidence_from_fixture
    from trust_receipt.storage.sqlite import SQLiteRepository

    fixture, candidate, _, _, service = m5_components
    workflow = M5Workflow(
        repository=SQLiteRepository(tmp_path / "projection.db"),
        evidence_provider=StaticEvidenceProvider(evidence_from_fixture(fixture, sufficient=False)),
        ai_service=RestrictedAIService(OfflineDemoStructuredOutputAdapter(candidate)),
    )
    task = workflow.confirm_task(candidate)
    projection = workflow.run_attempt(task.task_id, service).fund_flow

    assert projection is not None
    assert projection.outcome is VerificationOutcome.INCONCLUSIVE
    assert {edge.status for edge in projection.edges} == {FundFlowVisualStatus.INCONCLUSIVE}
