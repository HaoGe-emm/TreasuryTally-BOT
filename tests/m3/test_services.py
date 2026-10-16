from __future__ import annotations

from trust_receipt.hashing import verify_submission_hash
from trust_receipt.services import FaultMode, TeamControlledReportService, verify_submission_signature


def test_team_service_signs_submission_and_exposes_fault_metadata(
    hashed_task, eligible_service_records, fixed_time, private_key_a
) -> None:
    service = TeamControlledReportService(
        service_id="service-a",
        private_key=private_key_a,
        records_provider=lambda task: eligible_service_records,
        fault_by_attempt={1: FaultMode.OMIT_LAST_TRANSFER},
        clock=lambda: fixed_time,
    )
    delivery = service.submit(hashed_task, attempt=1)
    assert verify_submission_hash(delivery.submission)
    assert verify_submission_signature(delivery.submission, service.signer_address)
    assert delivery.fault_injection.injected is True
    assert delivery.fault_injection.mode is FaultMode.OMIT_LAST_TRANSFER
    assert all(record.source.value == "service" for record in delivery.submission.transfers)


def test_signature_fails_for_tampering_or_wrong_service(
    hashed_task, eligible_service_records, fixed_time, private_key_a, private_key_b
) -> None:
    service = TeamControlledReportService(
        service_id="service-a",
        private_key=private_key_a,
        records_provider=lambda task: eligible_service_records,
        clock=lambda: fixed_time,
    )
    submission = service.submit(hashed_task, attempt=1).submission
    wrong_service = TeamControlledReportService(
        service_id="service-b",
        private_key=private_key_b,
        records_provider=lambda task: eligible_service_records,
        clock=lambda: fixed_time,
    )
    wrong_signer = wrong_service.signer_address
    assert not verify_submission_signature(submission, wrong_signer)
    tampered = submission.model_copy(update={"report_hash": "0x" + "ff" * 32})
    assert not verify_submission_signature(tampered, service.signer_address)
