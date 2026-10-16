"""Exercise M11 input rejection, safe output, and recovery through the public CLI boundary."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.m11 import evaluate_report as evaluator
from scripts.m11.input_policy import read_bounded_report, validate_read_options
from scripts.m11.preflight import load_case_bundle
from trust_receipt.chain import RpcReferenceEvidenceProvider
from trust_receipt.hashing import task_spec_hash
from trust_receipt.integrations.errors import IntegrationError, IntegrationErrorCode

CASE_DIRECTORY = Path(__file__).resolve().parents[2] / "fixtures" / "m11"


@pytest.mark.parametrize("timeout,confirmations", [
    (float("nan"), 2), (float("inf"), 2), (0, 2), (31, 2), (30, -1), (30, 129), (30, True),
])
def test_invalid_read_options_are_rejected(timeout, confirmations):
    with pytest.raises(ValueError):
        validate_read_options(timeout_seconds=timeout, confirmations=confirmations)


def test_oversized_report_is_rejected_before_parsing(tmp_path):
    path = tmp_path / "oversized.json"
    path.write_bytes(b" " * 1_000_001)
    with pytest.raises(ValueError, match="at most 1 MB"):
        read_bounded_report(path)


def test_other_chain_is_rejected_before_rpc(tmp_path):
    bundle = load_case_bundle(CASE_DIRECTORY)
    unsigned = bundle.task.model_copy(update={"chain_id": 1})
    task = unsigned.model_copy(update={"spec_hash": task_spec_hash(unsigned)})
    task_path = tmp_path / "mainnet-task.json"
    task_path.write_text(task.model_dump_json(), encoding="utf-8")
    with pytest.raises(ValueError, match="supports Sepolia"):
        evaluator.evaluate_report(
            rpc_url="https://unused.invalid",
            task_spec_path=task_path,
            report_path=CASE_DIRECTORY / bundle.manifest["reports"]["corrected"],
        )


def test_invalid_input_is_redacted_at_cli_boundary(tmp_path, capsys):
    path = tmp_path / "invalid.json"
    path.write_text(json.dumps({"secret": "do-not-echo-this-api-token"}), encoding="utf-8")
    code = evaluator.main([
        "--rpc-url", "https://user:password@unused.invalid/api-token",
        "--task-spec", str(CASE_DIRECTORY / "task-spec.json"),
        "--report", str(path),
    ])
    output = capsys.readouterr().out
    assert code == 1
    assert json.loads(output)["status"] == "INCONCLUSIVE"
    assert "do-not-echo" not in output
    assert "password" not in output
    assert "api-token" not in output


def test_cli_rpc_failure_then_recovery_retains_report_and_scope(monkeypatch, capsys):
    bundle = load_case_bundle(CASE_DIRECTORY)

    class RecoveringProbe:
        fail = True

        def latest_block(self):
            if self.fail:
                raise IntegrationError(
                    IntegrationErrorCode.UNAVAILABLE,
                    "https://user:private-token@unavailable.invalid",
                )
            return bundle.task.end_block + 10

        def fetch_transfer_pages(self, **kwargs):
            assert kwargs["from_block"] == bundle.task.start_block
            assert kwargs["to_block"] == bundle.task.end_block
            return (bundle.reference_transfers,)

    probe = RecoveringProbe()
    provider = RpcReferenceEvidenceProvider(
        "https://unused.invalid", expected_chain_id=bundle.task.chain_id, rpc_probe=probe,
    )
    monkeypatch.setattr(evaluator, "RpcReferenceEvidenceProvider", lambda *args, **kwargs: provider)
    report_path = CASE_DIRECTORY / bundle.manifest["reports"]["corrected"]
    original_bytes = report_path.read_bytes()
    args = [
        "--rpc-url", "https://unused.invalid",
        "--task-spec", str(CASE_DIRECTORY / "task-spec.json"),
        "--report", str(report_path),
    ]
    assert evaluator.main(args) == 1
    failed_output = capsys.readouterr().out
    failed = json.loads(failed_output)
    assert failed["ok"] is False
    assert failed["outcome"] == "INCONCLUSIVE"
    assert failed["calculated_total_base_units"] is None
    assert "private-token" not in failed_output

    probe.fail = False
    assert evaluator.main(args) == 0
    recovered = json.loads(capsys.readouterr().out)
    assert recovered["ok"] is True
    assert recovered["outcome"] == "PASS"
    assert recovered["spec_hash"] == failed["spec_hash"] == bundle.task.spec_hash
    assert recovered["calculated_total_base_units"] == "180674489737"
    assert report_path.read_bytes() == original_bytes
