from __future__ import annotations

import pytest

from trust_receipt.agents import OfflineDemoStructuredOutputAdapter, RestrictedAIService
from trust_receipt.models import PublicationChainStatus, VerificationOutcome, VerificationPlan
from trust_receipt.orchestration import M5Workflow, StaticEvidenceProvider, evidence_from_fixture
from trust_receipt.storage.sqlite import SQLiteRepository


def test_fail_then_resubmit_keeps_two_attempts_and_two_receipts(m5_components) -> None:
    _, candidate, repository, workflow, service = m5_components
    task = workflow.confirm_task(candidate)

    first = workflow.run_attempt(task.task_id, service)
    second = workflow.run_attempt(task.task_id, service)

    assert first.result.outcome is VerificationOutcome.FAIL
    assert second.result.outcome is VerificationOutcome.PASS
    assert [item.submission.attempt for item in repository.list_attempts(task.task_id)] == [1, 2]
    assert first.receipt.receipt_hash != second.receipt.receipt_hash
    assert first.receipt_path is not None and first.receipt_path.is_file()
    assert second.receipt_path is not None and second.receipt_path.is_file()
    assert first.receipt.publication.chain_status is PublicationChainStatus.NOT_SUBMITTED
    assert second.receipt.publication.chain_status is PublicationChainStatus.NOT_SUBMITTED
    assert first.explanation is not None
    assert first.explanation.outcome is first.result.outcome
    restored = workflow.restore_latest()
    assert restored is not None
    restored_task, restored_executions = restored
    assert restored_task.task_id == task.task_id
    assert [item.result.outcome for item in restored_executions] == [
        VerificationOutcome.FAIL,
        VerificationOutcome.PASS,
    ]


def test_inconclusive_is_explained_as_evidence_shortfall(tmp_path, m5_components) -> None:
    fixture, candidate, _, _, service = m5_components
    workflow = M5Workflow(
        repository=SQLiteRepository(tmp_path / "inconclusive.db"),
        evidence_provider=StaticEvidenceProvider(evidence_from_fixture(fixture, sufficient=False)),
        ai_service=RestrictedAIService(OfflineDemoStructuredOutputAdapter(candidate)),
    )
    task = workflow.confirm_task(candidate)

    execution = workflow.run_attempt(task.task_id, service)

    assert execution.result.outcome is VerificationOutcome.INCONCLUSIVE
    assert execution.explanation is not None
    assert "not a service failure" in execution.explanation.summary
    assert execution.follow_up is not None
    assert execution.follow_up.suggestions[0].action.value == "REFRESH_REFERENCE_EVIDENCE"


def test_invalid_ai_plan_returns_to_retryable_state_without_consuming_attempt(
    tmp_path, m5_components
) -> None:
    fixture, candidate, repository, _, service = m5_components
    delegate = OfflineDemoStructuredOutputAdapter(candidate)

    class InvalidPlanAdapter:
        def generate(self, *, schema, system_prompt, payload):
            artifact = delegate.generate(schema=schema, system_prompt=system_prompt, payload=payload)
            if schema is VerificationPlan:
                query = artifact.queries[0].model_copy(update={"arguments": {"chain_id": 1}})
                return artifact.model_copy(update={"queries": (query,)})
            return artifact

    workflow = M5Workflow(
        repository=repository,
        evidence_provider=StaticEvidenceProvider(evidence_from_fixture(fixture)),
        ai_service=RestrictedAIService(InvalidPlanAdapter()),
        receipt_directory=tmp_path / "rejected",
    )
    task = workflow.confirm_task(candidate)

    with pytest.raises(ValueError, match="derived from the confirmed task"):
        workflow.run_attempt(task.task_id, service)

    assert repository.list_attempts(task.task_id) == ()
