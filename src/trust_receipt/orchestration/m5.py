"""M5 page-facing use case that composes existing stable ports."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from trust_receipt.agents import FollowUpAdvice, RestrictedAIService, ResultExplanation, TaskSpecCandidate
from trust_receipt.chain import EvidenceDiagnostic
from trust_receipt.hashing import verify_submission_hash, verify_task_spec_hash
from trust_receipt.models import (
    FixtureCase,
    FundFlowProjection,
    Receipt,
    ServiceIdentity,
    ServiceSubmission,
    TaskSpec,
    VerificationPlan,
    VerificationResult,
)
from trust_receipt.orchestration.workflow import ReferenceEvidenceProvider
from trust_receipt.projections import project_fund_flow
from trust_receipt.receipts import build_receipt, load_receipt, replay_receipt, save_receipt
from trust_receipt.services import ReportService, verify_submission_signature
from trust_receipt.storage.models import AttemptBlockReason, AttemptStatus
from trust_receipt.storage.ports import TaskRepository
from trust_receipt.verification import ReferenceEvidence, ReferencePage, ReferenceStream, verify_submission
from trust_receipt.verification.scope import scope_violation


@dataclass(frozen=True)
class StaticEvidenceProvider:
    evidence: ReferenceEvidence

    def fetch(self, task: TaskSpec) -> ReferenceEvidence:
        del task
        return self.evidence


@dataclass(frozen=True)
class AttemptExecution:
    submission: ServiceSubmission
    plan: VerificationPlan
    result: VerificationResult
    receipt: Receipt
    receipt_path: Path | None
    explanation: ResultExplanation | None
    follow_up: FollowUpAdvice | None
    ai_errors: tuple[str, ...]
    evidence: ReferenceEvidence | None
    evidence_diagnostics: tuple[EvidenceDiagnostic, ...]
    fund_flow: FundFlowProjection | None


class M5Workflow:
    """One page-safe vertical workflow; no Streamlit or supplier SDK dependency."""

    def __init__(
        self,
        *,
        repository: TaskRepository,
        evidence_provider: ReferenceEvidenceProvider,
        ai_service: RestrictedAIService,
        receipt_directory: Path | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        id_factory: Callable[[], str] = lambda: str(uuid4()),
    ) -> None:
        self._repository = repository
        self._evidence_provider = evidence_provider
        self._ai_service = ai_service
        self._receipt_directory = receipt_directory
        self._clock = clock
        self._id_factory = id_factory

    def draft_task(self, user_request: str) -> TaskSpecCandidate:
        if not user_request.strip():
            raise ValueError("Describe the verification task before generating a candidate")
        return self._ai_service.draft_task(user_request)

    def confirm_task(self, candidate: TaskSpecCandidate) -> TaskSpec:
        task = self._ai_service.confirm_task(
            candidate,
            task_id=f"task-{self._id_factory()}",
            confirmed_at=self._clock(),
        )
        if not verify_task_spec_hash(task):
            raise ValueError("confirmed task hash does not match canonical content")
        self._repository.add_task(task)
        return task

    def run_attempt(
        self,
        task_id: str,
        service: ReportService,
        *,
        pre_persist_validator: Callable[[ServiceSubmission], None] | None = None,
        pre_submit: Callable[[int], None] | None = None,
    ) -> AttemptExecution:
        stored = self._repository.get_task(task_id)
        attempt = self._repository.request_attempt(task_id)
        try:
            if pre_submit is not None:
                pre_submit(attempt)
            delivery = service.submit(stored.task, attempt=attempt)
            submission = delivery.submission
            self._validate_delivery(service, submission)
            if pre_persist_validator is not None:
                pre_persist_validator(submission)
            extraction = self._ai_service.extract_claims(
                report_id=submission.submission_id,
                report_text=submission.report_text,
            )
            plan = self._ai_service.propose_plan(stored.task, extraction)
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
            run_id=f"run-{self._id_factory()}",
            started_at=started_at,
            finished_at=self._clock(),
        )
        self._repository.save_verification(result)

        explanation, follow_up, errors = self._safe_ai_result_artifacts(result)
        receipt = build_receipt(
            receipt_id=f"receipt-{self._id_factory()}",
            task=stored.task,
            submission=submission,
            service_identity=ServiceIdentity(
                service_id=submission.service_id,
                name=getattr(service, "identity_name", f"Team-controlled {submission.service_id}"),
                identity_scheme=getattr(service, "identity_scheme", "local-demo-signer"),
                identity_reference=service.signer_address,
            ),
            plan=plan,
            result=result,
            evidence=evidence,
            created_at=self._clock(),
        )
        receipt_path = self._save_receipt(receipt, attempt)
        return AttemptExecution(
            submission=submission,
            plan=plan,
            result=result,
            receipt=receipt,
            receipt_path=receipt_path,
            explanation=explanation,
            follow_up=follow_up,
            ai_errors=errors,
            evidence=evidence,
            evidence_diagnostics=tuple(getattr(self._evidence_provider, "diagnostics", ())),
            fund_flow=project_fund_flow(stored.task, submission, result, evidence),
        )

    def list_attempts(self, task_id: str):
        return self._repository.list_attempts(task_id)

    def get_attempt_status(self, task_id: str) -> AttemptStatus:
        status = self._repository.get_attempt_status(task_id)
        if self._receipt_directory is None:
            return status
        records = self._repository.list_attempts(task_id)
        if len(records) != status.persisted_attempts:
            return replace(status, next_attempt=None, blocking_reason=AttemptBlockReason.STATE_CONFLICT)
        task = self._repository.get_task(task_id).task
        for record in records:
            if record.verification_result is None:
                continue
            path = self._receipt_directory / task_id / f"attempt-{record.submission.attempt}.json"
            if not path.is_file():
                return replace(status, next_attempt=None, blocking_reason=AttemptBlockReason.MISSING_RECEIPT)
            try:
                self._validate_restored_receipt(load_receipt(path), task, record)
            except (OSError, ValueError):
                return replace(status, next_attempt=None, blocking_reason=AttemptBlockReason.RECEIPT_CONFLICT)
        return status

    def restore_latest(self) -> tuple[TaskSpec, tuple[AttemptExecution, ...]] | None:
        """Restore the newest completed task after a Streamlit process restart."""
        tasks = self._repository.list_tasks()
        if not tasks:
            return None
        return self.restore_task(tasks[0].task.task_id)

    def restore_task(self, task_id: str) -> tuple[TaskSpec, tuple[AttemptExecution, ...]]:
        """Read only this task's available receipts; never request or rerun it."""
        task = self._repository.get_task(task_id).task
        executions: list[AttemptExecution] = []
        for attempt in self._repository.list_attempts(task.task_id):
            if attempt.verification_result is None or self._receipt_directory is None:
                continue
            number = attempt.submission.attempt
            path = self._receipt_directory / task.task_id / f"attempt-{number}.json"
            if not path.is_file():
                continue
            receipt = load_receipt(path)
            self._validate_restored_receipt(receipt, task, attempt)
            list_publications = getattr(self._repository, "list_publications", None)
            if list_publications is not None:
                events = list_publications(receipt.receipt_id)
                if events:
                    receipt = events[-1].receipt
            executions.append(
                AttemptExecution(
                    submission=attempt.submission,
                    plan=receipt.verification_plan,
                    result=receipt.verification_result,
                    receipt=receipt,
                    receipt_path=path,
                    explanation=None,
                    follow_up=None,
                    ai_errors=("Restored locally; AI text was not regenerated.",),
                    evidence=None,
                    evidence_diagnostics=(),
                    fund_flow=None,
                )
            )
        return task, tuple(executions)

    @staticmethod
    def _validate_restored_receipt(receipt, task, record) -> None:
        if (
            not replay_receipt(receipt).valid or receipt.task_spec != task
            or receipt.submission_hash != record.submission.report_hash
            or receipt.verification_result != record.verification_result
            or receipt.service_identity.service_id != record.submission.service_id
        ):
            raise ValueError("stored receipt conflicts with the persisted task attempt")

    @staticmethod
    def _validate_delivery(service: ReportService, submission) -> None:
        if submission.service_id != service.service_id:
            raise ValueError("service response identity does not match selected service")
        if not verify_submission_hash(submission):
            raise ValueError("service report_hash does not match canonical content")
        if not verify_submission_signature(submission, service.signer_address):
            raise ValueError("service submission signature is invalid")

    def _safe_ai_result_artifacts(
        self, result: VerificationResult
    ) -> tuple[ResultExplanation | None, FollowUpAdvice | None, tuple[str, ...]]:
        errors: list[str] = []
        explanation = None
        follow_up = None
        try:
            explanation = self._ai_service.explain_result(result)
        except Exception:
            # Vendor/validation exceptions may embed private model input.
            errors.append("RESULT_EXPLANATION_UNAVAILABLE")
        try:
            follow_up = self._ai_service.suggest_follow_up(result)
        except Exception:
            errors.append("FOLLOW_UP_ADVICE_UNAVAILABLE")
        return explanation, follow_up, tuple(errors)

    def _save_receipt(self, receipt: Receipt, attempt: int) -> Path | None:
        if self._receipt_directory is None:
            return None
        path = self._receipt_directory / receipt.task_spec.task_id / f"attempt-{attempt}.json"
        return save_receipt(receipt, path)


