from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.export_schemas import FixtureValidationError, validate_fixture_directory
from tests.contracts.samples import fixture_case_data, fixture_manifest_data


def write_fixture_directory(root: Path) -> Path:
    fixture_directory = root / "m1"
    cases_directory = fixture_directory / "cases"
    cases_directory.mkdir(parents=True)
    manifest = fixture_manifest_data()
    (fixture_directory / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    for entry in manifest["fixtures"]:
        case = fixture_case_data(entry["fixture_id"])
        (fixture_directory / entry["file"]).write_text(
            json.dumps(case, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    return fixture_directory


def test_fixture_validation_entrypoint_accepts_exact_manifest_and_twelve_cases(tmp_path: Path) -> None:
    fixture_directory = write_fixture_directory(tmp_path)
    assert validate_fixture_directory(fixture_directory) == 12


def test_fixture_validation_rejects_manifest_case_metadata_drift(tmp_path: Path) -> None:
    fixture_directory = write_fixture_directory(tmp_path)
    case_path = fixture_directory / "cases" / "correct-report-01.json"
    case = json.loads(case_path.read_text(encoding="utf-8"))
    case["title"] = "Different title"
    case_path.write_text(json.dumps(case), encoding="utf-8")

    with pytest.raises(FixtureValidationError, match="title does not match manifest"):
        validate_fixture_directory(fixture_directory)


def test_fixture_validation_rejects_unlisted_case_file(tmp_path: Path) -> None:
    fixture_directory = write_fixture_directory(tmp_path)
    extra = fixture_directory / "cases" / "unlisted-case.json"
    extra.write_text(json.dumps(fixture_case_data("unlisted-case")), encoding="utf-8")

    with pytest.raises(FixtureValidationError, match="unlisted fixture case files"):
        validate_fixture_directory(fixture_directory)


def test_fixture_validation_rejects_schema_invalid_case_before_link_checks(tmp_path: Path) -> None:
    fixture_directory = write_fixture_directory(tmp_path)
    case_path = fixture_directory / "cases" / "correct-report-01.json"
    case = json.loads(case_path.read_text(encoding="utf-8"))
    case["submission"]["claimed_total_base_units"] = 120000.0
    case_path.write_text(json.dumps(case), encoding="utf-8")

    with pytest.raises(FixtureValidationError, match="fails JSON Schema"):
        validate_fixture_directory(fixture_directory)
