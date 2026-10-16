from __future__ import annotations

import pytest
from pydantic import ValidationError

from trust_receipt.agents import AIValidationError
from trust_receipt.agents.validation import validate_verification_plan
from trust_receipt.models import VerificationPlan


def plan_data(task, claims):
    return {
        "schema_version": "1.0",
        "plan_id": "plan-1",
        "task_id": task.task_id,
        "claims": [claim.model_dump(mode="json") for claim in claims],
        "queries": [
            {
                "query_id": "query-transfers",
                "query_type": "FETCH_ERC20_TRANSFERS",
                "arguments": {
                    "chain_id": task.chain_id,
                    "token_address": task.token_address,
                    "start_block": task.start_block,
                    "end_block": task.end_block,
                    "max_records": 200,
                },
            }
        ],
        "filters": [
            {
                "filter_id": "filter-token",
                "filter_type": "TOKEN_ADDRESS",
                "arguments": {"token_address": task.token_address},
            },
            {
                "filter_id": "filter-range",
                "filter_type": "BLOCK_RANGE",
                "arguments": {"start_block": 100, "end_block": 200, "inclusive": True},
            },
            {
                "filter_id": "filter-direction",
                "filter_type": "TREASURY_DIRECTION",
                "arguments": {"treasury_addresses": list(task.treasury_addresses), "direction": "outbound"},
            },
            {
                "filter_id": "filter-recipients",
                "filter_type": "RECIPIENT_SET",
                "arguments": {"recipient_addresses": list(task.recipient_addresses)},
            },
            {
                "filter_id": "filter-internal",
                "filter_type": "EXCLUDE_INTERNAL_TRANSFER",
                "arguments": {"treasury_addresses": list(task.treasury_addresses)},
            },
        ],
        "aggregation_rules": [
            {"aggregation_id": "sum", "aggregation_type": "SUM_BASE_UNITS", "arguments": {}},
            {"aggregation_id": "count", "aggregation_type": "COUNT_TRANSFERS", "arguments": {}},
        ],
        "checks": [
            {"check_id": f"check-{name.lower()}", "check_type": name, "arguments": {}}
            for name in (
                "COMPARE_EVENT_SET",
                "COMPARE_TOTAL",
                "DETECT_DUPLICATES",
                "VALIDATE_SCOPE",
                "VALIDATE_TOKEN_DECIMALS",
            )
        ],
        "plan_version": "1.0.0",
    }


def test_complete_whitelisted_plan_is_bound_to_confirmed_task(confirmed_task, claim_extraction) -> None:
    plan = VerificationPlan.model_validate(plan_data(confirmed_task, claim_extraction.claims))
    assert validate_verification_plan(plan, task=confirmed_task, claims=claim_extraction.claims) is plan


def test_unknown_operation_is_rejected_before_execution(confirmed_task, claim_extraction) -> None:
    data = plan_data(confirmed_task, claim_extraction.claims)
    data["checks"][0]["check_type"] = "RUN_PYTHON"
    with pytest.raises(ValidationError):
        VerificationPlan.model_validate(data)


def test_model_cannot_change_task_bound_arguments(confirmed_task, claim_extraction) -> None:
    data = plan_data(confirmed_task, claim_extraction.claims)
    data["queries"][0]["arguments"]["end_block"] = 999
    plan = VerificationPlan.model_validate(data)
    with pytest.raises(AIValidationError, match="derived from the confirmed task"):
        validate_verification_plan(plan, task=confirmed_task, claims=claim_extraction.claims)


def test_model_cannot_drop_a_required_check(confirmed_task, claim_extraction) -> None:
    data = plan_data(confirmed_task, claim_extraction.claims)
    data["checks"].pop()
    plan = VerificationPlan.model_validate(data)
    with pytest.raises(AIValidationError, match="each approved operation exactly once"):
        validate_verification_plan(plan, task=confirmed_task, claims=claim_extraction.claims)
