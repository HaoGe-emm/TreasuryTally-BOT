"""Deterministic gates applied after every untrusted model response."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from typing import Any

from trust_receipt.agents.models import (
    ClaimExtraction,
    FollowUpAdvice,
    ResultExplanation,
    TaskSpecCandidate,
)
from trust_receipt.hashing import task_spec_hash
from trust_receipt.models import (
    AggregationRuleType,
    CheckType,
    Claim,
    ExclusionRuleType,
    FilterType,
    QueryType,
    TaskSpec,
    VerificationPlan,
    VerificationResult,
)

MVP_CHAIN_ID = 11_155_111


class AIValidationError(ValueError):
    """Raised when a model-produced artifact crosses a deterministic boundary."""


def confirm_task_candidate(
    candidate: TaskSpecCandidate,
    *,
    task_id: str,
    confirmed_at: datetime,
) -> TaskSpec:
    """Create and hash a confirmed task only after every user-controlled field is resolved."""
    if not candidate.ready_for_confirmation:
        raise AIValidationError("task candidate still has missing or ambiguous fields")
    if candidate.chain_id != MVP_CHAIN_ID:
        raise AIValidationError(f"MVP only supports chain_id={MVP_CHAIN_ID}")
    payload = {
        "schema_version": "1.0",
        "task_id": task_id,
        "chain_id": candidate.chain_id,
        "token_address": candidate.token_address,
        "treasury_addresses": candidate.treasury_addresses,
        "recipient_addresses": candidate.recipient_addresses,
        "start_block": candidate.start_block,
        "end_block": candidate.end_block,
        "exclusion_rules": candidate.exclusion_rules,
        "max_records": 200,
        "confirmed_at": confirmed_at,
        "spec_hash": "0x" + "0" * 64,
    }
    task = TaskSpec.model_validate(payload)
    return task.model_copy(update={"spec_hash": task_spec_hash(task)})


def validate_claim_extraction(extraction: ClaimExtraction) -> ClaimExtraction:
    if extraction.ambiguities:
        raise AIValidationError("ambiguous claims must be clarified before plan generation")
    if not extraction.claims:
        raise AIValidationError("at least one validated claim is required")
    return extraction


def validate_verification_plan(
    plan: VerificationPlan,
    *,
    task: TaskSpec,
    claims: tuple[Claim, ...],
) -> VerificationPlan:
    """Require the exact executable whitelist and bind every argument to confirmed task data."""
    if plan.task_id != task.task_id:
        raise AIValidationError("verification plan task_id does not match the confirmed task")
    if tuple(item.model_dump(mode="json") for item in plan.claims) != tuple(
        item.model_dump(mode="json") for item in claims
    ):
        raise AIValidationError("verification plan claims do not match validated extracted claims")

    expected_operations = _expected_operation_arguments(task)
    _validate_operations(
        plan.queries,
        type_attr="query_type",
        id_attr="query_id",
        expected=expected_operations["queries"],
        label="queries",
    )
    _validate_operations(
        plan.filters,
        type_attr="filter_type",
        id_attr="filter_id",
        expected=expected_operations["filters"],
        label="filters",
    )
    _validate_operations(
        plan.aggregation_rules,
        type_attr="aggregation_type",
        id_attr="aggregation_id",
        expected=expected_operations["aggregation_rules"],
        label="aggregation_rules",
    )
    _validate_operations(
        plan.checks,
        type_attr="check_type",
        id_attr="check_id",
        expected=expected_operations["checks"],
        label="checks",
    )
    return plan


def verification_plan_contract(task: TaskSpec) -> dict[str, list[dict[str, Any]]]:
    """Return the exact operation contract that a model must reproduce."""
    expected = _expected_operation_arguments(task)
    return {
        category: [
            {"operation_type": operation_type.value, "arguments": arguments}
            for operation_type, arguments in operations.items()
        ]
        for category, operations in expected.items()
    }


def validate_follow_up(advice: FollowUpAdvice, result: VerificationResult) -> FollowUpAdvice:
    if advice.outcome is not result.outcome:
        raise AIValidationError("follow-up outcome does not match deterministic verification result")
    known_refs = {ref for finding in result.findings for ref in finding.evidence_refs}
    supplied_refs = {ref for suggestion in advice.suggestions for ref in suggestion.evidence_refs}
    unknown = supplied_refs - known_refs
    if unknown:
        raise AIValidationError(f"follow-up contains unknown evidence refs: {sorted(unknown)!r}")
    return advice


def validate_result_explanation(
    explanation: ResultExplanation,
    result: VerificationResult,
) -> ResultExplanation:
    if explanation.outcome is not result.outcome:
        raise AIValidationError("explanation outcome does not match deterministic verification result")
    if explanation.calculated_total_base_units != result.calculated_total_base_units:
        raise AIValidationError("explanation cannot change the deterministic calculated total")
    if explanation.calculated_count != result.calculated_count:
        raise AIValidationError("explanation cannot change the deterministic calculated count")
    expected = {finding.finding_id: set(finding.evidence_refs) for finding in result.findings}
    actual = {item.finding_id: set(item.evidence_refs) for item in explanation.finding_explanations}
    if len(actual) != len(explanation.finding_explanations) or actual != expected:
        raise AIValidationError("explanation must cover exactly the deterministic findings and evidence refs")
    return explanation


def _validate_operations(
    operations: Iterable[Any],
    *,
    type_attr: str,
    id_attr: str,
    expected: dict[Any, dict[str, Any]],
    label: str,
) -> None:
    operations = tuple(operations)
    operation_ids = [getattr(item, id_attr) for item in operations]
    if len(operation_ids) != len(set(operation_ids)):
        raise AIValidationError(f"{label} operation IDs must be unique")
    actual_types = [getattr(item, type_attr) for item in operations]
    if len(actual_types) != len(set(actual_types)) or set(actual_types) != set(expected):
        raise AIValidationError(f"{label} must contain each approved operation exactly once")
    for operation in operations:
        operation_type = getattr(operation, type_attr)
        if operation.arguments != expected[operation_type]:
            raise AIValidationError(
                f"{label} arguments for {operation_type.value} must be derived from the confirmed task"
            )


def _expected_operation_arguments(task: TaskSpec) -> dict[str, dict[Any, dict[str, Any]]]:
    filters: dict[Any, dict[str, Any]] = {
        FilterType.TOKEN_ADDRESS: {"token_address": task.token_address},
        FilterType.BLOCK_RANGE: {
            "start_block": task.start_block,
            "end_block": task.end_block,
            "inclusive": True,
        },
        FilterType.TREASURY_DIRECTION: {
            "treasury_addresses": list(task.treasury_addresses),
            "direction": "outbound",
        },
        FilterType.RECIPIENT_SET: {"recipient_addresses": list(task.recipient_addresses)},
    }
    if any(rule.rule_type is ExclusionRuleType.EXCLUDE_TREASURY_INTERNAL for rule in task.exclusion_rules):
        filters[FilterType.EXCLUDE_INTERNAL_TRANSFER] = {
            "treasury_addresses": list(task.treasury_addresses)
        }
    return {
        "queries": {
            QueryType.FETCH_ERC20_TRANSFERS: {
                "chain_id": task.chain_id,
                "token_address": task.token_address,
                "start_block": task.start_block,
                "end_block": task.end_block,
                "max_records": task.max_records,
            }
        },
        "filters": filters,
        "aggregation_rules": {
            AggregationRuleType.SUM_BASE_UNITS: {},
            AggregationRuleType.COUNT_TRANSFERS: {},
        },
        "checks": {check: {} for check in CheckType},
    }
