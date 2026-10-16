"""UI-free use cases for report submission and deterministic verification."""

from trust_receipt.orchestration.m5 import (
    AttemptExecution,
    M5Workflow,
    StaticEvidenceProvider,
    candidate_from_fixture,
    eligible_records,
    evidence_from_fixture,
    load_vertical_demo_fixture,
)
from trust_receipt.orchestration.m6 import M6Workflow
from trust_receipt.orchestration.m8 import M8CommitmentWorkflow
from trust_receipt.orchestration.workflow import (
    ReferenceEvidenceProvider,
    VerificationOrchestrator,
    is_negative_feedback_candidate,
)

__all__ = [
    "AttemptExecution",
    "M5Workflow",
    "M6Workflow",
    "M8CommitmentWorkflow",
    "ReferenceEvidenceProvider",
    "StaticEvidenceProvider",
    "VerificationOrchestrator",
    "candidate_from_fixture",
    "eligible_records",
    "evidence_from_fixture",
    "is_negative_feedback_candidate",
    "load_vertical_demo_fixture",
]
