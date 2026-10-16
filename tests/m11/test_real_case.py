from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from scripts.m11.evaluate_report import evaluate_report
from scripts.m11.preflight import PreflightError, load_case_bundle, load_task_spec, run_preflight
from trust_receipt.agents import OfflineDemoStructuredOutputAdapter, RestrictedAIService, TaskSpecCandidate
from trust_receipt.hashing import task_spec_hash
from trust_receipt.models import (
    EvidenceSource,
    FindingType,
    ServiceSubmission,
    SourceDescriptor,
    VerificationOutcome,
)
from trust_receipt.orchestration import M5Workflow, StaticEvidenceProvider
from trust_receipt.services.upload import UploadedReportService
from trust_receipt.storage.sqlite import SQLiteRepository
from trust_receipt.verification import ReferenceEvidence, ReferencePage, ReferenceStream, verify_submission

CASE_DIRECTORY = Path(__file__).resolve().parents[2] / "fixtures" / "m11"


class FakeProbe:
    def __init__(self, pages, *, latest_block=12_000_000) -> None:
        self.pages = pages
        self.latest = latest_block

    def latest_block(self):
        return self.latest

    def fetch_transfer_pages(self, **kwargs):
        assert kwargs == {
            "token_address": "0x7b79995e5f793A07Bc00c21412e50Ecae098E7f9",
            "from_block": 11855664,
            "to_block": 11855664,
            "page_size_blocks": 2_000,
        }
        return self.pages


def _submission(bundle, report, *, attempt):
    return ServiceSubmission(
        schema_version="1.0",
        submission_id=f"m11-upload-{attempt}",
        task_id=bundle.task.task_id,
        service_id="uploaded-report-intake",
        service_version="upload-intake-1.0",
        attempt=attempt,
        claimed_total_base_units=report.claimed_total_base_units,
        claimed_count=report.claimed_count,
        transfers=report.transfers,
        report_text="team-constructed strict JSON fixture",
        created_at=datetime(2026, 10, 7, 8, attempt, tzinfo=UTC),
        report_hash="0x" + f"{attempt}" * 64,
        signature=None,
    )


def _evidence(bundle, *, sufficient=True):
    descriptor = SourceDescriptor(
        source=EvidenceSource.RPC,
        source_id="rpc:11155111:11855664-11855664",
        retrieved_at=datetime(2026, 10, 7, 7, 10, 54, tzinfo=UTC),
        complete=True,
        details={"pages": 1, "records": 6},
    )
    return ReferenceEvidence(
        streams=(ReferenceStream(
            source=descriptor,
            pages=(ReferencePage(cursor=None, next_cursor=None, transfers=bundle.reference_transfers),),
        ),),
        evidence_sufficient=sufficient,
        insufficiency_reason=None if sufficient else "simulated read-only RPC outage",
    )


def test_strict_reports_and_inventory_match_the_frozen_uploaded_report_contract():
    bundle = load_case_bundle(CASE_DIRECTORY)

    assert bundle.manifest["disclosure"].startswith("Team-constructed reports")
    assert bundle.error_report.claimed_count == 0
    assert bundle.error_report.claimed_total_base_units == "0"
    assert bundle.corrected_report.claimed_count == 1
    assert bundle.corrected_report.claimed_total_base_units == "180674489737"
    assert len(bundle.reference_transfers) == 6
    assert all(record.source is EvidenceSource.RPC for record in bundle.reference_transfers)


def test_real_event_snapshot_deterministically_yields_fail_then_pass():
    bundle = load_case_bundle(CASE_DIRECTORY)
    evidence = _evidence(bundle)
    started = datetime(2026, 10, 7, 8, 10, tzinfo=UTC)
    finished = datetime(2026, 10, 7, 8, 10, 1, tzinfo=UTC)

    failed = verify_submission(
        bundle.task,
        _submission(bundle, bundle.error_report, attempt=1),
        evidence,
        run_id="m11-error-run",
        started_at=started,
        finished_at=finished,
    )
    passed = verify_submission(
        bundle.task,
        _submission(bundle, bundle.corrected_report, attempt=2),
        evidence,
        run_id="m11-corrected-run",
        started_at=started,
        finished_at=finished,
    )

    assert failed.outcome is VerificationOutcome.FAIL
    assert failed.calculated_total_base_units == "180674489737"
    assert failed.calculated_count == 1
    assert [finding.finding_type for finding in failed.findings] == [FindingType.MISSING_TRANSFER]
    assert failed.findings[0].evidence_refs == (
        "rpc:11155111:0x0442da2dc2aa4e4557e648fe3a6fad49c43f5e9db89b36e156f1a790d3b64b6f:128",
    )
    assert passed.outcome is VerificationOutcome.PASS
    assert passed.calculated_total_base_units == "180674489737"
    assert passed.calculated_count == 1
    assert passed.findings == ()


