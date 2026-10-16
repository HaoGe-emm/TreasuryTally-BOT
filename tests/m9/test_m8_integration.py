from pathlib import Path

from eth_account import Account

from trust_receipt.agents import OfflineDemoStructuredOutputAdapter, RestrictedAIService
from trust_receipt.m9 import CommitmentStatus, LocalRevisionStore
from trust_receipt.m9.commitments import M8CommitmentBinding, M8ReceiptCommitmentVerifier
from trust_receipt.orchestration import (
    M5Workflow,
    StaticEvidenceProvider,
    candidate_from_fixture,
    eligible_records,
    evidence_from_fixture,
    load_vertical_demo_fixture,
)
from trust_receipt.orchestration.m8 import M8CommitmentWorkflow
from trust_receipt.orchestration.m8_workspace import M8WorkspaceWorkflow
from trust_receipt.orchestration.m9 import build_m9_artifacts
from trust_receipt.services import FaultMode, TeamControlledReportService
from trust_receipt.storage.m8 import M8ArtifactStore
from trust_receipt.storage.sqlite import SQLiteRepository


def _m5_components(tmp_path):
    fixture = load_vertical_demo_fixture(Path(__file__).parents[2])
    candidate = candidate_from_fixture(fixture)
    workflow = M5Workflow(
        repository=SQLiteRepository(tmp_path / "m9-m8.db"),
        evidence_provider=StaticEvidenceProvider(evidence_from_fixture(fixture)),
        ai_service=RestrictedAIService(OfflineDemoStructuredOutputAdapter(candidate)),
        receipt_directory=tmp_path / "receipts",
    )
    service = TeamControlledReportService(
        service_id="service-a",
        private_key=Account.create().key.to_0x_hex(),
        records_provider=lambda _: eligible_records(fixture),
        fault_by_attempt={1: FaultMode.OMIT_LAST_TRANSFER},
    )
    return candidate, workflow, service


def test_m9_comparison_verifies_real_m8_commitment_snapshots(tmp_path) -> None:
    candidate, workflow, service = _m5_components(tmp_path)
    task = workflow.confirm_task(candidate)
    workspace = M8WorkspaceWorkflow(
        workflow,
        M8CommitmentWorkflow(),
        M8ArtifactStore(tmp_path / "m8-artifacts.db"),
    )
    first, first_snapshot = workspace.run_attempt(task, service)
    second, second_snapshot = workspace.run_attempt(task, service)
    pairs = (
        (
            first_snapshot.task_commitment,
            first_snapshot.delivery_commitment,
            first_snapshot.expected_signer,
        ),
        (
            second_snapshot.task_commitment,
            second_snapshot.delivery_commitment,
            second_snapshot.expected_signer,
        ),
    )

    artifacts = build_m9_artifacts(
        (first, second),
        pairs,
        LocalRevisionStore(tmp_path / "revisions"),
    )

    assert artifacts.rework_package is not None
    assert artifacts.comparison is not None
    assert artifacts.comparison.before.commitment_status is CommitmentStatus.VERIFIED
    assert artifacts.comparison.after.commitment_status is CommitmentStatus.VERIFIED
    assert len(artifacts.revisions) == 2
    rebuilt = build_m9_artifacts(
        (first, second), pairs, LocalRevisionStore(tmp_path / "revisions")
    )
    assert rebuilt.rework_package == artifacts.rework_package
    assert rebuilt.revisions == artifacts.revisions
    assert rebuilt.comparison == artifacts.comparison


def test_m8_adapter_distinguishes_missing_and_invalid_snapshots(tmp_path) -> None:
    candidate, workflow, service = _m5_components(tmp_path)
    task = workflow.confirm_task(candidate)
    workspace = M8WorkspaceWorkflow(
        workflow,
        M8CommitmentWorkflow(),
        M8ArtifactStore(tmp_path / "m8-artifacts.db"),
    )
    execution, snapshot = workspace.run_attempt(task, service)

    missing = M8ReceiptCommitmentVerifier(()).verify(execution.receipt, attempt=1)
    altered_delivery = snapshot.delivery_commitment.model_copy(
        update={"report_hash": "0x" + "0" * 64}
    )
    invalid = M8ReceiptCommitmentVerifier(
        (
            M8CommitmentBinding(
                task_commitment=snapshot.task_commitment,
                delivery_commitment=altered_delivery,
                submission=execution.submission,
                expected_signer=snapshot.expected_signer,
            ),
        )
    ).verify(execution.receipt, attempt=1)

    assert missing.status is CommitmentStatus.UNVERIFIED
    assert invalid.status is CommitmentStatus.INVALID
