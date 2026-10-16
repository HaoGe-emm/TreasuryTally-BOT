"""Deterministic, credential-free MVP demonstration workflow."""

from __future__ import annotations

from pathlib import Path

from eth_account import Account

from trust_receipt.agents import OfflineDemoStructuredOutputAdapter, RestrictedAIService
from trust_receipt.models.enums import VerificationOutcome
from trust_receipt.orchestration.m5 import (
    M5Workflow,
    StaticEvidenceProvider,
    candidate_from_fixture,
    eligible_records,
    evidence_from_fixture,
    load_vertical_demo_fixture,
)
from trust_receipt.receipts import replay_receipt
from trust_receipt.services import FaultMode, TeamControlledReportService
from trust_receipt.storage.sqlite import SQLiteRepository


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(f"MVP demo acceptance failed: {message}")


def run_offline_mvp_demo(project_root: Path, output_directory: Path) -> dict[str, object]:
    """Run FAIL -> switch service -> PASS, persist both attempts, and replay both receipts."""
    output_directory.mkdir(parents=True, exist_ok=True)
    if any(output_directory.iterdir()):
        raise ValueError("demo output directory must be empty")

    fixture = load_vertical_demo_fixture(project_root)
    candidate = candidate_from_fixture(fixture)
    repository = SQLiteRepository(output_directory / "demo.db")
    receipt_directory = output_directory / "receipts"
    ai_service = RestrictedAIService(OfflineDemoStructuredOutputAdapter(candidate))
    workflow = M5Workflow(
        repository=repository,
        evidence_provider=StaticEvidenceProvider(evidence_from_fixture(fixture)),
        ai_service=ai_service,
        receipt_directory=receipt_directory,
    )
    records = eligible_records(fixture)
    service_a = TeamControlledReportService(
        service_id="service-a",
        private_key=Account.create().key.to_0x_hex(),
        records_provider=lambda task: records,
        fault_by_attempt={1: FaultMode.OMIT_LAST_TRANSFER},
    )
    service_b = TeamControlledReportService(
        service_id="service-b",
        private_key=Account.create().key.to_0x_hex(),
        records_provider=lambda task: records,
    )

    task = workflow.confirm_task(candidate)
    first = workflow.run_attempt(task.task_id, service_a)
    second = workflow.run_attempt(task.task_id, service_b)
    first_replay = replay_receipt(first.receipt)
    second_replay = replay_receipt(second.receipt)
    restored_workflow = M5Workflow(
        repository=SQLiteRepository(output_directory / "demo.db"),
        evidence_provider=StaticEvidenceProvider(evidence_from_fixture(fixture)),
        ai_service=RestrictedAIService(OfflineDemoStructuredOutputAdapter(candidate)),
        receipt_directory=receipt_directory,
    )
    restored = restored_workflow.restore_latest()

    _require(first.result.outcome is VerificationOutcome.FAIL, "attempt 1 must fail")
    _require(second.result.outcome is VerificationOutcome.PASS, "attempt 2 must pass")
    _require(first_replay.valid and second_replay.valid, "both receipts must replay")
    _require(restored is not None, "persisted task must restore")
    _, restored_executions = restored
    restored_outcomes = [execution.result.outcome.value for execution in restored_executions]
    _require(restored_outcomes == ["FAIL", "PASS"], "restored outcomes must preserve both attempts")
    attempts = repository.list_attempts(task.task_id)
    _require(
        [attempt.submission.service_id for attempt in attempts] == ["service-a", "service-b"],
        "service switch history must remain append-only",
    )
    _require(
        second.result.calculated_total_base_units == "110000",
        "deterministic total must equal 110000 base units",
    )

    return {
        "valid": True,
        "mode": "offline-fixture",
        "fixture_id": fixture.fixture_id,
        "calculation": fixture.human_review.calculation,
        "task_id": task.task_id,
        "attempts": [
            {
                "attempt": attempt.submission.attempt,
                "service_id": attempt.submission.service_id,
                "outcome": attempt.verification_result.outcome.value,
            }
            for attempt in attempts
            if attempt.verification_result is not None
        ],
        "receipt_replays": [first_replay.valid, second_replay.valid],
        "restored_outcomes": restored_outcomes,
        "publication_mode": "not-executed",
        "output_directory": str(output_directory.resolve()),
    }