def test_read_only_preflight_requires_an_exact_live_inventory_match():
    bundle = load_case_bundle(CASE_DIRECTORY)
    result = run_preflight(
        "https://unused.invalid",
        case_directory=CASE_DIRECTORY,
        probe=FakeProbe((bundle.reference_transfers,)),
    )

    assert result["ok"] is True
    assert result["status"] == "COMPLETE"
    assert result["read_only"] is True
    assert result["raw_event_count"] == 6
    assert result["eligible_event_count"] == 1
    assert result["calculated_total_base_units"] == "180674489737"

    with pytest.raises(PreflightError, match="live RPC inventory differs"):
        run_preflight(
            "https://unused.invalid",
            case_directory=CASE_DIRECTORY,
            probe=FakeProbe((bundle.reference_transfers[:-1],)),
        )


def test_existing_upload_entry_runs_the_fixed_case_fail_then_pass(tmp_path):
    bundle = load_case_bundle(CASE_DIRECTORY)
    task = bundle.task
    candidate = TaskSpecCandidate(
        schema_version="1.0",
        candidate_id="candidate-m11-real-case",
        chain_id=task.chain_id,
        token_address=task.token_address,
        treasury_addresses=task.treasury_addresses,
        recipient_addresses=task.recipient_addresses,
        start_block=task.start_block,
        end_block=task.end_block,
        exclusion_rules=task.exclusion_rules,
        max_records=task.max_records,
        ambiguities=(),
        missing_fields=(),
        clarification_questions=(),
    )
    repository = SQLiteRepository(tmp_path / "m11.db")
    repository.add_task(task)
    workflow = M5Workflow(
        repository=repository,
        evidence_provider=StaticEvidenceProvider(_evidence(bundle)),
        ai_service=RestrictedAIService(OfflineDemoStructuredOutputAdapter(candidate)),
        receipt_directory=tmp_path / "receipts",
    )
    error_path = CASE_DIRECTORY / bundle.manifest["reports"]["error"]
    corrected_path = CASE_DIRECTORY / bundle.manifest["reports"]["corrected"]

    failed = workflow.run_attempt(
        task.task_id,
        UploadedReportService(error_path.read_bytes(), private_directory=tmp_path / "uploads"),
    )
    passed = workflow.run_attempt(
        task.task_id,
        UploadedReportService(corrected_path.read_bytes(), private_directory=tmp_path / "uploads"),
    )

    assert failed.result.outcome is VerificationOutcome.FAIL
    assert passed.result.outcome is VerificationOutcome.PASS
    assert failed.submission.report_text.encode() == error_path.read_bytes()
    assert passed.submission.report_text.encode() == corrected_path.read_bytes()
    assert failed.receipt_path is not None and failed.receipt_path.is_file()
    assert passed.receipt_path is not None and passed.receipt_path.is_file()
    assert len(repository.list_attempts(task.task_id)) == 2


def test_generic_evaluator_accepts_a_different_valid_task_and_report(tmp_path):
    bundle = load_case_bundle(CASE_DIRECTORY)
    alternate_reference = bundle.reference_transfers[0]
    unhashed_task = bundle.task.model_copy(update={
        "task_id": "m11-alternate-real-event",
        "treasury_addresses": (alternate_reference.from_address,),
        "recipient_addresses": (alternate_reference.to_address,),
        "spec_hash": "0x" + "0" * 64,
    })
    alternate_task = unhashed_task.model_copy(update={"spec_hash": task_spec_hash(unhashed_task)})
    task_path = tmp_path / "alternate-task.json"
    task_path.write_text(alternate_task.model_dump_json(indent=2), encoding="utf-8")
    report_path = tmp_path / "alternate-report.json"
    report_path.write_text(json.dumps({
        "schema_version": "1.0",
        "claimed_total_base_units": alternate_reference.amount_base_units,
        "claimed_count": 1,
        "transfers": [{**alternate_reference.model_dump(mode="json"), "source": "service"}],
    }, indent=2), encoding="utf-8")

    result = evaluate_report(
        rpc_url="https://unused.invalid",
        task_spec_path=task_path,
        report_path=report_path,
        evidence_provider=StaticEvidenceProvider(_evidence(bundle)),
    )

    assert load_task_spec(task_path) == alternate_task
    assert result["outcome"] == "PASS"
    assert result["calculated_total_base_units"] == "321794352786"
    assert result["calculated_count"] == 1
    assert result["findings"] == []


def test_generic_evaluator_preserves_inconclusive_for_incomplete_evidence():
    bundle = load_case_bundle(CASE_DIRECTORY)
    result = evaluate_report(
        rpc_url="https://unused.invalid",
        task_spec_path=CASE_DIRECTORY / bundle.manifest["task_spec"],
        report_path=CASE_DIRECTORY / bundle.manifest["reports"]["corrected"],
        evidence_provider=StaticEvidenceProvider(_evidence(bundle, sufficient=False)),
    )

    assert result["outcome"] == "INCONCLUSIVE"
    assert result["reference_complete"] is True
    assert result["evidence_sufficient"] is False
    assert "simulated read-only RPC outage" in result["inconclusive_reason"]