def load_vertical_demo_fixture(project_root: Path) -> FixtureCase:
    path = project_root / "fixtures" / "m1" / "cases" / "missing-transfer-vertical-slice.json"
    return FixtureCase.model_validate(json.loads(path.read_text(encoding="utf-8")))


def candidate_from_fixture(fixture: FixtureCase) -> TaskSpecCandidate:
    task = fixture.task_spec
    return TaskSpecCandidate(
        schema_version="1.0",
        candidate_id=f"candidate-{fixture.fixture_id}",
        chain_id=task.chain_id,
        token_address=task.token_address,
        treasury_addresses=task.treasury_addresses,
        recipient_addresses=task.recipient_addresses,
        start_block=task.start_block,
        end_block=task.end_block,
        exclusion_rules=task.exclusion_rules,
        max_records=200,
        ambiguities=(),
        missing_fields=(),
        clarification_questions=(),
    )


def evidence_from_fixture(fixture: FixtureCase, *, sufficient: bool = True) -> ReferenceEvidence:
    source = fixture.reference.sources[0]
    stream = ReferenceStream(
        source=source,
        pages=(ReferencePage(cursor=None, next_cursor=None, transfers=fixture.reference.transfers),),
    )
    return ReferenceEvidence(
        streams=(stream,),
        evidence_sufficient=sufficient,
        insufficiency_reason=None if sufficient else "Offline demo: independent evidence source unavailable",
    )


def eligible_records(fixture: FixtureCase):
    return tuple(record for record in fixture.reference.transfers if scope_violation(fixture.task_spec, record) is None)
