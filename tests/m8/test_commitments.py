from datetime import UTC, datetime, timedelta

import pytest
from eth_account import Account
from jsonschema import Draft202012Validator, FormatChecker

from scripts.export_schemas import generate_schemas
from trust_receipt.commitments import (
    create_delivery_commitment,
    create_task_commitment,
    verify_delivery_commitment,
    verify_task_commitment,
)


def test_task_and_delivery_eip712_signatures_bind_all_critical_fields(m5_components) -> None:
    _, candidate, _, workflow, service = m5_components
    task = workflow.confirm_task(candidate)
    execution = workflow.run_attempt(task.task_id, service)
    requester_key = Account.create().key.to_0x_hex()
    now = datetime(2026, 10, 7, tzinfo=UTC)
    task_commitment = create_task_commitment(
        task,
        service_id=service.service_id,
        requester_private_key=requester_key,
        created_at=now,
        expires_at=now + timedelta(days=1),
        commitment_id="commitment-test",
    )
    delivery = service.create_delivery_commitment(
        task_commitment,
        execution.submission,
        accepted_at=now,
        submitted_at=now,
    )

    assert verify_task_commitment(task_commitment, task)
    assert verify_delivery_commitment(
        delivery,
        task_commitment,
        execution.submission,
        expected_signer=service.signer_address,
    )
    assert task_commitment.anchor.status.value == "NOT_SUBMITTED"

    tampered_task = task_commitment.model_copy(update={"service_id": "other-service"})
    assert not verify_task_commitment(tampered_task, task)
    tampered_delivery = delivery.model_copy(update={"attempt": 2})
    assert not verify_delivery_commitment(
        tampered_delivery,
        task_commitment,
        execution.submission,
        expected_signer=service.signer_address,
    )


def test_delivery_rejects_wrong_service_signer(m5_components) -> None:
    _, candidate, _, workflow, service = m5_components
    task = workflow.confirm_task(candidate)
    execution = workflow.run_attempt(task.task_id, service)
    now = datetime(2026, 10, 7, tzinfo=UTC)
    task_commitment = create_task_commitment(
        task,
        service_id=service.service_id,
        requester_private_key=Account.create().key.to_0x_hex(),
        created_at=now,
    )
    wrong_key = Account.create().key.to_0x_hex()
    delivery = create_delivery_commitment(
        task_commitment,
        execution.submission,
        service_private_key=wrong_key,
        accepted_at=now,
        submitted_at=now,
    )

    assert not verify_delivery_commitment(
        delivery,
        task_commitment,
        execution.submission,
        expected_signer=service.signer_address,
    )


def test_commitment_rejection_happens_before_attempt_is_persisted(m5_components) -> None:
    _, candidate, repository, workflow, service = m5_components
    task = workflow.confirm_task(candidate)

    def reject(_submission):
        raise ValueError("commitment signer is not authorized")

    with pytest.raises(ValueError, match="not authorized"):
        workflow.run_attempt(task.task_id, service, pre_persist_validator=reject)

    assert repository.list_attempts(task.task_id) == ()


def test_m8_artifacts_satisfy_exported_json_schemas(m5_components) -> None:
    _, candidate, _, workflow, service = m5_components
    task = workflow.confirm_task(candidate)
    execution = workflow.run_attempt(task.task_id, service)
    now = datetime(2026, 10, 7, tzinfo=UTC)
    task_commitment = create_task_commitment(
        task,
        service_id=service.service_id,
        requester_private_key=Account.create().key.to_0x_hex(),
        created_at=now,
    )
    delivery = service.create_delivery_commitment(
        task_commitment,
        execution.submission,
        accepted_at=now,
        submitted_at=now,
    )
    schemas = generate_schemas()
    artifacts = {
        "task_commitment.schema.json": task_commitment,
        "delivery_commitment.schema.json": delivery,
        "fund_flow_projection.schema.json": execution.fund_flow,
    }

    for filename, artifact in artifacts.items():
        assert artifact is not None
        Draft202012Validator(schemas[filename], format_checker=FormatChecker()).validate(
            artifact.model_dump(mode="json")
        )
