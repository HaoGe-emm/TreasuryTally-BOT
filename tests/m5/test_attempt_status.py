"""Persisted progress must survive incomplete execution, not reset to attempt 1."""

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from eth_account import Account

from trust_receipt.agents import OfflineDemoStructuredOutputAdapter, RestrictedAIService
from trust_receipt.hashing import canonical_json_bytes
from trust_receipt.orchestration import M5Workflow, StaticEvidenceProvider, eligible_records, evidence_from_fixture
from trust_receipt.orchestration.m8 import M8CommitmentWorkflow
from trust_receipt.orchestration.m8_workspace import M8WorkspaceWorkflow
from trust_receipt.services import FaultMode, TeamControlledReportService
from trust_receipt.storage.m8 import M8ArtifactStore
from trust_receipt.storage.models import AttemptBlockReason, TaskState
from trust_receipt.storage.sqlite import RepositoryStateError, SQLiteRepository


def restarted(tmp_path, fixture, candidate):
    return M5Workflow(
        repository=SQLiteRepository(tmp_path / "m5.db"),
        evidence_provider=StaticEvidenceProvider(evidence_from_fixture(fixture)),
        ai_service=RestrictedAIService(OfflineDemoStructuredOutputAdapter(candidate)),
        receipt_directory=tmp_path / "receipts",
    )


@pytest.mark.parametrize("state", [TaskState.REQUESTED, TaskState.SUBMITTED, TaskState.VERIFYING])
def test_new_session_retains_incomplete_attempt_without_reexecution(tmp_path, m5_components, state):
    fixture, candidate, repository, workflow, service = m5_components
    task = workflow.confirm_task(candidate)
    repository.request_attempt(task.task_id)
    if state is not TaskState.REQUESTED:
        delivery = service.submit(task, attempt=1)
        repository.save_delivery(delivery)
        if state is TaskState.VERIFYING:
            repository.begin_verification(task.task_id, delivery.submission.submission_id)
    fresh = restarted(tmp_path, fixture, candidate)
    assert fresh.restore_task(task.task_id) == (task, ())
    status = fresh.get_attempt_status(task.task_id)
    assert status.state is state
    assert status.in_flight_attempt == 1
    assert status.next_attempt is None
    assert status.completed_attempts == 0
    assert status.persisted_attempts == (0 if state is TaskState.REQUESTED else 1)
    assert status.blocking_reason is AttemptBlockReason.IN_FLIGHT
    with pytest.raises(RepositoryStateError):
        fresh.run_attempt(task.task_id, service)
    assert repository.get_task(task.task_id).state is state


def test_fetch_exception_keeps_saved_delivery_locked_and_visible(tmp_path, m5_components):
    fixture, candidate, repository, _, service = m5_components

    class InterruptedProvider:
        calls = 0

        def fetch(self, task):
            self.calls += 1
            raise RuntimeError("process interrupted after delivery")

    provider = InterruptedProvider()
    workflow = M5Workflow(
        repository=repository, evidence_provider=provider,
        ai_service=RestrictedAIService(OfflineDemoStructuredOutputAdapter(candidate)),
        receipt_directory=tmp_path / "receipts",
    )
    task = workflow.confirm_task(candidate)
    with pytest.raises(RuntimeError, match="interrupted"):
        workflow.run_attempt(task.task_id, service)
    record = repository.get_attempt(task.task_id, 1)
    fresh = restarted(tmp_path, fixture, candidate)
    assert fresh.restore_task(task.task_id)[1] == ()
    assert fresh.get_attempt_status(task.task_id).state is TaskState.VERIFYING
    with pytest.raises(RepositoryStateError):
        workflow.run_attempt(task.task_id, service)
    assert repository.get_attempt(task.task_id, 1) == record
    assert provider.calls == 1


def test_result_without_receipt_is_not_presented_as_new_or_retryable(tmp_path, m5_components, monkeypatch):
    fixture, candidate, repository, workflow, service = m5_components
    task = workflow.confirm_task(candidate)

    def failed_save(receipt, attempt):
        raise OSError("disk unavailable after result commit")

    monkeypatch.setattr(workflow, "_save_receipt", failed_save)
    with pytest.raises(OSError, match="disk unavailable"):
        workflow.run_attempt(task.task_id, service)
    assert repository.get_task(task.task_id).state is TaskState.FAIL
    fresh = restarted(tmp_path, fixture, candidate)
    assert fresh.restore_task(task.task_id)[1] == ()
    status = fresh.get_attempt_status(task.task_id)
    assert (status.persisted_attempts, status.completed_attempts) == (1, 1)
    assert status.next_attempt is None
    assert status.blocking_reason is AttemptBlockReason.MISSING_RECEIPT
    assert len(repository.list_attempts(task.task_id)) == 1


