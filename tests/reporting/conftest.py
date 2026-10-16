"""Build honest offline test artifacts through the existing verifier and receipt builder."""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from tests.contracts.samples import plan_data
from trust_receipt.hashing import submission_hash, task_spec_hash
from trust_receipt.models import FixtureCase, ServiceIdentity, VerificationPlan
from trust_receipt.orchestration import evidence_from_fixture
from trust_receipt.projections import project_fund_flow
from trust_receipt.receipts import build_receipt
from trust_receipt.reporting.models import ReportAttemptInput
from trust_receipt.verification import verify_submission

ROOT = Path(__file__).parents[2]


def report_input(case_name="missing-transfer-vertical-slice", *, attempt=1, transform=None):
    fixture = FixtureCase.model_validate_json((ROOT / "fixtures/m1/cases" / f"{case_name}.json").read_bytes())
    if transform:
        fixture = transform(fixture)
    task = fixture.task_spec.model_copy(update={"spec_hash": task_spec_hash(fixture.task_spec)})
    draft = fixture.submission.model_copy(update={"attempt": attempt})
    submission = draft.model_copy(update={"report_hash": submission_hash(draft)})
    evidence = evidence_from_fixture(fixture, sufficient=fixture.reference.evidence_sufficient)
    now = datetime(2026, 10, 7, tzinfo=UTC)
    result = verify_submission(task, submission, evidence, run_id="report-test", started_at=now, finished_at=now)
    raw_plan = plan_data()
    raw_plan["task_id"] = task.task_id
    receipt = build_receipt(
        receipt_id=f"report-test-{attempt}",
        task=task,
        submission=submission,
        service_identity=ServiceIdentity(
            service_id=submission.service_id,
            name="Offline test service",
            identity_scheme="local-upload-intake",
            identity_reference="local test identity",
        ),
        plan=VerificationPlan.model_validate(raw_plan),
        result=result,
        evidence=evidence,
        created_at=now,
    )
    return ReportAttemptInput(receipt, submission, project_fund_flow(task, submission, result, evidence))


@pytest.fixture
def failing_input():
    return report_input()
