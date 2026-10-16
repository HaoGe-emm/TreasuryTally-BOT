"""Workspace-scoped history rebuilt from immutable attempts, never publication snapshots."""

from dataclasses import dataclass
from pathlib import Path

from trust_receipt.hashing import verify_submission_hash
from trust_receipt.history import ReceiptHistoryInput, ServiceHistoryProjection, project_service_histories
from trust_receipt.history.m9_adapter import VerifiedM9RevisionAdapter
from trust_receipt.m9.ports import V1SubmissionSignatureVerifier
from trust_receipt.m9.revisions import LocalRevisionStore, build_receipt_revision
from trust_receipt.models import Receipt
from trust_receipt.receipts import load_receipt, replay_receipt
from trust_receipt.storage.ports import TaskRepository

TASK_TYPE = "erc20-grant-report-v1"


@dataclass(frozen=True)
class WorkspaceHistory:
    histories: tuple[ServiceHistoryProjection, ...]
    receipts: tuple[Receipt, ...]
    issues: tuple[str, ...]


class M10Workflow:
    def __init__(self, repository: TaskRepository, receipt_directory: Path, revisions: LocalRevisionStore) -> None:
        self._repository = repository
        self._directory = receipt_directory.resolve()
        self._revisions = revisions

    def read_history(self) -> WorkspaceHistory:
        inputs = []
        receipts = []
        revisions = []
        issues = []
        signatures = V1SubmissionSignatureVerifier()
        for stored in self._repository.list_tasks():
            task_id = stored.task.task_id
            task_receipts = []
            task_inputs = []
            try:
                attempts = self._repository.list_attempts(task_id)
                for record in attempts:
                    submission = record.submission
                    if record.verification_result is None:
                        raise ValueError("attempt verification is missing")
                    path = (self._directory / task_id / f"attempt-{submission.attempt}.json").resolve()
                    if not path.is_relative_to(self._directory):
                        raise ValueError("receipt path is outside the workspace")
                    receipt = load_receipt(path)
                    if (
                        not replay_receipt(receipt).valid
                        or not verify_submission_hash(submission)
                        or not signatures.verify(submission, receipt.service_identity)
                        or receipt.task_spec != stored.task
                        or receipt.submission_hash != submission.report_hash
                        or receipt.service_identity.service_id != submission.service_id
                        or receipt.verification_result != record.verification_result
                    ):
                        raise ValueError("attempt receipt, submission, identity or result does not match")
                    task_receipts.append(receipt)
                    task_inputs.append(ReceiptHistoryInput(
                        receipt, TASK_TYPE, f"workspace-attempt:{task_id}:{submission.attempt}",
                    ))
                task_revisions = self._revisions.list(task_id)
                # Legacy receipts can rebuild the relation from actual ordered attempts without writing files.
                if not task_revisions:
                    rebuilt = []
                    for receipt, record in zip(task_receipts, attempts, strict=True):
                        rebuilt.append(build_receipt_revision(
                            receipt, attempt=record.submission.attempt, parent=rebuilt[0] if rebuilt else None,
                        ))
                    task_revisions = tuple(rebuilt)
                if len(task_revisions) != len(task_receipts):
                    raise ValueError("revision chain does not cover all immutable attempts")
                VerifiedM9RevisionAdapter(task_receipts, task_revisions)
            except (OSError, ValueError, KeyError):
                issues.append(f"{task_id}: INCONCLUSIVE — 回执、交付或父版本链缺失/不一致。未计入服务事实。")
                continue
            inputs.extend(task_inputs)
            receipts.extend(task_receipts)
            revisions.extend(task_revisions)
        adapter = VerifiedM9RevisionAdapter(receipts, revisions)
        return WorkspaceHistory(
            project_service_histories(inputs, revision_port=adapter), tuple(receipts), tuple(issues),
        )