def test_progress_uses_persisted_counts_and_never_grants_third_attempt(m5_components):
    _, candidate, repository, workflow, service = m5_components
    task = workflow.confirm_task(candidate)
    assert workflow.get_attempt_status(task.task_id).next_attempt == 1
    first = workflow.run_attempt(task.task_id, service)
    assert workflow.get_attempt_status(task.task_id).next_attempt == 2
    repository.request_attempt(task.task_id)
    status = workflow.get_attempt_status(task.task_id)
    assert status.in_flight_attempt == 2
    assert status.next_attempt is None
    repository.cancel_attempt_request(task.task_id)
    second = workflow.run_attempt(task.task_id, service)
    status = workflow.get_attempt_status(task.task_id)
    assert (status.persisted_attempts, status.completed_attempts) == (2, 2)
    assert status.next_attempt is None
    assert status.blocking_reason is AttemptBlockReason.PASSED
    assert first.receipt.receipt_hash != second.receipt.receipt_hash
    with pytest.raises(RepositoryStateError):
        workflow.run_attempt(task.task_id, service)


def test_current_task_recovery_is_not_changed_by_newest_task(tmp_path, m5_components):
    _, candidate, _, workflow, service = m5_components
    first_task = workflow.confirm_task(candidate)
    workspace = M8WorkspaceWorkflow(workflow, M8CommitmentWorkflow(), M8ArtifactStore(tmp_path / "m5.db"))
    execution, snapshot = workspace.run_attempt(first_task, service)
    second_task = workflow.confirm_task(candidate)
    assert workspace.restore_latest()[0] == second_task
    task, executions, snapshots = workspace.restore_task(first_task.task_id)
    assert task == first_task
    assert executions[0].receipt == execution.receipt
    assert snapshots == (snapshot,)
    assert workspace.get_attempt_status(first_task.task_id).next_attempt == 2


@pytest.mark.parametrize("sufficient", [True, False])
def test_two_nonpassing_attempts_are_exhausted_not_retryable(tmp_path, m5_components, sufficient):
    fixture, candidate, repository, _, _ = m5_components
    workflow = M5Workflow(
        repository=repository,
        evidence_provider=StaticEvidenceProvider(evidence_from_fixture(fixture, sufficient=sufficient)),
        ai_service=RestrictedAIService(OfflineDemoStructuredOutputAdapter(candidate)),
        receipt_directory=tmp_path / "receipts",
    )
    service = TeamControlledReportService(
        service_id="service-a", private_key=Account.create().key.to_0x_hex(),
        records_provider=lambda _: eligible_records(fixture),
        fault_by_attempt={1: FaultMode.OMIT_LAST_TRANSFER, 2: FaultMode.OMIT_LAST_TRANSFER},
    )
    task = workflow.confirm_task(candidate)
    workflow.run_attempt(task.task_id, service)
    assert workflow.get_attempt_status(task.task_id).next_attempt == 2
    workflow.run_attempt(task.task_id, service)
    status = workflow.get_attempt_status(task.task_id)
    assert status.state is (TaskState.FAIL if sufficient else TaskState.INCONCLUSIVE)
    assert status.next_attempt is None
    assert status.blocking_reason is AttemptBlockReason.ATTEMPTS_EXHAUSTED
    with pytest.raises(RepositoryStateError):
        workflow.run_attempt(task.task_id, service)


def test_receipt_conflict_is_blocked_in_status_and_current_task_recovery(m5_components):
    _, candidate, repository, workflow, service = m5_components
    task = workflow.confirm_task(candidate)
    execution = workflow.run_attempt(task.task_id, service)
    execution.receipt_path.write_bytes(canonical_json_bytes(
        execution.receipt.model_copy(update={"receipt_hash": "0x" + "0" * 64}),
    ))
    status = workflow.get_attempt_status(task.task_id)
    assert status.blocking_reason is AttemptBlockReason.RECEIPT_CONFLICT
    assert status.next_attempt is None
    with pytest.raises(ValueError, match="receipt_hash"):
        workflow.restore_task(task.task_id)
    assert repository.get_attempt(task.task_id, 1).verification_result == execution.result


def test_two_connections_cannot_both_reserve_the_same_attempt(tmp_path, m5_components, monkeypatch):
    _, candidate, repository, workflow, _ = m5_components
    task = workflow.confirm_task(candidate)
    barrier = Barrier(2)

    class RaceConnection(sqlite3.Connection):
        def execute(self, sql, parameters=()):
            cursor = super().execute(sql, parameters)
            # Force the old nontransactional read/check/update interleaving.
            # With BEGIN IMMEDIATE the second requester cannot read stale state.
            if sql == "SELECT state FROM tasks WHERE task_id = ?" and not self.in_transaction:
                barrier.wait(timeout=5)
            return cursor

    def connect():
        connection = sqlite3.connect(tmp_path / "m5.db", factory=RaceConnection)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    monkeypatch.setattr(repository, "_connect", connect)

    def request():
        try:
            return repository.request_attempt(task.task_id)
        except RepositoryStateError:
            return "blocked"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: request(), range(2)))
    assert results.count(1) == results.count("blocked") == 1
    assert repository.get_attempt_status(task.task_id).state is TaskState.REQUESTED
