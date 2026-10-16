from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from trust_receipt.agents import OfflineDemoStructuredOutputAdapter, RestrictedAIService, TaskSpecCandidate
from trust_receipt.chain import RpcReferenceEvidenceProvider
from trust_receipt.chain.rpc import EvmRpcProbe
from trust_receipt.hashing import canonical_json_bytes, content_hash
from trust_receipt.integrations.config import M0Settings
from trust_receipt.models import EvidenceSource, VerificationOutcome
from trust_receipt.orchestration import M5Workflow
from trust_receipt.services.upload import UploadedReport, UploadedReportService
from trust_receipt.storage.sqlite import SQLiteRepository
from trust_receipt.verification.scope import scope_violation

pytestmark = pytest.mark.external
PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _require_rpc_configuration(settings: M0Settings) -> None:
    missing = settings.missing_for_rpc()
    if missing:
        pytest.skip(f"M13 live uploaded-report flow blocked by missing configuration: {', '.join(missing)}")


def _candidate_from_live_transfer(settings: M0Settings, transfer) -> TaskSpecCandidate:
    return TaskSpecCandidate(
        schema_version="1.0",
        candidate_id="candidate-m13-live-independent-input",
        chain_id=settings.chain_id,
        token_address=transfer.token_address,
        treasury_addresses=(transfer.from_address,),
        recipient_addresses=(transfer.to_address,),
        start_block=settings.test_from_block,
        end_block=settings.test_to_block,
        exclusion_rules=(),
        max_records=200,
        ambiguities=(),
        missing_fields=(),
        clarification_questions=(),
    )


def _workflow(tmp_path: Path, candidate: TaskSpecCandidate, evidence_provider, *, name: str) -> M5Workflow:
    return M5Workflow(
        repository=SQLiteRepository(tmp_path / f"{name}.db"),
        evidence_provider=evidence_provider,
        ai_service=RestrictedAIService(OfflineDemoStructuredOutputAdapter(candidate)),
        receipt_directory=tmp_path / f"{name}-receipts",
    )


def _uploaded_report(records) -> bytes:
    service_records = tuple(record.model_copy(update={"source": EvidenceSource.SERVICE}) for record in records)
    report = UploadedReport(
        schema_version="1.0",
        claimed_total_base_units=str(sum(int(record.amount_base_units) for record in service_records)),
        claimed_count=len(service_records),
        transfers=service_records,
    )
    return canonical_json_bytes(report)


def _replay_in_fresh_process(receipt_path: Path, expected_outcome: VerificationOutcome) -> None:
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(PROJECT_ROOT / "src")
    completed = subprocess.run(
        [sys.executable, "-m", "trust_receipt.receipts.cli", str(receipt_path)],
        cwd=PROJECT_ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    result = json.loads(completed.stdout)
    assert result["valid"] is True
    assert result["recorded_outcome"] == expected_outcome.value
    assert result["recomputed_outcome"] == expected_outcome.value


def test_real_rpc_independent_upload_change_and_inconclusive_replay(tmp_path):
    settings = M0Settings.load()
    _require_rpc_configuration(settings)
    probe = EvmRpcProbe(
        settings.rpc_url_value(),
        expected_chain_id=settings.chain_id,
        timeout_seconds=settings.rpc_timeout_seconds,
    )
    known = probe.probe_transfer(
        token_address=settings.test_token_address or "",
        from_block=settings.test_from_block or 0,
        to_block=settings.test_to_block or 0,
        expected_transaction_hash=settings.test_transfer_tx_hash or "",
    ).transfer
    candidate = _candidate_from_live_transfer(settings, known)
    live_evidence = RpcReferenceEvidenceProvider(
        settings.rpc_url_value(),
        expected_chain_id=settings.chain_id,
        timeout_seconds=settings.rpc_timeout_seconds,
        confirmations=settings.rpc_confirmations,
    )
    workflow = _workflow(tmp_path, candidate, live_evidence, name="live")
    task = workflow.confirm_task(candidate)
    evidence = live_evidence.fetch(task)
    records = tuple(
        record
        for stream in evidence.streams
        for page in stream.pages
        for record in page.transfers
        if scope_violation(task, record) is None
    )
    assert evidence.evidence_sufficient is True
    assert 1 <= len(records) <= 200

    changed_first = records[0].model_copy(
        update={"amount_base_units": str(int(records[0].amount_base_units) + 1)}
    )
    altered_payload = _uploaded_report((changed_first, *records[1:]))
    correct_payload = _uploaded_report(records)
    assert altered_payload != correct_payload

    altered = workflow.run_attempt(
        task.task_id,
        UploadedReportService(altered_payload, private_directory=tmp_path / "live-uploads"),
    )
    corrected = workflow.run_attempt(
        task.task_id,
        UploadedReportService(correct_payload, private_directory=tmp_path / "live-uploads"),
    )
    assert altered.result.outcome is VerificationOutcome.FAIL
    assert corrected.result.outcome is VerificationOutcome.PASS
    assert altered.receipt_path is not None
    assert corrected.receipt_path is not None
    _replay_in_fresh_process(altered.receipt_path, VerificationOutcome.FAIL)
    _replay_in_fresh_process(corrected.receipt_path, VerificationOutcome.PASS)

    # A local simulated authorization tests serialization only; nothing is published.
    from trust_receipt.m9 import build_public_bundle

    bundle = build_public_bundle((altered.receipt, corrected.receipt), authorized=True)
    bundle_payload = canonical_json_bytes(bundle) + b"\n"
    bundle_path = tmp_path / "simulated-public-history.json"
    bundle_path.write_bytes(bundle_payload)
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(PROJECT_ROOT / "src")
    empty_cwd = tmp_path / "independent-session"
    empty_cwd.mkdir()
    completed = subprocess.run(
        [
            sys.executable, str(PROJECT_ROOT / "scripts" / "m13" / "check_history.py"),
            str(bundle_path), "--expected-content-hash", content_hash(bundle_payload),
        ],
        cwd=empty_cwd, env=environment, check=False, capture_output=True, text=True,
    )
    assert completed.returncode == 0, completed.stderr + completed.stdout
    public_result = json.loads(completed.stdout)
    assert public_result["status"] == "VERIFIED"
    assert public_result["resolution"] == "FIXED"
    assert public_result["attempt"] == 2

    unavailable_evidence = RpcReferenceEvidenceProvider(
        "http://127.0.0.1:9",
        expected_chain_id=settings.chain_id,
        timeout_seconds=0.2,
        confirmations=settings.rpc_confirmations,
    )
    unavailable_workflow = _workflow(tmp_path, candidate, unavailable_evidence, name="unavailable")
    unavailable_task = unavailable_workflow.confirm_task(candidate)
    inconclusive = unavailable_workflow.run_attempt(
        unavailable_task.task_id,
        UploadedReportService(correct_payload, private_directory=tmp_path / "unavailable-uploads"),
    )
    assert inconclusive.result.outcome is VerificationOutcome.INCONCLUSIVE
    assert inconclusive.result.inconclusive_reason
    assert inconclusive.receipt_path is not None
    _replay_in_fresh_process(inconclusive.receipt_path, VerificationOutcome.INCONCLUSIVE)
