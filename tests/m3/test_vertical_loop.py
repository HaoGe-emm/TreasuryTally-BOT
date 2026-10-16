from __future__ import annotations

from dataclasses import dataclass

import pytest

from trust_receipt.models.enums import VerificationOutcome
from trust_receipt.orchestration import VerificationOrchestrator, is_negative_feedback_candidate
from trust_receipt.services import FaultMode, TeamControlledReportService
from trust_receipt.storage.models import TaskState
from trust_receipt.storage.sqlite import RepositoryStateError, SQLiteRepository
from trust_receipt.verification import ReferenceEvidence


@dataclass(frozen=True)
class StaticEvidenceProvider:
    evidence: ReferenceEvidence

    def fetch(self, task):
        return self.evidence


def _orchestrator(repository, evidence, fixed_time):
    ids = iter(("run-1", "run-2", "run-3"))
    return VerificationOrchestrator(
        repository=repository,
        evidence_provider=StaticEvidenceProvider(evidence),
        clock=lambda: fixed_time,
        id_factory=lambda: next(ids),
    )


def _service(service_id, private_key, records, fixed_time, faults=None):
    return TeamControlledReportService(
        service_id=service_id,
        private_key=private_key,
        records_provider=lambda task: records,
        fault_by_attempt=faults,
        clock=lambda: fixed_time,
    )


def test_fail_then_one_resubmission_passes_and_both_attempts_remain_readable(
    tmp_path, hashed_task, eligible_service_records, reference_evidence, fixed_time, private_key_a
) -> None:
    repository = SQLiteRepository(tmp_path / "vertical.db")
    orchestrator = _orchestrator(repository, reference_evidence, fixed_time)
    service_a = _service(
        "service-a",
        private_key_a,
        eligible_service_records,
        fixed_time,
        {1: FaultMode.OMIT_LAST_TRANSFER},
    )
    orchestrator.confirm_task(hashed_task)
    first = orchestrator.run_attempt(hashed_task.task_id, service_a)
    second = orchestrator.run_attempt(hashed_task.task_id, service_a)

    assert first.outcome is VerificationOutcome.FAIL
    assert second.outcome is VerificationOutcome.PASS
    attempts = repository.list_attempts(hashed_task.task_id)
    assert [record.submission.attempt for record in attempts] == [1, 2]
    assert [record.verification_result.outcome for record in attempts] == [
        VerificationOutcome.FAIL,
        VerificationOutcome.PASS,
    ]
    assert repository.get_task(hashed_task.task_id).state is TaskState.PASS
    with pytest.raises(RepositoryStateError, match="only once"):
        orchestrator.run_attempt(hashed_task.task_id, service_a)


def test_failed_service_can_switch_to_service_b(
    tmp_path,
    hashed_task,
    eligible_service_records,
    reference_evidence,
    fixed_time,
    private_key_a,
    private_key_b,
) -> None:
    repository = SQLiteRepository(tmp_path / "switch.db")
    orchestrator = _orchestrator(repository, reference_evidence, fixed_time)
    service_a = _service(
        "service-a",
        private_key_a,
        eligible_service_records,
        fixed_time,
        {1: FaultMode.OMIT_LAST_TRANSFER},
    )
    service_b = _service("service-b", private_key_b, eligible_service_records, fixed_time)
    orchestrator.confirm_task(hashed_task)
    assert orchestrator.run_attempt(hashed_task.task_id, service_a).outcome is VerificationOutcome.FAIL
    assert orchestrator.run_attempt(hashed_task.task_id, service_b).outcome is VerificationOutcome.PASS
    assert [item.submission.service_id for item in repository.list_attempts(hashed_task.task_id)] == [
        "service-a",
        "service-b",
    ]


def test_inconclusive_is_not_negative_feedback(
    tmp_path, hashed_task, eligible_service_records, reference_evidence, fixed_time, private_key_a
) -> None:
    incomplete = reference_evidence.model_copy(
        update={"evidence_sufficient": False, "insufficiency_reason": "RPC unavailable"}
    )
    repository = SQLiteRepository(tmp_path / "inconclusive.db")
    orchestrator = _orchestrator(repository, incomplete, fixed_time)
    service = _service("service-a", private_key_a, eligible_service_records, fixed_time)
    orchestrator.confirm_task(hashed_task)
    result = orchestrator.run_attempt(hashed_task.task_id, service)
    assert result.outcome is VerificationOutcome.INCONCLUSIVE
    assert not is_negative_feedback_candidate(result)
    assert repository.get_task(hashed_task.task_id).state is TaskState.INCONCLUSIVE


def test_invalid_signature_is_rejected_without_consuming_attempt(
    tmp_path, hashed_task, eligible_service_records, reference_evidence, fixed_time, private_key_a
) -> None:
    repository = SQLiteRepository(tmp_path / "signature.db")
    orchestrator = _orchestrator(repository, reference_evidence, fixed_time)
    valid_service = _service("service-a", private_key_a, eligible_service_records, fixed_time)

    class WrongSignerService:
        service_id = valid_service.service_id
        signer_address = "0x" + "ff" * 20

        def submit(self, task, *, attempt):
            return valid_service.submit(task, attempt=attempt)

    orchestrator.confirm_task(hashed_task)
    with pytest.raises(ValueError, match="signature"):
        orchestrator.run_attempt(hashed_task.task_id, WrongSignerService())
    assert repository.get_task(hashed_task.task_id).state is TaskState.CONFIRMED
    assert repository.list_attempts(hashed_task.task_id) == ()
