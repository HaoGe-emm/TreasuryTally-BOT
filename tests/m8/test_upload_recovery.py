import json
import sqlite3
from datetime import timedelta

import pytest

from trust_receipt.agents import OfflineDemoStructuredOutputAdapter, RestrictedAIService
from trust_receipt.commitments import verify_delivery_commitment, verify_task_commitment
from trust_receipt.models import VerificationOutcome
from trust_receipt.orchestration import M5Workflow, StaticEvidenceProvider, eligible_records, evidence_from_fixture
from trust_receipt.orchestration.m8 import M8CommitmentWorkflow
from trust_receipt.orchestration.m8_workspace import M8WorkspaceWorkflow
from trust_receipt.services.upload import UploadedReportService, parse_report
from trust_receipt.storage.m8 import M8ArtifactStore
from trust_receipt.storage.sqlite import RepositoryStateError, SQLiteRepository


def report_bytes(records, *, total=None):
    return json.dumps({
        "schema_version": "1.0",
        "claimed_total_base_units": total or str(sum(int(record.amount_base_units) for record in records)),
        "claimed_count": len(records),
        "transfers": [{**record.model_dump(mode="json"), "source": "service"} for record in records],
    }).encode()


@pytest.mark.parametrize("payload", [
    b"", b"\xff", b"[]", b"{}", b'{"schema_version":"1.0","schema_version":"1.0"}',
    b'{"schema_version":"1.0","claimed_total_base_units":1.2,"claimed_count":0,"transfers":[]}',
    b" " * 1_000_001,
], ids=["empty", "encoding", "array", "missing", "duplicate-key", "float-amount", "oversize"])
def test_upload_rejects_invalid_json_and_lossy_amounts(payload):
    with pytest.raises(ValueError):
        parse_report(payload)


def test_actual_upload_is_verified_without_rewriting_claims_and_recovers(tmp_path, m5_components):
    fixture, candidate, repository, workflow, _ = m5_components
    task = workflow.confirm_task(candidate)
    store = M8ArtifactStore(tmp_path / "m8.db")
    workspace = M8WorkspaceWorkflow(workflow, M8CommitmentWorkflow(), store)
    records = eligible_records(fixture)
    raw = report_bytes(records[:-1])
    service = UploadedReportService(raw, private_directory=tmp_path / "uploads")
    first, snapshot = workspace.run_attempt(task, service)
    assert first.result.outcome is VerificationOutcome.FAIL
    assert first.submission.report_text.encode() == raw
    assert first.submission.claimed_count == len(records) - 1
    assert first.receipt.service_identity.identity_scheme == "local-upload-intake"
    assert "unverified" in first.receipt.service_identity.name
    assert (tmp_path / "uploads" / f"{service.original_hash[2:]}.json").read_bytes() == raw
    assert snapshot.delivery_commitment.accepted_at <= first.submission.created_at
    assert verify_task_commitment(snapshot.task_commitment, task)
    assert verify_delivery_commitment(
        snapshot.delivery_commitment, snapshot.task_commitment, first.submission,
        expected_signer=service.signer_address,
    )
    corrected = UploadedReportService(report_bytes(records), private_directory=tmp_path / "uploads")
    second, _ = workspace.run_attempt(task, corrected)
    assert second.result.outcome is VerificationOutcome.PASS
    assert second.submission.attempt == 2
    with pytest.raises(RepositoryStateError):
        workspace.run_attempt(task, corrected)
    restarted_workflow = M5Workflow(
        repository=SQLiteRepository(tmp_path / "m8.db"),
        evidence_provider=StaticEvidenceProvider(evidence_from_fixture(fixture, sufficient=False)),
        ai_service=RestrictedAIService(OfflineDemoStructuredOutputAdapter(candidate)),
        receipt_directory=tmp_path / "receipts",
    )
    restored = M8WorkspaceWorkflow(
        restarted_workflow, M8CommitmentWorkflow(), M8ArtifactStore(tmp_path / "m8.db"),
    )
    restored_task, executions, snapshots = restored.restore_latest()
    assert restored_task == task
    assert len(repository.list_attempts(task.task_id)) == len(executions) == 2
    assert executions[0].evidence == first.evidence
    assert executions[0].fund_flow == first.fund_flow
    assert executions[1].fund_flow == second.fund_flow
    assert snapshots[0] == snapshot
    store.save_commitments(snapshot)
    with pytest.raises(ValueError, match="immutable"):
        store.save_commitments(snapshot.model_copy(update={"expected_signer": corrected.signer_address}))
    with sqlite3.connect(tmp_path / "m8.db") as connection:
        connection.execute("UPDATE m8_artifacts SET body_hash=? WHERE kind='evidence'", ("0x" + "0" * 64,))
    with pytest.raises(ValueError, match="content hash"):
        restored.restore_latest()


def test_acceptance_binds_full_task_and_subsecond_time(tmp_path, m5_components):
    _, candidate, _, workflow, service = m5_components
    task = workflow.confirm_task(candidate)
    workspace = M8WorkspaceWorkflow(workflow, M8CommitmentWorkflow(), M8ArtifactStore(tmp_path / "m8.db"))
    execution, snapshot = workspace.run_attempt(task, service)
    altered_task = snapshot.task_commitment.model_copy(update={
        "created_at": snapshot.task_commitment.created_at + timedelta(microseconds=1),
    })
    assert not verify_task_commitment(altered_task, task)
    assert not verify_delivery_commitment(
        snapshot.delivery_commitment, altered_task, execution.submission,
        expected_signer=service.signer_address,
    )
    altered_delivery = snapshot.delivery_commitment.model_copy(update={
        "accepted_at": snapshot.delivery_commitment.accepted_at + timedelta(microseconds=1),
    })
    assert not verify_delivery_commitment(
        altered_delivery, snapshot.task_commitment, execution.submission,
        expected_signer=service.signer_address,
    )
