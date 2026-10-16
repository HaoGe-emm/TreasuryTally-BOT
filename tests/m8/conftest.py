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
from trust_receipt.storage.sqlite import SQLiteRepository


@pytest.fixture
def m5_components(tmp_path):
    fixture = load_vertical_demo_fixture(Path(__file__).parents[2])
    candidate = candidate_from_fixture(fixture)
    repository = SQLiteRepository(tmp_path / "m8.db")
    workflow = M5Workflow(
        repository=repository,
        evidence_provider=StaticEvidenceProvider(evidence_from_fixture(fixture)),
        ai_service=RestrictedAIService(OfflineDemoStructuredOutputAdapter(candidate)),
        receipt_directory=tmp_path / "receipts",
    )
    records = eligible_records(fixture)
    service = TeamControlledReportService(
        service_id="service-a",
        private_key=Account.create().key.to_0x_hex(),
        records_provider=lambda task: records,
        fault_by_attempt={1: FaultMode.OMIT_LAST_TRANSFER},
    )
    return fixture, candidate, repository, workflow, service
