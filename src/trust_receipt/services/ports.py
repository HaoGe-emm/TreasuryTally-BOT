"""Provider-neutral report service boundary."""

from __future__ import annotations

from enum import StrEnum
from typing import Protocol

from pydantic import StrictBool

from trust_receipt.models.base import DomainModel, NonEmptyText
from trust_receipt.models.submissions import ServiceSubmission
from trust_receipt.models.tasks import TaskSpec


class FaultMode(StrEnum):
    NONE = "NONE"
    OMIT_LAST_TRANSFER = "OMIT_LAST_TRANSFER"
    DUPLICATE_FIRST_TRANSFER = "DUPLICATE_FIRST_TRANSFER"


class FaultInjection(DomainModel):
    """Explicit synthetic-test metadata kept outside submitted evidence."""

    injected: StrictBool
    mode: FaultMode
    label: NonEmptyText


class ReportDelivery(DomainModel):
    submission: ServiceSubmission
    fault_injection: FaultInjection


class ReportService(Protocol):
    @property
    def service_id(self) -> str: ...

    @property
    def signer_address(self) -> str: ...

    def submit(
        self,
        task: TaskSpec,
        *,
        attempt: int,
    ) -> ReportDelivery: ...

    def accept_task(self, task_commitment, *, attempt, accepted_at): ...

    def create_delivery_commitment(
        self, task_commitment, submission, *, accepted_at, submitted_at, acceptance_signature=None,
    ): ...
