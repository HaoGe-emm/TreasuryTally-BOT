"""Application orchestration with no UI, database, or supplier SDK coupling."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Protocol
from uuid import uuid4

from trust_receipt.hashing import verify_submission_hash, verify_task_spec_hash
from trust_receipt.models.enums import VerificationOutcome
from trust_receipt.models.tasks import TaskSpec
from trust_receipt.models.verification import VerificationResult
from trust_receipt.services.ports import ReportService
from trust_receipt.services.signatures import verify_submission_signature
from trust_receipt.storage.ports import TaskRepository
from trust_receipt.verification import ReferenceEvidence, verify_submission


class ReferenceEvidenceProvider(Protocol):
    def fetch(self, task: TaskSpec) -> ReferenceEvidence: ...


def is_negative_feedback_candidate(result: VerificationResult) -> bool:
    """Only an evidence-sufficient FAIL may become negative reputation input."""
    return (
        result.outcome is VerificationOutcome.FAIL
        and result.reference_complete
        and result.evidence_sufficient
    )


class VerificationOrchestrator:
    def __init__(
        self,
        *,
        repository: TaskRepository,
        evidence_provider: ReferenceEvidenceProvider,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        id_factory: Callable[[], str] = lambda: str(uuid4()),
    ) -> None:
        self._repository = repository
        self._evidence_provider = evidence_provider
        self._clock = clock
        self._id_factory = id_factory

    def confirm_task(self, task: TaskSpec) -> None:
        if not verify_task_spec_hash(task):
            raise ValueError("task spec_hash does not match its canonical content")
        self._repository.add_task(task)

    def run_attempt(self, task_id: str, service: ReportService) -> VerificationResult:
        stored = self._repository.get_task(task_id)
        attempt = self._repository.request_attempt(task_id)
        try:
            delivery = service.submit(stored.task, attempt=attempt)
            submission = delivery.submission
            if submission.service_id != service.service_id:
                raise ValueError("service response identity does not match selected service")
            if not verify_submission_hash(submission):
                raise ValueError("service report_hash does not match its canonical content")
            if not verify_submission_signature(submission, service.signer_address):
                raise ValueError("service submission signature is invalid")
        except Exception:
            self._repository.cancel_attempt_request(task_id)
            raise
        self._repository.save_delivery(delivery)
        self._repository.begin_verification(task_id, submission.submission_id)
        evidence = self._evidence_provider.fetch(stored.task)
        started_at = self._clock()
        result = verify_submission(
            stored.task,
            submission,
            evidence,
            run_id=self._id_factory(),
            started_at=started_at,
            finished_at=self._clock(),
        )
        self._repository.save_verification(result)
        return result
