"""Generate stable public JSON Schemas and validate fixture directories."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = REPOSITORY_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from jsonschema import Draft202012Validator, FormatChecker  # noqa: E402
from pydantic import BaseModel  # noqa: E402

from trust_receipt.agents.models import (  # noqa: E402
    ClaimExtraction,
    FollowUpAdvice,
    ResultExplanation,
    TaskSpecCandidate,
)
from trust_receipt.m9 import (  # noqa: E402
    PublicVerificationBundle,
    PublicVerificationResult,
    ReceiptRevision,
    RepairComparison,
    ReworkPackage,
)
from trust_receipt.models import (  # noqa: E402
    DeliveryCommitment,
    FixtureCase,
    FixtureManifest,
    FundFlowProjection,
    Receipt,
    ServiceSubmission,
    TaskCommitment,
    TaskSpec,
    TransferRecord,
    VerificationPlan,
    VerificationResult,
)
from trust_receipt.services.upload import UploadedReport  # noqa: E402

SCHEMA_VERSION = "1.0"
SCHEMA_DIALECT = "https://json-schema.org/draft/2020-12/schema"
SCHEMA_DIRECTORY = REPOSITORY_ROOT / "schemas" / "v1"
UTC_DATETIME_PATTERN = r".*(?:Z|[+-]00:00)$"

SCHEMA_MODELS: tuple[tuple[str, str, type[BaseModel]], ...] = (
    ("task_spec.schema.json", "task-spec", TaskSpec),
    ("transfer_record.schema.json", "transfer-record", TransferRecord),
    ("service_submission.schema.json", "service-submission", ServiceSubmission),
    ("verification_plan.schema.json", "verification-plan", VerificationPlan),
    ("verification_result.schema.json", "verification-result", VerificationResult),
    ("receipt.schema.json", "receipt", Receipt),
    ("fixture_case.schema.json", "fixture-case", FixtureCase),
    ("fixture_manifest.schema.json", "fixture-manifest", FixtureManifest),
    ("task_spec_candidate.schema.json", "task-spec-candidate", TaskSpecCandidate),
    ("claim_extraction.schema.json", "claim-extraction", ClaimExtraction),
    ("follow_up_advice.schema.json", "follow-up-advice", FollowUpAdvice),
    ("result_explanation.schema.json", "result-explanation", ResultExplanation),
    ("task_commitment.schema.json", "task-commitment", TaskCommitment),
    ("delivery_commitment.schema.json", "delivery-commitment", DeliveryCommitment),
    ("fund_flow_projection.schema.json", "fund-flow-projection", FundFlowProjection),
    ("uploaded_report.schema.json", "uploaded-report", UploadedReport),
    ("rework_package.schema.json", "rework-package", ReworkPackage),
    ("receipt_revision.schema.json", "receipt-revision", ReceiptRevision),
    ("repair_comparison.schema.json", "repair-comparison", RepairComparison),
    ("public_verification_result.schema.json", "public-verification-result", PublicVerificationResult),
    ("public_verification_bundle.schema.json", "public-verification-bundle", PublicVerificationBundle),
)

MODEL_INVARIANTS: Mapping[str, tuple[str, ...]] = {
    "TaskSpec": (
        "start_block <= end_block",
        "treasury_addresses and recipient_addresses are unique ignoring case",
        "exclusion rule IDs are unique",
    ),
    "ServiceSubmission": ("every transfers item has source=service",),
    "VerificationResult": (
        "finished_at >= started_at",
        "reference sources exclude service and preserve completeness",
        "outcome follows evidence completeness and confirmed error findings",
    ),
    "Receipt": ("nested task references equal task_spec.task_id",),
    "FixtureCase": (
        "submission.task_id equals task_spec.task_id",
        "reference and expected outcome preserve evidence sufficiency",
        "confirmed error findings determine FAIL for conclusive cases",
    ),
    "FixtureManifest": (
        "fixture IDs and files are unique",
        "each file is cases/<fixture_id>.json",
    ),
    "TaskSpecCandidate": (
        "missing_fields exactly identify null required task fields",
        "unresolved candidates require clarification questions",
        "resolved candidates contain no clarification questions",
    ),
    "ClaimExtraction": (
        "claim IDs and claim types are unique and values match their closed claim type",
        "ambiguous claims require clarification questions",
    ),
    "FollowUpAdvice": ("follow-up actions are restricted by deterministic outcome",),
    "ResultExplanation": ("application validation binds values and finding references to VerificationResult",),
    "TaskCommitment": ("signature binds the immutable task hash and explicit application domain",),
    "DeliveryCommitment": ("acceptance and delivery signatures bind task, service, attempt, and report hash",),
    "FundFlowProjection": ("visual state derives from existing findings and never changes the outcome",),
    "ReworkPackage": ("items contain only actionable confirmed error findings from one FAIL receipt",),
    "ReceiptRevision": (
        "attempt 1 is ORIGINAL without parent links",
        "attempt 2 links and supersedes attempt 1 without changing either Receipt 1.0 object",
    ),
    "RepairComparison": ("before is attempt 1 and after is attempt 2 for the same immutable task",),
    "PublicVerificationResult": (
        "missing necessary public evidence is INCONCLUSIVE and conflicting evidence is INVALID",
        "missing optional M8 commitment evidence remains explicitly UNVERIFIED",
    ),
}


class FixtureValidationError(ValueError):
    """Raised when a fixture directory violates the frozen M1 contract."""


def _add_utc_patterns(value: Any) -> None:
    if isinstance(value, dict):
        if value.get("format") == "date-time" and value.get("type") == "string":
            value["pattern"] = UTC_DATETIME_PATTERN
        for child in value.values():
            _add_utc_patterns(child)
    elif isinstance(value, list):
        for child in value:
            _add_utc_patterns(child)


def build_schema(model: type[BaseModel], kebab_name: str) -> dict[str, Any]:
    """Build one deterministic validation schema from the frozen public model."""
    schema = model.model_json_schema(mode="validation", ref_template="#/$defs/{model}")
    schema["$schema"] = SCHEMA_DIALECT
    schema["$id"] = f"urn:xinjv:schema:{SCHEMA_VERSION}:{kebab_name}"
    schema["title"] = model.__name__
    if model is PublicVerificationBundle:
        # Reuse the published contracts instead of duplicating the entire receipt graph.
        schema.pop("$defs", None)
        schema["properties"]["receipts"]["items"] = {
            "$ref": f"urn:xinjv:schema:{SCHEMA_VERSION}:receipt",
        }
        schema["properties"]["revisions"]["items"] = {
            "$ref": f"urn:xinjv:schema:{SCHEMA_VERSION}:receipt-revision",
        }
    invariants = MODEL_INVARIANTS.get(model.__name__)
    if invariants:
        schema["x-contract-invariants"] = list(invariants)
    _add_utc_patterns(schema)
    Draft202012Validator.check_schema(schema)
    return schema


def generate_schemas() -> dict[str, dict[str, Any]]:
    """Return every versioned schema keyed by its stable file name."""
    return {
        filename: build_schema(model, kebab_name)
        for filename, kebab_name, model in SCHEMA_MODELS
    }


def render_schema(schema: Mapping[str, Any]) -> str:
    """Serialize a schema with stable ordering and one trailing newline."""
    return json.dumps(schema, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def write_schemas(output_directory: Path = SCHEMA_DIRECTORY, *, check: bool = False) -> None:
    """Write schemas, or fail when committed files differ in check mode."""
    rendered = {name: render_schema(schema) for name, schema in generate_schemas().items()}
    if check:
        problems = [
            name
            for name, expected in rendered.items()
            if not (output_directory / name).is_file()
            or (output_directory / name).read_text(encoding="utf-8") != expected
        ]
        unexpected = (
            sorted(path.name for path in output_directory.glob("*.schema.json") if path.name not in rendered)
            if output_directory.is_dir()
            else []
        )
        if problems or unexpected:
            details = [*(f"outdated or missing: {name}" for name in problems)]
            details.extend(f"unexpected: {name}" for name in unexpected)
            raise RuntimeError("schema check failed; " + "; ".join(details))
        return

    output_directory.mkdir(parents=True, exist_ok=True)
    for name, content in rendered.items():
        (output_directory / name).write_text(content, encoding="utf-8", newline="\n")


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise FixtureValidationError(f"cannot read valid JSON from {path}: {exc}") from exc


def _validate_json_schema(instance: Any, schema: Mapping[str, Any], label: str) -> None:
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(instance), key=lambda error: tuple(str(part) for part in error.path))
    if errors:
        first = errors[0]
        location = "/".join(str(part) for part in first.absolute_path) or "<root>"
        raise FixtureValidationError(f"{label} fails JSON Schema at {location}: {first.message}")


def validate_fixture_directory(fixture_directory: Path) -> int:
    """Validate the frozen manifest, every referenced case, and their links."""
    fixture_directory = fixture_directory.resolve()
    manifest_path = fixture_directory / "manifest.json"
    manifest_data = _load_json(manifest_path)
    schemas = generate_schemas()
    _validate_json_schema(manifest_data, schemas["fixture_manifest.schema.json"], "manifest.json")
    try:
        manifest = FixtureManifest.model_validate(manifest_data)
    except ValueError as exc:
        raise FixtureValidationError(f"manifest.json fails Pydantic validation: {exc}") from exc

    expected_paths: set[Path] = set()
    for entry in manifest.fixtures:
        case_path = (fixture_directory / entry.file).resolve()
        if fixture_directory not in case_path.parents:
            raise FixtureValidationError(f"fixture path escapes its directory: {entry.file}")
        expected_paths.add(case_path)
        case_data = _load_json(case_path)
        _validate_json_schema(case_data, schemas["fixture_case.schema.json"], entry.file)
        try:
            case = FixtureCase.model_validate(case_data)
        except ValueError as exc:
            raise FixtureValidationError(f"{entry.file} fails Pydantic validation: {exc}") from exc
        linked_values = (
            ("fixture_id", case.fixture_id, entry.fixture_id),
            ("title", case.title, entry.title),
            ("tags", case.tags, entry.tags),
            ("expected_outcome", case.expected.outcome, entry.expected_outcome),
        )
        for field_name, actual, expected in linked_values:
            if actual != expected:
                raise FixtureValidationError(
                    f"{entry.file} {field_name} does not match manifest: {actual!r} != {expected!r}"
                )

    cases_directory = fixture_directory / "cases"
    actual_paths = set(cases_directory.glob("*.json")) if cases_directory.is_dir() else set()
    unexpected_paths = sorted(path.relative_to(fixture_directory).as_posix() for path in actual_paths - expected_paths)
    if unexpected_paths:
        raise FixtureValidationError(f"unlisted fixture case files: {', '.join(unexpected_paths)}")
    return len(manifest.fixtures)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail if committed schemas are not reproducible")
    parser.add_argument(
        "--validate-fixtures",
        type=Path,
        metavar="DIRECTORY",
        help="validate an M1 fixture directory after checking committed schemas",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    write_schemas(check=args.check or args.validate_fixtures is not None)
    if args.validate_fixtures is not None:
        count = validate_fixture_directory(args.validate_fixtures)
        print(f"Validated {count} fixture cases in {args.validate_fixtures}")
    elif args.check:
        print(f"Validated {len(SCHEMA_MODELS)} reproducible schemas in {SCHEMA_DIRECTORY}")
    else:
        print(f"Wrote {len(SCHEMA_MODELS)} schemas to {SCHEMA_DIRECTORY}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
