"""Optional AI failures cannot expose vendor text or alter deterministic receipts."""

import pytest
from pydantic import ValidationError

from trust_receipt.agents import (
    FollowUpAdvice,
    OfflineDemoStructuredOutputAdapter,
    RestrictedAIService,
    ResultExplanation,
)
from trust_receipt.models import VerificationOutcome
from trust_receipt.orchestration import M5Workflow, StaticEvidenceProvider, evidence_from_fixture
from trust_receipt.receipts import replay_receipt
from trust_receipt.reporting import build_business_report

SECRET = "private-model-input-DO-NOT-DISPLAY"
VENDOR = "provider-body-DO-NOT-DISPLAY"


class UnstringifiableError(RuntimeError):
    def __str__(self):
        raise AssertionError("Exception text must never be inspected")

    def __repr__(self):
        raise AssertionError("Exception repr must never be inspected")


@pytest.mark.parametrize("schema,code", [
    (ResultExplanation, "RESULT_EXPLANATION_UNAVAILABLE"),
    (FollowUpAdvice, "FOLLOW_UP_ADVICE_UNAVAILABLE"),
])
@pytest.mark.parametrize("failure", ["validation", "vendor", "unstringifiable"])
@pytest.mark.parametrize("sufficient", [True, False])
def test_optional_ai_failure_is_fixed_safe_code_and_keeps_receipt(
    tmp_path, m5_components, schema, code, failure, sufficient,
):
    fixture, candidate, repository, _, service = m5_components
    delegate = OfflineDemoStructuredOutputAdapter(candidate)
    calls = []

    class FailingAdapter:
        def generate(self, *, schema, system_prompt, payload):
            calls.append(schema)
            if schema is target:
                if failure == "validation":
                    # Genuine Pydantic error embeds the rejected private input.
                    try:
                        schema.model_validate({"private_input": SECRET})
                    except ValidationError as error:
                        assert SECRET in str(error)
                        raise
                if failure == "vendor":
                    raise RuntimeError(VENDOR)
                raise UnstringifiableError()
            return delegate.generate(schema=schema, system_prompt=system_prompt, payload=payload)

    target = schema
    workflow = M5Workflow(
        repository=repository,
        evidence_provider=StaticEvidenceProvider(evidence_from_fixture(fixture, sufficient=sufficient)),
        ai_service=RestrictedAIService(FailingAdapter()),
        receipt_directory=tmp_path / "safe-receipts",
    )
    task = workflow.confirm_task(candidate)
    execution = workflow.run_attempt(task.task_id, service)

    assert execution.ai_errors == (code,)
    assert calls.count(target) == 1
    assert len(calls) == 4
    assert getattr(execution, "explanation" if schema is ResultExplanation else "follow_up") is None
    assert getattr(execution, "follow_up" if schema is ResultExplanation else "explanation") is not None
    assert execution.result.outcome is (
        VerificationOutcome.FAIL if sufficient else VerificationOutcome.INCONCLUSIVE
    )
    assert execution.result.calculated_total_base_units == ("110000" if sufficient else None)
    assert replay_receipt(execution.receipt).valid
    assert len(repository.list_attempts(task.task_id)) == 1
    assert execution.receipt_path is not None
    original = execution.receipt_path.read_bytes()
    assert SECRET.encode() not in original and VENDOR.encode() not in original
    view = build_business_report(
        execution.receipt, execution.submission, fund_flow=execution.fund_flow, source_mode="fixture",
    )
    assert SECRET not in view.model_dump_json() and VENDOR not in view.model_dump_json()
    restored = workflow.restore_latest()
    assert restored is not None
    assert restored[1][0].receipt == execution.receipt
    assert execution.receipt_path.read_bytes() == original


def test_both_optional_artifacts_fail_without_blocking_second_attempt(tmp_path, m5_components):
    fixture, candidate, repository, _, service = m5_components
    delegate = OfflineDemoStructuredOutputAdapter(candidate)

    class FailingAdapter:
        def generate(self, *, schema, system_prompt, payload):
            if schema in (ResultExplanation, FollowUpAdvice):
                raise UnstringifiableError()
            return delegate.generate(schema=schema, system_prompt=system_prompt, payload=payload)

    workflow = M5Workflow(
        repository=repository,
        evidence_provider=StaticEvidenceProvider(evidence_from_fixture(fixture)),
        ai_service=RestrictedAIService(FailingAdapter()),
        receipt_directory=tmp_path / "safe-receipts",
    )
    task = workflow.confirm_task(candidate)
    first = workflow.run_attempt(task.task_id, service)
    original = first.receipt_path.read_bytes()
    second = workflow.run_attempt(task.task_id, service)
    assert [e.result.outcome for e in (first, second)] == [VerificationOutcome.FAIL, VerificationOutcome.PASS]
    assert first.ai_errors == second.ai_errors == (
        "RESULT_EXPLANATION_UNAVAILABLE", "FOLLOW_UP_ADVICE_UNAVAILABLE",
    )
    assert first.receipt_path.read_bytes() == original
    assert all(replay_receipt(e.receipt).valid for e in (first, second))
    assert len(repository.list_attempts(task.task_id)) == 2
