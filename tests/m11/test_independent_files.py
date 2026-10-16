"""Permanent second-task inputs remain executable with the same public entry points."""

from __future__ import annotations

import json
from pathlib import Path

from scripts.m11.evaluate_report import evaluate_report
from scripts.m11.preflight import load_case_bundle
from trust_receipt.hashing import content_hash
from trust_receipt.models import SourceDescriptor
from trust_receipt.orchestration import StaticEvidenceProvider
from trust_receipt.verification import ReferenceEvidence, ReferencePage, ReferenceStream

CASE_DIRECTORY = Path(__file__).resolve().parents[2] / "fixtures" / "m11"


def test_committed_artifact_hashes_identify_all_case_inputs_and_rpc_inventory():
    manifest = json.loads((CASE_DIRECTORY / "artifact-hashes.json").read_text(encoding="utf-8"))
    assert manifest["algorithm"] == "sha256"
    inputs = {
        path.relative_to(CASE_DIRECTORY).as_posix()
        for path in CASE_DIRECTORY.rglob("*.json") if path.name != "artifact-hashes.json"
    }
    assert set(manifest["files"]) == inputs
    for relative_path, expected_hash in manifest["files"].items():
        assert content_hash((CASE_DIRECTORY / relative_path).read_bytes()) == expected_hash


def test_second_task_files_select_a_different_real_event_and_preserve_amount_error():
    original = load_case_bundle(CASE_DIRECTORY)
    independent = load_case_bundle(CASE_DIRECTORY, manifest_filename="independent-case.json")
    assert independent.task.spec_hash != original.task.spec_hash
    assert independent.task.treasury_addresses != original.task.treasury_addresses
    assert independent.task.recipient_addresses != original.task.recipient_addresses
    assert independent.corrected_report.transfers[0].event_key != original.corrected_report.transfers[0].event_key
    assert independent.reference_transfers == original.reference_transfers
    source = SourceDescriptor.model_validate({
        "source": "rpc", "source_id": "m11-committed-inventory", "complete": True,
        "retrieved_at": independent.manifest["provenance"]["observed_at"], "details": {"records": 6},
    })
    evidence = ReferenceEvidence(
        streams=(ReferenceStream(
            source=source,
            pages=(ReferencePage(cursor=None, next_cursor=None, transfers=independent.reference_transfers),),
        ),),
        evidence_sufficient=True, insufficiency_reason=None,
    )
    for report_kind, outcome in [("error", "FAIL"), ("corrected", "PASS")]:
        result = evaluate_report(
            rpc_url="https://unused.invalid",
            task_spec_path=CASE_DIRECTORY / independent.manifest["task_spec"],
            report_path=CASE_DIRECTORY / independent.manifest["reports"][report_kind],
            evidence_provider=StaticEvidenceProvider(evidence),
        )
        assert result["outcome"] == outcome
        assert result["calculated_total_base_units"] == "321794352786"
