"""Explicit offline fixture adapter for the M5 product demonstration."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from trust_receipt.agents.models import (
    ClaimExtraction,
    FollowUpAction,
    FollowUpAdvice,
    ResultExplanation,
    TaskSpecCandidate,
)
from trust_receipt.agents.ports import StructuredArtifact
from trust_receipt.models import VerificationPlan
from trust_receipt.models.enums import VerificationOutcome


class OfflineDemoStructuredOutputAdapter:
    """Deterministic, non-model adapter that is always disclosed as fixture-backed."""

    def __init__(self, task_candidate: TaskSpecCandidate) -> None:
        self._task_candidate = task_candidate

    def generate(
        self,
        *,
        schema: type[StructuredArtifact],
        system_prompt: str,
        payload: Mapping[str, Any],
    ) -> StructuredArtifact:
        del system_prompt
        builders = {
            TaskSpecCandidate: self._draft_task,
            ClaimExtraction: self._extract_claims,
            VerificationPlan: self._plan,
            FollowUpAdvice: self._follow_up,
            ResultExplanation: self._explanation,
        }
        try:
            raw = builders[schema](payload)
        except KeyError as error:
            raise TypeError(f"offline demo does not support schema {schema.__name__}") from error
        return schema.model_validate(raw)

    def _draft_task(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        if not str(payload.get("user_request", "")).strip():
            raise ValueError("user_request cannot be empty")
        return self._task_candidate.model_dump(mode="json")

    @staticmethod
    def _extract_claims(payload: Mapping[str, Any]) -> dict[str, Any]:
        report_id = str(payload["report_id"])
        report = json.loads(str(payload["report_text"]))
        return {
            "schema_version": "1.0",
            "report_id": report_id,
            "claims": [
                {
                    "claim_id": f"{report_id}:total",
                    "claim_type": "CLAIMED_TOTAL",
                    "value": report["claimed_total_base_units"],
                },
                {
                    "claim_id": f"{report_id}:count",
                    "claim_type": "CLAIMED_COUNT",
                    "value": report["claimed_count"],
                },
                {
                    "claim_id": f"{report_id}:transfers",
                    "claim_type": "TRANSFER_SET",
                    "value": report["transfers"],
                },
            ],
            "ambiguities": [],
            "clarification_questions": [],
            "source_summary": "Offline fixture adapter parsed the team-controlled JSON report.",
        }

    @staticmethod
    def _plan(payload: Mapping[str, Any]) -> dict[str, Any]:
        task = payload["confirmed_task"]
        contract = payload["required_operation_contract"]
        fields = {
            "queries": ("query_id", "query_type"),
            "filters": ("filter_id", "filter_type"),
            "aggregation_rules": ("aggregation_id", "aggregation_type"),
            "checks": ("check_id", "check_type"),
        }
        operations: dict[str, list[dict[str, Any]]] = {}
        for category, (id_field, type_field) in fields.items():
            operations[category] = [
                {
                    id_field: f"offline-{category}-{index}",
                    type_field: item["operation_type"],
                    "arguments": item["arguments"],
                }
                for index, item in enumerate(contract[category], start=1)
            ]
        return {
            "schema_version": "1.0",
            "plan_id": f"offline-plan-{task['task_id']}",
            "task_id": task["task_id"],
            "claims": payload["validated_claims"],
            **operations,
            "plan_version": "m5-offline-demo-1.0",
        }

    @staticmethod
    def _follow_up(payload: Mapping[str, Any]) -> dict[str, Any]:
        result = payload["verification_result"]
        outcome = VerificationOutcome(result["outcome"])
        refs = sorted({ref for finding in result["findings"] for ref in finding["evidence_refs"]})
        action = {
            VerificationOutcome.PASS: FollowUpAction.NO_ACTION,
            VerificationOutcome.FAIL: FollowUpAction.REQUEST_RESUBMISSION,
            VerificationOutcome.INCONCLUSIVE: FollowUpAction.REFRESH_REFERENCE_EVIDENCE,
        }[outcome]
        rationale = {
            VerificationOutcome.PASS: "All deterministic checks passed; no follow-up is required.",
            VerificationOutcome.FAIL: "Request one corrected submission for the confirmed findings.",
            VerificationOutcome.INCONCLUSIVE: "Refresh independent evidence before drawing a service conclusion.",
        }[outcome]
        return {
            "schema_version": "1.0",
            "outcome": outcome.value,
            "suggestions": [{"action": action.value, "rationale": rationale, "evidence_refs": refs}],
        }

    @staticmethod
    def _explanation(payload: Mapping[str, Any]) -> dict[str, Any]:
        result = payload["verification_result"]
        outcome = VerificationOutcome(result["outcome"])
        summary = {
            VerificationOutcome.PASS: "The submitted report matches the complete independent evidence.",
            VerificationOutcome.FAIL: "Confirmed deterministic differences require correction.",
            VerificationOutcome.INCONCLUSIVE: "Evidence is insufficient; this is not a service failure.",
        }[outcome]
        return {
            "schema_version": "1.0",
            "outcome": outcome.value,
            "calculated_total_base_units": result["calculated_total_base_units"],
            "calculated_count": result["calculated_count"],
            "summary": summary,
            "finding_explanations": [
                {
                    "finding_id": finding["finding_id"],
                    "explanation": finding["explanation"],
                    "evidence_refs": finding["evidence_refs"],
                }
                for finding in result["findings"]
            ],
        }
