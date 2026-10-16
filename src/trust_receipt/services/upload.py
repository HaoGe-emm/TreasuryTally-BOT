"""Strict private report intake; a local signature never authenticates the author."""

from __future__ import annotations

import json
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from eth_account import Account
from pydantic import Field, model_validator

from trust_receipt.commitments import create_delivery_commitment
from trust_receipt.commitments.eip712 import create_acceptance_signature
from trust_receipt.hashing import content_hash, submission_hash
from trust_receipt.models import EvidenceSource, ServiceSubmission, TaskSpec, TransferRecord
from trust_receipt.models.base import DecimalIntegerString, DomainModel, NonNegativeInt
from trust_receipt.services.ports import FaultInjection, FaultMode, ReportDelivery
from trust_receipt.services.signatures import sign_report_hash

MAX_REPORT_BYTES = 1_000_000


class UploadedReport(DomainModel):
    schema_version: Literal["1.0"]
    claimed_total_base_units: DecimalIntegerString
    claimed_count: NonNegativeInt
    transfers: tuple[TransferRecord, ...] = Field(max_length=200)

    @model_validator(mode="after")
    def require_service_source(self) -> UploadedReport:
        if any(record.source is not EvidenceSource.SERVICE for record in self.transfers):
            raise ValueError("uploaded report records must explicitly use source=service")
        return self


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON object keys are forbidden")
        result[key] = value
    return result


def parse_report(payload: bytes) -> UploadedReport:
    if not payload or len(payload) > MAX_REPORT_BYTES:
        raise ValueError("report must be nonempty and at most 1 MB")
    try:
        decoded = json.loads(payload.decode("utf-8"), object_pairs_hook=_unique_object)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("report must be a UTF-8 JSON object in UploadedReport format") from error
    return UploadedReport.model_validate(decoded)


def retain_original(payload: bytes, directory: Path) -> str:
    if not payload or len(payload) > MAX_REPORT_BYTES:
        raise ValueError("report must be nonempty and at most 1 MB")
    digest = content_hash(payload)
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"{digest[2:]}.json"
    descriptor, temporary_name = tempfile.mkstemp(prefix=".original-", suffix=".tmp", dir=directory)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        # A hard link publishes complete bytes without ever replacing existing evidence.
        # The temporary file is on the same filesystem and is already closed.
        try:
            os.link(temporary, target)
        except FileExistsError:
            if target.read_bytes() != payload:
                raise ValueError("private report content hash collision or corrupt file") from None
    finally:
        temporary.unlink()
    return digest


class UploadedReportService:
    service_id = "uploaded-report-intake"
    identity_scheme = "local-upload-intake"
    identity_name = "Uploaded report · local intake signature (author unverified)"

    def __init__(self, payload: bytes, *, private_directory: Path) -> None:
        self.original_hash = retain_original(payload, private_directory)
        self._report = parse_report(payload)
        self._text = payload.decode("utf-8")
        self._key = Account.create().key
        self.signer_address = Account.from_key(self._key).address

    def submit(self, task: TaskSpec, *, attempt: int) -> ReportDelivery:
        unsigned = ServiceSubmission(
            schema_version="1.0",
            submission_id=f"{task.task_id}:upload:{attempt}:{self.original_hash[2:18]}",
            task_id=task.task_id,
            service_id=self.service_id,
            service_version="upload-intake-1.0",
            attempt=attempt,
            claimed_total_base_units=self._report.claimed_total_base_units,
            claimed_count=self._report.claimed_count,
            transfers=self._report.transfers,
            report_text=self._text,
            created_at=datetime.now(UTC),
            report_hash="0x" + "0" * 64,
            signature=None,
        )
        digest = submission_hash(unsigned)
        submission = unsigned.model_copy(update={
            "report_hash": digest,
            "signature": sign_report_hash(digest, self._key),
        })
        return ReportDelivery(
            submission=submission,
            fault_injection=FaultInjection(injected=False, mode=FaultMode.NONE, label="uploaded-original-no-fault"),
        )

    def create_delivery_commitment(
        self, task_commitment, submission, *, accepted_at, submitted_at, acceptance_signature=None,
    ):
        return create_delivery_commitment(
            task_commitment, submission, service_private_key=self._key,
            accepted_at=accepted_at, submitted_at=submitted_at,
            acceptance_signature=acceptance_signature,
        )

    def accept_task(self, task_commitment, *, attempt, accepted_at):
        return create_acceptance_signature(
            task_commitment, attempt=attempt, accepted_at=accepted_at, service_private_key=self._key,
        )
