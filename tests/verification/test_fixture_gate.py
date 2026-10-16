import pytest

from trust_receipt.models import FixtureCase

from .fixture_gate import assert_expected, run_case
from .test_engine import STARTED, evidence, reported, submission, task, transfer


def test_fixture_bridge_checks_exact_expected_amount_and_findings() -> None:
    record = transfer(1, "100")
    case = FixtureCase.model_validate({
        "fixture_version": "1.0",
        "fixture_id": "bridge-check",
        "title": "Synthetic bridge check",
        "tags": ["correct"],
        "task_spec": task(),
        "submission": submission((reported(record),), "100", 1),
        "reference": {
            "sources": [evidence((record,)).streams[0].source],
            "reference_complete": True,
            "evidence_sufficient": True,
            "transfers": [record],
            "insufficiency_reason": None,
        },
        "expected": {
            "outcome": "PASS",
            "calculated_total_base_units": "100",
            "calculated_count": 1,
            "findings": [],
        },
        "human_review": {
            "summary": "Synthetic test of the fixture bridge, not an M1 delivered fixture.",
            "calculation": "100 = 100",
            "reviewer": "test",
            "verified_at": STARTED,
        },
    })
    result = run_case(case)
    assert_expected(case, result)
    wrong_total = result.model_copy(update={"calculated_total_base_units": "101"})
    with pytest.raises(AssertionError):
        assert_expected(case, wrong_total)
    wrong_count = result.model_copy(update={"calculated_count": 2})
    with pytest.raises(AssertionError):
        assert_expected(case, wrong_count)
    missing_data = case.model_dump(mode="json")
    missing_data["submission"].update(transfers=[], claimed_total_base_units="0", claimed_count=0)
    missing_data["expected"].update(outcome="FAIL", findings=[{
        "finding_type": "MISSING_TRANSFER",
        "severity": "error",
        "status": "confirmed",
        "violated_rule": "service transfer set must include every eligible reference event",
        "event_keys": [list(record.event_key)],
    }])
    missing_case = FixtureCase.model_validate(missing_data)
    missing_result = run_case(missing_case)
    assert_expected(missing_case, missing_result)
    with pytest.raises(AssertionError):
        assert_expected(missing_case, missing_result.model_copy(update={"findings": ()}))
