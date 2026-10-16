"""Use-case service that gates all model output before the rest of the application sees it."""

from __future__ import annotations

from datetime import datetime

from trust_receipt.agents.models import (
    ClaimExtraction,
    FollowUpAdvice,
    ResultExplanation,
    TaskSpecCandidate,
)
from trust_receipt.agents.ports import StructuredOutputPort
from trust_receipt.agents.prompts import (
    CLAIM_EXTRACTION_PROMPT,
    EXPLANATION_PROMPT,
    FOLLOW_UP_PROMPT,
    PLAN_PROMPT,
    TASK_CANDIDATE_PROMPT,
)
from trust_receipt.agents.validation import (
    confirm_task_candidate,
    validate_claim_extraction,
    validate_follow_up,
    validate_result_explanation,
    validate_verification_plan,
    verification_plan_contract,
)
from trust_receipt.models import TaskSpec, VerificationPlan, VerificationResult


class RestrictedAIService:
    """AI orchestration with no repository, shell, filesystem, publication, or chain-write capability."""

    def __init__(self, model: StructuredOutputPort) -> None:
        self._model = model

    def draft_task(self, user_request: str) -> TaskSpecCandidate:
        return self._model.generate(
            schema=TaskSpecCandidate,
            system_prompt=TASK_CANDIDATE_PROMPT,
            payload={"user_request": user_request},
        )

    def confirm_task(
        self,
        candidate: TaskSpecCandidate,
        *,
        task_id: str,
        confirmed_at: datetime,
    ) -> TaskSpec:
        return confirm_task_candidate(candidate, task_id=task_id, confirmed_at=confirmed_at)

    def extract_claims(self, *, report_id: str, report_text: str) -> ClaimExtraction:
        extraction = self._model.generate(
            schema=ClaimExtraction,
            system_prompt=CLAIM_EXTRACTION_PROMPT,
            payload={"report_id": report_id, "report_text": report_text},
        )
        if extraction.report_id != report_id:
            raise ValueError("claim extraction report_id does not match the requested report")
        return extraction

    def propose_plan(self, task: TaskSpec, extraction: ClaimExtraction) -> VerificationPlan:
        extraction = validate_claim_extraction(extraction)
        plan = self._model.generate(
            schema=VerificationPlan,
            system_prompt=PLAN_PROMPT,
            payload={
                "confirmed_task": task.model_dump(mode="json"),
                "validated_claims": [claim.model_dump(mode="json") for claim in extraction.claims],
                "required_operation_contract": verification_plan_contract(task),
            },
        )
        return validate_verification_plan(plan, task=task, claims=extraction.claims)

    def suggest_follow_up(self, result: VerificationResult) -> FollowUpAdvice:
        allowed_actions = {
            "PASS": ["NO_ACTION"],
            "FAIL": ["REQUEST_RESUBMISSION", "SWITCH_SERVICE", "MANUAL_REVIEW"],
            "INCONCLUSIVE": [
                "REFRESH_REFERENCE_EVIDENCE",
                "CROSS_CHECK_REFERENCE_SOURCE",
                "CONFIRM_TASK_SCOPE",
                "MANUAL_REVIEW",
            ],
        }[result.outcome.value]
        allowed_evidence_refs = sorted(
            {ref for finding in result.findings for ref in finding.evidence_refs}
        )
        advice = self._model.generate(
            schema=FollowUpAdvice,
            system_prompt=FOLLOW_UP_PROMPT,
            payload={
                "verification_result": result.model_dump(mode="json"),
                "allowed_actions": allowed_actions,
                "allowed_evidence_refs": allowed_evidence_refs,
            },
        )
        return validate_follow_up(advice, result)

    def explain_result(self, result: VerificationResult) -> ResultExplanation:
        explanation = self._model.generate(
            schema=ResultExplanation,
            system_prompt=EXPLANATION_PROMPT,
            payload={"verification_result": result.model_dump(mode="json")},
        )
        return validate_result_explanation(explanation, result)
