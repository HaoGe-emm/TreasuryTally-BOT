"""Canonical JSON-compatible samples shared by M1 contract tests."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

ADDRESS_A = "0x1111111111111111111111111111111111111111"
ADDRESS_B = "0x2222222222222222222222222222222222222222"
ADDRESS_C = "0x3333333333333333333333333333333333333333"
HASH_A = "0x" + "aa" * 32
HASH_B = "0x" + "bb" * 32
HASH_C = "0x" + "cc" * 32
NOW = "2026-10-06T00:00:00Z"


def transfer_data(*, source: str = "service", amount: object = "120000") -> dict[str, Any]:
    return {
        "chain_id": 11_155_111,
        "token_address": ADDRESS_A,
        "transaction_hash": HASH_A,
        "log_index": 2,
        "block_number": 9_000_000,
        "block_hash": HASH_B,
        "from_address": ADDRESS_B,
        "to_address": ADDRESS_C,
        "amount_base_units": amount,
        "token_decimals": 6,
        "source": source,
    }


def task_data() -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "task_id": "task-1",
        "chain_id": 11_155_111,
        "token_address": ADDRESS_A,
        "treasury_addresses": [ADDRESS_B],
        "recipient_addresses": [ADDRESS_C],
        "start_block": 8_999_000,
        "end_block": 9_001_000,
        "exclusion_rules": [
            {
                "rule_id": "exclude-internal",
                "rule_type": "EXCLUDE_TREASURY_INTERNAL",
                "reason": "Exclude movement between confirmed treasury accounts.",
            }
        ],
        "max_records": 200,
        "confirmed_at": NOW,
        "spec_hash": HASH_A,
    }


def submission_data() -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "submission_id": "submission-1",
        "task_id": "task-1",
        "service_id": "service-a",
        "service_version": "1.0.0",
        "attempt": 1,
        "claimed_total_base_units": "120000",
        "claimed_count": 1,
        "transfers": [transfer_data()],
        "report_text": "One reported transfer.",
        "created_at": NOW,
        "report_hash": HASH_B,
        "signature": None,
    }


def plan_data() -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "plan_id": "plan-1",
        "task_id": "task-1",
        "claims": [{"claim_id": "claim-1", "claim_type": "CLAIMED_TOTAL", "value": "120000"}],
        "queries": [
            {"query_id": "query-1", "query_type": "FETCH_ERC20_TRANSFERS", "arguments": {}}
        ],
        "filters": [{"filter_id": "filter-1", "filter_type": "BLOCK_RANGE", "arguments": {}}],
        "aggregation_rules": [
            {"aggregation_id": "aggregation-1", "aggregation_type": "SUM_BASE_UNITS", "arguments": {}}
        ],
        "checks": [{"check_id": "check-1", "check_type": "COMPARE_TOTAL", "arguments": {}}],
        "plan_version": "1.0.0",
    }


def source_data() -> dict[str, Any]:
    return {
        "source": "rpc",
        "source_id": "sepolia-rpc",
        "retrieved_at": NOW,
        "complete": True,
        "details": {"page_count": 1},
    }


def result_data() -> dict[str, Any]:
    return {
        "run_id": "run-1",
        "task_id": "task-1",
        "submission_id": "submission-1",
        "verifier_version": "1.0.0",
        "reference_sources": [source_data()],
        "reference_complete": True,
        "evidence_sufficient": True,
        "calculated_total_base_units": "120000",
        "calculated_count": 1,
        "findings": [],
        "outcome": "PASS",
        "inconclusive_reason": None,
        "started_at": NOW,
        "finished_at": "2026-10-06T00:00:01Z",
    }


def receipt_data() -> dict[str, Any]:
    return {
        "receipt_version": "1.0",
        "receipt_id": "receipt-1",
        "task_spec": task_data(),
        "service_identity": {
            "service_id": "service-a",
            "name": "Fixture service A",
            "identity_scheme": "agent0",
            "identity_reference": "11155111:10691",
        },
        "submission_hash": HASH_B,
        "verification_plan": plan_data(),
        "verification_result": result_data(),
        "evidence_manifest": [
            {
                "evidence_id": "rpc-log-1",
                "source": "rpc",
                "content_hash": HASH_C,
                "uri": None,
                "event_keys": [f"11155111:{HASH_A}:2"],
            }
        ],
        "created_at": "2026-10-06T00:00:02Z",
        "receipt_hash": HASH_C,
        "publication": {
            "authorized": False,
            "uri": None,
            "content_hash": None,
            "transaction_hash": None,
            "chain_status": "NOT_SUBMITTED",
        },
    }


def fixture_case_data(fixture_id: str = "correct-report-01") -> dict[str, Any]:
    return {
        "fixture_version": "1.0",
        "fixture_id": fixture_id,
        "title": f"Correct report {fixture_id}",
        "tags": ["correct"],
        "task_spec": task_data(),
        "submission": submission_data(),
        "reference": {
            "sources": [source_data()],
            "reference_complete": True,
            "evidence_sufficient": True,
            "transfers": [transfer_data(source="rpc")],
            "insufficiency_reason": None,
        },
        "expected": {
            "outcome": "PASS",
            "calculated_total_base_units": "120000",
            "calculated_count": 1,
            "findings": [],
        },
        "human_review": {
            "summary": "The report and reference contain the same event.",
            "calculation": "120000 = 120000",
            "reviewer": "M1 contract test",
            "verified_at": NOW,
        },
    }


def fixture_manifest_data() -> dict[str, Any]:
    fixtures = []
    for index in range(1, 13):
        fixture_id = f"correct-report-{index:02d}"
        case = fixture_case_data(fixture_id)
        fixtures.append(
            {
                "fixture_id": fixture_id,
                "file": f"cases/{fixture_id}.json",
                "title": case["title"],
                "tags": deepcopy(case["tags"]),
                "expected_outcome": case["expected"]["outcome"],
            }
        )
    return {"fixture_version": "1.0", "fixtures": fixtures}


def task_candidate_data() -> dict[str, Any]:
    task = task_data()
    return {
        "schema_version": "1.0",
        "candidate_id": "candidate-1",
        "chain_id": task["chain_id"],
        "token_address": task["token_address"],
        "treasury_addresses": task["treasury_addresses"],
        "recipient_addresses": task["recipient_addresses"],
        "start_block": task["start_block"],
        "end_block": task["end_block"],
        "exclusion_rules": task["exclusion_rules"],
        "max_records": 200,
        "ambiguities": [],
        "missing_fields": [],
        "clarification_questions": [],
    }


def claim_extraction_data() -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "report_id": "report-1",
        "claims": [{"claim_id": "claim-1", "claim_type": "CLAIMED_TOTAL", "value": "120000"}],
        "ambiguities": [],
        "clarification_questions": [],
        "source_summary": "The report explicitly claims a total.",
    }


def follow_up_advice_data() -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "outcome": "PASS",
        "suggestions": [{"action": "NO_ACTION", "rationale": "No follow-up is needed.", "evidence_refs": []}],
    }


def result_explanation_data() -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "outcome": "PASS",
        "calculated_total_base_units": "120000",
        "calculated_count": 1,
        "summary": "The report matches the complete reference evidence.",
        "finding_explanations": [],
    }


def top_level_samples() -> dict[str, dict[str, Any]]:
    return {
        "task_spec.schema.json": task_data(),
        "transfer_record.schema.json": transfer_data(),
        "service_submission.schema.json": submission_data(),
        "verification_plan.schema.json": plan_data(),
        "verification_result.schema.json": result_data(),
        "receipt.schema.json": receipt_data(),
        "fixture_case.schema.json": fixture_case_data(),
        "fixture_manifest.schema.json": fixture_manifest_data(),
        "task_spec_candidate.schema.json": task_candidate_data(),
        "claim_extraction.schema.json": claim_extraction_data(),
        "follow_up_advice.schema.json": follow_up_advice_data(),
        "result_explanation.schema.json": result_explanation_data(),
    }
