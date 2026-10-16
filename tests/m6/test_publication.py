from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from eth_account import Account

from trust_receipt.agents import OfflineDemoStructuredOutputAdapter, RestrictedAIService
from trust_receipt.hashing import content_hash, receipt_hash
from trust_receipt.models import PublicationChainStatus
from trust_receipt.orchestration import (
    M5Workflow,
    M6Workflow,
    StaticEvidenceProvider,
    candidate_from_fixture,
    eligible_records,
    evidence_from_fixture,
    load_vertical_demo_fixture,
)
from trust_receipt.publishing import (
    LocalDirectoryPublisher,
    PublicationIntegrityError,
    publish_receipt,
    verify_public_receipt,
)
from trust_receipt.services import TeamControlledReportService
from trust_receipt.storage import SQLiteRepository

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _receipt(project_root, tmp_path):
    fixture = load_vertical_demo_fixture(project_root)
    candidate = candidate_from_fixture(fixture)
    repository = SQLiteRepository(tmp_path / "m6.db")
    workflow = M5Workflow(
        repository=repository,
        evidence_provider=StaticEvidenceProvider(evidence_from_fixture(fixture)),
        ai_service=RestrictedAIService(OfflineDemoStructuredOutputAdapter(candidate)),
        receipt_directory=tmp_path / "private",
    )
    task = workflow.confirm_task(candidate)
    service = TeamControlledReportService(
        service_id="service-a",
        private_key=Account.create().key.to_0x_hex(),
        records_provider=lambda _: eligible_records(fixture),
    )
    return workflow.run_attempt(task.task_id, service).receipt, repository


def test_public_receipt_is_redacted_published_verified_and_replayable(tmp_path):
    receipt, repository = _receipt(PROJECT_ROOT, tmp_path)
    publisher = LocalDirectoryPublisher(tmp_path / "public")

    published, artifact = publish_receipt(receipt, publisher)
    event = repository.append_publication(published)

    assert published.publication.authorized is True
    assert published.publication.chain_status is PublicationChainStatus.NOT_SUBMITTED
    assert published.publication.uri == artifact.uri
    assert event.sequence == 1
    payload = publisher.fetch(artifact.uri)
    assert content_hash(payload) == artifact.content_hash
    public_snapshot = verify_public_receipt(payload, artifact.content_hash)
    serialized = json.loads(payload)
    assert public_snapshot.receipt_id == receipt.receipt_id
    assert "report_text" not in json.dumps(serialized)
    assert "private_key" not in json.dumps(serialized).lower()

    public_path = next((tmp_path / "public").glob("*.json"))
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(PROJECT_ROOT / "src")
    completed = subprocess.run(
        [sys.executable, "-m", "trust_receipt.receipts.cli", str(public_path)],
        cwd=PROJECT_ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout)["valid"] is True


def test_download_hash_mismatch_is_rejected(tmp_path):
    receipt, _ = _receipt(PROJECT_ROOT, tmp_path)

    class CorruptingPublisher:
        def publish(self, payload: bytes, *, name: str) -> str:
            self.payload = payload
            return "memory://receipt"

        def fetch(self, uri: str) -> bytes:
            return self.payload + b"tampered"

    with pytest.raises(PublicationIntegrityError, match="content hash"):
        publish_receipt(receipt, CorruptingPublisher())


def test_workflow_requires_explicit_publication_authorization(tmp_path):
    receipt, repository = _receipt(PROJECT_ROOT, tmp_path)
    workflow = M6Workflow(repository)
    with pytest.raises(ValueError, match="explicit"):
        workflow.publish(
            receipt,
            LocalDirectoryPublisher(tmp_path / "public"),
            authorized=False,
        )
    assert repository.list_publications(receipt.receipt_id) == ()


def test_publication_history_is_append_only_and_terminal(tmp_path):
    receipt, repository = _receipt(PROJECT_ROOT, tmp_path)
    published, _ = publish_receipt(receipt, LocalDirectoryPublisher(tmp_path / "public"))
    repository.append_publication(published)
    submitted_publication = published.publication.model_copy(
        update={
            "chain_status": PublicationChainStatus.SUBMITTED,
            "chain_id": 11_155_111,
            "reviewer_address": "0x" + "11" * 20,
            "transaction_nonce": 7,
            "transaction_hash": "0x" + "22" * 32,
        }
    )
    draft = published.model_copy(
        update={"publication": submitted_publication, "receipt_hash": "0x" + "0" * 64}
    )
    submitted = draft.model_copy(update={"receipt_hash": receipt_hash(draft)})
    repository.append_publication(submitted)
    failed_publication = submitted.publication.model_copy(
        update={
            "chain_status": PublicationChainStatus.FAILED,
            "error_code": "TRANSACTION_REVERTED",
            "error_message": "transaction reverted",
        }
    )
    failed_draft = submitted.model_copy(
        update={"publication": failed_publication, "receipt_hash": "0x" + "0" * 64}
    )
    failed = failed_draft.model_copy(update={"receipt_hash": receipt_hash(failed_draft)})
    repository.append_publication(failed)

    assert [event.receipt.publication.chain_status for event in repository.list_publications(receipt.receipt_id)] == [
        PublicationChainStatus.NOT_SUBMITTED,
        PublicationChainStatus.SUBMITTED,
        PublicationChainStatus.FAILED,
    ]
    with pytest.raises(RuntimeError, match="invalid publication state transition"):
        repository.append_publication(submitted)

    recovered = M6Workflow(repository).recover_failed(failed, authorized=True)
    assert recovered.publication.chain_status is PublicationChainStatus.NOT_SUBMITTED
    assert recovered.publication.uri == published.publication.uri
    assert recovered.publication.transaction_hash is None
    assert len(repository.list_publications(receipt.receipt_id)) == 4
