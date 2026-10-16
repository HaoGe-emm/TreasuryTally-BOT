from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest
from eth_account import Account

from trust_receipt.agents import OfflineDemoStructuredOutputAdapter, RestrictedAIService
from trust_receipt.orchestration import (
    M5Workflow,
    StaticEvidenceProvider,
    candidate_from_fixture,
    eligible_records,
    evidence_from_fixture,
    load_vertical_demo_fixture,
)
from trust_receipt.services import FaultMode, TeamControlledReportService
from trust_receipt.storage import SQLiteRepository


@dataclass(frozen=True)
class TwoAttemptArtifacts:
    first_receipt: object
    first_submission: object
    second_receipt: object
    second_submission: object


@pytest.fixture
def two_attempts(tmp_path) -> TwoAttemptArtifacts:
    project_root = Path(__file__).resolve().parents[2]
    fixture = load_vertical_demo_fixture(project_root)
    candidate = candidate_from_fixture(fixture)
    repository = SQLiteRepository(tmp_path / "m9.db")
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
        fault_by_attempt={1: FaultMode.OMIT_LAST_TRANSFER},
    )
    first = workflow.run_attempt(task.task_id, service)
    second = workflow.run_attempt(task.task_id, service)
    return TwoAttemptArtifacts(
        first_receipt=first.receipt,
        first_submission=repository.get_attempt(task.task_id, 1).submission,
        second_receipt=second.receipt,
        second_submission=repository.get_attempt(task.task_id, 2).submission,
    )
