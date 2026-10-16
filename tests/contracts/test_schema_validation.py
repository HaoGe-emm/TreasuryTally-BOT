from __future__ import annotations

from copy import deepcopy

import pytest
from jsonschema import Draft202012Validator, FormatChecker
from jsonschema import ValidationError as JsonSchemaError
from pydantic import ValidationError as PydanticError

from scripts.export_schemas import SCHEMA_MODELS, generate_schemas
from tests.contracts.samples import (
    ADDRESS_B,
    HASH_A,
    fixture_case_data,
    fixture_manifest_data,
    submission_data,
    task_data,
    top_level_samples,
    transfer_data,
)
from trust_receipt.models import (
    ServiceSubmission,
    TaskSpec,
    TransferRecord,
)

SCHEMAS = generate_schemas()
MODEL_BY_FILENAME = {filename: model for filename, _, model in SCHEMA_MODELS}
FORMAT_CHECKER = FormatChecker()


def validate_schema(filename: str, instance: object) -> None:
    Draft202012Validator(SCHEMAS[filename], format_checker=FORMAT_CHECKER).validate(instance)


@pytest.mark.parametrize(("filename", "sample"), top_level_samples().items())
def test_every_pydantic_valid_top_level_value_satisfies_its_schema(
    filename: str, sample: dict[str, object]
) -> None:
    normalized = MODEL_BY_FILENAME[filename].model_validate(sample).model_dump(mode="json")
    validate_schema(filename, normalized)


@pytest.mark.parametrize("missing", ["chain_id", "transaction_hash", "log_index"])
def test_transfer_event_identity_fields_are_required_by_schema(missing: str) -> None:
    data = transfer_data()
    del data[missing]
    with pytest.raises(JsonSchemaError):
        validate_schema("transfer_record.schema.json", data)


@pytest.mark.parametrize("amount", [120000, 120000.0, -1, "-1", "01", "1.5"])
def test_amount_schema_rejects_lossy_or_noncanonical_representations(amount: object) -> None:
    data = transfer_data(amount=amount)
    with pytest.raises(JsonSchemaError):
        validate_schema("transfer_record.schema.json", data)
    with pytest.raises(PydanticError):
        TransferRecord.model_validate(data)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("chain_id", 0),
        ("log_index", -1),
        ("block_number", -1),
        ("token_decimals", 256),
        ("source", "unknown"),
        ("token_address", "0x1234"),
        ("transaction_hash", "0x1234"),
    ],
)
def test_transfer_scalar_constraints_match_the_model(field: str, value: object) -> None:
    data = transfer_data()
    data[field] = value
    with pytest.raises(JsonSchemaError):
        validate_schema("transfer_record.schema.json", data)
    with pytest.raises(PydanticError):
        TransferRecord.model_validate(data)


def test_datetime_schema_requires_utc_and_model_rejects_non_utc() -> None:
    data = task_data()
    data["confirmed_at"] = "2026-10-06T08:00:00+08:00"
    with pytest.raises(JsonSchemaError):
        validate_schema("task_spec.schema.json", data)
    with pytest.raises(PydanticError):
        TaskSpec.model_validate(data)


def test_task_fixed_limits_and_extra_field_policy_are_in_schema() -> None:
    data = task_data()
    data["max_records"] = 201
    with pytest.raises(JsonSchemaError):
        validate_schema("task_spec.schema.json", data)

    data = task_data()
    data["unexpected"] = True
    with pytest.raises(JsonSchemaError):
        validate_schema("task_spec.schema.json", data)

    data = task_data()
    data["treasury_addresses"] = [ADDRESS_B, "0x" + "44" * 20, "0x" + "55" * 20]
    with pytest.raises(JsonSchemaError):
        validate_schema("task_spec.schema.json", data)


def test_submission_attempt_and_record_limit_are_in_schema() -> None:
    data = submission_data()
    data["attempt"] = 3
    with pytest.raises(JsonSchemaError):
        validate_schema("service_submission.schema.json", data)

    data = submission_data()
    data["transfers"] = [transfer_data() for _ in range(201)]
    with pytest.raises(JsonSchemaError):
        validate_schema("service_submission.schema.json", data)


def test_cross_field_invariants_remain_enforced_by_pydantic_and_documented_in_schema() -> None:
    reversed_range = task_data()
    reversed_range["start_block"] = 10
    reversed_range["end_block"] = 9
    with pytest.raises(PydanticError, match="start_block"):
        TaskSpec.model_validate(reversed_range)
    assert "start_block <= end_block" in SCHEMAS["task_spec.schema.json"]["x-contract-invariants"]

    wrong_source = submission_data()
    wrong_source["transfers"] = [transfer_data(source="rpc")]
    with pytest.raises(PydanticError, match="source=service"):
        ServiceSubmission.model_validate(wrong_source)
    assert "every transfers item has source=service" in SCHEMAS["service_submission.schema.json"][
        "x-contract-invariants"
    ]


def test_plan_and_fixture_enums_are_closed() -> None:
    case = fixture_case_data()
    case["expected"]["outcome"] = "UNKNOWN"
    with pytest.raises(JsonSchemaError):
        validate_schema("fixture_case.schema.json", case)

    manifest = fixture_manifest_data()
    manifest["fixtures"][0]["expected_outcome"] = "UNKNOWN"
    with pytest.raises(JsonSchemaError):
        validate_schema("fixture_manifest.schema.json", manifest)


def test_hash_and_address_shapes_are_not_relaxed_in_nested_schema() -> None:
    case = deepcopy(fixture_case_data())
    case["task_spec"]["spec_hash"] = HASH_A[:-1]
    with pytest.raises(JsonSchemaError):
        validate_schema("fixture_case.schema.json", case)
