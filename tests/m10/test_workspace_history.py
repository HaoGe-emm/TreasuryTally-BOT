from pathlib import Path

import pytest
from eth_account import Account

from trust_receipt.agents import OfflineDemoStructuredOutputAdapter, RestrictedAIService
from trust_receipt.history import compare_services
from trust_receipt.history.m9_adapter import VerifiedM9RevisionAdapter
from trust_receipt.m9 import LocalRevisionStore
from trust_receipt.m9.revisions import build_receipt_revision
from trust_receipt.models import PublicationChainStatus
from trust_receipt.orchestration import (
    M5Workflow,
    StaticEvidenceProvider,
    candidate_from_fixture,
    eligible_records,
    evidence_from_fixture,
    load_vertical_demo_fixture,
)
from trust_receipt.orchestration.m10 import TASK_TYPE, M10Workflow
from trust_receipt.publishing import authorize_public_receipt
from trust_receipt.reputation.public_feedback import _rehash
from trust_receipt.services import FaultMode, TeamControlledReportService
from trust_receipt.storage import SQLiteRepository


def setup_workspace(tmp_path, *, sufficient=True):
    fixture = load_vertical_demo_fixture(Path(__file__).parents[2])
    candidate = candidate_from_fixture(fixture)
    repository = SQLiteRepository(tmp_path / "history.db")
    directory = tmp_path / "receipts"
    store = LocalRevisionStore(tmp_path / "revisions")
    workflow = M5Workflow(
        repository=repository,
        evidence_provider=StaticEvidenceProvider(evidence_from_fixture(fixture, sufficient=sufficient)),
        ai_service=RestrictedAIService(OfflineDemoStructuredOutputAdapter(candidate)),
        receipt_directory=directory,
    )
    services = {
        name: TeamControlledReportService(
            service_id=name, private_key=Account.create().key.to_0x_hex(),
            records_provider=lambda _: eligible_records(fixture),
            fault_by_attempt={1: FaultMode.OMIT_LAST_TRANSFER} if name == "service-a" else {},
        )
        for name in ("service-a", "service-b")
    }
    return workflow, candidate, services, repository, store, M10Workflow(repository, directory, store)


def test_empty_history_and_two_candidates_have_no_implied_success(tmp_path):
    *_, history = setup_workspace(tmp_path)
    snapshot = history.read_history()
    comparison = compare_services(snapshot.histories, task_type=TASK_TYPE, service_ids=("service-a", "service-b"))
    assert snapshot.issues == ()
    assert all(service.verified_task_count == 0 for service in comparison.services)
    assert all(service.latest_delivery_at is None for service in comparison.services)


@pytest.mark.parametrize("switch_service", [False, True])
def test_actual_revision_chain_preserves_each_service_identity(tmp_path, switch_service):
    workflow, candidate, services, _, store, history = setup_workspace(tmp_path)
    task = workflow.confirm_task(candidate)
    first = workflow.run_attempt(task.task_id, services["service-a"])
    second = workflow.run_attempt(task.task_id, services["service-b" if switch_service else "service-a"])
    parent = build_receipt_revision(first.receipt, attempt=1)
    child = build_receipt_revision(second.receipt, attempt=2, parent=parent)
    store.append(parent)
    store.append(child)

    snapshot = history.read_history()
    by_service = {item.service_id: item for item in snapshot.histories}
    assert snapshot.issues == ()
    assert by_service["service-b" if switch_service else "service-a"].fixed_pass_count == 1
    assert by_service["service-a"].fail_count == (1 if switch_service else 0)
    assert by_service["service-a"].fixed_pass_count == (0 if switch_service else 1)


def test_missing_actual_parent_does_not_create_positive_or_negative_history(tmp_path):
    workflow, candidate, services, _, store, history = setup_workspace(tmp_path)
    task = workflow.confirm_task(candidate)
    first = workflow.run_attempt(task.task_id, services["service-a"])
    second = workflow.run_attempt(task.task_id, services["service-b"])
    parent = build_receipt_revision(first.receipt, attempt=1)
    child = build_receipt_revision(second.receipt, attempt=2, parent=parent)
    store.append(parent)
    store.append(child)
    first.receipt_path.unlink()

    snapshot = history.read_history()
    assert snapshot.histories == ()
    assert "INCONCLUSIVE" in snapshot.issues[0]
    with pytest.raises(ValueError, match="verified receipt"):
        VerifiedM9RevisionAdapter((second.receipt,), (parent, child))


def test_revision_adapter_rejects_fake_identity_even_with_valid_revision_hash(tmp_path):
    from trust_receipt.m9.revisions import receipt_revision_hash

    workflow, candidate, services, _, _, _ = setup_workspace(tmp_path)
    task = workflow.confirm_task(candidate)
    first = workflow.run_attempt(task.task_id, services["service-a"])
    parent = build_receipt_revision(first.receipt, attempt=1)
    draft = parent.model_copy(update={"service_id": "service-b"})
    forged = draft.model_copy(update={"revision_hash": receipt_revision_hash(draft)})
    with pytest.raises(ValueError, match="actual receipt"):
        VerifiedM9RevisionAdapter((first.receipt,), (forged,))


def test_m6_publication_snapshots_never_duplicate_attempt_history(tmp_path):
    workflow, candidate, services, repository, _, history = setup_workspace(tmp_path)
    task = workflow.confirm_task(candidate)
    execution = workflow.run_attempt(task.task_id, services["service-b"])
    public = authorize_public_receipt(execution.receipt)
    public = _rehash(public, uri="https://example.invalid/receipt.json", content_hash="0x" + "ab" * 32)
    repository.append_publication(public)
    failed = _rehash(public, chain_status=PublicationChainStatus.FAILED, error_code="TEST_FAILURE")
    repository.append_publication(failed)

    snapshot = history.read_history()
    assert snapshot.histories[0].verifiable_receipt_count == 1
    assert snapshot.receipts[0].receipt_hash == execution.receipt.receipt_hash
    assert snapshot.receipts[0].publication.uri is None


def test_evidence_shortfall_is_neutral_and_legacy_history_rebuilds_without_writes(tmp_path):
    workflow, candidate, services, _, store, history = setup_workspace(tmp_path, sufficient=False)
    task = workflow.confirm_task(candidate)
    workflow.run_attempt(task.task_id, services["service-a"])
    snapshot = history.read_history()
    assert snapshot.histories[0].inconclusive_count == 1
    assert snapshot.histories[0].fail_count == 0
    assert store.list(task.task_id) == ()
