from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest

from tests.contracts.samples import plan_data
from trust_receipt.models.enums import VerificationOutcome
from trust_receipt.models.plans import VerificationPlan
from trust_receipt.models.receipts import ServiceIdentity
from trust_receipt.orchestration import VerificationOrchestrator
from trust_receipt.receipts import (
    ReceiptIntegrityError,
    build_receipt,
    load_receipt,
    replay_receipt,
    save_receipt,
)
from trust_receipt.services import FaultMode, TeamControlledReportService
from trust_receipt.storage import SQLiteRepository
from trust_receipt.verification import ReferenceEvidence


class StaticEvidenceProvider:
    def __init__(self, evidence: ReferenceEvidence) -> None:
        self._evidence = evidence

    def fetch(self, task):
        return self._evidence


def test_two_attempts_create_distinct_append_only_receipts_replayable_in_new_process(
    tmp_path,
    hashed_task,
    eligible_service_records,
    reference_evidence,
    fixed_time,
    private_key_a,
) -> None:
    repository = SQLiteRepository(tmp_path / "receipts.db")
    run_ids = iter(("run-receipt-1", "run-receipt-2"))
    orchestrator = VerificationOrchestrator(
        repository=repository,
        evidence_provider=StaticEvidenceProvider(reference_evidence),
        clock=lambda: fixed_time,
        id_factory=lambda: next(run_ids),
    )
    service = TeamControlledReportService(
        service_id="service-a",
        private_key=private_key_a,
        records_provider=lambda task: eligible_service_records,
        fault_by_attempt={1: FaultMode.OMIT_LAST_TRANSFER},
        clock=lambda: fixed_time,
    )
    orchestrator.confirm_task(hashed_task)
    orchestrator.run_attempt(hashed_task.task_id, service)
    orchestrator.run_attempt(hashed_task.task_id, service)

    raw_plan = plan_data()
    raw_plan["task_id"] = hashed_task.task_id
    plan = VerificationPlan.model_validate(raw_plan)
    identity = ServiceIdentity(
        service_id=service.service_id,
        name="Team-controlled service A",
        identity_scheme="local-evm-signer",
        identity_reference=service.signer_address,
    )
    paths = []
    for attempt in (1, 2):
        stored = repository.get_attempt(hashed_task.task_id, attempt)
        receipt = build_receipt(
            receipt_id=f"receipt-{attempt}",
            task=hashed_task,
            submission=stored.submission,
            service_identity=identity,
            plan=plan,
            result=stored.verification_result,
            evidence=reference_evidence,
            created_at=fixed_time,
        )
        path = save_receipt(receipt, tmp_path / f"receipt-{attempt}.json")
        paths.append(path)
        loaded = load_receipt(path)
        assert replay_receipt(loaded).valid
        with pytest.raises(FileExistsError):
            save_receipt(receipt, path)

    first = load_receipt(paths[0])
    second = load_receipt(paths[1])
    assert first.verification_result.outcome is VerificationOutcome.FAIL
    assert second.verification_result.outcome is VerificationOutcome.PASS
    assert first.receipt_hash != second.receipt_hash
    assert first.submission_hash != second.submission_hash

    environment = os.environ.copy()
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    environment["PYTHONPATH"] = os.path.join(project_root, "src")
    completed = subprocess.run(
        [sys.executable, "-m", "trust_receipt.receipts.cli", str(paths[1])],
        cwd=project_root,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout)["valid"] is True

    tampered_payload = json.loads(paths[1].read_text(encoding="utf-8"))
    tampered_payload["receipt_id"] = "tampered-receipt"
    tampered_path = tmp_path / "tampered.json"
    tampered_path.write_text(json.dumps(tampered_payload), encoding="utf-8")
    with pytest.raises(ReceiptIntegrityError, match="receipt_hash"):
        load_receipt(tampered_path)
