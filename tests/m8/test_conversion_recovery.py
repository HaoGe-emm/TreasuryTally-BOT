"""Conversion provenance stays private; old signature/replay recovery is preserved."""

import csv
import io
import json

import pytest

from trust_receipt.agents import OfflineDemoStructuredOutputAdapter, RestrictedAIService
from trust_receipt.hashing import canonical_json_bytes, content_hash
from trust_receipt.m9 import build_public_bundle
from trust_receipt.models import VerificationOutcome
from trust_receipt.orchestration import M5Workflow
from trust_receipt.orchestration.m8 import M8CommitmentWorkflow
from trust_receipt.orchestration.m8_workspace import M8WorkspaceWorkflow
from trust_receipt.services.conversion_storage import persist_confirmed_conversion
from trust_receipt.services.report_conversion import convert_report_table, read_report_table
from trust_receipt.services.upload import UploadedReportService
from trust_receipt.storage.m8 import M8ArtifactStore
from trust_receipt.storage.sqlite import SQLiteRepository


def test_confirmed_conversion_cold_recovers_without_source_leakage(tmp_path, m5_components):
    fixture, candidate, repository, workflow, _ = m5_components
    records = [record.model_dump(mode="json") for record in fixture.submission.transfers]
    headers = [*records[0], "claimed_total_base_units", "claimed_count", "private_note"]
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=headers)
    writer.writeheader()
    for record in records:
        writer.writerow({
            **record, "claimed_total_base_units": fixture.submission.claimed_total_base_units,
            "claimed_count": fixture.submission.claimed_count, "private_note": "PRIVATE-CONVERSION-NOTE",
        })
    original = buffer.getvalue().encode("utf-8")
    converted = convert_report_table(read_report_table(original, "PRIVATE-ORIGINAL-FILENAME.csv"))
    assert converted.ready
    private = tmp_path / "uploads"
    normalized = persist_confirmed_conversion(original, converted, private, confirmed=True)
    # Adoption alone does not confirm a task or create an attempt/signature.
    assert not repository.list_tasks()
    service = UploadedReportService(normalized, private_directory=private)
    task = workflow.confirm_task(candidate)
    workspace = M8WorkspaceWorkflow(workflow, M8CommitmentWorkflow(), M8ArtifactStore(tmp_path / "m8.db"))
    first, snapshot = workspace.run_attempt(task, service)
    assert first.result.outcome is VerificationOutcome.FAIL
    assert first.submission.report_text.encode() == normalized
    assert first.submission.claimed_total_base_units == "120000"
    assert first.submission.claimed_count == 2
    assert first.receipt.service_identity.identity_scheme == "local-upload-intake"
    assert workspace.get_attempt_status(task.task_id).next_attempt == 2

    class NoNewEvidence:
        def fetch(self, _task):
            raise AssertionError("Recovery must use saved evidence, not fetch again")

    restarted = M5Workflow(
        repository=SQLiteRepository(tmp_path / "m8.db"), evidence_provider=NoNewEvidence(),
        ai_service=RestrictedAIService(OfflineDemoStructuredOutputAdapter(candidate)),
        receipt_directory=tmp_path / "receipts",
    )
    recovered = M8WorkspaceWorkflow(restarted, M8CommitmentWorkflow(), M8ArtifactStore(tmp_path / "m8.db"))
    recovered_task, attempts, snapshots = recovered.restore_latest()
    assert recovered_task == task and snapshots == (snapshot,)
    assert attempts[0].receipt == first.receipt
    assert attempts[0].evidence == first.evidence
    assert attempts[0].fund_flow == first.fund_flow
    assert attempts[0].submission.report_text.encode() == normalized
    assert recovered.get_attempt_status(task.task_id).next_attempt == 2
    manifest = json.loads(next((private / "conversion-provenance").iterdir()).read_bytes())
    assert manifest["original_hash"] == content_hash(original)
    assert manifest["normalized_hash"] == content_hash(normalized)
    assert manifest["original_author_verified"] is False
    assert next((private / "conversion-originals").iterdir()).read_bytes() == original
    with pytest.raises(ValueError, match="authorization"):
        build_public_bundle((first.receipt,), authorized=False)
    # Synthetic export authorization exercises serialization only: no publish/write port.
    public = canonical_json_bytes(build_public_bundle((first.receipt,), authorized=True))
    for marker in (b"PRIVATE-CONVERSION-NOTE", b"PRIVATE-ORIGINAL-FILENAME", b"conversion-provenance", b"report_text"):
        assert marker not in public
