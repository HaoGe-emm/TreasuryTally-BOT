"""Storage-facing state and immutable read models."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from trust_receipt.models.submissions import ServiceSubmission
from trust_receipt.models.tasks import TaskSpec
from trust_receipt.models.verification import VerificationResult
from trust_receipt.services.ports import FaultInjection


class TaskState(StrEnum):
    CONFIRMED = "CONFIRMED"
    REQUESTED = "REQUESTED"
    SUBMITTED = "SUBMITTED"
    VERIFYING = "VERIFYING"
    PASS = "PASS"
    FAIL = "FAIL"
    INCONCLUSIVE = "INCONCLUSIVE"
    RETRY_REQUESTED = "RETRY_REQUESTED"


@dataclass(frozen=True)
class AttemptRecord:
    submission: ServiceSubmission
    fault_injection: FaultInjection
    verification_result: VerificationResult | None


@dataclass(frozen=True)
class StoredTask:
    task: TaskSpec
    state: TaskState


class AttemptBlockReason(StrEnum):
    IN_FLIGHT = "IN_FLIGHT"
    PASSED = "PASSED"
    ATTEMPTS_EXHAUSTED = "ATTEMPTS_EXHAUSTED"
    STATE_CONFLICT = "STATE_CONFLICT"
    MISSING_RECEIPT = "MISSING_RECEIPT"
    RECEIPT_CONFLICT = "RECEIPT_CONFLICT"


@dataclass(frozen=True)
class AttemptStatus:
    """Read-only persisted progress, not a reservation or execution permission."""

    task_id: str
    state: TaskState
    persisted_attempts: int
    completed_attempts: int
    in_flight_attempt: int | None
    next_attempt: int | None
    blocking_reason: AttemptBlockReason | None
