"""M8 page-facing coordination with private persistence and deterministic recovery."""

from dataclasses import replace
from datetime import UTC, datetime

from trust_receipt.orchestration.m8 import M8CommitmentWorkflow
from trust_receipt.projections import project_fund_flow
from trust_receipt.storage.m8 import CommitmentSnapshot, M8ArtifactStore


class M8WorkspaceWorkflow:
    def __init__(self, workflow, commitments: M8CommitmentWorkflow, store: M8ArtifactStore) -> None:
        self._workflow = workflow
        self._commitments = commitments
        self._store = store

    def run_attempt(self, task, service):
        task_commitment = self._commitments.commit_task(task, service.service_id)
        holder = {}

        def accept(attempt):
            holder["accepted_at"] = datetime.now(UTC)
            holder["acceptance_signature"] = service.accept_task(
                task_commitment, attempt=attempt, accepted_at=holder["accepted_at"],
            )

        def validate(submission):
            delivery = self._commitments.commit_delivery(
                task_commitment, submission, service,
                accepted_at=holder["accepted_at"],
                acceptance_signature=holder["acceptance_signature"],
            )
            holder["snapshot"] = CommitmentSnapshot(
                task_commitment=task_commitment,
                delivery_commitment=delivery,
                expected_signer=service.signer_address,
            )

        execution = self._workflow.run_attempt(
            task.task_id, service, pre_persist_validator=validate, pre_submit=accept,
        )
        snapshot = holder["snapshot"]
        self._store.save_commitments(snapshot)
        if execution.evidence is not None:
            self._store.save_evidence(execution.submission.submission_id, execution.evidence)
        return execution, snapshot

    def restore_latest(self):
        restored = self._workflow.restore_latest()
        if restored is None:
            return None
        return self._restore_snapshots(restored)

    def get_attempt_status(self, task_id):
        return self._workflow.get_attempt_status(task_id)

    def restore_task(self, task_id):
        return self._restore_snapshots(self._workflow.restore_task(task_id))

    def _restore_snapshots(self, restored):
        task, executions = restored
        recovered = []
        snapshots = []
        for execution in executions:
            snapshot, evidence = self._store.restore(task, execution)
            recovered.append(replace(
                execution,
                evidence=evidence,
                fund_flow=project_fund_flow(task, execution.submission, execution.result, evidence)
                if evidence is not None else None,
            ))
            snapshots.append(snapshot)
        return task, tuple(recovered), tuple(snapshots)
