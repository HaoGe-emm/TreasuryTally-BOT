"""Team-controlled report services with explicit, isolated fault injection."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime

from eth_account import Account

from trust_receipt.commitments import create_delivery_commitment
from trust_receipt.commitments.eip712 import create_acceptance_signature
from trust_receipt.hashing import submission_hash
from trust_receipt.models import DeliveryCommitment, TaskCommitment
from trust_receipt.models.enums import EvidenceSource
from trust_receipt.models.submissions import ServiceSubmission
from trust_receipt.models.tasks import TaskSpec
from trust_receipt.models.transfers import TransferRecord
from trust_receipt.services.ports import FaultInjection, FaultMode, ReportDelivery
from trust_receipt.services.signatures import sign_report_hash


class TeamControlledReportService:
    """Deterministic local A/B adapter; it performs no network or arbitrary code execution."""

    def __init__(
        self,
        *,
        service_id: str,
        private_key: str,
        records_provider: Callable[[TaskSpec], tuple[TransferRecord, ...]],
        fault_by_attempt: dict[int, FaultMode] | None = None,
        clock=lambda: datetime.now(UTC),
    ) -> None:
        self._service_id = service_id
        self._private_key = private_key
        self._signer_address = Account.from_key(private_key).address
        self._records_provider = records_provider
        self._fault_by_attempt = dict(fault_by_attempt or {})
        self._clock = clock

    @property
    def service_id(self) -> str:
        return self._service_id

    @property
    def signer_address(self) -> str:
        return self._signer_address

    @staticmethod
    def _as_service(record: TransferRecord) -> TransferRecord:
        return record.model_copy(update={"source": EvidenceSource.SERVICE})

    def _apply_fault(
        self,
        records: tuple[TransferRecord, ...],
        mode: FaultMode,
    ) -> tuple[TransferRecord, ...]:
        if mode is FaultMode.OMIT_LAST_TRANSFER:
            return records[:-1]
        if mode is FaultMode.DUPLICATE_FIRST_TRANSFER and records:
            return (records[0], *records)
        return records

    def submit(
        self,
        task: TaskSpec,
        *,
        attempt: int,
    ) -> ReportDelivery:
        mode = self._fault_by_attempt.get(attempt, FaultMode.NONE)
        reference_transfers = self._records_provider(task)
        service_records = tuple(self._as_service(record) for record in reference_transfers)
        service_records = self._apply_fault(service_records, mode)
        total = sum(int(record.amount_base_units) for record in service_records)
        now = self._clock()
        unsigned = ServiceSubmission(
            schema_version="1.0",
            submission_id=f"{task.task_id}:{self.service_id}:attempt-{attempt}",
            task_id=task.task_id,
            service_id=self.service_id,
            service_version="m3-demo-1.0",
            attempt=attempt,
            claimed_total_base_units=str(total),
            claimed_count=len(service_records),
            transfers=service_records,
            report_text=json.dumps(
                {
                    "claimed_total_base_units": str(total),
                    "claimed_count": len(service_records),
                    "transfers": [record.model_dump(mode="json") for record in service_records],
                    "notice": "Team-controlled synthetic report; no production or personal data.",
                },
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ),
            created_at=now,
            report_hash="0x" + "0" * 64,
            signature=None,
        )
        report_hash = submission_hash(unsigned)
        submission = unsigned.model_copy(
            update={"report_hash": report_hash, "signature": sign_report_hash(report_hash, self._private_key)}
        )
        return ReportDelivery(
            submission=submission,
            fault_injection=FaultInjection(
                injected=mode is not FaultMode.NONE,
                mode=mode,
                label="synthetic-team-controlled-fault" if mode is not FaultMode.NONE else "no-fault",
            ),
        )

    def create_delivery_commitment(
        self,
        task_commitment: TaskCommitment,
        submission: ServiceSubmission,
        *,
        accepted_at: datetime,
        submitted_at: datetime,
        acceptance_signature: str | None = None,
    ) -> DeliveryCommitment:
        return create_delivery_commitment(
            task_commitment,
            submission,
            service_private_key=self._private_key,
            accepted_at=accepted_at,
            submitted_at=submitted_at,
            acceptance_signature=acceptance_signature,
        )

    def accept_task(self, task_commitment, *, attempt, accepted_at):
        return create_acceptance_signature(
            task_commitment, attempt=attempt, accepted_at=accepted_at,
            service_private_key=self._private_key,
        )
